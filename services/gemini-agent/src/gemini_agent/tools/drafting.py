"""Tool handler for contract draft generation."""

from __future__ import annotations

import logging

from gemini_agent.api_client import ApiClient
from gemini_agent.formatting import format_draft_output

logger = logging.getLogger(__name__)


async def handle_generate_draft(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Generate a contract draft from template and parameters."""
    contract_type: str = params.get("contract_type", "vendor")
    parties: list = params.get("parties", [])
    key_terms: dict = params.get("key_terms", {})

    body = {
        "contract_type": contract_type,
        "parties": parties,
        "key_terms": key_terms,
    }

    try:
        result = await api.generate_draft(body)
    except Exception:
        logger.exception("Failed to generate draft")
        return "Error: Gagal membuat draft kontrak."

    return format_draft_output(result)
