import asyncio
import httpx
import logging
from store import ProxyStore
from config import Config

logger = logging.getLogger(__name__)

async def fetch_and_sync_proxies(store: ProxyStore) -> None:
    """Fetches proxy payload from n8n webhook and stores it."""
    url = Config.N8N_PROXY_URL
    logger.debug(f"Fetching properties from n8n: {url}")
    
    try:
        headers = {Config.N8N_PROXY_AUTH_HEADER_NAME: Config.N8N_PROXY_AUTH_HEADER_VALUE}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            content = response.json()
            
            proxies = []
            
            if isinstance(content, dict) and "result" in content:
                items = content["result"]
            elif isinstance(content, list):
                items = content
            elif isinstance(content, str):
                # Fallback to legacy text payload parsing
                items = []
                for line in content.splitlines():
                    line = line.strip()
                    if line and ":" in line:
                        proxies.append(line)
            else:
                items = []

            for item in items:
                if isinstance(item, dict):
                    # Skip invalid proxies if "valid" flag is explicitly set to false
                    if item.get("valid", True) is False:
                        continue
                        
                    ip = item.get("proxy_address")
                    port = item.get("port")
                    username = item.get("username")
                    password = item.get("password")
                    
                    if ip and port:
                        if username and password:
                            proxies.append(f"{username}:{password}@{ip}:{port}")
                        else:
                            proxies.append(f"{ip}:{port}")
            
            if proxies:
                await store.sync_proxies(proxies)
                logger.info(f"Successfully synced {len(proxies)} proxies from n8n.")
            else:
                logger.warning(f"Received empty or improperly formatted proxy list from n8n. Payload: {content[:100]}...")
                
    except httpx.RequestError as exc:
        logger.error(f"HTTP exception occurred while fetching proxies: {exc}")
    except Exception as exc:
        logger.error(f"Unexpected error in n8n sync: {exc}")

async def sync_loop(store: ProxyStore) -> None:
    """Background daemon loop to periodically refresh proxies."""
    logger.info(f"Starting n8n proxy sync loop (Interval: {Config.SYNC_INTERVAL_SECONDS}s)")
    while True:
        await fetch_and_sync_proxies(store)
        await asyncio.sleep(Config.SYNC_INTERVAL_SECONDS)
