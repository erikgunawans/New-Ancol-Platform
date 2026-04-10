"""Tests for API Gateway main endpoints."""

from __future__ import annotations

import pytest
from api_gateway.main import app
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
    assert data["service"] == "api-gateway"


@pytest.mark.asyncio
async def test_api_root(client):
    response = await client.get("/api")
    assert response.status_code == 200
    data = response.json()
    assert "endpoints" in data
    assert "documents" in data["endpoints"]
    assert "hitl" in data["endpoints"]
    assert "reports" in data["endpoints"]
    assert "users" in data["endpoints"]
    assert "audit" in data["endpoints"]
    assert "dashboard" in data["endpoints"]
    assert "batch" in data["endpoints"]
    assert "analytics" in data["endpoints"]


@pytest.mark.asyncio
async def test_cors_headers(client):
    response = await client.options(
        "/api",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
