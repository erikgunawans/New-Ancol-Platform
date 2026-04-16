"""Push notification subscription and preference management."""

from __future__ import annotations

from ancol_common.auth.iap import get_iap_user
from ancol_common.auth.rbac import require_permission
from ancol_common.db.connection import get_session
from ancol_common.db.repository import get_user_by_email
from ancol_common.notifications.dispatcher import DEFAULT_CHANNELS, VALID_CHANNELS
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/notifications", tags=["Notifications"])

# In-memory subscription store keyed by endpoint (replaced by DB in production)
_subscriptions: dict[str, dict] = {}


class NotificationPreferencesResponse(BaseModel):
    channels: list[str]
    phone_number: str | None = None


class NotificationPreferencesUpdateRequest(BaseModel):
    channels: list[str]


@router.post("/subscribe")
async def subscribe(body: dict, _auth=require_permission("notifications:manage")):
    endpoint = body.get("endpoint")
    if not endpoint:
        return {"status": "error", "message": "Missing endpoint"}
    _subscriptions[endpoint] = body
    return {"status": "subscribed"}


@router.post("/unsubscribe")
async def unsubscribe(body: dict, _auth=require_permission("notifications:manage")):
    endpoint = body.get("endpoint", "")
    _subscriptions.pop(endpoint, None)
    return {"status": "unsubscribed"}


@router.get("/subscriptions")
async def list_subscriptions(_auth=require_permission("notifications:view")):
    subs = list(_subscriptions.values())
    return {"subscriptions": subs, "total": len(subs)}


@router.get("/me/preferences", response_model=NotificationPreferencesResponse)
async def get_preferences(request: Request, _auth=require_permission("notifications:view")):
    """Get current user's notification channel preferences."""
    iap_user = get_iap_user(request)
    async with get_session() as session:
        user = await get_user_by_email(session, iap_user["email"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return NotificationPreferencesResponse(
            channels=user.notification_channels or DEFAULT_CHANNELS,
            phone_number=user.phone_number,
        )


@router.patch("/me/preferences", response_model=NotificationPreferencesResponse)
async def update_preferences(
    request: Request, body: NotificationPreferencesUpdateRequest,
    _auth=require_permission("notifications:manage"),
):
    """Update current user's notification channel preferences."""
    iap_user = get_iap_user(request)
    invalid = set(body.channels) - VALID_CHANNELS
    if invalid:
        raise HTTPException(
            status_code=400, detail=f"Invalid channels: {', '.join(invalid)}"
        )

    async with get_session() as session:
        user = await get_user_by_email(session, iap_user["email"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if "whatsapp" in body.channels and not user.phone_number:
            raise HTTPException(
                status_code=400,
                detail="Phone number required to enable WhatsApp notifications",
            )

        user.notification_channels = body.channels
        await session.commit()
        await session.refresh(user)

        return NotificationPreferencesResponse(
            channels=user.notification_channels or DEFAULT_CHANNELS,
            phone_number=user.phone_number,
        )
