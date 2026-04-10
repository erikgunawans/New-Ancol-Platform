"""Batch Jobs API — create, list, monitor, pause, resume batch processing."""

from __future__ import annotations

import uuid

from ancol_common.db.connection import get_session
from ancol_common.utils import SYSTEM_USER_ID
from ancol_common.db.models import BatchJob, Document
from ancol_common.db.repository import (
    create_batch_job,
    get_batch_items,
    get_batch_job,
    transition_batch_status,
)
from ancol_common.schemas.batch import (
    BatchItemResponse,
    BatchJobCreate,
    BatchJobDetail,
    BatchJobResponse,
)
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select

router = APIRouter(prefix="/batch", tags=["Batch Processing"])


class BatchJobListResponse(BaseModel):
    jobs: list[BatchJobResponse]
    total: int


def _job_to_response(job: BatchJob) -> BatchJobResponse:
    total = max(job.total_documents, 1)
    progress = (job.processed_count + job.failed_count) / total * 100
    return BatchJobResponse(
        id=str(job.id),
        name=job.name,
        status=job.status,
        concurrency=job.concurrency,
        max_retries=job.max_retries,
        priority_order=job.priority_order,
        total_documents=job.total_documents,
        processed_count=job.processed_count,
        failed_count=job.failed_count,
        progress_pct=round(progress, 1),
        started_at=job.started_at,
        completed_at=job.completed_at,
        estimated_completion=job.estimated_completion,
        created_by=str(job.created_by),
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post("", response_model=BatchJobResponse, status_code=201)
async def create_batch(body: BatchJobCreate):
    """Create a new batch job with a list of document IDs."""
    # Validate all document IDs exist
    async with get_session() as session:
        existing = await session.execute(
            select(Document.id).where(Document.id.in_([uuid.UUID(d) for d in body.document_ids]))
        )
        found_ids = {str(row[0]) for row in existing.all()}
        missing = set(body.document_ids) - found_ids
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Documents not found: {', '.join(list(missing)[:5])}",
            )

        job = await create_batch_job(
            session,
            name=body.name,
            document_ids=body.document_ids,
            created_by=SYSTEM_USER_ID,  # TODO: from auth
            concurrency=body.concurrency,
            max_retries=body.max_retries,
            priority_order=body.priority_order.value,
        )
        return _job_to_response(job)


@router.get("", response_model=BatchJobListResponse)
async def list_batch_jobs(
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """List batch jobs with optional status filter."""
    async with get_session() as session:
        query = select(BatchJob).order_by(BatchJob.created_at.desc())
        count_query = select(func.count(BatchJob.id))

        if status:
            query = query.where(BatchJob.status == status)
            count_query = count_query.where(BatchJob.status == status)

        count_result = await session.execute(count_query)
        total = count_result.scalar() or 0

        result = await session.execute(query.offset(offset).limit(limit))
        jobs = result.scalars().all()

    return BatchJobListResponse(
        jobs=[_job_to_response(j) for j in jobs],
        total=total,
    )


@router.get("/{job_id}", response_model=BatchJobDetail)
async def get_batch_detail(job_id: str):
    """Get batch job detail with item breakdown."""
    async with get_session() as session:
        job = await get_batch_job(session, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Batch job not found")

        items = await get_batch_items(session, job_id)

        # Get filenames for items
        doc_ids = [item.document_id for item in items]
        docs_result = await session.execute(
            select(Document.id, Document.filename).where(Document.id.in_(doc_ids))
        )
        filename_map = {row[0]: row[1] for row in docs_result.all()}

        # Count items by status
        status_counts: dict[str, int] = {}
        item_responses = []
        for item in items:
            status_counts[item.status] = status_counts.get(item.status, 0) + 1
            item_responses.append(
                BatchItemResponse(
                    id=str(item.id),
                    batch_job_id=str(item.batch_job_id),
                    document_id=str(item.document_id),
                    filename=filename_map.get(item.document_id, "unknown"),
                    status=item.status,
                    retry_count=item.retry_count,
                    last_error=item.last_error,
                    started_at=item.started_at,
                    completed_at=item.completed_at,
                )
            )

    return BatchJobDetail(
        job=_job_to_response(job),
        items=item_responses,
        status_counts=status_counts,
    )


@router.post("/{job_id}/pause")
async def pause_batch(job_id: str):
    """Pause a running batch job."""
    async with get_session() as session:
        success = await transition_batch_status(session, job_id, "paused")
        if not success:
            raise HTTPException(status_code=400, detail="Cannot pause this job")
    return {"status": "paused", "job_id": job_id}


@router.post("/{job_id}/resume")
async def resume_batch(job_id: str):
    """Resume a paused batch job."""
    async with get_session() as session:
        job = await get_batch_job(session, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Batch job not found")
        if job.status != "paused":
            raise HTTPException(status_code=400, detail="Job is not paused")
        await transition_batch_status(session, job_id, "running")
    return {"status": "resumed", "job_id": job_id}
