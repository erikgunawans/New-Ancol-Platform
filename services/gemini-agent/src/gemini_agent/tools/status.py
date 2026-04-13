"""Tool handler — check document processing status."""

from __future__ import annotations

import logging
import re

from gemini_agent.api_client import ApiClient
from gemini_agent.formatting import format_document_status

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


async def handle_check_status(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Check the processing status of a document.

    If ``document_id`` is a valid UUID, fetches directly.
    Otherwise, lists documents and attempts to match by filename or date.

    Parameters
    ----------
    params:
        document_id (str | None): UUID or search term (filename / date).
    """
    query: str = params.get("document_id", "").strip()

    if not query:
        return "Error: Harap berikan document ID atau nama file untuk dicari."

    # Direct UUID lookup
    if _UUID_RE.match(query):
        logger.info("Direct status lookup: %s", query)
        try:
            doc = await api.get_document(query)
            return format_document_status(doc)
        except Exception:
            logger.exception("Failed to fetch document %s", query)
            return f"Dokumen dengan ID `{query}` tidak ditemukan."

    # Search by filename or meeting date
    logger.info("Searching documents for: %s", query)

    try:
        result = await api.list_documents(limit=100)
    except Exception:
        logger.exception("Failed to list documents")
        return "Gagal mengambil daftar dokumen dari server."

    documents = result.get("documents", [])
    query_lower = query.lower()

    matches = [
        d
        for d in documents
        if query_lower in d.get("filename", "").lower()
        or query_lower in (d.get("meeting_date") or "")
    ]

    if not matches:
        return (
            f"Tidak ditemukan dokumen yang cocok dengan `{query}`.\n"
            "Coba gunakan document ID (UUID) untuk pencarian lebih tepat."
        )

    if len(matches) == 1:
        return format_document_status(matches[0])

    # Multiple matches — show list
    lines = [f"Ditemukan **{len(matches)} dokumen** yang cocok dengan `{query}`:", ""]
    for i, doc in enumerate(matches[:10], 1):
        doc_id = doc.get("id", "-")
        filename = doc.get("filename", "-")
        status = doc.get("status", "-")
        lines.append(f"  {i}. **{filename}** — `{status}` (ID: `{doc_id}`)")

    if len(matches) > 10:
        lines.append(f"  ... dan {len(matches) - 10} dokumen lainnya.")

    lines.append("")
    lines.append("Gunakan document ID spesifik untuk melihat detail.")

    return "\n".join(lines)
