"""Tests for contract state machine, CRUD, and API endpoints."""

from __future__ import annotations

import pytest
from ancol_common.db.repository import CONTRACT_VALID_TRANSITIONS


class TestContractStateTransitions:
    """Verify the contract state machine allows only valid transitions."""

    def test_draft_can_move_to_pending_review(self):
        assert "pending_review" in CONTRACT_VALID_TRANSITIONS["draft"]

    def test_draft_can_fail(self):
        assert "failed" in CONTRACT_VALID_TRANSITIONS["draft"]

    def test_draft_cannot_skip_to_active(self):
        assert "active" not in CONTRACT_VALID_TRANSITIONS["draft"]

    def test_pending_review_can_go_back_to_draft(self):
        assert "draft" in CONTRACT_VALID_TRANSITIONS["pending_review"]

    def test_in_review_can_approve_or_reject(self):
        assert "approved" in CONTRACT_VALID_TRANSITIONS["in_review"]
        assert "draft" in CONTRACT_VALID_TRANSITIONS["in_review"]

    def test_approved_can_only_execute(self):
        assert CONTRACT_VALID_TRANSITIONS["approved"] == ["executed"]

    def test_active_can_expire_terminate_amend(self):
        transitions = CONTRACT_VALID_TRANSITIONS["active"]
        assert "expiring" in transitions
        assert "terminated" in transitions
        assert "amended" in transitions

    def test_expired_is_terminal(self):
        assert CONTRACT_VALID_TRANSITIONS["expired"] == []

    def test_terminated_is_terminal(self):
        assert CONTRACT_VALID_TRANSITIONS["terminated"] == []

    def test_failed_can_retry_to_draft(self):
        assert "draft" in CONTRACT_VALID_TRANSITIONS["failed"]

    def test_expiring_can_renew_to_active(self):
        assert "active" in CONTRACT_VALID_TRANSITIONS["expiring"]

    def test_all_states_are_defined(self):
        expected_states = {
            "draft",
            "pending_review",
            "in_review",
            "approved",
            "executed",
            "active",
            "expiring",
            "expired",
            "terminated",
            "amended",
            "failed",
        }
        assert set(CONTRACT_VALID_TRANSITIONS.keys()) == expected_states


class TestContractApiEndpoints:
    """Verify contract API endpoints are registered."""

    @pytest.fixture
    def client(self):
        from api_gateway.main import app
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_api_root_includes_contracts(self, client):
        response = await client.get("/api")
        data = response.json()
        assert "contracts" in data["endpoints"]
        assert "obligations" in data["endpoints"]
        assert "drafting" in data["endpoints"]
