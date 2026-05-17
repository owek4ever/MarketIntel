import logging
import re
from typing import Literal, NotRequired, TypedDict
from urllib.parse import urlparse, parse_qs

from playwright.async_api import Page

logger = logging.getLogger(__name__)

LOAD_MORE_SELECTORS = [
    'button[class*="load"]',
    'button[class*="more"]',
    'button[id*="load"]',
    'a[class*="load-more"]',
]

LOAD_MORE_TEXTS = re.compile(
    r"("
    r"\bload\b"
    r"|load more"
    r"|charger"
    r"|plus"
    r"|more"
    r"|afficher plus"
    r"|show more"
    r")",
    re.IGNORECASE,
)

URL_PARAM_CANDIDATES = ["page", "p"]

PAGINATION_NAV_SELECTORS = [
    "nav.pagination a",
    "ul.pagination a",
    ".page-numbers a",
    ".pagination-container a",
    ".pages-items a",
]

NEXT_BUTTON_SELECTORS = [
    'a[rel="next"]',
    'li[class*="next"] a',
    'a[class*="next"]',
    '[aria-label*="ext"]',
    '[aria-label*="uivant"]',
]


class PaginationTypeInfo(TypedDict):
    type: Literal["url", "load_more", "next_button", "infinite_scroll", "not_found"]
    pattern: NotRequired[str | None]
    selector: NotRequired[str | None]


async def detect_pagination_type(page: Page) -> PaginationTypeInfo:
    """
    Detect the type of pagination present on the current page.
    Returns a dictionary with type, pattern, and selector.
    """
    logger.info("Detecting pagination type...")

    for selector in LOAD_MORE_SELECTORS:
        try:
            # sb.is_element_visible(selector)
            locator = page.locator(selector)
            if await locator.count() > 0 and await locator.first.is_visible():
                logger.info(f"Detected Load More button via selector: {selector}")
                return {"type": "load_more", "pattern": None, "selector": selector}
        except Exception:
            pass

    try:
        # sb.find_elements("button, a")
        elements = await page.locator("button, a").all()
        for el in elements:
            text = (await el.text_content() or "").lower()
            if LOAD_MORE_TEXTS.match(text) and await el.is_visible():
                cls = await el.get_attribute("class")
                if cls:
                    first_class = cls.split()[0]
                    # el.tag_name
                    tag_name = await el.evaluate(
                        "element => element.tagName.toLowerCase()"
                    )
                    selector = f"{tag_name}.{first_class}"
                    # sb.is_element_visible(selector)
                    locator = page.locator(selector)
                    if await locator.count() > 0 and await locator.first.is_visible():
                        logger.info(
                            f"Detected Load More button via text heuristic: {selector}"
                        )
                        return {
                            "type": "load_more",
                            "pattern": None,
                            "selector": selector,
                        }
    except Exception as e:
        logger.debug(f"Error checking load more text: {e}")

    # sb.get_current_url()
    current_url = page.url
    parsed_url = urlparse(current_url)
    query_params = parse_qs(parsed_url.query)

    for param in URL_PARAM_CANDIDATES:
        if param in query_params:
            logger.info(f"Detected URL pagination in current URL via param: {param}")
            return {"type": "url", "pattern": param, "selector": None}

    for nav_selector in PAGINATION_NAV_SELECTORS:
        try:
            # sb.find_elements(nav_selector, timeout=2)
            links = await page.locator(nav_selector).all()
            for link in links:
                href = await link.get_attribute("href")
                if href and href != "javascript:void(0)" and href != "#":
                    parsed_href = urlparse(href)
                    href_params = parse_qs(parsed_href.query)
                    for param in URL_PARAM_CANDIDATES:
                        if param in href_params:
                            logger.info(
                                f"Detected URL pagination via anchor tag ({nav_selector}), param: {param}"
                            )
                            return {"type": "url", "pattern": param, "selector": None}
                    if re.search(r"/\d+/?$", href):
                        logger.info(
                            f"Detected URL path pagination via anchor tag ({nav_selector})"
                        )
                        return {"type": "url", "pattern": "__path__", "selector": None}
        except Exception:
            pass

    for selector in NEXT_BUTTON_SELECTORS:
        try:
            # sb.is_element_visible(selector)
            locator = page.locator(selector)
            if await locator.count() > 0 and await locator.first.is_visible():
                logger.info(f"Detected Next button via selector: {selector}")
                return {"type": "next_button", "pattern": None, "selector": selector}
        except Exception:
            pass

    # get all a tags and check if they have these words as text content (innerText)
    links = await page.locator("a, span").all()
    for link in links:
        text = (await link.text_content() or "").lower()
        if (
            re.compile(r"\bnext\b|\bSuivant\b", re.IGNORECASE).match(text)
            and await link.is_visible()
        ):
            await link.evaluate(
                "(el) => el.setAttribute('data-page-next-button', 'true')"
            )
            tag_name = await link.evaluate("element => element.tagName.toLowerCase()")
            selector = f"{tag_name}[data-page-next-button]"
            logger.info(f"Detected next page button via text heuristic: {selector}")
            return {
                "type": "next_button",
                "pattern": None,
                "selector": selector,
            }

    is_infinite_scroll = await page.evaluate("""
        async () => {
            const sleep = ms => new Promise(r => setTimeout(r, ms));

            let initialHeight = document.body?.scrollHeight;
            let currentHeight = initialHeight;
            let scrolled = 0;

            while (initialHeight === currentHeight && scrolled < initialHeight) {
                const waitTime = Math.floor(Math.random() * (3000 - 2000 + 1)) + 2000;
                const scrollSize = Math.floor(Math.random() * (600 - 300 + 1)) + 300;

                window.scrollBy(0, scrollSize);
                scrolled += scrollSize;

                await sleep(waitTime);
                currentHeight = document.body?.scrollHeight;
            }

            return Math.abs(currentHeight - initialHeight) > 500;
        }
    """)

    if is_infinite_scroll:
        logger.info("Detected Infinite Scroll via page height changes on scroll.")
        return {"type": "infinite_scroll", "pattern": None, "selector": None}

    logger.info("No pagination type detected.")
    return {"type": "not_found", "pattern": None, "selector": None}
