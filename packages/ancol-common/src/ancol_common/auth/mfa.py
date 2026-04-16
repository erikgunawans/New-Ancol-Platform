"""Multi-Factor Authentication (MFA) — TOTP enrollment, verification, and enforcement."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt
import pyotp
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request

from ancol_common.config import get_settings

logger = logging.getLogger(__name__)


# ── Encryption ──


def _get_fernet() -> Fernet:
    """Get Fernet cipher from config."""
    key = get_settings().mfa_encryption_key
    if not key:
        raise RuntimeError("MFA_ENCRYPTION_KEY not configured")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a TOTP secret for DB storage."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a TOTP secret from DB storage."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()


# ── TOTP ──


def generate_totp_secret() -> str:
    """Generate a new random TOTP secret (base32, 32 chars)."""
    return pyotp.random_base32(length=32)


def get_provisioning_uri(secret: str, email: str) -> str:
    """Generate otpauth:// URI for authenticator app QR code scanning."""
    settings = get_settings()
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=settings.mfa_totp_issuer)


def verify_totp_code(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code. Allows 1 window of clock drift (30s)."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


# ── Backup Codes ──


def _hash_code(code: str) -> str:
    """SHA-256 hash a backup code."""
    return hashlib.sha256(code.upper().encode()).hexdigest()


def generate_backup_codes(count: int = 10) -> tuple[list[str], str]:
    """Generate backup codes.

    Returns (plaintext_codes, json_of_hashes).
    Each code is 8 alphanumeric chars formatted as XXXX-XXXX.
    """
    codes = []
    hashes = []
    for _ in range(count):
        raw = secrets.token_hex(4).upper()  # 8 hex chars
        code = f"{raw[:4]}-{raw[4:]}"
        codes.append(code)
        hashes.append(_hash_code(code))
    return codes, json.dumps(hashes)


def verify_backup_code(code: str, hashes_json: str) -> tuple[bool, str | None]:
    """Verify a backup code against stored hashes (constant-time).

    Returns (is_valid, updated_hashes_json_with_code_removed).
    Always iterates all hashes to prevent timing side-channels.
    """
    import hmac

    code_hash = _hash_code(code)
    hashes: list[str] = json.loads(hashes_json)
    match_idx = -1
    for i, h in enumerate(hashes):
        if hmac.compare_digest(code_hash, h):
            match_idx = i
    if match_idx >= 0:
        hashes.pop(match_idx)
        return True, json.dumps(hashes)
    return False, None


# ── MFA Session Token (JWT) ──


def create_mfa_token(email: str) -> tuple[str, datetime]:
    """Create a short-lived JWT indicating MFA was verified.

    Returns (token, expires_at).
    """
    settings = get_settings()
    if not settings.mfa_jwt_secret:
        raise RuntimeError("MFA_JWT_SECRET not configured")
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.mfa_token_ttl_minutes)
    payload = {
        "sub": email,
        "type": "mfa_verified",
        "iat": datetime.now(UTC),
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.mfa_jwt_secret, algorithm="HS256")
    return token, expires_at


def verify_mfa_token(token: str) -> str | None:
    """Verify and decode an MFA session token.

    Returns the email if valid, None if expired/invalid/tampered.
    """
    settings = get_settings()
    if not settings.mfa_jwt_secret:
        return None
    try:
        payload = jwt.decode(token, settings.mfa_jwt_secret, algorithms=["HS256"])
        if payload.get("type") != "mfa_verified":
            return None
        return payload.get("sub")
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


# ── Role Check ──


def is_mfa_required_for_role(role: str) -> bool:
    """Check if a role requires MFA based on config."""
    settings = get_settings()
    if not settings.mfa_enabled:
        return False
    return role in set(settings.mfa_required_roles.split(","))


# ── FastAPI Dependency ──


def require_mfa_verified() -> Callable:
    """FastAPI dependency that enforces MFA verification for sensitive roles.

    Checks:
    1. MFA globally enabled? (kill switch — if disabled, pass through)
    2. User's role requires MFA? (if not, pass through)
    3. User has enrolled MFA? (if required but not enrolled → 403)
    4. Valid ancol_mfa_token cookie? (if not → 401)
    """

    async def _check_mfa(request: Request) -> None:
        settings = get_settings()
        if not settings.mfa_enabled:
            return

        user_role = getattr(request.state, "user_role", None)
        if user_role is None:
            return

        required_roles = set(settings.mfa_required_roles.split(","))
        if user_role not in required_roles:
            return

        # Check if user has MFA enrolled — need DB lookup
        user = getattr(request.state, "user", None)
        if user is not None:
            # AuthMiddleware populated request.state.user
            if not user.mfa_enabled:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "mfa_enrollment_required",
                        "message": "MFA enrollment is required for your role.",
                        "enroll_url": "/api/users/me/mfa/enroll",
                    },
                )
        else:
            # AuthMiddleware not wired — do lightweight lookup
            from ancol_common.auth.iap import get_iap_user
            from ancol_common.db.connection import get_session
            from ancol_common.db.repository import get_user_by_email

            iap_user = get_iap_user(request)
            async with get_session() as session:
                db_user = await get_user_by_email(session, iap_user["email"])
            if db_user is None:
                return
            if not db_user.mfa_enabled:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "mfa_enrollment_required",
                        "message": "MFA enrollment is required for your role.",
                        "enroll_url": "/api/users/me/mfa/enroll",
                    },
                )

        # Check MFA session token from cookie
        mfa_token = request.cookies.get("ancol_mfa_token")
        if not mfa_token:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "mfa_verification_required",
                    "message": "MFA verification required.",
                    "verify_url": "/api/users/me/mfa/verify",
                },
            )

        verified_email = verify_mfa_token(mfa_token)
        if verified_email is None:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "mfa_token_expired",
                    "message": "MFA session expired. Please verify again.",
                    "verify_url": "/api/users/me/mfa/verify",
                },
            )

        # Verify MFA token belongs to the current IAP user (prevents cookie theft reuse)
        iap_user = get_iap_user(request)
        if verified_email != iap_user["email"]:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "mfa_token_mismatch",
                    "message": "MFA session does not match current user.",
                    "verify_url": "/api/users/me/mfa/verify",
                },
            )

    return Depends(_check_mfa)
