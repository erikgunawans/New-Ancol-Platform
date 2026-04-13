"""Tool handlers — HITL review queue, detail, and decision submission."""

from __future__ import annotations

import logging
from collections.abc import Callable

from gemini_agent.api_client import ApiClient
from gemini_agent.formatting import (
    format_compliance_findings,
    format_extraction,
    format_hitl_queue,
    format_regulatory_mapping,
    format_scorecard,
)

logger = logging.getLogger(__name__)

# Gate → formatter mapping
_GATE_FORMATTERS: dict[str, Callable[[dict], str]] = {
    "hitl_gate_1": format_extraction,
    "hitl_gate_2": format_regulatory_mapping,
    "hitl_gate_3": format_compliance_findings,
    "hitl_gate_4": lambda data: format_scorecard(data) if data.get("scorecard") else str(data),
}


async def handle_review_gate(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Fetch the HITL review queue for a given gate.

    Parameters
    ----------
    params:
        gate (str | None): "gate_1", "gate_2", "gate_3", "gate_4" or None for all.
        limit (int): Max items to return.
    """
    gate: str | None = params.get("gate")
    limit: int = params.get("limit", 20)

    logger.info("Fetching HITL queue: gate=%s, limit=%d", gate, limit)

    result = await api.get_hitl_queue(gate=gate, limit=limit)
    items = result.get("items", [])

    header = ""
    if gate:
        header = f"Filter: **{gate}**\n\n"

    return header + format_hitl_queue(items)


async def handle_get_review_detail(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Fetch detailed AI output for a document pending HITL review.

    Parameters
    ----------
    params:
        document_id (str): UUID of the document to review.
    """
    document_id: str = params.get("document_id", "")
    if not document_id:
        return "Error: Harap berikan document_id untuk melihat detail review."

    logger.info("Fetching review detail for %s", document_id)

    review = await api.get_review_detail(document_id)
    gate = review.get("gate", "")

    formatter = _GATE_FORMATTERS.get(gate)
    if formatter:
        return formatter(review)

    # Fallback: render raw data summary
    return (
        f"**Detail Review** (Gate: `{gate}`)\n\n"
        f"Document ID: `{document_id}`\n"
        f"Data tersedia — gunakan gate-specific command untuk format lengkap."
    )


async def handle_submit_decision(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Submit a HITL decision (approve / reject / modify).

    Parameters
    ----------
    params:
        document_id (str): UUID of the document.
        decision (str): "approved", "rejected", or "modified".
        modified_data (dict | None): Changes if decision is "modified".
        modification_summary (str | None): Summary of modifications.
        notes (str | None): Reviewer notes.
    """
    document_id: str = params.get("document_id", "")
    decision: str = params.get("decision", "")

    if not document_id:
        return "Error: Harap berikan document_id."
    if decision not in ("approved", "rejected", "modified"):
        return (
            "Error: Keputusan harus salah satu dari: "
            "`approved`, `rejected`, atau `modified`."
        )

    reviewer_id: str = user.get("id", "")
    reviewer_role: str = user.get("role", "corp_secretary")

    if not reviewer_id:
        return "Error: User ID tidak ditemukan. Pastikan Anda sudah login."

    logger.info(
        "Submitting HITL decision: doc=%s, decision=%s, reviewer=%s",
        document_id,
        decision,
        reviewer_id,
    )

    result = await api.submit_decision(
        document_id=document_id,
        decision=decision,
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
        modified_data=params.get("modified_data"),
        modification_summary=params.get("modification_summary"),
        notes=params.get("notes"),
    )

    decision_id = result.get("decision_id", "-")
    gate = result.get("gate", "-")
    next_status = result.get("next_status", "-")

    decision_label = {
        "approved": "Disetujui",
        "rejected": "Ditolak",
        "modified": "Disetujui dengan Perubahan",
    }.get(decision, decision)

    return (
        f"**Keputusan Berhasil Disimpan**\n\n"
        f"**Decision ID:** `{decision_id}`\n"
        f"**Dokumen:** `{document_id}`\n"
        f"**Gate:** {gate}\n"
        f"**Keputusan:** {decision_label}\n"
        f"**Status Berikutnya:** `{next_status}`"
    )
