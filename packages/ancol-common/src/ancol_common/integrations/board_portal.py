"""Board Portal integration adapter.

Integrates with the corporate board portal to:
- Pull meeting schedules and agendas
- Push compliance reports for board review
- Sync document status updates
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from ancol_common.config import get_settings

from .base import IntegrationAdapter

logger = logging.getLogger(__name__)


class BoardPortalAdapter(IntegrationAdapter):
    """Board portal integration via REST API."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.board_portal_url
        self.api_key = settings.board_portal_api_key

    async def health_check(self) -> dict:
        if not self.base_url:
            return {"status": "not_configured", "service": "board_portal"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/health",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return {
                    "status": "ok" if response.status_code == 200 else "error",
                    "service": "board_portal",
                    "status_code": response.status_code,
                }
        except Exception as e:
            return {"status": "error", "service": "board_portal", "error": str(e)}

    async def sync(self, since: datetime | None = None) -> dict:
        """Pull upcoming meeting schedules from the board portal."""
        if not self.base_url:
            return {"synced": 0, "status": "not_configured"}

        try:
            params = {}
            if since:
                params["since"] = since.isoformat()

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/meetings",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    params=params,
                )
                response.raise_for_status()
                meetings = response.json()

            logger.info("Synced %d meetings from board portal", len(meetings))
            return {"synced": len(meetings), "meetings": meetings}
        except Exception as e:
            logger.exception("Board portal sync failed")
            return {"synced": 0, "error": str(e)}

    async def push(self, data: Any) -> dict:
        """Push a compliance report to the board portal for review."""
        if not self.base_url:
            return {"pushed": False, "status": "not_configured"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/compliance-reports",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=data,
                )
                response.raise_for_status()

            logger.info("Pushed compliance report to board portal")
            return {"pushed": True, "response": response.json()}
        except Exception as e:
            logger.exception("Board portal push failed")
            return {"pushed": False, "error": str(e)}
