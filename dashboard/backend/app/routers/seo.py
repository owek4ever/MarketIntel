"""SEO Intelligence router."""

from fastapi import APIRouter, Depends, Query

from app.db.pool import acquire
from app.dependencies import get_current_user

router = APIRouter(prefix="/seo", tags=["seo"])


@router.get("/summary")
async def seo_summary(user: dict = Depends(get_current_user)):
    """Competitor SEO ranking — all domains with dimension scores."""
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                competitor_id, domain, total_pages,
                avg_seo_score, median_seo_score,
                avg_content_score, avg_on_page_score,
                avg_technical_score, avg_ux_score,
                seo_stddev
            FROM competitor_seo_summary
            ORDER BY avg_seo_score DESC
            """
        )
    return [dict(r) for r in rows]


@router.get("/gap-matrix")
async def gap_matrix(user: dict = Depends(get_current_user)):
    """Pairwise SEO gap matrix between all competitors."""
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                domain_a, competitor_a,
                domain_b, competitor_b,
                seo_gap, content_gap,
                on_page_gap, technical_gap, ux_gap
            FROM competitor_gap_matrix
            ORDER BY domain_a, domain_b
            """
        )
    return [dict(r) for r in rows]


@router.get("/action-plan/{competitor_id}")
async def action_plan(competitor_id: int, user: dict = Depends(get_current_user)):
    """Prioritised SEO issue action plan for a competitor."""
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                issue, total_priority, avg_priority,
                total_affected_pages, priority_level
            FROM competitor_action_plan
            WHERE competitor_id = $1
            ORDER BY total_priority DESC
            """,
            competitor_id,
        )
    return [dict(r) for r in rows]


@router.get("/top-issues/{competitor_id}")
async def top_issues(
    competitor_id: int,
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """Top ranked SEO issues by priority score for a competitor."""
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                issue, occurrence_count, affected_pages,
                total_impact, avg_impact,
                impact_ratio, coverage_ratio, priority_score, rank
            FROM competitor_top_issues
            WHERE competitor_id = $1
            ORDER BY priority_score DESC
            LIMIT $2
            """,
            competitor_id,
            limit,
        )
    return [dict(r) for r in rows]


@router.get("/pages/{competitor_id}")
async def seo_pages(
    competitor_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """Per-page SEO scores for a competitor, ordered by score desc."""
    offset = (page - 1) * page_size
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                p.url, p.page_type,
                pss.content_score, pss.on_page_score,
                pss.technical_score, pss.ux_score,
                pss.overall_score, pss.page_seo_score
            FROM page_seo_scores pss
            JOIN pages p ON pss.page_url_hash = p.url_hash
            WHERE p.competitor_id = $1
            ORDER BY pss.page_seo_score DESC
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
