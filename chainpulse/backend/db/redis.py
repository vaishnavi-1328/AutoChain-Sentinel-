"""Redis async client singleton — used for streams, pub/sub, bloom filter, TTL cache."""
from __future__ import annotations

from redis.asyncio import Redis, from_url

from chainpulse.backend.config.settings import get_settings

_client: Redis | None = None


def get_redis() -> Redis:
    global _client
    if _client is None:
        s = get_settings()
        _client = from_url(
            s.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _client


async def dispose() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None
