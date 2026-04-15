"""Push notification subscription management.

In-memory storage for development. In production, subscriptions stored
in Cloud SQL via the User model's push_subscription JSONB field.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/notifications", tags=["Notifications"])

# In-memory subscription store keyed by endpoint (replaced by DB in production)
_subscriptions: dict[str, dict] = {}


@router.post("/subscribe")
async def subscribe(body: dict):
    endpoint = body.get("endpoint")
    if not endpoint:
        return {"status": "error", "message": "Missing endpoint"}
    _subscriptions[endpoint] = body
    return {"status": "subscribed"}


@router.post("/unsubscribe")
async def unsubscribe(body: dict):
    endpoint = body.get("endpoint", "")
    _subscriptions.pop(endpoint, None)
    return {"status": "unsubscribed"}


@router.get("/subscriptions")
async def list_subscriptions():
    subs = list(_subscriptions.values())
    return {"subscriptions": subs, "total": len(subs)}
