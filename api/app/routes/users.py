from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.supabase_auth import UserContext, require_user
from app.db.models import UserProfile, SavedTrolley
from app.db.session import async_transaction, get_async_session
from app.middleware import get_limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])
limiter = get_limiter()


VALID_LOYALTY_CHAINS = {"countdown", "new_world", "paknsave"}
DEFAULT_LOYALTY_CARDS = {"countdown": True, "new_world": True, "paknsave": True}


class UserProfileResponse(BaseModel):
    id: str
    email: str
    display_name: str | None = None
    preferred_radius_km: float = 2.0
    loyalty_cards: dict[str, bool] = DEFAULT_LOYALTY_CARDS
    saved_trolley_count: int = 0


class UserProfileUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=100)
    preferred_radius_km: float | None = Field(None, ge=0.5, le=50.0)
    loyalty_cards: dict[str, bool] | None = None

    @staticmethod
    def _validate_loyalty_cards(v: dict[str, bool] | None) -> dict[str, bool] | None:
        if v is None:
            return v
        if not all(k in VALID_LOYALTY_CHAINS for k in v):
            raise ValueError(f"loyalty_cards keys must be from: {VALID_LOYALTY_CHAINS}")
        if not all(isinstance(val, bool) for val in v.values()):
            raise ValueError("loyalty_cards values must be booleans")
        return v

    def __init__(self, **data):
        super().__init__(**data)
        self._validate_loyalty_cards(self.loyalty_cards)


@router.get("/me", response_model=UserProfileResponse)
async def get_or_create_profile(
    user: UserContext = Depends(require_user),
) -> UserProfileResponse:
    """Get current user's profile. Auto-creates on first call."""
    async with async_transaction() as session:
        result = await session.execute(
            select(UserProfile).where(UserProfile.id == uuid.UUID(user.id))
        )
        profile = result.scalar_one_or_none()

        if profile is None:
            # Seed display_name from Supabase user metadata if available
            profile = UserProfile(id=uuid.UUID(user.id), display_name=user.display_name)
            session.add(profile)
            await session.flush()

        # Count saved trolleys
        trolley_result = await session.execute(
            select(SavedTrolley.id).where(SavedTrolley.user_id == uuid.UUID(user.id))
        )
        trolley_count = len(trolley_result.all())

    return UserProfileResponse(
        id=str(profile.id),
        email=user.email,
        display_name=profile.display_name,
        preferred_radius_km=profile.preferred_radius_km,
        loyalty_cards=profile.loyalty_cards,
        saved_trolley_count=trolley_count,
    )


@router.patch("/me", response_model=UserProfileResponse)
@limiter.limit("10/minute")
async def update_profile(
    request: Request,
    body: UserProfileUpdate,
    user: UserContext = Depends(require_user),
) -> UserProfileResponse:
    """Update current user's profile."""
    async with async_transaction() as session:
        result = await session.execute(
            select(UserProfile).where(UserProfile.id == uuid.UUID(user.id))
        )
        profile = result.scalar_one_or_none()

        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found. Call GET /users/me first.")

        if body.display_name is not None:
            profile.display_name = body.display_name
        if body.preferred_radius_km is not None:
            profile.preferred_radius_km = body.preferred_radius_km
        if body.loyalty_cards is not None:
            profile.loyalty_cards = body.loyalty_cards

        await session.flush()

        trolley_result = await session.execute(
            select(SavedTrolley.id).where(SavedTrolley.user_id == uuid.UUID(user.id))
        )
        trolley_count = len(trolley_result.all())

    return UserProfileResponse(
        id=str(profile.id),
        email=user.email,
        display_name=profile.display_name,
        preferred_radius_km=profile.preferred_radius_km,
        loyalty_cards=profile.loyalty_cards,
        saved_trolley_count=trolley_count,
    )


@router.delete("/me", status_code=204)
@limiter.limit("10/minute")
async def delete_account(
    request: Request,
    user: UserContext = Depends(require_user),
) -> None:
    """Delete current user's profile and all associated data."""
    async with async_transaction() as session:
        result = await session.execute(
            select(UserProfile).where(UserProfile.id == uuid.UUID(user.id))
        )
        profile = result.scalar_one_or_none()

        if profile is None:
            return  # Already gone, idempotent

        await session.delete(profile)
