"""ERP integration adapter.

Integrates with the corporate ERP system to:
- Pull financial data for cross-checking MoM resolutions
- Verify related-party transaction amounts
- Cross-reference performance data cited in MoMs
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from ancol_common.config import get_settings

from .base import IntegrationAdapter

logger = logging.getLogger(__name__)


class ERPAdapter(IntegrationAdapter):
    """ERP integration via REST API."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.erp_api_url
        self.api_key = settings.erp_api_key

    async def health_check(self) -> dict:
        if not self.base_url:
            return {"status": "not_configured", "service": "erp"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/health",
                    headers={"X-API-Key": self.api_key},
                )
                return {
                    "status": "ok" if response.status_code == 200 else "error",
                    "service": "erp",
                    "status_code": response.status_code,
                }
        except Exception as e:
            return {"status": "error", "service": "erp", "error": str(e)}

    async def sync(self, since: datetime | None = None) -> dict:
        """Pull financial data for cross-checking."""
        if not self.base_url:
            return {"synced": 0, "status": "not_configured"}

        try:
            params = {}
            if since:
                params["since"] = since.isoformat()

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/financial-data",
                    headers={"X-API-Key": self.api_key},
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

            logger.info("Synced financial data from ERP")
            return {"synced": len(data.get("records", [])), "data": data}
        except Exception as e:
            logger.exception("ERP sync failed")
            return {"synced": 0, "error": str(e)}

    async def push(self, data: Any) -> dict:
        """Push compliance findings to ERP for audit tracking."""
        if not self.base_url:
            return {"pushed": False, "status": "not_configured"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/compliance-findings",
                    headers={"X-API-Key": self.api_key},
                    json=data,
                )
                response.raise_for_status()

            logger.info("Pushed compliance findings to ERP")
            return {"pushed": True}
        except Exception as e:
            logger.exception("ERP push failed")
            return {"pushed": False, "error": str(e)}

    async def get_rpt_transactions(
        self, entity_name: str, date_from: datetime, date_to: datetime
    ) -> list[dict]:
        """Fetch related-party transactions for cross-checking.

        Used by the Comparison Agent to verify RPT amounts cited in MoMs.
        """
        if not self.base_url:
            return []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/transactions/related-party",
                    headers={"X-API-Key": self.api_key},
                    params={
                        "entity": entity_name,
                        "from": date_from.isoformat(),
                        "to": date_to.isoformat(),
                    },
                )
                response.raise_for_status()
                return response.json().get("transactions", [])
        except Exception:
            logger.exception("Failed to fetch RPT transactions from ERP")
            return []
