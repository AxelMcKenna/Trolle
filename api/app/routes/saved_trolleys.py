from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.supabase_auth import UserContext, require_user
from app.db.models import SavedTrolley, UserProfile
from app.db.session import async_transaction, get_async_session
from app.middleware import get_limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trolleys", tags=["saved-trolleys"])
limiter = get_limiter()

MAX_TROLLEYS_PER_USER = 20
MAX_ITEMS_PER_TROLLEY = 50


class TrolleyItemSchema(BaseModel):
    product_id: str
    name: str
    brand: str | None = None
    size: str | None = None
    chain: str
    image_url: str | None = None
    quantity: int = Field(ge=1, le=99, default=1)


class CreateTrolleyRequest(BaseModel):
    name: str = Field(max_length=100)
    items: list[TrolleyItemSchema] = Field(max_length=MAX_ITEMS_PER_TROLLEY)


class UpdateTrolleyRequest(BaseModel):
    name: str | None = Field(None, max_length=100)
    items: list[TrolleyItemSchema] | None = Field(None, max_length=MAX_ITEMS_PER_TROLLEY)


class SavedTrolleyResponse(BaseModel):
    id: str
    name: str
    items: list[dict[str, Any]]
    item_count: int
    created_at: datetime
    updated_at: datetime


class SavedTrolleyListResponse(BaseModel):
    trolleys: list[SavedTrolleyResponse]
    count: int


def _trolley_to_response(t: SavedTrolley) -> SavedTrolleyResponse:
    items = t.items if isinstance(t.items, list) else []
    return SavedTrolleyResponse(
        id=str(t.id),
        name=t.name,
        items=items,
        item_count=len(items),
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@router.get("", response_model=SavedTrolleyListResponse)
async def list_trolleys(
    user: UserContext = Depends(require_user),
) -> SavedTrolleyListResponse:
    """List all saved trolleys for the current user."""
    async with get_async_session() as session:
        result = await session.execute(
            select(SavedTrolley)
            .where(SavedTrolley.user_id == uuid.UUID(user.id))
            .order_by(SavedTrolley.updated_at.desc())
            .limit(MAX_TROLLEYS_PER_USER)
        )
        trolleys = result.scalars().all()

    return SavedTrolleyListResponse(
        trolleys=[_trolley_to_response(t) for t in trolleys],
        count=len(trolleys),
    )


@router.post("", response_model=SavedTrolleyResponse, status_code=201)
@limiter.limit("10/minute")
async def create_trolley(
    request: Request,
    body: CreateTrolleyRequest,
    user: UserContext = Depends(require_user),
) -> SavedTrolleyResponse:
    """Save a new trolley."""
    user_uuid = uuid.UUID(user.id)

    async with async_transaction() as session:
        # Enforce max trolleys
        count_result = await session.execute(
            select(func.count()).select_from(SavedTrolley).where(SavedTrolley.user_id == user_uuid)
        )
        count = count_result.scalar_one()
        if count >= MAX_TROLLEYS_PER_USER:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum of {MAX_TROLLEYS_PER_USER} saved trolleys reached",
            )

        # Ensure profile exists (auto-create)
        profile_result = await session.execute(
            select(UserProfile).where(UserProfile.id == user_uuid)
        )
        if profile_result.scalar_one_or_none() is None:
            session.add(UserProfile(id=user_uuid))
            await session.flush()

        trolley = SavedTrolley(
            user_id=user_uuid,
            name=body.name,
            items=[item.model_dump() for item in body.items],
        )
        session.add(trolley)
        await session.flush()
        await session.refresh(trolley)

    return _trolley_to_response(trolley)


@router.get("/{trolley_id}", response_model=SavedTrolleyResponse)
async def get_trolley(
    trolley_id: uuid.UUID,
    user: UserContext = Depends(require_user),
) -> SavedTrolleyResponse:
    """Get a specific saved trolley."""
    async with get_async_session() as session:
        result = await session.execute(
            select(SavedTrolley).where(
                SavedTrolley.id == trolley_id,
                SavedTrolley.user_id == uuid.UUID(user.id),
            )
        )
        trolley = result.scalar_one_or_none()

    if trolley is None:
        raise HTTPException(status_code=404, detail="Trolley not found")

    return _trolley_to_response(trolley)


@router.put("/{trolley_id}", response_model=SavedTrolleyResponse)
@limiter.limit("10/minute")
async def update_trolley(
    request: Request,
    trolley_id: uuid.UUID,
    body: UpdateTrolleyRequest,
    user: UserContext = Depends(require_user),
) -> SavedTrolleyResponse:
    """Update a saved trolley's name and/or items."""
    async with async_transaction() as session:
        result = await session.execute(
            select(SavedTrolley).where(
                SavedTrolley.id == trolley_id,
                SavedTrolley.user_id == uuid.UUID(user.id),
            )
        )
        trolley = result.scalar_one_or_none()

        if trolley is None:
            raise HTTPException(status_code=404, detail="Trolley not found")

        if body.name is not None:
            trolley.name = body.name
        if body.items is not None:
            trolley.items = [item.model_dump() for item in body.items]

        await session.flush()
        await session.refresh(trolley)

    return _trolley_to_response(trolley)


@router.delete("/{trolley_id}", status_code=204)
@limiter.limit("10/minute")
async def delete_trolley(
    request: Request,
    trolley_id: uuid.UUID,
    user: UserContext = Depends(require_user),
) -> None:
    """Delete a saved trolley."""
    async with async_transaction() as session:
        result = await session.execute(
            select(SavedTrolley).where(
                SavedTrolley.id == trolley_id,
                SavedTrolley.user_id == uuid.UUID(user.id),
            )
        )
        trolley = result.scalar_one_or_none()

        if trolley is None:
            raise HTTPException(status_code=404, detail="Trolley not found")

        await session.delete(trolley)


# --- Sharing ---

class ShareResponse(BaseModel):
    share_token: str
    share_url: str


@router.post("/{trolley_id}/share", response_model=ShareResponse)
async def share_trolley(
    trolley_id: uuid.UUID,
    user: UserContext = Depends(require_user),
) -> ShareResponse:
    """Generate a share link for a saved trolley."""
    async with async_transaction() as session:
        result = await session.execute(
            select(SavedTrolley).where(
                SavedTrolley.id == trolley_id,
                SavedTrolley.user_id == uuid.UUID(user.id),
            )
        )
        trolley = result.scalar_one_or_none()
        if trolley is None:
            raise HTTPException(status_code=404, detail="Trolley not found")

        if not trolley.share_token:
            trolley.share_token = secrets.token_urlsafe(16)[:24]

    return ShareResponse(
        share_token=trolley.share_token,
        share_url=f"/trolley/shared/{trolley.share_token}",
    )


@router.get("/shared/{share_token}", response_model=SavedTrolleyResponse)
async def get_shared_trolley(share_token: str) -> SavedTrolleyResponse:
    """Get a shared trolley by its share token. No authentication required."""
    async with get_async_session() as session:
        result = await session.execute(
            select(SavedTrolley).where(SavedTrolley.share_token == share_token)
        )
        trolley = result.scalar_one_or_none()
        if trolley is None:
            raise HTTPException(status_code=404, detail="Shared trolley not found")

    return _trolley_to_response(trolley)
