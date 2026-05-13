"""Storage pipeline.

Reads processed.events stream → Postgres event row + Neo4j node + Redis TTL +
user impact match + per-user Redis publish.
"""
from __future__ import annotations

import logging
from typing import Any

from chainpulse.backend.services.delay_predictor import Features, predict
from chainpulse.backend.services.neo4j_writer import write_event
from chainpulse.backend.services.postgres_writer import insert_event, match_user_impacts
from chainpulse.backend.services.redis_broadcast import (
    cache_event,
    publish_to_global,
    publish_to_users,
)
from chainpulse.backend.services.stream import consume, settings_streams

log = logging.getLogger("chainpulse.storage")


async def process_one(event: dict[str, Any]) -> dict[str, Any]:
    """Enrich + persist event. Returns enriched dict (with delay fields)."""
    feats = Features(
        event_type=event.get("type", "OTHER"),
        severity=event.get("severity", "low"),
        location_name=event.get("location_name"),
        country_code=event.get("country_code"),
    )
    d_min, d_max, conf = predict(feats)
    event["predicted_delay_min_days"] = d_min
    event["predicted_delay_max_days"] = d_max
    event["delay_confidence"] = conf

    node_id = write_event(event)
    event["neo4j_event_node_id"] = node_id

    pg_id = await insert_event(event, node_id)

    impacts = await match_user_impacts(pg_id, event.get("country_code"))
    event["affected_sku_count"] = sum(impacts.values()) if impacts else 0

    await cache_event(event)
    if impacts:
        await publish_to_users(event, list(impacts.keys()))
    await publish_to_global(event)
    return event


async def run_consumer(consumer_name: str = "storage-1") -> None:
    _raw, processed_stream, group = settings_streams()
    log.info("storage consumer starting stream=%s group=%s", processed_stream, group)
    async for entry_id, event in consume(processed_stream, group, consumer_name):
        try:
            enriched = await process_one(event)
            log.info(
                "stored: %s %s delay=%d-%dd users=%d",
                enriched["id"],
                enriched["type"],
                enriched.get("predicted_delay_min_days", 0),
                enriched.get("predicted_delay_max_days", 0),
                enriched.get("affected_sku_count", 0),
            )
        except Exception:
            log.exception("storage process_one failed for %s", entry_id)
