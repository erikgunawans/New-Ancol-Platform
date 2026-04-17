"""Tests for the decisions router — endpoint registration, RBAC, MFA, response schemas.

No DB integration; focuses on router wiring + Pydantic contracts. E2E DB tests
land in Phase 6.5.
"""

from __future__ import annotations

import pytest
from ancol_common.auth.rbac import ROLE_PERMISSIONS
from ancol_common.schemas.mom import UserRole


class TestDecisionRouterRegistration:
    @pytest.fixture
    def app(self):
        from api_gateway.main import app

        return app

    def test_decisions_base_mounted(self, app):
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/api/decisions" in paths

    def test_decisions_dashboard_registered(self, app):
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/api/decisions/dashboard" in paths

    def test_retroactive_propose_registered(self, app):
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/api/decisions/retroactive-propose" in paths

    def test_bjr_compute_registered(self, app):
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/api/decisions/{decision_id}/bjr-compute" in paths

    def test_readiness_registered(self, app):
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/api/decisions/{decision_id}/readiness" in paths

    def test_evidence_link_registered(self, app):
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/api/decisions/{decision_id}/evidence" in paths

    def test_evidence_unlink_registered(self, app):
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/api/decisions/{decision_id}/evidence/{evidence_link_id}" in paths

    def test_gate5_routes_registered(self, app):
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/api/decisions/{decision_id}/gate5" in paths
        assert "/api/decisions/{decision_id}/gate5/komisaris" in paths
        assert "/api/decisions/{decision_id}/gate5/legal" in paths


class TestDecisionRouterAssertions:
    def test_decision_count(self):
        from api_gateway.main import app

        decision_paths = {
            getattr(r, "path", None)
            for r in app.routes
            if getattr(r, "path", "").startswith("/api/decisions")
        }
        # CRUD(4) + evidence(2) + compute(1) + readiness(1) +
        # retroactive(1) + gate5(3) + dashboard(1) = 13 ops across ~11 unique paths.
        assert len(decision_paths) >= 10, (
            f"Expected ≥10 unique decision paths, got {len(decision_paths)}"
        )


class TestDecisionSchemas:
    def test_create_valid(self):
        from api_gateway.routers.decisions import DecisionCreate

        payload = DecisionCreate(
            title="JV Hotel Beach City",
            initiative_type="partnership",
            business_owner_id="a0000000-0000-0000-0000-000000000014",
        )
        assert payload.source == "proactive"  # default
        assert payload.value_idr is None

    def test_create_rejects_short_title(self):
        from api_gateway.routers.decisions import DecisionCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DecisionCreate(
                title="JV",  # too short
                initiative_type="partnership",
                business_owner_id="a0000000-0000-0000-0000-000000000014",
            )

    def test_create_rejects_negative_value(self):
        from api_gateway.routers.decisions import DecisionCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DecisionCreate(
                title="Investment X",
                initiative_type="investment",
                business_owner_id="a0000000-0000-0000-0000-000000000014",
                value_idr=-100.0,
            )

    def test_update_all_optional(self):
        from api_gateway.routers.decisions import DecisionUpdate

        u = DecisionUpdate()
        dumped = u.model_dump(exclude_unset=True)
        assert dumped == {}

    def test_update_partial(self):
        from api_gateway.routers.decisions import DecisionUpdate

        u = DecisionUpdate(title="Revised")
        assert u.title == "Revised"
        assert u.status is None


class TestGate5Rbac:
    """Gate 5 dual-approval isolates roles — neither half can approve both."""

    def test_komisaris_cannot_do_legal_half(self):
        legal_allowed = ROLE_PERMISSIONS["bjr:gate_5_legal"]
        assert UserRole.KOMISARIS not in legal_allowed

    def test_legal_cannot_do_komisaris_half(self):
        kom_allowed = ROLE_PERMISSIONS["bjr:gate_5_komisaris"]
        assert UserRole.LEGAL_COMPLIANCE not in kom_allowed

    def test_admin_can_do_either(self):
        assert UserRole.ADMIN in ROLE_PERMISSIONS["bjr:gate_5_komisaris"]
        assert UserRole.ADMIN in ROLE_PERMISSIONS["bjr:gate_5_legal"]

    def test_direksi_cannot_approve_own_decision(self):
        """Direksi shouldn't approve their own BJR lock — conflict of interest."""
        assert UserRole.DIREKSI not in ROLE_PERMISSIONS["bjr:gate_5_komisaris"]
        assert UserRole.DIREKSI not in ROLE_PERMISSIONS["bjr:gate_5_legal"]


class TestRetroactiveBundlerRbac:
    def test_retroactive_bundle_limited_to_audit_and_legal(self):
        allowed = ROLE_PERMISSIONS["decisions:retroactive_bundle"]
        assert UserRole.LEGAL_COMPLIANCE in allowed
        assert UserRole.INTERNAL_AUDITOR in allowed
        assert UserRole.BUSINESS_DEV not in allowed
        assert UserRole.KOMISARIS not in allowed


class TestApiRootListsDecisions:
    @pytest.fixture
    def client(self):
        from api_gateway.main import app
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_api_root_lists_decisions(self, client):
        response = await client.get("/api")
        data = response.json()
        assert "decisions" in data["endpoints"]
        assert data["endpoints"]["decisions"] == "/api/decisions"
