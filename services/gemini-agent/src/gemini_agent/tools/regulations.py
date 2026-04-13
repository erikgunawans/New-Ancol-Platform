"""Tool handler — search regulations via RAG orchestrator (stub).

The RAG orchestrator is being built by another agent. This module imports
a placeholder and formats whatever it returns.
"""

from __future__ import annotations

import logging

from gemini_agent.api_client import ApiClient
from gemini_agent.formatting import format_regulation_result

logger = logging.getLogger(__name__)


async def handle_search_regulations(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Search the regulatory corpus for relevant regulations.

    Parameters
    ----------
    params:
        query (str): Natural-language search query in Bahasa Indonesia or English.
        top_k (int): Maximum number of results (default 5).
    """
    query: str = params.get("query", "").strip()
    top_k: int = params.get("top_k", 5)

    if not query:
        return "Error: Harap berikan query pencarian regulasi."

    logger.info("Searching regulations: query=%r, top_k=%d", query, top_k)

    try:
        from gemini_agent.rag.orchestrator import query_regulations

        result = await query_regulations(query=query)
        # The orchestrator returns {results, query, total_results}; trim to top_k
        results_list = result.get("results", [])[:top_k]
        result["results"] = results_list
    except ImportError:
        logger.warning("RAG orchestrator not yet available, returning stub response")
        result = {
            "query": query,
            "results": [],
            "citation_chain": [],
            "note": "RAG orchestrator belum tersedia — fitur ini sedang dalam pengembangan.",
        }
    except Exception:
        logger.exception("Regulation search failed")
        return "Gagal melakukan pencarian regulasi. Silakan coba lagi."

    return format_regulation_result(result)
