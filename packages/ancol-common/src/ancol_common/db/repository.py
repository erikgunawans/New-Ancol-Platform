"""Data access layer — document/contract state machines and common queries."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from dateutil.relativedelta import relativedelta
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ancol_common.db.models import (
    BatchItem,
    BatchJob,
    ClauseLibrary,
    Contract,
    ContractClauseRecord,
    ContractPartyRecord,
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
    result = await session.execute(select(Contract).where(Contract.id == uuid.UUID(contract_id)))
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


async def check_obligation_deadlines(session: AsyncSession) -> dict:
    """Run obligation status transitions, set reminder flags, handle recurrences.

    Called daily by Cloud Scheduler at 07:00 WIB.
    """
    import logging

    logger = logging.getLogger(__name__)
    today = date.today()

    # Phase 1: Overdue transition (must run before due_soon)
    overdue_result = await session.execute(
        update(ObligationRecord)
        .where(
            ObligationRecord.status.in_(["upcoming", "due_soon"]),
            ObligationRecord.due_date <= today,
        )
        .values(status="overdue")
    )
    transitioned_overdue = overdue_result.rowcount

    # Phase 2: Due-soon transition
    due_soon_cutoff = today + timedelta(days=30)
    due_soon_result = await session.execute(
        update(ObligationRecord)
        .where(
            ObligationRecord.status == "upcoming",
            ObligationRecord.due_date <= due_soon_cutoff,
            ObligationRecord.due_date > today,
        )
        .values(status="due_soon")
    )
    transitioned_due_soon = due_soon_result.rowcount

    # Phase 3: Reminder flags (log only — WhatsApp deferred until User model has phone field)
    reminders_flagged = 0

    for days_ahead, flag_col in [
        (30, ObligationRecord.reminder_30d_sent),
        (14, ObligationRecord.reminder_14d_sent),
        (7, ObligationRecord.reminder_7d_sent),
    ]:
        cutoff = today + timedelta(days=days_ahead)
        result = await session.execute(
            update(ObligationRecord)
            .where(
                ObligationRecord.status.in_(["upcoming", "due_soon", "overdue"]),
                ObligationRecord.due_date <= cutoff,
                flag_col.is_(False),
            )
            .values({flag_col.key: True})
        )
        count = result.rowcount
        if count:
            logger.info("Obligation reminders: %d flagged at %d-day window", count, days_ahead)
        reminders_flagged += count

    # Phase 4: Recurrence handling
    recurrences_created = 0
    recurrence_result = await session.execute(
        select(ObligationRecord).where(
            ObligationRecord.status == "fulfilled",
            ObligationRecord.recurrence.isnot(None),
            ObligationRecord.next_due_date.is_(None),
        )
    )
    fulfilled_recurring = recurrence_result.scalars().all()

    for ob in fulfilled_recurring:
        if ob.recurrence == "monthly":
            next_date = ob.due_date + relativedelta(months=1)
        elif ob.recurrence == "quarterly":
            next_date = ob.due_date + relativedelta(months=3)
        elif ob.recurrence == "annual":
            next_date = ob.due_date + relativedelta(years=1)
        else:
            logger.warning("Unknown recurrence %r for obligation %s", ob.recurrence, ob.id)
            continue

        new_ob = ObligationRecord(
            contract_id=ob.contract_id,
            obligation_type=ob.obligation_type,
            description=ob.description,
            due_date=next_date,
            recurrence=ob.recurrence,
            responsible_user_id=ob.responsible_user_id,
            responsible_party_name=ob.responsible_party_name,
            status="upcoming",
            reminder_30d_sent=False,
            reminder_14d_sent=False,
            reminder_7d_sent=False,
        )
        session.add(new_ob)
        ob.next_due_date = next_date
        recurrences_created += 1

    logger.info(
        "Obligation check: %d overdue, %d due_soon, %d reminders, %d recurrences",
        transitioned_overdue,
        transitioned_due_soon,
        reminders_flagged,
        recurrences_created,
    )

    return {
        "transitioned_overdue": transitioned_overdue,
        "transitioned_due_soon": transitioned_due_soon,
        "reminders_flagged": reminders_flagged,
        "recurrences_created": recurrences_created,
    }


# ── Contract Extraction ──


async def store_contract_extraction(
    session: AsyncSession,
    contract_id: str,
    extraction_data: dict,
    clauses: list[dict],
    parties: list[dict],
    key_dates: dict,
    financial_terms: dict,
    risk_summary: dict,
    obligations: list[dict] | None = None,
) -> None:
    """Store contract extraction results: clauses, parties, obligations, and metadata."""
    cid = uuid.UUID(contract_id)

    # Insert clause records
    for clause in clauses:
        record = ContractClauseRecord(
            contract_id=cid,
            clause_number=clause.get("clause_number", ""),
            title=clause.get("title", ""),
            text=clause.get("text", ""),
            category=clause.get("category"),
            risk_level=clause.get("risk_level"),
            risk_reason=clause.get("risk_reason"),
            confidence=clause.get("confidence", 0.8),
        )
        session.add(record)

    # Insert party records
    for party in parties:
        record = ContractPartyRecord(
            contract_id=cid,
            party_name=party.get("name", ""),
            party_role=party.get("role", "counterparty"),
            entity_type=party.get("entity_type", "external"),
        )
        session.add(record)

    # Update contract metadata
    contract = await session.get(Contract, cid)
    if contract:
        contract.extraction_data = extraction_data

        # Key dates
        eff = key_dates.get("effective_date")
        exp = key_dates.get("expiry_date")
        if eff:
            contract.effective_date = date.fromisoformat(eff)
        if exp:
            contract.expiry_date = date.fromisoformat(exp)

        # Financial terms
        val = financial_terms.get("total_value")
        cur = financial_terms.get("currency")
        if val is not None:
            contract.total_value = val
        if cur:
            contract.currency = cur

        # Risk
        risk_level = risk_summary.get("overall_risk_level")
        risk_score = risk_summary.get("overall_risk_score")
        if risk_level:
            contract.risk_level = risk_level
        if risk_score is not None:
            contract.risk_score = risk_score

        contract.updated_at = datetime.now(UTC)

    # Insert obligation records from extraction
    if obligations:
        for ob in obligations:
            import contextlib

            due = None
            if ob.get("due_date"):
                with contextlib.suppress(ValueError, TypeError):
                    due = date.fromisoformat(ob["due_date"])
            record = ObligationRecord(
                contract_id=cid,
                obligation_type=ob.get("obligation_type", "deliverable"),
                description=ob.get("description", ""),
                due_date=due or date.today(),
                recurrence=ob.get("recurrence"),
                responsible_party_name=ob.get("responsible_party", ""),
                status="upcoming",
            )
            session.add(record)


# ── Clause Library Queries ──


async def get_clauses_for_template(
    session: AsyncSession,
    contract_type: str,
    clause_categories: list[str],
) -> list[ClauseLibrary]:
    """Get active clause library entries for given categories."""
    result = await session.execute(
        select(ClauseLibrary)
        .where(
            ClauseLibrary.contract_type == contract_type,
            ClauseLibrary.clause_category.in_(clause_categories),
            ClauseLibrary.is_active.is_(True),
        )
        .order_by(ClauseLibrary.clause_category, ClauseLibrary.version.desc())
    )
    return list(result.scalars().all())


async def get_contract_template(
    session: AsyncSession,
    contract_type: str,
):
    """Get the latest active contract template for a type."""
    from ancol_common.db.models import ContractTemplate

    result = await session.execute(
        select(ContractTemplate)
        .where(
            ContractTemplate.contract_type == contract_type,
            ContractTemplate.is_active.is_(True),
        )
        .order_by(ContractTemplate.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
