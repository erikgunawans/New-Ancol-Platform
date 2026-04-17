"""Abstract interface for regulation knowledge graph queries.

Defines the data model (nodes, edges) and abstract base class that both
Spanner Graph and Neo4j implementations must satisfy.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from ancol_common.rag.models import (
    DecisionNode,
    DocumentIndicator,
    EvidenceNode,
    EvidenceSummary,
    Gate5Half,
)
from ancol_common.schemas.bjr import BJRItemCode


@dataclass
class RegulationNode:
    """A regulation vertex in the knowledge graph."""

    id: str
    title: str
    issuer: str
    effective_date: str
    status: str
    authority_level: int


@dataclass
class ClauseNode:
    """A clause (pasal/ayat) within a regulation."""

    id: str
    regulation_id: str
    clause_number: str
    text_summary: str
    domain: str


@dataclass
class AmendmentEdge:
    """Directed edge representing a regulation amendment relationship."""

    source_id: str
    target_id: str
    effective_date: str
    change_type: str


@dataclass
class CrossReference:
    """Edge between two clauses that reference each other."""

    source_clause_id: str
    target_clause_id: str
    reference_type: str


@dataclass
class ContractNode:
    """A contract vertex in the knowledge graph."""

    id: str
    title: str
    contract_type: str
    status: str


class GraphClient(ABC):
    """Abstract base for regulation knowledge graph backends.

    Implementations must handle connection errors gracefully — log the error
    and return empty results rather than propagating exceptions to callers.
    """

    @abstractmethod
    async def query_related_regulations(self, regulation_id: str) -> list[RegulationNode]:
        """Return regulations directly related to the given regulation."""

    @abstractmethod
    async def get_amendment_chain(self, regulation_id: str) -> list[AmendmentEdge]:
        """Traverse the amendment chain (up to 3 hops) from a regulation."""

    @abstractmethod
    async def find_cross_references(self, clause_id: str) -> list[CrossReference]:
        """Find all cross-references originating from a clause."""

    @abstractmethod
    async def get_regulations_by_domain(self, domain: str) -> list[RegulationNode]:
        """Return all active regulations governing a regulatory domain."""

    @abstractmethod
    async def check_active_status(self, regulation_id: str) -> bool:
        """Check if a regulation is still active (not superseded)."""

    @abstractmethod
    async def get_related_regulations_for_contract(
        self,
        contract_id: str,
    ) -> list[RegulationNode]:
        """Return regulations linked to a contract via graph edges."""

    @abstractmethod
    async def get_related_contracts(self, contract_id: str) -> list[ContractNode]:
        """Return contracts in the amendment/renewal chain."""

    # ── BJR extensions ──
    # These back the decision-level defensibility features: per-document
    # indicators, decision evidence browsing, and Gate 5 approval audit.

    @abstractmethod
    async def upsert_decision_node(self, decision: DecisionNode) -> None:
        """Create or update a Decision vertex.

        Idempotent: re-upserting the same decision_id updates the properties
        (status, readiness_score, locked_at) in place without duplicating.
        """

    @abstractmethod
    async def upsert_supported_by_edge(
        self,
        decision_id: uuid.UUID,
        evidence: EvidenceNode,
        linked_at: datetime,
        linked_by: uuid.UUID,
    ) -> None:
        """Create/update Decision-[SUPPORTED_BY]->Evidence edge.

        The Evidence vertex is upserted if it doesn't exist yet.
        """

    @abstractmethod
    async def upsert_satisfies_item_edge(
        self,
        evidence_id: uuid.UUID,
        item_code: BJRItemCode,
        decision_id: uuid.UUID,
        evaluator_status: str,
    ) -> None:
        """Create/update Evidence-[SATISFIES_ITEM {decision_id}]->ChecklistItem edge.

        Multiple edges can exist between the same Evidence and ChecklistItem
        (one per decision) — the `decision_id` property on the edge disambiguates.
        `evaluator_status` is the current evaluator output for that item under
        that decision (satisfied|flagged|not_started).
        """

    @abstractmethod
    async def upsert_approved_by_edge(
        self,
        decision_id: uuid.UUID,
        user_id: uuid.UUID,
        half: Gate5Half,
        approved_at: datetime,
    ) -> None:
        """Create Decision-[APPROVED_BY {half, approved_at}]->User edge.

        One edge per Gate 5 half (Komisaris + Legal). Re-upserting the same
        (decision_id, half) tuple updates `approved_at` to the latest value —
        needed when Gate 5 is re-opened after a rejection and re-approved.
        """

    @abstractmethod
    async def get_document_indicators(
        self,
        doc_id: uuid.UUID,
    ) -> list[DocumentIndicator]:
        """Return all BJR decisions this document supports, with per-decision status.

        One-hop query:
            MATCH (ev:Evidence {id: $doc_id})<-[:SUPPORTED_BY]-(d:Decision)
            OPTIONAL MATCH (ev)-[:SATISFIES_ITEM {decision_id: d.id}]->(item)
            RETURN d, collect(item.code) AS satisfied_items

        On connection failure, returns [] (graph is supplementary — API
        callers have a SQL fallback path).
        """

    @abstractmethod
    async def get_decision_evidence(
        self,
        decision_id: uuid.UUID,
    ) -> list[EvidenceSummary]:
        """Return all evidence linked to a decision, with per-evidence item codes.

        Reverse of `get_document_indicators`. Used by the chat tool
        `show_decision_evidence` to answer "what supports decision X?".
        """
