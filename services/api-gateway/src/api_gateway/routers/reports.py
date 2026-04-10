"""Reports API — list, get, download PDF/Excel."""

from __future__ import annotations

import uuid
from datetime import datetime

from ancol_common.db.connection import get_session
from ancol_common.db.models import Document, Report
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select

router = APIRouter(prefix="/reports", tags=["Reports"])


class ReportSummary(BaseModel):
    id: str
    document_id: str
    filename: str
    structural_score: float
    substantive_score: float
    regulatory_score: float
    composite_score: float
    is_approved: bool
    pdf_uri: str | None = None
    excel_uri: str | None = None
    created_at: datetime


class ReportListResponse(BaseModel):
    reports: list[ReportSummary]
    total: int


class ReportDetail(BaseModel):
    id: str
    document_id: str
    structural_score: float
    substantive_score: float
    regulatory_score: float
    composite_score: float
    score_weights: dict
    corrective_suggestions: list
    report_data: dict
    is_approved: bool
    is_visible_to_komisaris: bool
    pdf_uri: str | None = None
    excel_uri: str | None = None
    created_at: datetime


@router.get("", response_model=ReportListResponse)
async def list_reports(
    approved_only: bool = Query(False),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """List compliance reports."""
    async with get_session() as session:
        query = (
            select(Report, Document.filename)
            .join(Document, Report.document_id == Document.id)
            .order_by(Report.created_at.desc())
        )
        if approved_only:
            query = query.where(Report.is_approved.is_(True))

        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        rows = result.all()

    reports = [
        ReportSummary(
            id=str(r.id),
            document_id=str(r.document_id),
            filename=fname,
            structural_score=float(r.structural_score),
            substantive_score=float(r.substantive_score),
            regulatory_score=float(r.regulatory_score),
            composite_score=float(r.composite_score),
            is_approved=r.is_approved,
            pdf_uri=r.gcs_pdf_uri,
            excel_uri=r.gcs_excel_uri,
            created_at=r.created_at,
        )
        for r, fname in rows
    ]

    return ReportListResponse(reports=reports, total=len(reports))


@router.get("/{report_id}", response_model=ReportDetail)
async def get_report(report_id: str):
    """Get a single report with full data."""
    async with get_session() as session:
        report = await session.get(Report, uuid.UUID(report_id))
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

    return ReportDetail(
        id=str(report.id),
        document_id=str(report.document_id),
        structural_score=float(report.structural_score),
        substantive_score=float(report.substantive_score),
        regulatory_score=float(report.regulatory_score),
        composite_score=float(report.composite_score),
        score_weights=report.score_weights,
        corrective_suggestions=report.corrective_suggestions,
        report_data=report.report_data,
        is_approved=report.is_approved,
        is_visible_to_komisaris=report.is_visible_to_komisaris,
        pdf_uri=report.gcs_pdf_uri,
        excel_uri=report.gcs_excel_uri,
        created_at=report.created_at,
    )


@router.get("/{report_id}/download/{format}")
async def download_report(report_id: str, format: str):
    """Generate a signed URL for PDF or Excel download."""
    if format not in ("pdf", "excel"):
        raise HTTPException(status_code=400, detail="Format must be 'pdf' or 'excel'")

    async with get_session() as session:
        report = await session.get(Report, uuid.UUID(report_id))
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

    uri = report.gcs_pdf_uri if format == "pdf" else report.gcs_excel_uri
    if not uri:
        raise HTTPException(status_code=404, detail=f"{format.upper()} report not generated yet")

    # Generate signed URL
    from google.cloud import storage

    parts = uri.replace("gs://", "").split("/", 1)
    client = storage.Client()
    bucket = client.bucket(parts[0])
    blob = bucket.blob(parts[1])

    signed_url = blob.generate_signed_url(
        version="v4",
        expiration=3600,
        method="GET",
    )

    return RedirectResponse(url=signed_url)
