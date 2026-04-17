"""Cloud Spanner property graph implementation of GraphClient.

Uses GQL (Graph Query Language) to traverse the regulation knowledge graph
stored in Spanner. Requires the ``google-cloud-spanner`` package.
"""

from __future__ import annotations

import logging
import os

from google.cloud import spanner

from ancol_common.rag.graph_client import (
    AmendmentEdge,
    ContractNode,
    CrossReference,
    GraphClient,
    RegulationNode,
)

logger = logging.getLogger(__name__)


class SpannerGraphClient(GraphClient):
    """Primary graph backend using Cloud Spanner's property graph (GQL)."""

    def __init__(
        self,
        instance_id: str | None = None,
        database_id: str | None = None,
        project_id: str | None = None,
    ) -> None:
        self._project_id = project_id or os.getenv("GCP_PROJECT", "ancol-mom-compliance")
        self._instance_id = instance_id or os.getenv("SPANNER_INSTANCE", "ancol-compliance")
        self._database_id = database_id or os.getenv("SPANNER_DATABASE", "regulation-graph")

        self._client = spanner.Client(project=self._project_id)
        self._instance = self._client.instance(self._instance_id)
        self._database = self._instance.database(self._database_id)

        logger.info(
            "SpannerGraphClient initialised — project=%s instance=%s db=%s",
            self._project_id,
            self._instance_id,
            self._database_id,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _execute_gql(self, gql: str, params: dict, param_types: dict) -> list[dict]:
        """Run a GQL query and return rows as dicts.

        Connection / query errors are caught, logged, and an empty list is
        returned so that callers always get a safe default.
        """
        try:
            with self._database.snapshot() as snapshot:
                results = snapshot.execute_sql(gql, params=params, param_types=param_types)
                columns = [col.name for col in results.metadata.row_type.fields]
                return [dict(zip(columns, row, strict=False)) for row in results]
        except Exception:
            logger.exception("Spanner GQL query failed: %s", gql[:120])
            return []

    # ------------------------------------------------------------------
    # GraphClient implementation
    # ------------------------------------------------------------------

    async def query_related_regulations(self, regulation_id: str) -> list[RegulationNode]:
        """Find regulations related via AMENDS edges."""
        gql = """
            MATCH (r:Regulation)-[:AMENDS]->(t:Regulation)
            WHERE r.id = @regulation_id
            RETURN t.id, t.title, t.issuer, t.effective_date, t.status,
                   t.authority_level
        """
        params = {"regulation_id": regulation_id}
        param_types = {"regulation_id": spanner.param_types.STRING}
        rows = self._execute_gql(gql, params, param_types)

        return [
            RegulationNode(
                id=r["t.id"],
                title=r["t.title"],
                issuer=r["t.issuer"],
                effective_date=str(r["t.effective_date"]),
                status=r["t.status"],
                authority_level=int(r["t.authority_level"]),
            )
            for r in rows
        ]

    async def get_amendment_chain(self, regulation_id: str) -> list[AmendmentEdge]:
        """Traverse up to 3 hops of AMENDS relationships."""
        gql = """
            MATCH (r:Regulation)-[a:AMENDS*1..3]->(chain:Regulation)
            WHERE r.id = @regulation_id
            RETURN r.id AS source_id, chain.id AS target_id,
                   a.effective_date AS effective_date,
                   a.change_type AS change_type
        """
        params = {"regulation_id": regulation_id}
        param_types = {"regulation_id": spanner.param_types.STRING}
        rows = self._execute_gql(gql, params, param_types)

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
        gql = """
            MATCH (c1:Clause)-[ref:REFERENCES]->(c2:Clause)
            WHERE c1.id = @clause_id
            RETURN c1.id AS source_clause_id,
                   c2.id AS target_clause_id,
                   ref.reference_type AS reference_type
        """
        params = {"clause_id": clause_id}
        param_types = {"clause_id": spanner.param_types.STRING}
        rows = self._execute_gql(gql, params, param_types)

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
        gql = """
            MATCH (r:Regulation)-[:GOVERNS]->(d:Domain)
            WHERE d.name = @domain
            RETURN r.id, r.title, r.issuer, r.effective_date, r.status,
                   r.authority_level
        """
        params = {"domain": domain}
        param_types = {"domain": spanner.param_types.STRING}
        rows = self._execute_gql(gql, params, param_types)

        return [
            RegulationNode(
                id=r["r.id"],
                title=r["r.title"],
                issuer=r["r.issuer"],
                effective_date=str(r["r.effective_date"]),
                status=r["r.status"],
                authority_level=int(r["r.authority_level"]),
            )
            for r in rows
        ]

    async def check_active_status(self, regulation_id: str) -> bool:
        """Return True if the regulation is active and not superseded.

        A regulation is considered inactive when:
        - Its ``status`` field is not ``'active'``, **or**
        - A newer regulation has a ``SUPERSEDES`` edge pointing to it.
        """
        gql = """
            MATCH (r:Regulation)
            WHERE r.id = @regulation_id
            OPTIONAL MATCH (newer:Regulation)-[:SUPERSEDES]->(r)
            RETURN r.status AS status, COUNT(newer) AS supersede_count
        """
        params = {"regulation_id": regulation_id}
        param_types = {"regulation_id": spanner.param_types.STRING}
        rows = self._execute_gql(gql, params, param_types)

        if not rows:
            logger.warning(
                "Regulation %s not found in graph — treating as inactive",
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
        gql = """
            MATCH (c:Contract)-[:GOVERNED_BY]->(r:Regulation)
            WHERE c.id = @contract_id
            RETURN r.id AS id, r.title AS title, r.issuer AS issuer,
                   r.effective_date AS effective_date, r.status AS status,
                   r.authority_level AS authority_level
        """
        params = {"contract_id": contract_id}
        param_types = {"contract_id": spanner.param_types.STRING}
        rows = self._execute_gql(gql, params, param_types)

        return [
            RegulationNode(
                id=row["id"],
                title=row.get("title", ""),
                issuer=row.get("issuer", ""),
                effective_date=row.get("effective_date", ""),
                status=row.get("status", "active"),
                authority_level=int(row.get("authority_level", 1)),
            )
            for row in rows
        ]

    async def get_related_contracts(self, contract_id: str) -> list[ContractNode]:
        """Return contracts in the amendment/renewal chain (up to 3 hops)."""
        gql = """
            MATCH (c:Contract)-[:AMENDS|RENEWS*1..3]->(related:Contract)
            WHERE c.id = @contract_id
            RETURN related.id AS id, related.title AS title,
                   related.contract_type AS contract_type,
                   related.status AS status
        """
        params = {"contract_id": contract_id}
        param_types = {"contract_id": spanner.param_types.STRING}
        rows = self._execute_gql(gql, params, param_types)

        return [
            ContractNode(
                id=row["id"],
                title=row.get("title", ""),
                contract_type=row.get("contract_type", ""),
                status=row.get("status", ""),
            )
            for row in rows
        ]
