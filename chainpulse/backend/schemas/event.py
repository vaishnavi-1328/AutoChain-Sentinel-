"""Event Pydantic schemas. Mirrors WS schema from ARCHITECTURE_PROMPT lines 260-282."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["critical", "high", "medium", "low"]
EventType = Literal[
    "PORT_STRIKE",
    "WEATHER_EVENT",
    "FACTORY_CLOSURE",
    "SANCTIONS",
    "GEOPOLITICAL",
    "LOGISTICS_DELAY",
    "OTHER",
]


class RawNews(BaseModel):
    source: str
    raw_id: str
    headline: str
    body: str = ""
    url: str | None = None
    published_at: datetime | None = None
    ingested_at: datetime | None = None


class ProcessedEvent(BaseModel):
    id: str
    type: EventType
    severity: Severity
    title: str
    summary: str = Field(default="", max_length=280)
    source_url: str | None = None
    source_name: str | None = None
    lat: float | None = None
    lng: float | None = None
    location_name: str | None = None
    country_code: str | None = None
    predicted_delay_min_days: int | None = None
    predicted_delay_max_days: int | None = None
    delay_confidence: float | None = None
    neo4j_event_node_id: str | None = None
    affected_sku_count: int = 0
    affected_route_count: int = 0
    timestamp_utc: datetime
    ttl_seconds: int = 300


class EventResponse(ProcessedEvent):
    pass
