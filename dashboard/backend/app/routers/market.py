"""Market & Product Intelligence router."""

from fastapi import APIRouter, Depends, Query, HTTPException

from app.db.pool import acquire
from app.dependencies import get_current_user, require_role

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/scores")
async def market_scores(user: dict = Depends(get_current_user)):
    """Competitor market scores — coverage, balance, assortment, availability."""
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                competitor_id, competitor_domain,
                coverage_score, category_balance_score,
                assortment_score, availability_score, final_score
            FROM competitor_market_scores
            ORDER BY final_score DESC
            """
        )
    return [dict(r) for r in rows]


@router.get("/categories")
async def list_categories(user: dict = Depends(get_current_user)):
    """All target categories."""
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id, parent_category_id, category_name, normalized_name,
                category_description, relevance_weight, is_active, created_at
            FROM target_categories
            ORDER BY category_name
            """
        )
    return [dict(r) for r in rows]


@router.post("/categories", dependencies=[Depends(require_role("admin"))])
async def create_category(
    category_name: str,
    category_description: str | None = None,
    relevance_weight: float = 1.0,
    parent_category_id: int | None = None,
    user: dict = Depends(require_role("admin")),
):
    """Create a new target category (admin only)."""
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO target_categories
                (category_name, category_description, relevance_weight, parent_category_id)
            VALUES ($1, $2, $3, $4)
            RETURNING id, category_name, normalized_name, relevance_weight, created_at
            """,
            category_name,
            category_description,
            relevance_weight,
            parent_category_id,
        )
    return dict(row)


@router.get("/products/search")
async def semantic_product_search(
    q: str = Query(..., min_length=2, description="Natural language search query"),
    limit: int = Query(20, ge=1, le=100),
    competitor_id: int | None = None,
    user: dict = Depends(get_current_user),
):
    """
    Semantic product search using pgvector nearest-neighbor search.
    Requires the vector_embedding service to encode the query first.
    Falls back to full-text search if embedding is unavailable.
    """
    competitor_filter = "AND p.competitor_id = $3" if competitor_id else ""
    params_ft = [f"%{q}%", limit]
    if competitor_id:
        params_ft.append(competitor_id)

    async with acquire() as conn:
        # Full-text fallback (always available)
        rows = await conn.fetch(
            f"""
            SELECT
                p.id, p.title, p.category, p.brand,
                p.current_price, p.in_stock,
                c.domain AS competitor_domain,
                p.last_updated_at
            FROM products p
            JOIN competitors c ON c.id = p.competitor_id
            WHERE (p.title ILIKE $1 OR p.category ILIKE $1)
            {competitor_filter}
            ORDER BY p.last_updated_at DESC
            LIMIT $2
            """,
            *params_ft,
        )
    return {"mode": "fulltext", "results": [dict(r) for r in rows]}


@router.get("/price-history/{product_id}")
async def price_history(
    product_id: int,
    limit: int = Query(90, ge=1, le=365),
    user: dict = Depends(get_current_user),
):
    """Price history time series for a product."""
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT price, recorded_at
            FROM price_history
            WHERE product_id = $1
            ORDER BY recorded_at DESC
            LIMIT $2
            """,
            product_id,
            limit,
        )
    return [dict(r) for r in rows]


@router.get("/stock-history/{product_id}")
async def stock_history(
    product_id: int,
    limit: int = Query(90, ge=1, le=365),
    user: dict = Depends(get_current_user),
):
    """Stock availability history for a product."""
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT in_stock, recorded_at
            FROM stock_history
            WHERE product_id = $1
            ORDER BY recorded_at DESC
            LIMIT $2
            """,
            product_id,
            limit,
        )
    return [dict(r) for r in rows]
