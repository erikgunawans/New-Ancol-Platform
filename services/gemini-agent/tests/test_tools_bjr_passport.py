"""Unit tests for bjr_passport chat tool handler."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from gemini_agent.tools.bjr_passport import handle_get_passport_url


@pytest.fixture
def user() -> dict:
    return {"email": "direksi@ancol.test", "role": "direksi"}


@pytest.fixture
def api_mock() -> AsyncMock:
    return AsyncMock()


@pytest.mark.asyncio
async def test_get_passport_url_returns_signed_link(api_mock, user):
    did = uuid.uuid4()
    api_mock.get_passport_url = AsyncMock(
        return_value={
            "signed_url": "https://storage.googleapis.com/bucket/passport-x.pdf?sig=abc",
            "expires_at": "2026-04-18T09:00:00+07:00",
        }
    )
    out = await handle_get_passport_url({"decision_id": str(did)}, api_mock, user)
    assert "storage.googleapis.com" in out
    assert "expires" in out.lower() or "valid" in out.lower() or "berlaku" in out.lower()


@pytest.mark.asyncio
async def test_get_passport_url_missing_id(api_mock, user):
    out = await handle_get_passport_url({}, api_mock, user)
    assert "decision_id" in out.lower()
    api_mock.get_passport_url.assert_not_called()


@pytest.mark.asyncio
async def test_get_passport_url_decision_not_locked(api_mock, user):
    """API returns 409 Conflict when decision is not locked yet."""
    from httpx import HTTPStatusError, Request

    response = MagicMock()
    response.status_code = 409
    response.text = "decision not locked"
    api_mock.get_passport_url = AsyncMock(
        side_effect=HTTPStatusError(
            "409 Conflict",
            request=Request("GET", "http://test/api/decisions/x/passport/signed-url"),
            response=response,
        )
    )
    out = await handle_get_passport_url({"decision_id": str(uuid.uuid4())}, api_mock, user)
    lower = out.lower()
    assert "belum" in lower or "not locked" in lower or "tidak" in lower


@pytest.mark.asyncio
async def test_get_passport_url_generic_error(api_mock, user):
    api_mock.get_passport_url = AsyncMock(side_effect=Exception("boom"))
    out = await handle_get_passport_url({"decision_id": str(uuid.uuid4())}, api_mock, user)
    lower = out.lower()
    assert "gagal" in lower or "error" in lower
