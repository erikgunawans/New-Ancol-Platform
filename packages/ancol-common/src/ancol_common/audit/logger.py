"""Immutable audit trail logger — writes to both PostgreSQL and BigQuery."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from ancol_common.schemas.audit import AuditEntry

logger = logging.getLogger(__name__)


async def log_audit_event(
    *,
    actor_type: str,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    actor_role: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    model_used: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    processing_time_ms: int | None = None,
    session: object | None = None,
) -> AuditEntry:
    """Log an audit event to the immutable audit trail.

    Writes to PostgreSQL (via session) for immediate queries,
    and to BigQuery (via structured logging) for long-term immutable storage.

    Args:
        actor_type: "user", "agent", or "system"
        actor_id: User UUID or agent service name
        action: Action performed (e.g., "document.upload", "hitl.approve")
        resource_type: Type of resource affected
        resource_id: UUID of the affected resource
        session: Optional SQLAlchemy async session for DB write
    """
    entry = AuditEntry(
        actor_type=actor_type,
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
        model_used=model_used,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        processing_time_ms=processing_time_ms,
        timestamp=datetime.now(UTC),
    )

    # Write to structured logging (picked up by Cloud Logging -> BigQuery sink)
    logger.info(
        "AUDIT_EVENT",
        extra={
            "json_fields": entry.model_dump(mode="json"),
        },
    )

    # Write to PostgreSQL if session provided
    if session is not None:
        from ancol_common.db.models import AuditTrailRecord

        record = AuditTrailRecord(
            id=uuid.uuid4(),
            timestamp=entry.timestamp,
            actor_type=entry.actor_type,
            actor_id=entry.actor_id,
            actor_role=entry.actor_role,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=uuid.UUID(entry.resource_id),
            details=entry.details,
            ip_address=entry.ip_address,
            user_agent=entry.user_agent,
            model_used=entry.model_used,
            prompt_tokens=entry.prompt_tokens,
            completion_tokens=entry.completion_tokens,
            processing_time_ms=entry.processing_time_ms,
        )
        session.add(record)

    return entry
