"""Crawl Operations router — proxies to the existing scraper API, monitors jobs."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, HttpUrl

from app.db.pool import acquire
from app.dependencies import get_current_user, require_role
from app.services import scraper_client
from app.core.config import settings
import httpx

router = APIRouter(prefix="/crawl", tags=["crawl"])


class TriggerUrlRequest(BaseModel):
    url: HttpUrl
    priority: int = 5
    job_type: str | None = None


class BatchTriggerRequest(BaseModel):
    urls: list[TriggerUrlRequest]


async def _audit(user: dict, action: str, payload: dict | None = None) -> None:
    async with acquire() as conn:
        await conn.execute(
            """
            INSERT INTO dashboard.audit_log (user_id, action, payload)
            VALUES ($1, $2, $3)
            """,
            user["id"],
            action,
            payload,
        )


@router.post("/trigger", dependencies=[Depends(require_role("admin"))])
async def trigger_url(
    req: TriggerUrlRequest,
    user: dict = Depends(require_role("admin")),
):
    """Enqueue a single URL in the scraper frontier (admin only)."""
    try:
        result = await scraper_client.trigger_url(
            str(req.url), req.priority, req.job_type
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Scraper error: {exc.response.text}")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Scraper unreachable: {exc}")

    await _audit(user, "trigger_url", {"url": str(req.url), "priority": req.priority})
    return result


@router.post("/batch", dependencies=[Depends(require_role("admin"))])
async def trigger_batch(
    req: BatchTriggerRequest,
    user: dict = Depends(require_role("admin")),
):
    """Enqueue multiple URLs in the scraper frontier (admin only)."""
    urls = [
        {"url": str(u.url), "priority": u.priority, "job_type": u.job_type}
        for u in req.urls
    ]
    try:
        result = await scraper_client.trigger_urls_batch(urls)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Scraper error: {exc.response.text}")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Scraper unreachable: {exc}")

    await _audit(user, "trigger_batch", {"count": len(urls)})
    return result


@router.get("/jobs")
async def list_jobs(
    status: str | None = None,
    domain: str | None = None,
    job_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """Query scrape_jobs table with optional filters (polling-friendly)."""
    offset = (page - 1) * page_size
    conditions = []
    params: list = []

    if status:
        params.append(status)
        conditions.append(f"status = ${len(params)}")
    if domain:
        params.append(domain)
        conditions.append(f"domain = ${len(params)}")
    if job_type:
        params.append(job_type)
        conditions.append(f"job_type = ${len(params)}")

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params += [page_size, offset]
    limit_param = len(params) - 1
    offset_param = len(params)

    async with acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                id, url, domain, job_type, status, priority,
                retries, queued_at, started_at, finished_at
            FROM scrape_jobs
            {where}
            ORDER BY queued_at DESC
            LIMIT ${limit_param} OFFSET ${offset_param}
            """,
            *params,
        )
        count_params = params[:-2]
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM scrape_jobs {where}", *count_params
        )

    return {"total": total, "page": page, "page_size": page_size, "items": [dict(r) for r in rows]}


@router.get("/jobs/{job_id}")
async def get_job(job_id: int, user: dict = Depends(get_current_user)):
    """Single scrape job detail."""
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, url, domain, job_type, status, priority,
                   retries, queued_at, started_at, finished_at, technical_metadata
            FROM scrape_jobs WHERE id = $1
            """,
            job_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return dict(row)


@router.post(
    "/refresh-views",
    dependencies=[Depends(require_role("admin"))],
    summary="Trigger n8n to refresh all materialized views",
)
async def refresh_materialized_views(user: dict = Depends(require_role("admin"))):
    """
    Fires the n8n 'Refresh Materialized Views' webhook (admin only).
    n8n handles the REFRESH MATERIALIZED VIEW CONCURRENTLY calls.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{settings.n8n_webhook_base_url}/webhook/refresh_materialized_views",
                headers={"x-api-key": settings.n8n_api_key},
                json={"triggered_by": user["email"]},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=502, detail=f"n8n error: {exc.response.text}")
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"n8n unreachable: {exc}")

    await _audit(user, "refresh_materialized_views", None)
    return {"status": "triggered"}


@router.get("/scraper-health")
async def scraper_health(user: dict = Depends(get_current_user)):
    """Check if the existing scraper API is reachable."""
    alive = await scraper_client.scraper_health()
    return {"scraper_online": alive}


@router.get("/stats")
async def crawl_stats(user: dict = Depends(get_current_user)):
    """Live frontier stats: queue depth, inflight, failures, per-domain breakdown."""
    try:
        return await scraper_client.frontier_stats()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Scraper error: {exc.response.text}")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Scraper unreachable: {exc}")


@router.get("/stats/aggregate")
async def crawl_stats_aggregate(user: dict = Depends(get_current_user)):
    """Aggregate scrape_jobs stats from the database."""
    async with acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'queued') as queued,
                COUNT(*) FILTER (WHERE status = 'inflight') as inflight,
                COUNT(*) FILTER (WHERE status = 'failed') as failed,
                COUNT(*) FILTER (WHERE status = 'retry_scheduled') as retry_scheduled,
                COUNT(*) FILTER (WHERE finished_at IS NOT NULL AND finished_at > NOW() - INTERVAL '1 hour') as last_hour,
                COUNT(*) FILTER (WHERE finished_at IS NOT NULL AND finished_at > NOW() - INTERVAL '24 hours') as last_24h,
                AVG(EXTRACT(EPOCH FROM (finished_at - started_at))) FILTER (WHERE finished_at IS NOT NULL) as avg_duration_seconds
            FROM scrape_jobs
        """)
        domains = await conn.fetch("""
            SELECT domain,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'failed') as failed,
                MAX(finished_at) as last_scraped
            FROM scrape_jobs
            GROUP BY domain ORDER BY total DESC LIMIT 50
        """)
        recent = await conn.fetch("""
            SELECT id, url, domain, job_type, status, priority, queued_at, finished_at
            FROM scrape_jobs
            ORDER BY queued_at DESC LIMIT 20
        """)
    return {
        "totals": dict(row) if row else {},
        "domains": [dict(d) for d in domains],
        "recent": [dict(r) for r in recent],
    }
