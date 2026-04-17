"""Unit tests for the 6 BJR methods on Neo4jGraphClient.

Uses the neo4j async driver with its internal machinery mocked via AsyncMock.
Spanner parity tests land in a sibling file in Task 5.
"""

from __future__ import annotations

import importlib.util
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ancol_common.rag.models import (
    DecisionNode,
    DocumentIndicator,
    EvidenceNode,
    EvidenceSummary,
    Gate5Half,
)
from ancol_common.schemas.bjr import BJRItemCode
from ancol_common.schemas.decision import DecisionStatus

pytestmark = pytest.mark.skipif(
    not importlib.util.find_spec("neo4j"),
    reason="neo4j driver not installed",
)


def _make_client_with_mock_driver(records: list[dict]):
    """Build a Neo4jGraphClient whose driver returns preset records.

    Patches `neo4j.AsyncGraphDatabase.driver` during `__init__` so no real
    connection pool is created. Without this, each test leaks a driver pool
    (TCP resources + executor threads) that is never closed.
    """
    import neo4j
    from ancol_common.rag.neo4j_graph import Neo4jGraphClient

    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.data = AsyncMock(return_value=records)
    mock_session.run = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_driver = MagicMock()
    mock_driver.session = MagicMock(return_value=mock_session)
    mock_driver.close = AsyncMock()

    with patch.object(neo4j.AsyncGraphDatabase, "driver", return_value=mock_driver):
        client = Neo4jGraphClient(uri="bolt://dummy", username="neo4j", password="dummy")
    return client


@pytest.mark.asyncio
async def test_upsert_decision_node_generates_merge_cypher() -> None:
    client = _make_client_with_mock_driver([])
    now = datetime.now(UTC)
    decision = DecisionNode(
        id=uuid.uuid4(),
        title="Divestasi Hotel Jaya",
        status=DecisionStatus.BJR_LOCKED.value,
        readiness_score=94.0,
        corporate_score=94.0,
        regional_score=96.0,
        locked_at=now,
        initiative_type="divestment",
        origin="proactive",
    )
    await client.upsert_decision_node(decision)

    mock_session = client._driver.session.return_value
    cypher = mock_session.run.await_args_list[0].args[0]
    assert "MERGE (d:Decision {id:" in cypher
    assert "SET" in cypher


@pytest.mark.asyncio
async def test_upsert_supported_by_edge_includes_metadata() -> None:
    client = _make_client_with_mock_driver([])
    ev = EvidenceNode(id=uuid.uuid4(), type="mom")

    await client.upsert_supported_by_edge(
        decision_id=uuid.uuid4(),
        evidence=ev,
        linked_at=datetime.now(UTC),
        linked_by=uuid.uuid4(),
    )

    mock_session = client._driver.session.return_value
    cypher = mock_session.run.await_args_list[0].args[0]
    assert "MERGE (d)-[sb:SUPPORTED_BY]->(ev)" in cypher
    assert "sb.linked_at" in cypher
    assert "sb.linked_by" in cypher


@pytest.mark.asyncio
async def test_upsert_satisfies_item_edge_carries_decision_id() -> None:
    client = _make_client_with_mock_driver([])
    decision_id = uuid.uuid4()

    await client.upsert_satisfies_item_edge(
        evidence_id=uuid.uuid4(),
        item_code=BJRItemCode.D_06_QUORUM,
        decision_id=decision_id,
        evaluator_status="satisfied",
    )

    mock_session = client._driver.session.return_value
    call = mock_session.run.await_args_list[0]
    cypher = call.args[0]
    assert "SATISFIES_ITEM" in cypher
    assert "decision_id" in cypher
    params = call.args[1] if len(call.args) > 1 else call.kwargs
    assert str(decision_id) in str(params)


@pytest.mark.asyncio
async def test_upsert_approved_by_edge_includes_half() -> None:
    client = _make_client_with_mock_driver([])

    await client.upsert_approved_by_edge(
        decision_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        half=Gate5Half.KOMISARIS,
        approved_at=datetime.now(UTC),
    )

    mock_session = client._driver.session.return_value
    cypher = mock_session.run.await_args_list[0].args[0]
    assert "APPROVED_BY" in cypher
    assert "$half" in cypher


@pytest.mark.asyncio
async def test_upsert_approved_by_edge_keyed_by_half_not_user() -> None:
    """A re-approval by a DIFFERENT user for the same half must replace the
    prior edge, not create a duplicate — the contract is one edge per
    (decision_id, half), independent of the approver's identity.
    """
    client = _make_client_with_mock_driver([])

    await client.upsert_approved_by_edge(
        decision_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        half=Gate5Half.KOMISARIS,
        approved_at=datetime.now(UTC),
    )

    mock_session = client._driver.session.return_value
    cypher = mock_session.run.await_args_list[0].args[0]
    # Existing edges for this half must be DELETED before the new one is created.
    assert "OPTIONAL MATCH" in cypher
    assert "APPROVED_BY {half: $half}" in cypher
    assert "DELETE" in cypher
    # DISTINCT collapses duplicate (d, u) rows from OPTIONAL MATCH so CREATE
    # runs exactly once even if multiple stale edges were cleaned up.
    assert "WITH DISTINCT" in cypher
    # The new edge is created (not merged) after the cleanup.
    assert "CREATE" in cypher


@pytest.mark.asyncio
async def test_get_document_indicators_parses_records() -> None:
    decision_id = uuid.uuid4()
    records = [
        {
            "d_id": str(decision_id),
            "d_title": "Akuisisi Wahana",
            "d_status": DecisionStatus.DD_IN_PROGRESS.value,
            "d_readiness_score": 72.0,
            "d_locked_at": None,
            "d_origin": "proactive",
            "satisfied_items": [BJRItemCode.D_06_QUORUM.value],
        }
    ]
    client = _make_client_with_mock_driver(records)

    results = await client.get_document_indicators(doc_id=uuid.uuid4())

    assert len(results) == 1
    assert isinstance(results[0], DocumentIndicator)
    assert results[0].decision_id == decision_id
    assert results[0].is_locked is False
    assert BJRItemCode.D_06_QUORUM in results[0].satisfied_items


@pytest.mark.asyncio
async def test_get_document_indicators_handles_locked_decision() -> None:
    decision_id = uuid.uuid4()
    locked_at = datetime.now(UTC)
    records = [
        {
            "d_id": str(decision_id),
            "d_title": "Divestasi Hotel Jaya",
            "d_status": DecisionStatus.BJR_LOCKED.value,
            "d_readiness_score": 94.0,
            "d_locked_at": locked_at.isoformat(),
            "d_origin": "proactive",
            "satisfied_items": [
                BJRItemCode.D_06_QUORUM.value,
                BJRItemCode.D_07_SIGNED.value,
            ],
        }
    ]
    client = _make_client_with_mock_driver(records)

    results = await client.get_document_indicators(doc_id=uuid.uuid4())

    assert len(results) == 1
    assert results[0].is_locked is True
    assert results[0].state_emoji == "🔒"
    assert len(results[0].satisfied_items) == 2


@pytest.mark.asyncio
async def test_get_decision_evidence_groups_by_evidence_id() -> None:
    ev_id = uuid.uuid4()
    records = [
        {
            "ev_id": str(ev_id),
            "ev_type": "mom",
            "ev_title": "MoM BOD #5/2026",
            "satisfies_items": [
                BJRItemCode.D_06_QUORUM.value,
                BJRItemCode.D_07_SIGNED.value,
            ],
        }
    ]
    client = _make_client_with_mock_driver(records)

    results = await client.get_decision_evidence(decision_id=uuid.uuid4())

    assert len(results) == 1
    assert isinstance(results[0], EvidenceSummary)
    assert results[0].evidence_id == ev_id
    assert len(results[0].satisfies_items) == 2


@pytest.mark.asyncio
async def test_get_document_indicators_returns_empty_on_connection_error() -> None:
    """Degradation contract: graph failures must not propagate to callers."""
    import neo4j
    from ancol_common.rag.neo4j_graph import Neo4jGraphClient

    failing_session = AsyncMock()
    failing_session.run = AsyncMock(side_effect=ConnectionError("bolt unreachable"))
    failing_session.__aenter__ = AsyncMock(return_value=failing_session)
    failing_session.__aexit__ = AsyncMock(return_value=None)
    failing_driver = MagicMock()
    failing_driver.session = MagicMock(return_value=failing_session)
    failing_driver.close = AsyncMock()

    with patch.object(neo4j.AsyncGraphDatabase, "driver", return_value=failing_driver):
        client = Neo4jGraphClient(uri="bolt://dummy", username="neo4j", password="dummy")

    results = await client.get_document_indicators(doc_id=uuid.uuid4())
    assert results == []
