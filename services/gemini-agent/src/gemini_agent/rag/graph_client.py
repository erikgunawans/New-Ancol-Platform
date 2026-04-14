"""Abstract interface for regulation knowledge graph queries.

Defines the data model (nodes, edges) and abstract base class that both
Spanner Graph and Neo4j implementations must satisfy.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


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
        self, contract_id: str,
    ) -> list[RegulationNode]:
        """Return regulations linked to a contract via graph edges."""

    @abstractmethod
    async def get_related_contracts(self, contract_id: str) -> list[ContractNode]:
        """Return contracts in the amendment/renewal chain."""
