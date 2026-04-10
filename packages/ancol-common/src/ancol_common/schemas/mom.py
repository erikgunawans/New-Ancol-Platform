"""Shared MoM structured JSON schema — the contract between all 4 agents.

This is the single most important file in the system. Changes here cascade
to every agent service. Treat modifications with extreme care.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# -- Enums --


class DocumentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING_OCR = "processing_ocr"
    OCR_COMPLETE = "ocr_complete"
    EXTRACTING = "extracting"
    HITL_GATE_1 = "hitl_gate_1"
    RESEARCHING = "researching"
    HITL_GATE_2 = "hitl_gate_2"
    COMPARING = "comparing"
    HITL_GATE_3 = "hitl_gate_3"
    REPORTING = "reporting"
    HITL_GATE_4 = "hitl_gate_4"
    COMPLETE = "complete"
    FAILED = "failed"
    REJECTED = "rejected"


class DocumentFormat(StrEnum):
    PDF = "pdf"
    SCAN = "scan"
    WORD = "word"
    IMAGE = "image"


class MomType(StrEnum):
    REGULAR = "regular"
    CIRCULAR = "circular"
    EXTRAORDINARY = "extraordinary"


class FindingSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ComplianceStatus(StrEnum):
    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    SILENT = "silent"


class HitlGate(StrEnum):
    GATE_1 = "gate_1"
    GATE_2 = "gate_2"
    GATE_3 = "gate_3"
    GATE_4 = "gate_4"


class HitlDecisionType(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class UserRole(StrEnum):
    CORP_SECRETARY = "corp_secretary"
    INTERNAL_AUDITOR = "internal_auditor"
    KOMISARIS = "komisaris"
    LEGAL_COMPLIANCE = "legal_compliance"
    ADMIN = "admin"


# -- Shared Value Objects --


class Attendee(BaseModel):
    """A meeting attendee extracted from the MoM."""

    name: str
    title: str | None = None  # e.g., "Direktur Utama"
    role: str | None = None  # e.g., "chairman", "secretary", "member"
    present: bool = True
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class Resolution(BaseModel):
    """A numbered resolution from the meeting."""

    number: str  # e.g., "3.2"
    text: str
    assignee: str | None = None
    deadline: date | None = None
    agenda_item: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class PerformanceMetric(BaseModel):
    """A single metric from 'Result of the Month'."""

    name: str  # e.g., "Revenue", "Visitor Count"
    value: float
    unit: str  # e.g., "IDR billion", "persons"
    period: str  # e.g., "Q1 2025", "March 2025"
    year_over_year_change: float | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class PerformanceData(BaseModel):
    """Structured performance data from 'Result of the Month'."""

    metrics: list[PerformanceMetric] = []
    reporting_period: str | None = None
    notes: str | None = None


class SectionMapping(BaseModel):
    """Mapping of a document section to its content."""

    section_name: str  # e.g., "header", "agenda", "attendees", "resolutions"
    start_page: int | None = None
    start_paragraph: int | None = None
    content_summary: str | None = None
    present: bool = True


class DeviationFlag(BaseModel):
    """A structural deviation from the expected template."""

    field: str
    expected: str
    actual: str | None = None
    severity: str = "medium"  # low, medium, high
    description: str


class CrossReference(BaseModel):
    """Reference to a prior MoM or external regulation found in the text."""

    reference_text: str
    reference_type: str  # "prior_mom", "regulation", "other"
    target_id: str | None = None  # e.g., prior meeting date or regulation ID
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


# -- Structured MoM (the core data structure) --


class StructuredMoM(BaseModel):
    """The complete structured representation of a Minutes of Meeting document."""

    # Meeting metadata
    meeting_date: date
    meeting_type: MomType
    meeting_number: str | None = None
    location: str | None = None

    # Participants
    chairman: str | None = None
    secretary: str | None = None
    attendees: list[Attendee] = []
    total_directors: int | None = None
    directors_present: int | None = None
    quorum_met: bool | None = None

    # Content
    agenda_items: list[str] = []
    sections: list[SectionMapping] = []
    resolutions: list[Resolution] = []
    performance_data: PerformanceData | None = None
    cross_references: list[CrossReference] = []

    # Signatures
    signers: list[str] = []
    signatures_complete: bool | None = None

    # Raw text (for reference)
    full_text: str | None = None


# -- Agent I/O Schemas --


class ProcessingMetadata(BaseModel):
    """Metadata about agent processing."""

    agent_version: str
    model_used: str
    processing_time_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
