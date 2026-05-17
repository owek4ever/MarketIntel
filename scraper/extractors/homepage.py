"""
homepage.py — Extract category and product URLs from a homepage.
"""

from __future__ import annotations
import json
import re
import unicodedata
from typing import Any, Dict, List
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .models import (
    CrawlResult,
    DiscoveredUrl,
    DiscoverySource,
)
from .utils import normalize_url
from .sitemap_parser import classify_url
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)

_EXCLUDED_FRAGMENTS = (
    "#",
    "javascript:",
    "mailto:",
    "tel:",
    "login",
    "signup",
    "register",
    "account",
    "cart",
    "checkout",
    "wishlist",
    "compare",
    "privacy",
    "terms",
    "cookie",
    "search",
    # "contact",
    # "help",
    # "faq",
    # "support",
    "tracking",
    "returns",
    "compte",
    "connexion",
    "wish",
    "panier",
)

# _OTHER_PAGE_TEXT_HINTS = (
#     "about",
#     "about us",
#     "a propos",
#     "contact",
#     "event",
#     "events",
#     "evenement",
#     "evenements",
#     "blog",
#     "blogs",
#     "qui sommes",
#     "accueil",
#     "acceuil",
#     "actualit",
#     "promo",
#     "promotion",
#     "promotions",
#     "historique",
# )


def extract_metadata(html: str, base_url: str) -> dict[str, Any]:
    soup = _parse_html(html)
    # add jsonld
    jsonld = soup.find("script", type="application/ld+json")
    if jsonld:
        jsonld = json.loads(jsonld.string)

    description = soup.find("meta", attrs={"name": "description"})
    keywords = soup.find("meta", attrs={"name": "keywords"})
    author = soup.find("meta", attrs={"name": "author"})
    robots = soup.find("meta", attrs={"name": "robots"})
    canonical = soup.find("link", attrs={"rel": "canonical"})
    favicon = soup.find("link", attrs={"rel": "icon"})
    logo = soup.find("img", attrs={"alt": "logo"})
    facebook = soup.find("meta", attrs={"property": "og:site_name"})
    twitter = soup.find("meta", attrs={"property": "og:site_name"})
    instagram = soup.find("meta", attrs={"property": "og:site_name"})
    linkedin = soup.find("meta", attrs={"property": "og:site_name"})
    youtube = soup.find("meta", attrs={"property": "og:site_name"})
    locale = soup.find("meta", attrs={"property": "og:locale"})
    page_type = soup.find("meta", attrs={"property": "og:type"})
    updated_time = soup.find("meta", attrs={"property": "og:updated_time"})
    published_time = soup.find("meta", attrs={"property": "article:published_time"})
    modified_time = soup.find("meta", attrs={"property": "article:modified_time"})
    twitter_card = soup.find("meta", attrs={"name": "twitter:card"})
    twitter_title = soup.find("meta", attrs={"name": "twitter:title"})
    twitter_description = soup.find("meta", attrs={"name": "twitter:description"})
    twitter_label1 = soup.find("meta", attrs={"name": "twitter:label1"})
    twitter_data1 = soup.find("meta", attrs={"name": "twitter:data1"})
    twitter_label2 = soup.find("meta", attrs={"name": "twitter:label2"})
    twitter_data2 = soup.find("meta", attrs={"name": "twitter:data2"})
    image = soup.find("meta", attrs={"property": "og:image"})
    image_secure_url = soup.find("meta", attrs={"property": "og:image:secure_url"})
    image_width = soup.find("meta", attrs={"property": "og:image:width"})
    image_height = soup.find("meta", attrs={"property": "og:image:height"})
    image_alt = soup.find("meta", attrs={"property": "og:image:alt"})
    image_type = soup.find("meta", attrs={"property": "og:image:type"})

    metadata = {
        "title": soup.title.string if soup.title else "",
        "description": description["content"] if description else "",
        "keywords": keywords["content"] if keywords else "",
        "author": author["content"] if author else "",
        "robots": robots["content"] if robots else "",
        "canonical": canonical["href"] if canonical else "",
        "favicon": favicon["href"] if favicon else "",
        "logo": logo["src"] if logo else "",
        "locale": locale["content"] if locale else "",
        "page_type": page_type["content"] if page_type else "",
        "updated_time": updated_time["content"] if updated_time else "",
        "published_time": published_time["content"] if published_time else "",
        "modified_time": modified_time["content"] if modified_time else "",
        "twitter_card": twitter_card["content"] if twitter_card else "",
        "twitter_title": twitter_title["content"] if twitter_title else "",
        "twitter_description": twitter_description["content"] if twitter_description else "",
        "twitter_label1": twitter_label1["content"] if twitter_label1 else "",
        "twitter_data1": twitter_data1["content"] if twitter_data1 else "",
        "twitter_label2": twitter_label2["content"] if twitter_label2 else "",
        "twitter_data2": twitter_data2["content"] if twitter_data2 else "",
        "social_media": {
            "facebook": facebook["content"] if facebook else "",
            "twitter": twitter["content"] if twitter else "",
            "instagram": instagram["content"] if instagram else "",
            "linkedin": linkedin["content"] if linkedin else "",
            "youtube": youtube["content"] if youtube else "",
        },
        "image": {
            "image": image["content"] if image else "",
            "image_secure_url": image_secure_url["content"] if image_secure_url else "",
            "image_width": image_width["content"] if image_width else "",
            "image_height": image_height["content"] if image_height else "",
            "image_alt": image_alt["content"] if image_alt else "",
            "image_type": image_type["content"] if image_type else "",
        },
    }
    return metadata
    


def _parse_html(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def _is_excluded_href(href: str) -> bool:
    lowered = href.lower()
    return any(fragment in lowered for fragment in _EXCLUDED_FRAGMENTS)


def _same_host(url: str, base_url: str) -> bool:
    if not base_url:
        return True
    try:
        return urlparse(url).netloc == urlparse(base_url).netloc
    except Exception:
        return True


def _anchor_context_hints(tag) -> str:
    attrs = " ".join([tag.get("id") or "", " ".join(tag.get("class") or [])]).lower()
    return attrs


def _normalize_text_for_matching(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def is_base_url(url: str) -> bool:
    reg = re.compile(r"^https?://[www\.]?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}/?$")
    return reg.match(url) is not None

def classify_urls(urls: List[str]) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {
        "product": [],
        "category": [],
        "other": [],
        "blog": [],
        "news": [],
        "about": [],
        "contact": [],
        "event": [],
        "promo": [],
        "auth": [],
        "support": [],
        "rules": [],
    }

    for url in urls:
        url_category = classify_url(url)
        result[url_category.value].append(url)

    return result
    

def extract_urls(
    html: str,
    url: str = "",
) -> Dict[str, List[Dict]]:
    """
    Extract category and product URLs from a homepage.
    Returns HomepageUrls with category_urls, product_urls, and other_urls.
    """
    if not html:
        return {
            "product": [],
            "category": [],
            "other": [],
            "blog": [],
            "news": [],
            "about": [],
            "contact": [],
            "event": [],
            "promo": [],
            "auth": [],
            "support": [],
            "rules": [],
        }

    soup = _parse_html(html)

    selectors = [
        "nav a[href]",
        "header a[href]",
        "main a[href]",
        "li a[href]",
    ]

    seen = set()
    results: Dict[str, List[Dict]] = {
        "product": [],
        "category": [],
        "other": [],
        "blog": [],
        "news": [],
        "about": [],
        "contact": [],
        "event": [],
        "promo": [],
        "auth": [],
        "support": [],
        "rules": [],
    }

    for selector in selectors:
        for a in soup.select(selector):
            href = a.get("href")
            if not href:
                continue
            if _is_excluded_href(href):
                continue
            if is_base_url(href):
                continue

            normalized = normalize_url(href, url)
            if not normalized:
                continue
            if not _same_host(normalized, url):
                continue

            if normalized in seen:
                continue
            seen.add(normalized)

            # anchor_text = _normalize_text_for_matching(a.get_text(" ", strip=True) or "")
            # context_hints = _normalize_text_for_matching(_anchor_context_hints(a))

            # if any(term in anchor_text for term in _OTHER_PAGE_TEXT_HINTS) or any(
            #     term in context_hints for term in _OTHER_PAGE_TEXT_HINTS
            # ):
            #     results["category"].append(normalized)
            #     continue

            url_category = classify_url(normalized)
            results[url_category.value].append(DiscoveredUrl(
                url=normalized,
                category=url_category,
                source=DiscoverySource.HOMEPAGE,
            ).to_dict())

    return results


async def extract_urls_from_page(base_url: str, page: "Page") -> CrawlResult:
    """
    Navigate to the homepage, extract all links, and classify them
    into product / category / other.

    Delegates the heavy lifting to extract_homepage_urls(),
    which already handles anchor extraction and heuristic classification.

    Parameters
    ----------
    base_url : str
        The website's root URL (e.g. "https://egm.tn").
    page : Page
        An active Playwright page instance.

    Returns
    -------
    CrawlResult
        With source = DiscoverySource.HOMEPAGE and the classified URLs.
    """
    result = CrawlResult(base_url=base_url, source=DiscoverySource.HOMEPAGE)

    try:
        logger.info(f"Crawling homepage: {base_url}")
        # sb.open(base_url)
        await page.goto(base_url)
        # html = sb.get_page_source() or ""
        html = await page.content() or ""

        if not html.strip():
            result.error = "Homepage returned empty content."
            return result
        
        # extract all metadata
        metadata = extract_metadata(html, base_url)
        result.metadata = metadata

        homepage_data = extract_urls(html, base_url)
        result.urls = homepage_data

        logger.info(
            f"found {result} category, "
            f"{len(homepage_data.get('product', []))} product, "
            f"and other URLs."
        )

    except Exception as e:
        logger.error(f"Error crawling homepage {base_url}: {e}")
        result.error = str(e)

    return result
