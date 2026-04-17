"""gemini-agent RAG package.

``GraphClient`` + concrete backends moved to ``ancol_common.rag`` in
Phase 6.4a so other services (notably api-gateway) can import the
abstraction. This module is a backward-compat shim that re-exports
the same symbols local consumers were already importing.
"""

from __future__ import annotations

from ancol_common.rag import (
    AmendmentEdge,
    ClauseNode,
    CrossReference,
    GraphClient,
    RegulationNode,
)

from gemini_agent.rag.orchestrator import get_graph_client, query_regulations

__all__ = [
    "AmendmentEdge",
    "ClauseNode",
    "CrossReference",
    "GraphClient",
    "RegulationNode",
    "get_graph_client",
    "query_regulations",
]
