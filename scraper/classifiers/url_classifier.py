# ---------------------------------------------------------------------------
# URL classification helpers
# ---------------------------------------------------------------------------

import re
from typing import Optional
import unicodedata
from urllib.parse import unquote, urlparse

from .models import UrlCategory


_CATEGORY_PATTERNS = [
    r"(nos\-)?categor(?:y|ie|ies)?/[0-9a-zA-Z\-]+/?",
    r"/(nos\-)?categor",            # /category/, /categories/, /categorie/
    r"/collection[s]?/",
    r"/catalog\/?",
    r"/products",
    r"/produits",
    r"/c/",
    r"/cat/",
    r"\/\d{1,3}-[0-9a-zA-Z+\-?]+\/?$",
    # r"/accueil",
    r"[nos\-]?marque[s]?",
]

_PRODUCT_PATTERNS = [
    r"/product[s]?/[0-9\w-]+/?",
    r"/produit[s]?/[0-9\w-]+/?",
    r"/item[s]?/[0-9\w-]+/?",
    r"/p/[0-9\w-]+/?",
    r"[a-zA-Z][a-zA-Z0-9-]+-\d+\.html$",   # PrestaShop: slug-ID.html
    r"[?&](?:id|pid|product_id|item_id)=\d+",
    r"/product/[0-9\w-]+/?$",                    # WooCommerce
]

_BLOG_PATTERNS = [
    r"/blog[s]?",
    r"/article[s]?",
    r"/post[s]?",
    r"/tag[s]?",
    r"/wiki",
    r"/content",
]

_NEWS_PATTERNS = [
    r"/news",
    r"/actualit",
]

_ABOUT_PATTERNS = [
    r"/about[\w-]*",
    r"/a[-_/]?propos[\w-]*",
    r"/qui[-_/]?sommes(?:[-_/]?nous)?",
]

_CONTACT_PATTERNS = [
    r"/contact[\w-]*",
]

_EVENT_PATTERNS = [
    r"/event[s]?[\w-]*",
    r"/evenement[s]?[\w-]*",
]

_PROMO_PATTERNS = [
    r"/promo(?:tion)?s?",
    r"/offre[s]?",
    r"/pack[s]?",
]

_AUTH_PATTERNS = [
    r"/login",
    r"/logout",
    r"password",
    r"register|registration",
    r"account",
    r"checkout",
    r"\bcart\b",
    r"wishlist",
]

_SUPPORT_PATTERNS = [
    r"ticket[s]?",
]

_ANTI_PRODUCT_PATTERNS = [
    # r"/\d{4}/\d{2}/",       # Date-based paths
    r"/author",
    r"/page/\d+",
]

_RULES_PATTERNS = [
    r"conditions",
    r"mentions",
    r"politique",
    r"confidentialite",
]

_compiled_category = [re.compile(p, re.IGNORECASE) for p in _CATEGORY_PATTERNS]
_compiled_product = [re.compile(p, re.IGNORECASE) for p in _PRODUCT_PATTERNS]
_compiled_blog = [re.compile(p, re.IGNORECASE) for p in _BLOG_PATTERNS]
_compiled_news = [re.compile(p, re.IGNORECASE) for p in _NEWS_PATTERNS]
_compiled_about = [re.compile(p, re.IGNORECASE) for p in _ABOUT_PATTERNS]
_compiled_contact = [re.compile(p, re.IGNORECASE) for p in _CONTACT_PATTERNS]
_compiled_event = [re.compile(p, re.IGNORECASE) for p in _EVENT_PATTERNS]
_compiled_promo = [re.compile(p, re.IGNORECASE) for p in _PROMO_PATTERNS]
_compiled_auth = [re.compile(p, re.IGNORECASE) for p in _AUTH_PATTERNS]
_compiled_rules = [re.compile(p, re.IGNORECASE) for p in _RULES_PATTERNS]
_compiled_support = [re.compile(p, re.IGNORECASE) for p in _SUPPORT_PATTERNS]
_compiled_anti = [re.compile(p, re.IGNORECASE) for p in _ANTI_PRODUCT_PATTERNS]

# Path prefixes that act as a shop root (products live deep under these)
_SHOP_ROOT_SEGMENTS = {"shop", "boutique", "cat", "produits"}

# A "slug" segment: lowercase letters/digits/hyphens, at least 2 chars, not all digits
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,}$")


def _normalize_url_for_matching(url: str) -> str:
    """Return a lowercase, unquoted, ASCII-safe URL string for regex matching."""
    decoded = unquote(url)
    ascii_url = unicodedata.normalize("NFKD", decoded).encode("ascii", "ignore").decode("ascii")
    return ascii_url.lower()


def _is_slug(segment: str) -> bool:
    """Return True if the segment looks like a product slug (not a pure number)."""
    return bool(_SLUG_RE.match(segment)) and not segment.isdigit()


def _classify_by_depth(url: str) -> Optional[UrlCategory]:
    """
    Analyse the URL path depth to distinguish products from categories
    under shop-root prefixes.

    Heuristic:
        /shop/                          → CATEGORY  (just the root)
        /shop/cat1/                     → CATEGORY  (1 level below root)
        /shop/cat1/cat2/                → CATEGORY  (2 levels — still navigational)
        /shop/cat1/cat2/cat3/slug/      → PRODUCT   (3+ levels below root with slug tail)
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return None

    segments = [s for s in path.split("/") if s]
    if not segments:
        return None

    # Find a shop-root segment
    shop_idx: Optional[int] = None
    for i, seg in enumerate(segments):
        if seg.lower() in _SHOP_ROOT_SEGMENTS:
            shop_idx = i
            break

    if shop_idx is None:
        return None

    # Segments after the shop root
    after = segments[shop_idx + 1:]

    if len(after) <= 2:
        # /shop/ or /shop/cat1/ or /shop/cat1/cat2/ → CATEGORY
        return UrlCategory.CATEGORY

    # 3+ segments after shop root — check if the last segment is a slug
    if _is_slug(after[-1]):
        return UrlCategory.PRODUCT

    return None

def classify_url(url: str) -> UrlCategory:
    """
    Classify a single URL as PRODUCT, CATEGORY, or OTHER based on path heuristics.
    """
    matchable_url = _normalize_url_for_matching(url)

    # Check non-product content patterns first
    if any(pat.search(matchable_url) for pat in _compiled_anti):
        return UrlCategory.OTHER

    # Check category patterns
    if any(pat.search(matchable_url) for pat in _compiled_category):
        return UrlCategory.CATEGORY

    # Check product patterns
    if any(pat.search(matchable_url) for pat in _compiled_product):
        return UrlCategory.PRODUCT
    
    # Check blog patterns
    if any(pat.search(matchable_url) for pat in _compiled_blog):
        return UrlCategory.BLOG
    
    # Check news patterns
    if any(pat.search(matchable_url) for pat in _compiled_news):
        return UrlCategory.NEWS
    
    # Check about patterns
    if any(pat.search(matchable_url) for pat in _compiled_about):
        return UrlCategory.ABOUT
    
    # Check contact patterns
    if any(pat.search(matchable_url) for pat in _compiled_contact):
        return UrlCategory.CONTACT
    
    # Check event patterns
    if any(pat.search(matchable_url) for pat in _compiled_event):
        return UrlCategory.EVENT
    
    # Check promo patterns
    if any(pat.search(matchable_url) for pat in _compiled_promo):
        return UrlCategory.PROMO
    
    # Check auth patterns
    if any(pat.search(matchable_url) for pat in _compiled_auth):
        return UrlCategory.AUTH
    
    # Check support patterns
    if any(pat.search(matchable_url) for pat in _compiled_support):
        return UrlCategory.SUPPORT
    
    # Check rules patterns
    if any(pat.search(matchable_url) for pat in _compiled_rules):
        return UrlCategory.RULES

    # Depth-based analysis for /shop/-style paths
    depth_result = _classify_by_depth(matchable_url)
    if depth_result is not None:
        return depth_result

    return UrlCategory.OTHER