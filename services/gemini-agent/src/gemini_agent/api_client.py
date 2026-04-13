"""HTTP client wrapper for the Ancol MoM Compliance API Gateway.

Provides typed async methods for every API Gateway endpoint, with OIDC
service-to-service auth in production and retry with exponential backoff.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0


class ApiClient:
    """Async HTTP client for the Ancol API Gateway."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = (
            base_url or os.getenv("API_GATEWAY_URL", "http://localhost:8080")
        ).rstrip("/")
        self._timeout = timeout
        self._environment = os.getenv("ENVIRONMENT", "dev")
        self._client: httpx.AsyncClient | None = None

    # -- lifecycle --

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # -- auth --

    async def _auth_headers(self) -> dict[str, str]:
        """Return OIDC bearer token header in production, empty in dev."""
        if self._environment == "dev":
            return {}
        try:
            import google.auth.transport.requests
            from google.oauth2 import id_token

            request = google.auth.transport.requests.Request()
            token = id_token.fetch_id_token(request, self._base_url)
            return {"Authorization": f"Bearer {token}"}
        except Exception:
            logger.warning("OIDC token acquisition failed, proceeding without auth")
            return {}

    # -- retry wrapper --

    async def _request(
        self,
        method: str,
        path: str,
        *,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> dict:
        """Send an HTTP request with retry + exponential backoff.

        Returns parsed JSON as a dict.
        """
        client = await self._get_client()
        headers = await self._auth_headers()
        if "headers" in kwargs:
            kwargs["headers"] = {**headers, **kwargs["headers"]}
        else:
            kwargs["headers"] = headers

        if timeout is not None:
            kwargs["timeout"] = timeout

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = await client.request(method, path, **kwargs)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_exc = exc
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                    # Client errors are not retryable
                    logger.error("API %s %s returned %s", method, path, exc.response.status_code)
                    raise
                wait = _BACKOFF_BASE * (2**attempt)
                logger.warning(
                    "API %s %s attempt %d failed (%s), retrying in %.1fs",
                    method,
                    path,
                    attempt + 1,
                    exc,
                    wait,
                )
                await asyncio.sleep(wait)

        raise RuntimeError(
            f"API {method} {path} failed after {_MAX_RETRIES} retries"
        ) from last_exc

    # -- Document endpoints --

    async def upload_document(
        self,
        file_bytes: bytes,
        filename: str,
        mom_type: str = "regular",
        meeting_date: str | None = None,
        is_confidential: bool = False,
        uploaded_by: str = "a0000000-0000-0000-0000-000000000001",
    ) -> dict:
        """POST /api/documents/upload — multipart file upload."""
        data: dict[str, Any] = {
            "mom_type": mom_type,
            "is_confidential": str(is_confidential).lower(),
            "uploaded_by": uploaded_by,
        }
        if meeting_date:
            data["meeting_date"] = meeting_date

        files = {"file": (filename, file_bytes, "application/octet-stream")}
        return await self._request(
            "POST",
            "/api/documents/upload",
            data=data,
            files=files,
            timeout=60.0,
        )

    async def get_document(self, document_id: str) -> dict:
        """GET /api/documents/{id}."""
        return await self._request("GET", f"/api/documents/{document_id}")

    async def list_documents(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """GET /api/documents — list with optional status filter."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        return await self._request("GET", "/api/documents", params=params)

    # -- HITL endpoints --

    async def get_hitl_queue(
        self,
        gate: str | None = None,
        limit: int = 50,
    ) -> dict:
        """GET /api/hitl/queue."""
        params: dict[str, Any] = {"limit": limit}
        if gate:
            params["gate"] = gate
        return await self._request("GET", "/api/hitl/queue", params=params)

    async def get_review_detail(self, document_id: str) -> dict:
        """GET /api/hitl/review/{id}."""
        return await self._request("GET", f"/api/hitl/review/{document_id}")

    async def submit_decision(
        self,
        document_id: str,
        decision: str,
        reviewer_id: str,
        reviewer_role: str,
        modified_data: dict | None = None,
        modification_summary: str | None = None,
        notes: str | None = None,
    ) -> dict:
        """POST /api/hitl/decide/{id}."""
        body: dict[str, Any] = {
            "decision": decision,
            "reviewer_id": reviewer_id,
            "reviewer_role": reviewer_role,
        }
        if modified_data is not None:
            body["modified_data"] = modified_data
        if modification_summary is not None:
            body["modification_summary"] = modification_summary
        if notes is not None:
            body["notes"] = notes
        return await self._request("POST", f"/api/hitl/decide/{document_id}", json=body)

    # -- Report endpoints --

    async def get_report(self, report_id: str) -> dict:
        """GET /api/reports/{id}."""
        return await self._request("GET", f"/api/reports/{report_id}")

    # -- Dashboard endpoints --

    async def get_dashboard_stats(self) -> dict:
        """GET /api/dashboard/stats."""
        return await self._request("GET", "/api/dashboard/stats")

    async def get_dashboard_trends(self, months: int = 6) -> dict:
        """GET /api/dashboard/stats/trends."""
        return await self._request(
            "GET", "/api/dashboard/stats/trends", params={"months": months}
        )
