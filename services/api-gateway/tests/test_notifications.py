"""Tests for push notification subscription endpoints."""

from __future__ import annotations


class TestPushSubscription:
    def test_subscribe_stores_subscription(self):
        from api_gateway.routers.notifications import _subscriptions

        _subscriptions.clear()
        from api_gateway.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        sub_data = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/test-123",
            "keys": {"p256dh": "test-key", "auth": "test-auth"},
        }
        response = client.post("/api/notifications/subscribe", json=sub_data)
        assert response.status_code == 200
        assert response.json()["status"] == "subscribed"
        assert len(_subscriptions) == 1

    def test_subscribe_deduplicates_by_endpoint(self):
        from api_gateway.routers.notifications import _subscriptions

        _subscriptions.clear()
        from api_gateway.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        sub_data = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/test-456",
            "keys": {"p256dh": "key", "auth": "auth"},
        }
        client.post("/api/notifications/subscribe", json=sub_data)
        client.post("/api/notifications/subscribe", json=sub_data)
        assert len(_subscriptions) == 1

    def test_unsubscribe_removes_subscription(self):
        from api_gateway.routers.notifications import _subscriptions

        _subscriptions.clear()
        _subscriptions["https://fcm.googleapis.com/test-789"] = {"endpoint": "https://fcm.googleapis.com/test-789", "keys": {}}
        from api_gateway.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post(
            "/api/notifications/unsubscribe",
            json={"endpoint": "https://fcm.googleapis.com/test-789"},
        )
        assert response.status_code == 200
        assert len(_subscriptions) == 0

    def test_unsubscribe_nonexistent_is_ok(self):
        from api_gateway.routers.notifications import _subscriptions

        _subscriptions.clear()
        from api_gateway.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post(
            "/api/notifications/unsubscribe",
            json={"endpoint": "https://nonexistent"},
        )
        assert response.status_code == 200

    def test_list_subscriptions(self):
        from api_gateway.routers.notifications import _subscriptions

        _subscriptions.clear()
        _subscriptions["https://test-1"] = {"endpoint": "https://test-1", "keys": {}}
        _subscriptions["https://test-2"] = {"endpoint": "https://test-2", "keys": {}}
        from api_gateway.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/notifications/subscriptions")
        assert response.status_code == 200
        assert response.json()["total"] == 2
