"""Retroactive Impact Scanning API.

When a regulation in the corpus is updated or added, this endpoint
identifies all MoMs within the affected date range and queues them
for re-audit via the batch engine. New findings are flagged as
"retroactive alerts" with a separate review queue.
"""

from __future__ import annotations

from datetime import date

from ancol_common.db.connection import get_session
from ancol_common.db.models import (
    Document,
    RegulationIndex,
    Report,
)
from ancol_common.db.repository import create_batch_job
from ancol_common.utils import SYSTEM_USER_ID
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select, update

router = APIRouter(prefix="/retroactive", tags=["Retroactive Scanning"])


class ImpactScanRequest(BaseModel):
    """Request to scan for retroactive impact of a regulation change."""

    regulation_id: str
    effective_date: date
    affected_domains: list[str] = []
    date_range_start: date | None = None
    date_range_end: date | None = None


class AffectedDocument(BaseModel):
    id: str
    filename: str
    meeting_date: date | None = None
    status: str
    has_existing_report: bool


class ImpactAssessment(BaseModel):
    regulation_id: str
    regulation_title: str | None = None
    affected_documents: list[AffectedDocument]
    total_affected: int
    batch_job_id: str | None = None


async def _find_affected_documents(
    body: ImpactScanRequest,
) -> tuple[str | None, list[AffectedDocument], list[str]]:
    """Shared logic: find regulation title and affected documents.

    Returns (reg_title, affected_docs, doc_id_strings).
    """
    async with get_session() as session:
        reg_result = await session.execute(
            select(RegulationIndex).where(RegulationIndex.regulation_id == body.regulation_id)
        )
        regulation = reg_result.scalar_one_or_none()
        reg_title = regulation.title if regulation else None

        start_date = body.date_range_start or body.effective_date
        end_date = body.date_range_end or date.today()

        doc_query = (
            select(Document)
            .where(
                Document.meeting_date.isnot(None),
                Document.meeting_date >= start_date,
                Document.meeting_date <= end_date,
                Document.status == "complete",
            )
            .order_by(Document.meeting_date.desc())
        )
        doc_result = await session.execute(doc_query)
        documents = doc_result.scalars().all()

        # Batch-check which have reports (avoids N+1)
        doc_ids = [doc.id for doc in documents]
        report_doc_ids: set = set()
        if doc_ids:
            report_result = await session.execute(
                select(Report.document_id).where(Report.document_id.in_(doc_ids))
            )
            report_doc_ids = {row[0] for row in report_result.all()}

    affected = [
        AffectedDocument(
            id=str(doc.id),
            filename=doc.filename,
            meeting_date=doc.meeting_date,
            status=doc.status,
            has_existing_report=doc.id in report_doc_ids,
        )
        for doc in documents
    ]
    doc_id_strings = [str(doc.id) for doc in documents]

    return reg_title, affected, doc_id_strings


@router.post("/scan", response_model=ImpactAssessment)
async def scan_impact(body: ImpactScanRequest):
    """Scan for documents affected by a regulation change."""
    reg_title, affected, _ = await _find_affected_documents(body)

    return ImpactAssessment(
        regulation_id=body.regulation_id,
        regulation_title=reg_title,
        affected_documents=affected,
        total_affected=len(affected),
    )


@router.post("/scan-and-reprocess", response_model=ImpactAssessment)
async def scan_and_reprocess(body: ImpactScanRequest):
    """Scan for affected documents and create a batch job to re-process them."""
    reg_title, affected, doc_ids = await _find_affected_documents(body)

    if not doc_ids:
        return ImpactAssessment(
            regulation_id=body.regulation_id,
            regulation_title=reg_title or body.regulation_id,
            affected_documents=[],
            total_affected=0,
        )

    async with get_session() as session:
        start_date = body.date_range_start or body.effective_date
        end_date = body.date_range_end or date.today()
        batch_name = f"Retroactive: {reg_title or body.regulation_id} ({start_date} to {end_date})"

        job = await create_batch_job(
            session,
            name=batch_name[:255],
            document_ids=doc_ids,
            created_by=SYSTEM_USER_ID,
            concurrency=5,
            max_retries=2,
        )
        batch_job_id = str(job.id)

        # Reset documents via bulk UPDATE (not detached ORM objects)
        import uuid

        await session.execute(
            update(Document)
            .where(Document.id.in_([uuid.UUID(d) for d in doc_ids]))
            .values(status="pending", retry_count=0, error_message=None)
        )

    # Update response to reflect new status
    for doc in affected:
        doc.status = "pending"

    return ImpactAssessment(
        regulation_id=body.regulation_id,
        regulation_title=reg_title or body.regulation_id,
        affected_documents=affected,
        total_affected=len(affected),
        batch_job_id=batch_job_id,
    )
