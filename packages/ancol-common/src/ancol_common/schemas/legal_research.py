"""Legal Research Agent (Agent 2) input/output schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from .mom import ProcessingMetadata


class ApplicableClause(BaseModel):
    """A single regulation clause applicable to a resolution."""

    regulation_id: str  # e.g., "POJK-42-2020"
    article: str  # e.g., "Pasal 15 ayat (2)"
    clause_text: str
    effective_date: date
    expiry_date: date | None = None
    source_type: str  # "internal" or "external"
    domain: str  # e.g., "corporate_governance", "capital_markets"
    retrieval_score: float = Field(ge=0.0, le=1.0)
    retrieval_source_id: str  # links back to Vertex AI Search document


class RegulatoryMapping(BaseModel):
    """Mapping of a single resolution to its applicable regulations."""

    resolution_number: str
    resolution_summary: str
    regulatory_domains: list[str]
    applicable_clauses: list[ApplicableClause]


class RegulatoryFlag(BaseModel):
    """A flag for regulatory overlap or conflict."""

    flag_type: str  # "overlap" or "conflict"
    regulation_a_id: str
    regulation_b_id: str
    description: str
    affected_resolution: str


class CorpusFreshness(BaseModel):
    """Report on regulatory corpus freshness."""

    last_updated: date
    staleness_days: int
    alerts: list[str] = []


class LegalResearchInput(BaseModel):
    """Input to the Legal Research Agent."""

    document_id: str
    extraction_id: str
    structured_mom_json: dict
    meeting_date: date
    resolution_topics: list[dict]


class LegalResearchOutput(BaseModel):
    """Output from the Legal Research Agent."""

    document_id: str
    extraction_id: str
    regulatory_mapping: list[RegulatoryMapping]
    overlap_flags: list[RegulatoryFlag]
    conflict_flags: list[RegulatoryFlag]
    corpus_freshness: CorpusFreshness
    processing_metadata: ProcessingMetadata
