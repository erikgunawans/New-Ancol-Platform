"""Analytics API — compliance trends, violation heatmaps, coverage stats.

Serves pre-computed analytics from PostgreSQL for the Komisaris dashboard.
In production, these queries can be backed by BigQuery materialized views.
"""

from __future__ import annotations

from ancol_common.auth.rbac import require_permission
from ancol_common.db.connection import get_session
from ancol_common.db.models import (
    ComplianceFindingRecord,
    Document,
    HitlDecisionRecord,
    Report,
)
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import case, extract, func, select

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# ── Response Models ──


class TrendPoint(BaseModel):
    period: str  # "2026-01" format
    avg_structural: float | None = None
    avg_substantive: float | None = None
    avg_regulatory: float | None = None
    avg_composite: float | None = None
    document_count: int = 0


class ScoreTrendResponse(BaseModel):
    trends: list[TrendPoint]
    period_type: str  # "monthly"


class ViolationTypeCount(BaseModel):
    violation_type: str
    count: int
    avg_severity_score: float | None = None


class ViolationHeatmapResponse(BaseModel):
    violations: list[ViolationTypeCount]
    total_documents_analyzed: int


class CoverageStats(BaseModel):
    total_documents: int
    fully_processed: int
    coverage_pct: float
    by_mom_type: dict[str, dict[str, int]]
    by_year: dict[str, int]


class HitlPerformance(BaseModel):
    gate: str
    avg_decision_hours: float | None = None
    total_decisions: int
    approved_count: int
    rejected_count: int
    modified_count: int
    sla_breach_count: int


class HitlPerformanceResponse(BaseModel):
    gates: list[HitlPerformance]


# ── Endpoints ──


@router.get("/trends", response_model=ScoreTrendResponse)
async def get_score_trends(
    _auth=require_permission("dashboard:view"),
    months: int = Query(12, ge=1, le=60),
):
    """Get monthly compliance score trends for approved reports."""
    async with get_session() as session:
        query = (
            select(
                func.to_char(Report.created_at, "YYYY-MM").label("period"),
                func.avg(Report.structural_score).label("avg_structural"),
                func.avg(Report.substantive_score).label("avg_substantive"),
                func.avg(Report.regulatory_score).label("avg_regulatory"),
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
            avg_structural=round(float(row.avg_structural), 1) if row.avg_structural else None,
            avg_substantive=round(float(row.avg_substantive), 1) if row.avg_substantive else None,
            avg_regulatory=round(float(row.avg_regulatory), 1) if row.avg_regulatory else None,
            avg_composite=round(float(row.avg_composite), 1) if row.avg_composite else None,
            document_count=row.doc_count,
        )
        for row in reversed(rows)
    ]

    return ScoreTrendResponse(trends=trends, period_type="monthly")


@router.get("/violations", response_model=ViolationHeatmapResponse)
async def get_violation_heatmap(_auth=require_permission("dashboard:view")):
    """Get violation type distribution across all analyzed documents."""
    async with get_session() as session:
        # Count documents with findings
        doc_count = await session.execute(
            select(func.count(func.distinct(ComplianceFindingRecord.document_id)))
        )
        total_docs = doc_count.scalar() or 0

        # Get red flag type counts from JSONB
        # red_flags is stored as JSONB with structure:
        # {"quorum": [...], "rpt": [...], "conflict_of_interest": [...], ...}
        findings_result = await session.execute(
            select(ComplianceFindingRecord.red_flags).where(
                ComplianceFindingRecord.red_flags.isnot(None)
            )
        )
        findings = findings_result.scalars().all()

    # Aggregate red flag types across all findings
    type_counts: dict[str, list[int]] = {}
    for red_flags in findings:
        if not isinstance(red_flags, dict):
            continue
        for flag_type, flags in red_flags.items():
            if not isinstance(flags, list):
                continue
            if flag_type not in type_counts:
                type_counts[flag_type] = []
            type_counts[flag_type].append(len(flags))

    violations = [
        ViolationTypeCount(
            violation_type=vtype,
            count=sum(counts),
        )
        for vtype, counts in sorted(type_counts.items(), key=lambda x: -sum(x[1]))
    ]

    return ViolationHeatmapResponse(
        violations=violations,
        total_documents_analyzed=total_docs,
    )


@router.get("/coverage", response_model=CoverageStats)
async def get_coverage_stats(_auth=require_permission("dashboard:view")):
    """Get document processing coverage statistics."""
    async with get_session() as session:
        # Total and completed documents
        total_result = await session.execute(select(func.count(Document.id)))
        total = total_result.scalar() or 0

        completed_result = await session.execute(
            select(func.count(Document.id)).where(Document.status == "complete")
        )
        completed = completed_result.scalar() or 0

        # By MoM type
        type_result = await session.execute(
            select(
                Document.mom_type,
                Document.status,
                func.count(Document.id),
            ).group_by(Document.mom_type, Document.status)
        )
        by_type: dict[str, dict[str, int]] = {}
        for row in type_result.all():
            mom_type = row[0] or "unknown"
            status = row[1]
            count = row[2]
            if mom_type not in by_type:
                by_type[mom_type] = {}
            by_type[mom_type][status] = count

        # By year
        year_result = await session.execute(
            select(
                extract("year", Document.meeting_date).label("year"),
                func.count(Document.id),
            )
            .where(Document.meeting_date.isnot(None))
            .group_by(extract("year", Document.meeting_date))
            .order_by(extract("year", Document.meeting_date))
        )
        by_year = {str(int(row[0])): row[1] for row in year_result.all()}

    return CoverageStats(
        total_documents=total,
        fully_processed=completed,
        coverage_pct=round(completed / max(total, 1) * 100, 1),
        by_mom_type=by_type,
        by_year=by_year,
    )


@router.get("/hitl-performance", response_model=HitlPerformanceResponse)
async def get_hitl_performance(_auth=require_permission("dashboard:view")):
    """Get HITL gate decision performance metrics."""
    async with get_session() as session:
        result = await session.execute(
            select(
                HitlDecisionRecord.gate,
                func.avg(
                    extract("epoch", HitlDecisionRecord.decided_at - HitlDecisionRecord.assigned_at)
                    / 3600
                ).label("avg_hours"),
                func.count(HitlDecisionRecord.id).label("total"),
                func.sum(case((HitlDecisionRecord.decision == "approved", 1), else_=0)).label(
                    "approved"
                ),
                func.sum(case((HitlDecisionRecord.decision == "rejected", 1), else_=0)).label(
                    "rejected"
                ),
                func.sum(case((HitlDecisionRecord.decision == "modified", 1), else_=0)).label(
                    "modified"
                ),
                func.sum(case((HitlDecisionRecord.is_sla_breached.is_(True), 1), else_=0)).label(
                    "sla_breach"
                ),
            )
            .group_by(HitlDecisionRecord.gate)
            .order_by(HitlDecisionRecord.gate)
        )
        rows = result.all()

    gates = [
        HitlPerformance(
            gate=row.gate,
            avg_decision_hours=round(float(row.avg_hours), 1) if row.avg_hours else None,
            total_decisions=row.total,
            approved_count=row.approved or 0,
            rejected_count=row.rejected or 0,
            modified_count=row.modified or 0,
            sla_breach_count=row.sla_breach or 0,
        )
        for row in rows
    ]

    return HitlPerformanceResponse(gates=gates)
