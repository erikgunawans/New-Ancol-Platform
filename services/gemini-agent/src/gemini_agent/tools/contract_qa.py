"""Tool handler for conversational contract Q&A.

This is a Phase 1 stub. Full implementation with RAG will come in Phase 2
when the contract corpus is added to Vertex AI Search.
"""

from __future__ import annotations

import logging

from gemini_agent.api_client import ApiClient

logger = logging.getLogger(__name__)


async def handle_ask_contract_question(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Answer a natural-language question about contracts."""
    question: str = params.get("question", "")
    contract_id: str | None = params.get("contract_id")

    if not question:
        return "Error: Mohon berikan pertanyaan Anda."

    # Phase 1 stub — in Phase 2, this will:
    # 1. Search contract corpus via Vertex AI Search
    # 2. Expand via Spanner Graph (contract-regulation links)
    # 3. If contract_id given, fetch specific contract context
    # 4. Synthesize answer with citation chain

    context = ""
    if contract_id:
        try:
            contract = await api.get_contract(contract_id)
            clauses = await api.get_contract_clauses(contract_id)
            context = (
                f"\n\nKonteks kontrak: **{contract.get('title', '-')}** "
                f"(tipe: {contract.get('contract_type', '-')}, "
                f"status: {contract.get('status', '-')}). "
                f"{len(clauses.get('clauses', []))} klausul diekstrak."
            )
        except Exception:
            logger.warning("Could not fetch contract context for Q&A")

    return (
        "Fitur Q&A kontrak akan tersedia sepenuhnya di Phase 2 "
        "ketika corpus kontrak diintegrasikan dengan Vertex AI Search.\n\n"
        f"**Pertanyaan Anda:** {question}{context}\n\n"
        "Untuk saat ini, Anda dapat:\n"
        "- Gunakan `check_contract_status` untuk melihat status kontrak\n"
        "- Gunakan `list_obligations` untuk melihat kewajiban\n"
        "- Gunakan `search_regulations` untuk mencari regulasi terkait"
    )
