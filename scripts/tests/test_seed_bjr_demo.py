"""Tests for scripts/seed_bjr_demo.py — shape, idempotency, phase mapping."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from ancol_common.schemas.bjr import BJRItemCode, ChecklistPhase

from scripts.seed_bjr_demo import (
    _CHECKLISTS,
    _DECISIONS,
    _EVIDENCE,
    DECISION_1_ID,
    DECISION_2_ID,
    DECISION_3_ID,
    _phase_for,
    seed_all,
)


def test_decisions_cover_three_distinct_lifecycle_states():
    """The 3 seeded decisions must demo the 3 distinct states."""
    statuses = {d["status"] for d in _DECISIONS}
    assert statuses == {"dd_in_progress", "bjr_locked", "ideation"}


def test_decisions_use_deterministic_ids():
    """IDs are stable across re-runs (enables idempotent check-then-insert)."""
    ids = [d["id"] for d in _DECISIONS]
    assert ids == [DECISION_1_ID, DECISION_2_ID, DECISION_3_ID]
    assert len(set(ids)) == 3


def test_locked_decision_has_locked_at_and_passport_uri():
    """Decision 2 (locked) must have locked_at + gcs_passport_uri so
    get_passport_url returns a real URL during demo."""
    locked = next(d for d in _DECISIONS if d["status"] == "bjr_locked")
    assert locked["is_bjr_locked"] is True
    assert locked["locked_at"] is not None
    assert locked["gcs_passport_uri"] is not None
    assert "gs://" in locked["gcs_passport_uri"]


def test_ideation_decision_has_no_scores():
    """Fresh-state decision has readiness=None so the UI emoji is ⚪."""
    fresh = next(d for d in _DECISIONS if d["status"] == "ideation")
    assert fresh["bjr_readiness_score"] is None
    assert fresh["corporate_compliance_score"] is None
    assert fresh["regional_compliance_score"] is None


def test_in_progress_decision_has_dual_regime_scores():
    """Decision 1 demonstrates dual-regime min() logic: corporate 72 < regional 88 = readiness 72."""
    in_progress = next(d for d in _DECISIONS if d["status"] == "dd_in_progress")
    assert in_progress["corporate_compliance_score"] == 72.0
    assert in_progress["regional_compliance_score"] == 88.0
    assert in_progress["bjr_readiness_score"] == 72.0  # min() of the two


def test_phase_mapping_covers_all_16_codes():
    """_phase_for maps each BJRItemCode to a valid phase string."""
    valid_phases = {p.value for p in ChecklistPhase}
    for code in BJRItemCode:
        assert _phase_for(code) in valid_phases, f"Unknown phase for {code}"


def test_phase_mapping_pre_decision():
    for code in [BJRItemCode.PD_01_DD, BJRItemCode.PD_02_FS, BJRItemCode.PD_03_RKAB]:
        assert _phase_for(code) == ChecklistPhase.PRE_DECISION.value


def test_phase_mapping_decision():
    for code in [BJRItemCode.D_06_QUORUM, BJRItemCode.D_07_SIGNED, BJRItemCode.D_11_DISCLOSE]:
        assert _phase_for(code) == ChecklistPhase.DECISION.value


def test_phase_mapping_post_decision():
    for code in [BJRItemCode.POST_12_MONITOR, BJRItemCode.POST_16_ARCHIVE]:
        assert _phase_for(code) == ChecklistPhase.POST_DECISION.value


def test_each_decision_has_exactly_16_checklist_items():
    """All 16 BJRItemCode values must be present per decision (the stable-contract rule)."""
    for decision_id, items in _CHECKLISTS.items():
        codes = {item[0] for item in items}
        assert len(codes) == 16, f"decision {decision_id} missing codes: {set(BJRItemCode) - codes}"
        assert codes == set(BJRItemCode)


def test_locked_decision_has_all_items_satisfied_or_waived():
    """Decision 2 is locked — every checklist item must be SATISFIED or WAIVED (no flagged, no in_progress)."""
    items = _CHECKLISTS[DECISION_2_ID]
    statuses = {item[1].value for item in items}
    assert statuses.issubset({"satisfied", "waived"})


def test_in_progress_decision_has_flagged_critical():
    """Decision 1 demonstrates 'what's missing' chat response — must have at least one flagged CRITICAL item."""
    from ancol_common.schemas.bjr import CRITICAL_ITEMS

    items = _CHECKLISTS[DECISION_1_ID]
    flagged_critical = [
        code for code, status, _ in items if status.value == "flagged" and code in CRITICAL_ITEMS
    ]
    assert len(flagged_critical) >= 1, (
        "Decision 1 must have at least one flagged CRITICAL item for demo"
    )


def test_evidence_references_valid_decisions():
    """Every seeded evidence row points to one of the 3 seeded decisions."""
    seeded_ids = {d["id"] for d in _DECISIONS}
    for ev in _EVIDENCE:
        assert ev["decision_id"] in seeded_ids


def test_evidence_type_values_are_valid():
    """evidence_type must be one of the Enum values in DecisionEvidenceRecord."""
    valid = {
        "mom",
        "contract",
        "dd_report",
        "fs_report",
        "spi_report",
        "audit_committee_report",
        "ojk_disclosure",
        "organ_approval",
        "rkab_line",
        "rjpp_theme",
    }
    for ev in _EVIDENCE:
        assert ev["evidence_type"] in valid


def test_checklist_evidence_refs_use_string_uuids():
    """evidence_refs JSONB dict uses str(uuid), per BJRChecklistItemRecord contract."""
    for items in _CHECKLISTS.values():
        for _, _, refs in items:
            for ref in refs:
                assert "type" in ref and "id" in ref
                # Should parse as UUID
                uuid.UUID(ref["id"])


@pytest.mark.asyncio
async def test_seed_all_is_idempotent_on_existing_rows():
    """When all rows already exist, seed_all returns zero inserts."""
    session = AsyncMock()

    # session.get → existing decision
    session.get = AsyncMock(return_value=MagicMock())  # non-None = exists

    # select(DecisionEvidenceRecord)... → existing row
    async def fake_execute(stmt, *a, **k):
        result = MagicMock()
        result.scalar_one_or_none.return_value = MagicMock()  # exists
        return result

    session.execute = fake_execute
    session.add = MagicMock()
    session.flush = AsyncMock()

    stats = await seed_all(session)

    assert stats == {"decisions": 0, "evidence": 0, "checklist": 0}
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_seed_all_inserts_everything_on_empty_db():
    """When nothing exists yet, seed_all inserts all 3 + 7 + 48 rows."""
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)  # nothing exists

    async def fake_execute(stmt, *a, **k):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None  # nothing exists
        return result

    session.execute = fake_execute
    session.add = MagicMock()
    session.flush = AsyncMock()

    stats = await seed_all(session)

    assert stats["decisions"] == 3
    assert stats["evidence"] == 7
    assert stats["checklist"] == 48  # 3 decisions x 16 items
    # Total .add() calls = 3 + 7 + 48 = 58
    assert session.add.call_count == 58
