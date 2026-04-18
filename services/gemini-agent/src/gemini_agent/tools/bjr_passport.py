"""BJR Decision Passport URL tool handler.

Returns a signed GCS URL to a locked decision's Passport PDF. The URL
is short-lived (typically 1h TTL). Direksi/Legal/Komisaris use this
for legal-defensibility downloads.

409 from the API means the decision isn't locked yet — surface that
distinctly from a generic fetch failure so users can act on it (finish
Gate 5 dual-approval) rather than guess.
"""

from __future__ import annotations

import logging

from httpx import HTTPStatusError

from gemini_agent.api_client import ApiClient

logger = logging.getLogger(__name__)


async def handle_get_passport_url(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Fetch a signed Passport PDF URL for a locked decision."""
    decision_id: str = (params.get("decision_id") or "").strip()
    if not decision_id:
        return "Error: Harap berikan `decision_id` untuk mengambil Passport PDF."

    try:
        result = await api.get_passport_url(decision_id)
    except HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        if status == 409:
            return (
                f"Decision `{decision_id}` belum terkunci (Gate 5 belum selesai). "
                "Passport PDF akan tersedia setelah decision di-lock."
            )
        if status == 404:
            return f"Decision `{decision_id}` tidak ditemukan."
        logger.exception("get_passport_url HTTP error for %s", decision_id)
        return f"Gagal mengambil Passport untuk `{decision_id}`."
    except Exception:
        logger.exception("get_passport_url failed for %s", decision_id)
        return f"Gagal mengambil Passport untuk `{decision_id}`."

    url = result.get("signed_url", "")
    expires = result.get("expires_at", "")
    return f"📄 **Decision Passport PDF siap:**\n{url}\nLink berlaku sampai: {expires}"
