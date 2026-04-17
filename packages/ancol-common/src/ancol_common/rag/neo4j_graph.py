"""Neo4j fallback implementation of GraphClient.

Uses Cypher queries to traverse the regulation knowledge graph.  The
``neo4j`` Python driver is imported conditionally — if it is not installed
the module still loads but ``Neo4jGraphClient`` will raise at construction
time with a clear message.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime

from ancol_common.rag.graph_client import (
    AmendmentEdge,
    ContractNode,
    CrossReference,
    GraphClient,
    RegulationNode,
)
from ancol_common.rag.models import (
    DecisionNode,
    DocumentIndicator,
    EvidenceNode,
    EvidenceSummary,
    Gate5Half,
)
from ancol_common.schemas.bjr import BJRItemCode

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

    async def get_related_regulations_for_contract(
        self,
        contract_id: str,
    ) -> list[RegulationNode]:
        """Return regulations linked to a contract via GOVERNED_BY edges."""
        cypher = """
            MATCH (c:Contract)-[:GOVERNED_BY]->(r:Regulation)
            WHERE c.id = $contract_id
            RETURN r.id AS id, r.title AS title, r.issuer AS issuer,
                   r.effective_date AS effective_date, r.status AS status,
                   r.authority_level AS authority_level
        """
        rows = await self._run_query(cypher, {"contract_id": contract_id})

        return [
            RegulationNode(
                id=row["id"],
                title=row.get("title", ""),
                issuer=row.get("issuer", ""),
                effective_date=str(row.get("effective_date", "")),
                status=row.get("status", "active"),
                authority_level=int(row.get("authority_level", 1)),
            )
            for row in rows
        ]

    async def get_related_contracts(self, contract_id: str) -> list[ContractNode]:
        """Return contracts in the amendment/renewal chain (up to 3 hops)."""
        cypher = """
            MATCH (c:Contract)-[:AMENDS|RENEWS*1..3]->(related:Contract)
            WHERE c.id = $contract_id
            RETURN related.id AS id, related.title AS title,
                   related.contract_type AS contract_type,
                   related.status AS status
        """
        rows = await self._run_query(cypher, {"contract_id": contract_id})

        return [
            ContractNode(
                id=row["id"],
                title=row.get("title", ""),
                contract_type=row.get("contract_type", ""),
                status=row.get("status", ""),
            )
            for row in rows
        ]

    async def close(self) -> None:
        """Close the Neo4j driver and release connections."""
        await self._driver.close()
        logger.info("Neo4jGraphClient closed")

    # ── BJR implementations ──

    async def upsert_decision_node(self, decision: DecisionNode) -> None:
        """Create or update a Decision vertex. Idempotent via MERGE on id."""
        cypher = """
        MERGE (d:Decision {id: $id})
        SET d.title = $title,
            d.status = $status,
            d.readiness_score = $readiness_score,
            d.corporate_score = $corporate_score,
            d.regional_score = $regional_score,
            d.locked_at = $locked_at,
            d.initiative_type = $initiative_type,
            d.origin = $origin
        """
        params = {
            "id": str(decision.id),
            "title": decision.title,
            "status": decision.status,
            "readiness_score": decision.readiness_score,
            "corporate_score": decision.corporate_score,
            "regional_score": decision.regional_score,
            "locked_at": decision.locked_at.isoformat() if decision.locked_at else None,
            "initiative_type": decision.initiative_type,
            "origin": decision.origin,
        }
        try:
            async with self._driver.session() as session:
                await session.run(cypher, params)
        except Exception:
            logger.exception("upsert_decision_node failed for %s", decision.id)

    async def upsert_supported_by_edge(
        self,
        decision_id: uuid.UUID,
        evidence: EvidenceNode,
        linked_at: datetime,
        linked_by: uuid.UUID,
    ) -> None:
        """Create/update Decision-[SUPPORTED_BY]->Evidence edge. Upserts Evidence vertex."""
        cypher = """
        MATCH (d:Decision {id: $decision_id})
        MERGE (ev:Evidence {id: $evidence_id})
        SET ev.type = $evidence_type
        MERGE (d)-[sb:SUPPORTED_BY]->(ev)
        SET sb.linked_at = $linked_at,
            sb.linked_by = $linked_by
        """
        params = {
            "decision_id": str(decision_id),
            "evidence_id": str(evidence.id),
            "evidence_type": evidence.type,
            "linked_at": linked_at.isoformat(),
            "linked_by": str(linked_by),
        }
        try:
            async with self._driver.session() as session:
                await session.run(cypher, params)
        except Exception:
            logger.exception("upsert_supported_by_edge failed %s->%s", decision_id, evidence.id)

    async def upsert_satisfies_item_edge(
        self,
        evidence_id: uuid.UUID,
        item_code: BJRItemCode,
        decision_id: uuid.UUID,
        evaluator_status: str,
    ) -> None:
        """Create/update Evidence-[SATISFIES_ITEM {decision_id}]->ChecklistItem.

        The edge's decision_id property disambiguates per-decision semantics
        so one evidence can satisfy the same item for multiple decisions.
        """
        cypher = """
        MATCH (ev:Evidence {id: $evidence_id})
        MERGE (item:ChecklistItem {code: $item_code})
        MERGE (ev)-[si:SATISFIES_ITEM {decision_id: $decision_id}]->(item)
        SET si.evaluator_status = $evaluator_status
        """
        params = {
            "evidence_id": str(evidence_id),
            "item_code": item_code.value,
            "decision_id": str(decision_id),
            "evaluator_status": evaluator_status,
        }
        try:
            async with self._driver.session() as session:
                await session.run(cypher, params)
        except Exception:
            logger.exception(
                "upsert_satisfies_item_edge failed %s->%s for decision %s",
                evidence_id,
                item_code.value,
                decision_id,
            )

    async def upsert_approved_by_edge(
        self,
        decision_id: uuid.UUID,
        user_id: uuid.UUID,
        half: Gate5Half,
        approved_at: datetime,
    ) -> None:
        """Create Decision-[APPROVED_BY {half}]->User edge.

        Keyed on (decision_id, half) so a re-approved half — even by a
        different authorized user — replaces the prior edge rather than
        adding a duplicate. Any existing APPROVED_BY for this half is
        removed first, then a fresh edge is created pointing at the
        current approver.
        """
        cypher = """
        MATCH (d:Decision {id: $decision_id})
        MERGE (u:User {id: $user_id})
        WITH d, u
        OPTIONAL MATCH (d)-[old_ab:APPROVED_BY {half: $half}]->(:User)
        DELETE old_ab
        WITH d, u
        CREATE (d)-[:APPROVED_BY {half: $half, approved_at: $approved_at}]->(u)
        """
        params = {
            "decision_id": str(decision_id),
            "user_id": str(user_id),
            "half": half.value,
            "approved_at": approved_at.isoformat(),
        }
        try:
            async with self._driver.session() as session:
                await session.run(cypher, params)
        except Exception:
            logger.exception("upsert_approved_by_edge failed %s/%s", decision_id, half)

    async def get_document_indicators(
        self,
        doc_id: uuid.UUID,
    ) -> list[DocumentIndicator]:
        """Return all decisions this doc supports + per-decision checklist coverage."""
        cypher = """
        MATCH (ev:Evidence {id: $doc_id})
        MATCH (ev)<-[:SUPPORTED_BY]-(d:Decision)
        OPTIONAL MATCH (ev)-[si:SATISFIES_ITEM {decision_id: d.id}]->(item:ChecklistItem)
        WITH d, collect(DISTINCT item.code) AS satisfied_items
        RETURN d.id AS d_id, d.title AS d_title, d.status AS d_status,
               d.readiness_score AS d_readiness_score,
               d.locked_at AS d_locked_at, d.origin AS d_origin,
               satisfied_items
        """
        try:
            async with self._driver.session() as session:
                result = await session.run(cypher, {"doc_id": str(doc_id)})
                records = await result.data()
        except Exception:
            logger.exception("get_document_indicators failed for %s", doc_id)
            return []

        out: list[DocumentIndicator] = []
        all_items = set(BJRItemCode)
        for rec in records:
            satisfied = [BJRItemCode(c) for c in (rec["satisfied_items"] or []) if c]
            missing = sorted(all_items - set(satisfied), key=lambda c: c.value)
            locked_at_raw = rec.get("d_locked_at")
            locked_at = datetime.fromisoformat(locked_at_raw) if locked_at_raw else None
            out.append(
                DocumentIndicator(
                    decision_id=uuid.UUID(rec["d_id"]),
                    decision_title=rec["d_title"],
                    status=rec["d_status"],
                    readiness_score=rec.get("d_readiness_score"),
                    is_locked=locked_at is not None,
                    locked_at=locked_at,
                    satisfied_items=satisfied,
                    missing_items=missing,
                    origin=rec.get("d_origin", "proactive"),
                )
            )
        return out

    async def get_decision_evidence(
        self,
        decision_id: uuid.UUID,
    ) -> list[EvidenceSummary]:
        """Return all evidence for a decision + which items each satisfies."""
        cypher = """
        MATCH (d:Decision {id: $decision_id})-[:SUPPORTED_BY]->(ev:Evidence)
        OPTIONAL MATCH (ev)-[si:SATISFIES_ITEM {decision_id: $decision_id}]->(item:ChecklistItem)
        WITH ev, collect(DISTINCT item.code) AS satisfies_items
        RETURN ev.id AS ev_id, ev.type AS ev_type,
               coalesce(ev.title, '') AS ev_title,
               satisfies_items
        """
        try:
            async with self._driver.session() as session:
                result = await session.run(cypher, {"decision_id": str(decision_id)})
                records = await result.data()
        except Exception:
            logger.exception("get_decision_evidence failed for decision %s", decision_id)
            return []

        return [
            EvidenceSummary(
                evidence_id=uuid.UUID(rec["ev_id"]),
                evidence_type=rec["ev_type"],
                title=rec["ev_title"] or f"{rec['ev_type']}:{rec['ev_id'][:8]}",
                satisfies_items=[BJRItemCode(c) for c in (rec["satisfies_items"] or []) if c],
            )
            for rec in records
        ]
