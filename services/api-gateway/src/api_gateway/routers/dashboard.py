"""Dashboard API — aggregate statistics for Komisaris and management views."""

from __future__ import annotations

from ancol_common.db.connection import get_session
from ancol_common.db.models import BatchJob, Document, Report
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


class DashboardStats(BaseModel):
    total_documents: int
    pending_review: int
    completed: int
    failed: int
    rejected: int
    avg_composite_score: float | None = None
    avg_structural_score: float | None = None
    avg_substantive_score: float | None = None
    avg_regulatory_score: float | None = None
    documents_by_status: dict[str, int]
    active_batch_jobs: int
    batch_documents_queued: int


class TrendPoint(BaseModel):
    period: str
    avg_composite: float | None = None
    document_count: int = 0


class DashboardTrendsResponse(BaseModel):
    trends: list[TrendPoint]


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """Get aggregate compliance statistics."""
    async with get_session() as session:
        # Document counts by status
        status_query = select(Document.status, func.count(Document.id)).group_by(Document.status)
        result = await session.execute(status_query)
        status_counts = {row[0]: row[1] for row in result.all()}

        total = sum(status_counts.values())
        pending = sum(
            status_counts.get(s, 0)
            for s in ["hitl_gate_1", "hitl_gate_2", "hitl_gate_3", "hitl_gate_4"]
        )

        # Average scores from approved reports
        score_query = select(
            func.avg(Report.composite_score),
            func.avg(Report.structural_score),
            func.avg(Report.substantive_score),
            func.avg(Report.regulatory_score),
        ).where(Report.is_approved.is_(True))
        result = await session.execute(score_query)
        row = result.one_or_none()

        # Active batch jobs
        batch_query = select(func.count(BatchJob.id)).where(
            BatchJob.status.in_(["queued", "running"])
        )
        batch_result = await session.execute(batch_query)
        active_batches = batch_result.scalar() or 0

        queued_query = select(
            func.coalesce(
                func.sum(
                    BatchJob.total_documents - BatchJob.processed_count - BatchJob.failed_count
                ),
                0,
            )
        ).where(BatchJob.status.in_(["queued", "running"]))
        queued_result = await session.execute(queued_query)
        queued_docs = queued_result.scalar() or 0

    avg_composite = float(row[0]) if row and row[0] else None
    avg_structural = float(row[1]) if row and row[1] else None
    avg_substantive = float(row[2]) if row and row[2] else None
    avg_regulatory = float(row[3]) if row and row[3] else None

    return DashboardStats(
        total_documents=total,
        pending_review=pending,
        completed=status_counts.get("complete", 0),
        failed=status_counts.get("failed", 0),
        rejected=status_counts.get("rejected", 0),
        avg_composite_score=round(avg_composite, 1) if avg_composite else None,
        avg_structural_score=round(avg_structural, 1) if avg_structural else None,
        avg_substantive_score=round(avg_substantive, 1) if avg_substantive else None,
        avg_regulatory_score=round(avg_regulatory, 1) if avg_regulatory else None,
        documents_by_status=status_counts,
        active_batch_jobs=active_batches,
        batch_documents_queued=queued_docs,
    )


@router.get("/stats/trends", response_model=DashboardTrendsResponse)
async def get_dashboard_trends(
    months: int = Query(6, ge=1, le=24),
):
    """Get monthly composite score trends for the Komisaris dashboard."""
    async with get_session() as session:
        query = (
            select(
                func.to_char(Report.created_at, "YYYY-MM").label("period"),
                func.avg(Report.composite_score).label("avg_composite"),
                func.count(Report.id).label("doc_count"),
            )
            .where(Report.is_approved.is_(True))
            .group_by(func.to_char(Report.created_at, "YYYY-MM"))
            .order_by(func.to_char(Report.created_at, "YYYY-MM").desc())
            .limit(months)
        )
        result = await session.execute(query)
        rows = result.all()

    trends = [
        TrendPoint(
            period=row.period,
            avg_composite=round(float(row.avg_composite), 1) if row.avg_composite else None,
            document_count=row.doc_count,
        )
        for row in reversed(rows)
    ]

    return DashboardTrendsResponse(trends=trends)
