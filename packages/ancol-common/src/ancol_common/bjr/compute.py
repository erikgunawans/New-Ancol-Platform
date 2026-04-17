"""BJR compute orchestrator.

`compute_bjr(decision_id)` runs all 16 evaluators, upserts `bjr_checklists`
rows for the decision, computes dual-regime scores, and writes them back
to `strategic_decisions.bjr_readiness_score` / `corporate_compliance_score` /
`regional_compliance_score`.

This is the entry point called from the decisions router and (in a future
phase) from the bjr-agent Cloud Run service.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ancol_common.bjr.evaluators import EVALUATORS, EvaluationContext, EvaluatorResult
from ancol_common.bjr.scorer import BJRScoreResult, ChecklistSnapshot, compute_scores
from ancol_common.config import get_settings
from ancol_common.db.models import BJRChecklistItemRecord, StrategicDecision
from ancol_common.schemas.bjr import ChecklistItemStatus


@dataclass
class BJRComputeResult:
    """Full output of a compute run — checklist + scores + remediation notes."""

    decision_id: str
    items: list[EvaluatorResult]
    scores: BJRScoreResult
    computed_at: datetime


async def compute_bjr(
    session: AsyncSession,
    decision_id: str,
    triggered_by: str | None = None,
) -> BJRComputeResult:
    """Run the 16 evaluators and persist results.

    1. Loads the StrategicDecision
    2. Runs each evaluator in order
    3. Upserts a bjr_checklists row per item (unique on decision_id + item_code)
    4. Computes dual-regime scores via the scorer
    5. Writes the three scores back to the decision row

    Returns a BJRComputeResult summarizing the run. Caller commits the session.
    """
    decision_uuid = uuid.UUID(decision_id)
    result = await session.execute(
        select(StrategicDecision).where(StrategicDecision.id == decision_uuid)
    )
    decision = result.scalar_one_or_none()
    if decision is None:
        raise ValueError(f"StrategicDecision {decision_id} not found")

    settings = get_settings()
    ctx = EvaluationContext(
        decision=decision,
        session=session,
        materiality_threshold_idr=settings.bjr_materiality_threshold_idr,
    )

    # Run all 16 evaluators sequentially (they share one session)
    results: list[EvaluatorResult] = []
    for evaluator in EVALUATORS:
        results.append(await evaluator(ctx))

    # Upsert checklist rows
    triggered_by_uuid = uuid.UUID(triggered_by) if triggered_by else None
    await _upsert_checklist_rows(session, decision_uuid, results, triggered_by_uuid)

    # Compute scores
    snapshots = [ChecklistSnapshot(item_code=r.item_code, status=r.status) for r in results]
    scores = compute_scores(snapshots, gate_5_threshold=settings.bjr_gate5_threshold)

    # Write scores back to the decision
    now = datetime.now(UTC)
    decision.bjr_readiness_score = scores.bjr_readiness_score
    decision.corporate_compliance_score = scores.corporate_compliance_score
    decision.regional_compliance_score = scores.regional_compliance_score
    decision.updated_at = now

    return BJRComputeResult(
        decision_id=decision_id,
        items=results,
        scores=scores,
        computed_at=now,
    )


async def _upsert_checklist_rows(
    session: AsyncSession,
    decision_id: uuid.UUID,
    results: list[EvaluatorResult],
    triggered_by: uuid.UUID | None,
) -> None:
    """Insert-or-update a bjr_checklists row for every result.

    Uniqueness is enforced by (decision_id, item_code) — if a row exists we
    update in-place; otherwise we insert. Keeps history-free for v1; audit
    trail captures the compute event separately.
    """
    existing_result = await session.execute(
        select(BJRChecklistItemRecord).where(BJRChecklistItemRecord.decision_id == decision_id)
    )
    existing_by_code = {r.item_code: r for r in existing_result.scalars().all()}
    now = datetime.now(UTC)

    for r in results:
        row = existing_by_code.get(r.item_code)
        if row is None:
            row = BJRChecklistItemRecord(
                decision_id=decision_id,
                phase=r.phase,
                item_code=r.item_code,
                status=r.status,
                ai_confidence=r.ai_confidence,
                evidence_refs=r.evidence_refs or None,
                regulation_basis=r.regulation_basis or None,
                remediation_note=r.remediation_note,
                last_checked_at=now,
                last_checked_by=triggered_by,
            )
            session.add(row)
        else:
            # Preserve manual overrides — a human-set 'waived' stays waived on recompute.
            if row.status != ChecklistItemStatus.WAIVED.value:
                row.status = r.status
                row.ai_confidence = r.ai_confidence
                row.evidence_refs = r.evidence_refs or None
                row.regulation_basis = r.regulation_basis or None
                row.remediation_note = r.remediation_note
            row.last_checked_at = now
            row.last_checked_by = triggered_by
