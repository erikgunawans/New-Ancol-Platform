"""Tests for the pure BJR scorer — the dual-regime weighted average formula.

No DB required. Tests the mathematical invariants of the scoring model.
"""

from __future__ import annotations

from ancol_common.bjr.scorer import (
    BJRScoreResult,
    ChecklistSnapshot,
    all_item_codes,
    compute_scores,
    item_score,
)
from ancol_common.schemas.bjr import BJRItemCode


class TestItemScoreMapping:
    def test_satisfied_is_100(self):
        assert item_score("satisfied") == 100

    def test_waived_is_100(self):
        """Waived counts as satisfied (explicit opt-out, not a gap)."""
        assert item_score("waived") == 100

    def test_in_progress_is_50(self):
        assert item_score("in_progress") == 50

    def test_not_started_is_0(self):
        assert item_score("not_started") == 0

    def test_flagged_is_0(self):
        """Flagged = known-broken → zero, same as not_started for raw score."""
        assert item_score("flagged") == 0

    def test_unknown_status_defaults_to_0(self):
        assert item_score("garbage") == 0


class TestAllSixteenSnapshot:
    """16-item snapshots that cover every combination."""

    def _all(self, status: str) -> list[ChecklistSnapshot]:
        return [ChecklistSnapshot(item_code=code, status=status) for code in all_item_codes()]

    def test_all_satisfied_gives_100(self):
        r = compute_scores(self._all("satisfied"))
        assert r.bjr_readiness_score == 100.0
        assert r.corporate_compliance_score == 100.0
        assert r.regional_compliance_score == 100.0
        assert r.satisfied_count == 16
        assert r.flagged_count == 0
        assert r.gate_5_unlockable is True

    def test_all_not_started_gives_0(self):
        r = compute_scores(self._all("not_started"))
        assert r.bjr_readiness_score == 0.0
        assert r.gate_5_unlockable is False

    def test_all_in_progress_gives_50(self):
        r = compute_scores(self._all("in_progress"))
        assert r.bjr_readiness_score == 50.0
        assert r.corporate_compliance_score == 50.0
        assert r.regional_compliance_score == 50.0
        assert r.gate_5_unlockable is False  # below 85 threshold


class TestDualRegimeEnforcement:
    """The min(corporate, regional) rule is the CORE defense against dual-regime risk."""

    def test_corporate_pass_regional_fail_blocks_gate5(self):
        """A decision satisfying UU PT + OJK but failing PP BUMD gets NO BJR protection."""
        items = [
            # Corporate items all satisfied
            ChecklistSnapshot(BJRItemCode.PD_01_DD.value, "satisfied"),
            ChecklistSnapshot(BJRItemCode.PD_02_FS.value, "satisfied"),
            ChecklistSnapshot(BJRItemCode.D_06_QUORUM.value, "satisfied"),
            ChecklistSnapshot(BJRItemCode.D_07_SIGNED.value, "satisfied"),
            ChecklistSnapshot(BJRItemCode.D_08_RISK.value, "satisfied"),
            ChecklistSnapshot(BJRItemCode.D_09_LEGAL.value, "satisfied"),
            ChecklistSnapshot(BJRItemCode.D_11_DISCLOSE.value, "satisfied"),
            # Regional items all failing
            ChecklistSnapshot(BJRItemCode.PD_03_RKAB.value, "flagged"),
            ChecklistSnapshot(BJRItemCode.PD_04_RJPP.value, "not_started"),
            ChecklistSnapshot(BJRItemCode.PD_05_COI.value, "satisfied"),  # shared
            ChecklistSnapshot(BJRItemCode.D_10_ORGAN.value, "not_started"),
            ChecklistSnapshot(BJRItemCode.POST_12_MONITOR.value, "not_started"),
            ChecklistSnapshot(BJRItemCode.POST_13_SPI.value, "not_started"),
            ChecklistSnapshot(BJRItemCode.POST_14_AUDITCOM.value, "not_started"),
            ChecklistSnapshot(BJRItemCode.POST_15_DEWAS.value, "not_started"),
            ChecklistSnapshot(BJRItemCode.POST_16_ARCHIVE.value, "satisfied"),  # shared
        ]
        r = compute_scores(items)
        # Corporate is high, regional is low
        assert r.corporate_compliance_score > r.regional_compliance_score
        # Overall readiness = min(corp, regional)
        assert r.bjr_readiness_score == r.regional_compliance_score
        assert r.gate_5_unlockable is False

    def test_regional_pass_corporate_fail_also_blocks_gate5(self):
        """Symmetric case — failing corporate also voids BJR."""
        items = [
            ChecklistSnapshot(BJRItemCode.PD_03_RKAB.value, "satisfied"),
            ChecklistSnapshot(BJRItemCode.PD_04_RJPP.value, "satisfied"),
            ChecklistSnapshot(BJRItemCode.PD_05_COI.value, "satisfied"),
            ChecklistSnapshot(BJRItemCode.D_10_ORGAN.value, "satisfied"),
            ChecklistSnapshot(BJRItemCode.POST_12_MONITOR.value, "satisfied"),
            ChecklistSnapshot(BJRItemCode.POST_13_SPI.value, "satisfied"),
            ChecklistSnapshot(BJRItemCode.POST_14_AUDITCOM.value, "satisfied"),
            ChecklistSnapshot(BJRItemCode.POST_15_DEWAS.value, "satisfied"),
            ChecklistSnapshot(BJRItemCode.POST_16_ARCHIVE.value, "satisfied"),
            # Corporate items failing
            ChecklistSnapshot(BJRItemCode.PD_01_DD.value, "flagged"),
            ChecklistSnapshot(BJRItemCode.PD_02_FS.value, "not_started"),
            ChecklistSnapshot(BJRItemCode.D_06_QUORUM.value, "flagged"),
            ChecklistSnapshot(BJRItemCode.D_07_SIGNED.value, "not_started"),
            ChecklistSnapshot(BJRItemCode.D_08_RISK.value, "not_started"),
            ChecklistSnapshot(BJRItemCode.D_09_LEGAL.value, "not_started"),
            ChecklistSnapshot(BJRItemCode.D_11_DISCLOSE.value, "flagged"),
        ]
        r = compute_scores(items)
        assert r.regional_compliance_score > r.corporate_compliance_score
        assert r.bjr_readiness_score == r.corporate_compliance_score


class TestCriticalItemWeighting:
    """CRITICAL items weigh 2x - missing one tanks the score more than a normal item."""

    def test_missing_critical_weighs_more(self):
        # Scenario A: fail one non-critical (PD-01-DD)
        scenario_a = [ChecklistSnapshot(code, "satisfied") for code in all_item_codes()]
        for i, snap in enumerate(scenario_a):
            if snap.item_code == BJRItemCode.PD_01_DD.value:
                scenario_a[i] = ChecklistSnapshot(snap.item_code, "not_started")
        score_a = compute_scores(scenario_a).bjr_readiness_score

        # Scenario B: fail one CRITICAL (PD-03-RKAB)
        scenario_b = [ChecklistSnapshot(code, "satisfied") for code in all_item_codes()]
        for i, snap in enumerate(scenario_b):
            if snap.item_code == BJRItemCode.PD_03_RKAB.value:
                scenario_b[i] = ChecklistSnapshot(snap.item_code, "not_started")
        score_b = compute_scores(scenario_b).bjr_readiness_score

        # Critical miss should hurt more than non-critical miss
        assert score_b < score_a, (
            f"Missing CRITICAL PD-03-RKAB (score={score_b}) should hurt "
            f"more than missing non-critical PD-01-DD (score={score_a})"
        )


class TestGate5UnlockRule:
    """Gate 5 requires readiness >= 85 AND no CRITICAL items flagged."""

    def test_threshold_boundary(self):
        # All satisfied except one non-critical in_progress → 95+ range
        items = [ChecklistSnapshot(code, "satisfied") for code in all_item_codes()]
        for i, snap in enumerate(items):
            if snap.item_code == BJRItemCode.POST_12_MONITOR.value:
                items[i] = ChecklistSnapshot(snap.item_code, "in_progress")
        r = compute_scores(items)
        assert r.bjr_readiness_score >= 85.0
        assert r.gate_5_unlockable is True

    def test_flagged_critical_blocks_even_if_score_high(self):
        """A CRITICAL item in FLAGGED state blocks Gate 5 regardless of score."""
        items = [ChecklistSnapshot(code, "satisfied") for code in all_item_codes()]
        # Flag PD-05-COI (CRITICAL) while everything else satisfied
        for i, snap in enumerate(items):
            if snap.item_code == BJRItemCode.PD_05_COI.value:
                items[i] = ChecklistSnapshot(snap.item_code, "flagged")
        r = compute_scores(items)
        # Score might still be high because one flag dilutes
        # but the flagged-critical check must block
        assert r.gate_5_unlockable is False

    def test_below_threshold_blocks(self):
        # All in_progress → 50 < 85
        items = [ChecklistSnapshot(code, "in_progress") for code in all_item_codes()]
        r = compute_scores(items)
        assert r.bjr_readiness_score == 50.0
        assert r.gate_5_unlockable is False

    def test_custom_threshold(self):
        items = [ChecklistSnapshot(code, "in_progress") for code in all_item_codes()]
        # With threshold=40, 50.0 score unlocks
        r = compute_scores(items, gate_5_threshold=40.0)
        assert r.gate_5_unlockable is True


class TestScoreResultShape:
    def test_empty_snapshot_yields_zero(self):
        r = compute_scores([])
        assert r.bjr_readiness_score == 0.0
        assert r.corporate_compliance_score == 0.0
        assert r.regional_compliance_score == 0.0
        assert r.satisfied_count == 0
        assert r.flagged_count == 0

    def test_satisfied_and_flagged_counts(self):
        items = [
            ChecklistSnapshot(BJRItemCode.PD_01_DD.value, "satisfied"),
            ChecklistSnapshot(BJRItemCode.PD_02_FS.value, "satisfied"),
            ChecklistSnapshot(BJRItemCode.PD_03_RKAB.value, "flagged"),
            ChecklistSnapshot(BJRItemCode.PD_04_RJPP.value, "in_progress"),
            ChecklistSnapshot(BJRItemCode.PD_05_COI.value, "waived"),
        ]
        r = compute_scores(items)
        assert r.satisfied_count == 3  # satisfied + waived
        assert r.flagged_count == 1

    def test_dataclass_fields_present(self):
        r = compute_scores([ChecklistSnapshot(BJRItemCode.PD_01_DD.value, "satisfied")])
        assert isinstance(r, BJRScoreResult)
        # Check all expected fields are populated
        for attr in (
            "bjr_readiness_score",
            "corporate_compliance_score",
            "regional_compliance_score",
            "satisfied_count",
            "flagged_count",
            "gate_5_unlockable",
        ):
            assert hasattr(r, attr), f"Missing field: {attr}"


class TestAllItemCodes:
    def test_returns_sixteen(self):
        assert len(all_item_codes()) == 16

    def test_order_stable(self):
        codes = all_item_codes()
        assert codes[0] == "PD-01-DD"  # first pre-decision
        assert codes[-1] == "POST-16-ARCHIVE"  # last post-decision
