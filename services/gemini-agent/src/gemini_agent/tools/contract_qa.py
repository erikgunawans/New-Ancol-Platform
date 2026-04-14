"""Tool handler for conversational contract Q&A via 3-layer RAG."""

from __future__ import annotations

import logging

from gemini_agent.api_client import ApiClient
from gemini_agent.formatting import format_contract_qa_response
from gemini_agent.rag.contract_rag import answer_contract_question

logger = logging.getLogger(__name__)


async def handle_ask_contract_question(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Answer a natural-language question about contracts using hybrid RAG."""
    question: str = params.get("question", "")
    contract_id: str | None = params.get("contract_id")

    if not question:
        return "Error: Mohon berikan pertanyaan Anda."

    try:
        result = await answer_contract_question(question, contract_id, api)
        return format_contract_qa_response(result)
    except Exception:
        logger.exception("Contract Q&A failed for question: %s", question[:100])
        return (
            "Maaf, terjadi kesalahan saat memproses pertanyaan Anda. "
            "Silakan coba lagi atau gunakan perintah lain:\n"
            "- `check_contract_status` untuk status kontrak\n"
            "- `list_obligations` untuk kewajiban kontrak\n"
            "- `search_regulations` untuk regulasi terkait"
        )
