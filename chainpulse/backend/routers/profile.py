"""/onboarding/profile, /profile/me, /profile/skus-at-risk."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from chainpulse.backend.db.postgres import get_session
from chainpulse.backend.db.redis import get_redis
from chainpulse.backend.models import Event, User, UserEventImpact, UserProfile
from chainpulse.backend.schemas.profile import OnboardingProfileRequest, ProfileResponse
from chainpulse.backend.services.auth_deps import current_user

router = APIRouter(tags=["profile"])


@router.post("/onboarding/profile", response_model=ProfileResponse)
async def save_profile(
    body: OnboardingProfileRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> UserProfile:
    result = await session.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()

    if profile is None:
        profile = UserProfile(
            user_id=user.id,
            watched_regions=body.watched_regions,
            product_categories=body.product_categories,
            sku_codes=body.sku_codes,
            supplier_names=body.supplier_names,
        )
        session.add(profile)
    else:
        profile.watched_regions = body.watched_regions
        profile.product_categories = body.product_categories
        profile.sku_codes = body.sku_codes
        profile.supplier_names = body.supplier_names

    await session.commit()
    await session.refresh(profile)
    return profile


@router.get("/profile/me", response_model=ProfileResponse)
async def get_my_profile(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> UserProfile:
    result = await session.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "profile not set; complete onboarding")
    return profile


@router.get("/profile/skus-at-risk")
async def skus_at_risk(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Returns user's SKUs that are affected by currently-live events (TTL'd in Redis)."""
    prof_q = await session.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = prof_q.scalar_one_or_none()
    if profile is None:
        return {"skus": [], "live_events": []}

    impact_q = await session.execute(
        select(Event, UserEventImpact.affected_sku_count)
        .join(UserEventImpact, UserEventImpact.event_id == Event.id)
        .where(UserEventImpact.user_id == user.id)
        .order_by(desc(Event.timestamp_utc))
        .limit(200)
    )
    rows = impact_q.all()

    r = get_redis()
    live: list[dict] = []
    for event, sku_count in rows:
        cached = await r.get(f"event:{event.id}")
        if not cached:
            continue
        payload = json.loads(cached)
        payload["user_affected_sku_count"] = sku_count
        live.append(payload)

    return {
        "skus": profile.sku_codes,
        "live_events": live,
        "live_count": len(live),
    }
