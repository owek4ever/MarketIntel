"""Page classification and job routing for search-result URLs."""

from .classifier import classify_page
from .url_classifier import classify_url
from .pagination_type_classifier import detect_pagination_type, PaginationTypeInfo

from .models import PageClassification, PageType, PaginationInfo, ScrapeJob

__all__ = [
    "classify_page",
    "PageClassification",
    "PageType",
    "PaginationInfo",
    "ScrapeJob",
    "classify_url",
    "detect_pagination_type",
    "PaginationTypeInfo",
]
