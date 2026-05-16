"""/events/recent, /events/{id}."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chainpulse.backend.db.postgres import get_session
from chainpulse.backend.models import Event
from chainpulse.backend.services.delay_predictor import Features
from chainpulse.backend.services.shap_explainer import explain as shap_explain

router = APIRouter(prefix="/events", tags=["events"])


def _to_dict(e: Event) -> dict:
    return {
        "id": str(e.id),
        "type": e.type,
        "severity": e.severity,
        "title": e.title,
        "summary": e.summary,
        "source_url": e.source_url,
        "source_name": e.source_name,
        "lat": e.lat,
        "lng": e.lng,
        "location_name": e.location_name,
        "country_code": e.country_code,
        "predicted_delay_min_days": e.delay_min_days,
        "predicted_delay_max_days": e.delay_max_days,
        "delay_confidence": float(e.delay_confidence) if e.delay_confidence is not None else None,
        "neo4j_event_node_id": e.neo4j_node_id,
        "affected_route_count": e.affected_route_count,
        "timestamp_utc": e.timestamp_utc.isoformat() if e.timestamp_utc else None,
    }


@router.get("/recent")
async def recent(
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await session.execute(
        select(Event).order_by(Event.timestamp_utc.desc()).limit(limit)
    )
    events = [_to_dict(e) for e in result.scalars().all()]
    return {"events": events, "count": len(events)}


@router.get("/{event_id}")
async def get_event(
    event_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        pg_id = uuid.UUID(event_id)
    except ValueError:
        # support evt_<hex> form by deriving uuid5
        pg_id = uuid.uuid5(uuid.NAMESPACE_URL, event_id)

    result = await session.execute(select(Event).where(Event.id == pg_id))
    e = result.scalar_one_or_none()
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "event not found")
    return _to_dict(e)


@router.get("/{event_id}/shap")
async def event_shap(
    event_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        pg_id = uuid.UUID(event_id)
    except ValueError:
        pg_id = uuid.uuid5(uuid.NAMESPACE_URL, event_id)
    result = await session.execute(select(Event).where(Event.id == pg_id))
    e = result.scalar_one_or_none()
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "event not found")

    feats = Features(
        event_type=e.type,
        severity=e.severity,
        location_name=e.location_name,
        country_code=e.country_code,
    )
    result = shap_explain(feats)
    if result is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "XGBoost models not loaded — run train_delay_model.py")
    result["event_id"] = str(e.id)
    result["event_title"] = e.title
    result["actual_min"] = e.delay_min_days
    result["actual_max"] = e.delay_max_days
    return result
