"""Tests for push notification subscription endpoints."""

from __future__ import annotations

import inspect

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """Create a test client with RBAC overrides for notification endpoints."""
    from api_gateway.main import app
    from api_gateway.routers.notifications import _subscriptions, router

    _subscriptions.clear()

    auth_deps = []
    for route in router.routes:
        if hasattr(route, "endpoint"):
            sig = inspect.signature(route.endpoint)
            for name, param in sig.parameters.items():
                if name == "_auth" and hasattr(param.default, "dependency"):
                    dep_fn = param.default.dependency
                    app.dependency_overrides[dep_fn] = lambda: {
                        "email": "test@ancol.co.id",
                        "id": "dev-test",
                    }
                    auth_deps.append(dep_fn)

    yield TestClient(app)

    for dep_fn in auth_deps:
        app.dependency_overrides.pop(dep_fn, None)


class TestPushSubscription:
    def test_subscribe_stores_subscription(self, client):
        from api_gateway.routers.notifications import _subscriptions

        sub_data = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/test-123",
            "keys": {"p256dh": "test-key", "auth": "test-auth"},
        }
        response = client.post("/api/notifications/subscribe", json=sub_data)
        assert response.status_code == 200
        assert response.json()["status"] == "subscribed"
        assert len(_subscriptions) == 1

    def test_subscribe_deduplicates_by_endpoint(self, client):
        from api_gateway.routers.notifications import _subscriptions

        sub_data = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/test-456",
            "keys": {"p256dh": "key", "auth": "auth"},
        }
        client.post("/api/notifications/subscribe", json=sub_data)
        client.post("/api/notifications/subscribe", json=sub_data)
        assert len(_subscriptions) == 1

    def test_unsubscribe_removes_subscription(self, client):
        from api_gateway.routers.notifications import _subscriptions

        _subscriptions["https://fcm.googleapis.com/test-789"] = {
            "endpoint": "https://fcm.googleapis.com/test-789",
            "keys": {},
        }
        response = client.post(
            "/api/notifications/unsubscribe",
            json={"endpoint": "https://fcm.googleapis.com/test-789"},
        )
        assert response.status_code == 200
        assert len(_subscriptions) == 0

    def test_unsubscribe_nonexistent_is_ok(self, client):
        response = client.post(
            "/api/notifications/unsubscribe",
            json={"endpoint": "https://nonexistent"},
        )
        assert response.status_code == 200

    def test_list_subscriptions(self, client):
        from api_gateway.routers.notifications import _subscriptions

        _subscriptions["https://test-1"] = {"endpoint": "https://test-1", "keys": {}}
        _subscriptions["https://test-2"] = {"endpoint": "https://test-2", "keys": {}}
        response = client.get("/api/notifications/subscriptions")
        assert response.status_code == 200
        assert response.json()["total"] == 2
