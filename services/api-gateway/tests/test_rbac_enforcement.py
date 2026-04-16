"""Tests for RBAC enforcement wiring across all routers."""

from __future__ import annotations

from ancol_common.auth.rbac import (
    GATE_PERMISSIONS,
    ROLE_PERMISSIONS,
    check_gate_permission,
    get_user_visible_gates,
    require_permission,
)
from ancol_common.schemas.mom import UserRole


class TestPermissionMatrixCompleteness:
    """Verify all permission keys referenced by routers exist."""

    def test_hitl_decide_exists(self):
        assert "hitl:decide" in ROLE_PERMISSIONS

    def test_hitl_decide_roles(self):
        allowed = ROLE_PERMISSIONS["hitl:decide"]
        assert UserRole.CORP_SECRETARY in allowed
        assert UserRole.INTERNAL_AUDITOR in allowed
        assert UserRole.LEGAL_COMPLIANCE in allowed
        assert UserRole.ADMIN in allowed
        assert UserRole.KOMISARIS not in allowed
        assert UserRole.CONTRACT_MANAGER not in allowed
        assert UserRole.BUSINESS_DEV not in allowed

    def test_all_router_permissions_exist(self):
        """Every permission key used by routers must be in ROLE_PERMISSIONS."""
        required = [
            "documents:upload",
            "documents:list",
            "hitl:decide",
            "reports:view_approved",
            "dashboard:view",
            "audit_trail:view",
            "corpus:search",
            "contracts:create",
            "contracts:list",
            "contracts:review",
            "obligations:list",
            "obligations:fulfill",
            "drafting:generate",
        ]
        for perm in required:
            assert perm in ROLE_PERMISSIONS, f"Missing permission: {perm}"

    def test_documents_upload_excludes_readonly_roles(self):
        allowed = ROLE_PERMISSIONS["documents:upload"]
        assert UserRole.KOMISARIS not in allowed
        assert UserRole.CONTRACT_MANAGER not in allowed

    def test_dashboard_view_includes_komisaris(self):
        allowed = ROLE_PERMISSIONS["dashboard:view"]
        assert UserRole.KOMISARIS in allowed

    def test_corpus_search_restricted(self):
        allowed = ROLE_PERMISSIONS["corpus:search"]
        assert UserRole.LEGAL_COMPLIANCE in allowed
        assert UserRole.INTERNAL_AUDITOR in allowed
        assert UserRole.ADMIN in allowed
        assert UserRole.KOMISARIS not in allowed
        assert UserRole.BUSINESS_DEV not in allowed

    def test_contracts_create_excludes_komisaris(self):
        allowed = ROLE_PERMISSIONS["contracts:create"]
        assert UserRole.KOMISARIS not in allowed
        assert UserRole.BUSINESS_DEV not in allowed

    def test_obligations_fulfill_excludes_readonly(self):
        allowed = ROLE_PERMISSIONS["obligations:fulfill"]
        assert UserRole.KOMISARIS not in allowed
        assert UserRole.BUSINESS_DEV not in allowed
        assert UserRole.CORP_SECRETARY not in allowed


class TestGatePermissions:
    """Verify GATE_PERMISSIONS mapping and helper functions."""

    def test_gate_permissions_has_all_gates(self):
        assert "hitl_gate_1" in GATE_PERMISSIONS
        assert "hitl_gate_2" in GATE_PERMISSIONS
        assert "hitl_gate_3" in GATE_PERMISSIONS
        assert "hitl_gate_4" in GATE_PERMISSIONS

    def test_gate_4_has_dual_approval(self):
        perms = GATE_PERMISSIONS["hitl_gate_4"]
        assert "hitl:gate_4_corpsec" in perms
        assert "hitl:gate_4_audit" in perms

    def test_check_gate_permission_corp_secretary(self):
        assert check_gate_permission(UserRole.CORP_SECRETARY, "hitl_gate_1") is True
        assert check_gate_permission(UserRole.CORP_SECRETARY, "hitl_gate_2") is False
        assert check_gate_permission(UserRole.CORP_SECRETARY, "hitl_gate_3") is False
        assert check_gate_permission(UserRole.CORP_SECRETARY, "hitl_gate_4") is True

    def test_check_gate_permission_internal_auditor(self):
        assert check_gate_permission(UserRole.INTERNAL_AUDITOR, "hitl_gate_1") is False
        assert check_gate_permission(UserRole.INTERNAL_AUDITOR, "hitl_gate_2") is True
        assert check_gate_permission(UserRole.INTERNAL_AUDITOR, "hitl_gate_3") is True
        assert check_gate_permission(UserRole.INTERNAL_AUDITOR, "hitl_gate_4") is True

    def test_check_gate_permission_legal_compliance(self):
        assert check_gate_permission(UserRole.LEGAL_COMPLIANCE, "hitl_gate_1") is False
        assert check_gate_permission(UserRole.LEGAL_COMPLIANCE, "hitl_gate_2") is True
        assert check_gate_permission(UserRole.LEGAL_COMPLIANCE, "hitl_gate_3") is False
        assert check_gate_permission(UserRole.LEGAL_COMPLIANCE, "hitl_gate_4") is False

    def test_check_gate_permission_admin(self):
        for gate in GATE_PERMISSIONS:
            assert check_gate_permission(UserRole.ADMIN, gate) is True

    def test_check_gate_permission_non_reviewer_roles(self):
        for role in [UserRole.KOMISARIS, UserRole.CONTRACT_MANAGER, UserRole.BUSINESS_DEV]:
            for gate in GATE_PERMISSIONS:
                assert check_gate_permission(role, gate) is False

    def test_check_gate_permission_unknown_gate(self):
        assert check_gate_permission(UserRole.ADMIN, "hitl_gate_99") is False

    def test_get_user_visible_gates_corp_secretary(self):
        gates = get_user_visible_gates(UserRole.CORP_SECRETARY)
        assert "hitl_gate_1" in gates
        assert "hitl_gate_4" in gates
        assert "hitl_gate_2" not in gates
        assert "hitl_gate_3" not in gates

    def test_get_user_visible_gates_internal_auditor(self):
        gates = get_user_visible_gates(UserRole.INTERNAL_AUDITOR)
        assert "hitl_gate_2" in gates
        assert "hitl_gate_3" in gates
        assert "hitl_gate_4" in gates
        assert "hitl_gate_1" not in gates

    def test_get_user_visible_gates_legal_compliance(self):
        gates = get_user_visible_gates(UserRole.LEGAL_COMPLIANCE)
        assert gates == ["hitl_gate_2"]

    def test_get_user_visible_gates_admin(self):
        gates = get_user_visible_gates(UserRole.ADMIN)
        assert len(gates) == 4

    def test_get_user_visible_gates_komisaris(self):
        gates = get_user_visible_gates(UserRole.KOMISARIS)
        assert gates == []

    def test_check_gate_permission_accepts_string_role(self):
        assert check_gate_permission("corp_secretary", "hitl_gate_1") is True
        assert check_gate_permission("internal_auditor", "hitl_gate_1") is False


class TestRequirePermissionDependency:
    """Verify require_permission returns a FastAPI Depends callable."""

    def test_returns_depends(self):
        from fastapi.params import Depends as DependsClass

        dep = require_permission("documents:list")
        assert isinstance(dep, DependsClass)

    def test_unknown_permission_still_creates_dependency(self):
        from fastapi.params import Depends as DependsClass

        dep = require_permission("nonexistent:perm")
        assert isinstance(dep, DependsClass)


class TestRouterImportsCompile:
    """Verify all routers import and compile with require_permission."""

    def test_documents_router_loads(self):
        from api_gateway.routers import documents

        assert hasattr(documents, "router")

    def test_hitl_router_loads(self):
        from api_gateway.routers import hitl

        assert hasattr(hitl, "router")

    def test_reports_router_loads(self):
        from api_gateway.routers import reports

        assert hasattr(reports, "router")

    def test_dashboard_router_loads(self):
        from api_gateway.routers import dashboard

        assert hasattr(dashboard, "router")

    def test_analytics_router_loads(self):
        from api_gateway.routers import analytics

        assert hasattr(analytics, "router")

    def test_audit_router_loads(self):
        from api_gateway.routers import audit

        assert hasattr(audit, "router")

    def test_batch_router_loads(self):
        from api_gateway.routers import batch

        assert hasattr(batch, "router")

    def test_retroactive_router_loads(self):
        from api_gateway.routers import retroactive

        assert hasattr(retroactive, "router")

    def test_templates_router_loads(self):
        from api_gateway.routers import templates

        assert hasattr(templates, "router")

    def test_users_router_loads(self):
        from api_gateway.routers import users

        assert hasattr(users, "router")

    def test_contracts_router_loads(self):
        from api_gateway.routers import contracts

        assert hasattr(contracts, "router")

    def test_obligations_router_loads(self):
        from api_gateway.routers import obligations

        assert hasattr(obligations, "router")

    def test_drafting_router_loads(self):
        from api_gateway.routers import drafting

        assert hasattr(drafting, "router")
