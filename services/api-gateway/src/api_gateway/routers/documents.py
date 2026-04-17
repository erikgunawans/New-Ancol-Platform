"""Documents API — upload, list, get, status tracking."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, date, datetime

from ancol_common.auth.mfa import require_mfa_verified
from ancol_common.auth.rbac import require_permission
from ancol_common.config import get_settings
from ancol_common.db.connection import get_session
from ancol_common.db.models import Document
from ancol_common.db.repository import get_document_by_id
from ancol_common.pubsub.publisher import publish_message
from ancol_common.rag.graph_client import GraphClient
from ancol_common.rag.models import DocumentIndicator
from ancol_common.schemas.bjr import BJRItemCode
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"], dependencies=[require_mfa_verified()])


_graph_client_singleton: GraphClient | None = None


def _get_graph_client() -> GraphClient | None:
    """Return the configured GraphClient, or None if unavailable.

    Instantiated lazily on first call and cached for the process lifetime
    so Neo4j/Spanner driver connection pools are reused across requests.
    Returns None when GRAPH_BACKEND=none, or when backend client
    instantiation fails (missing deps, bad credentials, unreachable
    host). The caller degrades silently per the GraphClient contract.
    """
    global _graph_client_singleton
    backend = os.getenv("GRAPH_BACKEND", "spanner").lower()
    if backend == "none":
        return None
    if _graph_client_singleton is not None:
        return _graph_client_singleton
    try:
        if backend == "neo4j":
            from ancol_common.rag.neo4j_graph import Neo4jGraphClient

            _graph_client_singleton = Neo4jGraphClient(
                uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                username=os.getenv("NEO4J_USER", "neo4j"),
                password=os.getenv("NEO4J_PASSWORD", ""),
            )
        else:
            from ancol_common.rag.spanner_graph import SpannerGraphClient

            # Reads GCP_PROJECT / SPANNER_INSTANCE / SPANNER_DATABASE from env
            _graph_client_singleton = SpannerGraphClient()
    except Exception:
        logger.exception("GraphClient instantiation failed (backend=%s)", backend)
        return None
    return _graph_client_singleton


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
    _auth=require_permission("documents:upload"),
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
    _auth=require_permission("documents:list"),
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
async def get_document(document_id: str, _auth=require_permission("documents:list")):
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


class BJRIndicatorResponse(BaseModel):
    """Per-decision BJR status for a single document."""

    decision_id: uuid.UUID
    decision_title: str
    status: str
    readiness_score: float | None
    is_locked: bool
    locked_at: datetime | None
    satisfied_items: list[BJRItemCode]
    missing_items: list[BJRItemCode]
    origin: str

    @classmethod
    def from_indicator(cls, ind: DocumentIndicator) -> BJRIndicatorResponse:
        return cls(
            decision_id=ind.decision_id,
            decision_title=ind.decision_title,
            status=ind.status,
            readiness_score=ind.readiness_score,
            is_locked=ind.is_locked,
            locked_at=ind.locked_at,
            satisfied_items=ind.satisfied_items,
            missing_items=ind.missing_items,
            origin=ind.origin,
        )


class BJRIndicatorsListResponse(BaseModel):
    indicators: list[BJRIndicatorResponse]
    total: int


@router.get(
    "/{document_id}/bjr-indicators",
    response_model=BJRIndicatorsListResponse,
    summary="BJR decision indicators for a document",
)
async def get_document_bjr_indicators(
    document_id: uuid.UUID,
    _auth=require_permission("bjr:read"),
) -> BJRIndicatorsListResponse:
    """Return the set of BJR decisions this document supports.

    Each indicator carries current readiness state + satisfied/missing
    checklist items. Backs the Gemini Enterprise chat tool
    `show_document_indicators`, which proactively enriches document mentions
    with BJR context.

    Degradation: returns an empty list when the graph backend is disabled,
    unimplemented for the configured backend, or errors at query time.
    Callers treat "no BJR context available" as a silent no-op.
    """
    graph = _get_graph_client()
    if graph is None:
        return BJRIndicatorsListResponse(indicators=[], total=0)

    try:
        indicators = await graph.get_document_indicators(document_id)
    except NotImplementedError:
        return BJRIndicatorsListResponse(indicators=[], total=0)
    except Exception:
        logger.exception("get_document_bjr_indicators failed for %s", document_id)
        return BJRIndicatorsListResponse(indicators=[], total=0)

    serialized = [BJRIndicatorResponse.from_indicator(ind) for ind in indicators]
    return BJRIndicatorsListResponse(indicators=serialized, total=len(serialized))
