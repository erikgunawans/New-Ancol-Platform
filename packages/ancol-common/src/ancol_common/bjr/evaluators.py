"""The 16 BJR checklist item evaluators.

Each evaluator takes an `EvaluationContext` and returns an `EvaluatorResult`
describing the item's status, AI confidence, evidence references, and
regulation basis. Evaluators are deterministic DB queries in v1; AI-assist
items (PD-03, PD-04, D-08) use simple heuristics until the bjr-agent service
wraps them with Gemini calls in a follow-up phase.

Contract: every evaluator is tagged with its `item_code` and registered in
`EVALUATORS`. The orchestrator (`compute.py`) iterates all 16 and upserts
`bjr_checklists` rows.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ancol_common.db.models import (
    AuditCommitteeReport,
    Contract,
    DecisionEvidenceRecord,
    Document,
    DueDiligenceReport,
    Extraction,
    FeasibilityStudyReport,
    MaterialDisclosure,
    OrganApproval,
    RelatedPartyEntity,
    SPIReport,
    StrategicDecision,
)
from ancol_common.schemas.bjr import BJRItemCode, ChecklistItemStatus, ChecklistPhase


@dataclass
class EvaluationContext:
    """Inputs passed to every evaluator."""

    decision: StrategicDecision
    session: AsyncSession
    materiality_threshold_idr: float = 10_000_000_000.0
    spi_lookback_days: int = 90


@dataclass
class EvaluatorResult:
    """Output of an evaluator — maps to a bjr_checklists row."""

    item_code: str
    phase: str
    status: str
    ai_confidence: float | None = None
    evidence_refs: list[dict] = field(default_factory=list)
    regulation_basis: list[str] = field(default_factory=list)
    remediation_note: str | None = None


# ══════════════════════════════════════════════════════════════════════════════
# PRE-DECISION evaluators
# ══════════════════════════════════════════════════════════════════════════════


async def eval_pd_01_dd(ctx: EvaluationContext) -> EvaluatorResult:
    """PD-01-DD: Due Diligence comprehensive and reviewed by Legal."""
    result = await ctx.session.execute(
        select(DueDiligenceReport).where(DueDiligenceReport.decision_id == ctx.decision.id)
    )
    reports = list(result.scalars().all())
    if not reports:
        return EvaluatorResult(
            item_code=BJRItemCode.PD_01_DD.value,
            phase=ChecklistPhase.PRE_DECISION.value,
            status=ChecklistItemStatus.NOT_STARTED.value,
            regulation_basis=["PP-23-2022", "PP-54-2017"],
            remediation_note="Upload a Due Diligence report for this decision.",
        )
    reviewed = [r for r in reports if r.reviewed_by_legal is not None]
    if reviewed:
        return EvaluatorResult(
            item_code=BJRItemCode.PD_01_DD.value,
            phase=ChecklistPhase.PRE_DECISION.value,
            status=ChecklistItemStatus.SATISFIED.value,
            evidence_refs=[{"type": "dd_report", "id": str(reviewed[0].id)}],
            regulation_basis=["PP-23-2022", "PP-54-2017"],
        )
    return EvaluatorResult(
        item_code=BJRItemCode.PD_01_DD.value,
        phase=ChecklistPhase.PRE_DECISION.value,
        status=ChecklistItemStatus.IN_PROGRESS.value,
        evidence_refs=[{"type": "dd_report", "id": str(reports[0].id)}],
        regulation_basis=["PP-23-2022", "PP-54-2017"],
        remediation_note="DD uploaded but pending Legal review.",
    )


async def eval_pd_02_fs(ctx: EvaluationContext) -> EvaluatorResult:
    """PD-02-FS: Feasibility Study available + Finance-reviewed."""
    result = await ctx.session.execute(
        select(FeasibilityStudyReport).where(FeasibilityStudyReport.decision_id == ctx.decision.id)
    )
    reports = list(result.scalars().all())
    if not reports:
        return EvaluatorResult(
            item_code=BJRItemCode.PD_02_FS.value,
            phase=ChecklistPhase.PRE_DECISION.value,
            status=ChecklistItemStatus.NOT_STARTED.value,
            regulation_basis=["PP-23-2022", "PERGUB-DKI-127-2019"],
            remediation_note="Upload a Feasibility Study report.",
        )
    reviewed = [r for r in reports if r.reviewed_by_finance is not None]
    if reviewed:
        return EvaluatorResult(
            item_code=BJRItemCode.PD_02_FS.value,
            phase=ChecklistPhase.PRE_DECISION.value,
            status=ChecklistItemStatus.SATISFIED.value,
            evidence_refs=[{"type": "fs_report", "id": str(reviewed[0].id)}],
            regulation_basis=["PP-23-2022", "PERGUB-DKI-127-2019"],
        )
    return EvaluatorResult(
        item_code=BJRItemCode.PD_02_FS.value,
        phase=ChecklistPhase.PRE_DECISION.value,
        status=ChecklistItemStatus.IN_PROGRESS.value,
        evidence_refs=[{"type": "fs_report", "id": str(reports[0].id)}],
        regulation_basis=["PP-23-2022", "PERGUB-DKI-127-2019"],
        remediation_note="FS uploaded but pending Finance review.",
    )


async def eval_pd_03_rkab(ctx: EvaluationContext) -> EvaluatorResult:
    """PD-03-RKAB (CRITICAL): Activity is in an approved RKAB for the fiscal year.

    Decisions outside approved RKAB automatically void BJR protection per
    Pergub DKI 127/2019.
    """
    if ctx.decision.rkab_line_id is None:
        return EvaluatorResult(
            item_code=BJRItemCode.PD_03_RKAB.value,
            phase=ChecklistPhase.PRE_DECISION.value,
            status=ChecklistItemStatus.FLAGGED.value,  # CRITICAL — flag, not just not_started
            regulation_basis=["PERGUB-DKI-127-2019"],
            remediation_note=(
                "Decision is not linked to an RKAB line item. Decisions outside "
                "approved RKAB void BJR protection. Link via /api/rkab/match."
            ),
        )
    # Load the linked RKAB item
    from ancol_common.db.models import RKABLineItem

    result = await ctx.session.execute(
        select(RKABLineItem).where(RKABLineItem.id == ctx.decision.rkab_line_id)
    )
    rkab = result.scalar_one_or_none()
    if rkab is None:
        return EvaluatorResult(
            item_code=BJRItemCode.PD_03_RKAB.value,
            phase=ChecklistPhase.PRE_DECISION.value,
            status=ChecklistItemStatus.FLAGGED.value,
            regulation_basis=["PERGUB-DKI-127-2019"],
            remediation_note="rkab_line_id references missing row — data integrity issue.",
        )
    if rkab.approval_status in ("rups_approved", "dewas_approved"):
        return EvaluatorResult(
            item_code=BJRItemCode.PD_03_RKAB.value,
            phase=ChecklistPhase.PRE_DECISION.value,
            status=ChecklistItemStatus.SATISFIED.value,
            evidence_refs=[{"type": "rkab_line", "id": str(rkab.id), "code": rkab.code}],
            regulation_basis=["PERGUB-DKI-127-2019"],
        )
    return EvaluatorResult(
        item_code=BJRItemCode.PD_03_RKAB.value,
        phase=ChecklistPhase.PRE_DECISION.value,
        status=ChecklistItemStatus.IN_PROGRESS.value,
        evidence_refs=[{"type": "rkab_line", "id": str(rkab.id), "code": rkab.code}],
        regulation_basis=["PERGUB-DKI-127-2019"],
        remediation_note=(
            f"RKAB line item '{rkab.code}' is in '{rkab.approval_status}' - "
            "needs RUPS approval."
        ),
    )


async def eval_pd_04_rjpp(ctx: EvaluationContext) -> EvaluatorResult:
    """PD-04-RJPP: Activity is aligned to an active RJPP theme."""
    if ctx.decision.rjpp_theme_id is None:
        return EvaluatorResult(
            item_code=BJRItemCode.PD_04_RJPP.value,
            phase=ChecklistPhase.PRE_DECISION.value,
            status=ChecklistItemStatus.NOT_STARTED.value,
            regulation_basis=["PERGUB-DKI-10-2012"],
            remediation_note="Link decision to an RJPP theme.",
        )
    return EvaluatorResult(
        item_code=BJRItemCode.PD_04_RJPP.value,
        phase=ChecklistPhase.PRE_DECISION.value,
        status=ChecklistItemStatus.SATISFIED.value,
        evidence_refs=[{"type": "rjpp_theme", "id": str(ctx.decision.rjpp_theme_id)}],
        regulation_basis=["PERGUB-DKI-10-2012"],
    )


async def eval_pd_05_coi(ctx: EvaluationContext) -> EvaluatorResult:
    """PD-05-COI (CRITICAL): No conflict of interest among involved Direksi.

    v1 heuristic: if any linked MoM references an attendee whose name matches
    an active RelatedPartyEntity, flag. More sophisticated matching awaits
    AI-assist in bjr-agent service.
    """
    mom_ids = await _linked_evidence_ids(ctx, evidence_type="mom")
    if not mom_ids:
        # No MoMs linked yet — PD-05 applies only when Direksi involved
        return EvaluatorResult(
            item_code=BJRItemCode.PD_05_COI.value,
            phase=ChecklistPhase.PRE_DECISION.value,
            status=ChecklistItemStatus.NOT_STARTED.value,
            regulation_basis=["UU-PT-40-2007"],
            remediation_note="Link at least one board MoM to enable COI scan.",
        )
    # Fetch extractions for linked MoMs
    extractions = await ctx.session.execute(
        select(Extraction).where(Extraction.document_id.in_(mom_ids))
    )
    extractions = list(extractions.scalars().all())
    rpt_result = await ctx.session.execute(
        select(RelatedPartyEntity).where(RelatedPartyEntity.is_active.is_(True))
    )
    rpt_names = {r.entity_name.lower().strip() for r in rpt_result.scalars().all()}

    flagged_attendees: list[str] = []
    for ext in extractions:
        attendees = ext.attendees or {}
        names = _extract_attendee_names(attendees)
        for n in names:
            if any(rpt_name in n.lower() or n.lower() in rpt_name for rpt_name in rpt_names):
                flagged_attendees.append(n)

    if flagged_attendees:
        return EvaluatorResult(
            item_code=BJRItemCode.PD_05_COI.value,
            phase=ChecklistPhase.PRE_DECISION.value,
            status=ChecklistItemStatus.FLAGGED.value,
            regulation_basis=["UU-PT-40-2007", "POJK-42-2020"],
            remediation_note=(
                f"Potential COI: {', '.join(flagged_attendees[:3])}. "
                "Verify abstention recorded in MoM."
            ),
        )
    return EvaluatorResult(
        item_code=BJRItemCode.PD_05_COI.value,
        phase=ChecklistPhase.PRE_DECISION.value,
        status=ChecklistItemStatus.SATISFIED.value,
        regulation_basis=["UU-PT-40-2007", "POJK-42-2020"],
    )


# ══════════════════════════════════════════════════════════════════════════════
# DECISION evaluators
# ══════════════════════════════════════════════════════════════════════════════


async def eval_d_06_quorum(ctx: EvaluationContext) -> EvaluatorResult:
    """D-06-QUORUM (CRITICAL): Board meeting held with valid quorum."""
    mom_ids = await _linked_evidence_ids(ctx, evidence_type="mom")
    if not mom_ids:
        return EvaluatorResult(
            item_code=BJRItemCode.D_06_QUORUM.value,
            phase=ChecklistPhase.DECISION.value,
            status=ChecklistItemStatus.NOT_STARTED.value,
            regulation_basis=["UU-PT-40-2007", "ADART-PJAA"],
            remediation_note="Link the board MoM that authorizes this decision.",
        )
    extractions = await ctx.session.execute(
        select(Extraction).where(Extraction.document_id.in_(mom_ids))
    )
    extractions = list(extractions.scalars().all())
    all_quorum_met = all((e.structured_mom or {}).get("quorum_met") is True for e in extractions)
    if all_quorum_met and extractions:
        return EvaluatorResult(
            item_code=BJRItemCode.D_06_QUORUM.value,
            phase=ChecklistPhase.DECISION.value,
            status=ChecklistItemStatus.SATISFIED.value,
            regulation_basis=["UU-PT-40-2007", "ADART-PJAA"],
        )
    return EvaluatorResult(
        item_code=BJRItemCode.D_06_QUORUM.value,
        phase=ChecklistPhase.DECISION.value,
        status=ChecklistItemStatus.FLAGGED.value,
        regulation_basis=["UU-PT-40-2007", "ADART-PJAA"],
        remediation_note="One or more linked MoMs did not meet quorum.",
    )


async def eval_d_07_signed(ctx: EvaluationContext) -> EvaluatorResult:
    """D-07-SIGNED: Minutes signed by required parties."""
    mom_ids = await _linked_evidence_ids(ctx, evidence_type="mom")
    if not mom_ids:
        return EvaluatorResult(
            item_code=BJRItemCode.D_07_SIGNED.value,
            phase=ChecklistPhase.DECISION.value,
            status=ChecklistItemStatus.NOT_STARTED.value,
            regulation_basis=["UU-PT-40-2007", "POJK-21-2015"],
        )
    extractions = await ctx.session.execute(
        select(Extraction).where(Extraction.document_id.in_(mom_ids))
    )
    extractions = list(extractions.scalars().all())
    all_signed = all(
        (e.structured_mom or {}).get("signatures_complete") is True for e in extractions
    )
    return EvaluatorResult(
        item_code=BJRItemCode.D_07_SIGNED.value,
        phase=ChecklistPhase.DECISION.value,
        status=(
            ChecklistItemStatus.SATISFIED.value
            if all_signed and extractions
            else ChecklistItemStatus.FLAGGED.value
        ),
        regulation_basis=["UU-PT-40-2007", "POJK-21-2015"],
        remediation_note=(None if all_signed else "One or more linked MoMs is not fully signed."),
    )


async def eval_d_08_risk(ctx: EvaluationContext) -> EvaluatorResult:
    """D-08-RISK (AI-assist): Risk analysis captured in the MoM text.

    v1 heuristic: scan MoM full_text for risk-language keywords (Bahasa
    Indonesia + English). Gemini scan in bjr-agent service will replace this.
    """
    mom_ids = await _linked_evidence_ids(ctx, evidence_type="mom")
    if not mom_ids:
        return EvaluatorResult(
            item_code=BJRItemCode.D_08_RISK.value,
            phase=ChecklistPhase.DECISION.value,
            status=ChecklistItemStatus.NOT_STARTED.value,
            regulation_basis=["PP-23-2022", "POJK-21-2015"],
        )
    extractions = await ctx.session.execute(
        select(Extraction).where(Extraction.document_id.in_(mom_ids))
    )
    extractions = list(extractions.scalars().all())
    keywords = (
        "risiko",
        "mitigasi",
        "analisis risiko",
        "pertimbangan risiko",
        "risk",
        "mitigation",
    )
    any_risk_text = False
    for ext in extractions:
        full = ((ext.structured_mom or {}).get("full_text") or "").lower()
        if any(kw in full for kw in keywords):
            any_risk_text = True
            break
    return EvaluatorResult(
        item_code=BJRItemCode.D_08_RISK.value,
        phase=ChecklistPhase.DECISION.value,
        status=(
            ChecklistItemStatus.SATISFIED.value
            if any_risk_text
            else ChecklistItemStatus.IN_PROGRESS.value
        ),
        ai_confidence=0.7 if any_risk_text else 0.4,
        regulation_basis=["PP-23-2022", "POJK-21-2015"],
        remediation_note=(
            None
            if any_risk_text
            else "MoM text lacks explicit risk analysis keywords — confirm manually."
        ),
    )


async def eval_d_09_legal(ctx: EvaluationContext) -> EvaluatorResult:
    """D-09-LEGAL: Linked contracts reviewed by legal team."""
    contract_ids = await _linked_evidence_ids(ctx, evidence_type="contract")
    if not contract_ids:
        return EvaluatorResult(
            item_code=BJRItemCode.D_09_LEGAL.value,
            phase=ChecklistPhase.DECISION.value,
            status=ChecklistItemStatus.NOT_STARTED.value,
            regulation_basis=["PP-23-2022", "ADART-PJAA"],
            remediation_note="No contracts linked. Skip if decision has no contract phase.",
        )
    contracts = await ctx.session.execute(select(Contract).where(Contract.id.in_(contract_ids)))
    contracts = list(contracts.scalars().all())
    all_reviewed = all(c.reviewed_by is not None for c in contracts)
    return EvaluatorResult(
        item_code=BJRItemCode.D_09_LEGAL.value,
        phase=ChecklistPhase.DECISION.value,
        status=(
            ChecklistItemStatus.SATISFIED.value
            if all_reviewed
            else ChecklistItemStatus.IN_PROGRESS.value
        ),
        regulation_basis=["PP-23-2022", "ADART-PJAA"],
        remediation_note=None if all_reviewed else "One or more contracts lacks legal review.",
    )


async def eval_d_10_organ(ctx: EvaluationContext) -> EvaluatorResult:
    """D-10-ORGAN: Komisaris/Dewas/RUPS approval obtained."""
    result = await ctx.session.execute(
        select(OrganApproval).where(OrganApproval.decision_id == ctx.decision.id)
    )
    approvals = list(result.scalars().all())
    if approvals:
        return EvaluatorResult(
            item_code=BJRItemCode.D_10_ORGAN.value,
            phase=ChecklistPhase.DECISION.value,
            status=ChecklistItemStatus.SATISFIED.value,
            evidence_refs=[
                {"type": "organ_approval", "id": str(a.id), "approval_type": a.approval_type}
                for a in approvals
            ],
            regulation_basis=["PERGUB-DKI-50-2018", "ADART-PJAA"],
        )
    return EvaluatorResult(
        item_code=BJRItemCode.D_10_ORGAN.value,
        phase=ChecklistPhase.DECISION.value,
        status=ChecklistItemStatus.NOT_STARTED.value,
        regulation_basis=["PERGUB-DKI-50-2018", "ADART-PJAA"],
        remediation_note="No Komisaris/Dewas/RUPS approval on record for this decision.",
    )


async def eval_d_11_disclose(ctx: EvaluationContext) -> EvaluatorResult:
    """D-11-DISCLOSE (CRITICAL): Material OJK/BEI disclosure filed on time."""
    value = float(ctx.decision.value_idr) if ctx.decision.value_idr else 0.0
    if value < ctx.materiality_threshold_idr:
        return EvaluatorResult(
            item_code=BJRItemCode.D_11_DISCLOSE.value,
            phase=ChecklistPhase.DECISION.value,
            status=ChecklistItemStatus.WAIVED.value,
            regulation_basis=["POJK-30-2020", "IDX-I-A"],
            remediation_note=(
                f"Value (IDR {value:,.0f}) below materiality threshold "
                f"(IDR {ctx.materiality_threshold_idr:,.0f}) — disclosure not required."
            ),
        )
    result = await ctx.session.execute(
        select(MaterialDisclosure).where(MaterialDisclosure.decision_id == ctx.decision.id)
    )
    disclosures = list(result.scalars().all())
    if not disclosures:
        return EvaluatorResult(
            item_code=BJRItemCode.D_11_DISCLOSE.value,
            phase=ChecklistPhase.DECISION.value,
            status=ChecklistItemStatus.FLAGGED.value,
            regulation_basis=["POJK-30-2020", "IDX-I-A"],
            remediation_note=(f"Material decision (IDR {value:,.0f}) lacks OJK/BEI disclosure."),
        )
    on_time = all(d.is_on_time for d in disclosures)
    return EvaluatorResult(
        item_code=BJRItemCode.D_11_DISCLOSE.value,
        phase=ChecklistPhase.DECISION.value,
        status=(
            ChecklistItemStatus.SATISFIED.value if on_time else ChecklistItemStatus.FLAGGED.value
        ),
        evidence_refs=[{"type": "ojk_disclosure", "id": str(d.id)} for d in disclosures],
        regulation_basis=["POJK-30-2020", "IDX-I-A"],
        remediation_note=None if on_time else "At least one disclosure was filed past deadline.",
    )


# ══════════════════════════════════════════════════════════════════════════════
# POST-DECISION evaluators
# ══════════════════════════════════════════════════════════════════════════════


async def eval_post_12_monitor(ctx: EvaluationContext) -> EvaluatorResult:
    """POST-12-MONITOR: Monitoring mechanism defined (manual item).

    v1: satisfied iff decision has any post-decision evidence linked. Manual
    override is possible via PATCH on the checklist item.
    """
    monitor_evidence_types = {"spi_report", "audit_committee_report"}
    result = await ctx.session.execute(
        select(DecisionEvidenceRecord).where(
            DecisionEvidenceRecord.decision_id == ctx.decision.id,
            DecisionEvidenceRecord.evidence_type.in_(monitor_evidence_types),
        )
    )
    has_monitor = result.first() is not None
    return EvaluatorResult(
        item_code=BJRItemCode.POST_12_MONITOR.value,
        phase=ChecklistPhase.POST_DECISION.value,
        status=(
            ChecklistItemStatus.SATISFIED.value
            if has_monitor
            else ChecklistItemStatus.NOT_STARTED.value
        ),
        regulation_basis=["PP-23-2022", "PERGUB-DKI-131-2019"],
        remediation_note=(
            None if has_monitor else "Attach a monitoring plan (SPI or Audit Committee report)."
        ),
    )


async def eval_post_13_spi(ctx: EvaluationContext) -> EvaluatorResult:
    """POST-13-SPI: SPI report references this decision within lookback window."""
    cutoff = datetime.now(UTC) - timedelta(days=ctx.spi_lookback_days)
    result = await ctx.session.execute(
        select(SPIReport).where(
            SPIReport.related_decision_ids.isnot(None),
            SPIReport.created_at >= cutoff,
        )
    )
    candidates = list(result.scalars().all())
    matching = [
        r for r in candidates if _decision_in_array(r.related_decision_ids, ctx.decision.id)
    ]
    if matching:
        return EvaluatorResult(
            item_code=BJRItemCode.POST_13_SPI.value,
            phase=ChecklistPhase.POST_DECISION.value,
            status=ChecklistItemStatus.SATISFIED.value,
            evidence_refs=[{"type": "spi_report", "id": str(r.id)} for r in matching[:3]],
            regulation_basis=["PERGUB-DKI-1-2020", "PP-54-2017"],
        )
    return EvaluatorResult(
        item_code=BJRItemCode.POST_13_SPI.value,
        phase=ChecklistPhase.POST_DECISION.value,
        status=ChecklistItemStatus.NOT_STARTED.value,
        regulation_basis=["PERGUB-DKI-1-2020", "PP-54-2017"],
        remediation_note=(
            f"No SPI report references this decision in the last {ctx.spi_lookback_days} days."
        ),
    )


async def eval_post_14_auditcom(ctx: EvaluationContext) -> EvaluatorResult:
    """POST-14-AUDITCOM: Audit Committee reviewed this decision."""
    result = await ctx.session.execute(select(AuditCommitteeReport))
    reports = list(result.scalars().all())
    matching = [r for r in reports if _decision_in_array(r.decisions_reviewed, ctx.decision.id)]
    if matching:
        return EvaluatorResult(
            item_code=BJRItemCode.POST_14_AUDITCOM.value,
            phase=ChecklistPhase.POST_DECISION.value,
            status=ChecklistItemStatus.SATISFIED.value,
            evidence_refs=[
                {"type": "audit_committee_report", "id": str(r.id)} for r in matching[:3]
            ],
            regulation_basis=["PERGUB-DKI-13-2020", "POJK-35-2014"],
        )
    return EvaluatorResult(
        item_code=BJRItemCode.POST_14_AUDITCOM.value,
        phase=ChecklistPhase.POST_DECISION.value,
        status=ChecklistItemStatus.NOT_STARTED.value,
        regulation_basis=["PERGUB-DKI-13-2020", "POJK-35-2014"],
        remediation_note="Komite Audit has not reviewed this decision.",
    )


async def eval_post_15_dewas(ctx: EvaluationContext) -> EvaluatorResult:
    """POST-15-DEWAS: Periodic reports sent to Dewan Pengawas."""
    cutoff = datetime.now(UTC) - timedelta(days=ctx.spi_lookback_days)
    result = await ctx.session.execute(
        select(SPIReport).where(
            SPIReport.sent_to_dewas_at.isnot(None),
            SPIReport.sent_to_dewas_at >= cutoff,
        )
    )
    matching = [
        r
        for r in result.scalars().all()
        if _decision_in_array(r.related_decision_ids, ctx.decision.id)
    ]
    return EvaluatorResult(
        item_code=BJRItemCode.POST_15_DEWAS.value,
        phase=ChecklistPhase.POST_DECISION.value,
        status=(
            ChecklistItemStatus.SATISFIED.value
            if matching
            else ChecklistItemStatus.NOT_STARTED.value
        ),
        regulation_basis=["PERGUB-DKI-50-2018", "POJK-21-2015"],
        remediation_note=(
            None
            if matching
            else f"No SPI report sent to Dewas in the last {ctx.spi_lookback_days} days."
        ),
    )


async def eval_post_16_archive(ctx: EvaluationContext) -> EvaluatorResult:
    """POST-16-ARCHIVE: All linked artifacts have gcs_uri (are archived)."""
    evidence_result = await ctx.session.execute(
        select(DecisionEvidenceRecord).where(DecisionEvidenceRecord.decision_id == ctx.decision.id)
    )
    evidence_records = list(evidence_result.scalars().all())
    if not evidence_records:
        return EvaluatorResult(
            item_code=BJRItemCode.POST_16_ARCHIVE.value,
            phase=ChecklistPhase.POST_DECISION.value,
            status=ChecklistItemStatus.NOT_STARTED.value,
            regulation_basis=["UU-PT-40-2007", "PP-23-2022"],
            remediation_note="No evidence linked yet.",
        )
    # Check each evidence has a gcs_uri by looking up the underlying row.
    missing: list[str] = []
    for ev in evidence_records:
        uri = await _evidence_gcs_uri(ctx.session, ev.evidence_type, ev.evidence_id)
        if uri is None:
            missing.append(f"{ev.evidence_type}:{ev.evidence_id}")
    if missing:
        return EvaluatorResult(
            item_code=BJRItemCode.POST_16_ARCHIVE.value,
            phase=ChecklistPhase.POST_DECISION.value,
            status=ChecklistItemStatus.IN_PROGRESS.value,
            regulation_basis=["UU-PT-40-2007", "PP-23-2022"],
            remediation_note=f"Missing gcs_uri on: {', '.join(missing[:3])}",
        )
    return EvaluatorResult(
        item_code=BJRItemCode.POST_16_ARCHIVE.value,
        phase=ChecklistPhase.POST_DECISION.value,
        status=ChecklistItemStatus.SATISFIED.value,
        regulation_basis=["UU-PT-40-2007", "PP-23-2022"],
    )


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════


async def _linked_evidence_ids(ctx: EvaluationContext, evidence_type: str) -> list[uuid.UUID]:
    """Return evidence_id UUIDs of a given type linked to the decision."""
    result = await ctx.session.execute(
        select(DecisionEvidenceRecord.evidence_id).where(
            DecisionEvidenceRecord.decision_id == ctx.decision.id,
            DecisionEvidenceRecord.evidence_type == evidence_type,
        )
    )
    return [row[0] for row in result.all()]


def _extract_attendee_names(attendees: dict | list) -> list[str]:
    """Extract attendee names from the extraction.attendees JSONB blob."""
    names: list[str] = []
    items = attendees if isinstance(attendees, list) else attendees.get("attendees", [])
    if not isinstance(items, list):
        return names
    for item in items:
        if isinstance(item, dict) and "name" in item:
            names.append(str(item["name"]))
    return names


def _decision_in_array(array_val, decision_id: uuid.UUID) -> bool:
    """Check if a decision UUID is present in a UUID[] column value."""
    if not array_val:
        return False
    target = str(decision_id)
    return any(str(x) == target for x in array_val)


async def _evidence_gcs_uri(
    session: AsyncSession, evidence_type: str, evidence_id: uuid.UUID
) -> str | None:
    """Return the gcs_uri of a polymorphic evidence row, or None if missing."""
    type_to_model = {
        "mom": (Document, "gcs_raw_uri"),
        "contract": (Contract, "gcs_raw_uri"),
        "dd_report": (DueDiligenceReport, "gcs_uri"),
        "fs_report": (FeasibilityStudyReport, "gcs_uri"),
        "spi_report": (SPIReport, "gcs_uri"),
        "audit_committee_report": (AuditCommitteeReport, "gcs_uri"),
        "ojk_disclosure": (MaterialDisclosure, "gcs_uri"),
        "organ_approval": (OrganApproval, "gcs_uri"),
    }
    entry = type_to_model.get(evidence_type)
    if entry is None:
        return None
    model, uri_attr = entry
    result = await session.execute(select(model).where(model.id == evidence_id))
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return getattr(row, uri_attr, None)


# Registry — order matters for deterministic checklist display
EVALUATORS = [
    eval_pd_01_dd,
    eval_pd_02_fs,
    eval_pd_03_rkab,
    eval_pd_04_rjpp,
    eval_pd_05_coi,
    eval_d_06_quorum,
    eval_d_07_signed,
    eval_d_08_risk,
    eval_d_09_legal,
    eval_d_10_organ,
    eval_d_11_disclose,
    eval_post_12_monitor,
    eval_post_13_spi,
    eval_post_14_auditcom,
    eval_post_15_dewas,
    eval_post_16_archive,
]
