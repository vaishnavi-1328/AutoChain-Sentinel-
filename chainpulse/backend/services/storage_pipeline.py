"""Storage pipeline.

Reads processed.events stream → Postgres event row + Neo4j node + Redis TTL +
user impact match + per-user Redis publish + supplier delay recompute.
"""
from __future__ import annotations

import logging
from typing import Any

from chainpulse.backend.db.postgres import get_session_factory
from chainpulse.backend.db.redis import get_redis
from chainpulse.backend.services.delay_engine import build_order_delay_msg, recompute_for_user_orders
from chainpulse.backend.services.delay_predictor import Features, predict
from chainpulse.backend.services.neo4j_writer import write_event
from chainpulse.backend.services.postgres_writer import insert_event, match_user_impacts
from chainpulse.backend.services.redis_broadcast import (
    cache_event,
    publish_to_global,
    publish_to_users,
    wrap_event_msg,
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

    wrapped = wrap_event_msg(event)
    if impacts:
        await publish_to_users(wrapped, list(impacts.keys()))
    await publish_to_global(wrapped)

    # V2: recompute supplier delays vs all active events, broadcast per-user.
    try:
        redis = get_redis()
        factory = get_session_factory()
        user_emails: dict = {}
        async with factory() as session:
            changed = await recompute_for_user_orders(session, redis)
            if changed:
                from sqlalchemy import select as _select
                from chainpulse.backend.models import User as _User
                ids = list({order.user_id for order, _ in changed})
                rs = await session.execute(_select(_User).where(_User.id.in_(ids)))
                for u in rs.scalars().all():
                    user_emails[u.id] = u.email
        for order, analysis in changed:
            msg = build_order_delay_msg(order, analysis)
            try:
                await publish_to_users(msg, [str(order.user_id)])
            except Exception:
                log.exception("publish order_delay_update failed for %s", order.id)
            email = user_emails.get(order.user_id)
            if email:
                try:
                    from chainpulse.backend.services.email_alerts import maybe_alert
                    await maybe_alert(email, order, analysis)
                except Exception:
                    log.exception("email alert failed for order %s", order.id)
    except Exception:
        log.exception("supplier delay recompute failed")

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
