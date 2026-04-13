"""Neo4j fallback implementation of GraphClient.

Uses Cypher queries to traverse the regulation knowledge graph.  The
``neo4j`` Python driver is imported conditionally — if it is not installed
the module still loads but ``Neo4jGraphClient`` will raise at construction
time with a clear message.
"""

from __future__ import annotations

import logging
import os

from .graph_client import (
    AmendmentEdge,
    CrossReference,
    GraphClient,
    RegulationNode,
)

logger = logging.getLogger(__name__)

try:
    import neo4j  # type: ignore[import-untyped]

    _NEO4J_AVAILABLE = True
except ImportError:
    _NEO4J_AVAILABLE = False
    logger.debug(
        "neo4j driver not installed — Neo4jGraphClient will be unavailable. "
        "Install with: pip install neo4j"
    )


class Neo4jGraphClient(GraphClient):
    """Fallback graph backend using Neo4j (Cypher)."""

    def __init__(
        self,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        if not _NEO4J_AVAILABLE:
            raise RuntimeError("neo4j driver is not installed. Install with: pip install neo4j")

        self._uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self._username = username or os.getenv("NEO4J_USER", "neo4j")
        self._password = password or os.getenv("NEO4J_PASSWORD", "")

        self._driver = neo4j.AsyncGraphDatabase.driver(
            self._uri, auth=(self._username, self._password)
        )

        logger.info("Neo4jGraphClient initialised — uri=%s", self._uri)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_query(self, cypher: str, params: dict | None = None) -> list[dict]:
        """Execute a Cypher query and return result records as dicts.

        Connection / query errors are caught, logged, and an empty list is
        returned so that callers always receive a safe default.
        """
        try:
            async with self._driver.session() as session:
                result = await session.run(cypher, parameters=params or {})
                return [record.data() async for record in result]
        except Exception:
            logger.exception("Neo4j Cypher query failed: %s", cypher[:120])
            return []

    # ------------------------------------------------------------------
    # GraphClient implementation
    # ------------------------------------------------------------------

    async def query_related_regulations(self, regulation_id: str) -> list[RegulationNode]:
        """Find regulations related via AMENDS relationships."""
        cypher = """
            MATCH (r:Regulation)-[:AMENDS]->(t:Regulation)
            WHERE r.id = $regulation_id
            RETURN t
        """
        rows = await self._run_query(cypher, {"regulation_id": regulation_id})

        return [
            RegulationNode(
                id=r["t"]["id"],
                title=r["t"]["title"],
                issuer=r["t"]["issuer"],
                effective_date=str(r["t"]["effective_date"]),
                status=r["t"]["status"],
                authority_level=int(r["t"]["authority_level"]),
            )
            for r in rows
        ]

    async def get_amendment_chain(self, regulation_id: str) -> list[AmendmentEdge]:
        """Traverse up to 3 hops of AMENDS relationships."""
        cypher = """
            MATCH (r:Regulation)-[a:AMENDS*1..3]->(chain:Regulation)
            WHERE r.id = $regulation_id
            UNWIND range(0, size(a)-1) AS idx
            RETURN r.id AS source_id,
                   chain.id AS target_id,
                   a[idx].effective_date AS effective_date,
                   a[idx].change_type AS change_type
        """
        rows = await self._run_query(cypher, {"regulation_id": regulation_id})

        return [
            AmendmentEdge(
                source_id=r["source_id"],
                target_id=r["target_id"],
                effective_date=str(r["effective_date"]),
                change_type=r["change_type"],
            )
            for r in rows
        ]

    async def find_cross_references(self, clause_id: str) -> list[CrossReference]:
        """Find clauses referenced by the given clause."""
        cypher = """
            MATCH (c1:Clause)-[ref:REFERENCES]->(c2:Clause)
            WHERE c1.id = $clause_id
            RETURN c1.id AS source_clause_id,
                   c2.id AS target_clause_id,
                   ref.reference_type AS reference_type
        """
        rows = await self._run_query(cypher, {"clause_id": clause_id})

        return [
            CrossReference(
                source_clause_id=r["source_clause_id"],
                target_clause_id=r["target_clause_id"],
                reference_type=r["reference_type"],
            )
            for r in rows
        ]

    async def get_regulations_by_domain(self, domain: str) -> list[RegulationNode]:
        """Return regulations that govern the given domain."""
        cypher = """
            MATCH (r:Regulation)-[:GOVERNS]->(d:Domain)
            WHERE d.name = $domain
            RETURN r
        """
        rows = await self._run_query(cypher, {"domain": domain})

        return [
            RegulationNode(
                id=r["r"]["id"],
                title=r["r"]["title"],
                issuer=r["r"]["issuer"],
                effective_date=str(r["r"]["effective_date"]),
                status=r["r"]["status"],
                authority_level=int(r["r"]["authority_level"]),
            )
            for r in rows
        ]

    async def check_active_status(self, regulation_id: str) -> bool:
        """Return True if the regulation is active and not superseded."""
        cypher = """
            MATCH (r:Regulation)
            WHERE r.id = $regulation_id
            OPTIONAL MATCH (newer:Regulation)-[:SUPERSEDES]->(r)
            RETURN r.status AS status, COUNT(newer) AS supersede_count
        """
        rows = await self._run_query(cypher, {"regulation_id": regulation_id})

        if not rows:
            logger.warning(
                "Regulation %s not found in Neo4j — treating as inactive",
                regulation_id,
            )
            return False

        row = rows[0]
        return row["status"] == "active" and int(row["supersede_count"]) == 0
