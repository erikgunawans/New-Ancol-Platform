"""Contract lifecycle schemas — the data contract for CLM expansion."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from .mom import ProcessingMetadata

# -- Enums --


class ContractType(StrEnum):
    NDA = "nda"
    VENDOR = "vendor"
    SALE_PURCHASE = "sale_purchase"
    JOINT_VENTURE = "joint_venture"
    LAND_LEASE = "land_lease"
    EMPLOYMENT = "employment"
    SOP_BOARD_RESOLUTION = "sop_board_resolution"


class ContractStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    EXECUTED = "executed"
    ACTIVE = "active"
    EXPIRING = "expiring"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    AMENDED = "amended"
    FAILED = "failed"


class RiskLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# -- Value Objects --


class ContractParty(BaseModel):
    """A party to a contract (principal, counterparty, guarantor)."""

    name: str
    role: str  # "principal", "counterparty", "guarantor"
    entity_type: str  # "internal", "external", "related_party"
    related_party_entity_id: str | None = None
    contact_email: str | None = None


class ContractClause(BaseModel):
    """An extracted or drafted clause within a contract."""

    clause_number: str
    title: str
    text: str
    category: str  # "termination", "indemnification", "confidentiality", etc.
    risk_level: RiskLevel | None = None
    risk_reason: str | None = None
    is_from_library: bool = False
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class ContractMetadata(BaseModel):
    """Summary metadata for a contract record."""

    id: str
    title: str
    contract_number: str | None = None
    contract_type: ContractType
    status: ContractStatus
    parties: list[ContractParty] = []
    effective_date: date | None = None
    expiry_date: date | None = None
    total_value: float | None = None
    currency: str = "IDR"
    risk_level: RiskLevel | None = None
    risk_score: float | None = Field(None, ge=0.0, le=100.0)
    gcs_uri: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ContractExtractionOutput(BaseModel):
    """Output from Gemini extraction of a contract document."""

    contract_id: str
    clauses: list[ContractClause] = []
    parties: list[ContractParty] = []
    key_dates: dict = Field(default_factory=dict)
    financial_terms: dict = Field(default_factory=dict)
    risk_summary: dict = Field(default_factory=dict)
    processing_metadata: ProcessingMetadata
