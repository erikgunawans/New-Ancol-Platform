"""Reporting Agent (Agent 4) input/output schemas."""

from __future__ import annotations

from pydantic import BaseModel

from .mom import ProcessingMetadata


class ComplianceScorecard(BaseModel):
    """Three-pillar compliance scorecard."""

    structural_score: float  # 0-100
    substantive_score: float  # 0-100
    regulatory_score: float  # 0-100
    composite_score: float  # 0-100 (weighted: 30/35/35)
    weights: dict = {"structural": 0.30, "substantive": 0.35, "regulatory": 0.35}
    trend_3m: float | None = None
    trend_6m: float | None = None
    trend_12m: float | None = None


class CorrectiveSuggestion(BaseModel):
    """Corrective wording suggestion for a finding."""

    finding_id: str
    current_wording: str
    issue_explanation: str
    suggested_wording: str  # In Bahasa Indonesia
    regulatory_basis: str


class ReportingInput(BaseModel):
    """Input to the Reporting Agent."""

    document_id: str
    findings_id: str
    structural_score: float
    findings_json: dict
    historical_scores: list[dict] = []
    report_template: str = "default"


class ReportingOutput(BaseModel):
    """Output from the Reporting Agent."""

    document_id: str
    scorecard: ComplianceScorecard
    corrective_suggestions: list[CorrectiveSuggestion]
    executive_summary: str  # Bahasa Indonesia, 1 page
    detailed_findings_html: str  # HTML for PDF rendering
    report_data: dict  # Full report JSON
    processing_metadata: ProcessingMetadata
