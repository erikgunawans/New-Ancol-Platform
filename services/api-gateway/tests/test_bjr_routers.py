"""Tests for BJR router registration and endpoint exposure."""

from __future__ import annotations

import pytest


class TestBJRRouterRegistration:
    """Verify BJR routers are mounted at the expected prefixes."""

    @pytest.fixture
    def app(self):
        from api_gateway.main import app

        return app

    def test_rkab_router_mounted(self, app):
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/api/rkab" in paths
        assert "/api/rkab/{rkab_id}" in paths

    def test_rkab_match_endpoint(self, app):
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/api/rkab/match" in paths

    def test_rjpp_router_mounted(self, app):
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/api/rjpp" in paths
        assert "/api/rjpp/{rjpp_id}" in paths

    def test_all_artifact_types_mounted(self, app):
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/api/artifacts/dd" in paths
        assert "/api/artifacts/fs" in paths
        assert "/api/artifacts/spi" in paths
        assert "/api/artifacts/audit-committee" in paths
        assert "/api/artifacts/disclosures" in paths
        assert "/api/artifacts/organ-approvals" in paths

    def test_dd_review_subresource(self, app):
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/api/artifacts/dd/{dd_id}/review" in paths

    def test_fs_review_subresource(self, app):
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/api/artifacts/fs/{fs_id}/review" in paths


class TestBJRApiRoot:
    """The /api root descriptor should list all BJR endpoints."""

    @pytest.fixture
    def client(self):
        from api_gateway.main import app
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_api_root_lists_rkab(self, client):
        response = await client.get("/api")
        data = response.json()
        assert "rkab" in data["endpoints"]
        assert data["endpoints"]["rkab"] == "/api/rkab"

    @pytest.mark.asyncio
    async def test_api_root_lists_rjpp(self, client):
        response = await client.get("/api")
        data = response.json()
        assert "rjpp" in data["endpoints"]

    @pytest.mark.asyncio
    async def test_api_root_lists_artifacts(self, client):
        response = await client.get("/api")
        data = response.json()
        assert "artifacts" in data["endpoints"]

    @pytest.mark.asyncio
    async def test_health_still_works(self, client):
        """Adding BJR routers shouldn't break the health endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestBJREndpointCount:
    """Quantitative sanity check on the BJR endpoint surface."""

    @pytest.fixture
    def app(self):
        from api_gateway.main import app

        return app

    def test_bjr_endpoint_count(self, app):
        """Phase 6.2 adds 15 BJR routes (rkab 5 + rjpp 4 + artifacts 13 - dupes = 15)."""
        bjr_paths = {
            getattr(r, "path", None)
            for r in app.routes
            if getattr(r, "path", None)
            and any(p in r.path for p in ("/api/rkab", "/api/rjpp", "/api/artifacts"))
        }
        # Exact count can drift as we add sub-resources; at minimum we expect 15
        assert len(bjr_paths) >= 15, f"Expected ≥15 BJR paths, got {len(bjr_paths)}: {bjr_paths}"
