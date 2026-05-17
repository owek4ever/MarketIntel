from __future__ import annotations
from playwright.async_api import Page


from typing import Any


from bs4 import BeautifulSoup

from .classifier import classify_page

from .models import ScrapeJob


async def classify_page_from_html(
    page: Page,
    html: str,
    url: str,
    seo_report: dict[str, Any],
) -> ScrapeJob:
    soup = BeautifulSoup(html, "lxml")

    classification = await classify_page(page, soup, url, seo_report)

    metadata = {
        "page_type": classification.page_type,
        "pagination": classification.pagination,
        "signals": classification.signals,
        "notes": classification.notes,
    }

    return ScrapeJob(url=url, page_type=classification.page_type, metadata=metadata)
