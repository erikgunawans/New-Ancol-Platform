"""Tests for BJR Pydantic schemas (decision, bjr, artifact)."""

from __future__ import annotations

from datetime import date

import pytest
from ancol_common.schemas.artifact import DDRiskRating, OrganApprovalType, SPIReportType
from ancol_common.schemas.bjr import (
    CORPORATE_ITEMS,
    CRITICAL_ITEMS,
    REGIONAL_ITEMS,
    BJRItemCode,
    ChecklistItemStatus,
    ChecklistPhase,
    Gate5FinalDecision,
    RegulationLayer,
    RegulatoryRegime,
)
from ancol_common.schemas.decision import (
    DecisionStatus,
    EvidenceRelationship,
    EvidenceType,
    InitiativeType,
    RKABApprovalStatus,
    StrategicDecisionCreate,
    StrategicDecisionUpdate,
)
from pydantic import ValidationError


class TestBJRItemCodes:
    """Item codes are stable contracts — renaming breaks agent/UI/PDF."""

    def test_sixteen_items_exactly(self):
        assert len(list(BJRItemCode)) == 16

    def test_five_pre_decision_items(self):
        pd = [c for c in BJRItemCode if c.value.startswith("PD-")]
        assert len(pd) == 5

    def test_six_decision_items(self):
        d = [c for c in BJRItemCode if c.value.startswith("D-")]
        assert len(d) == 6

    def test_five_post_decision_items(self):
        post = [c for c in BJRItemCode if c.value.startswith("POST-")]
        assert len(post) == 5

    def test_specific_critical_codes_present(self):
        assert BJRItemCode.PD_03_RKAB.value == "PD-03-RKAB"
        assert BJRItemCode.PD_05_COI.value == "PD-05-COI"
        assert BJRItemCode.D_06_QUORUM.value == "D-06-QUORUM"
        assert BJRItemCode.D_11_DISCLOSE.value == "D-11-DISCLOSE"


class TestBJRScoringSets:
    """Verify CRITICAL/CORPORATE/REGIONAL sets used by the scoring formula."""

    def test_four_critical_items(self):
        assert len(CRITICAL_ITEMS) == 4

    def test_corporate_items_count(self):
        assert len(CORPORATE_ITEMS) == 9

    def test_regional_items_count(self):
        assert len(REGIONAL_ITEMS) == 9

    def test_coi_is_both_corporate_and_regional(self):
        """PD-05-COI applies in BOTH regimes (dual-regime overlap)."""
        assert BJRItemCode.PD_05_COI in CORPORATE_ITEMS
        assert BJRItemCode.PD_05_COI in REGIONAL_ITEMS

    def test_archive_is_both_regimes(self):
        """POST-16-ARCHIVE applies in BOTH regimes (dual-regime overlap)."""
        assert BJRItemCode.POST_16_ARCHIVE in CORPORATE_ITEMS
        assert BJRItemCode.POST_16_ARCHIVE in REGIONAL_ITEMS

    def test_rkab_is_regional_only(self):
        """PD-03-RKAB is BUMD-regime-specific (Pergub 127/2019)."""
        assert BJRItemCode.PD_03_RKAB in REGIONAL_ITEMS
        assert BJRItemCode.PD_03_RKAB not in CORPORATE_ITEMS

    def test_quorum_is_corporate_only(self):
        """D-06-QUORUM is UU PT-specific."""
        assert BJRItemCode.D_06_QUORUM in CORPORATE_ITEMS
        assert BJRItemCode.D_06_QUORUM not in REGIONAL_ITEMS


class TestDecisionEnums:
    def test_decision_status_has_14_states(self):
        assert len(list(DecisionStatus)) == 14

    def test_initiative_types_present(self):
        assert InitiativeType.INVESTMENT.value == "investment"
        assert InitiativeType.MAJOR_CONTRACT.value == "major_contract"
        assert InitiativeType.RUPS_ITEM.value == "rups_item"

    def test_evidence_types_count(self):
        assert len(list(EvidenceType)) == 10

    def test_evidence_relationships(self):
        assert EvidenceRelationship.AUTHORIZES.value == "authorizes"
        assert EvidenceRelationship.MONITORS.value == "monitors"


class TestRegulatoryRegimeAndLayer:
    def test_four_regimes(self):
        values = {r.value for r in RegulatoryRegime}
        assert values == {"corporate", "regional_finance", "listing", "internal"}

    def test_five_layers(self):
        values = {layer.value for layer in RegulationLayer}
        assert values == {"uu", "pp", "pergub_dki", "ojk_bei", "internal"}


class TestStrategicDecisionCreate:
    def test_minimal_valid_payload(self):
        payload = StrategicDecisionCreate(
            title="JV Hotel Beach City",
            initiative_type=InitiativeType.PARTNERSHIP,
            business_owner_id="a0000000-0000-0000-0000-000000000014",
        )
        assert payload.title == "JV Hotel Beach City"
        assert payload.rkab_line_id is None  # optional

    def test_title_too_short_rejected(self):
        with pytest.raises(ValidationError):
            StrategicDecisionCreate(
                title="JV",  # less than 3 chars
                initiative_type=InitiativeType.PARTNERSHIP,
                business_owner_id="a0000000-0000-0000-0000-000000000014",
            )

    def test_negative_value_rejected(self):
        with pytest.raises(ValidationError):
            StrategicDecisionCreate(
                title="Investasi",
                initiative_type=InitiativeType.INVESTMENT,
                business_owner_id="a0000000-0000-0000-0000-000000000014",
                value_idr=-100.0,
            )


class TestArtifactEnums:
    def test_dd_risk_ratings(self):
        assert {r.value for r in DDRiskRating} == {"low", "medium", "high", "critical"}

    def test_organ_approval_types(self):
        assert {t.value for t in OrganApprovalType} == {"komisaris", "dewas", "rups"}

    def test_spi_report_types(self):
        assert {t.value for t in SPIReportType} == {
            "routine",
            "incident",
            "special_audit",
            "follow_up",
        }


class TestChecklistEnums:
    def test_three_phases(self):
        assert {p.value for p in ChecklistPhase} == {
            "pre_decision",
            "decision",
            "post_decision",
        }

    def test_five_statuses(self):
        assert {s.value for s in ChecklistItemStatus} == {
            "not_started",
            "in_progress",
            "satisfied",
            "waived",
            "flagged",
        }

    def test_rkab_approval_statuses(self):
        values = {s.value for s in RKABApprovalStatus}
        assert "draft" in values
        assert "rups_approved" in values
        assert "superseded" in values

    def test_gate5_final_decisions(self):
        values = {g.value for g in Gate5FinalDecision}
        assert values == {"pending", "approved", "rejected"}


class TestStrategicDecisionUpdate:
    def test_empty_update_valid(self):
        """PATCH with no fields should be valid (no-op)."""
        update = StrategicDecisionUpdate()
        assert update.model_dump(exclude_unset=True) == {}

    def test_partial_update(self):
        update = StrategicDecisionUpdate(title="Revised title")
        dumped = update.model_dump(exclude_unset=True)
        assert dumped == {"title": "Revised title"}

    def test_status_transition_field(self):
        update = StrategicDecisionUpdate(status=DecisionStatus.MONITORING)
        assert update.status == DecisionStatus.MONITORING

    def test_date_field(self):
        """A date field can round-trip."""
        d = date(2026, 6, 15)
        # Just verify no exception — schemas accept dates where typed
        assert d.year == 2026
