"""Strategic Decisions + BJR — the orchestration root for Business Judgment Rule.

Exposes:
  POST   /api/decisions                         create
  GET    /api/decisions                         list with filters
  GET    /api/decisions/{id}                    detail
  PATCH  /api/decisions/{id}                    update
  POST   /api/decisions/{id}/evidence           link evidence
  DELETE /api/decisions/{id}/evidence/{eid}     unlink evidence
  POST   /api/decisions/{id}/bjr-compute        recompute checklist + scores
  GET    /api/decisions/{id}/readiness          current score + checklist
  POST   /api/decisions/retroactive-propose     suggest Decision from completed MoM
  POST   /api/decisions/{id}/gate5/komisaris    Komisaris half of Gate 5 (MFA)
  POST   /api/decisions/{id}/gate5/legal        Legal half of Gate 5 (MFA)
  GET    /api/decisions/{id}/gate5              Gate 5 current state
  GET    /api/decisions/dashboard               aggregate BJR stats
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ancol_common.auth.mfa import require_mfa_verified
from ancol_common.auth.rbac import require_permission
from ancol_common.bjr.compute import compute_bjr
from ancol_common.bjr.retroactive import propose_from_mom
from ancol_common.config import get_settings
from ancol_common.db.connection import get_session
from ancol_common.db.models import (
    BJRChecklistItemRecord,
    BJRGate5Decision,
    DecisionEvidenceRecord,
    StrategicDecision,
)
from ancol_common.db.repository import transition_decision_status
from ancol_common.schemas.bjr import Gate5FinalDecision
from ancol_common.schemas.decision import DecisionStatus
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

router = APIRouter(prefix="/decisions", tags=["Strategic Decisions"])


# ══════════════════════════════════════════════════════════════════════════════
# Response models
# ══════════════════════════════════════════════════════════════════════════════


class DecisionResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    initiative_type: str
    status: str
    rkab_line_id: str | None = None
    rjpp_theme_id: str | None = None
    business_owner_id: str
    legal_owner_id: str | None = None
    value_idr: float | None = None
    bjr_readiness_score: float | None = None
    corporate_compliance_score: float | None = None
    regional_compliance_score: float | None = None
    is_bjr_locked: bool
    locked_at: datetime | None = None
    gcs_passport_uri: str | None = None
    source: str
    created_at: datetime
    updated_at: datetime


class DecisionCreate(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    description: str | None = None
    initiative_type: str
    business_owner_id: str
    legal_owner_id: str | None = None
    rkab_line_id: str | None = None
    rjpp_theme_id: str | None = None
    value_idr: float | None = Field(default=None, ge=0.0)
    source: str = "proactive"


class DecisionUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    value_idr: float | None = None
    rkab_line_id: str | None = None
    rjpp_theme_id: str | None = None
    legal_owner_id: str | None = None
    status: str | None = None


class DecisionList(BaseModel):
    decisions: list[DecisionResponse]
    total: int


class EvidenceLinkRequest(BaseModel):
    evidence_type: str
    evidence_id: str
    relationship_type: str = "documents"
    created_by: str


class EvidenceLinkResponse(BaseModel):
    id: str
    decision_id: str
    evidence_type: str
    evidence_id: str
    relationship_type: str
    created_at: datetime


class ChecklistItemResponse(BaseModel):
    item_code: str
    phase: str
    status: str
    ai_confidence: float | None = None
    evidence_refs: list[dict] | None = None
    regulation_basis: list[str] | None = None
    remediation_note: str | None = None
    last_checked_at: datetime | None = None


class BJRComputeResponse(BaseModel):
    decision_id: str
    bjr_readiness_score: float
    corporate_compliance_score: float
    regional_compliance_score: float
    satisfied_count: int
    flagged_count: int
    gate_5_unlockable: bool
    checklist: list[ChecklistItemResponse]
    computed_at: datetime


class ReadinessResponse(BaseModel):
    decision_id: str
    bjr_readiness_score: float | None = None
    corporate_compliance_score: float | None = None
    regional_compliance_score: float | None = None
    checklist: list[ChecklistItemResponse]


class RetroactiveProposeRequest(BaseModel):
    document_id: str


class ProposedCandidateResponse(BaseModel):
    id: str
    code: str
    name: str
    confidence: float
    rationale: str | None = None


class ProposedDecisionResponse(BaseModel):
    source_document_id: str
    proposed_title: str
    proposed_description: str
    proposed_initiative_type: str
    rkab_candidates: list[ProposedCandidateResponse]
    rjpp_candidates: list[ProposedCandidateResponse]
    reasoning: str | None = None


class Gate5HalfRequest(BaseModel):
    approver_id: str
    decision: str  # "approved" or "rejected"
    notes: str | None = None


class Gate5State(BaseModel):
    id: str
    decision_id: str
    final_decision: str
    approver_komisaris_id: str | None = None
    komisaris_decided_at: datetime | None = None
    komisaris_decision: str | None = None
    komisaris_notes: str | None = None
    approver_legal_id: str | None = None
    legal_decided_at: datetime | None = None
    legal_decision: str | None = None
    legal_notes: str | None = None
    locked_at: datetime | None = None
    sla_deadline: datetime
    is_sla_breached: bool


class DashboardResponse(BaseModel):
    total_decisions: int
    by_status: dict[str, int]
    avg_readiness_score: float | None = None
    locked_count: int
    gate_5_pending_count: int


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════


def _decision_to_response(d: StrategicDecision) -> DecisionResponse:
    return DecisionResponse(
        id=str(d.id),
        title=d.title,
        description=d.description,
        initiative_type=d.initiative_type,
        status=d.status,
        rkab_line_id=str(d.rkab_line_id) if d.rkab_line_id else None,
        rjpp_theme_id=str(d.rjpp_theme_id) if d.rjpp_theme_id else None,
        business_owner_id=str(d.business_owner_id),
        legal_owner_id=str(d.legal_owner_id) if d.legal_owner_id else None,
        value_idr=float(d.value_idr) if d.value_idr is not None else None,
        bjr_readiness_score=(
            float(d.bjr_readiness_score) if d.bjr_readiness_score is not None else None
        ),
        corporate_compliance_score=(
            float(d.corporate_compliance_score)
            if d.corporate_compliance_score is not None
            else None
        ),
        regional_compliance_score=(
            float(d.regional_compliance_score) if d.regional_compliance_score is not None else None
        ),
        is_bjr_locked=d.is_bjr_locked,
        locked_at=d.locked_at,
        gcs_passport_uri=d.gcs_passport_uri,
        source=d.source,
        created_at=d.created_at,
        updated_at=d.updated_at,
    )


def _checklist_to_response(c: BJRChecklistItemRecord) -> ChecklistItemResponse:
    return ChecklistItemResponse(
        item_code=c.item_code,
        phase=c.phase,
        status=c.status,
        ai_confidence=float(c.ai_confidence) if c.ai_confidence is not None else None,
        evidence_refs=c.evidence_refs,
        regulation_basis=c.regulation_basis,
        remediation_note=c.remediation_note,
        last_checked_at=c.last_checked_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Dashboard (mount BEFORE /{id} so the route isn't captured as an ID)
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/dashboard", response_model=DashboardResponse)
async def decisions_dashboard(
    _auth=require_permission("decisions:list"),
):
    async with get_session() as session:
        # One query: total + avg score + locked count (three aggregates)
        agg_result = await session.execute(
            select(
                func.count(StrategicDecision.id),
                func.avg(StrategicDecision.bjr_readiness_score),
                func.count(StrategicDecision.id).filter(StrategicDecision.is_bjr_locked.is_(True)),
            )
        )
        total, avg_score, locked_count = agg_result.one()

        # Second query: by-status breakdown + pending Gate 5 count in one SELECT
        status_result = await session.execute(
            select(StrategicDecision.status, func.count(StrategicDecision.id)).group_by(
                StrategicDecision.status
            )
        )
        by_status = {row[0]: row[1] for row in status_result.all()}

        gate_5_result = await session.execute(
            select(func.count(BJRGate5Decision.id)).where(
                BJRGate5Decision.final_decision == Gate5FinalDecision.PENDING.value
            )
        )
        gate_5_pending = gate_5_result.scalar() or 0

    return DashboardResponse(
        total_decisions=total or 0,
        by_status=by_status,
        avg_readiness_score=round(float(avg_score), 2) if avg_score is not None else None,
        locked_count=locked_count or 0,
        gate_5_pending_count=gate_5_pending,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Retroactive bundler (also mount before /{id})
# ══════════════════════════════════════════════════════════════════════════════


@router.post("/retroactive-propose", response_model=ProposedDecisionResponse)
async def retroactive_propose(
    payload: RetroactiveProposeRequest,
    _auth=require_permission("decisions:retroactive_bundle"),
):
    """Propose a StrategicDecision draft from a completed MoM.

    Returns draft title/description + top-3 RKAB/RJPP candidates. Caller
    confirms selections and POSTs to /api/decisions to materialize.
    """
    async with get_session() as session:
        try:
            draft = await propose_from_mom(session, payload.document_id)
        except ValueError as e:
            raise HTTPException(404, str(e)) from e
    return ProposedDecisionResponse(
        source_document_id=draft.source_document_id,
        proposed_title=draft.proposed_title,
        proposed_description=draft.proposed_description,
        proposed_initiative_type=draft.proposed_initiative_type,
        rkab_candidates=[
            ProposedCandidateResponse(
                id=c.id,
                code=c.code,
                name=c.name,
                confidence=c.confidence,
                rationale=c.rationale,
            )
            for c in draft.rkab_candidates
        ],
        rjpp_candidates=[
            ProposedCandidateResponse(
                id=c.id,
                code=c.code,
                name=c.name,
                confidence=c.confidence,
                rationale=c.rationale,
            )
            for c in draft.rjpp_candidates
        ],
        reasoning=draft.reasoning,
    )


# ══════════════════════════════════════════════════════════════════════════════
# CRUD
# ══════════════════════════════════════════════════════════════════════════════


@router.post("", response_model=DecisionResponse)
async def create_decision(
    payload: DecisionCreate,
    _auth=require_permission("decisions:create"),
):
    async with get_session() as session:
        decision = StrategicDecision(
            title=payload.title,
            description=payload.description,
            initiative_type=payload.initiative_type,
            business_owner_id=payload.business_owner_id,
            legal_owner_id=payload.legal_owner_id,
            rkab_line_id=payload.rkab_line_id,
            rjpp_theme_id=payload.rjpp_theme_id,
            value_idr=payload.value_idr,
            source=payload.source,
        )
        session.add(decision)
        await session.commit()
        await session.refresh(decision)
    return _decision_to_response(decision)


@router.get("", response_model=DecisionList)
async def list_decisions(
    _auth=require_permission("decisions:list"),
    status: str | None = Query(None),
    business_owner_id: str | None = Query(None),
    is_bjr_locked: bool | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    async with get_session() as session:
        query = select(StrategicDecision)
        if status:
            query = query.where(StrategicDecision.status == status)
        if business_owner_id:
            query = query.where(StrategicDecision.business_owner_id == business_owner_id)
        if is_bjr_locked is not None:
            query = query.where(StrategicDecision.is_bjr_locked == is_bjr_locked)
        query = query.order_by(StrategicDecision.updated_at.desc()).limit(limit)
        result = await session.execute(query)
        decisions = list(result.scalars().all())
    return DecisionList(
        decisions=[_decision_to_response(d) for d in decisions], total=len(decisions)
    )


@router.get("/{decision_id}", response_model=DecisionResponse)
async def get_decision(
    decision_id: str,
    _auth=require_permission("decisions:list"),
):
    async with get_session() as session:
        result = await session.execute(
            select(StrategicDecision).where(StrategicDecision.id == decision_id)
        )
        d = result.scalar_one_or_none()
    if d is None:
        raise HTTPException(404, "Decision not found")
    return _decision_to_response(d)


@router.patch("/{decision_id}", response_model=DecisionResponse)
async def update_decision(
    decision_id: str,
    payload: DecisionUpdate,
    _auth=require_permission("decisions:edit"),
):
    async with get_session() as session:
        result = await session.execute(
            select(StrategicDecision).where(StrategicDecision.id == decision_id)
        )
        d = result.scalar_one_or_none()
        if d is None:
            raise HTTPException(404, "Decision not found")

        if payload.status and payload.status != d.status:
            ok = await transition_decision_status(session, decision_id, payload.status)
            if not ok:
                raise HTTPException(
                    422, f"Invalid transition from '{d.status}' to '{payload.status}'"
                )
        for field_name in (
            "title",
            "description",
            "value_idr",
            "rkab_line_id",
            "rjpp_theme_id",
            "legal_owner_id",
        ):
            v = getattr(payload, field_name)
            if v is not None:
                setattr(d, field_name, v)
        d.updated_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(d)
    return _decision_to_response(d)


# ══════════════════════════════════════════════════════════════════════════════
# Evidence linking
# ══════════════════════════════════════════════════════════════════════════════


@router.post("/{decision_id}/evidence", response_model=EvidenceLinkResponse)
async def link_evidence(
    decision_id: str,
    payload: EvidenceLinkRequest,
    _auth=require_permission("decisions:link_evidence"),
):
    async with get_session() as session:
        link = DecisionEvidenceRecord(
            decision_id=decision_id,
            evidence_type=payload.evidence_type,
            evidence_id=payload.evidence_id,
            relationship_type=payload.relationship_type,
            created_by=payload.created_by,
        )
        session.add(link)
        try:
            await session.commit()
        except IntegrityError as e:
            # Only unique-constraint violations map to 409 "duplicate link".
            # FK violations, invalid enum values, etc. stay as 500s — they
            # indicate bad input, not a duplicate.
            await session.rollback()
            raise HTTPException(409, f"Duplicate evidence link: {e.__class__.__name__}") from e
        await session.refresh(link)
    return EvidenceLinkResponse(
        id=str(link.id),
        decision_id=str(link.decision_id),
        evidence_type=link.evidence_type,
        evidence_id=str(link.evidence_id),
        relationship_type=link.relationship_type,
        created_at=link.created_at,
    )


@router.delete("/{decision_id}/evidence/{evidence_link_id}")
async def unlink_evidence(
    decision_id: str,
    evidence_link_id: str,
    _auth=require_permission("decisions:link_evidence"),
):
    async with get_session() as session:
        result = await session.execute(
            select(DecisionEvidenceRecord).where(
                DecisionEvidenceRecord.id == evidence_link_id,
                DecisionEvidenceRecord.decision_id == decision_id,
            )
        )
        link = result.scalar_one_or_none()
        if link is None:
            raise HTTPException(404, "Evidence link not found")
        await session.delete(link)
        await session.commit()
    return {"deleted": True}


# ══════════════════════════════════════════════════════════════════════════════
# BJR compute + readiness
# ══════════════════════════════════════════════════════════════════════════════


@router.post("/{decision_id}/bjr-compute", response_model=BJRComputeResponse)
async def trigger_bjr_compute(
    decision_id: str,
    triggered_by: str = Query(""),
    _auth=require_permission("bjr:compute"),
):
    settings = get_settings()
    if not settings.bjr_enabled:
        raise HTTPException(503, "BJR is disabled (BJR_ENABLED=false)")
    async with get_session() as session:
        try:
            result = await compute_bjr(
                session,
                decision_id,
                triggered_by=triggered_by or None,
            )
            await session.commit()
        except ValueError as e:
            raise HTTPException(404, str(e)) from e
    return BJRComputeResponse(
        decision_id=result.decision_id,
        bjr_readiness_score=result.scores.bjr_readiness_score,
        corporate_compliance_score=result.scores.corporate_compliance_score,
        regional_compliance_score=result.scores.regional_compliance_score,
        satisfied_count=result.scores.satisfied_count,
        flagged_count=result.scores.flagged_count,
        gate_5_unlockable=result.scores.gate_5_unlockable,
        checklist=[
            ChecklistItemResponse(
                item_code=r.item_code,
                phase=r.phase,
                status=r.status,
                ai_confidence=r.ai_confidence,
                evidence_refs=r.evidence_refs or None,
                regulation_basis=r.regulation_basis or None,
                remediation_note=r.remediation_note,
                last_checked_at=result.computed_at,
            )
            for r in result.items
        ],
        computed_at=result.computed_at,
    )


@router.get("/{decision_id}/readiness", response_model=ReadinessResponse)
async def get_readiness(
    decision_id: str,
    _auth=require_permission("decisions:list"),
):
    async with get_session() as session:
        d_result = await session.execute(
            select(StrategicDecision).where(StrategicDecision.id == decision_id)
        )
        d = d_result.scalar_one_or_none()
        if d is None:
            raise HTTPException(404, "Decision not found")
        cl_result = await session.execute(
            select(BJRChecklistItemRecord)
            .where(BJRChecklistItemRecord.decision_id == decision_id)
            .order_by(BJRChecklistItemRecord.item_code)
        )
        items = list(cl_result.scalars().all())
    return ReadinessResponse(
        decision_id=decision_id,
        # Use `is not None` — a valid 0.0 score must NOT be reported as null.
        bjr_readiness_score=(
            float(d.bjr_readiness_score) if d.bjr_readiness_score is not None else None
        ),
        corporate_compliance_score=(
            float(d.corporate_compliance_score)
            if d.corporate_compliance_score is not None
            else None
        ),
        regional_compliance_score=(
            float(d.regional_compliance_score) if d.regional_compliance_score is not None else None
        ),
        checklist=[_checklist_to_response(c) for c in items],
    )


# ══════════════════════════════════════════════════════════════════════════════
# Gate 5 dual-approval — MFA required
# ══════════════════════════════════════════════════════════════════════════════

gate5_router = APIRouter(
    prefix="/decisions",
    tags=["Strategic Decisions — Gate 5"],
    dependencies=[require_mfa_verified()],
)


_GATE5_VALID_HALF_DECISIONS = frozenset(
    {Gate5FinalDecision.APPROVED.value, Gate5FinalDecision.REJECTED.value}
)


async def _assert_decision_in_gate5(session, decision_id: str) -> StrategicDecision:
    """Load the decision and reject if it is not in `bjr_gate_5` state.

    Gate 5 half-approvals must only be recorded against a decision in the
    `bjr_gate_5` state. Calling against a decision in any other state would
    stash half-approvals that could never finalize (the lock transition is
    only valid from bjr_gate_5). Reject early with a client-friendly error.
    """
    result = await session.execute(
        select(StrategicDecision).where(StrategicDecision.id == decision_id)
    )
    decision = result.scalar_one_or_none()
    if decision is None:
        raise HTTPException(404, "Decision not found")
    if decision.status != DecisionStatus.BJR_GATE_5.value:
        raise HTTPException(
            409,
            f"Decision is in state '{decision.status}'; Gate 5 half-approvals "
            f"require '{DecisionStatus.BJR_GATE_5.value}'.",
        )
    return decision


async def _ensure_gate5_row(session, decision_id: str) -> BJRGate5Decision:
    """Fetch-or-create the Gate 5 record for a decision, serialized via row lock.

    `with_for_update()` holds the row until commit so two concurrent half-approvals
    can't both see "no row" and both insert. If no row exists yet, the INSERT races
    the unique constraint (`idx_gate5_decision`); we catch the IntegrityError and
    re-fetch the row the other request created.
    """
    result = await session.execute(
        select(BJRGate5Decision)
        .where(BJRGate5Decision.decision_id == decision_id)
        .with_for_update()
    )
    row = result.scalar_one_or_none()
    if row is not None:
        return row
    settings = get_settings()
    row = BJRGate5Decision(
        decision_id=decision_id,
        sla_deadline=datetime.now(UTC) + timedelta(days=settings.bjr_gate5_sla_days),
        final_decision=Gate5FinalDecision.PENDING.value,
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError:
        # Two causes possible: (a) unique-constraint race — another request
        # just created it; fetch and return. (b) FK violation — decision_id
        # doesn't exist. Differentiate by re-fetching; None means the FK
        # was invalid, so we surface a 404 instead of a 500.
        await session.rollback()
        result = await session.execute(
            select(BJRGate5Decision)
            .where(BJRGate5Decision.decision_id == decision_id)
            .with_for_update()
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            raise HTTPException(404, "Decision not found") from None
        return existing
    return row


async def _maybe_finalize_gate5(session, gate5: BJRGate5Decision, decision_id: str) -> None:
    """When both halves have decided, set final_decision + lock the decision.

    The row is held by SELECT FOR UPDATE from `_ensure_gate5_row`, so the
    "both decided" check runs on the latest state — no lost-update race even
    if the other half was committed milliseconds earlier.
    """
    k_decided = gate5.komisaris_decision is not None
    l_decided = gate5.legal_decision is not None
    if not (k_decided and l_decided):
        return
    approved = Gate5FinalDecision.APPROVED.value
    both_approved = gate5.komisaris_decision == approved and gate5.legal_decision == approved
    if both_approved:
        # Attempt the state-machine transition FIRST. Only if it succeeds do we
        # set final_decision=approved. Prevents inconsistent state where Gate 5
        # looks approved but the decision wasn't locked (e.g., decision in a
        # non-gate_5 state — though _assert_decision_in_gate5 should prevent
        # this earlier, we defend at finalization too).
        locked = await transition_decision_status(
            session, decision_id, DecisionStatus.BJR_LOCKED.value
        )
        if not locked:
            raise HTTPException(
                409,
                "Decision state no longer allows locking. "
                "Gate 5 halves recorded; re-transition to 'bjr_gate_5' and retry.",
            )
        d_result = await session.execute(
            select(StrategicDecision).where(StrategicDecision.id == decision_id)
        )
        decision = d_result.scalar_one()
        now = datetime.now(UTC)
        gate5.final_decision = approved
        gate5.locked_at = now
        decision.is_bjr_locked = True
        decision.locked_at = now
        decision.locked_by_komisaris_id = gate5.approver_komisaris_id
        decision.locked_by_legal_id = gate5.approver_legal_id
    else:
        gate5.final_decision = Gate5FinalDecision.REJECTED.value
        # Transition the decision to `rejected` so it doesn't stay stuck in
        # `bjr_gate_5` forever. Log but don't fail if the state machine refuses
        # (decision might already have moved on via admin action).
        await transition_decision_status(session, decision_id, DecisionStatus.REJECTED.value)


@gate5_router.get("/{decision_id}/gate5", response_model=Gate5State)
async def get_gate5_state(
    decision_id: str,
    _auth=require_permission("decisions:list"),
):
    async with get_session() as session:
        result = await session.execute(
            select(BJRGate5Decision).where(BJRGate5Decision.decision_id == decision_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(404, "Gate 5 not initiated for this decision")
    return _gate5_to_response(row)


@gate5_router.post("/{decision_id}/gate5/komisaris", response_model=Gate5State)
async def gate5_komisaris(
    decision_id: str,
    payload: Gate5HalfRequest,
    _auth=require_permission("bjr:gate_5_komisaris"),
):
    if payload.decision not in _GATE5_VALID_HALF_DECISIONS:
        raise HTTPException(422, "decision must be 'approved' or 'rejected'")
    async with get_session() as session:
        await _assert_decision_in_gate5(session, decision_id)
        gate5 = await _ensure_gate5_row(session, decision_id)
        if gate5.final_decision != Gate5FinalDecision.PENDING.value:
            raise HTTPException(409, "Gate 5 already finalized")
        if gate5.komisaris_decision is not None:
            raise HTTPException(409, "Komisaris half already decided")
        gate5.approver_komisaris_id = payload.approver_id
        gate5.komisaris_decided_at = datetime.now(UTC)
        gate5.komisaris_decision = payload.decision
        gate5.komisaris_notes = payload.notes
        await _maybe_finalize_gate5(session, gate5, decision_id)
        await session.commit()
        await session.refresh(gate5)
    return _gate5_to_response(gate5)


@gate5_router.post("/{decision_id}/gate5/legal", response_model=Gate5State)
async def gate5_legal(
    decision_id: str,
    payload: Gate5HalfRequest,
    _auth=require_permission("bjr:gate_5_legal"),
):
    if payload.decision not in _GATE5_VALID_HALF_DECISIONS:
        raise HTTPException(422, "decision must be 'approved' or 'rejected'")
    async with get_session() as session:
        await _assert_decision_in_gate5(session, decision_id)
        gate5 = await _ensure_gate5_row(session, decision_id)
        if gate5.final_decision != Gate5FinalDecision.PENDING.value:
            raise HTTPException(409, "Gate 5 already finalized")
        if gate5.legal_decision is not None:
            raise HTTPException(409, "Legal half already decided")
        gate5.approver_legal_id = payload.approver_id
        gate5.legal_decided_at = datetime.now(UTC)
        gate5.legal_decision = payload.decision
        gate5.legal_notes = payload.notes
        await _maybe_finalize_gate5(session, gate5, decision_id)
        await session.commit()
        await session.refresh(gate5)
    return _gate5_to_response(gate5)


def _gate5_to_response(g: BJRGate5Decision) -> Gate5State:
    return Gate5State(
        id=str(g.id),
        decision_id=str(g.decision_id),
        final_decision=g.final_decision,
        approver_komisaris_id=(str(g.approver_komisaris_id) if g.approver_komisaris_id else None),
        komisaris_decided_at=g.komisaris_decided_at,
        komisaris_decision=g.komisaris_decision,
        komisaris_notes=g.komisaris_notes,
        approver_legal_id=str(g.approver_legal_id) if g.approver_legal_id else None,
        legal_decided_at=g.legal_decided_at,
        legal_decision=g.legal_decision,
        legal_notes=g.legal_notes,
        locked_at=g.locked_at,
        sla_deadline=g.sla_deadline,
        is_sla_breached=g.is_sla_breached,
    )
