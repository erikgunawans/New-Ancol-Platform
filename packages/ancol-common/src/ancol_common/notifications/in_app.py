"""In-app notification writer."""

from __future__ import annotations

import logging
import uuid

from ancol_common.config import get_settings

logger = logging.getLogger(__name__)


async def create_in_app_notification(
    *,
    recipient_id: str,
    title: str,
    body: str,
    action_url: str | None = None,
    related_document_id: str | None = None,
    related_gate: str | None = None,
    session: object,
) -> str:
    """Create an in-app notification record.

    Returns the notification ID.
    """
    from ancol_common.db.models import Notification

    notification = Notification(
        id=uuid.uuid4(),
        recipient_id=uuid.UUID(recipient_id),
        channel="in_app",
        status="pending",
        title=title,
        body=body,
        action_url=action_url,
        related_document_id=uuid.UUID(related_document_id) if related_document_id else None,
        related_gate=related_gate,
    )
    session.add(notification)
    logger.info("Created in-app notification for user %s: %s", recipient_id, title)
    return str(notification.id)


async def create_hitl_notifications(
    *,
    document_id: str,
    document_name: str,
    gate: str,
    reviewer_ids: list[str],
    action_url: str,
    session: object,
) -> list[str]:
    """Create HITL review notifications for all reviewers (email + in-app).

    Returns list of notification IDs.
    """
    settings = get_settings()
    notification_ids = []

    gate_labels = {
        "gate_1": "Extraction Review",
        "gate_2": "Regulatory Mapping Review",
        "gate_3": "Compliance Findings Review",
        "gate_4": "Final Report Approval",
    }
    gate_label = gate_labels.get(gate, gate)
    title = f"Review Required: {gate_label} — {document_name}"
    body = (
        f"A new compliance review item requires your attention. "
        f"Please review within {settings.hitl_sla_hours} hours."
    )

    for reviewer_id in reviewer_ids:
        nid = await create_in_app_notification(
            recipient_id=reviewer_id,
            title=title,
            body=body,
            action_url=action_url,
            related_document_id=document_id,
            related_gate=gate,
            session=session,
        )
        notification_ids.append(nid)

    return notification_ids
