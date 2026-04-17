"""BJR readiness-score + checklist chat tool handlers (read-only)."""

from __future__ import annotations

import logging

from gemini_agent.api_client import ApiClient
from gemini_agent.formatting_bjr import (
    format_checklist_summary,
    format_readiness_card,
)

logger = logging.getLogger(__name__)


async def handle_get_readiness(params: dict, api: ApiClient, user: dict) -> str:
    """Fetch dual-regime BJR readiness for a decision."""
    decision_id: str = (params.get("decision_id") or "").strip()
    if not decision_id:
        return "Error: Harap berikan `decision_id` untuk melihat readiness score."

    try:
        readiness = await api.get_readiness(decision_id)
    except Exception:
        logger.exception("get_readiness failed for %s", decision_id)
        return f"Gagal mengambil readiness untuk `{decision_id}`."

    return format_readiness_card(readiness)


async def handle_get_checklist(params: dict, api: ApiClient, user: dict) -> str:
    """Fetch the 16-item BJR checklist for a decision."""
    decision_id: str = (params.get("decision_id") or "").strip()
    if not decision_id:
        return "Error: Harap berikan `decision_id` untuk melihat checklist."

    try:
        checklist = await api.get_checklist(decision_id)
    except Exception:
        logger.exception("get_checklist failed for %s", decision_id)
        return f"Gagal mengambil checklist untuk `{decision_id}`."

    return format_checklist_summary(checklist)
