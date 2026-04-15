"""Tests for HITL review tool handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from gemini_agent.tools.review import (
    handle_get_review_detail,
    handle_review_gate,
    handle_submit_decision,
)


@pytest.mark.asyncio
async def test_review_gate_returns_queue():
    api = AsyncMock()
    api.get_hitl_queue = AsyncMock(
        return_value={
            "items": [
                {
                    "document_id": "doc-001",
                    "filename": "Risalah.pdf",
                    "gate": "hitl_gate_2",
                    "status": "hitl_gate_2",
                }
            ],
            "total": 1,
        }
    )

    user = {"email": "legal@ancol.co.id", "role": "legal_compliance"}
    result = await handle_review_gate({"gate": "gate_2"}, api, user)
    assert "Risalah.pdf" in result or "doc-001" in result


@pytest.mark.asyncio
async def test_get_review_detail_formats_output():
    api = AsyncMock()
    api.get_review_detail = AsyncMock(
        return_value={
            "document_id": "doc-001",
            "gate": "hitl_gate_1",
            "ai_output": {
                "type": "extraction",
                "data": {"meeting_date": "2026-03-15"},
            },
        }
    )

    user = {"email": "auditor@ancol.co.id", "role": "internal_auditor"}
    result = await handle_get_review_detail({"document_id": "doc-001"}, api, user)
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_submit_decision_approved():
    api = AsyncMock()
    api.submit_decision = AsyncMock(
        return_value={
            "decision_id": "dec-001",
            "document_id": "doc-001",
            "gate": "hitl_gate_1",
            "decision": "approved",
            "next_status": "researching",
        }
    )

    user = {
        "id": "u-001",
        "email": "auditor@ancol.co.id",
        "role": "internal_auditor",
    }
    params = {
        "document_id": "doc-001",
        "decision": "approved",
    }
    result = await handle_submit_decision(params, api, user)
    assert "Disetujui" in result


@pytest.mark.asyncio
async def test_submit_decision_rejected():
    api = AsyncMock()
    api.submit_decision = AsyncMock(
        return_value={
            "decision_id": "dec-002",
            "document_id": "doc-001",
            "gate": "hitl_gate_3",
            "decision": "rejected",
            "next_status": "rejected",
        }
    )

    user = {
        "id": "u-002",
        "email": "auditor@ancol.co.id",
        "role": "internal_auditor",
    }
    params = {
        "document_id": "doc-001",
        "decision": "rejected",
        "notes": "Data tidak akurat",
    }
    result = await handle_submit_decision(params, api, user)
    assert "Ditolak" in result
