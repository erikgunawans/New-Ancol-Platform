"""Tests for Regulation Monitor service."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from regulation_monitor.main import app


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
    assert data["service"] == "regulation-monitor"
    assert data["monitored_sources"] == 5


@pytest.mark.asyncio
async def test_list_sources(client):
    response = await client.get("/sources")
    assert response.status_code == 200
    data = response.json()
    assert len(data["sources"]) == 5
    source_ids = {s["id"] for s in data["sources"]}
    assert "ojk" in source_ids
    assert "idx" in source_ids
    assert "kemenparekraf" in source_ids
    assert "klhk" in source_ids
    assert "atr_bpn" in source_ids
