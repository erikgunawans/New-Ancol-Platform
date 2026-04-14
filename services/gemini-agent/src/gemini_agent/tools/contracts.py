"""Tool handlers for contract operations — upload, status, portfolio."""

from __future__ import annotations

import logging

from gemini_agent.api_client import ApiClient
from gemini_agent.formatting import (
    format_contract_portfolio,
    format_contract_status,
)

logger = logging.getLogger(__name__)


async def handle_upload_contract(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Upload a contract document and return its metadata."""
    from ancol_common.utils import SYSTEM_USER_ID

    file_bytes: bytes = params.get("file_bytes", b"")
    filename: str = params.get("filename", "unknown.pdf")
    title: str = params.get("title", filename)
    contract_type: str = params.get("contract_type", "vendor")
    contract_number: str | None = params.get("contract_number")
    uploaded_by: str = user.get("id", SYSTEM_USER_ID)

    if not file_bytes:
        return "Error: Tidak ada file yang diunggah. Silakan lampirkan file kontrak."

    logger.info("Uploading contract %s (%d bytes)", filename, len(file_bytes))

    result = await api.upload_contract(
        file_bytes=file_bytes,
        filename=filename,
        title=title,
        contract_type=contract_type,
        contract_number=contract_number,
        uploaded_by=uploaded_by,
    )

    contract_id = result.get("id", "")
    if not contract_id:
        return "Error: Upload gagal — tidak mendapat contract ID dari server."

    return (
        f"Kontrak **{title}** berhasil diunggah.\n\n"
        + format_contract_status(result)
    )


async def handle_check_contract_status(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Check the current status of a contract."""
    contract_id: str = params.get("contract_id", "")
    if not contract_id:
        return "Error: Mohon berikan contract_id."

    try:
        data = await api.get_contract(contract_id)
    except Exception:
        logger.exception("Failed to get contract %s", contract_id)
        return f"Error: Gagal mengambil data kontrak `{contract_id}`."

    return format_contract_status(data)


async def handle_get_contract_portfolio(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Get portfolio-level contract summary."""
    status: str | None = params.get("status")
    contract_type: str | None = params.get("contract_type")

    try:
        data = await api.list_contracts(
            status=status,
            contract_type=contract_type,
            limit=200,
        )
    except Exception:
        logger.exception("Failed to get contract portfolio")
        return "Error: Gagal mengambil data portfolio kontrak."

    return format_contract_portfolio(data)
