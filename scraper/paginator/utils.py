import random
import asyncio
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


async def random_sleep(min_sec: float = 1.0, max_sec: float = 3.0) -> None:
    """Sleep for a random duration to mimic human interaction."""
    await asyncio.sleep(random.uniform(min_sec, max_sec))


# async def count_products(page: Page, selector: str) -> int:
#     """Count the number of visible products on the current page."""
#     try:
#         # sb.find_elements(selector, timeout=2)
#         return await page.locator(selector).count()
#     except Exception:
#         return 0


def get_next_page_url(base_url: str, param_name: str, next_page_num: int) -> str:
    """Construct the next URL by updating the pagination query parameter."""
    if param_name == "__path__":
        path = urlparse(base_url).path
        if re.search(r"/\d+/?$", path):
            new_path = re.sub(
                r"/(\d+)(/?)$", lambda m: f"/{next_page_num}{m.group(2)}", path
            )
        else:
            if path.endswith("/"):
                new_path = f"{path}{next_page_num}/"
            else:
                new_path = f"{path}/{next_page_num}/"
        return urlunparse(urlparse(base_url)._replace(path=new_path))
    
    parsed_url = urlparse(base_url)
    query_params = parse_qs(parsed_url.query)
    query_params[param_name] = [str(next_page_num)]
    new_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed_url._replace(query=new_query))
