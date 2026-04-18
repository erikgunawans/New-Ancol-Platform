"""Unit tests for bjr_readiness chat tool handlers."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from gemini_agent.tools.bjr_readiness import (
    handle_get_checklist,
    handle_get_readiness,
)


@pytest.fixture
def user_corp_sec() -> dict:
    return {"email": "corpsec@ancol.test", "role": "corp_secretary"}


@pytest.fixture
def api_mock() -> AsyncMock:
    return AsyncMock()


@pytest.mark.asyncio
async def test_get_readiness_shows_dual_regime(api_mock, user_corp_sec):
    did = uuid.uuid4()
    api_mock.get_readiness = AsyncMock(
        return_value={
            "decision_id": str(did),
            "readiness_score": 72.0,
            "corporate_score": 72.0,
            "regional_score": 88.0,
            "gate_5_unlockable": False,
            "critical_items_flagged": ["PD-03-RKAB"],
            "missing_items": ["PD-01-DD", "PD-05-COI"],
            "satisfied_items": [
                "PD-02-FS",
                "PD-04-RJPP",
                "D-06-QUORUM",
                "D-07-SIGNED",
            ],
        }
    )
    out = await handle_get_readiness({"decision_id": str(did)}, api_mock, user_corp_sec)
    assert "72" in out
    assert "88" in out
    assert "PD-03-RKAB" in out


@pytest.mark.asyncio
async def test_get_readiness_unlocked_shows_gate5_ready(api_mock, user_corp_sec):
    did = uuid.uuid4()
    api_mock.get_readiness = AsyncMock(
        return_value={
            "decision_id": str(did),
            "readiness_score": 92.0,
            "corporate_score": 92.0,
            "regional_score": 95.0,
            "gate_5_unlockable": True,
            "critical_items_flagged": [],
            "missing_items": [],
            "satisfied_items": [],
        }
    )
    out = await handle_get_readiness({"decision_id": str(did)}, api_mock, user_corp_sec)
    assert "Gate 5" in out
    assert "ready" in out.lower() or "siap" in out.lower()


@pytest.mark.asyncio
async def test_get_readiness_missing_id(api_mock, user_corp_sec):
    out = await handle_get_readiness({}, api_mock, user_corp_sec)
    assert "decision_id" in out.lower()


@pytest.mark.asyncio
async def test_get_checklist_groups_by_phase(api_mock, user_corp_sec):
    did = uuid.uuid4()
    api_mock.get_checklist = AsyncMock(
        return_value={
            "items": [
                {"code": "PD-01-DD", "status": "not_started", "phase": "pre-decision"},
                {"code": "PD-02-FS", "status": "satisfied", "phase": "pre-decision"},
                {"code": "PD-03-RKAB", "status": "flagged", "phase": "pre-decision"},
                {"code": "D-06-QUORUM", "status": "satisfied", "phase": "decision"},
                {"code": "POST-13-MONITOR", "status": "not_started", "phase": "post-decision"},
            ],
        }
    )
    out = await handle_get_checklist({"decision_id": str(did)}, api_mock, user_corp_sec)
    lower = out.lower()
    assert "pre-decision" in lower
    assert "decision" in lower
    assert "post-decision" in lower


@pytest.mark.asyncio
async def test_get_checklist_flags_critical_items(api_mock, user_corp_sec):
    did = uuid.uuid4()
    api_mock.get_checklist = AsyncMock(
        return_value={
            "items": [
                {"code": "PD-03-RKAB", "status": "flagged", "phase": "pre-decision"},
                {"code": "PD-05-COI", "status": "not_started", "phase": "pre-decision"},
            ],
        }
    )
    out = await handle_get_checklist({"decision_id": str(did)}, api_mock, user_corp_sec)
    assert "CRITICAL" in out or "⚠" in out or "🚨" in out
