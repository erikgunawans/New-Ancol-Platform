"""Audit trail API — read-only access to immutable audit log."""

from __future__ import annotations

from datetime import datetime

from ancol_common.auth.mfa import require_mfa_verified
from ancol_common.auth.rbac import require_permission
from ancol_common.db.connection import get_session
from ancol_common.db.models import AuditTrailRecord
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

router = APIRouter(prefix="/audit", tags=["Audit Trail"], dependencies=[require_mfa_verified()])


class AuditEntryResponse(BaseModel):
    id: str
    timestamp: datetime
    actor_type: str
    actor_id: str
    actor_role: str | None = None
    action: str
    resource_type: str
    resource_id: str
    details: dict | None = None


class AuditListResponse(BaseModel):
    entries: list[AuditEntryResponse]
    total: int


@router.get("", response_model=AuditListResponse)
async def list_audit_entries(
    _auth=require_permission("audit_trail:view"),
    resource_type: str | None = Query(None),
    resource_id: str | None = Query(None),
    actor_id: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """List audit trail entries with optional filters."""
    async with get_session() as session:
        query = select(AuditTrailRecord).order_by(AuditTrailRecord.timestamp.desc())

        if resource_type:
            query = query.where(AuditTrailRecord.resource_type == resource_type)
        if resource_id:
            query = query.where(AuditTrailRecord.resource_id == resource_id)
        if actor_id:
            query = query.where(AuditTrailRecord.actor_id == actor_id)

        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        entries = result.scalars().all()

    return AuditListResponse(
        entries=[
            AuditEntryResponse(
                id=str(e.id),
                timestamp=e.timestamp,
                actor_type=e.actor_type,
                actor_id=e.actor_id,
                actor_role=e.actor_role,
                action=e.action,
                resource_type=e.resource_type,
                resource_id=str(e.resource_id),
                details=e.details,
            )
            for e in entries
        ],
        total=len(entries),
    )
