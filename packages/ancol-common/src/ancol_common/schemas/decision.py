"""StrategicDecision schemas — the BJR orchestration root entity.

A StrategicDecision aggregates the evidence needed to defend a board decision
under Indonesian Business Judgment Rule (UU PT Pasal 97(5)). One Decision
bundles: 1 RKAB line + 1 Feasibility Study + 1 Due Diligence + N MoMs +
N Contracts + post-decision monitoring reports.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class InitiativeType(StrEnum):
    """Classification of the business initiative a Decision represents."""

    INVESTMENT = "investment"
    PARTNERSHIP = "partnership"
    CAPEX = "capex"
    DIVESTMENT = "divestment"
    MAJOR_CONTRACT = "major_contract"
    RUPS_ITEM = "rups_item"
    ORGANIZATIONAL_CHANGE = "organizational_change"


class DecisionStatus(StrEnum):
    """StrategicDecision state machine (14 terminal/non-terminal states)."""

    IDEATION = "ideation"
    DD_IN_PROGRESS = "dd_in_progress"
    FS_IN_PROGRESS = "fs_in_progress"
    RKAB_VERIFIED = "rkab_verified"
    BOARD_PROPOSED = "board_proposed"
    ORGAN_APPROVAL_PENDING = "organ_approval_pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    MONITORING = "monitoring"
    BJR_GATE_5 = "bjr_gate_5"
    BJR_LOCKED = "bjr_locked"
    ARCHIVED = "archived"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class EvidenceType(StrEnum):
    """Polymorphic evidence types linked to a Decision via decision_evidence."""

    MOM = "mom"
    CONTRACT = "contract"
    DD_REPORT = "dd_report"
    FS_REPORT = "fs_report"
    SPI_REPORT = "spi_report"
    AUDIT_COMMITTEE_REPORT = "audit_committee_report"
    OJK_DISCLOSURE = "ojk_disclosure"
    ORGAN_APPROVAL = "organ_approval"
    RKAB_LINE = "rkab_line"
    RJPP_THEME = "rjpp_theme"


class EvidenceRelationship(StrEnum):
    """How a piece of evidence relates to the Decision."""

    AUTHORIZES = "authorizes"
    DOCUMENTS = "documents"
    SUPPORTS = "supports"
    MONITORS = "monitors"
    DISCLOSES = "discloses"


class RKABApprovalStatus(StrEnum):
    """Approval chain for an RKAB line item."""

    DRAFT = "draft"
    DIREKSI_APPROVED = "direksi_approved"
    DEWAS_APPROVED = "dewas_approved"
    RUPS_APPROVED = "rups_approved"
    SUPERSEDED = "superseded"


# -- Schemas --


class StrategicDecisionBase(BaseModel):
    """Shared fields between create/update/read forms."""

    title: str = Field(min_length=3, max_length=500)
    description: str | None = None
    initiative_type: InitiativeType
    value_idr: float | None = Field(default=None, ge=0.0)


class StrategicDecisionCreate(StrategicDecisionBase):
    """Payload for POST /api/decisions."""

    rkab_line_id: str | None = None
    rjpp_theme_id: str | None = None
    business_owner_id: str
    legal_owner_id: str | None = None


class StrategicDecisionUpdate(BaseModel):
    """Payload for PATCH /api/decisions/{id}."""

    title: str | None = None
    description: str | None = None
    initiative_type: InitiativeType | None = None
    value_idr: float | None = None
    rkab_line_id: str | None = None
    rjpp_theme_id: str | None = None
    legal_owner_id: str | None = None
    status: DecisionStatus | None = None


class StrategicDecisionResponse(StrategicDecisionBase):
    """Response shape for GET /api/decisions/{id}."""

    id: str
    status: DecisionStatus
    rkab_line_id: str | None = None
    rjpp_theme_id: str | None = None
    business_owner_id: str
    legal_owner_id: str | None = None
    bjr_readiness_score: float | None = Field(default=None, ge=0.0, le=100.0)
    corporate_compliance_score: float | None = Field(default=None, ge=0.0, le=100.0)
    regional_compliance_score: float | None = Field(default=None, ge=0.0, le=100.0)
    is_bjr_locked: bool = False
    locked_at: datetime | None = None
    locked_by_komisaris_id: str | None = None
    locked_by_legal_id: str | None = None
    gcs_passport_uri: str | None = None
    created_at: datetime
    updated_at: datetime


class DecisionEvidenceLink(BaseModel):
    """Payload for POST /api/decisions/{id}/evidence."""

    evidence_type: EvidenceType
    evidence_id: str
    relationship_type: EvidenceRelationship = EvidenceRelationship.DOCUMENTS


class DecisionEvidenceResponse(BaseModel):
    """Evidence link with ID (for deletion)."""

    id: str
    decision_id: str
    evidence_type: EvidenceType
    evidence_id: str
    relationship_type: EvidenceRelationship
    created_at: datetime


# -- RKAB / RJPP registry schemas --


class RKABLineItemBase(BaseModel):
    fiscal_year: int = Field(ge=2020, le=2100)
    code: str = Field(min_length=1, max_length=100)
    category: str
    activity_name: str
    description: str | None = None
    budget_idr: float = Field(ge=0.0)


class RKABLineItemCreate(RKABLineItemBase):
    pass


class RKABLineItemResponse(RKABLineItemBase):
    id: str
    approval_status: RKABApprovalStatus
    rups_approval_date: date | None = None
    is_active: bool
    effective_from: date | None = None
    effective_until: date | None = None
    created_at: datetime


class RKABMatchRequest(BaseModel):
    """Semantic match a decision description against RKAB line items."""

    decision_title: str
    decision_description: str | None = None
    fiscal_year: int


class RKABMatchCandidate(BaseModel):
    rkab_line_id: str
    code: str
    activity_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str | None = None


class RKABMatchResponse(BaseModel):
    candidates: list[RKABMatchCandidate]
    best_match: RKABMatchCandidate | None = None


class RJPPThemeBase(BaseModel):
    period_start_year: int = Field(ge=2020, le=2100)
    period_end_year: int = Field(ge=2020, le=2100)
    theme_name: str
    description: str | None = None


class RJPPThemeCreate(RJPPThemeBase):
    target_metrics: dict = Field(default_factory=dict)


class RJPPThemeResponse(RJPPThemeBase):
    id: str
    target_metrics: dict
    is_active: bool
    created_at: datetime


# -- Retroactive bundling --


class RetroactiveProposeRequest(BaseModel):
    """POST /api/decisions/retroactive-propose — propose Decision from existing MoM."""

    document_id: str


class ProposedDecisionDraft(BaseModel):
    """AI-proposed Decision draft with top-3 RKAB/RJPP candidates."""

    proposed_title: str
    proposed_description: str
    proposed_initiative_type: InitiativeType
    rkab_candidates: list[RKABMatchCandidate] = []
    rjpp_candidates: list[RKABMatchCandidate] = []
    reasoning: str | None = None
