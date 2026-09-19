"""HTTP client for the existing scraper FastAPI — pure HTTP, no shared code."""

import httpx

from app.core.config import settings

_client: httpx.AsyncClient | None = None


async def init_scraper_client() -> None:
    global _client
    _client = httpx.AsyncClient(
        base_url=settings.scraper_api_base_url,
        timeout=15.0,
    )


async def close_scraper_client() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None


def get_scraper_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("Scraper client not initialised")
    return _client


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------

async def trigger_url(url: str, priority: int = 5, job_type: str | None = None) -> dict:
    resp = await get_scraper_client().post(
        "/frontier/urls",
        json={"url": url, "priority": priority, "job_type": job_type},
    )
    resp.raise_for_status()
    return resp.json()


async def trigger_urls_batch(urls: list[dict]) -> dict:
    resp = await get_scraper_client().post(
        "/frontier/urls/batch",
        json={"urls": urls},
    )
    resp.raise_for_status()
    return resp.json()


async def get_job_status(url_id: str) -> dict:
    resp = await get_scraper_client().get(f"/frontier/urls/{url_id}")
    resp.raise_for_status()
    return resp.json()


async def scraper_health() -> bool:
    try:
        resp = await get_scraper_client().get("/health", timeout=3.0)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


async def frontier_stats() -> dict:
    resp = await get_scraper_client().get("/frontier/stats")
    resp.raise_for_status()
    return resp.json()
