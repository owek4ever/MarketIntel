from fastapi import APIRouter, Depends, HTTPException
from app.db.pool import acquire
from app.dependencies import get_current_user
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

router = APIRouter(prefix="/reports", tags=["reports"])

class ReportCreate(BaseModel):
    title: str
    filters: dict

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
            import_json(payload.filters)
        )
    return dict(row)

@router.delete("/{report_id}", status_code=204)
async def delete_report(report_id: UUID, user: dict = Depends(get_current_user)):
    async with acquire() as conn:
        await conn.execute(
            "DELETE FROM dashboard.saved_reports WHERE id = $1 AND user_id = $2",
            report_id,
            user["id"],
        )

def import_json(data: dict) -> str:
    import json
    return json.dumps(data)
