import os

import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
TTL_SECONDS = 86400  # 24 hours

_client: aioredis.Redis | None = None


async def _get_client() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _client


async def is_duplicate(event_id: str) -> bool:
    try:
        client = await _get_client()
        return await client.exists(f"event:{event_id}") == 1
    except Exception:
        return False  # Redis unavailable — allow event through


async def mark_processed(event_id: str) -> None:
    try:
        client = await _get_client()
        await client.setex(f"event:{event_id}", TTL_SECONDS, "1")
    except Exception:
        pass  # Best-effort — dedup skipped when Redis is down
