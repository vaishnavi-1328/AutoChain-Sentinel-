"""Order + supplier schemas."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["CRITICAL_DELAY", "DELAY_RISK", "MONITOR", "ON_SCHEDULE", "DELIVERED"]
ShippingMode = Literal["Sea freight", "Air freight", "Rail", "Road", "Multimodal"]


class OrderCreate(BaseModel):
    supplier_name: str
    supplier_city: str
    supplier_country: str = Field(min_length=2, max_length=2)
    supplier_lat: float
    supplier_lng: float
    materials: str
    quantity: float | None = None
    quantity_unit: str | None = None
    expected_delivery: date
    po_reference: str | None = None
    shipping_mode: ShippingMode = "Sea freight"
    notes: str | None = None


class MatchedEvent(BaseModel):
    event_id: str
    title: str
    source_url: str | None = None
    source_name: str | None = None
    severity: str
    distance_km: float
    delay_contribution_days: int
    delay_contribution_max: int | None = None
    timestamp_utc: datetime | None = None


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    supplier_name: str
    supplier_city: str
    supplier_country: str
    supplier_lat: float
    supplier_lng: float
    materials: str
    quantity: float | None = None
    quantity_unit: str | None = None
    expected_delivery: date
    po_reference: str | None = None
    shipping_mode: str
    notes: str | None = None
    status: Status
    delay_min_days: int
    delay_max_days: int
    new_eta_earliest: date | None = None
    new_eta_latest: date | None = None
    created_at: datetime
    updated_at: datetime


class OrderAnalysis(BaseModel):
    order: OrderRead
    matched_events: list[MatchedEvent] = []
    overlap_adjustment_days: int = 0
    chart_data: list[dict] = []


class GeoResolveResponse(BaseModel):
    lat: float
    lng: float
    resolved_name: str
    country_code: str | None = None
    source: str | None = None


class OrderDelayUpdateMsg(BaseModel):
    msg_type: Literal["order_delay_update"] = "order_delay_update"
    order_id: str
    supplier_name: str
    supplier_lat: float
    supplier_lng: float
    status: Status
    delay_min_days: int
    delay_max_days: int
    original_eta: str
    new_eta_earliest: str | None = None
    new_eta_latest: str | None = None
    matched_events: list[MatchedEvent] = []
    overlap_adjustment_days: int = 0
