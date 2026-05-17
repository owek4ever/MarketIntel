"""Performance Intelligence router."""

from fastapi import APIRouter, Depends, Query

from app.db.pool import acquire
from app.dependencies import get_current_user

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/summary")
async def performance_summary(user: dict = Depends(get_current_user)):
    """All competitors — page speed aggregate scores."""
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                c.id AS competitor_id, c.domain,
                cps.total_pages, cps.avg_score,
                cps.median_score, cps.worst_page_score, cps.best_page_score
            FROM competitor_page_scores cps
            JOIN competitors c ON c.id = cps.competitor_id
            ORDER BY cps.avg_score DESC
            """
        )
    return [dict(r) for r in rows]


@router.get("/pages/{competitor_id}")
async def performance_pages(
    competitor_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """Per-page composite scores (SEO + speed) for a competitor."""
    offset = (page - 1) * page_size
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                p.url, p.page_type,
                pos.seo_score, pos.page_speed_score, pos.overall_score
            FROM page_overall_scores pos
            JOIN pages p ON pos.url_hash = p.url_hash
            WHERE pos.competitor_id = $1
            ORDER BY pos.overall_score DESC
            LIMIT $2 OFFSET $3
            """,
            competitor_id,
            page_size,
            offset,
        )
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM pages WHERE competitor_id = $1", competitor_id
        )
    return {"total": total, "page": page, "page_size": page_size, "items": [dict(r) for r in rows]}


@router.get("/page-types/{competitor_id}")
async def page_type_scores(competitor_id: int, user: dict = Depends(get_current_user)):
    """Average overall score broken down by page type for a competitor."""
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT page_type, AVG(overall_score) AS avg_score
            FROM page_type_scores
            WHERE competitor_id = $1
            GROUP BY page_type
            ORDER BY avg_score DESC
            """,
            competitor_id,
        )
    return [dict(r) for r in rows]


@router.get("/speed-breakdown/{competitor_id}")
async def speed_breakdown(competitor_id: int, user: dict = Depends(get_current_user)):
    """Raw page speed metric averages (TTFB, FP, DOM…) for a competitor."""
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                AVG(ttfb_score)  AS avg_ttfb_score,
                AVG(fp_score)    AS avg_fp_score,
                AVG(di_score)    AS avg_di_score,
                AVG(dc_score)    AS avg_dc_score,
                AVG(ps_score)    AS avg_ps_score,
                AVG(dom_score)   AS avg_dom_score,
                AVG(res_score)   AS avg_res_score,
                AVG(page_speed_score) AS avg_page_speed_score
            FROM page_performance_scores
            WHERE competitor_id = $1
            """,
            competitor_id,
        )
    return dict(row) if row else {}
