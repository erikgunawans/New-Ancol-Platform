"""Audit trail schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AuditEntry(BaseModel):
    """A single entry in the immutable audit trail."""

    actor_type: str  # "user", "agent", "system"
    actor_id: str
    actor_role: str | None = None
    action: str  # e.g., "document.upload", "hitl.approve", "agent.extract"
    resource_type: str  # e.g., "document", "extraction", "report"
    resource_id: str
    details: dict | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    model_used: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    processing_time_ms: int | None = None
    timestamp: datetime
