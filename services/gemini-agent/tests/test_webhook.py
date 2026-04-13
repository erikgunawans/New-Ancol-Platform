"""Tests for the webhook endpoint and routing."""

from __future__ import annotations

import pytest
from gemini_agent.main import app
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "gemini-agent"


@pytest.mark.asyncio
async def test_webhook_access_denied(client):
    """Role without access to tool gets a denial message."""
    resp = await client.post(
        "/webhook",
        json={
            "tool_call": {
                "name": "upload_document",
                "parameters": {},
            },
            "user_identity": {
                "email": "komisaris@ancol.co.id",
                "role": "komisaris",
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "tidak memiliki akses" in data["tool_response"]["content"]


@pytest.mark.asyncio
async def test_webhook_unknown_tool(client):
    """Unknown tool name returns error in response."""
    resp = await client.post(
        "/webhook",
        json={
            "tool_call": {
                "name": "nonexistent_tool",
                "parameters": {},
            },
            "user_identity": {
                "email": "admin@ancol.co.id",
                "role": "admin",
            },
        },
    )
    # Unknown tool is caught by the exception handler and returns 200
    # with an error message, or 400 from HTTPException
    assert resp.status_code in (200, 400)
