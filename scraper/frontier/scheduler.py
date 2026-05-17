"""Atomic Redis scheduling primitives for the distributed frontier."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

from .domain_queue import DomainQueue
from .url_store import FrontierKeys, ScheduledURL
from datetime import datetime

    # 'budget_key', ARGV[9],
    # 'proxy_group', ARGV[10],
    # 'shard_key', ARGV[11]

ADD_URL_LUA = """
local added = redis.call('SET', KEYS[1], '1', 'EX', ARGV[12], 'NX')
if not added then
    return 0
end

redis.call(
    'HSET',
    KEYS[2],
    'id', ARGV[1],
    'priority', ARGV[2],
    'job_type', ARGV[3],
    'url', ARGV[4],
    'domain', ARGV[5],
    'retries', ARGV[6],
    'created_at', ARGV[7],
    'updated_at', ARGV[8],
    'status', ARGV[9],
    'queue_side', ARGV[10]
)

if ARGV[11] and ARGV[11] ~= "" then
    redis.call('HSET', KEYS[2], 'metadata', ARGV[11])
end

if ARGV[10] == 'left' then
    redis.call('LPUSH', KEYS[3], ARGV[1])
else
    redis.call('RPUSH', KEYS[3], ARGV[1])
end

redis.call('ZADD', KEYS[4], 'NX', 0, ARGV[5])

-- Also expire the URL metadata hash so it doesn't stay forever
redis.call('EXPIRE', KEYS[2], ARGV[12])

return 1
"""

LEASE_URL_LUA = """
local max_iterations = 100
local iterations = 0

while iterations < max_iterations do
    iterations = iterations + 1
    local ready = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, 1)
    if #ready == 0 then
        return nil
    end

    local domain = ready[1]
    local queue_key = ARGV[2] .. domain

    -- Check in-flight limit
    local inflight_count = tonumber(redis.call('HGET', KEYS[5], domain) or '0')
    local max_jobs = tonumber(ARGV[6])

    if inflight_count >= max_jobs then
        -- Domain is throttled, remove from ready_domains for now.
        -- It will be re-added when a job completes or fails.
        redis.call('ZREM', KEYS[1], domain)
    else
        local url_id = redis.call('LPOP', queue_key)
        if not url_id then
            redis.call('ZREM', KEYS[1], domain)
        else
            -- Increment in-flight count
            inflight_count = redis.call('HINCRBY', KEYS[5], domain, 1)

            local deadline = tonumber(ARGV[1]) + tonumber(ARGV[3])
            local pending = redis.call('LLEN', queue_key)

            if pending > 0 and inflight_count < max_jobs then
                -- Still ready to lease more from this domain
                redis.call('ZADD', KEYS[1], 0, domain)
            else
                -- No more URLs or reached limit
                redis.call('ZREM', KEYS[1], domain)
            end

            local lease_payload = cjson.encode({
                domain = domain,
                leased_at = tonumber(ARGV[1]),
                lease_deadline = deadline
            })
            redis.call('HSET', KEYS[2], url_id, lease_payload)
            redis.call('ZADD', KEYS[3], deadline, url_id)
            redis.call(
                'HSET',
                ARGV[5] .. url_id,
                'status', 'inflight',
                'started_at', ARGV[1],
                'updated_at', ARGV[1],
                'lease_deadline', tostring(deadline)
            )

            return {url_id, domain, tostring(deadline)}
        end
    end
end

return {'stale', 'batch_limit'}
"""

COMPLETE_URL_LUA = """
local removed = redis.call('HDEL', KEYS[1], ARGV[1])
redis.call('ZREM', KEYS[2], ARGV[1])
if removed == 0 then
    return 0
end

local domain = redis.call('HGET', KEYS[3], 'domain')
if domain then
    local inflight_count = redis.call('HINCRBY', KEYS[4], domain, -1)
    if inflight_count < 0 then
        redis.call('HSET', KEYS[4], domain, 0)
        inflight_count = 0
    end
    
    -- Re-add to ready_domains if it has pending URLs
    local queue_key = ARGV[3] .. domain
    if redis.call('LLEN', queue_key) > 0 then
        redis.call('ZADD', ARGV[4], 0, domain)
    end
end

redis.call(
    'HSET',
    KEYS[3],
    'status', 'completed',
    'completed_at', ARGV[2],
    'updated_at', ARGV[2]
)
redis.call('HDEL', KEYS[3], 'started_at', 'lease_deadline', 'next_retry_at')
return 1
"""

FAIL_URL_LUA = """
local removed = redis.call('HDEL', KEYS[1], ARGV[1])
redis.call('ZREM', KEYS[2], ARGV[1])
if removed == 0 then
    return 0
end

local domain = ARGV[2]
local inflight_count = redis.call('HINCRBY', KEYS[6], domain, -1)
if inflight_count < 0 then
    redis.call('HSET', KEYS[6], domain, 0)
    inflight_count = 0
end

-- Re-add to ready_domains if it has pending URLs (FAIL might not add to queue, it adds to retry_schedule)
-- But if it was throttled, and now it's not, we should check if it has other URLs.
local queue_key = ARGV[7] .. domain
if redis.call('LLEN', queue_key) > 0 then
    redis.call('ZADD', ARGV[8], 0, domain)
end

local retries = redis.call('HINCRBY', KEYS[3], 'retries', 1)
redis.call(
    'HSET',
    KEYS[3],
    'last_error', ARGV[3],
    'updated_at', ARGV[4]
)
redis.call('HDEL', KEYS[3], 'started_at', 'lease_deadline')

if retries > tonumber(ARGV[5]) then
    local url = redis.call('HGET', KEYS[3], 'url')
    redis.call(
        'HSET',
        KEYS[3],
        'status', 'failed',
        'failed_at', ARGV[4]
    )
    redis.call('HDEL', KEYS[3], 'next_retry_at')
    redis.call(
        'RPUSH',
        KEYS[5],
        cjson.encode({
            id = ARGV[1],
            url = url,
            domain = ARGV[2],
            retries = retries,
            error = ARGV[3],
            failed_at = tonumber(ARGV[4])
        })
    )
    return 2
end

redis.call(
    'HSET',
    KEYS[3],
    'status', 'retry_scheduled',
    'next_retry_at', ARGV[6]
)
redis.call('ZADD', KEYS[4], ARGV[6], ARGV[1])
return 1
"""

PROMOTE_RETRIES_LUA = """
local due_ids = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, ARGV[2])
local promoted = 0

for _, url_id in ipairs(due_ids) do
    if redis.call('ZREM', KEYS[1], url_id) == 1 then
        local url_key = ARGV[3] .. url_id
        local domain = redis.call('HGET', url_key, 'domain')
        local queue_side = redis.call('HGET', url_key, 'queue_side')

        if domain and domain ~= '' then
            local queue_key = ARGV[4] .. domain
            if queue_side == 'left' then
                redis.call('LPUSH', queue_key, url_id)
            else
                redis.call('RPUSH', queue_key, url_id)
            end
            redis.call('ZADD', KEYS[2], 'NX', 0, domain)
            redis.call(
                'HSET',
                url_key,
                'status', 'queued',
                'updated_at', ARGV[1]
            )
            redis.call('HDEL', url_key, 'next_retry_at')
            promoted = promoted + 1
        end
    end
end

return promoted
"""


@dataclass(slots=True)
class LeaseResult:
    """Represents the leased URL ID and timing information."""

    url_id: str
    domain: str
    lease_deadline: float


class RedisFrontierScheduler:
    """Coordinates atomic scheduling operations against Redis."""

    def __init__(
        self,
        redis: Redis,
        *,
        keys: FrontierKeys,
        domain_queue: DomainQueue,
        default_crawl_delay_seconds: float,
        max_jobs_per_domain: int,
        inflight_timeout_seconds: float,
        max_retries: int,
        retry_delay_seconds: float,
        retry_backoff_multiplier: float,
        max_retry_delay_seconds: float,
        seen_urls_ttl_seconds: int = 259200,
    ) -> None:
        self.redis = redis
        self.keys = keys
        self.domain_queue = domain_queue
        self.default_crawl_delay_seconds = max(0.0, default_crawl_delay_seconds)
        self.max_jobs_per_domain = max(1, max_jobs_per_domain)
        self.inflight_timeout_seconds = max(1.0, inflight_timeout_seconds)
        self.max_retries = max_retries
        self.retry_delay_seconds = max(0.0, retry_delay_seconds)
        self.retry_backoff_multiplier = max(1.0, retry_backoff_multiplier)
        self.max_retry_delay_seconds = max(
            self.retry_delay_seconds,
            max_retry_delay_seconds,
        )
        self.seen_urls_ttl_seconds = max(1, seen_urls_ttl_seconds)

        self._add_url_script = self.redis.register_script(ADD_URL_LUA)
        self._lease_url_script = self.redis.register_script(LEASE_URL_LUA)
        self._complete_url_script = self.redis.register_script(COMPLETE_URL_LUA)
        self._fail_url_script = self.redis.register_script(FAIL_URL_LUA)
        self._promote_retries_script = self.redis.register_script(PROMOTE_RETRIES_LUA)

    async def add_url(
        self,
        *,
        url_id: str,
        priority: int,
        job_type: str,
        url: str,
        domain: str,
        created_at: float,
        metadata: dict[str, Any] | None = None,
        # budget_key: str | None = None,
        # proxy_group: str | None = None,
        # shard_key: str | None = None,
    ) -> bool:
        """Adds a new URL if it has not been seen before."""

        metadata_str = json.dumps(metadata) if metadata else ""

        result = await self._add_url_script(
            keys=[
                self.keys.seen_url(url_id),
                self.keys.url_key(url_id),
                self.keys.domain_queue(domain),
                self.keys.ready_domains,
            ],
            args=[
                url_id,
                str(priority),
                job_type or "",
                url,
                domain,
                "0",
                str(created_at),
                str(created_at),
                "queued",
                self.domain_queue.push_side_for_priority(priority),
                metadata_str,
                str(self.seen_urls_ttl_seconds),
                # budget_key or "",
                # proxy_group or "",
                # shard_key or "",
            ],
        )
        return bool(result)

    async def lease_next_url(self, now: float | None = None) -> LeaseResult | None:
        """Claims the next available URL while enforcing domain job limits."""

        lease_time = time.time() if now is None else now

        while True:
            result = await self._lease_url_script(
                keys=[
                    self.keys.ready_domains,
                    self.keys.inflight,
                    self.keys.inflight_timeouts,
                    self.keys.domain_delays,
                    self.keys.domain_inflight,
                ],
                args=[
                    str(lease_time),
                    self.keys.domain_queue_prefix,
                    str(self.inflight_timeout_seconds),
                    str(self.default_crawl_delay_seconds),
                    self.keys.url_prefix,
                    str(self.max_jobs_per_domain),
                ],
            )

            if result is None:
                return None

            if result[0] == "stale":
                continue

            return LeaseResult(
                url_id=result[0],
                domain=result[1],
                lease_deadline=float(result[2]),
            )

    async def complete_url(self, url_id: str, *, now: float | None = None) -> bool:
        """Completes a leased URL and clears its inflight state."""

        completed_at = time.time() if now is None else now
        result = await self._complete_url_script(
            keys=[
                self.keys.inflight,
                self.keys.inflight_timeouts,
                self.keys.url_key(url_id),
                self.keys.domain_inflight,
            ],
            args=[
                url_id,
                str(completed_at),
                self.keys.domain_queue_prefix,
                self.keys.ready_domains,
            ],
        )
        return bool(result)

    async def fail_url(
        self,
        scheduled_url: ScheduledURL,
        *,
        error_message: str,
        now: float | None = None,
    ) -> str:
        """Retries or dead-letters a leased URL after worker failure."""

        failed_at = time.time() if now is None else now
        retry_delay = self._compute_retry_delay_seconds(scheduled_url.retries + 1)
        next_retry_at = failed_at + retry_delay
        result = await self._fail_url_script(
            keys=[
                self.keys.inflight,
                self.keys.inflight_timeouts,
                self.keys.url_key(scheduled_url.id),
                self.keys.retry_schedule,
                self.keys.failed,
                self.keys.domain_inflight,
            ],
            args=[
                scheduled_url.id,
                scheduled_url.domain,
                error_message,
                str(failed_at),
                str(self.max_retries),
                str(next_retry_at),
                self.keys.domain_queue_prefix,
                self.keys.ready_domains,
            ],
        )

        if result == 2:
            return "failed"
        if result == 1:
            return "requeued"
        return "missing"

    async def drop_inflight(self, url_id: str) -> None:
        """Clears inflight bookkeeping for a corrupted or missing URL record."""

        async with self.redis.pipeline(transaction=True) as pipeline:
            pipeline.hdel(self.keys.inflight, url_id)
            pipeline.zrem(self.keys.inflight_timeouts, url_id)
            await pipeline.execute()

    async def promote_due_retries(
        self,
        *,
        now: float | None = None,
        limit: int = 100,
    ) -> int:
        """Moves expired retry-scheduled URLs back into their domain queues."""

        current_time = time.time() if now is None else now
        promoted = await self._promote_retries_script(
            keys=[
                self.keys.retry_schedule,
                self.keys.ready_domains,
            ],
            args=[
                str(current_time),
                str(max(1, limit)),
                self.keys.url_prefix,
                self.keys.domain_queue_prefix,
            ],
        )
        return int(promoted or 0)

    async def next_ready_delay(self, now: float | None = None) -> float | None:
        """Returns the seconds until the next domain becomes eligible."""

        current_time = time.time() if now is None else now
        result = await self.redis.zrange(
            self.keys.ready_domains,
            0,
            0,
            withscores=True,
        )
        if not result:
            return None

        _domain, ready_at = result[0]
        return max(0.0, float(ready_at) - current_time)

    async def next_retry_delay(self, now: float | None = None) -> float | None:
        """Returns the seconds until the next delayed retry becomes eligible."""

        current_time = time.time() if now is None else now
        result = await self.redis.zrange(
            self.keys.retry_schedule,
            0,
            0,
            withscores=True,
        )
        if not result:
            return None

        _url_id, retry_at = result[0]
        return max(0.0, float(retry_at) - current_time)

    async def expired_inflight_ids(
        self,
        *,
        now: float | None = None,
        limit: int = 100,
    ) -> list[str]:
        """Returns URL IDs whose inflight lease deadline has expired."""

        current_time = time.time() if now is None else now
        return await self.redis.zrangebyscore(
            self.keys.inflight_timeouts,
            min="-inf",
            max=current_time,
            start=0,
            num=limit,
        )

    def _compute_retry_delay_seconds(self, retry_attempt: int) -> float:
        """Returns the backoff delay for the next retry attempt."""

        if self.retry_delay_seconds <= 0:
            return 0.0

        exponent = max(0, retry_attempt - 1)
        delay = self.retry_delay_seconds * (self.retry_backoff_multiplier ** exponent)
        return min(self.max_retry_delay_seconds, delay)
