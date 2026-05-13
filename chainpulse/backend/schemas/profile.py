"""Onboarding profile schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OnboardingProfileRequest(BaseModel):
    watched_regions: list[str] = []
    product_categories: list[str] = []
    sku_codes: list[str] = []
    supplier_names: list[str] = []


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    watched_regions: list[str]
    product_categories: list[str]
    sku_codes: list[str]
    supplier_names: list[str]
    updated_at: datetime
