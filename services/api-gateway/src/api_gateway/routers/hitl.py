"""HITL (Human-in-the-Loop) review queue API."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from ancol_common.auth.mfa import require_mfa_verified
from ancol_common.auth.rbac import check_gate_permission, get_user_visible_gates, require_permission
from ancol_common.config import get_settings
from ancol_common.db.connection import get_session
from ancol_common.db.models import (
    ComplianceFindingRecord,
    Document,
    Extraction,
    HitlDecisionRecord,
    RegulatoryContext,
    Report,
)
from ancol_common.db.repository import transition_document_status
from ancol_common.notifications.dispatcher import notify_gate_reviewers
from ancol_common.pubsub.publisher import publish_message
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select

router = APIRouter(prefix="/hitl", tags=["HITL Review"], dependencies=[require_mfa_verified()])


class HitlQueueItem(BaseModel):
    document_id: str
    filename: str
    gate: str
    status: str
    meeting_date: str | None = None
    assigned_at: datetime | None = None
    sla_deadline: datetime | None = None


class HitlQueueResponse(BaseModel):
    items: list[HitlQueueItem]
    total: int


class HitlReviewDetail(BaseModel):
    document_id: str
    gate: str
    ai_output: dict
    deviation_flags: list | None = None
    red_flags: dict | None = None
    scorecard: dict | None = None


class HitlDecisionRequest(BaseModel):
    decision: str  # "approved", "rejected", "modified"
    reviewer_id: str
    reviewer_role: str
    modified_data: dict | None = None
    modification_summary: str | None = None
    notes: str | None = None


class HitlDecisionResponse(BaseModel):
    decision_id: str
    document_id: str
    gate: str
    decision: str
    next_status: str


GATE_STATUS_MAP = {
    "gate_1": "hitl_gate_1",
    "gate_2": "hitl_gate_2",
    "gate_3": "hitl_gate_3",
    "gate_4": "hitl_gate_4",
}

GATE_APPROVE_TRANSITIONS = {
    "hitl_gate_1": "researching",
    "hitl_gate_2": "comparing",
    "hitl_gate_3": "reporting",
    "hitl_gate_4": "complete",
}

GATE_ENTITY_TYPE = {
    "hitl_gate_1": "extraction",
    "hitl_gate_2": "regulatory_context",
    "hitl_gate_3": "compliance_findings",
    "hitl_gate_4": "report",
}


@router.get("/queue", response_model=HitlQueueResponse)
async def get_review_queue(
    request: Request,
    _auth=require_permission("hitl:decide"),
    gate: str | None = Query(None),
    limit: int = Query(50, le=200),
):
    """Get the HITL review queue — filtered to gates the user's role can review."""
    user_role = request.state.user_role
    visible_gates = get_user_visible_gates(user_role)

    if gate and gate in GATE_STATUS_MAP:
        gate_statuses = [GATE_STATUS_MAP[gate]]
        # Filter to only gates this role can see
        gate_statuses = [s for s in gate_statuses if s in visible_gates]
    else:
        gate_statuses = visible_gates

    if not gate_statuses:
        return HitlQueueResponse(items=[], total=0)

    async with get_session() as session:
        query = (
            select(Document)
            .where(Document.status.in_(gate_statuses))
            .order_by(Document.updated_at.asc())
            .limit(limit)
        )
        result = await session.execute(query)
        docs = result.scalars().all()

    items = [
        HitlQueueItem(
            document_id=str(d.id),
            filename=d.filename,
            gate=d.status,
            status=d.status,
            meeting_date=d.meeting_date.isoformat() if d.meeting_date else None,
        )
        for d in docs
    ]

    return HitlQueueResponse(items=items, total=len(items))


@router.get("/review/{document_id}", response_model=HitlReviewDetail)
async def get_review_detail(
    document_id: str,
    request: Request,
    _auth=require_permission("hitl:decide"),
):
    """Get the AI output for a document pending HITL review."""
    async with get_session() as session:
        doc = await session.get(Document, uuid.UUID(document_id))
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        gate = doc.status

        if not check_gate_permission(request.state.user_role, gate):
            raise HTTPException(
                status_code=403,
                detail=f"You do not have permission to review {gate}",
            )
        ai_output = {}
        deviation_flags = None
        red_flags = None
        scorecard = None

        if gate == "hitl_gate_1":
            stmt = (
                select(Extraction)
                .where(Extraction.document_id == doc.id)
                .order_by(Extraction.created_at.desc())
            )
            result = await session.execute(stmt)
            extraction = result.scalars().first()
            if extraction:
                ai_output = extraction.structured_mom
                deviation_flags = extraction.deviation_flags

        elif gate == "hitl_gate_2":
            stmt = (
                select(RegulatoryContext)
                .where(RegulatoryContext.document_id == doc.id)
                .order_by(RegulatoryContext.created_at.desc())
            )
            result = await session.execute(stmt)
            ctx = result.scalars().first()
            if ctx:
                ai_output = ctx.regulatory_mapping

        elif gate == "hitl_gate_3":
            stmt = (
                select(ComplianceFindingRecord)
                .where(ComplianceFindingRecord.document_id == doc.id)
                .order_by(ComplianceFindingRecord.created_at.desc())
            )
            result = await session.execute(stmt)
            findings = result.scalars().first()
            if findings:
                ai_output = findings.findings
                red_flags = findings.red_flags

        elif gate == "hitl_gate_4":
            stmt = (
                select(Report)
                .where(Report.document_id == doc.id)
                .order_by(Report.created_at.desc())
            )
            result = await session.execute(stmt)
            report = result.scalars().first()
            if report:
                ai_output = report.report_data
                scorecard = {
                    "structural": float(report.structural_score),
                    "substantive": float(report.substantive_score),
                    "regulatory": float(report.regulatory_score),
                    "composite": float(report.composite_score),
                }

    return HitlReviewDetail(
        document_id=document_id,
        gate=gate,
        ai_output=ai_output,
        deviation_flags=deviation_flags,
        red_flags=red_flags,
        scorecard=scorecard,
    )


@router.post("/decide/{document_id}", response_model=HitlDecisionResponse)
async def submit_decision(
    document_id: str,
    body: HitlDecisionRequest,
    request: Request,
    _auth=require_permission("hitl:decide"),
):
    """Submit a HITL decision (approve/reject/modify)."""
    settings = get_settings()

    async with get_session() as session:
        doc = await session.get(Document, uuid.UUID(document_id))
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        gate = doc.status
        if gate not in GATE_APPROVE_TRANSITIONS:
            raise HTTPException(status_code=400, detail=f"Document not in a HITL gate: {gate}")

        if not check_gate_permission(request.state.user_role, gate):
            raise HTTPException(
                status_code=403,
                detail=f"You do not have permission to decide on {gate}",
            )

        entity_type = GATE_ENTITY_TYPE.get(gate, "unknown")
        now = datetime.now(UTC)

        # Record decision
        decision_record = HitlDecisionRecord(
            document_id=doc.id,
            gate=gate.replace("hitl_", ""),
            reviewed_entity_type=entity_type,
            reviewed_entity_id=doc.id,  # Simplified — points to document
            decision=body.decision,
            reviewer_id=uuid.UUID(body.reviewer_id),
            reviewer_role=body.reviewer_role,
            original_data=None,
            modified_data=body.modified_data,
            modification_summary=body.modification_summary,
            notes=body.notes,
            assigned_at=now,
            decided_at=now,
            sla_deadline=now + timedelta(hours=settings.hitl_sla_hours),
        )
        session.add(decision_record)
        await session.flush()
        decision_id = str(decision_record.id)
        doc_filename = doc.filename

    # Transition status
    if body.decision == "approved":
        next_status = GATE_APPROVE_TRANSITIONS[gate]
    elif body.decision == "rejected":
        next_status = "rejected"
    else:  # modified — approve with changes
        next_status = GATE_APPROVE_TRANSITIONS[gate]

    async with get_session() as session:
        await transition_document_status(session, document_id, next_status)

    # Publish event to trigger next agent
    publish_message(
        f"hitl-{gate.replace('hitl_', '')}-decided",
        {
            "document_id": document_id,
            "decision": body.decision,
            "gate": gate,
            "next_status": next_status,
        },
    )

    # Notify reviewers for the next gate (if approved and entering a new HITL gate)
    if next_status.startswith("hitl_gate_"):
        async with get_session() as session:
            await notify_gate_reviewers(
                document_id=document_id,
                document_name=doc_filename,
                gate=next_status,
                session=session,
            )

    return HitlDecisionResponse(
        decision_id=decision_id,
        document_id=document_id,
        gate=gate,
        decision=body.decision,
        next_status=next_status,
    )
