from classifiers.pagination_type_classifier import (
    PaginationTypeInfo,
    detect_pagination_type,
)
from extractors.product_list import extract_product_list_items
import logging
from typing import List

from playwright.async_api import Page

from . import constants, utils

logger = logging.getLogger(__name__)


class HybridPaginator:
    """
    Production-ready Hybrid Pagination Engine using Playwright.
    Handles URL pagination, Load More buttons, Next buttons, and Infinite Scroll.
    """

    def __init__(
        self,
        page: Page,
        start_url: str,
        max_pages: int = 50,
        pagination_type: PaginationTypeInfo | None = None,
    ):
        self.page = page
        self.start_url = start_url
        self.max_pages = max_pages
        self.current_page_count = 0
        self.pagination_type: PaginationTypeInfo | None = pagination_type
        # self.product_selector = None

    async def detect_pagination_type(self) -> PaginationTypeInfo:
        """
        Detect the type of pagination present on the current page.
        Returns a dictionary with type, pattern, and selector.
        """
        return await detect_pagination_type(self.page)

    async def extract_products_while_paginating(self) -> List[str]:
        """
        Extract products from the current page, then paginate (scroll/load more/next/url)
        and keep extracting until exhaustion or max_pages.
        """

        logger.info(f"Starting extract+paginate for {self.start_url}")

        if not self.pagination_type:
            self.pagination_type = await self.detect_pagination_type()

        p_type = self.pagination_type.get("type")

        collected: set[str] = set()

        # self.sb.get_current_url()
        products = await extract_product_list_items(self.page)
        collected.update(products)

        pages_crawled = 1
        logger.info(
            f"Page {pages_crawled}: Collected {len(products)} products. Total so far: {len(collected)}"
        )

        async def run_url_pagination(param_name: str) -> int:
            nonlocal pages_crawled
            from urllib.parse import urlparse, parse_qs

            parsed = urlparse(self.start_url)
            params = parse_qs(parsed.query)
            current_page = 1
            if param_name in params:
                try:
                    current_page = int(params[param_name][0])
                except ValueError:
                    pass

            last_url = self.start_url
            while pages_crawled < self.max_pages:
                current_page += 1
                next_url = utils.get_next_page_url(
                    self.start_url, param_name, current_page
                )
                logger.info(f"Navigating to next page: {next_url}")
                try:
                    # self.sb.open(next_url)
                    await self.page.goto(next_url)
                    await utils.random_sleep(*constants.WAIT_SEC_BETWEEN_PAGE_SCRAPE)

                    # self.sb.get_current_url()
                    real_url = self.page.url
                    if real_url == last_url or real_url == self.start_url:
                        logger.info("Redirected to a previously seen URL. Stopping.")
                        break
                    last_url = real_url

                    length_before = len(collected)

                    products = await extract_product_list_items(self.page)
                    collected.update(products)

                    pages_crawled += 1
                    logger.info(
                        f"Page {pages_crawled}: Collected {len(products)} products. Total so far: {len(collected)}"
                    )

                    if len(collected) == length_before:
                        logger.info("No new products found. Stopping.")
                        break

                except Exception as exc:
                    logger.error(f"Error during URL pagination: {exc}")
                    break
            return pages_crawled

        async def run_next_button(selector: str) -> int:
            nonlocal pages_crawled

            while pages_crawled < self.max_pages:
                try:
                    # self.sb.is_element_present(selector)
                    next_button = self.page.locator(selector)
                    if await next_button.count() == 0:
                        logger.info("Next button not present. Stopping.")
                        break

                    # self.sb.find_element(selector)
                    el = next_button.first
                    cls = await el.get_attribute("class") or ""
                    if "disabled" in cls.lower() or await el.get_attribute("disabled"):
                        logger.info("Next button disabled. Stopping.")
                        break

                    logger.debug("Clicking Next button...")
                    try:
                        # self.sb.click(selector)
                        await el.click()
                    except Exception:
                        safe_sel = selector.replace('"', '\\"')
                        # self.sb.execute_script(...)
                        await self.page.evaluate(
                            f'document.querySelector("{safe_sel}").click();'
                        )

                    await utils.random_sleep(*constants.WAIT_SEC_BETWEEN_PAGE_SCRAPE)

                    length_before = len(collected)
                    products = await extract_product_list_items(self.page)
                    collected.update(products)

                    pages_crawled += 1
                    logger.info(
                        f"Page {pages_crawled}: Collected {len(products)} products. Total so far: {len(collected)}"
                    )

                    if len(collected) == length_before:
                        logger.info("No new products found. Stopping.")
                        break

                except Exception as exc:
                    logger.error(f"Error interacting with Next button: {exc}")
                    break

            return pages_crawled

        async def run_load_more(selector: str) -> int:
            nonlocal pages_crawled

            while pages_crawled < self.max_pages:
                try:
                    # self.sb.is_element_visible(selector)
                    load_more = self.page.locator(selector)
                    if (
                        await load_more.count() == 0
                        or not await load_more.first.is_visible()
                    ):
                        logger.info("Load More button not visible. Stopping.")
                        break

                    logger.debug("Clicking Load More button...")
                    # self.sb.click(selector)
                    await load_more.first.click()
                    await utils.random_sleep(*constants.WAIT_SEC_BETWEEN_PAGE_SCRAPE)

                    length_before = len(collected)
                    products = await extract_product_list_items(self.page)
                    collected.update(products)

                    pages_crawled += 1
                    logger.info(
                        f"Page {pages_crawled}: Collected {len(products)} products. Total so far: {len(collected)}"
                    )

                    if len(collected) == length_before:
                        logger.info("No new products found. Stopping.")
                        break

                except Exception as exc:
                    logger.error(f"Error interacting with Load More button: {exc}")
                    break
            return pages_crawled

        async def run_infinite_scroll() -> int:
            nonlocal pages_crawled
            attempts = 0
            max_stable_attempts = 3
            # self.sb.execute_script("return document.body.scrollHeight")
            last_height = await self.page.evaluate("() => document.body.scrollHeight")

            while pages_crawled < self.max_pages:
                try:
                    # self.sb.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    await self.page.evaluate(
                        "() => window.scrollTo(0, document.body.scrollHeight)"
                    )
                    await utils.random_sleep(*constants.WAIT_SEC_BETWEEN_PAGE_SCRAPE)

                    # self.sb.execute_script("return document.body.scrollHeight")
                    new_height = self.page.evaluate("() => document.body.scrollHeight")
                    if new_height == last_height:
                        attempts += 1
                        if attempts >= max_stable_attempts:
                            logger.info(
                                "Document height stable. Stopping infinite scroll."
                            )
                            break
                    else:
                        attempts = 0
                        last_height = new_height

                        length_before = len(collected)
                        products = await extract_product_list_items(self.page)
                        collected.update(products)

                        pages_crawled += 1
                        logger.info(
                            f"Page {pages_crawled}: Collected {len(products)} products. Total so far: {len(collected)}"
                        )

                        if len(collected) == length_before:
                            logger.info("No new products found. Stopping.")
                            break

                except Exception as exc:
                    logger.error(f"Error during infinite scroll: {exc}")
                    break
            return pages_crawled

        # Execute pagination strategy with fallbacks
        if p_type == "url":
            param = self.pagination_type.get("pattern")
            if param:
                await run_url_pagination(param)
            if pages_crawled <= 1:
                logger.info("URL pagination failed. Trying Next Button fallback...")
                p_type = "next_button"

        if p_type == "next_button":
            sel = (
                self.pagination_type.get("selector")
                if self.pagination_type.get("type") == "next_button"
                else 'a[rel="next"]'
            )
            await run_next_button(sel or "")
            if pages_crawled <= 1:
                logger.info("Next Button failed. Trying Load More fallback...")
                p_type = "load_more"

        if p_type == "load_more":
            sel = (
                self.pagination_type.get("selector")
                if self.pagination_type.get("type") == "load_more"
                else 'button[class*="load"]'
            )
            await run_load_more(sel or "")
            if pages_crawled <= 1:
                logger.info("Load More failed. Trying Infinite Scroll fallback...")
                p_type = "infinite_scroll"

        if p_type == "infinite_scroll":
            await run_infinite_scroll()

        result = list(collected)
        return result
