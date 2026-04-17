"""Shared AsyncMock helpers for BJR evaluator and compute tests.

The BJR schema uses PostgreSQL-specific types (JSONB, UUID[], GIN indexes) that
don't translate to SQLite, so integration tests against a real DB would need a
live Postgres. For unit-level tests of evaluator logic + orchestrator invariants,
AsyncMock sessions are sufficient and match the existing project pattern
(`test_obligation_transitions.py`).

Usage:

    from tests._bjr_fixtures import fake_session, make_decision

    async def test_my_evaluator():
        decision = make_decision(title="JV Hotel", ...)
        session = fake_session(
            DueDiligenceReport=[dd_fixture(decision.id, reviewed=True)],
        )
        ctx = EvaluationContext(decision=decision, session=session)
        result = await eval_pd_01_dd(ctx)
        assert result.status == "satisfied"
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from ancol_common.db.models import (
    AuditCommitteeReport,
    Contract,
    DecisionEvidenceRecord,
    Document,
    DueDiligenceReport,
    Extraction,
    FeasibilityStudyReport,
    MaterialDisclosure,
    OrganApproval,
    RelatedPartyEntity,
    RJPPTheme,
    RKABLineItem,
    SPIReport,
    StrategicDecision,
)


def _wrap_rows(rows: list[Any]) -> MagicMock:
    """Build a MagicMock matching the SQLAlchemy Result interface."""
    result = MagicMock()
    # .scalars().all() — most common evaluator pattern
    scalars = MagicMock()
    scalars.all.return_value = list(rows)
    scalars.first.return_value = rows[0] if rows else None
    result.scalars.return_value = scalars
    # .scalar_one_or_none()
    result.scalar_one_or_none.return_value = rows[0] if rows else None
    # .scalar_one() — raises NoResultFound if empty (match production)
    if rows:
        result.scalar_one.return_value = rows[0]
    else:
        from sqlalchemy.exc import NoResultFound

        result.scalar_one.side_effect = NoResultFound()
    # .scalar() — first column of first row, or None
    result.scalar.return_value = rows[0] if rows else None
    # .all() for evaluators that select tuples (e.g. POST-16-ARCHIVE batch lookup)
    result.all.return_value = [
        (r.id, getattr(r, "gcs_uri", None)) for r in rows if hasattr(r, "id")
    ]
    return result


def fake_session(
    **rows_by_model: list[Any],
) -> AsyncMock:
    """Build an AsyncMock session that routes queries to pre-configured rows.

    Pass rows keyed by model class name — order doesn't matter, multiple
    `select(Model)` calls return the same results. For tests that need
    sequence-dependent behavior, use AsyncMock directly.

    Model keys match SQLAlchemy model class names (Document, Contract, etc).
    """
    model_rows: dict[str, list[Any]] = {name: list(rows) for name, rows in rows_by_model.items()}
    session = AsyncMock()

    async def mock_execute(stmt):
        model_name = _select_target_name(stmt)
        return _wrap_rows(model_rows.get(model_name, []))

    session.execute = mock_execute
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _select_target_name(stmt: Any) -> str:
    """Extract the primary model class name from a SELECT statement.

    Best-effort: inspects `stmt.selected_columns` and returns the first
    column's class name. Handles simple `select(Model)` and `select(Model.col)`
    patterns — exotic queries should build the MagicMock manually.
    """
    # Try the column_descriptions entry first
    descriptions = getattr(stmt, "column_descriptions", None)
    if descriptions:
        for d in descriptions:
            entity = d.get("entity")
            if entity is not None:
                return entity.__name__
            target_type = d.get("type")
            if target_type is not None and hasattr(target_type, "__name__"):
                return target_type.__name__
    # Fallback: try selected_columns
    cols = getattr(stmt, "selected_columns", None)
    if cols is not None:
        for col in cols:
            parent = getattr(col, "table", None)
            if parent is not None and hasattr(parent, "name"):
                # Map tablename -> model name via known models
                return _tablename_to_model.get(parent.name, "")
    return ""


# Reverse map: ORM tablename → model class name
_tablename_to_model: dict[str, str] = {
    Document.__tablename__: "Document",
    Contract.__tablename__: "Contract",
    DueDiligenceReport.__tablename__: "DueDiligenceReport",
    FeasibilityStudyReport.__tablename__: "FeasibilityStudyReport",
    SPIReport.__tablename__: "SPIReport",
    AuditCommitteeReport.__tablename__: "AuditCommitteeReport",
    MaterialDisclosure.__tablename__: "MaterialDisclosure",
    OrganApproval.__tablename__: "OrganApproval",
    RKABLineItem.__tablename__: "RKABLineItem",
    RJPPTheme.__tablename__: "RJPPTheme",
    RelatedPartyEntity.__tablename__: "RelatedPartyEntity",
    Extraction.__tablename__: "Extraction",
    StrategicDecision.__tablename__: "StrategicDecision",
    DecisionEvidenceRecord.__tablename__: "DecisionEvidenceRecord",
}


# Factory helpers — create lightweight model instances without hitting the DB.


def make_decision(
    title: str = "Test Decision",
    initiative_type: str = "investment",
    status: str = "ideation",
    rkab_line_id: uuid.UUID | None = None,
    rjpp_theme_id: uuid.UUID | None = None,
    value_idr: float | None = None,
    decision_id: uuid.UUID | None = None,
) -> StrategicDecision:
    d = StrategicDecision(
        title=title,
        initiative_type=initiative_type,
        status=status,
        rkab_line_id=rkab_line_id,
        rjpp_theme_id=rjpp_theme_id,
        business_owner_id=uuid.uuid4(),
        value_idr=value_idr,
    )
    d.id = decision_id or uuid.uuid4()
    d.is_bjr_locked = False
    d.source = "proactive"
    d.bjr_readiness_score = None
    d.corporate_compliance_score = None
    d.regional_compliance_score = None
    d.updated_at = datetime.now(UTC)
    return d


def make_dd_report(
    decision_id: uuid.UUID,
    reviewed_by_legal: uuid.UUID | None = None,
    risk_rating: str = "medium",
    gcs_uri: str | None = "gs://bucket/dd.pdf",
) -> DueDiligenceReport:
    r = DueDiligenceReport(
        decision_id=decision_id,
        title="Test DD",
        risk_rating=risk_rating,
        prepared_by=uuid.uuid4(),
        reviewed_by_legal=reviewed_by_legal,
        gcs_uri=gcs_uri,
    )
    r.id = uuid.uuid4()
    return r


def make_fs_report(
    decision_id: uuid.UUID,
    reviewed_by_finance: uuid.UUID | None = None,
    gcs_uri: str | None = "gs://bucket/fs.pdf",
) -> FeasibilityStudyReport:
    r = FeasibilityStudyReport(
        decision_id=decision_id,
        title="Test FS",
        prepared_by=uuid.uuid4(),
        reviewed_by_finance=reviewed_by_finance,
        gcs_uri=gcs_uri,
    )
    r.id = uuid.uuid4()
    return r


def make_rkab(
    approval_status: str = "rups_approved",
    fiscal_year: int = 2026,
    code: str = "TP-01",
) -> RKABLineItem:
    r = RKABLineItem(
        fiscal_year=fiscal_year,
        code=code,
        category="theme_park",
        activity_name="Test activity",
        budget_idr=1000000.0,
        approval_status=approval_status,
    )
    r.id = uuid.uuid4()
    return r


def make_rjpp(is_active: bool = True) -> RJPPTheme:
    r = RJPPTheme(
        period_start_year=2025,
        period_end_year=2029,
        theme_name="Test Theme",
        is_active=is_active,
    )
    r.id = uuid.uuid4()
    return r


def make_extraction(
    document_id: uuid.UUID,
    quorum_met: bool | None = True,
    signatures_complete: bool | None = True,
    attendees: Any = None,
    full_text: str = "",
) -> Extraction:
    structured_mom = {}
    if quorum_met is not None:
        structured_mom["quorum_met"] = quorum_met
    if signatures_complete is not None:
        structured_mom["signatures_complete"] = signatures_complete
    if full_text:
        structured_mom["full_text"] = full_text
    e = Extraction(
        document_id=document_id,
        agent_version="test",
        model_used="test",
        structured_mom=structured_mom,
        attendees=attendees if attendees is not None else [],
        resolutions={},
        field_confidence={},
    )
    e.id = uuid.uuid4()
    return e


def make_rpt_entity(name: str) -> RelatedPartyEntity:
    r = RelatedPartyEntity(
        entity_name=name,
        entity_type="subsidiary",
        effective_from=date(2020, 1, 1),
        is_active=True,
    )
    r.id = uuid.uuid4()
    return r


def make_material_disclosure(decision_id: uuid.UUID, is_on_time: bool = True) -> MaterialDisclosure:
    r = MaterialDisclosure(
        disclosure_type="keterbukaan informasi material",
        decision_id=decision_id,
        submission_date=date(2026, 4, 1),
        deadline_date=date(2026, 4, 10),
        is_on_time=is_on_time,
        filed_by=uuid.uuid4(),
    )
    r.id = uuid.uuid4()
    return r


def make_organ_approval(decision_id: uuid.UUID, approval_type: str = "komisaris") -> OrganApproval:
    r = OrganApproval(
        approval_type=approval_type,
        decision_id=decision_id,
        approver_user_id=uuid.uuid4(),
        approval_date=date(2026, 4, 1),
    )
    r.id = uuid.uuid4()
    return r
