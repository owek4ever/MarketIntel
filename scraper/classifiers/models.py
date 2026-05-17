from __future__ import annotations


from dataclasses import dataclass, field

from enum import Enum

from typing import Any, Dict, List, Optional

from classifiers.pagination_type_classifier import PaginationTypeInfo

class UrlCategory(str, Enum):
    """Classification of a discovered URL."""

    HOME = "home"
    PRODUCT = "product"
    CATEGORY = "category"
    OTHER = "other"
    BLOG = "blog"
    NEWS = "news"
    ABOUT = "about"
    CONTACT = "contact"
    EVENT = "event"
    PROMO = "promo"
    AUTH = "auth"
    SUPPORT = "support"
    RULES = "rules"

class PageType(str, Enum):
    GENERAL = "general"
    PRODUCT_LIST = "product_list"
    PRODUCT_LIST_PAGINATED = "product_list_paginated"
    PRODUCT_DETAIL = "product_detail"
    CONTENT_LIST = "content_list"
    UNKNOWN = "unknown"
    OTHER = "other"


@dataclass
class PaginationInfo:
    has_pagination: bool

    hints: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:

        return {"has_pagination": self.has_pagination, "hints": list(self.hints)}


@dataclass
class PageClassification:
    page_type: PageType

    pagination: Optional[PaginationTypeInfo] = None

    signals: Dict[str, Any] = field(default_factory=dict)

    notes: str = ""

    def to_dict(self) -> dict:

        return {
            "page_type": self.page_type.value,
            "pagination": self.pagination,
            "signals": self.signals,
            "notes": self.notes,
        }


@dataclass
class ScrapeJob:
    url: str

    page_type: PageType

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:

        return {
            "url": self.url,
            "page_type": self.page_type.value,
            "metadata": self.metadata,
        }
