"""Redis-backed dedup. SETNX with TTL — Upstash-friendly (no SET intersection)."""
from __future__ import annotations

import hashlib

from chainpulse.backend.db.redis import get_redis

DEDUP_TTL_SECONDS = 60 * 60 * 24 * 3  # 3 days
DEDUP_PREFIX = "seen:"


def _fingerprint(source: str, raw_id: str) -> str:
    return hashlib.sha256(f"{source}:{raw_id}".encode()).hexdigest()


async def is_new(source: str, raw_id: str) -> bool:
    r = get_redis()
    key = DEDUP_PREFIX + _fingerprint(source, raw_id)
    # nx=True → SET only if not exists. Returns True if new, None if exists.
    return bool(await r.set(key, "1", ex=DEDUP_TTL_SECONDS, nx=True))
