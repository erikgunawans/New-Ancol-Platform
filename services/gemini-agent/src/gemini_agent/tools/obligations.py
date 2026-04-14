"""Tool handlers for obligation tracking — list, fulfill."""

from __future__ import annotations

import logging

from gemini_agent.api_client import ApiClient
from gemini_agent.formatting import format_obligations

logger = logging.getLogger(__name__)


async def handle_list_obligations(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """List obligations, optionally filtered by contract or status."""
    contract_id: str | None = params.get("contract_id")
    status: str | None = params.get("status")
    upcoming_only: bool = params.get("upcoming_only", False)

    try:
        if upcoming_only:
            days = params.get("days", 30)
            data = await api.get_upcoming_obligations(days=days)
        else:
            data = await api.list_obligations(
                contract_id=contract_id,
                status=status,
            )
    except Exception:
        logger.exception("Failed to list obligations")
        return "Error: Gagal mengambil daftar kewajiban kontrak."

    return format_obligations(data)


async def handle_fulfill_obligation(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Mark an obligation as fulfilled."""
    from ancol_common.utils import SYSTEM_USER_ID

    obligation_id: str = params.get("obligation_id", "")
    if not obligation_id:
        return "Error: Mohon berikan obligation_id."

    fulfilled_by: str = user.get("id", SYSTEM_USER_ID)
    evidence_uri: str | None = params.get("evidence_gcs_uri")

    try:
        result = await api.fulfill_obligation(
            obligation_id=obligation_id,
            fulfilled_by=fulfilled_by,
            evidence_gcs_uri=evidence_uri,
        )
    except Exception:
        logger.exception("Failed to fulfill obligation %s", obligation_id)
        return f"Error: Gagal menyelesaikan kewajiban `{obligation_id}`."

    return (
        f"Kewajiban `{obligation_id}` berhasil ditandai sebagai **terpenuhi**.\n"
        f"Status: `{result.get('status', 'fulfilled')}`"
    )
