"""Tests for Batch Engine main endpoints."""

from __future__ import annotations

import pytest
from batch_engine.main import app
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
    assert data["service"] == "batch-engine"
    assert "running_jobs" in data
