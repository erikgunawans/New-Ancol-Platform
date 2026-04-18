"""Tests for scripts/bjr_graph_backfill.py."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from scripts.bjr_graph_backfill import (
    backfill_all,
    backfill_decision_edges,
    backfill_decisions,
)


class _FakeGraphClient:
    """Duck-typed GraphClient (NOT subclassing) — only implements the 4
    upsert methods the backfill actually calls."""

    def __init__(self) -> None:
        self.decisions: dict = {}
        self.supported_by: list = []
        self.satisfies_item: list = []

    async def upsert_decision_node(self, decision) -> None:
        self.decisions[str(decision.id)] = decision

    async def upsert_supported_by_edge(self, decision_id, evidence, linked_at, linked_by) -> None:
        self.supported_by.append((str(decision_id), str(evidence.id), evidence.type))

    async def upsert_satisfies_item_edge(
        self, evidence_id, item_code, decision_id, evaluator_status
    ) -> None:
        self.satisfies_item.append(
            (str(evidence_id), item_code.value, str(decision_id), evaluator_status)
        )

    async def upsert_approved_by_edge(self, *a, **k) -> None:
        """Unused by backfill — stubbed as no-op."""


def _make_decision_orm(**overrides):
    """ORM-like MagicMock matching StrategicDecision's public attributes."""
    d = MagicMock()
    d.id = overrides.get("id", uuid.uuid4())
    d.title = overrides.get("title", "Test")
    d.status = overrides.get("status", "ideation")
    d.bjr_readiness_score = overrides.get("bjr_readiness_score")
    d.corporate_compliance_score = overrides.get("corporate_compliance_score")
    d.regional_compliance_score = overrides.get("regional_compliance_score")
    d.locked_at = overrides.get("locked_at")
    d.initiative_type = overrides.get("initiative_type", "investment")
    d.source = overrides.get("source", "proactive")
    d.created_at = overrides.get("created_at")
    return d


def _make_evidence_orm(**overrides):
    ev = MagicMock()
    ev.decision_id = overrides.get("decision_id", uuid.uuid4())
    ev.evidence_type = overrides.get("evidence_type", "mom")
    ev.evidence_id = overrides.get("evidence_id", uuid.uuid4())
    ev.created_by = overrides.get("created_by", uuid.uuid4())
    ev.created_at = overrides.get("created_at")
    return ev


def _make_checklist_orm(evidence_refs=None, **overrides):
    item = MagicMock()
    item.id = overrides.get("id", uuid.uuid4())
    item.decision_id = overrides.get("decision_id", uuid.uuid4())
    item.item_code = overrides.get("item_code", "D-06-QUORUM")
    item.status = overrides.get("status", "satisfied")
    item.evidence_refs = evidence_refs or []
    return item


def _fake_session_by_table(decisions=None, evidence=None, checklist=None):
    """Async session whose execute() dispatches on str(select(X)) table name."""

    async def fake_execute(stmt, *a, **k):
        stmt_str = str(stmt).lower()
        result = MagicMock()
        if "strategic_decisions" in stmt_str:
            result.scalars.return_value.all.return_value = decisions or []
        elif "decision_evidence" in stmt_str:
            result.scalars.return_value.all.return_value = evidence or []
        elif "bjr_checklists" in stmt_str:
            result.scalars.return_value.all.return_value = checklist or []
        else:
            result.scalars.return_value.all.return_value = []
        return result

    session = AsyncMock()
    session.execute = fake_execute
    return session


@pytest.mark.asyncio
async def test_backfill_decisions_maps_real_column_names():
    """Column mapping: bjr_readiness_score→readiness_score, source→origin, etc."""
    d = _make_decision_orm(
        title="Akuisisi X",
        bjr_readiness_score=72.0,
        corporate_compliance_score=72.0,
        regional_compliance_score=88.0,
        source="retroactive",
    )
    session = _fake_session_by_table(decisions=[d])
    graph = _FakeGraphClient()

    count = await backfill_decisions(session, graph)

    assert count == 1
    node = next(iter(graph.decisions.values()))
    assert node.title == "Akuisisi X"
    assert node.readiness_score == 72.0  # bjr_readiness_score → readiness_score
    assert node.corporate_score == 72.0  # corporate_compliance_score → corporate_score
    assert node.regional_score == 88.0  # regional_compliance_score → regional_score
    assert node.origin == "retroactive"  # source → origin


@pytest.mark.asyncio
async def test_backfill_is_idempotent():
    """Running twice over same input produces the same final state (MERGE semantics)."""
    d = _make_decision_orm()
    graph = _FakeGraphClient()

    await backfill_decisions(_fake_session_by_table(decisions=[d]), graph)
    first = len(graph.decisions)
    await backfill_decisions(_fake_session_by_table(decisions=[d]), graph)
    second = len(graph.decisions)

    assert first == second == 1


@pytest.mark.asyncio
async def test_satisfies_item_edges_from_jsonb_refs():
    """evidence_refs JSONB list of {type,id} dicts → one SATISFIES_ITEM edge per entry."""
    ev_id_1 = uuid.uuid4()
    ev_id_2 = uuid.uuid4()
    item = _make_checklist_orm(
        item_code="D-06-QUORUM",
        status="satisfied",
        evidence_refs=[
            {"type": "mom", "id": str(ev_id_1)},
            {"type": "mom", "id": str(ev_id_2)},
        ],
    )
    session = _fake_session_by_table(checklist=[item])
    graph = _FakeGraphClient()

    await backfill_decision_edges(session, graph)

    assert len(graph.satisfies_item) == 2
    evidence_ids_emitted = {edge[0] for edge in graph.satisfies_item}
    assert evidence_ids_emitted == {str(ev_id_1), str(ev_id_2)}


@pytest.mark.asyncio
async def test_malformed_evidence_refs_are_skipped_not_fatal():
    """Non-dict entries, missing 'id', or unparseable UUIDs are logged + skipped."""
    good_id = uuid.uuid4()
    item = _make_checklist_orm(
        evidence_refs=[
            {"type": "mom", "id": str(good_id)},  # good
            "not-a-dict",  # malformed
            {"type": "mom"},  # missing id
            {"type": "mom", "id": "not-a-uuid"},  # unparseable UUID
        ],
    )
    session = _fake_session_by_table(checklist=[item])
    graph = _FakeGraphClient()

    await backfill_decision_edges(session, graph)

    assert len(graph.satisfies_item) == 1
    assert graph.satisfies_item[0][0] == str(good_id)


@pytest.mark.asyncio
async def test_unknown_item_code_is_skipped_not_fatal():
    """Stale item_code not in BJRItemCode enum → log + skip, don't crash."""
    good = _make_checklist_orm(
        item_code="D-06-QUORUM",
        evidence_refs=[{"type": "mom", "id": str(uuid.uuid4())}],
    )
    stale = _make_checklist_orm(
        item_code="OLD-RENAMED-CODE",
        evidence_refs=[{"type": "mom", "id": str(uuid.uuid4())}],
    )
    session = _fake_session_by_table(checklist=[good, stale])
    graph = _FakeGraphClient()

    await backfill_decision_edges(session, graph)

    assert len(graph.satisfies_item) == 1  # good row landed, stale skipped


@pytest.mark.asyncio
async def test_backfill_all_end_to_end():
    """backfill_all wires decisions + SUPPORTED_BY + SATISFIES_ITEM."""
    d = _make_decision_orm()
    ev = _make_evidence_orm(decision_id=d.id, evidence_type="mom")
    item = _make_checklist_orm(
        decision_id=d.id,
        evidence_refs=[{"type": "mom", "id": str(ev.evidence_id)}],
    )
    session = _fake_session_by_table(decisions=[d], evidence=[ev], checklist=[item])
    graph = _FakeGraphClient()

    stats = await backfill_all(session, graph)

    assert stats == {"decisions": 1, "edges": 2}
    assert len(graph.decisions) == 1
    assert len(graph.supported_by) == 1
    assert len(graph.satisfies_item) == 1
