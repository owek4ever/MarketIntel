"""Integrated crawler entrypoint using the Redis frontier and Playwright browser pool."""

from __future__ import annotations

import asyncio
import time
import logging
from pathlib import Path
from typing import Any

from fastapi.encoders import jsonable_encoder

import yaml
from playwright.async_api import BrowserContext

from SEO.analyze import analyze_seo
from browser_pool import BrowserPool, BrowserPoolConfig
from extractors.crawler import discover_urls
from extractors.product_detail import extract_product_detail
from extractors.product_list import extract_product_list_items
from extractors.text_content import extract_text_content
from frontier import FrontierConfig, FrontierManager
from frontier.url_store import ScheduledURL
from classifiers.job_builder import classify_page_from_html
from classifiers.models import PageType
from paginator.paginator import HybridPaginator
from webhook_notifier import WebhookNotifier
from extractors import classify_urls

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(path: Path = Path.cwd() / "config.yaml") -> dict[str, Any]:
    """Loads application configuration from YAML."""

    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def build_frontier_config(config: dict[str, Any]) -> FrontierConfig:
    """Builds frontier settings from the existing project config shape."""

    redis_cfg = config.get("redis", {})
    frontier_cfg = config.get("frontier", {})
    worker_cfg = config.get("worker", {})

    return FrontierConfig(
        host=redis_cfg.get("host", "localhost"),
        port=redis_cfg.get("port", 6379),
        password=redis_cfg.get("password"),
        db=redis_cfg.get("db", 0),
        key_prefix=frontier_cfg.get("key_prefix", "frontier"),
        default_crawl_delay_seconds=frontier_cfg.get(
            "default_crawl_delay_seconds", 2.0
        ),
        inflight_timeout_seconds=frontier_cfg.get(
            "inflight_timeout_seconds",
            redis_cfg.get("timeout_seconds", 300),
        ),
        max_retries=frontier_cfg.get(
            "max_retries",
            redis_cfg.get("max_retries", 3),
        ),
        retry_delay_seconds=frontier_cfg.get(
            "retry_delay_seconds",
            worker_cfg.get("retry_backoff_sec", 10.0),
        ),
        retry_backoff_multiplier=frontier_cfg.get("retry_backoff_multiplier", 2.0),
        max_retry_delay_seconds=frontier_cfg.get("max_retry_delay_seconds", 300.0),
        max_jobs_per_domain=frontier_cfg.get("max_jobs_per_domain", 10),
        retry_promotion_batch_size=frontier_cfg.get("retry_promotion_batch_size", 100),
        domain_delays=frontier_cfg.get("domain_delays", {}),
        priority_boost_threshold=frontier_cfg.get("priority_boost_threshold", 3),
        wait_max_sleep_seconds=frontier_cfg.get("wait_max_sleep_seconds", 1.0),
        seen_urls_ttl_seconds=frontier_cfg.get("seen_urls_ttl_seconds", 259200),
    )


def build_browser_pool_config(config: dict[str, Any]) -> BrowserPoolConfig:
    """Builds browser-pool settings from the existing project config shape."""

    browser_cfg = config.get("browser", {})
    frontier_cfg = config.get("frontier", {})
    pool_cfg = frontier_cfg.get("browser_pool", {})

    launch_args: list[str] = []
    if browser_cfg.get("disable_images"):
        launch_args.append("--blink-settings=imagesEnabled=false")

    launch_options: dict[str, Any] = {
        "args": launch_args,
    }
    extra_launch_options = pool_cfg.get("launch_options", {})
    launch_options.update(extra_launch_options)

    proxy = browser_cfg.get("proxy")
    browser_proxies = ({"server": proxy},) if proxy else ()

    return BrowserPoolConfig(
        browsers=pool_cfg.get("browsers", 2),
        contexts_per_browser=pool_cfg.get("contexts_per_browser", 4),
        headless=browser_cfg.get("headless", True),
        context_options=pool_cfg.get("context_options", {"ignore_https_errors": True}),
        browser_proxies=browser_proxies,
        max_pages_per_context=pool_cfg.get("max_pages_per_context", 25),
        acquire_timeout_seconds=pool_cfg.get("acquire_timeout_seconds"),
        context_operation_timeout_seconds=pool_cfg.get(
            "context_operation_timeout_seconds", 15.0
        ),
        reset_origin_timeout_seconds=pool_cfg.get("reset_origin_timeout_seconds", 5.0),
        default_timeout_ms=pool_cfg.get("default_timeout_ms", 30_000),
        default_navigation_timeout_ms=pool_cfg.get(
            "default_navigation_timeout_ms", 30_000
        ),
        launch_options=launch_options,
        on_context_created=on_context_created,
    )


def build_webhook_config(config: dict[str, Any]) -> dict[str, Any]:
    """Builds webhook settings from the project config."""

    webhook_cfg = config.get("webhook", {})
    return {
        "scrape_started_url": webhook_cfg.get("scrape_started_url"),
        "crawl_result_url": webhook_cfg.get("crawl_result_url"),
        "product_list_scrape_result_url": webhook_cfg.get("product_list_scrape_result_url"),
        "product_scrape_result_url": webhook_cfg.get("product_scrape_result_url"),
        "content_scrape_result_url": webhook_cfg.get("content_scrape_result_url"),
        "timeout_seconds": float(webhook_cfg.get("timeout_seconds", 10.0)),
        "authorization_header_name": webhook_cfg.get("authorization_header_name"),
        "authorization_header_value": webhook_cfg.get("authorization_header_value"),
    }


async def on_context_created(context: BrowserContext) -> None:
    """Applies lightweight stealth defaults to every pooled context."""

    await context.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
        """
    )

def _get_resource_type(url: str, response) -> str:
    """Determine resource type from URL and response"""
    url_lower = url.lower()

    # Check by extension
    if any(url_lower.endswith(ext) for ext in ['.js', '.mjs']):
        return 'javascript'
    elif any(url_lower.endswith(ext) for ext in ['.css']):
        return 'css'
    elif any(url_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']):
        return 'image'
    elif any(url_lower.endswith(ext) for ext in ['.woff', '.woff2', '.ttf', '.eot']):
        return 'font'

    # Check by content-type
    content_type = response.headers.get('content-type', '').lower()
    if 'javascript' in content_type:
        return 'javascript'
    elif 'css' in content_type:
        return 'css'
    elif 'image' in content_type:
        return 'image'
    elif 'font' in content_type:
        return 'font'

    return 'other'

async def make_request(page, url):
    try:
        asset_responses = {}

        # Listen to all network responses
        async def on_response(response):
            url = response.url
            resource_type = _get_resource_type(url, response)

            text_content = None
            if resource_type in ['javascript', 'css'] and not (300 <= response.status < 400):
                try:
                    text_content = await response.text()
                except Exception:
                    pass

            # Store response details for matching URLs
            asset_responses[url] = {
                'url': url,
                'status_code': response.status,
                'headers': response.headers,
                'resource_type': resource_type,
                'timing': response.request.timing,
                'text': text_content
            }

        page.on('response', on_response)
        # Enable performance logging
        await page.evaluate("""() => {
            window.performanceEntries = [];
            const observer = new PerformanceObserver((list) => {
                list.getEntries().forEach(entry => {
                    window.performanceEntries.push(entry);
                });
            });
            observer.observe({entryTypes: ['resource', 'navigation', 'paint']});
        }""")

        # start_time = datetime.now()
        response = await page.goto(url, wait_until='networkidle')
        # ttfb = (datetime.now() - start_time).total_seconds()

        # Get comprehensive metrics
        metrics = await page.evaluate("""() => {
            const navigation = performance.getEntriesByType('navigation')[0];
            const paint = performance.getEntriesByType('paint');
            const resources = performance.getEntriesByType('resource');

            return {
                navigation: {
                    ttfb: navigation.responseStart - navigation.requestStart,
                    dom_interactive: navigation.domInteractive - navigation.requestStart,
                    dom_complete: navigation.domComplete - navigation.requestStart,
                    load_time: navigation.loadEventEnd - navigation.requestStart
                },
                paint: {
                    first_paint: paint.find(p => p.name === 'first-paint')?.startTime,
                    first_contentful_paint: paint.find(p => p.name === 'first-contentful-paint')?.startTime
                },
                resources: resources.length
            };
        }""")

        return response, asset_responses, {
            # 'ttfb': ttfb,
            'metrics': metrics,
            'final_url': response.url,
            'page': page
        }
    except Exception as e:
        print(f"Request failed for {url}: {e}")
        return None, {}, {}

async def scrape_url(pool: BrowserPool, scheduled_url: ScheduledURL, notifier: WebhookNotifier, webhook_config: dict[str, Any]) -> dict[str, Any]:
    """Fetches one URL with the shared browser pool and returns scrape metadata."""

    async with pool.get_page() as page:

        result = {
            "id": scheduled_url.id,
            "url": scheduled_url.url,
            "domain": scheduled_url.domain,
            "priority": scheduled_url.priority,
            "retries": scheduled_url.retries,
            "last_error": scheduled_url.last_error,
            "queued_at": scheduled_url.created_at,
            "started_at": time.time(),
            "job_metadata": scheduled_url.metadata,
            "status": "processing"
        }

        # response = await page.goto(scheduled_url.url, wait_until="domcontentloaded")
        response, assets, performance_data = await make_request(page, scheduled_url.url)
        html = await page.content()
        title = await page.title()

        result["final_url"] = performance_data.get("final_url") if performance_data else ""
        result["status_code"] = response.status if response else None
        result["title"] = title

        seo_report = analyze_seo(scheduled_url.url, html, response, performance_data, assets)
        result["seo_report"] = seo_report

        if scheduled_url.job_type == "homepage_sitemap_crawl":
            result["job_type"] = "homepage_sitemap_crawl"
            logger.info("Sending job started notification for: %s", scheduled_url.url)
            # await notifier.send_payload(webhook_config.get("scrape_started_url"), jsonable_encoder(result))

            # discovered_urls = await discover_urls(scheduled_url.url, page, max_sitemaps=50, include_homepage=False)
            # result["sitemap_urls"] = discovered_urls
            result["homepage_urls"] = classify_urls(seo_report["seo_attributes"]["OnPageAnalyzer"]["internalLinks"])
            result["status"] = "completed"
            result["completed_at"] = time.time()
            return result

        job = await classify_page_from_html(page, html, scheduled_url.url, seo_report)
        result["metadata"] = job.metadata

        logger.info("Sending job started notification for: %s", scheduled_url.url)
        # await notifier.send_payload(webhook_config.get("scrape_started_url"), jsonable_encoder(result))

        if job.page_type == PageType.OTHER:
            result["job_type"] = "none"
        elif job.page_type == PageType.PRODUCT_LIST_PAGINATED:
            result["job_type"] = "extract_product_list"
            paginator = HybridPaginator(page=page, start_url=scheduled_url.url, max_pages=50, pagination_type=job.metadata.get("pagination"))
            result["products"] = await paginator.extract_products_while_paginating()

        elif job.page_type == PageType.PRODUCT_LIST:
            result["job_type"] = "extract_product_list"
            result["products"] = await extract_product_list_items(page)

        elif job.page_type == PageType.PRODUCT_DETAIL:
            result["job_type"] = "extract_product_detail"
            result["product"] = await extract_product_detail(page, html, job.metadata["signals"].get("product_json_ld"), scheduled_url.url)

        elif job.page_type == PageType.CONTENT_LIST or job.page_type == PageType.GENERAL or job.page_type == PageType.UNKNOWN:
            result["job_type"] = "extract_page_content"
            result["page_content"] = await extract_text_content(page)

        result["status"] = "completed"
        result["completed_at"] = time.time()
        return result


async def send_result_to_webhook(
    webhook_config: dict[str, Any],
    payload: dict[str, Any],
    notifier: WebhookNotifier,
) -> None:
    """Posts a scrape result payload to the configured webhook."""

    # Ensure any Pydantic models/dataclasses in the payload are dicts
    safe_payload = jsonable_encoder(payload)

    webhook_url = None

    if safe_payload["result"].get("job_type") == "homepage_sitemap_crawl":
        webhook_url = webhook_config.get("crawl_result_url")
    elif safe_payload["result"].get("job_type") == "extract_product_list":
        webhook_url = webhook_config.get("product_list_scrape_result_url")
    elif safe_payload["result"].get("job_type") == "extract_product_detail":
        webhook_url = webhook_config.get("product_scrape_result_url")
    elif safe_payload["result"].get("job_type") == "extract_page_content":
        webhook_url = webhook_config.get("content_scrape_result_url")

    if not webhook_url:
        return

    logger.info("Sending result to webhook: %s", webhook_url)
    await notifier.send_payload(webhook_url, safe_payload)


async def worker_loop(
    worker_name: str,
    frontier: FrontierManager,
    pool: BrowserPool,
    webhook_config: dict[str, Any],
    notifier: WebhookNotifier,
) -> None:
    """Continuously leases URLs from the frontier and processes them."""

    while True:
        scheduled_url = await frontier.get_next_url(wait=True)
        if scheduled_url is None:
            logger.debug("%s waiting for ready URLs", worker_name)
            continue

        logger.info(
            "%s leased %s priority=%s retries=%s domain=%s",
            worker_name,
            scheduled_url.url,
            scheduled_url.priority,
            scheduled_url.retries,
            scheduled_url.domain,
        )

        try:
            result = await scrape_url(pool, scheduled_url, notifier, webhook_config)
            await send_result_to_webhook(
                webhook_config,
                {
                    "worker_name": worker_name,
                    "event": "scrape.completed",
                    "result": result,
                },
                notifier,
            )
        except Exception as exc:
            failure_state = await frontier.fail_url(scheduled_url.id, str(exc))
            logger.warning(
                "%s failed %s -> %s (%s)",
                worker_name,
                scheduled_url.url,
                failure_state,
                exc,
            )
            continue

        await frontier.complete_url(scheduled_url.id)
        logger.info(
            "%s completed %s status=%s",
            worker_name,
            result["url"],
            result["status_code"],
        )


async def recovery_loop(frontier: FrontierManager, interval_seconds: float) -> None:
    """Periodically requeues expired inflight URLs."""

    try:
        while True:
            recovered = await frontier.recover_timed_out_urls(limit=100)
            if recovered["requeued"] or recovered["failed"]:
                logger.info("Recovered timed out URLs: %s", recovered)
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        raise


async def main() -> None:
    """Boots the integrated crawler stack."""

    config = load_config()
    frontier_config = build_frontier_config(config)
    browser_pool_config = build_browser_pool_config(config)
    webhook_config = build_webhook_config(config)
    worker_count = config.get("worker", {}).get("concurrency", 2)
    recovery_interval_seconds = config.get("frontier", {}).get(
        "recovery_interval_seconds", 30.0
    )
    webhook_notifier = WebhookNotifier(
        timeout_seconds=webhook_config.get("timeout_seconds", 10.0),
        auth_header_name=webhook_config.get("authorization_header_name"),
        auth_header_value=webhook_config.get("authorization_header_value"),
    )

    async with FrontierManager(frontier_config) as frontier:
        # await seed_frontier(frontier, config)

        async with BrowserPool(browser_pool_config) as pool:
            recovery_task = asyncio.create_task(
                recovery_loop(frontier, recovery_interval_seconds)
            )
            try:
                workers = [
                    asyncio.create_task(
                        worker_loop(
                            f"worker-{index}",
                            frontier,
                            pool,
                            webhook_config,
                            webhook_notifier,
                        )
                    )
                    for index in range(worker_count)
                ]
                await asyncio.gather(*workers)
            finally:
                recovery_task.cancel()
                await asyncio.gather(recovery_task, return_exceptions=True)

            logger.info("Browser pool metrics: %s", pool.snapshot_metrics())


if __name__ == "__main__":
    asyncio.run(main())
