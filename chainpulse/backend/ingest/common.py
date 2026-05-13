"""Shared publish helper — dedup + RawNews validation + stream xadd."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from chainpulse.backend.schemas.event import RawNews
from chainpulse.backend.services.dedup import is_new
from chainpulse.backend.services.stream import publish, settings_streams

log = logging.getLogger("chainpulse.ingest")


async def publish_raw(article: dict[str, Any]) -> bool:
    """Validate as RawNews, dedup by (source, raw_id), publish to raw stream."""
    try:
        raw = RawNews(**article)
    except Exception:
        log.warning("invalid raw article shape: %s", article.get("raw_id"))
        return False

    if not await is_new(raw.source, raw.raw_id):
        return False

    raw_stream, _proc_stream, _group = settings_streams()
    payload = raw.model_dump(mode="json")
    payload.setdefault("ingested_at", datetime.now(timezone.utc).isoformat())
    await publish(raw_stream, payload)
    log.info("raw published: %s %s", raw.source, raw.raw_id)
    return True
