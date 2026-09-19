"""
product_detail.py — Heuristic extraction for product detail pages.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from playwright.async_api import Page
from bs4 import BeautifulSoup
import re

from .models import ProductDetail
from .utils import normalize_url
from markdownify import MarkdownConverter

import logging

logger = logging.getLogger(__name__)


def _parse_html(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def _get_meta(soup: BeautifulSoup, *keys: str) -> Optional[str]:
    for key in keys:
        tag = soup.find("meta", attrs={"property": key}) or soup.find(
            "meta", attrs={"name": key}
        )
        if tag and tag.get("content"):
            return str(tag.get("content")).strip()
    return None


def _clean_text(value: str | None) -> Optional[str]:
    if not value:
        return None
    text = " ".join(str(value).split())
    return text[:2000] if text else None

def _extract_offer_fields(offers: Any) -> Dict[str, Optional[str]]:
    if isinstance(offers, list) and offers:
        offers = offers[0]
    if not isinstance(offers, dict):
        return {"price": None, "currency": None, "availability": None, "url": None}

    price = offers.get("price")
    price_spec = offers.get("priceSpecification") or {}
    if not price and isinstance(price_spec, dict):
        price = price_spec.get("price")

    currency = offers.get("priceCurrency")
    if not currency and isinstance(price_spec, dict):
        currency = price_spec.get("priceCurrency")

    availability = offers.get("availability")
    offer_url = offers.get("url")

    if isinstance(availability, list) and availability:
        availability = availability[0]

    return {
        "price": _clean_text(str(price)) if price else None,
        "currency": _clean_text(str(currency)) if currency else None,
        "availability": _clean_text(str(availability)) if availability else None,
        "url": _clean_text(str(offer_url)) if offer_url else None,
    }

def extract_price_text(text: str, patterns: List[re.Pattern]) -> Optional[str]:
    """
    Search *text* for a price match using all configured patterns.
    Returns the first match string, stripped. None if no match.
    """
    for pattern in patterns:
        m = pattern.search(text)
        if m:
            return m.group(0).strip()
    return None

price_patterns: List[str] = [
    r"\d+[,]?\d[\d\s]*[.,]\d*\s*(?:DT|TND|\$|د.ت)",
    r"(?:DT|TND|€|\$|د.ت)\s*\d[\d\s]*[.,]?\d+[.,]?\d*",
    r"\d+[.,]?\d*\s*(?:DT|TND|€|\$|د.ت)",     # minimal form
]

compiled_price_patterns = [re.compile(p, re.IGNORECASE) for p in price_patterns]

async def extract_product_detail(
    page: Page,
    html: str,
    jsonld: dict[str, Any] | None = None,
    url: str = "",
) -> ProductDetail:
    """
    Extract product detail fields from a page.
    Returns a ProductDetail object with best-effort fields.
    """
    if not html:
        return ProductDetail(url=url)

    soup = _parse_html(html)

    product_json = jsonld or {}

    title = _clean_text(product_json.get("name"))
    description = _clean_text(product_json.get("description"))
    offer_fields = _extract_offer_fields(product_json.get("offers"))

    images: List[str] = []
    raw_images = product_json.get("image")
    if isinstance(raw_images, str):
        images = [raw_images]
    elif isinstance(raw_images, list):
        images = [str(x) for x in raw_images if x]
    elif isinstance(raw_images, dict) and raw_images.get("url"):
        images = [str(raw_images.get("url"))]

    brand = product_json.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name")
    if brand is not None:
        brand = _clean_text(str(brand))

    sku = product_json.get("sku") or product_json.get("mpn")
    if sku is not None:
        sku = _clean_text(str(sku))

    # Fallbacks from meta / itemprop / title tags
    if not title:
        title = _get_meta(soup, "og:title", "twitter:title", "title")
    if not title:
        h1 = soup.find("h1")
        title = _clean_text(h1.get_text(" ", strip=True) if h1 else None)
    if not title:
        title_tag = soup.find("title")
        title = _clean_text(title_tag.get_text(" ", strip=True) if title_tag else None)

    if not description:
        description = _get_meta(soup, "og:description", "description")
    if not description:
        desc_tag = soup.select_one('[itemprop="description"]')
        if desc_tag:
            description = _clean_text(desc_tag.get_text(" ", strip=True))

    if not images:
        og_image = _get_meta(soup, "og:image", "twitter:image")
        if og_image:
            images = [og_image]
    if not images:
        img_tag = soup.select_one('[itemprop="image"]')
        if img_tag and img_tag.get("src"):
            images = [str(img_tag.get("src"))]

    price = offer_fields.get("price")
    currency = offer_fields.get("currency")
    availability = offer_fields.get("availability")

    if not price:
        price = _get_meta(
            soup,
            "product:price:amount",
            "og:price:amount",
            "product:price",
        )
    if not currency:
        currency = _get_meta(
            soup,
            "product:price:currency",
            "og:price:currency",
        )
    if not price:
        price_tag = soup.select_one('[itemprop="price"]')
        if price_tag:
            price = _clean_text(
                price_tag.get("content") or price_tag.get_text(" ", strip=True) # type: ignore
            )
    if not currency:
        currency_tag = soup.select_one('[itemprop="priceCurrency"]')
        if currency_tag:
            currency = _clean_text(
                currency_tag.get("content") or currency_tag.get_text(" ", strip=True) # type: ignore
            )

    if not sku:
        sku_tag = soup.select_one('[itemprop="sku"], [data-sku]')
        if sku_tag:
            sku = _clean_text(
                sku_tag.get("content")
                or sku_tag.get("data-sku")
                or sku_tag.get_text(" ", strip=True) # type: ignore
            )

    if not brand:
        brand_tag = soup.select_one('[itemprop="brand"], [data-brand]')
        if brand_tag:
            brand = _clean_text(
                brand_tag.get("content")
                or brand_tag.get("data-brand")
                or brand_tag.get_text(" ", strip=True) # type: ignore
            )

    if availability:
        if isinstance(availability, list):
            availability = availability[0] if availability else None
        if isinstance(availability, str):
            availability = availability.split("/")[-1]

    # Normalize URLs
    images = [normalize_url(img, url) or img for img in images]

    SELECTORS = "h2, h3, h4, h5, h6, button, a, div[tabindex]"
    # CONTENT_SELECTORS = "h2, h3, h4, h5, h6, p, ul > li:not(:has(a)), table"

    product_element = None

    selectors = [
        ('h1', page.locator('h1')),
        ('main', page.locator("main"))
    ]
    if images and images[0]:
        selectors.insert(0, ('img', page.locator(f'img[src="{images[0]}"]')))

    for name, locator in selectors:
        count = await locator.count()
        if count > 0:
            product_element = locator.first
            logger.info(f"Using {name} as product element (found {count} element(s))")
            break

    if not product_element:
        return ProductDetail(url=url)

    main_section = product_element.locator("xpath=..")
    depth = 0

    descs: dict[str, Any] = {}        # text -> locator
    traversed: Set[str] = set() # track element handles

    # climb up DOM
    while True:
        tag = await main_section.evaluate("(el) => el.nodeName.toLowerCase()")
        if tag == "body":
            break

        nodes = main_section.locator(SELECTORS)
        count = await nodes.count()

        for i in range(count):
            node = nodes.nth(i)
            uid = await node.evaluate("""
                el => {
                    if (!el.__uid) {
                        el.__uid = Math.random().toString(36).slice(2);
                    }
                    return el.__uid;
                }
                """)

            if uid in traversed:
                continue

            text = (await node.inner_text() or "").lower()

            has_description = re.search(r"(desc|détail|detail|en savoir plus)", text)
            fiche_technique = re.search(r"fiche technique", text)
            has_specs = re.search(r"(specification|spécification)", text)

            if has_description or fiche_technique or has_specs:
                if text not in descs:
                    descs[text] = node

            traversed.add(uid)

        if descs:
            break

        main_section = main_section.locator("xpath=..")
        depth += 1

    product_details: dict[str, str] = {}
    anchor_parent = None

    for key, el in descs.items():

        # ---- CLICK (important for tabs) ----
        try:
            await el.click(timeout=1000)
        except:
            pass

        target = None

        # ---- href case ----
        href = await el.get_attribute("href")
        if href and href.startswith("#"):
            try:
                target = page.locator(f'css={href}')
            except Exception:
                target = None

        # ---- aria-controls case ----
        elif await el.get_attribute("aria-controls"):
            target_id = await el.get_attribute("aria-controls")
            try:
                target = page.locator(f'css=#{target_id}')
            except Exception:
                target = None

        text_nodes = []
        md = None

        if target:
            try:
                target_count = await target.count()
            except Exception:
                target_count = 0
        else:
            target_count = 0

        if target and target_count > 0:
            # text_nodes = target.locator(CONTENT_SELECTORS)
            md = MarkdownConverter().convert(await target.inner_html())
        else:
            anchor_parent = el.locator("xpath=..")
            text_nodes = anchor_parent.locator("h1, p, ul > li:not(:has(a)), table")

            # climb until content found
            while True:
                if await text_nodes.count() > 0:
                    break

                parent = anchor_parent.locator("xpath=..")
                if parent == main_section:
                    break

                anchor_parent = parent
                text_nodes = anchor_parent.locator("h1, p, ul > li:not(:has(a)), table")

        # ---- extract text ----
        if anchor_parent:
            # text_nodes = anchor_parent.locator(CONTENT_SELECTORS)
            md = MarkdownConverter().convert(await anchor_parent.inner_html())

        # values = []
        # for i in range(await text_nodes.count()):
        #     txt = (await text_nodes.nth(i).inner_text()).strip()
        #     if txt:
        #         values.append(txt)

        # product_details[key] = values
        if md:
            product_details[key] = md

    if not price:
        idx = 0
        parent2 = product_element.locator("xpath=..")

        while idx < depth - 1:
            if price_text := await parent2.inner_text():
                price = extract_price_text(price_text, compiled_price_patterns)
                if price:
                    break

            parent2 = parent2.locator("xpath=..")
            idx += 1

    if not currency:
        currency = "TND"

    if not availability:
        idx = 0
        parent2 = product_element.locator("xpath=..")
        while idx < depth - 1:
            if availability_text := await parent2.inner_text():
                if re.search(r"((en|in) stock|disponible)", availability_text.lower()):
                    availability = "InStock"
                    break
                if re.search(r"(épuisé|epuisé|rupture|out of stock)", availability_text.lower()):
                    availability = "OutOfStock"
                    break
            parent2 = parent2.locator("xpath=..")
            idx += 1

    if not availability or not price:
        product_details["main_product_full_content"] = MarkdownConverter().convert(await main_section.inner_html())

    return ProductDetail(
        url=url,
        title=title,
        price=price,
        currency=currency,
        description=description,
        images=images,
        sku=sku,
        brand=brand,
        availability=availability,
        on_page_details=product_details,
    )
