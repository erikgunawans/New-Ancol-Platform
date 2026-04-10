"""Email notification service via SendGrid."""

from __future__ import annotations

import logging

import httpx

from ancol_common.config import get_settings

logger = logging.getLogger(__name__)

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


async def send_email_notification(
    *,
    to_email: str,
    to_name: str,
    subject: str,
    html_body: str,
) -> bool:
    """Send an email notification via SendGrid.

    Returns True if sent successfully, False otherwise.
    """
    settings = get_settings()

    if not settings.sendgrid_api_key:
        logger.warning("SendGrid API key not configured — skipping email to %s", to_email)
        return False

    payload = {
        "personalizations": [
            {
                "to": [{"email": to_email, "name": to_name}],
                "subject": subject,
            }
        ],
        "from": {
            "email": settings.notification_from_email,
            "name": "Ancol MoM Compliance System",
        },
        "content": [{"type": "text/html", "value": html_body}],
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SENDGRID_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.sendgrid_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            if response.status_code in (200, 201, 202):
                logger.info("Email sent to %s: %s", to_email, subject)
                return True
            else:
                logger.error("SendGrid error %d: %s", response.status_code, response.text)
                return False
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return False


def build_hitl_notification_html(
    *,
    reviewer_name: str,
    document_name: str,
    gate: str,
    action_url: str,
    sla_hours: int = 48,
) -> str:
    """Build HTML email body for HITL review notification."""
    gate_labels = {
        "gate_1": "Extraction Review (Gate 1)",
        "gate_2": "Regulatory Mapping Review (Gate 2)",
        "gate_3": "Compliance Findings Review (Gate 3)",
        "gate_4": "Final Report Approval (Gate 4)",
    }
    gate_label = gate_labels.get(gate, gate)

    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1a1a1a;">Review Required: {gate_label}</h2>
        <p>Dear {reviewer_name},</p>
        <p>A new compliance review item requires your attention:</p>
        <div style="background: #f5f5f5; padding: 16px; border-radius: 8px; margin: 16px 0;">
            <p><strong>Document:</strong> {document_name}</p>
            <p><strong>Review Stage:</strong> {gate_label}</p>
            <p><strong>SLA:</strong> Please review within {sla_hours} hours</p>
        </div>
        <a href="{action_url}"
           style="display: inline-block; background: #2563eb; color: white;
                  padding: 12px 24px; border-radius: 6px; text-decoration: none;
                  font-weight: bold;">
            Review Now
        </a>
        <p style="color: #666; font-size: 12px; margin-top: 24px;">
            This is an automated message from the Ancol MoM Compliance System.
        </p>
    </div>
    """
