"""Tests for MFA (TOTP) enrollment, verification, and enforcement."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from urllib.parse import unquote

import jwt
import pyotp
import pytest
from ancol_common.auth.mfa import (
    create_mfa_token,
    decrypt_secret,
    encrypt_secret,
    generate_backup_codes,
    generate_totp_secret,
    get_provisioning_uri,
    is_mfa_required_for_role,
    require_mfa_verified,
    verify_backup_code,
    verify_mfa_token,
    verify_totp_code,
)
from ancol_common.config import Settings
from cryptography.fernet import Fernet
from pydantic import ValidationError

_TEST_FERNET_KEY = Fernet.generate_key().decode()
_TEST_JWT_SECRET = "test-jwt-secret-for-mfa-32chars!"

_MFA_SETTINGS = Settings(
    mfa_encryption_key=_TEST_FERNET_KEY,
    mfa_jwt_secret=_TEST_JWT_SECRET,
    mfa_enabled=True,
    mfa_required_roles="admin,corp_secretary,internal_auditor,legal_compliance",
    mfa_token_ttl_minutes=480,
    mfa_totp_issuer="Ancol Test",
)


@pytest.fixture(autouse=True)
def _mock_mfa_settings(monkeypatch):
    """Ensure all MFA tests use consistent settings regardless of test ordering."""
    monkeypatch.setattr("ancol_common.auth.mfa.get_settings", lambda: _MFA_SETTINGS)


class TestMFACrypto:
    """Test encryption/decryption of TOTP secrets."""

    def test_encrypt_decrypt_roundtrip(self):
        secret = "JBSWY3DPEHPK3PXP"
        encrypted = encrypt_secret(secret)
        assert encrypted != secret
        assert decrypt_secret(encrypted) == secret

    def test_decrypt_tampered_fails(self):
        from cryptography.fernet import InvalidToken

        secret = "JBSWY3DPEHPK3PXP"
        encrypted = encrypt_secret(secret)
        tampered = encrypted[:-5] + "XXXXX"
        with pytest.raises(InvalidToken):
            decrypt_secret(tampered)

    def test_generate_totp_secret_format(self):
        secret = generate_totp_secret()
        assert len(secret) == 32
        base64.b32decode(secret)  # Should not raise

    def test_encrypt_different_each_time(self):
        secret = "JBSWY3DPEHPK3PXP"
        e1 = encrypt_secret(secret)
        e2 = encrypt_secret(secret)
        assert e1 != e2
        assert decrypt_secret(e1) == decrypt_secret(e2) == secret


class TestMFATotp:
    """Test TOTP code generation and verification."""

    def test_verify_valid_code(self):
        secret = generate_totp_secret()
        totp = pyotp.TOTP(secret)
        code = totp.now()
        assert verify_totp_code(secret, code) is True

    def test_verify_wrong_code(self):
        secret = generate_totp_secret()
        assert verify_totp_code(secret, "000000") is False

    def test_provisioning_uri_format(self):
        secret = "JBSWY3DPEHPK3PXP"
        uri = get_provisioning_uri(secret, "test@ancol.co.id")
        assert uri.startswith("otpauth://totp/")
        decoded = unquote(uri)
        assert "test@ancol.co.id" in decoded
        assert "Ancol" in decoded


class TestMFABackupCodes:
    """Test backup code generation and verification."""

    def test_generate_produces_10_codes(self):
        codes, hashes_json = generate_backup_codes()
        assert len(codes) == 10
        hashes = json.loads(hashes_json)
        assert len(hashes) == 10

    def test_backup_code_format(self):
        codes, _ = generate_backup_codes()
        for code in codes:
            assert len(code) == 9  # XXXX-XXXX
            assert code[4] == "-"

    def test_verify_valid_backup_code(self):
        codes, hashes_json = generate_backup_codes()
        valid, updated = verify_backup_code(codes[0], hashes_json)
        assert valid is True
        assert updated is not None
        assert len(json.loads(updated)) == 9

    def test_backup_code_single_use(self):
        codes, hashes_json = generate_backup_codes()
        valid, updated = verify_backup_code(codes[0], hashes_json)
        assert valid is True
        valid2, _ = verify_backup_code(codes[0], updated)
        assert valid2 is False

    def test_verify_invalid_backup_code(self):
        _, hashes_json = generate_backup_codes()
        valid, updated = verify_backup_code("XXXX-YYYY", hashes_json)
        assert valid is False
        assert updated is None


class TestMFASessionToken:
    """Test MFA session JWT creation and verification."""

    def test_create_and_verify_roundtrip(self):
        token, expires_at = create_mfa_token("test@ancol.co.id")
        assert isinstance(token, str)
        assert expires_at > datetime.now(UTC)
        email = verify_mfa_token(token)
        assert email == "test@ancol.co.id"

    def test_expired_token_rejected(self):
        payload = {
            "sub": "test@ancol.co.id",
            "type": "mfa_verified",
            "iat": datetime.now(UTC) - timedelta(hours=10),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        }
        token = jwt.encode(payload, _TEST_JWT_SECRET, algorithm="HS256")
        assert verify_mfa_token(token) is None

    def test_tampered_token_rejected(self):
        token, _ = create_mfa_token("test@ancol.co.id")
        tampered = token[:-5] + "XXXXX"
        assert verify_mfa_token(tampered) is None

    def test_wrong_type_rejected(self):
        payload = {
            "sub": "test@ancol.co.id",
            "type": "wrong_type",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(hours=8),
        }
        token = jwt.encode(payload, _TEST_JWT_SECRET, algorithm="HS256")
        assert verify_mfa_token(token) is None


class TestMFARolePolicy:
    """Test role-based MFA requirement logic."""

    def test_admin_requires_mfa(self):
        assert is_mfa_required_for_role("admin") is True

    def test_corp_secretary_requires_mfa(self):
        assert is_mfa_required_for_role("corp_secretary") is True

    def test_internal_auditor_requires_mfa(self):
        assert is_mfa_required_for_role("internal_auditor") is True

    def test_legal_compliance_requires_mfa(self):
        assert is_mfa_required_for_role("legal_compliance") is True

    def test_komisaris_does_not_require_mfa(self):
        assert is_mfa_required_for_role("komisaris") is False

    def test_contract_manager_does_not_require_mfa(self):
        assert is_mfa_required_for_role("contract_manager") is False

    def test_business_dev_does_not_require_mfa(self):
        assert is_mfa_required_for_role("business_dev") is False

    def test_mfa_kill_switch(self):
        """When MFA_ENABLED=false, no role requires MFA."""
        disabled_settings = Settings(mfa_enabled=False)
        with patch("ancol_common.auth.mfa.get_settings", return_value=disabled_settings):
            assert is_mfa_required_for_role("admin") is False
            assert is_mfa_required_for_role("corp_secretary") is False


class TestMFAEnforcementDependency:
    """Test require_mfa_verified() FastAPI dependency."""

    def test_returns_depends(self):
        from fastapi.params import Depends as DependsClass

        dep = require_mfa_verified()
        assert isinstance(dep, DependsClass)

    def test_dependency_has_callable(self):
        dep = require_mfa_verified()
        assert dep.dependency is not None
        assert callable(dep.dependency)


class TestMFAEndpointSchemas:
    """Test MFA Pydantic schemas validate correctly."""

    def test_mfa_status_response(self):
        from api_gateway.routers.users import MFAStatusResponse

        resp = MFAStatusResponse(mfa_enabled=True, mfa_required=True, enrolled_at=datetime.now())
        assert resp.mfa_enabled is True

    def test_mfa_confirm_request_validates_code(self):
        from api_gateway.routers.users import MFAConfirmRequest

        req = MFAConfirmRequest(code="123456")
        assert req.code == "123456"

    def test_mfa_confirm_request_rejects_bad_code(self):
        from api_gateway.routers.users import MFAConfirmRequest

        with pytest.raises(ValidationError):
            MFAConfirmRequest(code="abc")

    def test_mfa_verify_response(self):
        from api_gateway.routers.users import MFAVerifyResponse

        resp = MFAVerifyResponse(verified=True, expires_at=datetime.now())
        assert resp.verified is True

    def test_mfa_enroll_response(self):
        from api_gateway.routers.users import MFAEnrollResponse

        resp = MFAEnrollResponse(provisioning_uri="otpauth://totp/test", qr_code_base64="abc123")
        assert resp.provisioning_uri.startswith("otpauth://")


class TestMFAPermissionInRBAC:
    """Test MFA permission key exists in RBAC matrix."""

    def test_mfa_admin_reset_exists(self):
        from ancol_common.auth.rbac import ROLE_PERMISSIONS
        from ancol_common.schemas.mom import UserRole

        assert "mfa:admin_reset" in ROLE_PERMISSIONS
        assert UserRole.ADMIN in ROLE_PERMISSIONS["mfa:admin_reset"]

    def test_mfa_admin_reset_admin_only(self):
        from ancol_common.auth.rbac import ROLE_PERMISSIONS
        from ancol_common.schemas.mom import UserRole

        allowed = ROLE_PERMISSIONS["mfa:admin_reset"]
        assert len(allowed) == 1
        assert UserRole.ADMIN in allowed


class TestRouterMFADependencyWired:
    """Verify that sensitive routers have MFA dependency wired."""

    def test_documents_router_has_mfa(self):
        from api_gateway.routers import documents

        deps = documents.router.dependencies
        assert any("_check_mfa" in str(d.dependency) for d in deps)

    def test_hitl_router_has_mfa(self):
        from api_gateway.routers import hitl

        deps = hitl.router.dependencies
        assert any("_check_mfa" in str(d.dependency) for d in deps)

    def test_contracts_router_has_mfa(self):
        from api_gateway.routers import contracts

        deps = contracts.router.dependencies
        assert any("_check_mfa" in str(d.dependency) for d in deps)

    def test_drafting_router_has_mfa(self):
        from api_gateway.routers import drafting

        deps = drafting.router.dependencies
        assert any("_check_mfa" in str(d.dependency) for d in deps)

    def test_reports_router_has_mfa(self):
        from api_gateway.routers import reports

        deps = reports.router.dependencies
        assert any("_check_mfa" in str(d.dependency) for d in deps)

    def test_audit_router_has_mfa(self):
        from api_gateway.routers import audit

        deps = audit.router.dependencies
        assert any("_check_mfa" in str(d.dependency) for d in deps)

    def test_users_router_no_mfa(self):
        """Users router should NOT have MFA (would block enrollment)."""
        from api_gateway.routers import users

        deps = users.router.dependencies
        assert not any("_check_mfa" in str(d.dependency) for d in deps)

    def test_notifications_router_no_mfa(self):
        from api_gateway.routers import notifications

        deps = notifications.router.dependencies
        assert not any("_check_mfa" in str(d.dependency) for d in deps)
