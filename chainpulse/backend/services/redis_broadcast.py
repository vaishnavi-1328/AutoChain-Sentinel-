"""Redis TTL cache + per-user pub/sub publish."""
from __future__ import annotations

import json
import logging
from typing import Any

from chainpulse.backend.db.redis import get_redis

log = logging.getLogger("chainpulse.redis.broadcast")

EVENT_TTL_SECONDS = 300  # 5-min live TTL per spec
USER_CHANNEL_PREFIX = "events:"


def wrap_event_msg(event: dict[str, Any]) -> dict[str, Any]:
    """Frontend WS router uses msg_type discriminator. Existing handlers expect msg_type='event'."""
    if event.get("msg_type"):
        return event
    return {"msg_type": "event", **event}


async def cache_event(event: dict[str, Any]) -> None:
    r = get_redis()
    key = f"event:{event['id']}"
    await r.set(key, json.dumps(event, default=str), ex=EVENT_TTL_SECONDS)


async def publish_to_users(event: dict[str, Any], user_ids: list[str]) -> int:
    r = get_redis()
    payload = json.dumps(event, default=str)
    sent = 0
    for uid in user_ids:
        await r.publish(USER_CHANNEL_PREFIX + uid, payload)
        sent += 1
    return sent


async def publish_to_global(event: dict[str, Any]) -> None:
    """Anon clients (no JWT) get all events on a global channel."""
    r = get_redis()
    await r.publish(USER_CHANNEL_PREFIX + "*", json.dumps(event, default=str))
