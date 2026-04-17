"""BJR artifact CRUD — Due Diligence, Feasibility Study, SPI report,
Audit Committee report, Material Disclosure, Organ Approval.

Each of the 6 artifact types is mounted under /api/artifacts/{type}. Every
artifact is linkable to a StrategicDecision as evidence (decision_evidence
polymorphic join) — but that linkage happens via the decisions router in
Phase 6.3. Here we just store the artifacts themselves.
"""

from __future__ import annotations

from datetime import date, datetime

from ancol_common.auth.rbac import require_permission
from ancol_common.db.connection import get_session
from ancol_common.db.models import (
    AuditCommitteeReport,
    DueDiligenceReport,
    FeasibilityStudyReport,
    MaterialDisclosure,
    OrganApproval,
    SPIReport,
)
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

router = APIRouter(prefix="/artifacts", tags=["BJR Artifacts"])


# ══════════════════════════════════════════════════════════════════════════════
# Due Diligence reports (PD-01-DD)
# ══════════════════════════════════════════════════════════════════════════════


class DDReportCreate(BaseModel):
    decision_id: str
    title: str = Field(min_length=1, max_length=500)
    summary: str | None = None
    findings: dict = Field(default_factory=dict)
    risk_rating: str  # low | medium | high | critical
    gcs_uri: str | None = None
    prepared_by: str


class DDReportResponse(BaseModel):
    id: str
    decision_id: str
    title: str
    summary: str | None = None
    findings: dict | None = None
    risk_rating: str
    gcs_uri: str | None = None
    prepared_by: str
    reviewed_by_legal: str | None = None
    review_date: date | None = None
    created_at: datetime


class DDReportReviewRequest(BaseModel):
    reviewed_by_legal: str
    review_date: date


@router.post("/dd", response_model=DDReportResponse)
async def create_dd_report(
    payload: DDReportCreate,
    _auth=require_permission("dd:create"),
):
    async with get_session() as session:
        report = DueDiligenceReport(
            decision_id=payload.decision_id,
            title=payload.title,
            summary=payload.summary,
            findings=payload.findings,
            risk_rating=payload.risk_rating,
            gcs_uri=payload.gcs_uri,
            prepared_by=payload.prepared_by,
        )
        session.add(report)
        await session.commit()
        await session.refresh(report)
    return _dd_to_response(report)


@router.get("/dd", response_model=list[DDReportResponse])
async def list_dd_reports(
    _auth=require_permission("dd:review"),
    decision_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    async with get_session() as session:
        query = select(DueDiligenceReport)
        if decision_id:
            query = query.where(DueDiligenceReport.decision_id == decision_id)
        result = await session.execute(query.limit(limit))
        return [_dd_to_response(r) for r in result.scalars().all()]


@router.get("/dd/{dd_id}", response_model=DDReportResponse)
async def get_dd_report(dd_id: str, _auth=require_permission("dd:review")):
    async with get_session() as session:
        r = (
            await session.execute(
                select(DueDiligenceReport).where(DueDiligenceReport.id == dd_id)
            )
        ).scalar_one_or_none()
    if r is None:
        raise HTTPException(404, "DD report not found")
    return _dd_to_response(r)


@router.post("/dd/{dd_id}/review", response_model=DDReportResponse)
async def review_dd_report(
    dd_id: str,
    payload: DDReportReviewRequest,
    _auth=require_permission("dd:review"),
):
    async with get_session() as session:
        r = (
            await session.execute(
                select(DueDiligenceReport).where(DueDiligenceReport.id == dd_id)
            )
        ).scalar_one_or_none()
        if r is None:
            raise HTTPException(404, "DD report not found")
        r.reviewed_by_legal = payload.reviewed_by_legal
        r.review_date = payload.review_date
        await session.commit()
        await session.refresh(r)
    return _dd_to_response(r)


def _dd_to_response(r: DueDiligenceReport) -> DDReportResponse:
    return DDReportResponse(
        id=str(r.id),
        decision_id=str(r.decision_id),
        title=r.title,
        summary=r.summary,
        findings=r.findings,
        risk_rating=r.risk_rating,
        gcs_uri=r.gcs_uri,
        prepared_by=str(r.prepared_by),
        reviewed_by_legal=str(r.reviewed_by_legal) if r.reviewed_by_legal else None,
        review_date=r.review_date,
        created_at=r.created_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Feasibility Study reports (PD-02-FS)
# ══════════════════════════════════════════════════════════════════════════════


class FSReportCreate(BaseModel):
    decision_id: str
    title: str = Field(min_length=1, max_length=500)
    financial_projections: dict = Field(default_factory=dict)
    rjpp_alignment_theme_id: str | None = None
    assumptions: dict = Field(default_factory=dict)
    gcs_uri: str | None = None
    prepared_by: str


class FSReportResponse(BaseModel):
    id: str
    decision_id: str
    title: str
    financial_projections: dict | None = None
    rjpp_alignment_theme_id: str | None = None
    assumptions: dict | None = None
    gcs_uri: str | None = None
    prepared_by: str
    reviewed_by_finance: str | None = None
    review_date: date | None = None
    created_at: datetime


class FSReportReviewRequest(BaseModel):
    reviewed_by_finance: str
    review_date: date


@router.post("/fs", response_model=FSReportResponse)
async def create_fs_report(
    payload: FSReportCreate,
    _auth=require_permission("fs:create"),
):
    async with get_session() as session:
        report = FeasibilityStudyReport(
            decision_id=payload.decision_id,
            title=payload.title,
            financial_projections=payload.financial_projections,
            rjpp_alignment_theme_id=payload.rjpp_alignment_theme_id,
            assumptions=payload.assumptions,
            gcs_uri=payload.gcs_uri,
            prepared_by=payload.prepared_by,
        )
        session.add(report)
        await session.commit()
        await session.refresh(report)
    return _fs_to_response(report)


@router.get("/fs", response_model=list[FSReportResponse])
async def list_fs_reports(
    _auth=require_permission("fs:review"),
    decision_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    async with get_session() as session:
        query = select(FeasibilityStudyReport)
        if decision_id:
            query = query.where(FeasibilityStudyReport.decision_id == decision_id)
        result = await session.execute(query.limit(limit))
        return [_fs_to_response(r) for r in result.scalars().all()]


@router.get("/fs/{fs_id}", response_model=FSReportResponse)
async def get_fs_report(fs_id: str, _auth=require_permission("fs:review")):
    async with get_session() as session:
        r = (
            await session.execute(
                select(FeasibilityStudyReport).where(FeasibilityStudyReport.id == fs_id)
            )
        ).scalar_one_or_none()
    if r is None:
        raise HTTPException(404, "FS report not found")
    return _fs_to_response(r)


@router.post("/fs/{fs_id}/review", response_model=FSReportResponse)
async def review_fs_report(
    fs_id: str,
    payload: FSReportReviewRequest,
    _auth=require_permission("fs:review"),
):
    async with get_session() as session:
        r = (
            await session.execute(
                select(FeasibilityStudyReport).where(FeasibilityStudyReport.id == fs_id)
            )
        ).scalar_one_or_none()
        if r is None:
            raise HTTPException(404, "FS report not found")
        r.reviewed_by_finance = payload.reviewed_by_finance
        r.review_date = payload.review_date
        await session.commit()
        await session.refresh(r)
    return _fs_to_response(r)


def _fs_to_response(r: FeasibilityStudyReport) -> FSReportResponse:
    return FSReportResponse(
        id=str(r.id),
        decision_id=str(r.decision_id),
        title=r.title,
        financial_projections=r.financial_projections,
        rjpp_alignment_theme_id=(
            str(r.rjpp_alignment_theme_id) if r.rjpp_alignment_theme_id else None
        ),
        assumptions=r.assumptions,
        gcs_uri=r.gcs_uri,
        prepared_by=str(r.prepared_by),
        reviewed_by_finance=str(r.reviewed_by_finance) if r.reviewed_by_finance else None,
        review_date=r.review_date,
        created_at=r.created_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
# SPI (Sistem Pengendalian Internal) reports (POST-13-SPI)
# ══════════════════════════════════════════════════════════════════════════════


class SPIReportCreate(BaseModel):
    period_start: date
    period_end: date
    report_type: str  # routine | incident | special_audit | follow_up
    findings: dict = Field(default_factory=dict)
    related_decision_ids: list[str] = Field(default_factory=list)
    gcs_uri: str | None = None
    submitted_by: str


class SPIReportResponse(BaseModel):
    id: str
    period_start: date
    period_end: date
    report_type: str
    findings: dict | None = None
    related_decision_ids: list[str] | None = None
    gcs_uri: str | None = None
    submitted_by: str
    sent_to_direksi_at: datetime | None = None
    sent_to_audit_committee_at: datetime | None = None
    sent_to_dewas_at: datetime | None = None
    created_at: datetime


@router.post("/spi", response_model=SPIReportResponse)
async def create_spi_report(
    payload: SPIReportCreate,
    _auth=require_permission("spi:submit"),
):
    if payload.period_end < payload.period_start:
        raise HTTPException(422, "period_end must be >= period_start")
    async with get_session() as session:
        report = SPIReport(
            period_start=payload.period_start,
            period_end=payload.period_end,
            report_type=payload.report_type,
            findings=payload.findings,
            related_decision_ids=payload.related_decision_ids,
            gcs_uri=payload.gcs_uri,
            submitted_by=payload.submitted_by,
        )
        session.add(report)
        await session.commit()
        await session.refresh(report)
    return _spi_to_response(report)


@router.get("/spi", response_model=list[SPIReportResponse])
async def list_spi_reports(
    _auth=require_permission("spi:view"),
    limit: int = Query(100, ge=1, le=500),
):
    async with get_session() as session:
        result = await session.execute(
            select(SPIReport).order_by(SPIReport.period_end.desc()).limit(limit)
        )
        return [_spi_to_response(r) for r in result.scalars().all()]


def _spi_to_response(r: SPIReport) -> SPIReportResponse:
    return SPIReportResponse(
        id=str(r.id),
        period_start=r.period_start,
        period_end=r.period_end,
        report_type=r.report_type,
        findings=r.findings,
        related_decision_ids=(
            [str(x) for x in r.related_decision_ids] if r.related_decision_ids else None
        ),
        gcs_uri=r.gcs_uri,
        submitted_by=str(r.submitted_by),
        sent_to_direksi_at=r.sent_to_direksi_at,
        sent_to_audit_committee_at=r.sent_to_audit_committee_at,
        sent_to_dewas_at=r.sent_to_dewas_at,
        created_at=r.created_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Audit Committee reports (POST-14-AUDITCOM)
# ══════════════════════════════════════════════════════════════════════════════


class AuditCommitteeReportCreate(BaseModel):
    meeting_date: date
    agenda_items: list[dict] = Field(default_factory=list)
    decisions_reviewed: list[str] = Field(default_factory=list)
    findings: str | None = None
    recommendations: str | None = None
    gcs_uri: str | None = None
    secretary_id: str


class AuditCommitteeReportResponse(BaseModel):
    id: str
    meeting_date: date
    agenda_items: list[dict] | None = None
    decisions_reviewed: list[str] | None = None
    findings: str | None = None
    recommendations: str | None = None
    gcs_uri: str | None = None
    secretary_id: str
    created_at: datetime


@router.post("/audit-committee", response_model=AuditCommitteeReportResponse)
async def create_audit_committee_report(
    payload: AuditCommitteeReportCreate,
    _auth=require_permission("audit_committee:submit"),
):
    async with get_session() as session:
        report = AuditCommitteeReport(
            meeting_date=payload.meeting_date,
            agenda_items=payload.agenda_items,
            decisions_reviewed=payload.decisions_reviewed,
            findings=payload.findings,
            recommendations=payload.recommendations,
            gcs_uri=payload.gcs_uri,
            secretary_id=payload.secretary_id,
        )
        session.add(report)
        await session.commit()
        await session.refresh(report)
    return _auditcom_to_response(report)


@router.get("/audit-committee", response_model=list[AuditCommitteeReportResponse])
async def list_audit_committee_reports(
    _auth=require_permission("audit_committee:view"),
    limit: int = Query(100, ge=1, le=500),
):
    async with get_session() as session:
        result = await session.execute(
            select(AuditCommitteeReport)
            .order_by(AuditCommitteeReport.meeting_date.desc())
            .limit(limit)
        )
        return [_auditcom_to_response(r) for r in result.scalars().all()]


def _auditcom_to_response(r: AuditCommitteeReport) -> AuditCommitteeReportResponse:
    return AuditCommitteeReportResponse(
        id=str(r.id),
        meeting_date=r.meeting_date,
        agenda_items=r.agenda_items,
        decisions_reviewed=[str(x) for x in r.decisions_reviewed] if r.decisions_reviewed else None,
        findings=r.findings,
        recommendations=r.recommendations,
        gcs_uri=r.gcs_uri,
        secretary_id=str(r.secretary_id),
        created_at=r.created_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Material Disclosures (D-11-DISCLOSE)
# ══════════════════════════════════════════════════════════════════════════════


class MaterialDisclosureCreate(BaseModel):
    disclosure_type: str = Field(max_length=200)
    decision_id: str | None = None
    ojk_filing_ref: str | None = None
    idx_filing_ref: str | None = None
    submission_date: date
    deadline_date: date
    gcs_uri: str | None = None
    filed_by: str


class MaterialDisclosureResponse(BaseModel):
    id: str
    disclosure_type: str
    decision_id: str | None = None
    ojk_filing_ref: str | None = None
    idx_filing_ref: str | None = None
    submission_date: date
    deadline_date: date
    is_on_time: bool
    gcs_uri: str | None = None
    filed_by: str
    created_at: datetime


@router.post("/disclosures", response_model=MaterialDisclosureResponse)
async def create_material_disclosure(
    payload: MaterialDisclosureCreate,
    _auth=require_permission("material_disclosure:file"),
):
    is_on_time = payload.submission_date <= payload.deadline_date
    async with get_session() as session:
        disc = MaterialDisclosure(
            disclosure_type=payload.disclosure_type,
            decision_id=payload.decision_id,
            ojk_filing_ref=payload.ojk_filing_ref,
            idx_filing_ref=payload.idx_filing_ref,
            submission_date=payload.submission_date,
            deadline_date=payload.deadline_date,
            is_on_time=is_on_time,
            gcs_uri=payload.gcs_uri,
            filed_by=payload.filed_by,
        )
        session.add(disc)
        await session.commit()
        await session.refresh(disc)
    return _disclosure_to_response(disc)


@router.get("/disclosures", response_model=list[MaterialDisclosureResponse])
async def list_material_disclosures(
    _auth=require_permission("material_disclosure:file"),
    decision_id: str | None = Query(None),
    is_on_time: bool | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    async with get_session() as session:
        query = select(MaterialDisclosure)
        if decision_id:
            query = query.where(MaterialDisclosure.decision_id == decision_id)
        if is_on_time is not None:
            query = query.where(MaterialDisclosure.is_on_time == is_on_time)
        result = await session.execute(query.limit(limit))
        return [_disclosure_to_response(r) for r in result.scalars().all()]


def _disclosure_to_response(r: MaterialDisclosure) -> MaterialDisclosureResponse:
    return MaterialDisclosureResponse(
        id=str(r.id),
        disclosure_type=r.disclosure_type,
        decision_id=str(r.decision_id) if r.decision_id else None,
        ojk_filing_ref=r.ojk_filing_ref,
        idx_filing_ref=r.idx_filing_ref,
        submission_date=r.submission_date,
        deadline_date=r.deadline_date,
        is_on_time=r.is_on_time,
        gcs_uri=r.gcs_uri,
        filed_by=str(r.filed_by),
        created_at=r.created_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Organ Approvals — Komisaris / Dewan Pengawas / RUPS (D-10-ORGAN)
# ══════════════════════════════════════════════════════════════════════════════


class OrganApprovalCreate(BaseModel):
    approval_type: str  # komisaris | dewas | rups
    decision_id: str
    approver_user_id: str
    approval_date: date
    conditions_text: str | None = None
    meeting_reference: str | None = None
    gcs_uri: str | None = None


class OrganApprovalResponse(BaseModel):
    id: str
    approval_type: str
    decision_id: str
    approver_user_id: str
    approval_date: date
    conditions_text: str | None = None
    meeting_reference: str | None = None
    gcs_uri: str | None = None
    created_at: datetime


@router.post("/organ-approvals", response_model=OrganApprovalResponse)
async def create_organ_approval(
    payload: OrganApprovalCreate,
    _auth=require_permission("organ_approval:sign"),
):
    if payload.approval_type not in ("komisaris", "dewas", "rups"):
        raise HTTPException(422, "approval_type must be one of: komisaris, dewas, rups")
    async with get_session() as session:
        approval = OrganApproval(
            approval_type=payload.approval_type,
            decision_id=payload.decision_id,
            approver_user_id=payload.approver_user_id,
            approval_date=payload.approval_date,
            conditions_text=payload.conditions_text,
            meeting_reference=payload.meeting_reference,
            gcs_uri=payload.gcs_uri,
        )
        session.add(approval)
        await session.commit()
        await session.refresh(approval)
    return _organ_to_response(approval)


@router.get("/organ-approvals", response_model=list[OrganApprovalResponse])
async def list_organ_approvals(
    _auth=require_permission("organ_approval:sign"),
    decision_id: str | None = Query(None),
    approval_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    async with get_session() as session:
        query = select(OrganApproval)
        if decision_id:
            query = query.where(OrganApproval.decision_id == decision_id)
        if approval_type:
            query = query.where(OrganApproval.approval_type == approval_type)
        result = await session.execute(query.limit(limit))
        return [_organ_to_response(r) for r in result.scalars().all()]


def _organ_to_response(r: OrganApproval) -> OrganApprovalResponse:
    return OrganApprovalResponse(
        id=str(r.id),
        approval_type=r.approval_type,
        decision_id=str(r.decision_id),
        approver_user_id=str(r.approver_user_id),
        approval_date=r.approval_date,
        conditions_text=r.conditions_text,
        meeting_reference=r.meeting_reference,
        gcs_uri=r.gcs_uri,
        created_at=r.created_at,
    )
