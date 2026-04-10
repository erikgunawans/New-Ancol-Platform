"""Extraction Agent (Agent 1) input/output schemas."""

from __future__ import annotations

from pydantic import BaseModel

from .mom import (
    Attendee,
    CrossReference,
    DeviationFlag,
    PerformanceData,
    ProcessingMetadata,
    Resolution,
    SectionMapping,
    StructuredMoM,
)


class TemplateConfig(BaseModel):
    """MoM template configuration passed to the Extraction Agent."""

    template_id: str
    template_name: str
    mom_type: str
    required_sections: list[str]
    quorum_rules: dict
    signature_rules: dict
    field_definitions: dict


class ExtractionInput(BaseModel):
    """Input to the Extraction Agent."""

    document_id: str
    ocr_text: str
    layout_map: dict
    extracted_tables: list[dict]
    page_confidences: list[float]
    template: TemplateConfig
    meeting_metadata: dict | None = None


class ExtractionOutput(BaseModel):
    """Output from the Extraction Agent."""

    document_id: str
    structured_mom: StructuredMoM
    attendees: list[Attendee]
    resolutions: list[Resolution]
    performance_data: PerformanceData | None = None
    sections: list[SectionMapping]
    cross_references: list[CrossReference]
    structural_score: float  # 0-100
    field_confidence: dict[str, float]
    deviation_flags: list[DeviationFlag]
    low_confidence_fields: list[str]
    processing_metadata: ProcessingMetadata
