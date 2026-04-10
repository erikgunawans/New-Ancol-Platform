"""Document metadata schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from .mom import DocumentFormat, DocumentStatus, MomType


class DocumentMetadata(BaseModel):
    """Metadata for an uploaded MoM document."""

    id: str
    filename: str
    format: DocumentFormat
    file_size_bytes: int
    gcs_raw_uri: str
    gcs_processed_uri: str | None = None
    status: DocumentStatus
    mom_type: MomType | None = None
    meeting_date: date | None = None
    template_id: str | None = None
    ocr_confidence: float | None = None
    page_count: int | None = None
    is_confidential: bool = False
    uploaded_by: str
    batch_job_id: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    created_at: datetime
    updated_at: datetime
