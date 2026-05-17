import time
import random
import logging
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

class ProxyStore:
    def __init__(self, redis: Redis, hourly_limit: int, daily_limit: int):
        self.redis = redis
        self.hourly_limit = hourly_limit
        self.daily_limit = daily_limit
        self.key_available = "proxies:available"
        self.key_failed = "proxies:failed"

    async def sync_proxies(self, proxy_list: list[str]):
        """Replaces the available proxy set with the new n8n payload."""
        if not proxy_list:
            return
            
        temp_key = "proxies:temp_sync"
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.delete(temp_key)
            pipe.sadd(temp_key, *proxy_list)
            pipe.rename(temp_key, self.key_available)
            await pipe.execute()

    async def get_best_proxy(self, domain: str) -> str | None:
        """Finds a random healthy proxy that hasn't hit its limits."""
        proxies = await self.redis.smembers(self.key_available) # type: ignore
        if not proxies:
            return None
            
        proxies_list = list(proxies)
        random.shuffle(proxies_list)
        
        current_hour = int(time.time() // 3600)
        current_day = int(time.time() // 86400)
        
        for proxy_bytes in proxies_list:
            proxy = proxy_bytes.decode("utf-8") if isinstance(proxy_bytes, bytes) else proxy_bytes
            
            # Check if temporarily banned
            failed_key = f"failed_proxy:{proxy}"
            is_failed = await self.redis.get(failed_key)
            if is_failed:
                continue

            h_key = f"rate:{proxy}:{domain}:h:{current_hour}"
            d_key = f"rate:{proxy}:{domain}:d:{current_day}"
            
            # Fetch counter values
            res = await self.redis.mget(h_key, d_key)
            h_count = int(res[0] or 0)
            d_count = int(res[1] or 0)
            
            if h_count < self.hourly_limit and d_count < self.daily_limit:
                return proxy
                
        return None

    async def record_usage(self, proxy: str, domain: str):
        """Increments the rate limit counters for a proxy/domain combination."""
        current_hour = int(time.time() // 3600)
        current_day = int(time.time() // 86400)
        
        h_key = f"rate:{proxy}:{domain}:h:{current_hour}"
        d_key = f"rate:{proxy}:{domain}:d:{current_day}"
        
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(h_key)
            pipe.expire(h_key, 3600 * 2)  # Keep tracker for 2 hours
            pipe.incr(d_key)
            pipe.expire(d_key, 86400 * 2) # Keep tracker for 2 days
            await pipe.execute()
            
    async def report_failure(self, proxy: str):
        """Temporarily bans a proxy if it fails to connect."""
        logger.warning(f"Reporting failure for proxy {proxy}")
        # Add to failed set and expire after some time (using a string + TTL or sorted set)
        # For simplicity, we just use string key `failed_proxy:<ip>` with short TTL
        failed_key = f"failed_proxy:{proxy}"
        await self.redis.set(failed_key, "1", ex=600)  # ban for 10 minutes
        # We can check this key in get_best_proxy
