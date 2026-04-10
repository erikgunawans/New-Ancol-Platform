"""Batch processing schemas for bulk MoM processing."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class BatchStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class BatchItemStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class BatchPriorityOrder(StrEnum):
    NEWEST_FIRST = "newest_first"
    OLDEST_FIRST = "oldest_first"
    BY_TYPE = "by_type"


class BatchJobCreate(BaseModel):
    """Request to create a new batch job."""

    name: str = Field(..., min_length=1, max_length=255)
    document_ids: list[str] = Field(..., min_length=1)
    concurrency: int = Field(default=10, ge=1, le=50)
    max_retries: int = Field(default=3, ge=0, le=10)
    priority_order: BatchPriorityOrder = BatchPriorityOrder.NEWEST_FIRST


class BatchJobResponse(BaseModel):
    """Batch job summary returned by API."""

    id: str
    name: str
    status: BatchStatus
    concurrency: int
    max_retries: int
    priority_order: str
    total_documents: int
    processed_count: int
    failed_count: int
    progress_pct: float
    started_at: datetime | None = None
    completed_at: datetime | None = None
    estimated_completion: datetime | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime


class BatchItemResponse(BaseModel):
    """Single item within a batch job."""

    id: str
    batch_job_id: str
    document_id: str
    filename: str
    status: BatchItemStatus
    retry_count: int
    last_error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class BatchJobDetail(BaseModel):
    """Full batch job with item breakdown."""

    job: BatchJobResponse
    items: list[BatchItemResponse]
    status_counts: dict[str, int]


class BatchProgressEvent(BaseModel):
    """Real-time progress event published to Pub/Sub."""

    batch_job_id: str
    document_id: str
    status: BatchItemStatus
    processed_count: int
    total_documents: int
    error: str | None = None
