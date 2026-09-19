from fastapi import APIRouter, Depends, HTTPException
from app.db.pool import acquire
from app.dependencies import get_current_user
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
import json

router = APIRouter(prefix="/reports", tags=["reports"])

class ReportCreate(BaseModel):
    title: str
    filters: dict

class ReportGenerate(BaseModel):
    report_type: str  # "competitor_platform" | "social_media" | "seo_gap" | "refresh_views"
    competitor_id: int | None = None
    title: str | None = None
    extra: dict | None = None

@router.get("/")
async def list_reports(user: dict = Depends(get_current_user)):
    async with acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, title, filters, created_at FROM dashboard.saved_reports WHERE user_id = $1 ORDER BY created_at DESC",
            user["id"],
        )
    return [dict(r) for r in rows]

@router.post("/")
async def create_report(payload: ReportCreate, user: dict = Depends(get_current_user)):
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO dashboard.saved_reports (user_id, title, filters)
            VALUES ($1, $2, $3)
            RETURNING id, title, filters, created_at
            """,
            user["id"],
            payload.title,
            json.dumps(payload.filters),
        )
    return dict(row)

@router.post("/generate")
async def generate_report(payload: ReportGenerate, user: dict = Depends(get_current_user)):
    """Generate a report by type. Returns report data from the database."""
    report_data = {}

    async with acquire() as conn:
        if payload.report_type == "social_media" and payload.competitor_id:
            accounts = await conn.fetch(
                "SELECT * FROM social_accounts WHERE competitor_id = $1",
                payload.competitor_id,
            )
            posts = await conn.fetch(
                """SELECT sp.* FROM social_posts sp
                   JOIN social_accounts sa ON sa.id = sp.account_id
                   WHERE sa.competitor_id = $1
                   ORDER BY sp.like_count + sp.comment_count DESC LIMIT 20""",
                payload.competitor_id,
            )
            scores = await conn.fetch(
                "SELECT * FROM competitor_social_score WHERE competitor_id = $1",
                payload.competitor_id,
            )
            report_data = {
                "type": "social_media",
                "competitor_id": payload.competitor_id,
                "accounts": [dict(r) for r in accounts],
                "top_posts": [dict(r) for r in posts],
                "scores": [dict(r) for r in scores],
            }

        elif payload.report_type == "seo_gap":
            summary = await conn.fetch(
                """SELECT c.domain, cs.avg_seo_score, cs.avg_content_score,
                          cs.avg_technical_score
                   FROM competitor_seo_summary cs
                   JOIN competitors c ON c.id = cs.competitor_id
                   ORDER BY cs.avg_seo_score DESC"""
            )
            report_data = {
                "type": "seo_gap",
                "competitors": [dict(r) for r in summary],
            }

        elif payload.report_type == "competitor_platform" and payload.competitor_id:
            comp = await conn.fetchrow(
                "SELECT * FROM competitors WHERE id = $1",
                payload.competitor_id,
            )
            pages = await conn.fetch(
                "SELECT COUNT(*) as cnt FROM pages WHERE competitor_id = $1",
                payload.competitor_id,
            )
            products = await conn.fetch(
                "SELECT COUNT(*) as cnt FROM products WHERE competitor_id = $1",
                payload.competitor_id,
            )
            report_data = {
                "type": "competitor_platform",
                "competitor": dict(comp) if comp else None,
                "page_count": pages[0]["cnt"] if pages else 0,
                "product_count": products[0]["cnt"] if products else 0,
            }

        else:
            raise HTTPException(status_code=400, detail=f"Unknown report type: {payload.report_type}")

        # Save the report
        title = payload.title or f"{payload.report_type.replace('_', ' ').title()} Report"
        row = await conn.fetchrow(
            """
            INSERT INTO dashboard.saved_reports (user_id, title, filters)
            VALUES ($1, $2, $3)
            RETURNING id, title, created_at
            """,
            user["id"],
            title,
            json.dumps({"type": payload.report_type, **(payload.extra or {})}),
        )

    return {"report": report_data, "saved": dict(row)}


@router.delete("/{report_id}", status_code=204)
async def delete_report(report_id: UUID, user: dict = Depends(get_current_user)):
    async with acquire() as conn:
        await conn.execute(
            "DELETE FROM dashboard.saved_reports WHERE id = $1 AND user_id = $2",
            report_id,
            user["id"],
        )
