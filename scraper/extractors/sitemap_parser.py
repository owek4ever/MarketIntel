"""
sitemap_parser.py — Fetch and parse sitemap XML files (both <sitemapindex>
and <urlset> formats).

Uses httpx for lightweight HTTP fetching (no browser needed for XML).
"""
from __future__ import annotations

import logging
import re
import random
import time
import unicodedata
from typing import List, Optional, Dict
from urllib.parse import unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from classifiers.models import UrlCategory
from classifiers.url_classifier import classify_url

from .models import DiscoveredUrl, DiscoverySource, SitemapEntry

logger = logging.getLogger(__name__)


def fetch_sitemap(url: str) -> Optional[str]:
    """
    Fetch a sitemap XML file via HTTP and return its raw text.
    Returns None on failure.
    """
    logger.info(f"Fetching sitemap: {url}")
    try:
        response = httpx.get(url, timeout=15, follow_redirects=True)
        if response.status_code != 200:
            logger.warning(f"Sitemap {url} returned status {response.status_code}.")
            return None
        text = response.text
        if not text.strip():
            return None
        return text
    except Exception as e:
        logger.warning(f"Failed to fetch sitemap {url}: {e}")
        return None


def parse_sitemap_xml(xml_text: str) -> tuple[List[SitemapEntry], List[str]]:
    """
    Parse a sitemap XML string.

    Returns a tuple of (url_entries, child_sitemap_urls):
        - url_entries: list of SitemapEntry from <urlset><url> elements
        - child_sitemap_urls: list of sitemap URLs from <sitemapindex><sitemap> elements

    Handles both <sitemapindex> (index pointing to other sitemaps) and
    <urlset> (actual URL list) formats.
    """
    soup = BeautifulSoup(xml_text, "lxml-xml")

    entries: List[SitemapEntry] = []
    child_sitemaps: List[str] = []

    # Check for sitemap index: <sitemapindex> -> <sitemap> -> <loc>
    for sitemap_tag in soup.find_all("sitemap"):
        loc = sitemap_tag.find("loc")
        if loc and loc.string:
            child_sitemaps.append(loc.string.strip())

    # Check for URL set: <urlset> -> <url> -> <loc>, <lastmod>, etc.
    for url_tag in soup.find_all("url"):
        loc = url_tag.find("loc")
        if not loc or not loc.string:
            continue

        lastmod_tag = url_tag.find("lastmod")
        changefreq_tag = url_tag.find("changefreq")
        priority_tag = url_tag.find("priority")

        entry = SitemapEntry(
            loc=loc.string.strip(),
            lastmod=lastmod_tag.string.strip() if lastmod_tag and lastmod_tag.string else None,
            changefreq=changefreq_tag.string.strip() if changefreq_tag and changefreq_tag.string else None,
            priority=float(priority_tag.string.strip()) if priority_tag and priority_tag.string else None,
        )
        entries.append(entry)

    return entries, child_sitemaps


def fetch_and_parse_all_sitemaps(
    sitemap_urls: List[str],
    *,
    max_sitemaps: int = 50,
) -> List[SitemapEntry]:
    """
    Recursively fetch and parse sitemaps (following sitemap index files).
    Stops after processing max_sitemaps files to avoid runaway crawls.

    Each SitemapEntry records which sitemap file it originated from via
    the ``source_sitemap`` field.

    Returns a flat list of all SitemapEntry objects discovered.
    """
    all_entries: List[SitemapEntry] = []
    visited: set[str] = set()
    queue = list(sitemap_urls)

    while queue and len(visited) < max_sitemaps:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        xml_text = fetch_sitemap(url)
        time.sleep(random.randint(8, 15))

        if not xml_text:
            continue

        entries, child_sitemaps = parse_sitemap_xml(xml_text)

        # Tag every entry with the sitemap it came from
        for entry in entries:
            entry.source_sitemap = url

        all_entries.extend(entries)

        # Queue child sitemaps for processing
        for child_url in child_sitemaps:
            if child_url not in visited:
                queue.append(child_url)

    logger.info(
        f"Parsed {len(visited)} sitemap(s), found {len(all_entries)} URL entries."
    )
    return all_entries


# ---------------------------------------------------------------------------
# Sitemap-name classification
# ---------------------------------------------------------------------------

# Patterns to detect the *type* of content from the sitemap filename itself.
# Checked against the filename portion of the sitemap URL (e.g. "product-sitemap1.xml").

_SITEMAP_PRODUCT_PATTERNS = [
    re.compile(r"product[-_]sitemap", re.IGNORECASE),
    re.compile(r"produit[-_]sitemap", re.IGNORECASE),
    re.compile(r"sitemap[-_]product", re.IGNORECASE),
]

_SITEMAP_CATEGORY_PATTERNS = [
    re.compile(r"category[-_]sitemap", re.IGNORECASE),
    re.compile(r"categorie[-_]sitemap", re.IGNORECASE),
    re.compile(r"product[_-]cat[-_]sitemap", re.IGNORECASE),
    re.compile(r"project[_-]cat[-_]sitemap", re.IGNORECASE),
    re.compile(r"sitemap[-_]categor", re.IGNORECASE),
]

_SITEMAP_SKIP_PATTERNS = [
    re.compile(r"post[-_]sitemap", re.IGNORECASE),
    re.compile(r"page[-_]sitemap", re.IGNORECASE),
    re.compile(r"cms[_-]block[-_]sitemap", re.IGNORECASE),
    re.compile(r"portfolio[-_]sitemap", re.IGNORECASE),
    re.compile(r"product[_-]tag[-_]sitemap", re.IGNORECASE),
    re.compile(r"basel[_-]sidebar[-_]sitemap", re.IGNORECASE),
    re.compile(r"author[-_]sitemap", re.IGNORECASE),
]


def classify_sitemap_name(sitemap_url: str) -> Optional[UrlCategory]:
    """
    Inspect a sitemap URL's filename to determine the type of content it holds.

    Returns:
        UrlCategory.PRODUCT  — sitemap clearly holds products
        UrlCategory.CATEGORY — sitemap clearly holds categories
        UrlCategory.OTHER    — sitemap is known non-product/non-category (blog, pages …)
        None                 — no signal from the filename
    """
    # Extract just the filename: "product-sitemap1.xml"
    path = urlparse(sitemap_url).path
    filename = path.rsplit("/", 1)[-1] if "/" in path else path

    for pat in _SITEMAP_SKIP_PATTERNS:
        if pat.search(filename):
            return UrlCategory.OTHER

    for pat in _SITEMAP_PRODUCT_PATTERNS:
        if pat.search(filename):
            return UrlCategory.PRODUCT

    for pat in _SITEMAP_CATEGORY_PATTERNS:
        if pat.search(filename):
            return UrlCategory.CATEGORY

    return None


def classify_sitemap_entries(entries: List[SitemapEntry]) -> Dict[str, List[Dict]]:
    """
    Convert a list of SitemapEntry objects into classified DiscoveredUrl objects.

    If an entry's ``source_sitemap`` provides a strong classification signal
    (via the sitemap filename), that classification is used directly.
    Otherwise, the URL-level heuristics are applied.
    """
    # Pre-compute sitemap-name classifications (cache per sitemap URL)
    _sitemap_hint_cache: dict[str, Optional[UrlCategory]] = {}

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

    for entry in entries:
        category: Optional[UrlCategory] = None

        # Try sitemap-name hint first
        if entry.source_sitemap:
            if entry.source_sitemap not in _sitemap_hint_cache:
                _sitemap_hint_cache[entry.source_sitemap] = classify_sitemap_name(
                    entry.source_sitemap
                )
            category = _sitemap_hint_cache[entry.source_sitemap]

        # Fall back to URL-level classification
        if category is None:
            category = classify_url(entry.loc)

        results[category.value].append(DiscoveredUrl(
            url=entry.loc,
            lastmod=entry.lastmod,
            changefreq=entry.changefreq,
            category=category,
            source=DiscoverySource.SITEMAP,
        ).to_dict())

    return results
