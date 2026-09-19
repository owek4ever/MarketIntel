"""Minimal webhook receiver — saves scraper results to PostgreSQL."""
import json, hashlib, logging
from contextlib import asynccontextmanager
import asyncpg
from fastapi import FastAPI, Request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_URL = "postgresql://postgres:postgres@localhost:5432/pfe2"
pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=5)
    logger.info("Connected to PostgreSQL")
    yield
    await pool.close()

app = FastAPI(title="Scraper Webhook Receiver", lifespan=lifespan)

def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()

def normalize_domain(domain: str) -> str:
    return domain[4:] if domain.startswith("www.") else domain

async def upsert_competitor(domain: str) -> int:
    domain = normalize_domain(domain)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO competitors (domain) VALUES ($1) ON CONFLICT (domain) DO UPDATE SET domain=EXCLUDED.domain RETURNING id",
            domain,
        )
        return row["id"]

async def upsert_page(competitor_id: int, url: str, page_type: str) -> str:
    h = url_hash(url)
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO pages (url_hash, competitor_id, url, page_type) VALUES ($1,$2,$3,$4) ON CONFLICT (url_hash) DO UPDATE SET last_seen_at=NOW()",
            h, competitor_id, url, page_type,
        )
    return h

async def save_snapshot(url_hash_val: str, data: dict) -> None:
    seo = data.get("seo_report", {})
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO page_snapshots (page_url_hash, status_code, final_url, title, seo_flags)
               VALUES ($1,$2,$3,$4,$5)""",
            url_hash_val, data.get("status_code"), data.get("final_url"), data.get("title"), json.dumps(seo),
        )

async def save_products(competitor_id: int, url_hash_val: str, products: list) -> None:
    async with pool.acquire() as conn:
        for p in products:
            title = p.get("title", "")
            price = p.get("price")
            try:
                price = float(str(price).replace(",",".").replace(" ","").replace("DT","").strip()) if price else None
            except: price = None
            await conn.execute(
                "INSERT INTO products (competitor_id, url_hash, title, current_price, in_stock) VALUES ($1,$2,$3,$4,$5) ON CONFLICT (url_hash) DO UPDATE SET title=EXCLUDED.title, current_price=EXCLUDED.current_price, last_updated_at=NOW()",
                competitor_id, url_hash_val, title, price, p.get("in_stock", True),
            )

async def save_job(url, domain, status, job_type, meta=None):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO scrape_jobs (url, domain, status, job_type, technical_metadata, finished_at) VALUES ($1,$2,$3,$4,$5,NOW())",
            url, domain, status, job_type, json.dumps(meta or {}),
        )

@app.post("/webhook/crawl_result")
async def handle_crawl(request: Request):
    body = await request.json()
    r = body.get("result", {})
    url = r.get("url", "")
    domain = r.get("domain", "")
    logger.info("Crawl: %s", url)
    cid = await upsert_competitor(domain)
    h = url_hash(url)
    await upsert_page(cid, url, "homepage")
    await save_snapshot(h, r)
    await save_job(url, domain, "completed", r.get("job_type", "homepage_sitemap_crawl"))
    homepage_urls = r.get("homepage_urls", {})
    if isinstance(homepage_urls, dict):
        all_links = []
        for urls_list in homepage_urls.values():
            if isinstance(urls_list, list):
                all_links.extend(urls_list)
        homepage_urls = all_links
    for link in homepage_urls[:50]:
        if not isinstance(link, str):
            continue
        d = link.split("//")[-1].split("/")[0]
        lcid = await upsert_competitor(d)
        await upsert_page(lcid, link, "unknown")
    return {"status": "saved"}

@app.post("/webhook/content_scrape_result")
async def handle_content(request: Request):
    body = await request.json()
    r = body.get("result", {})
    url = r.get("url", "")
    domain = r.get("domain", "")
    logger.info("Content: %s", url)
    cid = await upsert_competitor(domain)
    h = url_hash(url)
    await upsert_page(cid, url, "content")
    await save_snapshot(h, r)
    await save_job(url, domain, "completed", r.get("job_type", "extract_page_content"))
    return {"status": "saved"}

@app.post("/webhook/product_list_scrape_result")
async def handle_product_list(request: Request):
    body = await request.json()
    r = body.get("result", {})
    url = r.get("url", "")
    domain = r.get("domain", "")
    logger.info("Product list: %s (%d products)", url, len(r.get("products", [])))
    cid = await upsert_competitor(domain)
    h = url_hash(url)
    await upsert_page(cid, url, "product_list")
    await save_snapshot(h, r)
    await save_products(cid, h, r.get("products", []))
    await save_job(url, domain, "completed", r.get("job_type", "extract_product_list"))
    return {"status": "saved"}

@app.post("/webhook/product_scrape_result")
async def handle_product(request: Request):
    body = await request.json()
    r = body.get("result", {})
    url = r.get("url", "")
    domain = r.get("domain", "")
    logger.info("Product: %s", url)
    cid = await upsert_competitor(domain)
    h = url_hash(url)
    await upsert_page(cid, url, "product_detail")
    await save_snapshot(h, r)
    p = r.get("product", {})
    if p:
        await save_products(cid, h, [p])
    await save_job(url, domain, "completed", r.get("job_type", "extract_product_detail"))
    return {"status": "saved"}

@app.get("/health")
async def health():
    return {"status": "ok"}
