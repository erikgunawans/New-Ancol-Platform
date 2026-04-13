"""Tool handler — fetch and format compliance reports."""

from __future__ import annotations

import logging

from gemini_agent.api_client import ApiClient
from gemini_agent.formatting import format_report

logger = logging.getLogger(__name__)


async def handle_get_report(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Fetch a compliance report by ID and return formatted output.

    Parameters
    ----------
    params:
        report_id (str): UUID of the report.
    """
    report_id: str = params.get("report_id", "").strip()

    if not report_id:
        return "Error: Harap berikan report_id untuk mengambil laporan."

    logger.info("Fetching report: %s", report_id)

    try:
        report = await api.get_report(report_id)
    except Exception:
        logger.exception("Failed to fetch report %s", report_id)
        return f"Gagal mengambil laporan dengan ID `{report_id}`. Pastikan ID sudah benar."

    return format_report(report)
