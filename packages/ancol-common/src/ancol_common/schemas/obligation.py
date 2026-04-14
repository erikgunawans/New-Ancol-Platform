"""Obligation tracking schemas for contract lifecycle management."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel


class ObligationType(StrEnum):
    RENEWAL = "renewal"
    REPORTING = "reporting"
    PAYMENT = "payment"
    TERMINATION_NOTICE = "termination_notice"
    DELIVERABLE = "deliverable"
    COMPLIANCE_FILING = "compliance_filing"


class ObligationStatus(StrEnum):
    UPCOMING = "upcoming"
    DUE_SOON = "due_soon"  # within 30 days
    OVERDUE = "overdue"
    FULFILLED = "fulfilled"
    WAIVED = "waived"


class Obligation(BaseModel):
    """A tracked obligation extracted from or linked to a contract."""

    id: str
    contract_id: str
    obligation_type: ObligationType
    description: str
    due_date: date
    recurrence: str | None = None  # "monthly", "quarterly", "annual"
    next_due_date: date | None = None
    responsible_party: str
    responsible_user_id: str | None = None
    status: ObligationStatus = ObligationStatus.UPCOMING
    reminder_sent_30d: bool = False
    reminder_sent_14d: bool = False
    reminder_sent_7d: bool = False
    evidence_gcs_uri: str | None = None
    fulfilled_at: datetime | None = None
    fulfilled_by: str | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
