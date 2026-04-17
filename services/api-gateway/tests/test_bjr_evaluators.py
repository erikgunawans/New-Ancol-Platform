"""Tests for the 16 BJR evaluators.

Focuses on the 4 CRITICAL items (PD-03-RKAB, PD-05-COI, D-06-QUORUM,
D-11-DISCLOSE) and the regression tests for the silent-failure bugs that
were fixed in the 6-agent pr-review-toolkit pass (commit d9176d4). The
non-critical evaluators (PD-01/02/04, D-07/08/09/10, POST-12 through 16)
are covered at the pattern level via the compute orchestrator tests.
"""

from __future__ import annotations

import pytest
from ancol_common.bjr.evaluators import (
    EvaluationContext,
    _extract_bool_field,
    eval_d_06_quorum,
    eval_d_07_signed,
    eval_d_11_disclose,
    eval_pd_01_dd,
    eval_pd_03_rkab,
    eval_pd_04_rjpp,
    eval_pd_05_coi,
)
from ancol_common.schemas.bjr import ChecklistItemStatus

from ._bjr_fixtures import (
    fake_session,
    make_dd_report,
    make_decision,
    make_extraction,
    make_material_disclosure,
    make_rjpp,
    make_rkab,
    make_rpt_entity,
)

# ══════════════════════════════════════════════════════════════════════════════
# _extract_bool_field — pure helper; regression tests for missing-vs-False fix
# ══════════════════════════════════════════════════════════════════════════════


class TestExtractBoolField:
    """Before the fix, missing field and explicit False were conflated."""

    def test_none_structured_mom_returns_none(self):
        assert _extract_bool_field(None, "quorum_met") is None

    def test_missing_key_returns_none(self):
        assert _extract_bool_field({}, "quorum_met") is None

    def test_explicit_true_returns_true(self):
        assert _extract_bool_field({"quorum_met": True}, "quorum_met") is True

    def test_explicit_false_returns_false(self):
        assert _extract_bool_field({"quorum_met": False}, "quorum_met") is False

    def test_non_bool_returns_none(self):
        """Defensive: stringly-typed booleans in malformed JSONB should NOT
        be treated as True/False. Return None so the evaluator falls through
        to NOT_STARTED with 're-extract' remediation."""
        assert _extract_bool_field({"quorum_met": "true"}, "quorum_met") is None
        assert _extract_bool_field({"quorum_met": 1}, "quorum_met") is None
        assert _extract_bool_field({"quorum_met": None}, "quorum_met") is None


# ══════════════════════════════════════════════════════════════════════════════
# PD-01-DD — baseline evaluator pattern (non-critical but simplest)
# ══════════════════════════════════════════════════════════════════════════════


class TestPD01DueDiligence:
    @pytest.mark.asyncio
    async def test_no_dd_report_not_started(self):
        d = make_decision()
        ctx = EvaluationContext(decision=d, session=fake_session(DueDiligenceReport=[]))
        result = await eval_pd_01_dd(ctx)
        assert result.status == ChecklistItemStatus.NOT_STARTED.value
        assert "upload" in (result.remediation_note or "").lower()

    @pytest.mark.asyncio
    async def test_unreviewed_dd_report_in_progress(self):
        d = make_decision()
        dd = make_dd_report(d.id, reviewed_by_legal=None)
        ctx = EvaluationContext(decision=d, session=fake_session(DueDiligenceReport=[dd]))
        result = await eval_pd_01_dd(ctx)
        assert result.status == ChecklistItemStatus.IN_PROGRESS.value
        assert "legal review" in (result.remediation_note or "").lower()

    @pytest.mark.asyncio
    async def test_reviewed_dd_report_satisfied(self):
        import uuid

        d = make_decision()
        dd = make_dd_report(d.id, reviewed_by_legal=uuid.uuid4())
        ctx = EvaluationContext(decision=d, session=fake_session(DueDiligenceReport=[dd]))
        result = await eval_pd_01_dd(ctx)
        assert result.status == ChecklistItemStatus.SATISFIED.value
        assert result.remediation_note is None


# ══════════════════════════════════════════════════════════════════════════════
# PD-03-RKAB (CRITICAL) — the "not in RKAB = void BJR" rule
# ══════════════════════════════════════════════════════════════════════════════


class TestPD03RKAB:
    @pytest.mark.asyncio
    async def test_no_rkab_link_flagged_critical(self):
        """A decision not linked to ANY RKAB line is FLAGGED (not NOT_STARTED) —
        this is the #1 strategic risk from the BJR matrix."""
        d = make_decision(rkab_line_id=None)
        ctx = EvaluationContext(decision=d, session=fake_session())
        result = await eval_pd_03_rkab(ctx)
        assert result.status == ChecklistItemStatus.FLAGGED.value
        assert "void BJR protection" in (result.remediation_note or "")

    @pytest.mark.asyncio
    async def test_rkab_link_points_to_missing_row_flagged(self):
        import uuid

        d = make_decision(rkab_line_id=uuid.uuid4())
        # No RKABLineItem with that id — FK integrity gap
        ctx = EvaluationContext(decision=d, session=fake_session(RKABLineItem=[]))
        result = await eval_pd_03_rkab(ctx)
        assert result.status == ChecklistItemStatus.FLAGGED.value
        assert "data integrity" in (result.remediation_note or "").lower()

    @pytest.mark.asyncio
    async def test_rkab_draft_status_in_progress(self):
        rkab = make_rkab(approval_status="draft")
        d = make_decision(rkab_line_id=rkab.id)
        ctx = EvaluationContext(decision=d, session=fake_session(RKABLineItem=[rkab]))
        result = await eval_pd_03_rkab(ctx)
        assert result.status == ChecklistItemStatus.IN_PROGRESS.value
        assert "needs RUPS approval" in (result.remediation_note or "")

    @pytest.mark.asyncio
    async def test_rkab_rups_approved_satisfied(self):
        rkab = make_rkab(approval_status="rups_approved")
        d = make_decision(rkab_line_id=rkab.id)
        ctx = EvaluationContext(decision=d, session=fake_session(RKABLineItem=[rkab]))
        result = await eval_pd_03_rkab(ctx)
        assert result.status == ChecklistItemStatus.SATISFIED.value

    @pytest.mark.asyncio
    async def test_rkab_dewas_approved_also_satisfied(self):
        """RKAB is approved via either RUPS or Dewas — both unlock the checklist."""
        rkab = make_rkab(approval_status="dewas_approved")
        d = make_decision(rkab_line_id=rkab.id)
        ctx = EvaluationContext(decision=d, session=fake_session(RKABLineItem=[rkab]))
        result = await eval_pd_03_rkab(ctx)
        assert result.status == ChecklistItemStatus.SATISFIED.value


# ══════════════════════════════════════════════════════════════════════════════
# PD-04-RJPP — regression tests for the inactive-theme acceptance bug
# ══════════════════════════════════════════════════════════════════════════════


class TestPD04RJPP:
    @pytest.mark.asyncio
    async def test_no_rjpp_link_not_started(self):
        d = make_decision(rjpp_theme_id=None)
        ctx = EvaluationContext(decision=d, session=fake_session())
        result = await eval_pd_04_rjpp(ctx)
        assert result.status == ChecklistItemStatus.NOT_STARTED.value

    @pytest.mark.asyncio
    async def test_rjpp_link_points_to_missing_flagged(self):
        import uuid

        d = make_decision(rjpp_theme_id=uuid.uuid4())
        ctx = EvaluationContext(decision=d, session=fake_session(RJPPTheme=[]))
        result = await eval_pd_04_rjpp(ctx)
        assert result.status == ChecklistItemStatus.FLAGGED.value
        assert "missing row" in (result.remediation_note or "").lower()

    @pytest.mark.asyncio
    async def test_inactive_rjpp_flagged(self):
        """Regression: before /codex review, an inactive/superseded theme
        silently marked the item SATISFIED, overstating compliance."""
        theme = make_rjpp(is_active=False)
        d = make_decision(rjpp_theme_id=theme.id)
        ctx = EvaluationContext(decision=d, session=fake_session(RJPPTheme=[theme]))
        result = await eval_pd_04_rjpp(ctx)
        assert result.status == ChecklistItemStatus.FLAGGED.value
        assert "inactive" in (result.remediation_note or "").lower()

    @pytest.mark.asyncio
    async def test_active_rjpp_satisfied(self):
        theme = make_rjpp(is_active=True)
        d = make_decision(rjpp_theme_id=theme.id)
        ctx = EvaluationContext(decision=d, session=fake_session(RJPPTheme=[theme]))
        result = await eval_pd_04_rjpp(ctx)
        assert result.status == ChecklistItemStatus.SATISFIED.value


# ══════════════════════════════════════════════════════════════════════════════
# PD-05-COI (CRITICAL) — regression tests for the silent-failure bug
# ══════════════════════════════════════════════════════════════════════════════


class TestPD05COI:
    """The silent failure: before d9176d4, a corrupt `attendees` JSONB
    blob made PD-05 return SATISFIED even though the COI scan never ran."""

    @pytest.mark.asyncio
    async def test_no_linked_mom_not_started(self):
        d = make_decision()
        ctx = EvaluationContext(
            decision=d,
            session=fake_session(
                DecisionEvidenceRecord=[],
                Extraction=[],
                RelatedPartyEntity=[],
            ),
        )
        result = await eval_pd_05_coi(ctx)
        assert result.status == ChecklistItemStatus.NOT_STARTED.value

    @pytest.mark.asyncio
    async def test_malformed_attendees_flagged(self):
        """BEFORE FIX: malformed attendees → SATISFIED (false pass)
        AFTER FIX: malformed attendees → FLAGGED with explicit remediation"""
        import uuid

        d = make_decision()
        doc_id = uuid.uuid4()
        # Link a MoM to the decision
        evidence = _make_evidence_link(d.id, "mom", doc_id)
        # Attendees is a malformed string instead of list/dict
        ext = make_extraction(doc_id, attendees="corrupt data")
        ctx = EvaluationContext(
            decision=d,
            session=fake_session(
                DecisionEvidenceRecord=[evidence],
                Extraction=[ext],
                RelatedPartyEntity=[],
            ),
        )
        result = await eval_pd_05_coi(ctx)
        assert result.status == ChecklistItemStatus.FLAGGED.value
        assert "malformed" in (result.remediation_note or "").lower()

    @pytest.mark.asyncio
    async def test_rpt_match_flagged(self):
        import uuid

        d = make_decision()
        doc_id = uuid.uuid4()
        evidence = _make_evidence_link(d.id, "mom", doc_id)
        ext = make_extraction(
            doc_id,
            attendees=[{"name": "PT Anak Perusahaan Ancol"}, {"name": "Budi Santoso"}],
        )
        rpt = make_rpt_entity("PT Anak Perusahaan Ancol")
        ctx = EvaluationContext(
            decision=d,
            session=fake_session(
                DecisionEvidenceRecord=[evidence],
                Extraction=[ext],
                RelatedPartyEntity=[rpt],
            ),
        )
        result = await eval_pd_05_coi(ctx)
        assert result.status == ChecklistItemStatus.FLAGGED.value
        assert "Potential COI" in (result.remediation_note or "")

    @pytest.mark.asyncio
    async def test_short_rpt_name_no_false_positive(self):
        """Regression: before the 4-char minimum filter, an RPT named 'PT'
        would match every attendee whose title contained 'PT'."""
        import uuid

        d = make_decision()
        doc_id = uuid.uuid4()
        evidence = _make_evidence_link(d.id, "mom", doc_id)
        ext = make_extraction(
            doc_id,
            attendees=[{"name": "Budi Santoso"}, {"name": "Siti Aminah"}],
        )
        # "PT" is 2 chars — MUST NOT match attendees
        rpt_short = make_rpt_entity("PT")
        ctx = EvaluationContext(
            decision=d,
            session=fake_session(
                DecisionEvidenceRecord=[evidence],
                Extraction=[ext],
                RelatedPartyEntity=[rpt_short],
            ),
        )
        result = await eval_pd_05_coi(ctx)
        assert result.status == ChecklistItemStatus.SATISFIED.value

    @pytest.mark.asyncio
    async def test_clean_attendees_satisfied(self):
        import uuid

        d = make_decision()
        doc_id = uuid.uuid4()
        evidence = _make_evidence_link(d.id, "mom", doc_id)
        ext = make_extraction(
            doc_id,
            attendees=[{"name": "Budi Santoso"}, {"name": "Siti Aminah"}],
        )
        rpt = make_rpt_entity("PT Totally Unrelated Company")
        ctx = EvaluationContext(
            decision=d,
            session=fake_session(
                DecisionEvidenceRecord=[evidence],
                Extraction=[ext],
                RelatedPartyEntity=[rpt],
            ),
        )
        result = await eval_pd_05_coi(ctx)
        assert result.status == ChecklistItemStatus.SATISFIED.value


# ══════════════════════════════════════════════════════════════════════════════
# D-06-QUORUM (CRITICAL) — regression tests for missing-vs-False fix
# ══════════════════════════════════════════════════════════════════════════════


class TestD06Quorum:
    """Before fix: missing quorum_met field was treated identically to
    explicit False, conflating 'data gap' with 'confirmed violation'."""

    @pytest.mark.asyncio
    async def test_missing_quorum_met_field_not_started(self):
        """Extraction has no quorum_met key — data gap, needs re-extract."""
        import uuid

        d = make_decision()
        doc_id = uuid.uuid4()
        evidence = _make_evidence_link(d.id, "mom", doc_id)
        ext = make_extraction(doc_id, quorum_met=None)  # field absent
        ctx = EvaluationContext(
            decision=d,
            session=fake_session(
                DecisionEvidenceRecord=[evidence],
                Extraction=[ext],
            ),
        )
        result = await eval_d_06_quorum(ctx)
        assert result.status == ChecklistItemStatus.NOT_STARTED.value
        assert "re-extract" in (result.remediation_note or "").lower()

    @pytest.mark.asyncio
    async def test_explicit_false_flagged(self):
        """Extraction explicitly says False — real violation."""
        import uuid

        d = make_decision()
        doc_id = uuid.uuid4()
        evidence = _make_evidence_link(d.id, "mom", doc_id)
        ext = make_extraction(doc_id, quorum_met=False)
        ctx = EvaluationContext(
            decision=d,
            session=fake_session(
                DecisionEvidenceRecord=[evidence],
                Extraction=[ext],
            ),
        )
        result = await eval_d_06_quorum(ctx)
        assert result.status == ChecklistItemStatus.FLAGGED.value
        assert "did not meet quorum" in (result.remediation_note or "").lower()

    @pytest.mark.asyncio
    async def test_explicit_true_satisfied(self):
        import uuid

        d = make_decision()
        doc_id = uuid.uuid4()
        evidence = _make_evidence_link(d.id, "mom", doc_id)
        ext = make_extraction(doc_id, quorum_met=True)
        ctx = EvaluationContext(
            decision=d,
            session=fake_session(
                DecisionEvidenceRecord=[evidence],
                Extraction=[ext],
            ),
        )
        result = await eval_d_06_quorum(ctx)
        assert result.status == ChecklistItemStatus.SATISFIED.value


# ══════════════════════════════════════════════════════════════════════════════
# D-07-SIGNED — same missing-vs-False regression as D-06
# ══════════════════════════════════════════════════════════════════════════════


class TestD07Signed:
    @pytest.mark.asyncio
    async def test_missing_signatures_complete_not_started(self):
        import uuid

        d = make_decision()
        doc_id = uuid.uuid4()
        evidence = _make_evidence_link(d.id, "mom", doc_id)
        ext = make_extraction(doc_id, signatures_complete=None)
        ctx = EvaluationContext(
            decision=d,
            session=fake_session(
                DecisionEvidenceRecord=[evidence],
                Extraction=[ext],
            ),
        )
        result = await eval_d_07_signed(ctx)
        assert result.status == ChecklistItemStatus.NOT_STARTED.value

    @pytest.mark.asyncio
    async def test_explicit_false_flagged(self):
        import uuid

        d = make_decision()
        doc_id = uuid.uuid4()
        evidence = _make_evidence_link(d.id, "mom", doc_id)
        ext = make_extraction(doc_id, signatures_complete=False)
        ctx = EvaluationContext(
            decision=d,
            session=fake_session(
                DecisionEvidenceRecord=[evidence],
                Extraction=[ext],
            ),
        )
        result = await eval_d_07_signed(ctx)
        assert result.status == ChecklistItemStatus.FLAGGED.value


# ══════════════════════════════════════════════════════════════════════════════
# D-11-DISCLOSE (CRITICAL) — materiality threshold + on-time check
# ══════════════════════════════════════════════════════════════════════════════


class TestD11Disclose:
    @pytest.mark.asyncio
    async def test_below_materiality_waived(self):
        """A 5-billion-IDR decision is below the 10B threshold — WAIVED."""
        d = make_decision(value_idr=5_000_000_000.0)
        ctx = EvaluationContext(decision=d, session=fake_session(MaterialDisclosure=[]))
        result = await eval_d_11_disclose(ctx)
        assert result.status == ChecklistItemStatus.WAIVED.value
        assert "disclosure not required" in (result.remediation_note or "").lower()

    @pytest.mark.asyncio
    async def test_above_materiality_no_disclosure_flagged(self):
        d = make_decision(value_idr=50_000_000_000.0)
        ctx = EvaluationContext(decision=d, session=fake_session(MaterialDisclosure=[]))
        result = await eval_d_11_disclose(ctx)
        assert result.status == ChecklistItemStatus.FLAGGED.value
        assert "lacks OJK/BEI disclosure" in (result.remediation_note or "")

    @pytest.mark.asyncio
    async def test_late_disclosure_flagged(self):
        d = make_decision(value_idr=50_000_000_000.0)
        disc = make_material_disclosure(d.id, is_on_time=False)
        ctx = EvaluationContext(decision=d, session=fake_session(MaterialDisclosure=[disc]))
        result = await eval_d_11_disclose(ctx)
        assert result.status == ChecklistItemStatus.FLAGGED.value
        assert "past deadline" in (result.remediation_note or "").lower()

    @pytest.mark.asyncio
    async def test_on_time_disclosure_satisfied(self):
        d = make_decision(value_idr=50_000_000_000.0)
        disc = make_material_disclosure(d.id, is_on_time=True)
        ctx = EvaluationContext(decision=d, session=fake_session(MaterialDisclosure=[disc]))
        result = await eval_d_11_disclose(ctx)
        assert result.status == ChecklistItemStatus.SATISFIED.value


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════


def _make_evidence_link(decision_id, evidence_type: str, evidence_id):
    """Lightweight DecisionEvidenceRecord for evaluator tests."""
    import uuid

    from ancol_common.db.models import DecisionEvidenceRecord

    link = DecisionEvidenceRecord(
        decision_id=decision_id,
        evidence_type=evidence_type,
        evidence_id=evidence_id,
        relationship_type="documents",
        created_by=uuid.uuid4(),
    )
    link.id = uuid.uuid4()
    return link
