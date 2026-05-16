"""Order + OrderEventImpact ORM."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import CHAR, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from chainpulse.backend.models.base import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    supplier_name: Mapped[str] = mapped_column(String, nullable=False)
    supplier_city: Mapped[str] = mapped_column(String, nullable=False)
    supplier_country: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    supplier_lat: Mapped[float] = mapped_column(Float, nullable=False)
    supplier_lng: Mapped[float] = mapped_column(Float, nullable=False)
    materials: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    quantity_unit: Mapped[str | None] = mapped_column(String, nullable=True)
    expected_delivery: Mapped[date] = mapped_column(Date, nullable=False)
    po_reference: Mapped[str | None] = mapped_column(String, nullable=True)
    shipping_mode: Mapped[str] = mapped_column(String, nullable=False, default="Sea freight")
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="ON_SCHEDULE")
    delay_min_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delay_max_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_eta_earliest: Mapped[date | None] = mapped_column(Date, nullable=True)
    new_eta_latest: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OrderEventImpact(Base):
    __tablename__ = "order_event_impacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    distance_km: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    delay_contribution_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
