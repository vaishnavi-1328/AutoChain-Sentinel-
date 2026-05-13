"""Redis Streams producer + consumer helpers (Kafka replacement)."""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from chainpulse.backend.config.settings import get_settings
from chainpulse.backend.db.redis import get_redis

log = logging.getLogger("chainpulse.stream")


async def publish(stream: str, payload: dict[str, Any]) -> str:
    r = get_redis()
    return await r.xadd(stream, {"data": json.dumps(payload, default=str)}, maxlen=10000, approximate=True)


async def ensure_group(stream: str, group: str) -> None:
    r = get_redis()
    try:
        await r.xgroup_create(stream, group, id="0", mkstream=True)
    except Exception as e:
        # BUSYGROUP — already exists, fine.
        if "BUSYGROUP" not in str(e):
            raise


async def consume(
    stream: str,
    group: str,
    consumer: str,
    block_ms: int = 5000,
    count: int = 16,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    await ensure_group(stream, group)
    r = get_redis()
    while True:
        try:
            resp = await r.xreadgroup(group, consumer, {stream: ">"}, count=count, block=block_ms)
        except Exception:
            log.exception("xreadgroup failed; backing off")
            continue
        if not resp:
            continue
        for _stream_name, entries in resp:
            for entry_id, fields in entries:
                raw = fields.get("data")
                if not raw:
                    await r.xack(stream, group, entry_id)
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    log.exception("bad json in stream %s id=%s", stream, entry_id)
                    await r.xack(stream, group, entry_id)
                    continue
                yield entry_id, payload
                await r.xack(stream, group, entry_id)


def settings_streams() -> tuple[str, str, str]:
    s = get_settings()
    return s.stream_raw, s.stream_processed, s.stream_group
