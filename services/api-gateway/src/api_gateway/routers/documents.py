"""Documents API — upload, list, get, status tracking."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from ancol_common.config import get_settings
from ancol_common.db.connection import get_session
from ancol_common.db.models import Document
from ancol_common.db.repository import get_document_by_id
from ancol_common.pubsub.publisher import publish_message
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/documents", tags=["Documents"])


class DocumentResponse(BaseModel):
    id: str
    filename: str
    format: str
    status: str
    mom_type: str | None = None
    meeting_date: date | None = None
    page_count: int | None = None
    ocr_confidence: float | None = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    mom_type: str = Form("regular"),
    meeting_date: str | None = Form(None),
    is_confidential: bool = Form(False),
    uploaded_by: str = Form("a0000000-0000-0000-0000-000000000001"),
):
    """Upload a MoM document for compliance processing."""
    settings = get_settings()

    from ancol_common.utils import detect_document_format, get_gcs_client

    doc_format = detect_document_format(file.filename or "unknown.pdf")

    content = await file.read()
    file_size = len(content)
    doc_id = str(uuid.uuid4())

    gcs_client = get_gcs_client()
    bucket = gcs_client.bucket(settings.bucket_raw)
    blob_name = f"uploads/{doc_id}/{file.filename}"
    blob = bucket.blob(blob_name)
    blob.metadata = {"document_id": doc_id, "uploaded_by": uploaded_by}
    blob.upload_from_string(content, content_type=file.content_type or "application/octet-stream")

    gcs_raw_uri = f"gs://{settings.bucket_raw}/{blob_name}"

    # Parse meeting date
    parsed_date = None
    if meeting_date:
        parsed_date = date.fromisoformat(meeting_date)

    # Create document record
    async with get_session() as session:
        document = Document(
            id=uuid.UUID(doc_id),
            filename=file.filename or "unknown",
            format=doc_format,
            file_size_bytes=file_size,
            gcs_raw_uri=gcs_raw_uri,
            status="pending",
            mom_type=mom_type,
            meeting_date=parsed_date,
            is_confidential=is_confidential,
            uploaded_by=uuid.UUID(uploaded_by),
        )
        session.add(document)

    # Publish upload event to trigger document processor
    publish_message(
        "mom-uploaded",
        {
            "document_id": doc_id,
            "bucket": settings.bucket_raw,
            "name": blob_name,
            "contentType": file.content_type or "application/pdf",
            "size": str(file_size),
            "metadata": {"document_id": doc_id, "uploaded_by": uploaded_by},
        },
    )

    return DocumentResponse(
        id=doc_id,
        filename=file.filename or "unknown",
        format=doc_format,
        status="pending",
        mom_type=mom_type,
        meeting_date=parsed_date,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """List documents with optional status filter."""
    from sqlalchemy import func, select

    async with get_session() as session:
        query = select(Document).order_by(Document.created_at.desc())
        count_query = select(func.count(Document.id))

        if status:
            query = query.where(Document.status == status)
            count_query = count_query.where(Document.status == status)

        count_result = await session.execute(count_query)
        total = count_result.scalar() or 0

        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        docs = result.scalars().all()

    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=str(d.id),
                filename=d.filename,
                format=d.format,
                status=d.status,
                mom_type=d.mom_type,
                meeting_date=d.meeting_date,
                page_count=d.page_count,
                ocr_confidence=float(d.ocr_confidence) if d.ocr_confidence else None,
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
            for d in docs
        ],
        total=total,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """Get a single document by ID."""
    async with get_session() as session:
        doc = await get_document_by_id(session, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        return DocumentResponse(
            id=str(doc.id),
            filename=doc.filename,
            format=doc.format,
            status=doc.status,
            mom_type=doc.mom_type,
            meeting_date=doc.meeting_date,
            page_count=doc.page_count,
            ocr_confidence=float(doc.ocr_confidence) if doc.ocr_confidence else None,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
