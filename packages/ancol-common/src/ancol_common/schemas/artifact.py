"""BJR artifact schemas — Due Diligence, Feasibility Study, SPI report,
Audit Committee report, Material Disclosure, Organ Approval.

Each artifact is a first-class entity linkable to a StrategicDecision via
the `decision_evidence` polymorphic join.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class DDRiskRating(StrEnum):
    """Risk rating on a Due Diligence report. Distinct from contract risk_level
    because DD considers full strategic risk including geopolitical/regulatory."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OrganApprovalType(StrEnum):
    """Which corporate organ granted approval."""

    KOMISARIS = "komisaris"
    DEWAS = "dewas"
    RUPS = "rups"


class SPIReportType(StrEnum):
    """Classification of Sistem Pengendalian Internal reports."""

    ROUTINE = "routine"
    INCIDENT = "incident"
    SPECIAL_AUDIT = "special_audit"
    FOLLOW_UP = "follow_up"


# -- Due Diligence --


class DueDiligenceReportCreate(BaseModel):
    decision_id: str
    title: str
    summary: str | None = None
    findings: dict = Field(default_factory=dict)
    risk_rating: DDRiskRating
    gcs_uri: str | None = None


class DueDiligenceReportResponse(DueDiligenceReportCreate):
    id: str
    prepared_by: str
    reviewed_by_legal: str | None = None
    review_date: date | None = None
    created_at: datetime


# -- Feasibility Study --


class FeasibilityStudyReportCreate(BaseModel):
    decision_id: str
    title: str
    financial_projections: dict = Field(default_factory=dict)
    rjpp_alignment_theme_id: str | None = None
    assumptions: dict = Field(default_factory=dict)
    gcs_uri: str | None = None


class FeasibilityStudyReportResponse(FeasibilityStudyReportCreate):
    id: str
    prepared_by: str
    reviewed_by_finance: str | None = None
    review_date: date | None = None
    created_at: datetime


# -- SPI Report --


class SPIReportCreate(BaseModel):
    period_start: date
    period_end: date
    report_type: SPIReportType
    findings: dict = Field(default_factory=dict)
    related_decision_ids: list[str] = Field(default_factory=list)
    gcs_uri: str | None = None


class SPIReportResponse(SPIReportCreate):
    id: str
    submitted_by: str
    sent_to_direksi_at: datetime | None = None
    sent_to_audit_committee_at: datetime | None = None
    sent_to_dewas_at: datetime | None = None
    created_at: datetime


# -- Audit Committee Report --


class AuditCommitteeReportCreate(BaseModel):
    meeting_date: date
    agenda_items: list[dict] = Field(default_factory=list)
    decisions_reviewed: list[str] = Field(default_factory=list)
    findings: str | None = None
    recommendations: str | None = None
    gcs_uri: str | None = None


class AuditCommitteeReportResponse(AuditCommitteeReportCreate):
    id: str
    secretary_id: str
    created_at: datetime


# -- Material Disclosure --


class MaterialDisclosureCreate(BaseModel):
    disclosure_type: str  # e.g. "keterbukaan informasi material"
    decision_id: str | None = None
    ojk_filing_ref: str | None = None
    idx_filing_ref: str | None = None
    submission_date: date
    deadline_date: date
    gcs_uri: str | None = None


class MaterialDisclosureResponse(MaterialDisclosureCreate):
    id: str
    is_on_time: bool
    filed_by: str
    created_at: datetime


# -- Organ Approval --


class OrganApprovalCreate(BaseModel):
    approval_type: OrganApprovalType
    decision_id: str
    approval_date: date
    conditions_text: str | None = None
    meeting_reference: str | None = None
    gcs_uri: str | None = None


class OrganApprovalResponse(OrganApprovalCreate):
    id: str
    approver_user_id: str
    created_at: datetime
