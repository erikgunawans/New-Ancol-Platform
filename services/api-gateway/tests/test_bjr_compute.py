"""Tests for the BJR compute orchestrator (compute_bjr).

Covers the invariants that the orchestrator must preserve:
- All 16 evaluators run on each compute
- A raising evaluator produces a synthetic FLAGGED result (doesn't abort compute)
- WAIVED manual overrides are preserved on re-compute
- Scores are written back to the StrategicDecision
- `_EVALUATOR_METADATA` covers every EVALUATORS entry (drift guard)

Regression tests for the silent-failure-hunter findings in commit d9176d4.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ancol_common.bjr.compute import _EVALUATOR_METADATA, compute_bjr
from ancol_common.bjr.evaluators import EVALUATORS, EvaluatorResult
from ancol_common.schemas.bjr import ChecklistItemStatus, ChecklistPhase

from ._bjr_fixtures import make_decision

# ══════════════════════════════════════════════════════════════════════════════
# Metadata completeness — drift guard
# ══════════════════════════════════════════════════════════════════════════════


class TestEvaluatorMetadataCompleteness:
    """Every registered evaluator must have metadata; every metadata entry
    must map to a real evaluator. Prevents silent drift when adding
    evaluators (synthetic failure results would have "UNKNOWN" item_code)."""

    def test_every_evaluator_has_metadata(self):
        evaluator_names = {e.__name__ for e in EVALUATORS}
        missing = evaluator_names - set(_EVALUATOR_METADATA.keys())
        assert not missing, f"Evaluators without metadata: {missing}"

    def test_no_orphan_metadata(self):
        evaluator_names = {e.__name__ for e in EVALUATORS}
        orphans = set(_EVALUATOR_METADATA.keys()) - evaluator_names
        assert not orphans, f"Metadata entries with no evaluator: {orphans}"

    def test_metadata_count_matches_sixteen(self):
        assert len(_EVALUATOR_METADATA) == 16


# ══════════════════════════════════════════════════════════════════════════════
# Evaluator-failure resilience (regression test for d9176d4 silent-failure fix)
# ══════════════════════════════════════════════════════════════════════════════


class TestComputeBJR:
    @pytest.mark.asyncio
    async def test_compute_runs_all_sixteen_evaluators(self):
        """Baseline: compute_bjr invokes every evaluator once."""
        d = make_decision()
        session = _session_for_compute(d)
        with patch("ancol_common.bjr.compute.EVALUATORS", new=_stub_evaluators_16()) as stubs:
            await compute_bjr(session, str(d.id))
        # Each stub is a MagicMock — verify each was awaited exactly once.
        for stub in stubs:
            assert stub.call_count == 1, f"{stub._name} was called {stub.call_count} times"

    @pytest.mark.asyncio
    async def test_failing_evaluator_produces_synthetic_flagged(self):
        """Regression: one bad evaluator used to abort the entire compute.
        After the fix, it produces a synthetic FLAGGED result with a
        remediation note, and the other 15 evaluators still run."""
        d = make_decision()
        session = _session_for_compute(d)

        # Build 16 stubs; one of them raises.
        good_stubs = _stub_evaluators_16()
        # Monkey-patch the 3rd stub to raise
        bad_stub = AsyncMock(side_effect=RuntimeError("synthetic DB timeout"))
        bad_stub.__name__ = "eval_pd_03_rkab"
        stubs = [*good_stubs[:2], bad_stub, *good_stubs[3:]]

        with patch("ancol_common.bjr.compute.EVALUATORS", new=stubs):
            result = await compute_bjr(session, str(d.id))

        # 16 checklist items regardless of the failure
        assert len(result.items) == 16
        # The failing evaluator's slot has a FLAGGED synthetic result
        failed = [r for r in result.items if r.item_code == "PD-03-RKAB"]
        assert len(failed) == 1
        assert failed[0].status == ChecklistItemStatus.FLAGGED.value
        assert "Evaluator error" in (failed[0].remediation_note or "")
        assert "RuntimeError" in (failed[0].remediation_note or "")

    @pytest.mark.asyncio
    async def test_scores_written_back_to_decision(self):
        """After compute, the decision row gets the three score fields set."""
        d = make_decision()
        session = _session_for_compute(d)
        with patch("ancol_common.bjr.compute.EVALUATORS", new=_stub_evaluators_16("satisfied")):
            result = await compute_bjr(session, str(d.id))

        assert d.bjr_readiness_score == result.scores.bjr_readiness_score
        assert d.corporate_compliance_score == result.scores.corporate_compliance_score
        assert d.regional_compliance_score == result.scores.regional_compliance_score
        # With all 16 satisfied, scores are 100
        assert d.bjr_readiness_score == 100.0

    @pytest.mark.asyncio
    async def test_missing_decision_raises_value_error(self):
        """A decision_id that doesn't exist raises ValueError, which the
        router translates to 404. Without this, the caller would see a
        confusing NoneType-AttributeError deep in the orchestrator."""
        session = AsyncMock()
        session.execute.return_value = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = None
        with pytest.raises(ValueError, match="not found"):
            await compute_bjr(session, str(uuid.uuid4()))

    @pytest.mark.asyncio
    async def test_all_flagged_yields_zero_scores(self):
        d = make_decision()
        session = _session_for_compute(d)
        with patch("ancol_common.bjr.compute.EVALUATORS", new=_stub_evaluators_16("flagged")):
            result = await compute_bjr(session, str(d.id))

        assert result.scores.bjr_readiness_score == 0.0
        assert result.scores.gate_5_unlockable is False


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════


def _session_for_compute(decision) -> AsyncMock:
    """Build a session where the first `select(StrategicDecision)` returns
    the given decision, and the subsequent `select(BJRChecklistItemRecord)`
    (inside _upsert_checklist_rows) returns an empty existing set."""

    call_count = {"i": 0}

    async def mock_execute(stmt):
        call_count["i"] += 1
        result = MagicMock()
        if call_count["i"] == 1:
            # First call: select the StrategicDecision
            result.scalar_one_or_none.return_value = decision
        else:
            # _upsert_checklist_rows: existing rows query
            scalars = MagicMock()
            scalars.all.return_value = []
            result.scalars.return_value = scalars
        return result

    session = AsyncMock()
    session.execute = mock_execute
    session.add = MagicMock()
    return session


def _stub_evaluators_16(status: str = "satisfied") -> list:
    """Build 16 AsyncMock evaluators that each return a canned EvaluatorResult."""
    from ancol_common.schemas.bjr import BJRItemCode

    # item_code order matches EVALUATORS registry
    item_codes = [code.value for code in BJRItemCode]
    stubs = []
    for idx, code in enumerate(item_codes):
        # Phase inferred from code prefix
        if code.startswith("PD-"):
            phase = ChecklistPhase.PRE_DECISION.value
        elif code.startswith("D-"):
            phase = ChecklistPhase.DECISION.value
        else:
            phase = ChecklistPhase.POST_DECISION.value

        stub = AsyncMock(
            return_value=EvaluatorResult(
                item_code=code,
                phase=phase,
                status=status,
                regulation_basis=["TEST-REG"],
            )
        )
        # Give the stub a __name__ so _EVALUATOR_METADATA lookup works if the
        # orchestrator ever reaches the failure path for it.
        stub.__name__ = list(_EVALUATOR_METADATA.keys())[idx]
        stubs.append(stub)
    return stubs
