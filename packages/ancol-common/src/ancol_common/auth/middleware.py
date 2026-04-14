"""Authentication middleware — resolves IAP user to DB user with role.

This middleware intercepts all requests, extracts the IAP identity,
looks up the user in the database, and attaches the user object and role
to the request state for downstream RBAC checks.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ancol_common.auth.iap import get_iap_user
from ancol_common.db.connection import get_session
from ancol_common.db.repository import get_user_by_email

logger = logging.getLogger(__name__)

# Paths that skip auth
PUBLIC_PATHS = {
    "/health",
    "/api",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/obligations/check-deadlines",
}


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that resolves IAP identity to a database user."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip auth for public endpoints
        if request.url.path in PUBLIC_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        try:
            iap_user = get_iap_user(request)
        except Exception:
            return Response(
                content='{"detail": "Authentication required"}',
                status_code=401,
                media_type="application/json",
            )

        # Look up user in database
        async with get_session() as session:
            db_user = await get_user_by_email(session, iap_user["email"])

        if db_user is None:
            logger.warning("Unknown user: %s", iap_user["email"])
            return Response(
                content='{"detail": "User not found in system"}',
                status_code=403,
                media_type="application/json",
            )

        if not db_user.is_active:
            return Response(
                content='{"detail": "User account is deactivated"}',
                status_code=403,
                media_type="application/json",
            )

        # Attach user info to request state
        request.state.user = db_user
        request.state.user_id = str(db_user.id)
        request.state.user_email = db_user.email
        request.state.user_role = db_user.role
        request.state.user_display_name = db_user.display_name

        return await call_next(request)
