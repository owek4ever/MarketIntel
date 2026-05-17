"""Competitors router."""

from fastapi import APIRouter, Depends, Query

from app.db.pool import acquire
from app.dependencies import get_current_user

router = APIRouter(prefix="/competitors", tags=["competitors"])


@router.get("")
async def list_competitors(user: dict = Depends(get_current_user)):
    """All competitors with their latest composite scores."""
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                c.id,
                c.domain,
                c.name,
                c.created_at,
                cs.avg_seo_score   AS seo_score,
                cps.avg_score      AS perf_score,
                css.score          AS social_score,
                cms.final_score    AS market_score,
                (SELECT COUNT(*) FROM pages p WHERE p.competitor_id = c.id) AS page_count,
                (SELECT COUNT(*) FROM products pr WHERE pr.competitor_id = c.id) AS product_count
            FROM competitors c
            LEFT JOIN competitor_seo_summary cs ON cs.competitor_id = c.id
            LEFT JOIN competitor_page_scores cps ON cps.competitor_id = c.id
            LEFT JOIN (
                SELECT competitor_id,
                    ROUND(AVG(score)::numeric, 4) AS score
                FROM competitor_social_score
                GROUP BY competitor_id
            ) css ON css.competitor_id = c.id
            LEFT JOIN competitor_market_scores cms ON cms.competitor_id = c.id
            ORDER BY c.domain
            """
        )
    return [dict(r) for r in rows]


@router.get("/{competitor_id}")
async def get_competitor(competitor_id: int, user: dict = Depends(get_current_user)):
    """Single competitor with all score dimensions."""
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                c.id, c.domain, c.name, c.metadata, c.created_at,
                cs.avg_seo_score, cs.median_seo_score,
                cs.avg_content_score, cs.avg_on_page_score,
                cs.avg_technical_score, cs.avg_ux_score,
                cps.avg_score      AS avg_perf_score,
                cps.median_score   AS median_perf_score,
                cps.total_pages,
                cms.final_score    AS market_score,
                cms.coverage_score, cms.category_balance_score,
                cms.assortment_score, cms.availability_score
            FROM competitors c
            LEFT JOIN competitor_seo_summary cs ON cs.competitor_id = c.id
            LEFT JOIN competitor_page_scores cps ON cps.competitor_id = c.id
            LEFT JOIN competitor_market_scores cms ON cms.competitor_id = c.id
            WHERE c.id = $1
            """,
            competitor_id,
        )
    if row is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Competitor not found")
    return dict(row)


@router.get("/{competitor_id}/pages")
async def get_competitor_pages(
    competitor_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    page_type: str | None = None,
    user: dict = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    filters = "AND p.page_type = $4" if page_type else ""
    params = [competitor_id, page_size, offset]
    if page_type:
        params.append(page_type)

    async with acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                p.url_hash, p.url, p.page_type,
                p.first_seen_at, p.last_seen_at, p.next_run_at,
                pos.seo_score, pos.page_speed_score, pos.overall_score
            FROM pages p
            LEFT JOIN page_overall_scores pos ON pos.url_hash = p.url_hash
            WHERE p.competitor_id = $1
            {filters}
            ORDER BY pos.overall_score DESC NULLS LAST
            LIMIT $2 OFFSET $3
            """,
            *params,
        )
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM pages WHERE competitor_id = $1", competitor_id
        )

    return {"total": total, "page": page, "page_size": page_size, "items": [dict(r) for r in rows]}


@router.get("/{competitor_id}/products")
async def get_competitor_products(
    competitor_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    in_stock: bool | None = None,
    user: dict = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    stock_filter = ""
    params = [competitor_id, page_size, offset]
    if in_stock is not None:
        stock_filter = "AND pr.in_stock = $4"
        params.append(in_stock)

    async with acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                pr.id, pr.title, pr.category, pr.brand,
                pr.current_price, pr.in_stock, pr.first_seen_at, pr.last_updated_at
            FROM products pr
            WHERE pr.competitor_id = $1
            {stock_filter}
            ORDER BY pr.last_updated_at DESC
            LIMIT $2 OFFSET $3
            """,
            *params,
        )
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM products WHERE competitor_id = $1", competitor_id
        )

    return {"total": total, "page": page, "page_size": page_size, "items": [dict(r) for r in rows]}
