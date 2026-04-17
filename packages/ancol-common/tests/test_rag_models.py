"""Tests for BJR-specific graph data models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

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


def test_decision_node_required_fields() -> None:
    node = DecisionNode(
        id=uuid.uuid4(),
        title="Divestasi Hotel Jaya",
        status=DecisionStatus.BJR_LOCKED.value,
        readiness_score=94.0,
        corporate_score=94.0,
        regional_score=96.0,
        locked_at=datetime(2026, 4, 1, tzinfo=UTC),
        initiative_type="divestment",
        origin="proactive",
    )
    assert node.is_locked is True


def test_decision_node_unlocked_state() -> None:
    node = DecisionNode(
        id=uuid.uuid4(),
        title="Akuisisi X",
        status=DecisionStatus.DD_IN_PROGRESS.value,
        readiness_score=None,
        corporate_score=None,
        regional_score=None,
        locked_at=None,
        initiative_type="acquisition",
        origin="proactive",
    )
    assert node.is_locked is False


def test_evidence_node_valid_type() -> None:
    node = EvidenceNode(id=uuid.uuid4(), type="mom")
    assert node.type == "mom"


def test_evidence_node_rejects_empty_type() -> None:
    with pytest.raises(ValueError, match="type"):
        EvidenceNode(id=uuid.uuid4(), type="")


def test_document_indicator_items() -> None:
    decision_id = uuid.uuid4()
    indicator = DocumentIndicator(
        decision_id=decision_id,
        decision_title="Acquisition X",
        status=DecisionStatus.DD_IN_PROGRESS.value,
        readiness_score=72.0,
        is_locked=False,
        locked_at=None,
        satisfied_items=[BJRItemCode.D_06_QUORUM],
        missing_items=[BJRItemCode.PD_01_DD, BJRItemCode.PD_05_COI],
        origin="proactive",
    )
    assert len(indicator.satisfied_items) == 1
    assert len(indicator.missing_items) == 2
    # Emoji state helper
    assert indicator.state_emoji == "🟡"


def test_document_indicator_locked_emoji() -> None:
    indicator = DocumentIndicator(
        decision_id=uuid.uuid4(),
        decision_title="Locked decision",
        status=DecisionStatus.BJR_LOCKED.value,
        readiness_score=95.0,
        is_locked=True,
        locked_at=datetime.now(UTC),
        satisfied_items=[],
        missing_items=[],
        origin="proactive",
    )
    assert indicator.state_emoji == "🔒"


def test_evidence_summary_groups_by_item() -> None:
    ev_id = uuid.uuid4()
    summary = EvidenceSummary(
        evidence_id=ev_id,
        evidence_type="mom",
        title="MoM BOD #5/2026",
        satisfies_items=[BJRItemCode.D_06_QUORUM, BJRItemCode.D_07_SIGNED],
    )
    assert BJRItemCode.D_06_QUORUM in summary.satisfies_items


def test_gate5_half_values() -> None:
    assert Gate5Half.KOMISARIS == "komisaris"
    assert Gate5Half.LEGAL == "legal"
