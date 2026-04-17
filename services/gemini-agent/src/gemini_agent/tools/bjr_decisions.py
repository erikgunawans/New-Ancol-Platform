"""Read-only BJR decision chat tool handlers.

Three tools:
- ``get_decision(decision_id)`` — full decision detail.
- ``list_decisions(status?, limit?)`` — paginated list.
- ``list_my_decisions()`` — decisions owned by the current user.

All output is chat-formatted with moderate PII scrubbing (spec § 6.4):
large IDR values rounded to ``Rp X miliar``; conflicted party names
appear as initials elsewhere (not in this handler).
"""

from __future__ import annotations

import logging

from gemini_agent.api_client import ApiClient
from gemini_agent.formatting_bjr import (
    format_decision_detail,
    format_decision_list,
)

logger = logging.getLogger(__name__)


async def handle_get_decision(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Fetch a single BJR decision by ID."""
    decision_id: str = (params.get("decision_id") or "").strip()
    if not decision_id:
        return "Error: Harap berikan `decision_id` untuk mengambil decision."

    logger.info("Fetching decision: %s", decision_id)
    try:
        decision = await api.get_decision(decision_id)
    except Exception:
        logger.exception("Failed to fetch decision %s", decision_id)
        return f"Gagal mengambil decision `{decision_id}`. Pastikan ID sudah benar."

    return format_decision_detail(decision)


async def handle_list_decisions(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """List BJR decisions with optional status filter."""
    status: str | None = params.get("status")
    limit = int(params.get("limit", 20))

    logger.info("Listing decisions: status=%s limit=%s", status, limit)
    try:
        result = await api.list_decisions(status=status, limit=limit)
    except Exception:
        logger.exception("Failed to list decisions")
        return "Gagal mengambil daftar decision. Coba lagi nanti."

    return format_decision_list(result)


async def handle_list_my_decisions(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """List decisions owned by the current user."""
    owner_email = user.get("email", "")
    limit = int(params.get("limit", 20))

    logger.info("Listing my decisions for %s", owner_email)
    try:
        result = await api.list_decisions(
            owner_email=owner_email,
            limit=limit,
        )
    except Exception:
        logger.exception("Failed to list my decisions for %s", owner_email)
        return "Gagal mengambil decision Anda. Coba lagi nanti."

    return format_decision_list(result, personalized_for=owner_email)
