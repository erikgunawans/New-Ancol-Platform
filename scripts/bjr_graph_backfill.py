"""BJR graph backfill — populate Decision + edges from existing PG state.

Idempotent. Uses MERGE semantics from the standard GraphClient upsert methods.
Safe to re-run.  Supports --dry-run for a row-count probe without writes.

Usage:
    PYTHONPATH=packages/ancol-common/src python3 scripts/bjr_graph_backfill.py
    PYTHONPATH=packages/ancol-common/src python3 scripts/bjr_graph_backfill.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import uuid

from ancol_common.db.connection import dispose_engine, get_session
from ancol_common.db.models import (
    BJRChecklistItemRecord,
    DecisionEvidenceRecord,
    StrategicDecision,
)
from ancol_common.rag.graph_client import GraphClient
from ancol_common.rag.models import DecisionNode, EvidenceNode
from ancol_common.schemas.bjr import BJRItemCode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _build_graph_client() -> GraphClient:
    """Construct the GraphClient based on GRAPH_BACKEND env.

    Supported: ``neo4j`` (fully implemented in Task 4), ``spanner`` (stubs only;
    Task 5 deferred). Any other value raises — fail-loud is preferable to
    silently no-op writes.
    """
    backend = os.getenv("GRAPH_BACKEND", "spanner").lower()
    if backend == "neo4j":
        from ancol_common.rag.neo4j_graph import Neo4jGraphClient

        return Neo4jGraphClient(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
        )
    if backend == "spanner":
        from ancol_common.rag.spanner_graph import SpannerGraphClient

        return SpannerGraphClient(
            project_id=os.getenv("GCP_PROJECT_ID", ""),
            instance_id=os.getenv("SPANNER_INSTANCE_ID", ""),
            database_id=os.getenv("SPANNER_DATABASE_ID", ""),
        )
    raise ValueError(f"Unknown GRAPH_BACKEND={backend!r}; expected neo4j|spanner")


async def backfill_decisions(session: AsyncSession, graph: GraphClient) -> int:
    """Read StrategicDecision rows, upsert Decision nodes. Return count.

    Column mapping (PG → DecisionNode):
      bjr_readiness_score         → readiness_score
      corporate_compliance_score  → corporate_score
      regional_compliance_score   → regional_score
      source                      → origin
    """
    result = await session.execute(select(StrategicDecision))
    rows = list(result.scalars().all())
    for d in rows:
        node = DecisionNode(
            id=d.id,
            title=d.title,
            status=d.status,
            readiness_score=d.bjr_readiness_score,
            corporate_score=d.corporate_compliance_score,
            regional_score=d.regional_compliance_score,
            locked_at=d.locked_at,
            initiative_type=d.initiative_type,
            origin=d.source,
            created_at=d.created_at,
        )
        await graph.upsert_decision_node(node)
    logger.info("Backfilled %d Decision nodes", len(rows))
    return len(rows)


async def backfill_decision_edges(session: AsyncSession, graph: GraphClient) -> int:
    """Backfill SUPPORTED_BY + SATISFIES_ITEM edges.

    SUPPORTED_BY: one edge per DecisionEvidenceRecord row.
    SATISFIES_ITEM: one edge per valid {type, id} entry in
    BJRChecklistItemRecord.evidence_refs JSONB. Malformed refs and stale
    item_codes are logged and skipped — one bad row should not kill the
    other 15 per decision.
    """
    # SUPPORTED_BY: DecisionEvidenceRecord → one edge per row
    result = await session.execute(select(DecisionEvidenceRecord))
    ev_rows = list(result.scalars().all())
    supported = 0
    for row in ev_rows:
        node = EvidenceNode(id=row.evidence_id, type=row.evidence_type)
        await graph.upsert_supported_by_edge(
            decision_id=row.decision_id,
            evidence=node,
            linked_at=row.created_at,
            linked_by=row.created_by,
        )
        supported += 1

    # SATISFIES_ITEM: BJRChecklistItemRecord.evidence_refs JSONB → one edge per valid ref
    # evidence_refs shape per evaluators.py: list[{"type": "<ev_type>", "id": "<str-uuid>"}]
    result = await session.execute(select(BJRChecklistItemRecord))
    item_rows = list(result.scalars().all())
    satisfies = 0
    for row in item_rows:
        try:
            item_enum = BJRItemCode(row.item_code)
        except ValueError:
            logger.warning(
                "Skipping unknown item_code=%r on checklist row id=%s",
                row.item_code,
                row.id,
            )
            continue

        for ref in row.evidence_refs or []:
            if not isinstance(ref, dict):
                logger.warning(
                    "Skipping non-dict evidence_ref on checklist row id=%s: %r",
                    row.id,
                    ref,
                )
                continue
            ref_id = ref.get("id")
            if not ref_id:
                logger.warning(
                    "Skipping evidence_ref without id on checklist row id=%s: %r",
                    row.id,
                    ref,
                )
                continue
            try:
                evidence_uuid = uuid.UUID(str(ref_id))
            except (ValueError, TypeError):
                logger.warning(
                    "Skipping malformed evidence_ref id=%r on checklist row id=%s",
                    ref_id,
                    row.id,
                )
                continue
            await graph.upsert_satisfies_item_edge(
                evidence_id=evidence_uuid,
                item_code=item_enum,
                decision_id=row.decision_id,
                evaluator_status=row.status,
            )
            satisfies += 1

    logger.info("Backfilled %d SUPPORTED_BY + %d SATISFIES_ITEM edges", supported, satisfies)
    return supported + satisfies


async def backfill_all(session: AsyncSession, graph: GraphClient) -> dict[str, int]:
    """Run the full backfill: decisions then edges. Return stats dict."""
    decisions = await backfill_decisions(session, graph)
    edges = await backfill_decision_edges(session, graph)
    return {"decisions": decisions, "edges": edges}


async def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill the BJR graph from PG state.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count source rows without writing to the graph.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        async with get_session() as session:
            if args.dry_run:
                logger.info("DRY RUN — counting source rows only")
                n_dec = len(
                    list((await session.execute(select(StrategicDecision))).scalars().all())
                )
                n_ev = len(
                    list((await session.execute(select(DecisionEvidenceRecord))).scalars().all())
                )
                n_items = len(
                    list((await session.execute(select(BJRChecklistItemRecord))).scalars().all())
                )
                logger.info(
                    "Would backfill: %d decisions, %d decision_evidence rows, %d checklist rows",
                    n_dec,
                    n_ev,
                    n_items,
                )
                return 0

            graph = _build_graph_client()
            stats = await backfill_all(session, graph)
            logger.info("Backfill complete: %s", stats)
    finally:
        await dispose_engine()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
