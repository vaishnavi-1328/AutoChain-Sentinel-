"""Postgres event row insert + user impact match writer."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from chainpulse.backend.db.postgres import get_session_factory
from chainpulse.backend.models import Event, UserEventImpact, UserProfile

log = logging.getLogger("chainpulse.pg.writer")


def _coerce_uuid(evt_id: str) -> uuid.UUID:
    # processed event IDs look like "evt_<12hex>" — derive deterministic UUID.
    if evt_id.startswith("evt_"):
        return uuid.uuid5(uuid.NAMESPACE_URL, evt_id)
    try:
        return uuid.UUID(evt_id)
    except Exception:
        return uuid.uuid5(uuid.NAMESPACE_URL, evt_id)


def _coerce_dt(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            pass
    return datetime.now(timezone.utc)


async def insert_event(event: dict[str, Any], neo4j_node_id: str | None) -> uuid.UUID:
    factory = get_session_factory()
    pg_id = _coerce_uuid(event["id"])
    async with factory() as s:  # type: AsyncSession
        stmt = pg_insert(Event).values(
            id=pg_id,
            type=event["type"],
            severity=event["severity"],
            title=event["title"],
            summary=event.get("summary"),
            source_url=event.get("source_url"),
            source_name=event.get("source_name"),
            lat=event.get("lat"),
            lng=event.get("lng"),
            location_name=event.get("location_name"),
            country_code=event.get("country_code"),
            delay_min_days=event.get("predicted_delay_min_days"),
            delay_max_days=event.get("predicted_delay_max_days"),
            delay_confidence=event.get("delay_confidence"),
            neo4j_node_id=neo4j_node_id,
            affected_route_count=event.get("affected_route_count", 0),
            timestamp_utc=_coerce_dt(event["timestamp_utc"]),
        ).on_conflict_do_nothing(index_elements=["id"])
        await s.execute(stmt)
        await s.commit()
    return pg_id


async def match_user_impacts(event_pg_id: uuid.UUID, country_code: str | None) -> dict[str, int]:
    """Find users with watched_regions overlapping country_code → insert impact rows.

    Returns {user_id_str: affected_sku_count}.
    """
    if not country_code:
        return {}

    factory = get_session_factory()
    hits: dict[str, int] = {}
    async with factory() as s:
        result = await s.execute(
            select(UserProfile).where(UserProfile.watched_regions.any(country_code))
        )
        profiles = result.scalars().all()
        for prof in profiles:
            sku_count = len(prof.sku_codes or [])
            stmt = pg_insert(UserEventImpact).values(
                event_id=event_pg_id,
                user_id=prof.user_id,
                affected_sku_count=sku_count,
            ).on_conflict_do_nothing(index_elements=["event_id", "user_id"])
            await s.execute(stmt)
            hits[str(prof.user_id)] = sku_count
        await s.commit()
    return hits
