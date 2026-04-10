"""HITL (Human-in-the-Loop) review schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from .mom import HitlDecisionType, HitlGate, UserRole


class HitlReviewItem(BaseModel):
    """An item in the HITL review queue."""

    id: str
    document_id: str
    gate: HitlGate
    reviewed_entity_type: str  # "extraction", "regulatory_context", "findings", "report"
    reviewed_entity_id: str
    ai_output: dict
    auto_flagged: bool = False
    auto_flag_reasons: list[str] = []
    assigned_at: datetime
    sla_deadline: datetime
    is_sla_breached: bool = False


class HitlDecision(BaseModel):
    """A human decision on a HITL review item."""

    review_item_id: str
    document_id: str
    gate: HitlGate
    decision: HitlDecisionType
    reviewer_id: str
    reviewer_role: UserRole
    modified_data: dict | None = None
    modification_summary: str | None = None
    notes: str | None = None
    decided_at: datetime
