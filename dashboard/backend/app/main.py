"""PFE2 Dashboard — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.pool import close_pool, init_pool
from app.services.scraper_client import close_scraper_client, init_scraper_client
from app.routers import auth, competitors, seo, performance, social, market, crawl, analytics


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    await init_pool()
    await init_scraper_client()
    yield
    await close_pool()
    await close_scraper_client()


app = FastAPI(
    title="PFE2 Intelligence Dashboard API",
    version="1.0.0",
    description="Competitive intelligence dashboard for the PFE2 scraping ecosystem.",
    lifespan=lifespan,
)

# CORS — allow only the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers under /api/v1
PREFIX = "/api/v1"
app.include_router(auth.router,        prefix=PREFIX)
app.include_router(competitors.router, prefix=PREFIX)
app.include_router(seo.router,         prefix=PREFIX)
app.include_router(performance.router, prefix=PREFIX)
app.include_router(social.router,      prefix=PREFIX)
app.include_router(market.router,      prefix=PREFIX)
app.include_router(crawl.router,       prefix=PREFIX)
app.include_router(analytics.router,   prefix=PREFIX)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "pfe2-dashboard-backend"}
