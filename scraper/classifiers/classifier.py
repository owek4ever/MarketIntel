from __future__ import annotations

import logging
import html
from typing import Any

from bs4 import BeautifulSoup

from classifiers.url_classifier import classify_url
from classifiers.pagination_type_classifier import detect_pagination_type
from playwright.async_api import Page


from .models import PageClassification, PageType

from .signals import (
    _RELATED_HINTS,
    count_time_markers,
    extract_meta_tags,
    has_filter_controls,
    has_related_section,
    has_schema_product,
    has_search_input,
)


logger = logging.getLogger(__name__)

# NOISE_SIGNALS = re.compile(
#     r"produits similaires"
#     r"|produits connexes"
#     r"|aussi aimer"
#     r"|vous aimerez aussi"
#     r"|produits associés"
#     r"|autres produits"
#     r"|voir aussi"
#     r"|produits recommandés"
#     r"|Produits dans la même"
#     r"|\w+ ont également apprécié"
#     r"|\w+ vous recommande"
#     r"|\w+ dans la même catégorie",
#     re.I,
# )

# def has_related_section(soup: BeautifulSoup, tag: str) -> bool:
#     related_headings = soup.find_all(tag)
#     for heading in related_headings:
#         if NOISE_SIGNALS.search(heading.get_text(" ", strip=True) or ""):
#             return True
#     return False


def get_main_heading(soup: BeautifulSoup) -> str | None:
    h1 = [c for c in soup.find_all("h1") if not _RELATED_HINTS.search(c.text or "")]
    if len(h1) == 1:
        return h1[0].text
    if len(h1) == 0:
        h2 = [c for c in soup.find_all("h2") if not _RELATED_HINTS.search(c.text or "")]
        if len(h2) == 1:
            return h2[0].text
    return None


async def classify_page(page: Page, soup: BeautifulSoup, url: str, seo_report: dict[str, Any]) -> PageClassification:

    if not soup:
        return PageClassification(page_type=PageType.UNKNOWN)

    # page_text = soup.get_text(" ", strip=True)

    schema_product = has_schema_product(soup)

    json_lds = seo_report.get("seo_attributes", {}).get("TechnicalSEOAnalyzer", {}).get("jsonLdData", [])

    json_ld = json_lds[0] if json_lds else {}

    metatypes = extract_meta_tags(soup)

    product_json_ld_count = sum(
        1 for item in json_ld.get("@graph", []) if (item.get("@type") or "").lower() == "product"
    )

    product_json_ld = [prd for prd in json_ld.get("@graph", []) if (prd.get("@type") or "").lower() == "product"]
    breadcrumb_json_ld = [prd for prd in json_ld.get("@graph", []) if (prd.get("@type") or "").lower().startswith("breadcrumb")]
    organization_json_ld = [prd for prd in json_ld.get("@graph", []) if (prd.get("@type") or "").lower().startswith("organization")]

    json_ld_name = (
        html.unescape((product_json_ld[0].get("name") or "") if product_json_ld else "")
        if product_json_ld
        else None
    )
    page_title = await page.title() or ""
    main_heading = get_main_heading(soup)
    main_heading = main_heading.replace(" ", "").lower() if main_heading else None

    is_product_name_main_heading = (
        main_heading == json_ld_name
        or main_heading == page_title.replace(" ", "").lower()
    )

    time_markers = count_time_markers(soup)

    has_search = None
    filter_controls = None
    pagination = None
    url_type = classify_url(url)

    has_search = has_search_input(soup)
    filter_controls = has_filter_controls(soup)
    pagination = await detect_pagination_type(page)

    if url_type in ["about", "contact", "event", "promo", "auth", "support", "rules"]:
        return PageClassification(
            page_type=PageType.OTHER,
            pagination=pagination,
            signals={
                "url_type": url_type,
                "json_ld": json_ld,
                "meta_types": metatypes,
                "time_markers": time_markers,
                "organization_json_ld": organization_json_ld[0] if organization_json_ld else {},
            },
            notes=f"{url_type} page detected via URL pattern",
        )

    if url_type == "home":
        signals = {
            "url_type": url_type,
            "json_ld": json_ld,
            "meta_types": metatypes,
            "time_markers": time_markers,
            "organization_json_ld": organization_json_ld[0] if organization_json_ld else {},
        }
        return PageClassification(
            page_type=PageType.GENERAL, pagination=pagination, signals=signals
        )

    if schema_product:
        related_section = await has_related_section(page)
        signals = {
            "url_type": url_type,
            "json_ld": json_ld,
            "product_json_ld": product_json_ld[0] if product_json_ld else {},
            "breadcrumb_json_ld": breadcrumb_json_ld[0] if breadcrumb_json_ld else {},
            "meta_types": metatypes,
            "schema_product": schema_product,
            "time_markers": time_markers,
            "has_related_section": related_section is not None,
            "organization_json_ld": organization_json_ld[0] if organization_json_ld else {},
        }
        return PageClassification(
            page_type=PageType.PRODUCT_DETAIL,
            pagination=pagination,
            signals=signals,
            notes="Strong product detail signals: URL pattern + schema.org Product",
        )
    
    if product_json_ld_count == 1 and is_product_name_main_heading:
        related_section = await has_related_section(page)
        signals = {
            "url_type": url_type,
            "json_ld": json_ld,
            "product_json_ld": product_json_ld[0] if product_json_ld else {},
            "breadcrumb_json_ld": breadcrumb_json_ld[0] if breadcrumb_json_ld else {},
            "meta_types": metatypes,
            "schema_product": schema_product,
            "time_markers": time_markers,
            "has_related_section": related_section is not None,
            "organization_json_ld": organization_json_ld[0] if organization_json_ld else {},
        }
        return PageClassification(
            page_type=PageType.PRODUCT_DETAIL,
            pagination=pagination,
            signals=signals,
            notes="Strong product detail signals: single Product in JSON-LD + main heading matches product name",
        )


    signals = {
        "url_type": url_type,
        "json_ld": json_ld,
        "product_json_ld": product_json_ld[0] if product_json_ld else {},
        "breadcrumb_json_ld": breadcrumb_json_ld[0] if breadcrumb_json_ld else {},
        "meta_types": metatypes,
        "schema_product": schema_product,
        "time_markers": time_markers,
        "has_search": has_search,
        "has_filters": filter_controls,
        "organization_json_ld": organization_json_ld[0] if organization_json_ld else {},
    }

    if filter_controls and pagination and pagination.get("type") != "not_found":
        return PageClassification(
            page_type=PageType.PRODUCT_LIST_PAGINATED,
            pagination=pagination,
            signals=signals,
            notes="Paginated product list detected via filters + pagination controls",
        )

    if filter_controls:
        return PageClassification(
            page_type=PageType.PRODUCT_LIST,
            pagination=pagination,
            signals=signals,
            notes="Detected product list via filter controls",
        )

    # if url_type == "category":
    #     return PageClassification(
    #         page_type=PageType.PRODUCT_LIST,
    #         pagination=pagination,
    #         signals=signals,
    #         notes="Detected category page via URL classifier",
    #     )

    if not schema_product and not (url_type == "product" or url_type == "category"):
        return PageClassification(
            page_type=PageType.CONTENT_LIST,
            pagination=pagination,
            signals=signals,
            notes="Detected content/blog list signals",
        )

    return PageClassification(
        page_type=PageType.UNKNOWN,
        pagination=pagination,
        signals=signals,
        notes="No strong signals matched",
    )
