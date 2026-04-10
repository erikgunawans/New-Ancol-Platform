"""Comparison & Reasoning Agent (Agent 3) input/output schemas."""

from __future__ import annotations

from pydantic import BaseModel

from .mom import ComplianceStatus, FindingSeverity, ProcessingMetadata


class ComplianceFinding(BaseModel):
    """A single compliance finding with reasoning chain."""

    finding_id: str
    resolution_number: str
    regulation_id: str
    clause_id: str
    compliance_status: ComplianceStatus
    severity: FindingSeverity
    title: str
    description: str
    chain_of_thought: str  # Full reasoning explanation
    evidence_refs: list[str]  # MoM paragraph + regulation clause refs
    current_wording: str | None = None
    is_red_flag: bool = False
    red_flag_type: str | None = None  # "quorum", "rpt", "conflict_of_interest", etc.


class ConsistencyCheck(BaseModel):
    """Substantive consistency analysis result."""

    check_type: str  # "data_trend", "resolution_data_match", "copy_paste_detection"
    description: str
    is_consistent: bool
    details: str


class RedFlagSummary(BaseModel):
    """Summary of detected red flags."""

    total_count: int
    critical_count: int
    flags: list[dict]  # {type, description, evidence}


class ComparisonInput(BaseModel):
    """Input to the Comparison & Reasoning Agent."""

    document_id: str
    extraction_id: str
    regulatory_context_id: str
    structured_mom_json: dict
    regulatory_mapping_json: dict
    historical_data: dict | None = None  # Prior MoMs for same topics
    related_party_entities: list[dict] = []


class ComparisonOutput(BaseModel):
    """Output from the Comparison & Reasoning Agent."""

    document_id: str
    findings: list[ComplianceFinding]
    red_flags: RedFlagSummary
    consistency_report: list[ConsistencyCheck]
    substantive_score: float  # 0-100
    regulatory_score: float  # 0-100
    processing_metadata: ProcessingMetadata
