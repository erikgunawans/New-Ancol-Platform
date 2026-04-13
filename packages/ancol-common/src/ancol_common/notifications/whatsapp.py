"""WhatsApp Business API notifications via Twilio.

Sends templated messages containing only IDs, dates, and deep links.
No sensitive contract/MoM content is transmitted — data stays in asia-southeast2.
"""

from __future__ import annotations

import logging

import httpx

from ancol_common.config import get_settings

logger = logging.getLogger(__name__)


async def send_notification(
    to_phone: str,
    template_id: str,
    template_params: dict,
) -> bool:
    """Send a templated WhatsApp message via Twilio.

    Returns True on success, False on failure.
    """
    settings = get_settings()
    if not settings.whatsapp_api_token or not settings.whatsapp_api_url:
        logger.warning("WhatsApp not configured — skipping notification to %s", to_phone)
        return False

    payload = {
        "to": f"whatsapp:{to_phone}",
        "template_id": template_id,
        "parameters": template_params,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                settings.whatsapp_api_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.whatsapp_api_token}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            logger.info("WhatsApp sent to %s (template=%s)", to_phone, template_id)
            return True
    except Exception:
        logger.exception("WhatsApp delivery failed to %s", to_phone)
        return False


async def send_obligation_reminder(
    to_phone: str,
    contract_title: str,
    due_date: str,
    obligation_id: str,
    deep_link_base: str = "https://compliance.ancol.co.id",
) -> bool:
    """Send an obligation deadline reminder via WhatsApp."""
    deep_link = f"{deep_link_base}/obligations?id={obligation_id}"
    return await send_notification(
        to_phone=to_phone,
        template_id="obligation_reminder",
        template_params={
            "contract_title": contract_title,
            "due_date": due_date,
            "deep_link": deep_link,
        },
    )


async def send_approval_request(
    to_phone: str,
    document_title: str,
    document_type: str,
    document_id: str,
    deep_link_base: str = "https://compliance.ancol.co.id",
) -> bool:
    """Send an approval request notification via WhatsApp."""
    deep_link = f"{deep_link_base}/approve?id={document_id}"
    return await send_notification(
        to_phone=to_phone,
        template_id="approval_request",
        template_params={
            "title": document_title,
            "document_type": document_type,
            "deep_link": deep_link,
        },
    )
