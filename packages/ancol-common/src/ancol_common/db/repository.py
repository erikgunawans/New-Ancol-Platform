"""Data access layer — document/contract state machines and common queries."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ancol_common.db.models import (
    BatchItem,
    BatchJob,
    Contract,
    Document,
    ObligationRecord,
    User,
)

# Valid state transitions for the document state machine
VALID_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["processing_ocr"],
    "processing_ocr": ["ocr_complete", "failed"],
    "ocr_complete": ["extracting"],
    "extracting": ["hitl_gate_1", "failed"],
    "hitl_gate_1": ["researching", "rejected"],
    "researching": ["hitl_gate_2", "failed"],
    "hitl_gate_2": ["comparing", "rejected"],
    "comparing": ["hitl_gate_3", "failed"],
    "hitl_gate_3": ["reporting", "rejected"],
    "reporting": ["hitl_gate_4", "failed"],
    "hitl_gate_4": ["complete", "rejected"],
    "complete": [],
    "failed": ["pending"],  # Allow retry
    "rejected": [],
}


async def transition_document_status(
    session: AsyncSession,
    document_id: str,
    new_status: str,
    error_message: str | None = None,
) -> bool:
    """Transition a document to a new status if the transition is valid.

    Returns True if transition succeeded, False if invalid.
    """
    doc_uuid = uuid.UUID(document_id)
    result = await session.execute(select(Document).where(Document.id == doc_uuid))
    document = result.scalar_one_or_none()

    if document is None:
        return False

    current_status = document.status
    if new_status not in VALID_TRANSITIONS.get(current_status, []):
        return False

    document.status = new_status
    document.updated_at = datetime.now(UTC)
    if error_message:
        document.error_message = error_message
    return True


async def get_document_by_id(session: AsyncSession, document_id: str) -> Document | None:
    """Fetch a document by ID."""
    result = await session.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
    return result.scalar_one_or_none()


async def get_documents_by_status(
    session: AsyncSession, status: str, limit: int = 50
) -> list[Document]:
    """Fetch documents by status."""
    result = await session.execute(select(Document).where(Document.status == status).limit(limit))
    return list(result.scalars().all())


async def get_users_by_role(session: AsyncSession, role: str) -> list[User]:
    """Fetch active users by role."""
    result = await session.execute(select(User).where(User.role == role, User.is_active.is_(True)))
    return list(result.scalars().all())


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Fetch a user by email."""
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


# ── Batch Job Operations ──


VALID_BATCH_TRANSITIONS: dict[str, list[str]] = {
    "queued": ["running", "failed"],
    "running": ["paused", "completed", "failed"],
    "paused": ["running", "failed"],
    "completed": [],
    "failed": ["queued"],  # Allow retry
}


async def create_batch_job(
    session: AsyncSession,
    name: str,
    document_ids: list[str],
    created_by: str,
    concurrency: int = 10,
    max_retries: int = 3,
    priority_order: str = "newest_first",
) -> BatchJob:
    """Create a batch job and its items."""
    job = BatchJob(
        name=name,
        status="queued",
        concurrency=concurrency,
        max_retries=max_retries,
        priority_order=priority_order,
        total_documents=len(document_ids),
        created_by=uuid.UUID(created_by),
    )
    session.add(job)
    await session.flush()

    doc_uuids = [uuid.UUID(d) for d in document_ids]

    for doc_uuid in doc_uuids:
        item = BatchItem(
            batch_job_id=job.id,
            document_id=doc_uuid,
            status="pending",
        )
        session.add(item)

    await session.execute(
        update(Document).where(Document.id.in_(doc_uuids)).values(batch_job_id=job.id)
    )

    return job


async def get_batch_job(session: AsyncSession, job_id: str) -> BatchJob | None:
    """Fetch a batch job by ID."""
    result = await session.execute(select(BatchJob).where(BatchJob.id == uuid.UUID(job_id)))
    return result.scalar_one_or_none()


async def get_batch_items(
    session: AsyncSession, job_id: str, status: str | None = None
) -> list[BatchItem]:
    """Fetch batch items for a job, optionally filtered by status."""
    query = select(BatchItem).where(BatchItem.batch_job_id == uuid.UUID(job_id))
    if status:
        query = query.where(BatchItem.status == status)
    result = await session.execute(query.order_by(BatchItem.created_at))
    return list(result.scalars().all())


async def transition_batch_status(
    session: AsyncSession,
    job_id: str,
    new_status: str,
) -> bool:
    """Transition a batch job status if valid. Returns True on success."""
    job = await get_batch_job(session, job_id)
    if job is None:
        return False

    if new_status not in VALID_BATCH_TRANSITIONS.get(job.status, []):
        return False

    job.status = new_status
    if new_status == "running" and job.started_at is None:
        job.started_at = datetime.now(UTC)
    elif new_status in ("completed", "failed"):
        job.completed_at = datetime.now(UTC)
    return True


async def update_batch_item_status(
    session: AsyncSession,
    item_id: str,
    new_status: str,
    error: str | None = None,
) -> bool:
    """Update a batch item status and sync parent job counters."""
    result = await session.execute(select(BatchItem).where(BatchItem.id == uuid.UUID(item_id)))
    item = result.scalar_one_or_none()
    if item is None:
        return False

    old_status = item.status
    item.status = new_status
    if error:
        item.last_error = error

    if new_status == "processing" and item.started_at is None:
        item.started_at = datetime.now(UTC)
    elif new_status in ("completed", "failed"):
        item.completed_at = datetime.now(UTC)

    # Update parent job counters
    job = await get_batch_job(session, str(item.batch_job_id))
    if job:
        if new_status == "completed" and old_status != "completed":
            job.processed_count += 1
        elif new_status == "failed" and old_status != "failed":
            job.failed_count += 1

        # Auto-complete job if all items are done
        pending_result = await session.execute(
            select(BatchItem).where(
                BatchItem.batch_job_id == item.batch_job_id,
                BatchItem.status.in_(["pending", "processing", "retrying"]),
            )
        )
        if not pending_result.scalars().first():
            job.status = "completed"
            job.completed_at = datetime.now(UTC)

    return True


async def get_next_batch_items(
    session: AsyncSession, job_id: str, limit: int = 10
) -> list[BatchItem]:
    """Get the next pending items from a batch job for processing."""
    result = await session.execute(
        select(BatchItem)
        .where(
            BatchItem.batch_job_id == uuid.UUID(job_id),
            BatchItem.status == "pending",
        )
        .order_by(BatchItem.created_at)
        .limit(limit)
    )
    return list(result.scalars().all())


# ── Contract Lifecycle Operations ──


CONTRACT_VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["pending_review", "failed"],
    "pending_review": ["in_review", "draft"],
    "in_review": ["approved", "draft"],  # reject → draft
    "approved": ["executed"],
    "executed": ["active"],
    "active": ["expiring", "terminated", "amended"],
    "expiring": ["active", "expired", "terminated"],  # renew → active
    "expired": [],  # terminal
    "terminated": [],  # terminal
    "amended": ["active"],  # new version activates
    "failed": ["draft"],  # retry
}


async def transition_contract_status(
    session: AsyncSession,
    contract_id: str,
    new_status: str,
    error_message: str | None = None,
) -> bool:
    """Transition a contract to a new status if the transition is valid."""
    contract = await get_contract_by_id(session, contract_id)
    if contract is None:
        return False

    current_status = contract.status
    if new_status not in CONTRACT_VALID_TRANSITIONS.get(current_status, []):
        return False

    contract.status = new_status
    contract.updated_at = datetime.now(UTC)
    if error_message:
        contract.error_message = error_message
    return True


async def create_contract(
    session: AsyncSession,
    title: str,
    contract_type: str,
    uploaded_by: str,
    gcs_raw_uri: str | None = None,
    contract_number: str | None = None,
    template_id: str | None = None,
) -> Contract:
    """Create a new contract in draft status."""
    contract = Contract(
        title=title,
        contract_type=contract_type,
        status="draft",
        uploaded_by=uuid.UUID(uploaded_by),
        gcs_raw_uri=gcs_raw_uri,
        contract_number=contract_number,
        template_id=uuid.UUID(template_id) if template_id else None,
    )
    session.add(contract)
    await session.flush()
    return contract


async def get_contract_by_id(session: AsyncSession, contract_id: str) -> Contract | None:
    """Fetch a contract by ID."""
    result = await session.execute(
        select(Contract).where(Contract.id == uuid.UUID(contract_id))
    )
    return result.scalar_one_or_none()


async def list_contracts(
    session: AsyncSession,
    status: str | None = None,
    contract_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Contract]:
    """List contracts with optional filtering."""
    query = select(Contract)
    if status:
        query = query.where(Contract.status == status)
    if contract_type:
        query = query.where(Contract.contract_type == contract_type)
    query = query.order_by(Contract.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    return list(result.scalars().all())


async def create_obligation(
    session: AsyncSession,
    contract_id: str,
    obligation_type: str,
    description: str,
    due_date: date,
    responsible_party_name: str,
    recurrence: str | None = None,
    responsible_user_id: str | None = None,
) -> ObligationRecord:
    """Create a new obligation linked to a contract."""
    obligation = ObligationRecord(
        contract_id=uuid.UUID(contract_id),
        obligation_type=obligation_type,
        description=description,
        due_date=due_date,
        responsible_party_name=responsible_party_name,
        recurrence=recurrence,
        responsible_user_id=uuid.UUID(responsible_user_id) if responsible_user_id else None,
        status="upcoming",
    )
    session.add(obligation)
    await session.flush()
    return obligation


async def list_obligations(
    session: AsyncSession,
    contract_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[ObligationRecord]:
    """List obligations with optional filtering."""
    query = select(ObligationRecord)
    if contract_id:
        query = query.where(ObligationRecord.contract_id == uuid.UUID(contract_id))
    if status:
        query = query.where(ObligationRecord.status == status)
    query = query.order_by(ObligationRecord.due_date).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def fulfill_obligation(
    session: AsyncSession,
    obligation_id: str,
    fulfilled_by: str,
    evidence_gcs_uri: str | None = None,
) -> bool:
    """Mark an obligation as fulfilled."""
    result = await session.execute(
        select(ObligationRecord).where(ObligationRecord.id == uuid.UUID(obligation_id))
    )
    obligation = result.scalar_one_or_none()
    if obligation is None:
        return False

    if obligation.status in ("fulfilled", "waived"):
        return False  # already terminal

    obligation.status = "fulfilled"
    obligation.fulfilled_at = datetime.now(UTC)
    obligation.fulfilled_by = uuid.UUID(fulfilled_by)
    if evidence_gcs_uri:
        obligation.evidence_gcs_uri = evidence_gcs_uri
    obligation.updated_at = datetime.now(UTC)
    return True
