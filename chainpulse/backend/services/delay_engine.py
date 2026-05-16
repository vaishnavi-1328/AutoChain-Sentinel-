"""Personalized supplier delay engine.

- Pure: analyse_order(order, active_events) → status + delay + matched.
- Async: fetch_active_events(redis), recompute_for_user_orders(session, redis).
- WS payload builder: build_order_delay_msg(order, analysis).
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from geopy.distance import geodesic
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from chainpulse.backend.models import Event, Order, OrderEventImpact
from chainpulse.backend.services.postgres_writer import _coerce_uuid
from chainpulse.backend.services.shipping_lanes import lanes_near, supplier_uses_lane

log = logging.getLogger("chainpulse.delay_engine")

PROXIMITY_KM = 800
ROUTE_BUFFER_KM = 120

SHIPPING_MODE_FACTORS: dict[str, float] = {
    "Sea freight":  1.00,
    "Multimodal":   0.85,
    "Rail":         0.60,
    "Road":         0.50,
    "Air freight":  0.15,
}


def distance_factor(km: float) -> float:
    if km < 200: return 1.00
    if km < 500: return 0.85
    if km < 800: return 0.60
    return 0.40


def derive_status(delay_min: int, severity: str) -> str:
    if delay_min >= 14 or severity == "critical": return "CRITICAL_DELAY"
    if delay_min >= 3:  return "DELAY_RISK"
    if delay_min >= 1:  return "MONITOR"
    return "ON_SCHEDULE"


@dataclass
class _OrderLite:
    """Minimal supplier-side fields used by analyse_order (works for ORM Order or dict)."""
    supplier_lat: float
    supplier_lng: float
    expected_delivery: date
    shipping_mode: str = "Sea freight"
    supplier_country: str = ""


def _to_lite(order: Any) -> _OrderLite:
    if isinstance(order, _OrderLite):
        return order
    if hasattr(order, "supplier_lat"):
        return _OrderLite(
            supplier_lat=float(order.supplier_lat),
            supplier_lng=float(order.supplier_lng),
            expected_delivery=order.expected_delivery,
            shipping_mode=order.shipping_mode or "Sea freight",
            supplier_country=(order.supplier_country or "").upper(),
        )
    return _OrderLite(
        supplier_lat=float(order["supplier_lat"]),
        supplier_lng=float(order["supplier_lng"]),
        expected_delivery=order["expected_delivery"],
        shipping_mode=order.get("shipping_mode", "Sea freight"),
        supplier_country=(order.get("supplier_country") or "").upper(),
    )


def analyse_order(order: Any, active_events: list[dict]) -> dict:
    """Run delay analysis. Returns {status, delay_min, delay_max, new_eta_*, overlap_adjustment_days, matched}."""
    lite = _to_lite(order)
    matched: list[dict] = []

    for event in active_events:
        lat = event.get("lat")
        lng = event.get("lng")
        d_min = event.get("predicted_delay_min_days")
        d_max = event.get("predicted_delay_max_days")
        if lat is None or lng is None or d_min is None or d_max is None:
            continue

        try:
            dist = geodesic((float(lat), float(lng)), (lite.supplier_lat, lite.supplier_lng)).km
        except Exception:
            continue

        on_lane = None
        if dist > PROXIMITY_KM:
            if lite.shipping_mode not in ("Sea freight", "Multimodal"):
                continue
            hits = lanes_near(float(lat), float(lng))
            for h in hits:
                if lite.supplier_country and supplier_uses_lane(lite.supplier_country, h["id"]):
                    on_lane = h
                    break
            if on_lane is None:
                continue
            effective_dist = 400.0  # lane-close tier
        else:
            effective_dist = dist

        df = distance_factor(effective_dist)
        mf = SHIPPING_MODE_FACTORS.get(lite.shipping_mode, 1.0)
        contrib_min = round(float(d_min) * df * mf)
        contrib_max = round(float(d_max) * df * mf)
        if contrib_min <= 0:
            continue

        matched.append({
            "event_id":                event.get("id"),
            "title":                   event.get("title", ""),
            "source_url":              event.get("source_url"),
            "source_name":             event.get("source_name"),
            "severity":                event.get("severity", "low"),
            "distance_km":             round(dist, 1),
            "delay_contribution_days": contrib_min,
            "delay_contribution_max":  contrib_max,
            "on_shipping_lane":        on_lane,
            "timestamp_utc":           event.get("timestamp_utc"),
        })

    if not matched:
        return {
            "status": "ON_SCHEDULE",
            "delay_min": 0,
            "delay_max": 0,
            "new_eta_earliest": None,
            "new_eta_latest": None,
            "overlap_adjustment_days": 0,
            "matched": [],
        }

    matched.sort(key=lambda m: m["delay_contribution_days"], reverse=True)
    total_min = matched[0]["delay_contribution_days"]
    total_max = matched[0]["delay_contribution_max"]
    overlap_adj = 0
    for m in matched[1:]:
        add_min = round(m["delay_contribution_days"] * 0.5)
        add_max = round(m["delay_contribution_max"] * 0.5)
        overlap_adj -= round(m["delay_contribution_days"] * 0.5)
        total_min += add_min
        total_max += add_max

    new_eta_min = lite.expected_delivery + timedelta(days=total_min)
    new_eta_max = lite.expected_delivery + timedelta(days=total_max)
    return {
        "status":                  derive_status(total_min, matched[0]["severity"]),
        "delay_min":               total_min,
        "delay_max":               total_max,
        "new_eta_earliest":        new_eta_min.isoformat(),
        "new_eta_latest":          new_eta_max.isoformat(),
        "overlap_adjustment_days": overlap_adj,
        "matched":                 matched,
    }


async def fetch_active_events(redis) -> list[dict]:
    """Read all event:* TTL'd keys from Redis and decode JSON."""
    out: list[dict] = []
    async for key in redis.scan_iter(match="event:*", count=200):
        raw = await redis.get(key)
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return out


async def _persist_analysis(session: AsyncSession, order: Order, analysis: dict) -> None:
    """Update order row + replace order_event_impacts for that order."""
    order.status = analysis["status"]
    order.delay_min_days = int(analysis["delay_min"])
    order.delay_max_days = int(analysis["delay_max"])
    order.new_eta_earliest = (
        date.fromisoformat(analysis["new_eta_earliest"]) if analysis["new_eta_earliest"] else None
    )
    order.new_eta_latest = (
        date.fromisoformat(analysis["new_eta_latest"]) if analysis["new_eta_latest"] else None
    )

    await session.execute(delete(OrderEventImpact).where(OrderEventImpact.order_id == order.id))
    # Look up which event_ids actually exist in Postgres (Redis cache may have
    # entries that predate or skip the DB insert — e.g. test-seeded events).
    candidate_ids = [_coerce_uuid(m["event_id"]) for m in analysis["matched"] if m.get("event_id")]
    existing: set = set()
    if candidate_ids:
        q = await session.execute(select(Event.id).where(Event.id.in_(candidate_ids)))
        existing = {row[0] for row in q.all()}
    for m in analysis["matched"]:
        evt_id = m.get("event_id")
        if not evt_id:
            continue
        pg_event_id = _coerce_uuid(evt_id)
        if pg_event_id not in existing:
            continue
        session.add(OrderEventImpact(
            order_id=order.id,
            event_id=pg_event_id,
            distance_km=m["distance_km"],
            delay_contribution_days=m["delay_contribution_days"],
        ))


async def recompute_for_user_orders(
    session: AsyncSession,
    redis,
    user_id: uuid.UUID | None = None,
) -> list[tuple[Order, dict]]:
    """Re-analyse all (or one user's) orders. Persist. Return changed (order, analysis) tuples."""
    active = await fetch_active_events(redis)

    q = select(Order)
    if user_id is not None:
        q = q.where(Order.user_id == user_id)
    result = await session.execute(q)
    orders = result.scalars().all()

    changed: list[tuple[Order, dict]] = []
    for order in orders:
        if order.status == "DELIVERED":
            continue
        prev_status = order.status
        prev_min = order.delay_min_days
        analysis = analyse_order(order, active)
        if (analysis["status"] != prev_status) or (int(analysis["delay_min"]) != prev_min):
            await _persist_analysis(session, order, analysis)
            changed.append((order, analysis))
    if changed:
        await session.commit()
    return changed


def build_order_delay_msg(order: Order, analysis: dict) -> dict:
    """WS payload — bare dict matching OrderDelayUpdateMsg shape."""
    return {
        "msg_type": "order_delay_update",
        "order_id": str(order.id),
        "supplier_name": order.supplier_name,
        "supplier_lat": float(order.supplier_lat),
        "supplier_lng": float(order.supplier_lng),
        "status": analysis["status"],
        "delay_min_days": int(analysis["delay_min"]),
        "delay_max_days": int(analysis["delay_max"]),
        "original_eta": order.expected_delivery.isoformat(),
        "new_eta_earliest": analysis.get("new_eta_earliest"),
        "new_eta_latest": analysis.get("new_eta_latest"),
        "matched_events": analysis.get("matched", []),
        "overlap_adjustment_days": int(analysis.get("overlap_adjustment_days", 0)),
    }
