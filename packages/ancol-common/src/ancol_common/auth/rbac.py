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
    # Union permission for HITL decide endpoint (any role that can approve at least one gate)
    "hitl:decide": {
        UserRole.CORP_SECRETARY,
        UserRole.INTERNAL_AUDITOR,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.ADMIN,
    },
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
    "notifications:manage": {
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
    # MFA
    "mfa:admin_reset": {UserRole.ADMIN},
    # User profile
    "users:update_profile": {
        UserRole.CORP_SECRETARY,
        UserRole.INTERNAL_AUDITOR,
        UserRole.KOMISARIS,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.CONTRACT_MANAGER,
        UserRole.BUSINESS_DEV,
        UserRole.DEWAN_PENGAWAS,
        UserRole.DIREKSI,
        UserRole.ADMIN,
    },
    # ── BJR: Strategic Decisions ──
    "decisions:create": {
        UserRole.BUSINESS_DEV,
        UserRole.CORP_SECRETARY,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.DIREKSI,
        UserRole.ADMIN,
    },
    "decisions:list": {
        UserRole.BUSINESS_DEV,
        UserRole.CORP_SECRETARY,
        UserRole.INTERNAL_AUDITOR,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.KOMISARIS,
        UserRole.DEWAN_PENGAWAS,
        UserRole.DIREKSI,
        UserRole.ADMIN,
    },
    "decisions:edit": {
        UserRole.BUSINESS_DEV,
        UserRole.CORP_SECRETARY,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.ADMIN,
    },
    "decisions:link_evidence": {
        UserRole.BUSINESS_DEV,
        UserRole.CORP_SECRETARY,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.INTERNAL_AUDITOR,
        UserRole.ADMIN,
    },
    "decisions:passport": {
        UserRole.KOMISARIS,
        UserRole.DEWAN_PENGAWAS,
        UserRole.DIREKSI,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.CORP_SECRETARY,
        UserRole.INTERNAL_AUDITOR,
        UserRole.ADMIN,
    },
    "bjr:compute": {
        UserRole.BUSINESS_DEV,
        UserRole.CORP_SECRETARY,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.INTERNAL_AUDITOR,
        UserRole.ADMIN,
    },
    "bjr:read": {
        UserRole.BUSINESS_DEV,
        UserRole.CORP_SECRETARY,
        UserRole.INTERNAL_AUDITOR,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.KOMISARIS,
        UserRole.DEWAN_PENGAWAS,
        UserRole.DIREKSI,
        UserRole.ADMIN,
    },
    "bjr:gate_5_komisaris": {UserRole.KOMISARIS, UserRole.ADMIN},
    "bjr:gate_5_legal": {UserRole.LEGAL_COMPLIANCE, UserRole.ADMIN},
    # ── BJR: RKAB / RJPP registries ──
    "rkab:view": {
        UserRole.BUSINESS_DEV,
        UserRole.CORP_SECRETARY,
        UserRole.INTERNAL_AUDITOR,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.KOMISARIS,
        UserRole.DEWAN_PENGAWAS,
        UserRole.DIREKSI,
        UserRole.ADMIN,
    },
    "rkab:manage": {
        UserRole.BUSINESS_DEV,
        UserRole.CORP_SECRETARY,
        UserRole.ADMIN,
    },
    "rjpp:view": {
        UserRole.BUSINESS_DEV,
        UserRole.CORP_SECRETARY,
        UserRole.KOMISARIS,
        UserRole.DEWAN_PENGAWAS,
        UserRole.DIREKSI,
        UserRole.ADMIN,
    },
    "rjpp:manage": {
        UserRole.BUSINESS_DEV,
        UserRole.ADMIN,
    },
    # ── BJR: Artifacts (DD/FS/SPI/AuditCom/Disclosure/OrganApproval) ──
    "dd:create": {
        UserRole.BUSINESS_DEV,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.ADMIN,
    },
    "dd:review": {UserRole.LEGAL_COMPLIANCE, UserRole.INTERNAL_AUDITOR, UserRole.ADMIN},
    "fs:create": {
        UserRole.BUSINESS_DEV,
        UserRole.CORP_SECRETARY,
        UserRole.ADMIN,
    },
    "fs:review": {UserRole.INTERNAL_AUDITOR, UserRole.LEGAL_COMPLIANCE, UserRole.ADMIN},
    "spi:submit": {UserRole.INTERNAL_AUDITOR, UserRole.ADMIN},
    "spi:view": {
        UserRole.INTERNAL_AUDITOR,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.CORP_SECRETARY,
        UserRole.KOMISARIS,
        UserRole.DEWAN_PENGAWAS,
        UserRole.ADMIN,
    },
    "audit_committee:submit": {UserRole.INTERNAL_AUDITOR, UserRole.ADMIN},
    "audit_committee:view": {
        UserRole.INTERNAL_AUDITOR,
        UserRole.KOMISARIS,
        UserRole.DEWAN_PENGAWAS,
        UserRole.CORP_SECRETARY,
        UserRole.ADMIN,
    },
    "material_disclosure:file": {
        UserRole.CORP_SECRETARY,
        UserRole.LEGAL_COMPLIANCE,
        UserRole.ADMIN,
    },
    "organ_approval:sign": {
        UserRole.KOMISARIS,
        UserRole.DEWAN_PENGAWAS,
        UserRole.DIREKSI,
        UserRole.ADMIN,
    },
    # Union permission for retroactive bundler
    "decisions:retroactive_bundle": {
        UserRole.LEGAL_COMPLIANCE,
        UserRole.INTERNAL_AUDITOR,
        UserRole.ADMIN,
    },
}


# Gate-to-permission mapping: which permission keys apply to each HITL gate
GATE_PERMISSIONS: dict[str, list[str]] = {
    "hitl_gate_1": ["hitl:gate_1"],
    "hitl_gate_2": ["hitl:gate_2"],
    "hitl_gate_3": ["hitl:gate_3"],
    "hitl_gate_4": ["hitl:gate_4_corpsec", "hitl:gate_4_audit"],
}


def check_gate_permission(user_role: str | UserRole, gate: str) -> bool:
    """Check if a user role has permission for a specific HITL gate.

    For gates 1-3, checks a single permission.
    For gate 4 (dual approval), checks either corpsec or audit permission.
    """
    role = UserRole(user_role)
    perm_keys = GATE_PERMISSIONS.get(gate, [])
    return any(role in ROLE_PERMISSIONS.get(pk, set()) for pk in perm_keys)


def get_user_visible_gates(user_role: str | UserRole) -> list[str]:
    """Return which HITL gate statuses a role is allowed to review."""
    role = UserRole(user_role)
    return [
        gate
        for gate, perm_keys in GATE_PERMISSIONS.items()
        if any(role in ROLE_PERMISSIONS.get(pk, set()) for pk in perm_keys)
    ]


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
