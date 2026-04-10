"""Tests for document-processor FastAPI endpoints."""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, patch

import pytest
from document_processor.main import app
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
    assert data["service"] == "document-processor"


@pytest.mark.asyncio
async def test_process_invalid_payload(client):
    response = await client.post("/process", json={"bad": "data"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_process_missing_bucket(client):
    payload = _make_pubsub_payload({"name": "test.pdf"})
    response = await client.post("/process", json=payload)
    assert response.status_code == 400


@pytest.mark.asyncio
@patch("document_processor.processor.process_document", new_callable=AsyncMock)
async def test_process_valid_payload(mock_process, client):
    mock_process.return_value = {
        "document_id": "test-id",
        "processed_uri": "gs://bucket/output.json",
        "page_count": 3,
        "overall_confidence": 0.95,
        "processing_time_ms": 1200,
    }

    payload = _make_pubsub_payload(
        {
            "bucket": "ancol-mom-raw",
            "name": "uploads/test-mom.pdf",
            "contentType": "application/pdf",
            "size": "50000",
            "metadata": {"document_id": "test-id", "uploaded_by": "user-1"},
        }
    )
    response = await client.post("/process", json=payload)
    assert response.status_code == 200

    mock_process.assert_called_once_with(
        bucket="ancol-mom-raw",
        object_name="uploads/test-mom.pdf",
        document_id="test-id",
        content_type="application/pdf",
        file_size=50000,
    )


def _make_pubsub_payload(data: dict) -> dict:
    """Build a Pub/Sub push message envelope."""
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
