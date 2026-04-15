"""Tests for the upload_document tool handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from gemini_agent.tools.upload import handle_upload_document


def _mock_api():
    api = AsyncMock()
    api.upload_document = AsyncMock(
        return_value={
            "id": "doc-001",
            "filename": "Risalah.pdf",
            "status": "pending",
        }
    )
    return api


@pytest.mark.asyncio
async def test_upload_no_file_returns_error():
    """When no file_bytes provided, returns error message."""
    api = _mock_api()
    user = {
        "id": "u-001",
        "email": "secretary@ancol.co.id",
        "role": "corp_secretary",
    }
    params = {"filename": "Risalah.pdf", "mom_type": "regular"}

    result = await handle_upload_document(params, api, user)
    assert "Tidak ada file" in result


@pytest.mark.asyncio
async def test_upload_timeout_fallback():
    """When polling times out, returns async fallback message."""
    api = _mock_api()
    api.get_document = AsyncMock(return_value={"id": "doc-001", "status": "extracting"})

    user = {
        "id": "u-001",
        "email": "secretary@ancol.co.id",
        "role": "corp_secretary",
    }
    params = {
        "filename": "Risalah.pdf",
        "file_bytes": b"test-content",
        "mom_type": "regular",
    }

    with (
        patch("gemini_agent.tools.upload._POLL_INTERVAL_S", 0.01),
        patch("gemini_agent.tools.upload._MAX_POLL_ITERATIONS", 2),
    ):
        result = await handle_upload_document(params, api, user)

    assert "doc-001" in result
    assert "berjalan" in result or "status" in result.lower()


@pytest.mark.asyncio
async def test_upload_reaches_gate1():
    """When document reaches hitl_gate_1, returns extraction."""
    api = _mock_api()
    api.get_document = AsyncMock(
        side_effect=[
            {"id": "doc-001", "status": "extracting"},
            {"id": "doc-001", "status": "hitl_gate_1"},
        ]
    )
    api.get_review_detail = AsyncMock(
        return_value={
            "document_id": "doc-001",
            "gate": "hitl_gate_1",
            "ai_output": {
                "type": "extraction",
                "data": {
                    "meeting_date": "2026-03-15",
                    "meeting_type": "regular",
                    "attendees": [],
                    "resolutions": [],
                },
            },
        }
    )

    user = {
        "id": "u-001",
        "email": "secretary@ancol.co.id",
        "role": "corp_secretary",
    }
    params = {
        "filename": "Risalah.pdf",
        "file_bytes": b"test-content",
        "mom_type": "regular",
    }

    with (
        patch("gemini_agent.tools.upload._POLL_INTERVAL_S", 0.01),
        patch("gemini_agent.tools.upload._MAX_POLL_ITERATIONS", 5),
    ):
        result = await handle_upload_document(params, api, user)

    assert "Risalah.pdf" in result
    assert "diekstrak" in result or "berhasil" in result
    api.get_review_detail.assert_called_once()
