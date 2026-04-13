"""Contracts API — upload, list, get, update, status transitions, clauses, risk."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from ancol_common.config import get_settings
from ancol_common.db.connection import get_session
from ancol_common.db.models import Contract
from ancol_common.db.repository import (
    create_contract,
    get_contract_by_id,
    transition_contract_status,
)
from ancol_common.pubsub.publisher import publish_message
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/contracts", tags=["Contracts"])


class ContractResponse(BaseModel):
    id: str
    title: str
    contract_number: str | None = None
    contract_type: str
    status: str
    effective_date: date | None = None
    expiry_date: date | None = None
    total_value: float | None = None
    currency: str = "IDR"
    risk_level: str | None = None
    risk_score: float | None = None
    page_count: int | None = None
    created_at: datetime
    updated_at: datetime


class ContractListResponse(BaseModel):
    contracts: list[ContractResponse]
    total: int


class ContractUpdateRequest(BaseModel):
    title: str | None = None
    contract_number: str | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    total_value: float | None = None
    currency: str | None = None
    is_confidential: bool | None = None


class StatusTransitionRequest(BaseModel):
    new_status: str
    error_message: str | None = None


def _contract_to_response(c: Contract) -> ContractResponse:
    return ContractResponse(
        id=str(c.id),
        title=c.title,
        contract_number=c.contract_number,
        contract_type=c.contract_type,
        status=c.status,
        effective_date=c.effective_date,
        expiry_date=c.expiry_date,
        total_value=float(c.total_value) if c.total_value else None,
        currency=c.currency,
        risk_level=c.risk_level,
        risk_score=float(c.risk_score) if c.risk_score else None,
        page_count=c.page_count,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.post("", response_model=ContractResponse)
async def upload_contract(
    file: UploadFile = File(...),
    title: str = Form(...),
    contract_type: str = Form("vendor"),
    contract_number: str | None = Form(None),
    uploaded_by: str = Form("a0000000-0000-0000-0000-000000000001"),
):
    """Upload a contract document for processing."""
    settings = get_settings()

    from ancol_common.utils import get_gcs_client

    content = await file.read()
    doc_id = str(uuid.uuid4())

    gcs_client = get_gcs_client()
    bucket = gcs_client.bucket(settings.bucket_contracts)
    blob_name = f"uploads/{doc_id}/{file.filename}"
    blob = bucket.blob(blob_name)
    blob.metadata = {"contract_id": doc_id, "uploaded_by": uploaded_by}
    blob.upload_from_string(
        content, content_type=file.content_type or "application/octet-stream"
    )

    gcs_raw_uri = f"gs://{settings.bucket_contracts}/{blob_name}"

    async with get_session() as session:
        contract = await create_contract(
            session,
            title=title,
            contract_type=contract_type,
            uploaded_by=uploaded_by,
            gcs_raw_uri=gcs_raw_uri,
            contract_number=contract_number,
        )
        contract_id = str(contract.id)

    publish_message(
        "contract-uploaded",
        {
            "contract_id": contract_id,
            "bucket": settings.bucket_contracts,
            "name": blob_name,
            "contract_type": contract_type,
        },
    )

    return ContractResponse(
        id=contract_id,
        title=title,
        contract_number=contract_number,
        contract_type=contract_type,
        status="draft",
        currency="IDR",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@router.get("", response_model=ContractListResponse)
async def list_contracts_endpoint(
    status: str | None = Query(None),
    contract_type: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """List contracts with optional status/type filter."""
    from sqlalchemy import func, select

    async with get_session() as session:
        query = select(Contract).order_by(Contract.created_at.desc())
        count_query = select(func.count(Contract.id))

        if status:
            query = query.where(Contract.status == status)
            count_query = count_query.where(Contract.status == status)
        if contract_type:
            query = query.where(Contract.contract_type == contract_type)
            count_query = count_query.where(Contract.contract_type == contract_type)

        count_result = await session.execute(count_query)
        total = count_result.scalar() or 0

        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        contracts = result.scalars().all()

    return ContractListResponse(
        contracts=[_contract_to_response(c) for c in contracts],
        total=total,
    )


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(contract_id: str):
    """Get a single contract by ID."""
    async with get_session() as session:
        contract = await get_contract_by_id(session, contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        return _contract_to_response(contract)


@router.patch("/{contract_id}", response_model=ContractResponse)
async def update_contract(contract_id: str, body: ContractUpdateRequest):
    """Update contract metadata."""
    async with get_session() as session:
        contract = await get_contract_by_id(session, contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(contract, field, value)
        contract.updated_at = datetime.now(UTC)

    return _contract_to_response(contract)


@router.post("/{contract_id}/status")
async def transition_status(contract_id: str, body: StatusTransitionRequest):
    """Transition contract to a new lifecycle status."""
    async with get_session() as session:
        success = await transition_contract_status(
            session, contract_id, body.new_status, body.error_message
        )
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Invalid status transition or contract not found",
            )
    return {"contract_id": contract_id, "new_status": body.new_status}


@router.get("/{contract_id}/clauses")
async def get_contract_clauses(contract_id: str):
    """Get extracted clauses for a contract."""
    from ancol_common.db.models import ContractClauseRecord

    async with get_session() as session:
        contract = await get_contract_by_id(session, contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        from sqlalchemy import select

        result = await session.execute(
            select(ContractClauseRecord)
            .where(ContractClauseRecord.contract_id == contract.id)
            .order_by(ContractClauseRecord.clause_number)
        )
        clauses = result.scalars().all()

    return {
        "contract_id": contract_id,
        "clauses": [
            {
                "id": str(cl.id),
                "clause_number": cl.clause_number,
                "title": cl.title,
                "text": cl.text,
                "category": cl.category,
                "risk_level": cl.risk_level,
                "risk_reason": cl.risk_reason,
                "confidence": float(cl.confidence),
            }
            for cl in clauses
        ],
    }


@router.get("/{contract_id}/risk")
async def get_contract_risk(contract_id: str):
    """Get risk analysis for a contract."""
    async with get_session() as session:
        contract = await get_contract_by_id(session, contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

    return {
        "contract_id": contract_id,
        "risk_level": contract.risk_level,
        "risk_score": float(contract.risk_score) if contract.risk_score else None,
        "extraction_data": contract.extraction_data or {},
    }


@router.get("/{contract_id}/download")
async def download_contract(contract_id: str):
    """Get a signed download URL for the contract document."""
    from ancol_common.utils import get_gcs_client, parse_gcs_uri

    async with get_session() as session:
        contract = await get_contract_by_id(session, contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

    uri = contract.gcs_raw_uri
    if not uri:
        raise HTTPException(status_code=404, detail="No file attached to contract")

    bucket_name, blob_name = parse_gcs_uri(uri)
    gcs_client = get_gcs_client()
    bucket = gcs_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    import datetime as dt

    url = blob.generate_signed_url(expiration=dt.timedelta(hours=1))
    return {"download_url": url}
