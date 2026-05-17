"""Analytics overview router — aggregated KPIs for the dashboard homepage."""

from fastapi import APIRouter, Depends

from app.db.pool import acquire
from app.dependencies import get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
async def overview(user: dict = Depends(get_current_user)):
    """
    Top-level KPIs for the command-center dashboard:
    - Competitor count
    - Total pages crawled
    - Total products indexed
    - Active / pending scrape jobs
    - Latest action plan critical issues
    """
    async with acquire() as conn:
        kpis = await conn.fetchrow(
            """
            SELECT
                (SELECT COUNT(*) FROM competitors)             AS competitors_total,
                (SELECT COUNT(*) FROM pages)                   AS pages_total,
                (SELECT COUNT(*) FROM products)                AS products_total,
                (SELECT COUNT(*) FROM scrape_jobs
                    WHERE status IN ('pending','in_progress')) AS jobs_active,
                (SELECT COUNT(*) FROM scrape_jobs
                    WHERE status = 'failed')                   AS jobs_failed,
                (SELECT COUNT(*) FROM scrape_jobs
                    WHERE status = 'completed')                AS jobs_completed
            """
        )

        # Latest critical issues across all competitors
        critical = await conn.fetch(
            """
            SELECT
                competitor_id, issue,
                total_affected_pages, total_priority
            FROM competitor_action_plan
            WHERE priority_level = 'critical'
            ORDER BY total_priority DESC
            LIMIT 10
            """
        )

        # Score averages across all competitors
        scores = await conn.fetchrow(
            """
            SELECT
                ROUND(AVG(avg_seo_score), 2)    AS avg_seo,
                ROUND(AVG(avg_score), 2)         AS avg_perf
            FROM competitor_seo_summary
            CROSS JOIN competitor_page_scores
            LIMIT 1
            """
        )

        social_avg = await conn.fetchval(
            "SELECT ROUND(AVG(score)::numeric, 4) FROM competitor_social_score"
        )

        market_avg = await conn.fetchval(
            "SELECT ROUND(AVG(final_score)::numeric, 2) FROM competitor_market_scores"
        )

    return {
        "kpis": dict(kpis),
        "score_overview": {
            "seo": scores["avg_seo"] if scores else None,
            "performance": scores["avg_perf"] if scores else None,
            "social": social_avg,
            "market": market_avg,
        },
        "critical_issues": [dict(r) for r in critical],
    }
