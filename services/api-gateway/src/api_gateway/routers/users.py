"""Users API — list users, manage roles, and MFA enrollment/verification."""

from __future__ import annotations

import base64
import io
import uuid
from datetime import UTC, datetime

import qrcode
from ancol_common.auth.iap import get_iap_user
from ancol_common.auth.mfa import (
    create_mfa_token,
    decrypt_secret,
    encrypt_secret,
    generate_backup_codes,
    generate_totp_secret,
    get_provisioning_uri,
    is_mfa_required_for_role,
    verify_backup_code,
    verify_totp_code,
)
from ancol_common.auth.rbac import require_permission, require_role
from ancol_common.config import get_settings
from ancol_common.db.connection import get_session
from ancol_common.db.models import User
from ancol_common.db.repository import get_user_by_email
from ancol_common.notifications.dispatcher import VALID_CHANNELS
from ancol_common.schemas.mom import UserRole
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

router = APIRouter(prefix="/users", tags=["Users"])


# ── Schemas ──


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    department: str | None = None
    phone_number: str | None = None
    notification_channels: list[str] | None = None
    is_active: bool
    created_at: datetime

    @classmethod
    def from_user(cls, u: User) -> UserResponse:
        return cls(
            id=str(u.id),
            email=u.email,
            display_name=u.display_name,
            role=u.role,
            department=u.department,
            phone_number=u.phone_number,
            notification_channels=u.notification_channels,
            is_active=u.is_active,
            created_at=u.created_at,
        )


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int


class MFAStatusResponse(BaseModel):
    mfa_enabled: bool
    mfa_required: bool
    enrolled_at: datetime | None = None


class MFAEnrollResponse(BaseModel):
    provisioning_uri: str
    qr_code_base64: str


class MFAConfirmRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class MFAConfirmResponse(BaseModel):
    backup_codes: list[str]
    message: str


class MFAVerifyRequest(BaseModel):
    code: str


class MFAVerifyResponse(BaseModel):
    verified: bool
    expires_at: datetime


class MFADisableRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class UserProfileUpdateRequest(BaseModel):
    phone_number: str | None = Field(None, pattern=r"^\+[1-9]\d{6,14}$")
    notification_channels: list[str] | None = None


# ── Helpers ──


def _clear_mfa_fields(user: User) -> None:
    """Reset all MFA-related fields on a user."""
    user.mfa_enabled = False
    user.mfa_secret_encrypted = None
    user.mfa_backup_codes_encrypted = None
    user.mfa_enrolled_at = None


# ── User Endpoints ──


@router.get("", response_model=UserListResponse)
async def list_users(
    _auth=require_permission("audit_trail:view"),
    role: str | None = None,
    active_only: bool = True,
):
    """List users with optional role filter."""
    async with get_session() as session:
        query = select(User).order_by(User.display_name)
        if role:
            query = query.where(User.role == role)
        if active_only:
            query = query.where(User.is_active.is_(True))

        result = await session.execute(query)
        users = result.scalars().all()

    return UserListResponse(
        users=[UserResponse.from_user(u) for u in users],
        total=len(users),
    )


@router.get("/me/mfa/status", response_model=MFAStatusResponse)
async def mfa_status(request: Request, _auth=require_permission("users:update_profile")):
    """Check current user's MFA enrollment status."""
    iap_user = get_iap_user(request)
    async with get_session() as session:
        user = await get_user_by_email(session, iap_user["email"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return MFAStatusResponse(
            mfa_enabled=user.mfa_enabled,
            mfa_required=is_mfa_required_for_role(user.role),
            enrolled_at=user.mfa_enrolled_at,
        )


@router.post("/me/mfa/enroll", response_model=MFAEnrollResponse)
async def mfa_enroll(request: Request, _auth=require_permission("users:update_profile")):
    """Begin MFA enrollment — returns TOTP secret and QR code."""
    iap_user = get_iap_user(request)
    async with get_session() as session:
        user = await get_user_by_email(session, iap_user["email"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.mfa_enabled:
            raise HTTPException(status_code=409, detail="MFA already enrolled")
        if user.mfa_secret_encrypted:
            raise HTTPException(status_code=409, detail="MFA enrollment already in progress")

        secret = generate_totp_secret()
        user.mfa_secret_encrypted = encrypt_secret(secret)
        await session.commit()

    uri = get_provisioning_uri(secret, iap_user["email"])
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return MFAEnrollResponse(provisioning_uri=uri, qr_code_base64=qr_b64)


@router.post("/me/mfa/confirm", response_model=MFAConfirmResponse)
async def mfa_confirm(
    request: Request, body: MFAConfirmRequest, _auth=require_permission("users:update_profile")
):
    """Confirm enrollment with first valid TOTP code. Returns backup codes."""
    iap_user = get_iap_user(request)
    async with get_session() as session:
        user = await get_user_by_email(session, iap_user["email"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.mfa_enabled:
            raise HTTPException(status_code=409, detail="MFA already confirmed")
        if not user.mfa_secret_encrypted:
            raise HTTPException(status_code=400, detail="MFA enrollment not started")

        secret = decrypt_secret(user.mfa_secret_encrypted)
        if not verify_totp_code(secret, body.code):
            raise HTTPException(status_code=400, detail="Invalid TOTP code")

        codes, hashes_json = generate_backup_codes()
        user.mfa_enabled = True
        user.mfa_backup_codes_encrypted = hashes_json
        user.mfa_enrolled_at = datetime.now(UTC)
        await session.commit()

    return MFAConfirmResponse(
        backup_codes=codes,
        message="MFA enabled successfully. Save your backup codes securely.",
    )


@router.post("/me/mfa/verify", response_model=MFAVerifyResponse)
async def mfa_verify(
    request: Request,
    body: MFAVerifyRequest,
    response: Response,
    _auth=require_permission("users:update_profile"),
):
    """Verify TOTP or backup code for current session. Sets MFA cookie."""
    iap_user = get_iap_user(request)
    async with get_session() as session:
        user = await get_user_by_email(session, iap_user["email"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not user.mfa_enabled or not user.mfa_secret_encrypted:
            raise HTTPException(status_code=400, detail="MFA not enrolled")

        secret = decrypt_secret(user.mfa_secret_encrypted)
        code = body.code.strip()

        if code.isdigit() and len(code) == 6:
            if not verify_totp_code(secret, code):
                raise HTTPException(status_code=401, detail="Invalid TOTP code")
        elif "-" in code and user.mfa_backup_codes_encrypted:
            valid, updated_hashes = verify_backup_code(code, user.mfa_backup_codes_encrypted)
            if not valid:
                raise HTTPException(status_code=401, detail="Invalid backup code")
            user.mfa_backup_codes_encrypted = updated_hashes
            await session.commit()
        else:
            raise HTTPException(status_code=400, detail="Invalid code format")

    token, expires_at = create_mfa_token(iap_user["email"])
    response.set_cookie(
        key="ancol_mfa_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=get_settings().mfa_token_ttl_minutes * 60,
    )
    return MFAVerifyResponse(verified=True, expires_at=expires_at)


@router.post("/me/mfa/disable")
async def mfa_disable(
    request: Request, body: MFADisableRequest, _auth=require_permission("users:update_profile")
):
    """Disable MFA (self-service). Requires current TOTP code."""
    iap_user = get_iap_user(request)
    async with get_session() as session:
        user = await get_user_by_email(session, iap_user["email"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not user.mfa_enabled:
            raise HTTPException(status_code=400, detail="MFA not enabled")

        if is_mfa_required_for_role(user.role):
            raise HTTPException(status_code=403, detail="MFA is mandatory for your role")

        secret = decrypt_secret(user.mfa_secret_encrypted)
        if not verify_totp_code(secret, body.code):
            raise HTTPException(status_code=400, detail="Invalid TOTP code")

        _clear_mfa_fields(user)
        await session.commit()

    return {"message": "MFA disabled successfully"}


@router.post("/{user_id}/mfa/reset")
async def mfa_admin_reset(
    user_id: str,
    _auth=require_role(UserRole.ADMIN),
):
    """Admin force-reset another user's MFA."""
    async with get_session() as session:
        user = await session.get(User, uuid.UUID(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        _clear_mfa_fields(user)
        await session.commit()

    return {"message": f"MFA reset for user {user_id}"}


@router.patch("/me/profile", response_model=UserResponse)
async def update_profile(
    request: Request,
    body: UserProfileUpdateRequest,
    _auth=require_permission("users:update_profile"),
):
    """Update current user's phone number and notification preferences."""
    iap_user = get_iap_user(request)
    async with get_session() as session:
        user = await get_user_by_email(session, iap_user["email"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if body.notification_channels is not None:
            invalid = set(body.notification_channels) - VALID_CHANNELS
            if invalid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid channels: {', '.join(invalid)}",
                )
            if "whatsapp" in body.notification_channels:
                phone = body.phone_number or user.phone_number
                if not phone:
                    raise HTTPException(
                        status_code=400,
                        detail="Phone number required to enable WhatsApp notifications",
                    )
            user.notification_channels = body.notification_channels

        if body.phone_number is not None:
            user.phone_number = body.phone_number

        await session.commit()
        await session.refresh(user)

        return UserResponse.from_user(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, _auth=require_permission("audit_trail:view")):
    """Get a single user."""
    async with get_session() as session:
        user = await session.get(User, uuid.UUID(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

    return UserResponse.from_user(user)
