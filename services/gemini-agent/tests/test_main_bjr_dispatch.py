"""Dispatcher + RBAC contract tests for the new BJR tool handlers.

Task 11 of Phase 6.4a — makes the 8 BJR read-only tools shipped in
Tasks 7-10 reachable from the webhook. Tests cover:

1. ``_dispatch_tool`` routes BJR tool names to their handlers.
2. Unknown tool names raise ValueError (unchanged existing contract).
3. ``_role_allowed_tools`` exposes the right BJR tools per role, per
   spec § 4.2.
4. ``admin`` has every BJR tool (no forgotten wiring).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from gemini_agent.main import _dispatch_tool, _role_allowed_tools


@pytest.mark.asyncio
async def test_dispatch_get_decision_routes_to_handler(monkeypatch):
    """Dispatcher routes the `get_decision` tool name to its handler."""
    called = {}

    async def fake_handle_get_decision(params, api, user):
        called["ok"] = True
        called["params"] = params
        called["user"] = user
        return "ok"

    monkeypatch.setattr(
        "gemini_agent.tools.bjr_decisions.handle_get_decision",
        fake_handle_get_decision,
    )
    api = AsyncMock()
    user = {"email": "x@a.test", "role": "admin"}
    result = await _dispatch_tool("get_decision", {"decision_id": str(uuid.uuid4())}, api, user)
    assert called.get("ok") is True
    assert result == "ok"


@pytest.mark.asyncio
async def test_dispatch_unknown_tool_raises():
    """Unknown tool names still raise ValueError (existing contract)."""
    api = AsyncMock()
    user = {"email": "x@a.test", "role": "admin"}
    with pytest.raises(ValueError, match="Unknown tool"):
        await _dispatch_tool("nonexistent_tool", {}, api, user)


@pytest.mark.parametrize(
    "role,tool,should_allow",
    [
        # admin has everything
        ("admin", "get_decision", True),
        ("admin", "get_readiness", True),
        ("admin", "show_document_indicators", True),
        ("admin", "get_passport_url", True),
        # business_dev: read decisions, indicators; NO passport
        ("business_dev", "get_decision", True),
        ("business_dev", "show_document_indicators", True),
        ("business_dev", "get_passport_url", False),
        # direksi: passport + readiness + own decisions
        ("direksi", "get_passport_url", True),
        ("direksi", "get_readiness", True),
        ("direksi", "list_my_decisions", True),
        # corp_secretary: all read-only BJR tools
        ("corp_secretary", "show_document_indicators", True),
        ("corp_secretary", "show_decision_evidence", True),
        # komisaris: read-only, passport, indicators
        ("komisaris", "get_readiness", True),
        ("komisaris", "show_document_indicators", True),
        ("komisaris", "get_passport_url", True),
        # dewan_pengawas: same as komisaris
        ("dewan_pengawas", "get_readiness", True),
        # legal_compliance: read
        ("legal_compliance", "show_document_indicators", True),
        # internal_auditor: read
        ("internal_auditor", "show_decision_evidence", True),
    ],
)
def test_role_has_bjr_tool(role: str, tool: str, should_allow: bool):
    """Per spec § 4.2: each role's chat-side RBAC permits the expected BJR tools."""
    allowed = _role_allowed_tools(role)
    verb = "have" if should_allow else "not have"
    assert (tool in allowed) == should_allow, f"{role} should {verb} {tool}"


def test_all_bjr_tools_in_admin_allowed():
    """Drift-guard: admin must have every BJR tool. Missing any = forgotten wiring."""
    admin_tools = _role_allowed_tools("admin")
    expected_bjr_tools = {
        "get_decision",
        "list_decisions",
        "list_my_decisions",
        "get_readiness",
        "get_checklist",
        "show_document_indicators",
        "show_decision_evidence",
        "get_passport_url",
    }
    missing = expected_bjr_tools - admin_tools
    assert not missing, f"admin missing BJR tools: {missing}"


def test_unknown_role_returns_empty_frozenset():
    """Roles not in the matrix get no tools (fail-closed RBAC)."""
    allowed = _role_allowed_tools("nonexistent_role")
    assert allowed == frozenset()


def test_baseline_non_bjr_tools_preserved():
    """Existing pre-BJR tools must remain accessible to the same roles."""
    assert "upload_document" in _role_allowed_tools("corp_secretary")
    assert "get_dashboard" in _role_allowed_tools("internal_auditor")
    assert "generate_draft" in _role_allowed_tools("contract_manager")
    assert "search_regulations" in _role_allowed_tools("komisaris")
