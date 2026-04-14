"""Role-Based Access Control (RBAC) middleware."""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request

from ancol_common.auth.iap import get_iap_user
from ancol_common.schemas.mom import UserRole

logger = logging.getLogger(__name__)

# Route permissions: which roles can access which endpoints
ROLE_PERMISSIONS: dict[str, set[UserRole]] = {
    # Corp Secretary
    "documents:upload": {UserRole.CORP_SECRETARY, UserRole.ADMIN},
    "documents:list": {
        UserRole.CORP_SECRETARY,
        UserRole.INTERNAL_AUDITOR,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.ADMIN,
    },
    "hitl:gate_1": {UserRole.CORP_SECRETARY, UserRole.ADMIN},
    "hitl:gate_4_corpsec": {UserRole.CORP_SECRETARY, UserRole.ADMIN},
    # Internal Auditor
    "hitl:gate_2": {UserRole.INTERNAL_AUDITOR, UserRole.LEGAL_COMPLIANCE, UserRole.ADMIN},
    "hitl:gate_3": {UserRole.INTERNAL_AUDITOR, UserRole.ADMIN},
    "hitl:gate_4_audit": {UserRole.INTERNAL_AUDITOR, UserRole.ADMIN},
    # Komisaris
    "dashboard:view": {
        UserRole.KOMISARIS,
        UserRole.INTERNAL_AUDITOR,
        UserRole.CORP_SECRETARY,
        UserRole.ADMIN,
    },
    "reports:view_approved": {
        UserRole.KOMISARIS,
        UserRole.INTERNAL_AUDITOR,
        UserRole.CORP_SECRETARY,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.ADMIN,
    },
    # Legal
    "corpus:search": {
        UserRole.LEGAL_COMPLIANCE,
        UserRole.INTERNAL_AUDITOR,
        UserRole.ADMIN,
    },
    # Shared
    "audit_trail:view": {
        UserRole.CORP_SECRETARY,
        UserRole.INTERNAL_AUDITOR,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.ADMIN,
    },
    "notifications:view": {
        UserRole.CORP_SECRETARY,
        UserRole.INTERNAL_AUDITOR,
        UserRole.KOMISARIS,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.CONTRACT_MANAGER,
        UserRole.BUSINESS_DEV,
        UserRole.ADMIN,
    },
    # Contract Lifecycle Management
    "contracts:create": {
        UserRole.CORP_SECRETARY,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.CONTRACT_MANAGER,
        UserRole.ADMIN,
    },
    "contracts:list": {
        UserRole.CORP_SECRETARY,
        UserRole.INTERNAL_AUDITOR,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.CONTRACT_MANAGER,
        UserRole.BUSINESS_DEV,
        UserRole.KOMISARIS,
        UserRole.ADMIN,
    },
    "contracts:review": {
        UserRole.LEGAL_COMPLIANCE,
        UserRole.INTERNAL_AUDITOR,
        UserRole.CONTRACT_MANAGER,
        UserRole.ADMIN,
    },
    "contracts:approve": {
        UserRole.LEGAL_COMPLIANCE,
        UserRole.CORP_SECRETARY,
        UserRole.ADMIN,
    },
    "obligations:list": {
        UserRole.CORP_SECRETARY,
        UserRole.INTERNAL_AUDITOR,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.CONTRACT_MANAGER,
        UserRole.KOMISARIS,
        UserRole.ADMIN,
    },
    "obligations:fulfill": {
        UserRole.CONTRACT_MANAGER,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.ADMIN,
    },
    "drafting:generate": {
        UserRole.LEGAL_COMPLIANCE,
        UserRole.CONTRACT_MANAGER,
        UserRole.BUSINESS_DEV,
        UserRole.ADMIN,
    },
    "drafting:manage_library": {
        UserRole.LEGAL_COMPLIANCE,
        UserRole.ADMIN,
    },
}


def require_role(*allowed_roles: UserRole) -> Callable:
    """FastAPI dependency that enforces role-based access."""

    async def _check_role(request: Request) -> dict:
        user_info = get_iap_user(request)
        user_role = request.state.user_role if hasattr(request.state, "user_role") else None

        if user_role is None:
            raise HTTPException(status_code=403, detail="User role not found")

        if UserRole(user_role) not in allowed_roles:
            logger.warning(
                "Access denied: user %s (role=%s) attempted %s %s",
                user_info["email"],
                user_role,
                request.method,
                request.url.path,
            )
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        return user_info

    return Depends(_check_role)


def require_permission(permission: str) -> Callable:
    """FastAPI dependency that checks a named permission."""

    async def _check_permission(request: Request) -> dict:
        user_info = get_iap_user(request)
        user_role = request.state.user_role if hasattr(request.state, "user_role") else None

        if user_role is None:
            raise HTTPException(status_code=403, detail="User role not found")

        allowed = ROLE_PERMISSIONS.get(permission, set())
        if UserRole(user_role) not in allowed:
            logger.warning(
                "Permission denied: user %s (role=%s) lacks %s",
                user_info["email"],
                user_role,
                permission,
            )
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        return user_info

    return Depends(_check_permission)
