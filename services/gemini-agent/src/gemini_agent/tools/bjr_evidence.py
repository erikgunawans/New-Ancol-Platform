"""BJR evidence chat tool handlers (read-only).

Two tools:

- ``show_document_indicators(doc_id, doc_type)`` — proactive indicator on
  every document mention (see spec § 5.2). Silent when the doc has no
  BJR context; silent on missing args; silent on API failure. Noise is
  worse than no-op here because the LLM calls this speculatively.
- ``show_decision_evidence(decision_id)`` — inverse: list all evidence
  linked to a decision, grouped by evidence type. Deliberate call, so
  errors surface as friendly Indonesian strings.
"""

from __future__ import annotations

import logging

from gemini_agent.api_client import ApiClient
from gemini_agent.formatting_bjr import (
    format_decision_evidence,
    format_document_indicators,
)

logger = logging.getLogger(__name__)


async def handle_show_document_indicators(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Proactive BJR indicator for a document.

    Returns empty string when the doc_id is missing or no decisions
    reference the document. This is intentional — the LLM calls this
    speculatively whenever it mentions a doc; a silent response means
    "no BJR context here" and the conversation continues unaltered.
    """
    doc_id: str = (params.get("doc_id") or "").strip()
    if not doc_id:
        return ""

    try:
        payload = await api.get_bjr_indicators(doc_id)
    except Exception:
        logger.exception("get_bjr_indicators failed for doc %s", doc_id)
        return ""

    indicators = payload.get("indicators", [])
    return format_document_indicators(indicators)


async def handle_show_decision_evidence(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """List all evidence linked to a decision, grouped by evidence type."""
    decision_id: str = (params.get("decision_id") or "").strip()
    if not decision_id:
        return "Error: Harap berikan `decision_id`."

    try:
        payload = await api.get_decision_evidence(decision_id)
    except Exception:
        logger.exception("get_decision_evidence failed for %s", decision_id)
        return f"Gagal mengambil evidence untuk `{decision_id}`."

    return format_decision_evidence(payload)
