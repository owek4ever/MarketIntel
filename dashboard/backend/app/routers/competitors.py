"""Competitors router."""

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.db.pool import acquire
from app.dependencies import get_current_user

router = APIRouter(prefix="/competitors", tags=["competitors"])

SCRAPER_API = "http://localhost:8889/frontier/urls"


class AddCompetitorRequest(BaseModel):
    domain: str
    name: str | None = None
    scrape: bool = True  # auto-submit homepage to scraper


def normalize_domain(domain: str) -> str:
    """Strip protocol, www., and trailing slash."""
    d = domain.strip().lower()
    if d.startswith("https://"):
        d = d[8:]
    elif d.startswith("http://"):
        d = d[7:]
    if d.startswith("www."):
        d = d[4:]
    d = d.rstrip("/")
    return d


@router.post("")
async def add_competitor(
    body: AddCompetitorRequest,
    user: dict = Depends(get_current_user),
):
    """Add a competitor and optionally start scraping their homepage."""
    domain = normalize_domain(body.domain)
    name = body.name or domain.split(".")[0].title()

    async with acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO competitors (domain, name)
               VALUES ($1, $2)
               ON CONFLICT (domain) DO UPDATE SET name = EXCLUDED.name
               RETURNING id, domain, name, created_at""",
            domain,
            name,
        )

    competitor = dict(row)

    # Submit homepage to scraper
    if body.scrape:
        homepage = f"https://www.{domain}/"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    SCRAPER_API,
                    json={
                        "url": homepage,
                        "job_type": "homepage_sitemap_crawl",
                        "priority": 1,
                    },
                )
                result = resp.json()
                competitor["scrape_submitted"] = result.get("inserted", False)
        except Exception as e:
            competitor["scrape_submitted"] = False
            competitor["scrape_error"] = str(e)

    return competitor


@router.delete("/{competitor_id}")
async def delete_competitor(
    competitor_id: int,
    user: dict = Depends(get_current_user),
):
    """Delete a competitor and all associated data."""
    async with acquire() as conn:
        result = await conn.execute(
            "DELETE FROM competitors WHERE id = $1", competitor_id
        )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Competitor not found")
    return {"status": "deleted", "id": competitor_id}


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


@router.get("/compare")
async def compare_competitors(
    ids: str = Query(..., description="Comma-separated competitor IDs (max 5)"),
    user: dict = Depends(get_current_user),
):
    """Side-by-side comparison of multiple competitors."""
    id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
    if len(id_list) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 competitor IDs")
    if len(id_list) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 competitors per comparison")

    placeholders = ", ".join(f"${i+1}" for i in range(len(id_list)))

    async with acquire() as conn:
        competitors = await conn.fetch(
            f"""
            SELECT
                c.id, c.domain, c.name,
                cs.avg_seo_score, cs.avg_content_score, cs.avg_on_page_score,
                cs.avg_technical_score, cs.avg_ux_score,
                cps.avg_score AS perf_score, cps.total_pages,
                cms.final_score AS market_score, cms.coverage_score,
                cms.category_balance_score, cms.assortment_score,
                COALESCE(css.score, 0) AS social_score,
                (SELECT COUNT(*) FROM products pr WHERE pr.competitor_id = c.id) AS product_count,
                (SELECT ROUND(AVG(pr.current_price)::numeric, 2) FROM products pr WHERE pr.competitor_id = c.id AND pr.current_price IS NOT NULL) AS avg_price,
                (SELECT COUNT(*) FROM products pr WHERE pr.competitor_id = c.id AND pr.in_stock = true) AS in_stock_count
            FROM competitors c
            LEFT JOIN competitor_seo_summary cs ON cs.competitor_id = c.id
            LEFT JOIN competitor_page_scores cps ON cps.competitor_id = c.id
            LEFT JOIN competitor_market_scores cms ON cms.competitor_id = c.id
            LEFT JOIN (
                SELECT competitor_id, ROUND(AVG(score)::numeric, 4) AS score
                FROM competitor_social_score GROUP BY competitor_id
            ) css ON css.competitor_id = c.id
            WHERE c.id IN ({placeholders})
            """,
            *id_list,
        )

        categories = await conn.fetch(
            f"""
            SELECT competitor_id, category, COUNT(*) as count
            FROM products
            WHERE competitor_id IN ({placeholders}) AND category IS NOT NULL
            GROUP BY competitor_id, category
            ORDER BY count DESC
            """,
            *id_list,
        )

        price_ranges = await conn.fetch(
            f"""
            SELECT competitor_id,
                ROUND(MIN(current_price)::numeric, 2) AS min_price,
                ROUND(MAX(current_price)::numeric, 2) AS max_price,
                ROUND(AVG(current_price)::numeric, 2) AS avg_price,
                COUNT(*) AS priced_products
            FROM products
            WHERE competitor_id IN ({placeholders}) AND current_price IS NOT NULL
            GROUP BY competitor_id
            """,
            *id_list,
        )

        social_accounts = await conn.fetch(
            f"""
            SELECT sa.competitor_id, sa.platform, sa.follower_count, sa.is_verified
            FROM social_accounts sa
            WHERE sa.competitor_id IN ({placeholders})
            ORDER BY sa.follower_count DESC
            """,
            *id_list,
        )

    comp_map = {dict(r)["id"]: dict(r) for r in competitors}

    result = []
    for cid in id_list:
        c = comp_map.get(cid, {"id": cid, "name": "Unknown", "domain": "unknown"})
        c["categories"] = [
            {"category": r["category"], "count": r["count"]}
            for r in categories if r["competitor_id"] == cid
        ][:10]
        pr = next((dict(r) for r in price_ranges if r["competitor_id"] == cid), None)
        c["price_range"] = pr
        c["social_accounts"] = [
            {"platform": r["platform"], "followers": r["follower_count"], "verified": r["is_verified"]}
            for r in social_accounts if r["competitor_id"] == cid
        ]
        scores = [c.get("avg_seo_score"), c.get("perf_score"), c.get("social_score"), c.get("market_score")]
        valid_scores = [float(s) for s in scores if s is not None]
        c["composite_score"] = round(sum(valid_scores) / len(valid_scores), 4) if valid_scores else None
        result.append(c)

    return result


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
