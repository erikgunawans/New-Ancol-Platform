"""Knowledge graph abstraction shared by gemini-agent and api-gateway.

Re-exports the public ``GraphClient`` interface + data model dataclasses
so consumers don't have to reach into submodule paths.
"""

from __future__ import annotations

from ancol_common.rag.graph_client import (
    AmendmentEdge,
    ClauseNode,
    ContractNode,
    CrossReference,
    GraphClient,
    RegulationNode,
)

__all__ = [
    "AmendmentEdge",
    "ClauseNode",
    "ContractNode",
    "CrossReference",
    "GraphClient",
    "RegulationNode",
]
