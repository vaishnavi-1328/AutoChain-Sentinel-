"""NLP pipeline orchestrator.

Reads raw.news stream → Groq extract → geo resolve → ProcessedEvent → publish processed stream.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from chainpulse.backend.schemas.event import ProcessedEvent
from chainpulse.backend.services import groq_extractor
from chainpulse.backend.services.geo import resolve as geo_resolve
from chainpulse.backend.services.stream import publish, settings_streams

log = logging.getLogger("chainpulse.nlp.pipeline")

DROP_CONFIDENCE = 0.30  # drop OTHER + low confidence


async def process_one(raw: dict[str, Any]) -> ProcessedEvent | None:
    """Process one raw.news dict → ProcessedEvent (or None to drop)."""
    headline = raw.get("headline") or ""
    if not headline:
        return None

    body = raw.get("body") or ""
    extracted = await groq_extractor.extract(headline, body)
    if extracted is None:
        return None

    if not extracted.get("is_supply_chain") or extracted["type"] == "OTHER":
        if extracted.get("confidence", 0) < DROP_CONFIDENCE:
            return None

    geo = await geo_resolve(
        location_str=extracted.get("location_name") or None,
        llm_lat=extracted.get("lat"),
        llm_lng=extracted.get("lng"),
        llm_country=extracted.get("country_code"),
    )

    ts = raw.get("published_at") or raw.get("ingested_at") or datetime.now(timezone.utc).isoformat()
    if isinstance(ts, str):
        try:
            ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            ts_dt = datetime.now(timezone.utc)
    else:
        ts_dt = ts

    event = ProcessedEvent(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        type=extracted["type"],
        severity=extracted["severity"],
        title=extracted["title"][:200],
        summary=extracted["summary"][:280],
        source_url=raw.get("url"),
        source_name=raw.get("source"),
        lat=geo["lat"] if geo else None,
        lng=geo["lng"] if geo else None,
        location_name=(geo["name"] if geo else extracted.get("location_name")) or None,
        country_code=(geo["country_code"] if geo else extracted.get("country_code")) or None,
        timestamp_utc=ts_dt,
    )
    return event


async def run_consumer(consumer_name: str = "nlp-1") -> None:
    """Long-running loop. Reads raw stream, processes, publishes processed stream."""
    from chainpulse.backend.services.stream import consume
    raw_stream, processed_stream, group = settings_streams()

    log.info("nlp consumer starting raw=%s processed=%s group=%s", raw_stream, processed_stream, group)
    async for entry_id, raw in consume(raw_stream, group, consumer_name):
        try:
            event = await process_one(raw)
        except Exception:
            log.exception("nlp process_one failed for %s", entry_id)
            continue
        if event is None:
            continue
        await publish(processed_stream, event.model_dump(mode="json"))
        log.info("processed: %s %s %s", event.type, event.severity, event.title[:60])
