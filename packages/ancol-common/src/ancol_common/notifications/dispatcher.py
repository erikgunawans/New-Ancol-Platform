"""Unified notification dispatcher — routes to email, WhatsApp, and in-app."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from ancol_common.auth.rbac import GATE_PERMISSIONS, ROLE_PERMISSIONS
from ancol_common.config import get_settings
from ancol_common.notifications.email import build_hitl_notification_html, send_email_notification
from ancol_common.notifications.in_app import create_in_app_notification
from ancol_common.notifications.whatsapp import send_approval_request

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ancol_common.db.models import User

logger = logging.getLogger(__name__)

VALID_CHANNELS = {"email", "in_app", "whatsapp", "push"}
DEFAULT_CHANNELS: list[str] = ["email", "in_app"]

DEEP_LINK_BASE = "https://compliance.ancol.co.id"


async def send_notification(
    *,
    recipient: User,
    title: str,
    body: str,
    action_url: str | None = None,
    related_document_id: str | None = None,
    related_gate: str | None = None,
    session: AsyncSession,
) -> list[str]:
    """Send notification via all enabled channels for the recipient.

    Returns list of in-app notification IDs created.
    """
    channels = recipient.notification_channels or DEFAULT_CHANNELS
    notification_ids: list[str] = []
    tasks: list[asyncio.Task] = []

    for channel in channels:
        if channel not in VALID_CHANNELS:
            continue

        if channel == "in_app":
            nid = await create_in_app_notification(
                recipient_id=str(recipient.id),
                title=title,
                body=body,
                action_url=action_url,
                related_document_id=related_document_id,
                related_gate=related_gate,
                session=session,
            )
            notification_ids.append(nid)

        elif channel == "email":
            gate_key = related_gate or ""
            html = build_hitl_notification_html(
                reviewer_name=recipient.display_name,
                document_name=title,
                gate=gate_key,
                action_url=action_url or "",
                sla_hours=get_settings().hitl_sla_hours,
            )
            tasks.append(
                asyncio.create_task(
                    send_email_notification(
                        to_email=recipient.email,
                        to_name=recipient.display_name,
                        subject=title,
                        html_body=html,
                    )
                )
            )

        elif channel == "whatsapp":
            if not recipient.phone_number:
                logger.debug(
                    "Skipping WhatsApp for %s — no phone number", recipient.email
                )
                continue
            tasks.append(
                asyncio.create_task(
                    send_approval_request(
                        to_phone=recipient.phone_number,
                        document_title=title,
                        document_type=related_gate or "review",
                        document_id=related_document_id or "",
                    )
                )
            )

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                logger.error("Notification delivery failed: %s", r)

    return notification_ids


async def notify_gate_reviewers(
    *,
    document_id: str,
    document_name: str,
    gate: str,
    session: AsyncSession,
) -> int:
    """Send notifications to all reviewers eligible for a HITL gate.

    Uses GATE_PERMISSIONS to find eligible roles, then dispatches notifications
    to all active users with those roles.
    Returns count of notifications sent.
    """
    from sqlalchemy import select

    from ancol_common.db.models import User

    perm_keys = GATE_PERMISSIONS.get(gate, [])
    if not perm_keys:
        return 0

    eligible_roles: set[str] = set()
    for pk in perm_keys:
        for role in ROLE_PERMISSIONS.get(pk, set()):
            eligible_roles.add(role.value if hasattr(role, "value") else str(role))

    if not eligible_roles:
        return 0

    # Batch query: fetch all eligible users in one DB call
    result = await session.execute(
        select(User).where(User.role.in_(eligible_roles), User.is_active.is_(True))
    )
    users = list(result.scalars().all())

    if not users:
        return 0

    action_url = f"{DEEP_LINK_BASE}/approve?id={document_id}"
    gate_labels = {
        "hitl_gate_1": "Extraction Review",
        "hitl_gate_2": "Regulatory Mapping Review",
        "hitl_gate_3": "Compliance Findings Review",
        "hitl_gate_4": "Final Report Approval",
    }
    gate_label = gate_labels.get(gate, gate)
    title = f"Review Required: {gate_label} — {document_name}"
    settings = get_settings()
    body = (
        f"A new compliance review item requires your attention. "
        f"Please review within {settings.hitl_sla_hours} hours."
    )

    for user in users:
        await send_notification(
            recipient=user,
            title=title,
            body=body,
            action_url=action_url,
            related_document_id=document_id,
            related_gate=gate.replace("hitl_", ""),
            session=session,
        )

    logger.info(
        "Notified %d reviewers for %s on document %s",
        len(users),
        gate,
        document_id,
    )
    return len(users)
