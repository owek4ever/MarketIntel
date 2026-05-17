from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.async_api import Locator, Page

# _BLOG_HINTS = ("blog", "news", "article", "post", "wiki", "press", "stories")
_DATE_RE = re.compile(r"\b(20\d{2}|19\d{2})[-/]\d{1,2}[-/]\d{1,2}\b")
# _PRODUCT_DETAIL_ID_RE = re.compile(r"-\d+\.html?$", re.I)
_HOME_INDEX_RE = re.compile(r"/index\.html?$", re.I)
FILTER_REGEX = re.compile(
    # r"\b(tri|sort|filtres?|trier\s*par|prix\s*croissant|prix\s*décroissant|tarif\s*croissant|tarif\s*décroissant|Affichage de [0-9]+\-[0-9]+|Sous-categories)\b",
    r"\b(tri|sort|trier\s*par|prix\s*croissant|prix\s*décroissant|tarif\s*croissant|tarif\s*décroissant|Affichage de [0-9]+\-[0-9]+|Sous-categories|Il y a \d+ produits)\b",
    re.I
)


_FILTER_SELECTORS = [
    "form#productsSortForm",
    "form.productsSortForm",
    "form.wd-product-filters",
    "select#selectProductSort",
    "form.nbrItemPage",
    "select#nb_item",
    "ul.display li#grid",
    "ul.display li#list",
]

_RELATED_HINTS = re.compile(
    r"produits similaires"
    r"|produits connexes"
    r"|aussi aimer"
    r"|vous aimerez aussi"
    r"|produits associés"
    r"|autres produits"
    r"|voir aussi"
    r"|produits recommandés"
    r"|Produits dans la même"
    r"|\w+ ont également apprécié"
    r"|\w+ vous recommande"
    r"|\w+ dans la même catégorie"
    r"|related"
    r"|similar"
    r"|you may also like"
    r"|products you may like"
    r"|produits similaires"
    r"|produits associes"
    r"|produits liés"
    r"|cross-sell"
    r"|upsell",
    re.I,
    # "accessoires",
)

# def _iter_jsonld_nodes(data: Any) -> Iterable[Dict[str, Any]]:
#     if isinstance(data, dict):
#         yield data
#         for value in data.values():
#             yield from _iter_jsonld_nodes(value)
#     elif isinstance(data, list):
#         for item in data:
#             yield from _iter_jsonld_nodes(item)


# def _is_product_type(type_value: Any) -> bool:
#     if isinstance(type_value, list):
#         return any(_is_product_type(v) for v in type_value)
#     return isinstance(type_value, str) and "product" in type_value.lower()


# def extract_json_ld(soup: BeautifulSoup) -> List[Dict[str, Any]]:
#     data = []
#     for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
#         raw = script.string or script.get_text(strip=True)
#         if not raw:
#             continue
#         try:
#             data.append(json.loads(raw))
#         except Exception:
#             continue

#     return data

# def find_jsonld_product(soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
#     data = extract_json_ld(soup)
#     if not data:
#         return None

#     for node in _iter_jsonld_nodes(data):
#         type_value = node.get("@type")
#         if type_value and _is_product_type(type_value):
#             return node

#     return None

def extract_jsonld_types(soup: BeautifulSoup) -> set[str]:
    types: set[str] = set()
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue

        def _collect(item):
            if isinstance(item, dict):
                t = item.get("@type")
                if isinstance(t, list):
                    types.update(str(x) for x in t)
                elif t:
                    types.add(str(t))
                for v in item.values():
                    _collect(v)
            elif isinstance(item, list):
                for v in item:
                    _collect(v)

        _collect(data)
    return types

def extract_meta_tags(soup: BeautifulSoup) -> dict:
    data = {}

    # Target meta tags with property or name
    meta_tags = soup.find_all("meta")

    for tag in meta_tags:
        key = tag.get("property") or tag.get("name")
        value = tag.get("content")

        if not key or not value:
            continue

        # Keep only relevant namespaces
        if key.startswith(("og:", "product:", "twitter:")): # type: ignore
            # Avoid overwriting (handle duplicates)
            if key not in data:
                data[key] = value

    return data

def has_schema_product(soup: BeautifulSoup) -> bool:
    types = extract_jsonld_types(soup)
    if any(t.lower() == "product" or "product" in t.lower() for t in types):
        return True

    og_type = soup.find("meta", attrs={"property": "og:type"})
    if og_type and "product" in (og_type.get("content") or "").lower(): # type: ignore
        return True

    products = soup.select('[itemtype*="schema.org/Product"]')
    if products:
        return len(products) == 1
    return False


# def count_add_to_cart_signals(soup: BeautifulSoup, config: ScoringConfig) -> int:
#     count = 0
#     keywords = [k.lower() for k in config.add_to_cart_keywords]
#     class_frags = [k.lower() for k in config.add_to_cart_class_fragments]

#     for tag in soup.find_all(["button", "a", "input"]):
#         text = (tag.get_text(" ", strip=True) or "").lower()
#         if text and any(k in text for k in keywords):
#             count += 1
#             continue
#         classes = " ".join(tag.get("class") or []).lower()
#         if classes and any(frag in classes for frag in class_frags):
#             count += 1

#     return count


# def count_price_matches(text: str, config: ScoringConfig) -> int:
#     if not text:
#         return 0
#     patterns = config.compiled_price_patterns()
#     matches = 0
#     for pattern in patterns:
#         matches += len(pattern.findall(text))
#     return matches


# def count_article_candidates(soup: BeautifulSoup) -> int:
#     count = len(soup.find_all("article"))
#     if count >= 3:
#         return count
#     # Fallback: class-based detection
#     for tag in soup.find_all(True):
#         classes = " ".join(tag.get("class") or []).lower()
#         if any(key in classes for key in ("post", "entry", "article", "blog")):
#             count += 1
#     return count


def count_time_markers(soup: BeautifulSoup) -> int:
    count = len(soup.find_all("time"))
    for meta in soup.find_all("meta", attrs={"property": re.compile(r"article:", re.I)}):
        if meta.get("content"):
            count += 1
    # Textual date markers
    text = soup.get_text(" ", strip=True)
    if text:
        count += len(_DATE_RE.findall(text))
    return count


# def url_has_blog_hint(url: str) -> bool:
#     try:
#         path = urlparse(url).path.lower()
#     except Exception:
#         path = url.lower()
#     return any(hint in path for hint in _BLOG_HINTS)


# def url_has_product_hint(url: str, config: ScoringConfig) -> bool:
#     try:
#         patterns = config.compiled_product_url_patterns()
#         anti = config.compiled_anti_product_patterns()
#         return matches_product_url(url, patterns, anti)
#     except Exception:
#         return False


def url_is_homepage(url: str) -> bool:
    try:
        path = urlparse(url).path or "/"
    except Exception:
        return False
    if path in ("", "/"):
        return True
    return bool(_HOME_INDEX_RE.search(path))


# def url_has_product_detail_hint(url: str, config: ScoringConfig) -> bool:
#     if url_has_product_hint(url, config):
#         return True
#     try:
#         path = urlparse(url).path or ""
#     except Exception:
#         path = url
#     if _PRODUCT_DETAIL_ID_RE.search(path):
#         return True
#     return False


# def url_has_category_hint(url: str) -> bool:
#     try:
#         path = urlparse(url).path or "/"
#     except Exception:
#         path = url
#     if path in ("", "/"):
#         return False
#     if path.count("/") <= 2 and path.endswith("/"):
#         return True
#     for frag in ("/category/", "/categories/", "/shop/", "/c/", "/catalogue"):
#         if frag in path.lower():
#             return True
#     return False


# def count_product_like_links(
#     soup: BeautifulSoup, base_url: str, config: ScoringConfig
# ) -> int:
#     patterns = config.compiled_product_url_patterns()
#     anti = config.compiled_anti_product_patterns()
#     count = 0
#     for a in soup.find_all("a", href=True):
#         href = normalize_url(a.get("href") or "", base_url) # type: ignore
#         if href and matches_product_url(href, patterns, anti):
#             count += 1
#     return count


# def count_nav_links(soup: BeautifulSoup) -> int:
#     count = 0
#     for nav in soup.find_all(["nav", "header"]):
#         count += len(nav.find_all("a", href=True))
#     return count


def has_search_input(soup: BeautifulSoup) -> bool:
    if soup.select_one('input[type="search"]'):
        return True
    for inp in soup.find_all("input"):
        name = (inp.get("name") or "").lower() # type: ignore
        placeholder = (inp.get("placeholder") or "").lower() # type: ignore
        if name in {"q", "s", "search", "query"}:
            return True
        if "search" in placeholder:
            return True
    return False


def has_filter_controls(soup: BeautifulSoup) -> bool:
    if soup.select_one(", ".join(_FILTER_SELECTORS)):
        return True

    body = soup.find("body")
    if body and body.find(string=FILTER_REGEX):
        return True

    return False


async def has_related_section(page: Page) -> Locator | None:
    # Headings with related-like text
    # heading_re = re.compile("|".join(re.escape(h) for h in _RELATED_HINTS), re.I)
    for tag in await page.locator("h2, h3, h4, h5").all():
        text = await tag.inner_text()
        if text and _RELATED_HINTS.search(text):
            return tag
    # Containers with related-like class/id
    elements_with_attrs = await page.locator("[id], [class]").all()
    for element in elements_with_attrs:
        element_id = await element.get_attribute("id") or ""
        class_attr = await element.get_attribute("class") or ""
        attrs = f"{element_id} {class_attr}".lower()

        if attrs and _RELATED_HINTS.search(attrs):
            return element
    return None
