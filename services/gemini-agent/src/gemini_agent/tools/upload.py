"""Tool handler — upload a MoM document and poll for extraction results."""

from __future__ import annotations

import asyncio
import logging

from gemini_agent.api_client import ApiClient
from gemini_agent.formatting import format_extraction

logger = logging.getLogger(__name__)

_POLL_INTERVAL_S = 10
_MAX_POLL_ITERATIONS = 30  # 5 minutes total


async def handle_upload_document(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Upload a document and wait for extraction to reach HITL Gate 1.

    Parameters
    ----------
    params:
        file_bytes (bytes): Raw file content.
        filename (str): Original filename.
        mom_type (str): "regular" | "circular" | "extraordinary".
        meeting_date (str | None): ISO date string.
        is_confidential (bool): Confidentiality flag.
    api:
        Initialised ApiClient instance.
    user:
        Authenticated user context dict with at least ``id`` and ``role``.
    """
    from ancol_common.utils import SYSTEM_USER_ID

    file_bytes: bytes = params.get("file_bytes", b"")
    filename: str = params.get("filename", "unknown.pdf")
    mom_type: str = params.get("mom_type", "regular")
    meeting_date: str | None = params.get("meeting_date")
    is_confidential: bool = params.get("is_confidential", False)
    uploaded_by: str = user.get("id", SYSTEM_USER_ID)

    if not file_bytes:
        return "Error: Tidak ada file yang diunggah. Silakan lampirkan file MoM."

    logger.info("Uploading document %s (%d bytes)", filename, len(file_bytes))

    result = await api.upload_document(
        file_bytes=file_bytes,
        filename=filename,
        mom_type=mom_type,
        meeting_date=meeting_date,
        is_confidential=is_confidential,
        uploaded_by=uploaded_by,
    )

    document_id = result.get("id", "")
    if not document_id:
        return "Error: Upload gagal — tidak mendapat document ID dari server."

    logger.info("Document uploaded: %s, polling for extraction...", document_id)

    # Poll until document reaches HITL Gate 1
    for iteration in range(_MAX_POLL_ITERATIONS):
        await asyncio.sleep(_POLL_INTERVAL_S)

        try:
            doc = await api.get_document(document_id)
        except Exception:
            logger.warning("Poll iteration %d: failed to get document status", iteration + 1)
            continue

        status = doc.get("status", "")
        logger.debug("Poll %d/%d: status=%s", iteration + 1, _MAX_POLL_ITERATIONS, status)

        if status == "hitl_gate_1":
            # Extraction complete — fetch review detail
            try:
                review = await api.get_review_detail(document_id)
                return (
                    f"Dokumen **{filename}** berhasil diunggah dan diekstrak.\n\n"
                    + format_extraction(review)
                )
            except Exception:
                logger.exception("Failed to fetch review detail for %s", document_id)
                return (
                    f"Dokumen **{filename}** berhasil diekstrak (ID: `{document_id}`).\n"
                    "Namun gagal mengambil detail review. "
                    "Gunakan perintah cek status untuk melihat hasil."
                )

        if status in ("failed", "rejected"):
            return (
                f"Dokumen **{filename}** gagal diproses.\n"
                f"Status: `{status}` | ID: `{document_id}`"
            )

    # Timeout — processing is still ongoing
    return (
        f"Dokumen **{filename}** berhasil diunggah (ID: `{document_id}`).\n"
        f"Proses masih berjalan — status terakhir: `{status}`.\n"
        "Sistem akan mengirim notifikasi ketika ekstraksi selesai, "
        "atau Anda dapat cek status secara manual."
    )
