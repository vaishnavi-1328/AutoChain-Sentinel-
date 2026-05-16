"""POST/GET /orders, /orders/{id}/analysis, DELETE /orders/{id}."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from chainpulse.backend.db.postgres import get_session
from chainpulse.backend.db.redis import get_redis
from chainpulse.backend.models import Event, Order, OrderEventImpact, User
from chainpulse.backend.schemas.order import OrderAnalysis, OrderCreate, OrderRead
from chainpulse.backend.services.auth_deps import current_user
from chainpulse.backend.services.delay_engine import (
    analyse_order,
    build_order_delay_msg,
    fetch_active_events,
    _persist_analysis,
)
from chainpulse.backend.services.mitigations import suggest as suggest_mitigations
from chainpulse.backend.services.redis_broadcast import publish_to_users

router = APIRouter(prefix="/orders", tags=["orders"])


STATUS_ORDER = case(
    {
        "CRITICAL_DELAY": 1,
        "DELAY_RISK":     2,
        "MONITOR":        3,
        "ON_SCHEDULE":    4,
        "DELIVERED":      5,
    },
    value=Order.status,
    else_=6,
)


@router.post("", response_model=OrderAnalysis, status_code=status.HTTP_201_CREATED)
async def create_order(
    body: OrderCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderAnalysis:
    redis = get_redis()
    order = Order(
        user_id=user.id,
        supplier_name=body.supplier_name,
        supplier_city=body.supplier_city,
        supplier_country=body.supplier_country.upper(),
        supplier_lat=body.supplier_lat,
        supplier_lng=body.supplier_lng,
        materials=body.materials,
        quantity=body.quantity,
        quantity_unit=body.quantity_unit,
        expected_delivery=body.expected_delivery,
        po_reference=body.po_reference,
        shipping_mode=body.shipping_mode,
        notes=body.notes,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)

    active = await fetch_active_events(redis)
    analysis = analyse_order(order, active)
    await _persist_analysis(session, order, analysis)
    await session.commit()
    await session.refresh(order)

    # broadcast initial delay state to this user only
    msg = build_order_delay_msg(order, analysis)
    try:
        await publish_to_users(msg, [str(user.id)])
    except Exception:
        pass

    return OrderAnalysis(
        order=OrderRead.model_validate(order),
        matched_events=analysis["matched"],
        overlap_adjustment_days=analysis["overlap_adjustment_days"],
        chart_data=[
            {
                "label": m.get("title", "")[:40],
                "value": m["delay_contribution_days"],
                "source": m.get("source_name"),
            }
            for m in analysis["matched"]
        ],
    )


@router.get("", response_model=list[OrderRead])
async def list_orders(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Order]:
    result = await session.execute(
        select(Order).where(Order.user_id == user.id).order_by(STATUS_ORDER, Order.expected_delivery)
    )
    return list(result.scalars().all())


@router.get("/{order_id}/analysis", response_model=OrderAnalysis)
async def order_analysis(
    order_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderAnalysis:
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None or order.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "order not found")

    join_q = await session.execute(
        select(OrderEventImpact, Event)
        .join(Event, Event.id == OrderEventImpact.event_id)
        .where(OrderEventImpact.order_id == order.id)
        .order_by(OrderEventImpact.delay_contribution_days.desc())
    )
    matched = []
    chart = []
    overlap_adj = 0
    for impact, event in join_q.all():
        matched.append({
            "event_id":                str(event.id),
            "title":                   event.title,
            "source_url":              event.source_url,
            "source_name":             event.source_name,
            "severity":                event.severity,
            "distance_km":             float(impact.distance_km) if impact.distance_km is not None else 0.0,
            "delay_contribution_days": int(impact.delay_contribution_days or 0),
            "delay_contribution_max":  None,
            "timestamp_utc":           event.timestamp_utc,
        })
        chart.append({
            "label": event.title[:40],
            "value": int(impact.delay_contribution_days or 0),
            "source": event.source_name,
        })

    # overlap_adjustment = -0.5 of each non-top contribution
    if len(matched) > 1:
        for m in matched[1:]:
            overlap_adj -= round(m["delay_contribution_days"] * 0.5)

    return OrderAnalysis(
        order=OrderRead.model_validate(order),
        matched_events=matched,
        overlap_adjustment_days=overlap_adj,
        chart_data=chart,
    )


@router.get("/{order_id}/mitigations")
async def order_mitigations(
    order_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None or order.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "order not found")

    join_q = await session.execute(
        select(OrderEventImpact, Event)
        .join(Event, Event.id == OrderEventImpact.event_id)
        .where(OrderEventImpact.order_id == order.id)
        .order_by(OrderEventImpact.delay_contribution_days.desc())
    )
    matched = []
    for impact, event in join_q.all():
        matched.append({
            "event_id":                str(event.id),
            "title":                   event.title,
            "source_url":              event.source_url,
            "source_name":             event.source_name,
            "severity":                event.severity,
            "distance_km":             float(impact.distance_km) if impact.distance_km is not None else 0.0,
            "delay_contribution_days": int(impact.delay_contribution_days or 0),
        })

    return {
        "order_id": str(order.id),
        "current_status": order.status,
        "current_delay_min": order.delay_min_days,
        "current_delay_max": order.delay_max_days,
        "suggestions": suggest_mitigations(order, matched),
    }


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(
    order_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None or order.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "order not found")
    await session.delete(order)
    await session.commit()
