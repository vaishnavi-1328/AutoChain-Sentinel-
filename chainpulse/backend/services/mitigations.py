"""Mitigation recommender — rule-based.

Each candidate has: action, est_delay_reduction_days, cost_factor, eta_change_days, reason.
Uses order shipping_mode + matched events.
"""
from __future__ import annotations

from typing import Any

from chainpulse.backend.services.delay_engine import SHIPPING_MODE_FACTORS


def _air_switch(order, matched: list[dict]) -> dict | None:
    if order.shipping_mode == "Air freight":
        return None
    # Air mode factor is 0.15. New delay roughly = current * 0.15 / current_factor
    current_factor = SHIPPING_MODE_FACTORS.get(order.shipping_mode, 1.0)
    reduction = max(0, int(order.delay_min_days - round(order.delay_min_days * 0.15 / current_factor)))
    if reduction < 2:
        return None
    cost_uplift_pct = {
        "Sea freight": 380, "Multimodal": 300, "Rail": 220, "Road": 180,
    }.get(order.shipping_mode, 300)
    return {
        "action": "Switch to air freight",
        "est_delay_reduction_days": reduction,
        "cost_uplift_pct": cost_uplift_pct,
        "reason": f"Air freight bypasses port/maritime disruptions (factor 0.15 vs {current_factor})",
        "feasibility": "high" if (order.quantity or 0) < 5000 else "medium",
    }


def _reroute(order, matched: list[dict]) -> dict | None:
    if not matched:
        return None
    biggest = matched[0]
    # if there is a port-strike, suggest reroute via alternate hub
    dist = biggest.get("distance_km", 0)
    if dist >= 500:
        return None
    return {
        "action": f"Reroute via alternate hub (avoid {biggest.get('title','event')[:40]})",
        "est_delay_reduction_days": int(biggest.get("delay_contribution_days", 0) * 0.5),
        "cost_uplift_pct": 12,
        "reason": "Disruption is local; rerouting bypasses affected port/route",
        "feasibility": "medium",
    }


def _safety_stock(order, matched: list[dict]) -> dict | None:
    # always recommend if order has delay >0
    if order.delay_min_days < 3:
        return None
    qty = float(order.quantity) if order.quantity is not None else 100.0
    buffer_units = max(1, int(qty * 0.15))
    return {
        "action": f"Hold +{buffer_units} {order.quantity_unit or 'units'} safety stock",
        "est_delay_reduction_days": 0,
        "cost_uplift_pct": 4,
        "reason": "Forward-buy 15% buffer; absorbs delay without changing logistics",
        "feasibility": "high",
    }


def _split_shipment(order, matched: list[dict]) -> dict | None:
    qty = float(order.quantity) if order.quantity is not None else 0.0
    if qty < 500:
        return None
    return {
        "action": "Split shipment 70/30 across two modes",
        "est_delay_reduction_days": max(1, int(order.delay_min_days * 0.4)),
        "cost_uplift_pct": 22,
        "reason": "Send 30% air for critical SKUs; rest sea. Hedges full-batch delay.",
        "feasibility": "medium",
    }


def _change_supplier(order, matched: list[dict]) -> dict | None:
    # only if all matched events are concentrated in supplier's country
    if not matched:
        return None
    cc = (order.supplier_country or "").upper()
    if not cc:
        return None
    cc_count = sum(1 for m in matched if (m.get("source_name") or "").lower().startswith(cc.lower()))
    if cc_count == 0:
        return None
    return {
        "action": "Add backup supplier in different region",
        "est_delay_reduction_days": int(order.delay_min_days * 0.8),
        "cost_uplift_pct": 18,
        "reason": "Disruptions concentrated in supplier's country; dual-source reduces single-point risk",
        "feasibility": "low",
    }


_RULES = [_air_switch, _reroute, _safety_stock, _split_shipment, _change_supplier]


def suggest(order, matched: list[dict]) -> list[dict[str, Any]]:
    out = []
    for rule in _RULES:
        r = rule(order, matched)
        if r:
            out.append(r)
    return out
