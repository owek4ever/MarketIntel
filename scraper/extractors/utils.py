from urllib.parse import urljoin, urlparse, urlunparse
from typing import Optional

def normalize_url(href: str, base_url: str = "") -> Optional[str]:
    """
    Resolve *href* against *base_url* and return a clean absolute URL.
    Returns None if href is empty, a fragment-only link, or javascript:.
    """
    if not href:
        return None
    href = href.strip()
    if href.startswith("javascript:") or href == "#":
        return None
    try:
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        # Re-serialise without fragment to normalise
        clean = urlunparse(parsed._replace(fragment=""))
        return clean if clean else None
    except Exception:
        return None