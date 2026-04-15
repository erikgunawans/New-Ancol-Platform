"""Tests for CLM RBAC permissions."""

from __future__ import annotations

from ancol_common.auth.rbac import ROLE_PERMISSIONS
from ancol_common.schemas.mom import UserRole


class TestClmRbacPermissions:
    """Verify CLM permissions are correctly mapped to roles."""

    def test_contracts_create_permissions(self):
        allowed = ROLE_PERMISSIONS["contracts:create"]
        assert UserRole.CONTRACT_MANAGER in allowed
        assert UserRole.LEGAL_COMPLIANCE in allowed
        assert UserRole.ADMIN in allowed
        assert UserRole.KOMISARIS not in allowed

    def test_contracts_list_all_roles(self):
        allowed = ROLE_PERMISSIONS["contracts:list"]
        assert UserRole.CONTRACT_MANAGER in allowed
        assert UserRole.BUSINESS_DEV in allowed
        assert UserRole.KOMISARIS in allowed
        assert len(allowed) == 7  # all roles

    def test_obligations_fulfill_restricted(self):
        allowed = ROLE_PERMISSIONS["obligations:fulfill"]
        assert UserRole.CONTRACT_MANAGER in allowed
        assert UserRole.LEGAL_COMPLIANCE in allowed
        assert UserRole.ADMIN in allowed
        assert UserRole.KOMISARIS not in allowed
        assert UserRole.BUSINESS_DEV not in allowed

    def test_drafting_generate_permissions(self):
        allowed = ROLE_PERMISSIONS["drafting:generate"]
        assert UserRole.BUSINESS_DEV in allowed
        assert UserRole.CONTRACT_MANAGER in allowed
        assert UserRole.KOMISARIS not in allowed

    def test_drafting_manage_library_restricted(self):
        allowed = ROLE_PERMISSIONS["drafting:manage_library"]
        assert UserRole.LEGAL_COMPLIANCE in allowed
        assert UserRole.ADMIN in allowed
        assert len(allowed) == 2

    def test_new_roles_have_notifications_access(self):
        allowed = ROLE_PERMISSIONS["notifications:view"]
        assert UserRole.CONTRACT_MANAGER in allowed
        assert UserRole.BUSINESS_DEV in allowed

    def test_all_clm_permissions_exist(self):
        clm_perms = [
            "contracts:create",
            "contracts:list",
            "contracts:review",
            "contracts:approve",
            "obligations:list",
            "obligations:fulfill",
            "drafting:generate",
            "drafting:manage_library",
        ]
        for perm in clm_perms:
            assert perm in ROLE_PERMISSIONS, f"Missing permission: {perm}"
