"""Event + per-user impact ORM."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CHAR,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from chainpulse.backend.models.base import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    source_name: Mapped[str | None] = mapped_column(String, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_name: Mapped[str | None] = mapped_column(String, nullable=True)
    country_code: Mapped[str | None] = mapped_column(CHAR(2), nullable=True)
    delay_min_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delay_max_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delay_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    neo4j_node_id: Mapped[str | None] = mapped_column(String, nullable=True)
    affected_route_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )


class UserEventImpact(Base):
    __tablename__ = "user_event_impacts"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    affected_sku_count: Mapped[int] = mapped_column(Integer, default=0)
