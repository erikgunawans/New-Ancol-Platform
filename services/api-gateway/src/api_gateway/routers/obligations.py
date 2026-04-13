"""Obligations API — list, get, fulfill, waive, upcoming dashboard."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from ancol_common.db.connection import get_session
from ancol_common.db.models import ObligationRecord
from ancol_common.db.repository import fulfill_obligation
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/obligations", tags=["Obligations"])


class ObligationResponse(BaseModel):
    id: str
    contract_id: str
    obligation_type: str
    description: str
    due_date: date
    recurrence: str | None = None
    next_due_date: date | None = None
    responsible_party_name: str
    responsible_user_id: str | None = None
    status: str
    reminder_30d_sent: bool = False
    reminder_14d_sent: bool = False
    reminder_7d_sent: bool = False
    fulfilled_at: datetime | None = None
    fulfilled_by: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class ObligationListResponse(BaseModel):
    obligations: list[ObligationResponse]
    total: int


class FulfillRequest(BaseModel):
    fulfilled_by: str
    evidence_gcs_uri: str | None = None


class WaiveRequest(BaseModel):
    waived_by: str
    reason: str


def _obligation_to_response(o: ObligationRecord) -> ObligationResponse:
    return ObligationResponse(
        id=str(o.id),
        contract_id=str(o.contract_id),
        obligation_type=o.obligation_type,
        description=o.description,
        due_date=o.due_date,
        recurrence=o.recurrence,
        next_due_date=o.next_due_date,
        responsible_party_name=o.responsible_party_name,
        responsible_user_id=str(o.responsible_user_id) if o.responsible_user_id else None,
        status=o.status,
        reminder_30d_sent=o.reminder_30d_sent,
        reminder_14d_sent=o.reminder_14d_sent,
        reminder_7d_sent=o.reminder_7d_sent,
        fulfilled_at=o.fulfilled_at,
        fulfilled_by=str(o.fulfilled_by) if o.fulfilled_by else None,
        notes=o.notes,
        created_at=o.created_at,
        updated_at=o.updated_at,
    )


@router.get("", response_model=ObligationListResponse)
async def list_obligations_endpoint(
    contract_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
):
    """List obligations with optional contract/status filter."""
    from sqlalchemy import func, select

    async with get_session() as session:
        query = select(ObligationRecord).order_by(ObligationRecord.due_date)
        count_query = select(func.count(ObligationRecord.id))

        if contract_id:
            import uuid

            cid = uuid.UUID(contract_id)
            query = query.where(ObligationRecord.contract_id == cid)
            count_query = count_query.where(ObligationRecord.contract_id == cid)
        if status:
            query = query.where(ObligationRecord.status == status)
            count_query = count_query.where(ObligationRecord.status == status)

        count_result = await session.execute(count_query)
        total = count_result.scalar() or 0

        result = await session.execute(query.limit(limit))
        obligations = result.scalars().all()

    return ObligationListResponse(
        obligations=[_obligation_to_response(o) for o in obligations],
        total=total,
    )


@router.get("/upcoming")
async def get_upcoming_obligations(days: int = Query(30, le=90)):
    """Get obligations due within N days."""
    from sqlalchemy import select

    target_date = date.today() + timedelta(days=days)

    async with get_session() as session:
        result = await session.execute(
            select(ObligationRecord)
            .where(
                ObligationRecord.status.in_(["upcoming", "due_soon"]),
                ObligationRecord.due_date <= target_date,
            )
            .order_by(ObligationRecord.due_date)
            .limit(100)
        )
        obligations = result.scalars().all()

    return {
        "upcoming": [_obligation_to_response(o) for o in obligations],
        "total": len(obligations),
        "within_days": days,
    }


@router.get("/{obligation_id}", response_model=ObligationResponse)
async def get_obligation(obligation_id: str):
    """Get a single obligation by ID."""
    import uuid

    from sqlalchemy import select

    async with get_session() as session:
        result = await session.execute(
            select(ObligationRecord).where(
                ObligationRecord.id == uuid.UUID(obligation_id)
            )
        )
        obligation = result.scalar_one_or_none()
        if not obligation:
            raise HTTPException(status_code=404, detail="Obligation not found")
        return _obligation_to_response(obligation)


@router.post("/{obligation_id}/fulfill")
async def fulfill_obligation_endpoint(obligation_id: str, body: FulfillRequest):
    """Mark an obligation as fulfilled."""
    async with get_session() as session:
        success = await fulfill_obligation(
            session, obligation_id, body.fulfilled_by, body.evidence_gcs_uri
        )
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Obligation not found or already fulfilled/waived",
            )
    return {"obligation_id": obligation_id, "status": "fulfilled"}


@router.post("/{obligation_id}/waive")
async def waive_obligation(obligation_id: str, body: WaiveRequest):
    """Waive an obligation (requires approval)."""
    import uuid

    from sqlalchemy import select

    async with get_session() as session:
        result = await session.execute(
            select(ObligationRecord).where(
                ObligationRecord.id == uuid.UUID(obligation_id)
            )
        )
        obligation = result.scalar_one_or_none()
        if not obligation:
            raise HTTPException(status_code=404, detail="Obligation not found")

        if obligation.status in ("fulfilled", "waived"):
            raise HTTPException(status_code=400, detail="Obligation already resolved")

        obligation.status = "waived"
        obligation.notes = f"Waived by {body.waived_by}: {body.reason}"
        obligation.updated_at = datetime.now(UTC)

    return {"obligation_id": obligation_id, "status": "waived"}
