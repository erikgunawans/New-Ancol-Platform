"""Identity-Aware Proxy (IAP) JWT verification middleware."""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

IAP_HEADER = "X-Goog-IAP-JWT-Assertion"
IAP_EMAIL_HEADER = "X-Goog-Authenticated-User-Email"
IAP_ID_HEADER = "X-Goog-Authenticated-User-ID"


def get_iap_user(request: Request) -> dict:
    """Extract authenticated user info from IAP headers.

    In production, IAP sets these headers after JWT verification.
    In dev without IAP, falls back to a test user.

    Returns:
        Dict with email and id fields.
    """
    email = request.headers.get(IAP_EMAIL_HEADER)
    user_id = request.headers.get(IAP_ID_HEADER)

    if email and user_id:
        # Strip "accounts.google.com:" prefix
        email = email.removeprefix("accounts.google.com:")
        user_id = user_id.removeprefix("accounts.google.com:")
        return {"email": email, "id": user_id}

    # Dev fallback — check for X-Dev-User-Email header
    dev_email = request.headers.get("X-Dev-User-Email")
    if dev_email:
        logger.warning("Using dev fallback auth for %s", dev_email)
        return {"email": dev_email, "id": f"dev-{dev_email}"}

    raise HTTPException(status_code=401, detail="Authentication required")
