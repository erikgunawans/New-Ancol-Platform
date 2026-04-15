"""Seed Spanner Graph with contract nodes and relationship edges."""

from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)


async def seed_contract_graph(
    contract_id: str,
    contract_title: str,
    contract_type: str,
    parent_contract_id: str | None,
    applicable_regulations: list[dict],
) -> dict:
    """Create Spanner Graph nodes and edges for a contract.

    Creates:
    - Contract node
    - ContractRegulation edges (contract → regulation)
    - ContractAmendment edges (child → parent contract)

    Best-effort — returns summary, logs warnings on failure.
    """
    try:
        return await asyncio.to_thread(
            _seed_sync,
            contract_id,
            contract_title,
            contract_type,
            parent_contract_id,
            applicable_regulations,
        )
    except Exception:
        logger.warning("Contract graph seeding failed", exc_info=True)
        return {"nodes_created": 0, "edges_created": 0}


def _seed_sync(
    contract_id: str,
    contract_title: str,
    contract_type: str,
    parent_contract_id: str | None,
    applicable_regulations: list[dict],
) -> dict:
    """Synchronous Spanner Graph seeding (runs in thread)."""
    try:
        from google.cloud import spanner
    except ImportError:
        logger.error("google-cloud-spanner not installed — graph seeding unavailable")
        return {"nodes_created": 0, "edges_created": 0}

    project_id = os.getenv("GCP_PROJECT", "ancol-mom-compliance")
    instance_id = os.getenv("SPANNER_INSTANCE", "ancol-compliance")
    database_id = os.getenv("SPANNER_DATABASE", "regulation-graph")

    client = spanner.Client(project=project_id)
    instance = client.instance(instance_id)
    database = instance.database(database_id)

    nodes_created = 0
    edges_created = 0

    def _transaction(transaction):
        nonlocal nodes_created, edges_created

        # Insert contract node
        transaction.insert_or_update(
            table="Contracts",
            columns=["id", "title", "contract_type", "status"],
            values=[[contract_id, contract_title, contract_type, "draft"]],
        )
        nodes_created += 1

        # Insert contract-regulation edges
        for reg in applicable_regulations:
            reg_id = reg.get("regulation_id", "")
            relevance = reg.get("relevance", "")
            if reg_id:
                transaction.insert_or_update(
                    table="ContractRegulations",
                    columns=["contract_id", "regulation_id", "relevance"],
                    values=[[contract_id, reg_id, relevance]],
                )
                edges_created += 1

        # Insert amendment edge if parent exists
        if parent_contract_id:
            transaction.insert_or_update(
                table="ContractAmendments",
                columns=["source_id", "target_id", "change_type"],
                values=[[contract_id, parent_contract_id, "amendment"]],
            )
            edges_created += 1

    try:
        database.run_in_transaction(_transaction)
    except Exception:
        logger.warning("Spanner transaction failed for contract %s", contract_id, exc_info=True)

    logger.info(
        "Graph seeded: contract=%s, nodes=%d, edges=%d",
        contract_id,
        nodes_created,
        edges_created,
    )
    return {"nodes_created": nodes_created, "edges_created": edges_created}
