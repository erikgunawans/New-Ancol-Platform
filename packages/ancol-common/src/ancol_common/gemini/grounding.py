"""Vertex AI Search grounding configuration for the Legal Research Agent."""

from __future__ import annotations

from google.genai.types import Retrieval, Tool, VertexAISearch

from ancol_common.config import get_settings


def get_regulatory_search_tool() -> Tool:
    """Create a Vertex AI Search grounding tool for the regulatory corpus."""
    settings = get_settings()
    return Tool(
        retrieval=Retrieval(
            vertex_ai_search=VertexAISearch(
                datastore=settings.vertex_search_datastore,
            )
        )
    )
