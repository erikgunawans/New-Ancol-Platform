"""Integration tests for GET /api/documents/{id}/bjr-indicators.

Uses the app.dependency_overrides reflection pattern from test_notifications.py
to bypass IAP + RBAC without touching the DB. Graph client is mocked with
AsyncMock; no Neo4j/Spanner required.
"""

from __future__ import annotations

import inspect
import uuid
from unittest.mock import AsyncMock

import pytest
from ancol_common.rag.models import DocumentIndicator
from ancol_common.schemas.bjr import BJRItemCode
from ancol_common.schemas.decision import DecisionStatus
from fastapi.testclient import TestClient


def _override_all_auth_deps(app, router) -> list:
    """Override every `_auth` Depends on a router to return a dev user.

    Returns the list of overridden dep_fns so the caller can pop them after.
    """
    auth_deps: list = []
    for route in router.routes:
        if not hasattr(route, "endpoint"):
            continue
        sig = inspect.signature(route.endpoint)
        for name, param in sig.parameters.items():
            if name == "_auth" and hasattr(param.default, "dependency"):
                dep_fn = param.default.dependency
                app.dependency_overrides[dep_fn] = lambda: {
                    "email": "test@ancol.co.id",
                    "id": "dev-test",
                }
                auth_deps.append(dep_fn)
    return auth_deps


@pytest.fixture()
def client_with_mocked_graph(monkeypatch):
    """TestClient with a mocked graph client returning one canned indicator."""
    from api_gateway.main import app
    from api_gateway.routers import documents
    from api_gateway.routers.documents import router

    decision_id = uuid.uuid4()
    mock_graph = AsyncMock()
    mock_graph.get_document_indicators = AsyncMock(
        return_value=[
            DocumentIndicator(
                decision_id=decision_id,
                decision_title="Test Decision",
                status=DecisionStatus.DD_IN_PROGRESS.value,
                readiness_score=72.0,
                is_locked=False,
                locked_at=None,
                satisfied_items=[BJRItemCode.D_06_QUORUM],
                missing_items=[BJRItemCode.PD_01_DD],
                origin="proactive",
            )
        ]
    )
    monkeypatch.setattr(documents, "_get_graph_client", lambda: mock_graph)

    auth_deps = _override_all_auth_deps(app, router)

    yield TestClient(app), mock_graph, decision_id

    for dep_fn in auth_deps:
        app.dependency_overrides.pop(dep_fn, None)


def test_bjr_indicators_returns_list_for_authorized_user(client_with_mocked_graph):
    client, mock_graph, decision_id = client_with_mocked_graph
    doc_id = uuid.uuid4()

    response = client.get(f"/api/documents/{doc_id}/bjr-indicators")
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 1
    assert len(body["indicators"]) == 1
    indicator = body["indicators"][0]
    assert indicator["decision_id"] == str(decision_id)
    assert indicator["decision_title"] == "Test Decision"
    assert indicator["status"] == "dd_in_progress"
    assert indicator["readiness_score"] == 72.0
    assert indicator["is_locked"] is False
    assert indicator["origin"] == "proactive"
    assert indicator["satisfied_items"] == ["D-06-QUORUM"]
    assert indicator["missing_items"] == ["PD-01-DD"]

    mock_graph.get_document_indicators.assert_awaited_once()
    called_doc_id = mock_graph.get_document_indicators.await_args.args[0]
    assert called_doc_id == doc_id


def test_bjr_indicators_returns_empty_list_when_graph_backend_off(monkeypatch):
    """When GRAPH_BACKEND=none (factory returns None), endpoint returns empty list."""
    from api_gateway.main import app
    from api_gateway.routers import documents
    from api_gateway.routers.documents import router

    monkeypatch.setattr(documents, "_get_graph_client", lambda: None)
    auth_deps = _override_all_auth_deps(app, router)

    try:
        client = TestClient(app)
        doc_id = uuid.uuid4()
        response = client.get(f"/api/documents/{doc_id}/bjr-indicators")
        assert response.status_code == 200
        body = response.json()
        assert body["indicators"] == []
        assert body["total"] == 0
    finally:
        for dep_fn in auth_deps:
            app.dependency_overrides.pop(dep_fn, None)


def test_bjr_indicators_rejects_unauthenticated():
    """Request without any auth should be rejected by AuthMiddleware."""
    from api_gateway.main import app

    client = TestClient(app)
    doc_id = uuid.uuid4()
    response = client.get(f"/api/documents/{doc_id}/bjr-indicators")
    # AuthMiddleware returns 401; if bypassed, RBAC would return 403.
    assert response.status_code in (401, 403)


def test_bjr_indicators_invalid_uuid_returns_422(client_with_mocked_graph):
    """Non-UUID path param should fail Pydantic validation with 422."""
    client, _, _ = client_with_mocked_graph
    response = client.get("/api/documents/not-a-uuid/bjr-indicators")
    assert response.status_code == 422


def test_bjr_indicators_serializes_locked_decision(monkeypatch):
    """A locked decision should serialize is_locked=true and a non-null locked_at."""
    from datetime import UTC, datetime

    from api_gateway.main import app
    from api_gateway.routers import documents
    from api_gateway.routers.documents import router

    decision_id = uuid.uuid4()
    locked_at = datetime(2026, 4, 17, 12, 0, tzinfo=UTC)
    mock_graph = AsyncMock()
    mock_graph.get_document_indicators = AsyncMock(
        return_value=[
            DocumentIndicator(
                decision_id=decision_id,
                decision_title="Locked Decision",
                status="bjr_locked",
                readiness_score=92.0,
                is_locked=True,
                locked_at=locked_at,
                satisfied_items=[BJRItemCode.D_06_QUORUM, BJRItemCode.PD_01_DD],
                missing_items=[],
                origin="proactive",
            )
        ]
    )
    monkeypatch.setattr(documents, "_get_graph_client", lambda: mock_graph)
    auth_deps = _override_all_auth_deps(app, router)

    try:
        client = TestClient(app)
        doc_id = uuid.uuid4()
        response = client.get(f"/api/documents/{doc_id}/bjr-indicators")
        assert response.status_code == 200

        body = response.json()
        assert body["total"] == 1
        assert len(body["indicators"]) == 1
        ind = body["indicators"][0]
        assert ind["is_locked"] is True
        assert ind["locked_at"] is not None
        assert ind["status"] == "bjr_locked"
        assert sorted(ind["satisfied_items"]) == ["D-06-QUORUM", "PD-01-DD"]
        assert ind["missing_items"] == []
    finally:
        for dep_fn in auth_deps:
            app.dependency_overrides.pop(dep_fn, None)


def test_bjr_indicators_swallows_graph_client_error(monkeypatch):
    """If the graph client raises, the endpoint degrades to empty list instead of 500."""
    from api_gateway.main import app
    from api_gateway.routers import documents
    from api_gateway.routers.documents import router

    failing_graph = AsyncMock()
    failing_graph.get_document_indicators = AsyncMock(
        side_effect=ConnectionError("bolt unreachable"),
    )
    monkeypatch.setattr(documents, "_get_graph_client", lambda: failing_graph)
    auth_deps = _override_all_auth_deps(app, router)

    try:
        client = TestClient(app)
        response = client.get(f"/api/documents/{uuid.uuid4()}/bjr-indicators")
        assert response.status_code == 200
        body = response.json()
        assert body["indicators"] == []
        assert body["total"] == 0
    finally:
        for dep_fn in auth_deps:
            app.dependency_overrides.pop(dep_fn, None)


def test_bjr_indicators_swallows_not_implemented(monkeypatch):
    """Spanner stub raises NotImplementedError; endpoint must not bubble as 500."""
    from api_gateway.main import app
    from api_gateway.routers import documents
    from api_gateway.routers.documents import router

    stub_graph = AsyncMock()
    stub_graph.get_document_indicators = AsyncMock(
        side_effect=NotImplementedError("Spanner BJR backend not implemented"),
    )
    monkeypatch.setattr(documents, "_get_graph_client", lambda: stub_graph)
    auth_deps = _override_all_auth_deps(app, router)

    try:
        client = TestClient(app)
        response = client.get(f"/api/documents/{uuid.uuid4()}/bjr-indicators")
        assert response.status_code == 200
        body = response.json()
        assert body["indicators"] == []
        assert body["total"] == 0
    finally:
        for dep_fn in auth_deps:
            app.dependency_overrides.pop(dep_fn, None)


def test_get_graph_client_swallows_instantiation_failure(monkeypatch):
    """Backend client ctor failure (missing deps, bad creds) returns None, not 500."""
    from api_gateway.routers import documents

    monkeypatch.setenv("GRAPH_BACKEND", "neo4j")
    monkeypatch.setattr(documents, "_graph_client_singleton", None)

    def _raise(*args, **kwargs):
        raise RuntimeError("neo4j driver not installed")

    monkeypatch.setattr(
        "ancol_common.rag.neo4j_graph.Neo4jGraphClient",
        _raise,
    )

    assert documents._get_graph_client() is None
