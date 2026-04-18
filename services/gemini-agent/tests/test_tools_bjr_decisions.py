"""Unit tests for BJR decision read-only chat tool handlers."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from gemini_agent.tools.bjr_decisions import (
    handle_get_decision,
    handle_list_decisions,
    handle_list_my_decisions,
)


@pytest.fixture
def user_corp_sec() -> dict:
    return {"email": "corpsec@ancol.test", "role": "corp_secretary"}


@pytest.fixture
def api_mock() -> AsyncMock:
    return AsyncMock()


@pytest.mark.asyncio
async def test_get_decision_formats_response(api_mock, user_corp_sec):
    decision_id = uuid.uuid4()
    api_mock.get_decision = AsyncMock(
        return_value={
            "id": str(decision_id),
            "title": "Akuisisi PT Wahana Baru",
            "status": "dd_in_progress",
            "readiness_score": 72.0,
            "corporate_score": 72.0,
            "regional_score": 78.0,
            "initiative_type": "acquisition",
            "estimated_value_idr": 150_000_000_000,
            "origin": "proactive",
            "created_at": "2026-03-01T10:00:00+07:00",
            "owner_id": "user-xyz",
        }
    )
    out = await handle_get_decision({"decision_id": str(decision_id)}, api_mock, user_corp_sec)
    assert "Akuisisi PT Wahana Baru" in out
    assert "72" in out
    assert "miliar" in out.lower()
    assert "150" in out


@pytest.mark.asyncio
async def test_get_decision_missing_id_returns_error(api_mock, user_corp_sec):
    out = await handle_get_decision({}, api_mock, user_corp_sec)
    assert "decision_id" in out.lower()
    api_mock.get_decision.assert_not_called()


@pytest.mark.asyncio
async def test_get_decision_handles_api_404(api_mock, user_corp_sec):
    api_mock.get_decision = AsyncMock(side_effect=Exception("404"))
    out = await handle_get_decision({"decision_id": str(uuid.uuid4())}, api_mock, user_corp_sec)
    lower = out.lower()
    assert "gagal" in lower or "tidak dapat" in lower or "error" in lower


@pytest.mark.asyncio
async def test_list_decisions_default_limit(api_mock, user_corp_sec):
    api_mock.list_decisions = AsyncMock(
        return_value={
            "items": [
                {
                    "id": str(uuid.uuid4()),
                    "title": f"Decision {i}",
                    "status": "ideation",
                    "readiness_score": None,
                    "initiative_type": "acquisition",
                    "origin": "proactive",
                    "created_at": "2026-04-01T10:00:00+07:00",
                }
                for i in range(10)
            ],
            "total": 10,
        }
    )
    out = await handle_list_decisions({}, api_mock, user_corp_sec)
    call = api_mock.list_decisions.await_args
    assert call.kwargs.get("limit") == 20
    assert "10" in out


@pytest.mark.asyncio
async def test_list_decisions_status_filter(api_mock, user_corp_sec):
    api_mock.list_decisions = AsyncMock(return_value={"items": [], "total": 0})
    await handle_list_decisions({"status": "bjr_locked"}, api_mock, user_corp_sec)
    call = api_mock.list_decisions.await_args
    assert call.kwargs.get("status") == "bjr_locked"


@pytest.mark.asyncio
async def test_list_my_decisions_passes_user_email(api_mock, user_corp_sec):
    api_mock.list_decisions = AsyncMock(return_value={"items": [], "total": 0})
    await handle_list_my_decisions({}, api_mock, user_corp_sec)
    call = api_mock.list_decisions.await_args
    assert call.kwargs.get("owner_email") == "corpsec@ancol.test"
