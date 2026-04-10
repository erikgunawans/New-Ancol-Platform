"""Tests for Extraction Agent FastAPI endpoints."""

from __future__ import annotations

import base64
import json

import pytest
from extraction_agent.main import app
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "extraction-agent"


@pytest.mark.asyncio
async def test_extract_invalid_payload(client):
    response = await client.post("/extract", json={"bad": "data"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_extract_missing_fields(client):
    payload = _make_pubsub_payload({"document_id": "test-123"})
    response = await client.post("/extract", json=payload)
    assert response.status_code == 400


def _make_pubsub_payload(data: dict) -> dict:
    encoded = base64.b64encode(json.dumps(data).encode()).decode()
    return {
        "message": {
            "data": encoded,
            "message_id": "test-msg-001",
            "publish_time": "2026-04-09T10:00:00Z",
            "attributes": {},
        },
        "subscription": "projects/test/subscriptions/test-sub",
    }
