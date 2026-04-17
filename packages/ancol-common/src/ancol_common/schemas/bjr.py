"""BJR Checklist + Gate 5 + Readiness Score schemas.

The 16-item BJR proof checklist per UU PT Pasal 97(5) + PP 23/2022 BJR phases.
Each item has a stable `item_code` used across: BJR Agent output, UI checklist,
Decision Passport PDF, audit trail entries.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ChecklistPhase(StrEnum):
    PRE_DECISION = "pre_decision"
    DECISION = "decision"
    POST_DECISION = "post_decision"


class ChecklistItemStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SATISFIED = "satisfied"
    WAIVED = "waived"
    FLAGGED = "flagged"


class RegulatoryRegime(StrEnum):
    """Classification of which legal regime a regulation or item belongs to.

    Ancol is subject to BOTH corporate (UU PT + OJK) and regional finance
    (PP BUMD + Pergub DKI) regimes. BJR score takes min(corporate, regional).
    """

    CORPORATE = "corporate"
    REGIONAL_FINANCE = "regional_finance"
    LISTING = "listing"
    INTERNAL = "internal"


class RegulationLayer(StrEnum):
    """Four-tier hierarchy of Indonesian regulation by authority."""

    UU = "uu"  # Undang-Undang (law)
    PP = "pp"  # Peraturan Pemerintah (government regulation)
    PERGUB_DKI = "pergub_dki"  # Peraturan Gubernur DKI
    OJK_BEI = "ojk_bei"  # POJK + IDX rules
    INTERNAL = "internal"  # AD/ART, charters, policies


class Gate5FinalDecision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# -- Stable item codes (the contract between agent, UI, PDF, audit trail) --


class BJRItemCode(StrEnum):
    """Stable codes for the 16 BJR checklist items. DO NOT RENAME."""

    # Pre-decision (5)
    PD_01_DD = "PD-01-DD"
    PD_02_FS = "PD-02-FS"
    PD_03_RKAB = "PD-03-RKAB"
    PD_04_RJPP = "PD-04-RJPP"
    PD_05_COI = "PD-05-COI"

    # Decision (6)
    D_06_QUORUM = "D-06-QUORUM"
    D_07_SIGNED = "D-07-SIGNED"
    D_08_RISK = "D-08-RISK"
    D_09_LEGAL = "D-09-LEGAL"
    D_10_ORGAN = "D-10-ORGAN"
    D_11_DISCLOSE = "D-11-DISCLOSE"

    # Post-decision (5)
    POST_12_MONITOR = "POST-12-MONITOR"
    POST_13_SPI = "POST-13-SPI"
    POST_14_AUDITCOM = "POST-14-AUDITCOM"
    POST_15_DEWAS = "POST-15-DEWAS"
    POST_16_ARCHIVE = "POST-16-ARCHIVE"


# Critical items weight 2x in score computation
CRITICAL_ITEMS: frozenset[str] = frozenset(
    {
        BJRItemCode.PD_03_RKAB,
        BJRItemCode.PD_05_COI,
        BJRItemCode.D_06_QUORUM,
        BJRItemCode.D_11_DISCLOSE,
    }
)

# Items scored under the corporate compliance regime
CORPORATE_ITEMS: frozenset[str] = frozenset(
    {
        BJRItemCode.PD_01_DD,
        BJRItemCode.PD_02_FS,
        BJRItemCode.PD_05_COI,
        BJRItemCode.D_06_QUORUM,
        BJRItemCode.D_07_SIGNED,
        BJRItemCode.D_08_RISK,
        BJRItemCode.D_09_LEGAL,
        BJRItemCode.D_11_DISCLOSE,
        BJRItemCode.POST_16_ARCHIVE,
    }
)

# Items scored under the regional finance compliance regime
REGIONAL_ITEMS: frozenset[str] = frozenset(
    {
        BJRItemCode.PD_03_RKAB,
        BJRItemCode.PD_04_RJPP,
        BJRItemCode.PD_05_COI,
        BJRItemCode.D_10_ORGAN,
        BJRItemCode.POST_12_MONITOR,
        BJRItemCode.POST_13_SPI,
        BJRItemCode.POST_14_AUDITCOM,
        BJRItemCode.POST_15_DEWAS,
        BJRItemCode.POST_16_ARCHIVE,
    }
)


# -- Schemas --


class BJRChecklistItem(BaseModel):
    """Single checklist item state."""

    id: str
    decision_id: str
    phase: ChecklistPhase
    item_code: str
    status: ChecklistItemStatus
    ai_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_refs: list[dict] = Field(default_factory=list)
    regulation_basis: list[str] = Field(default_factory=list)
    remediation_note: str | None = None
    last_checked_at: datetime | None = None
    last_checked_by: str | None = None


class BJRReadinessScore(BaseModel):
    """Dual-regime BJR readiness — enforces min(corporate, regional)."""

    decision_id: str
    bjr_readiness_score: float = Field(ge=0.0, le=100.0)
    corporate_compliance_score: float = Field(ge=0.0, le=100.0)
    regional_compliance_score: float = Field(ge=0.0, le=100.0)
    satisfied_count: int = Field(ge=0, le=16)
    flagged_count: int = Field(ge=0, le=16)
    gate_5_unlockable: bool
    computed_at: datetime


class BJRGap(BaseModel):
    """A gap identified by the BJR Compliance Agent."""

    item_code: str
    phase: ChecklistPhase
    current_status: ChecklistItemStatus
    gap_description: str
    recommended_action: str
    regulation_basis: list[str] = Field(default_factory=list)
    severity: str = "medium"  # high | medium | low


class BJRAgentOutput(BaseModel):
    """Output from BJR Compliance Agent — full compute result."""

    decision_id: str
    checklist: list[BJRChecklistItem]
    readiness: BJRReadinessScore
    gaps: list[BJRGap]
    remediation_summary: str | None = None


# -- Gate 5 dual-approval --


class Gate5HalfDecision(BaseModel):
    """One half of Gate 5 dual-approval. Used identically for Komisaris and Legal."""

    decision: str  # "approved" or "rejected" — validated by Gate5FinalDecision at router edge
    notes: str | None = None


class Gate5Response(BaseModel):
    """Current state of Gate 5 dual-approval for a decision."""

    id: str
    decision_id: str
    final_decision: Gate5FinalDecision
    approver_komisaris_id: str | None = None
    komisaris_decided_at: datetime | None = None
    komisaris_notes: str | None = None
    approver_legal_id: str | None = None
    legal_decided_at: datetime | None = None
    legal_notes: str | None = None
    locked_at: datetime | None = None
    sla_deadline: datetime
