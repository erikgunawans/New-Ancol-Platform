"""Push notification subscription management.

In-memory storage for development. In production, subscriptions stored
in Cloud SQL via the User model's push_subscription JSONB field.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/notifications", tags=["Notifications"])

# In-memory subscription store (replaced by DB in production)
_subscriptions: list[dict] = []


@router.post("/subscribe")
async def subscribe(body: dict):
    endpoint = body.get("endpoint")
    if not endpoint:
        return {"status": "error", "message": "Missing endpoint"}
    for sub in _subscriptions:
        if sub["endpoint"] == endpoint:
            sub.update(body)
            return {"status": "subscribed"}
    _subscriptions.append(body)
    return {"status": "subscribed"}


@router.post("/unsubscribe")
async def unsubscribe(body: dict):
    endpoint = body.get("endpoint", "")
    _subscriptions[:] = [s for s in _subscriptions if s["endpoint"] != endpoint]
    return {"status": "unsubscribed"}


@router.get("/subscriptions")
async def list_subscriptions():
    return {"subscriptions": _subscriptions, "total": len(_subscriptions)}
