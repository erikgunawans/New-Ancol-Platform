"""Unit tests for bjr_evidence chat tool handlers."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from gemini_agent.tools.bjr_evidence import (
    handle_show_decision_evidence,
    handle_show_document_indicators,
)


@pytest.fixture
def user() -> dict:
    return {"email": "x@ancol.test", "role": "business_dev"}


@pytest.fixture
def api_mock() -> AsyncMock:
    return AsyncMock()


@pytest.mark.asyncio
async def test_show_document_indicators_renders_one_decision(api_mock, user):
    doc_id = uuid.uuid4()
    api_mock.get_bjr_indicators = AsyncMock(
        return_value={
            "indicators": [
                {
                    "decision_id": str(uuid.uuid4()),
                    "decision_title": "Divestasi Hotel Jaya",
                    "status": "bjr_locked",
                    "readiness_score": 94.0,
                    "is_locked": True,
                    "locked_at": "2026-04-01T09:00:00+07:00",
                    "satisfied_items": ["D-06-QUORUM", "D-07-SIGNED"],
                    "missing_items": [],
                    "origin": "proactive",
                }
            ]
        }
    )
    out = await handle_show_document_indicators(
        {"doc_id": str(doc_id), "doc_type": "mom"}, api_mock, user
    )
    assert "Divestasi Hotel Jaya" in out
    assert "🔒" in out
    assert "D-06-QUORUM" in out or "✓" in out


@pytest.mark.asyncio
async def test_show_document_indicators_silently_omits_when_empty(api_mock, user):
    """Spec § 5.2: empty indicator list is silent (empty string), never noisy."""
    api_mock.get_bjr_indicators = AsyncMock(return_value={"indicators": []})
    out = await handle_show_document_indicators(
        {"doc_id": str(uuid.uuid4()), "doc_type": "mom"}, api_mock, user
    )
    assert out == ""


@pytest.mark.asyncio
async def test_show_document_indicators_handles_multiple_decisions(api_mock, user):
    api_mock.get_bjr_indicators = AsyncMock(
        return_value={
            "indicators": [
                {
                    "decision_id": str(uuid.uuid4()),
                    "decision_title": "Decision 1",
                    "status": "bjr_locked",
                    "readiness_score": 95.0,
                    "is_locked": True,
                    "locked_at": "2026-04-01T09:00:00+07:00",
                    "satisfied_items": ["D-06-QUORUM"],
                    "missing_items": [],
                    "origin": "proactive",
                },
                {
                    "decision_id": str(uuid.uuid4()),
                    "decision_title": "Decision 2",
                    "status": "dd_in_progress",
                    "readiness_score": 72.0,
                    "is_locked": False,
                    "locked_at": None,
                    "satisfied_items": ["D-06-QUORUM"],
                    "missing_items": ["PD-01-DD", "PD-05-COI"],
                    "origin": "proactive",
                },
            ]
        }
    )
    out = await handle_show_document_indicators(
        {"doc_id": str(uuid.uuid4()), "doc_type": "mom"}, api_mock, user
    )
    assert "Decision 1" in out
    assert "Decision 2" in out
    assert "🔒" in out
    assert "🟡" in out


@pytest.mark.asyncio
async def test_show_document_indicators_missing_doc_id_returns_empty(api_mock, user):
    """Proactive tool: silent when arguments are invalid — Gemini may still
    attempt the call when it misidentifies a doc reference."""
    out = await handle_show_document_indicators({"doc_type": "mom"}, api_mock, user)
    assert out == ""
    api_mock.get_bjr_indicators.assert_not_called()


@pytest.mark.asyncio
async def test_show_decision_evidence_renders_by_phase(api_mock, user):
    did = uuid.uuid4()
    api_mock.get_decision_evidence = AsyncMock(
        return_value={
            "evidence": [
                {
                    "evidence_id": str(uuid.uuid4()),
                    "evidence_type": "dd_report",
                    "title": "DD Report #42",
                    "satisfies_items": ["PD-01-DD"],
                },
                {
                    "evidence_id": str(uuid.uuid4()),
                    "evidence_type": "mom",
                    "title": "MoM BOD #5/2026",
                    "satisfies_items": ["D-06-QUORUM", "D-07-SIGNED"],
                },
            ]
        }
    )
    out = await handle_show_decision_evidence({"decision_id": str(did)}, api_mock, user)
    assert "DD Report #42" in out
    assert "MoM BOD #5/2026" in out
    assert "PD-01-DD" in out


@pytest.mark.asyncio
async def test_show_decision_evidence_missing_id_returns_error(api_mock, user):
    out = await handle_show_decision_evidence({}, api_mock, user)
    assert "decision_id" in out.lower()
