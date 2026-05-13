"""User supply chain profile ORM."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import ARRAY, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from chainpulse.backend.models.base import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    watched_regions: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    product_categories: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    sku_codes: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    supplier_names: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
