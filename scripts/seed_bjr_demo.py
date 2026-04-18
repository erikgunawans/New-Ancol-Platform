"""Seed demo BJR decisions + evidence + checklist for staging / demo environments.

Creates 3 StrategicDecisions covering 3 distinct lifecycle states, plus evidence
and checklist rows, so the Gemini chat tools return real (non-empty) responses
in demos. Idempotent — safe to re-run (check-then-insert on deterministic UUIDs
and on existing unique indexes).

Decisions:
  1. "Akuisisi Hotel Wahana" — dd_in_progress, readiness 72 (below Gate 5 threshold,
     flagged CRITICAL item demonstrates "what's missing" chat response)
  2. "Divestasi Unit Marine Park" — bjr_locked, readiness 94 (shows Passport-ready
     state, get_passport_url returns a signed URL)
  3. "Kerjasama Strategis PT Jaya Konstruksi" — ideation, readiness None (fresh
     state, all checklist items not_started)

Usage:
    PYTHONPATH=packages/ancol-common/src python3 scripts/seed_bjr_demo.py --dry-run
    PYTHONPATH=packages/ancol-common/src python3 scripts/seed_bjr_demo.py

After seeding, run the graph backfill to populate Neo4j:
    PYTHONPATH=packages/ancol-common/src python3 scripts/bjr_graph_backfill.py
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from datetime import UTC, datetime

from ancol_common.db.connection import dispose_engine, get_session
from ancol_common.db.models import (
    BJRChecklistItemRecord,
    DecisionEvidenceRecord,
    StrategicDecision,
)
from ancol_common.schemas.bjr import (
    BJRItemCode,
    ChecklistItemStatus,
    ChecklistPhase,
)
from ancol_common.utils import SYSTEM_USER_ID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Deterministic UUIDs for the 3 seeded decisions — stable across re-runs so
# idempotency works without a separate lookup table.
DECISION_1_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DECISION_2_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
DECISION_3_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")

_SYS = uuid.UUID(SYSTEM_USER_ID)

# Fake evidence UUIDs — the evidence_id column is polymorphic (no FK), so these
# don't need to exist in any actual source table. They produce visible edges
# in the graph for demo purposes.
EV_DD_1 = uuid.UUID("aaaa1111-0000-0000-0000-000000000001")
EV_FS_1 = uuid.UUID("aaaa1111-0000-0000-0000-000000000002")
EV_MOM_1 = uuid.UUID("aaaa1111-0000-0000-0000-000000000003")

EV_DD_2 = uuid.UUID("bbbb2222-0000-0000-0000-000000000001")
EV_FS_2 = uuid.UUID("bbbb2222-0000-0000-0000-000000000002")
EV_MOM_2 = uuid.UUID("bbbb2222-0000-0000-0000-000000000003")
EV_OJK_2 = uuid.UUID("bbbb2222-0000-0000-0000-000000000004")


_DECISIONS: list[dict] = [
    {
        "id": DECISION_1_ID,
        "title": "Akuisisi Hotel Wahana",
        "description": "Akuisisi 100% saham PT Wahana Hotel senilai Rp 150 miliar.",
        "initiative_type": "investment",
        "status": "dd_in_progress",
        "business_owner_id": _SYS,
        "value_idr": 150_000_000_000,
        "bjr_readiness_score": 72.0,
        "corporate_compliance_score": 72.0,
        "regional_compliance_score": 88.0,
        "is_bjr_locked": False,
        "locked_at": None,
        "source": "proactive",
    },
    {
        "id": DECISION_2_ID,
        "title": "Divestasi Unit Marine Park",
        "description": "Divestasi unit usaha Marine Park ke PT Investor Asing senilai Rp 2,5 triliun.",
        "initiative_type": "divestment",
        "status": "bjr_locked",
        "business_owner_id": _SYS,
        "value_idr": 2_500_000_000_000,
        "bjr_readiness_score": 94.0,
        "corporate_compliance_score": 94.0,
        "regional_compliance_score": 94.0,
        "is_bjr_locked": True,
        "locked_at": datetime(2026, 4, 1, 9, 0, 0, tzinfo=UTC),
        "gcs_passport_uri": "gs://ancol-bjr-passports/divestasi-marine-park-v1.pdf",
        "source": "proactive",
    },
    {
        "id": DECISION_3_ID,
        "title": "Kerjasama Strategis PT Jaya Konstruksi",
        "description": "Kerjasama konstruksi fase ekspansi 2026-2028.",
        "initiative_type": "partnership",
        "status": "ideation",
        "business_owner_id": _SYS,
        "value_idr": None,
        "bjr_readiness_score": None,
        "corporate_compliance_score": None,
        "regional_compliance_score": None,
        "is_bjr_locked": False,
        "source": "proactive",
    },
]


_EVIDENCE: list[dict] = [
    # Decision 1 — 3 evidence (partial: DD + FS in progress, MoM from recent meeting)
    {
        "decision_id": DECISION_1_ID,
        "evidence_type": "dd_report",
        "evidence_id": EV_DD_1,
        "relationship_type": "documents",
    },
    {
        "decision_id": DECISION_1_ID,
        "evidence_type": "fs_report",
        "evidence_id": EV_FS_1,
        "relationship_type": "documents",
    },
    {
        "decision_id": DECISION_1_ID,
        "evidence_type": "mom",
        "evidence_id": EV_MOM_1,
        "relationship_type": "supports",
    },
    # Decision 2 — 4 evidence (complete: DD + FS + MoM + OJK disclosure)
    {
        "decision_id": DECISION_2_ID,
        "evidence_type": "dd_report",
        "evidence_id": EV_DD_2,
        "relationship_type": "documents",
    },
    {
        "decision_id": DECISION_2_ID,
        "evidence_type": "fs_report",
        "evidence_id": EV_FS_2,
        "relationship_type": "documents",
    },
    {
        "decision_id": DECISION_2_ID,
        "evidence_type": "mom",
        "evidence_id": EV_MOM_2,
        "relationship_type": "authorizes",
    },
    {
        "decision_id": DECISION_2_ID,
        "evidence_type": "ojk_disclosure",
        "evidence_id": EV_OJK_2,
        "relationship_type": "discloses",
    },
    # Decision 3 — no evidence yet (ideation state)
]


def _phase_for(item_code: BJRItemCode) -> str:
    """Map BJRItemCode to its phase string."""
    code = item_code.value
    if code.startswith("PD-"):
        return ChecklistPhase.PRE_DECISION.value
    if code.startswith("D-"):
        return ChecklistPhase.DECISION.value
    return ChecklistPhase.POST_DECISION.value


def _checklist_for_decision_1() -> list[dict]:
    """Mixed statuses — flagged CRITICAL item for 'what's missing' demo."""
    return [
        (
            BJRItemCode.PD_01_DD,
            ChecklistItemStatus.SATISFIED,
            [{"type": "dd_report", "id": str(EV_DD_1)}],
        ),
        (
            BJRItemCode.PD_02_FS,
            ChecklistItemStatus.IN_PROGRESS,
            [{"type": "fs_report", "id": str(EV_FS_1)}],
        ),
        (BJRItemCode.PD_03_RKAB, ChecklistItemStatus.FLAGGED, []),  # CRITICAL — blocks Gate 5
        (BJRItemCode.PD_04_RJPP, ChecklistItemStatus.SATISFIED, []),
        (BJRItemCode.PD_05_COI, ChecklistItemStatus.NOT_STARTED, []),
        (
            BJRItemCode.D_06_QUORUM,
            ChecklistItemStatus.SATISFIED,
            [{"type": "mom", "id": str(EV_MOM_1)}],
        ),
        (
            BJRItemCode.D_07_SIGNED,
            ChecklistItemStatus.SATISFIED,
            [{"type": "mom", "id": str(EV_MOM_1)}],
        ),
        (BJRItemCode.D_08_RISK, ChecklistItemStatus.IN_PROGRESS, []),
        (BJRItemCode.D_09_LEGAL, ChecklistItemStatus.NOT_STARTED, []),
        (BJRItemCode.D_10_ORGAN, ChecklistItemStatus.NOT_STARTED, []),
        (BJRItemCode.D_11_DISCLOSE, ChecklistItemStatus.NOT_STARTED, []),
        (BJRItemCode.POST_12_MONITOR, ChecklistItemStatus.NOT_STARTED, []),
        (BJRItemCode.POST_13_SPI, ChecklistItemStatus.NOT_STARTED, []),
        (BJRItemCode.POST_14_AUDITCOM, ChecklistItemStatus.NOT_STARTED, []),
        (BJRItemCode.POST_15_DEWAS, ChecklistItemStatus.NOT_STARTED, []),
        (BJRItemCode.POST_16_ARCHIVE, ChecklistItemStatus.NOT_STARTED, []),
    ]


def _checklist_for_decision_2() -> list[dict]:
    """All 16 items satisfied or waived — Gate 5 locked state."""
    return [
        (
            BJRItemCode.PD_01_DD,
            ChecklistItemStatus.SATISFIED,
            [{"type": "dd_report", "id": str(EV_DD_2)}],
        ),
        (
            BJRItemCode.PD_02_FS,
            ChecklistItemStatus.SATISFIED,
            [{"type": "fs_report", "id": str(EV_FS_2)}],
        ),
        (BJRItemCode.PD_03_RKAB, ChecklistItemStatus.SATISFIED, []),
        (BJRItemCode.PD_04_RJPP, ChecklistItemStatus.SATISFIED, []),
        (BJRItemCode.PD_05_COI, ChecklistItemStatus.SATISFIED, []),
        (
            BJRItemCode.D_06_QUORUM,
            ChecklistItemStatus.SATISFIED,
            [{"type": "mom", "id": str(EV_MOM_2)}],
        ),
        (
            BJRItemCode.D_07_SIGNED,
            ChecklistItemStatus.SATISFIED,
            [{"type": "mom", "id": str(EV_MOM_2)}],
        ),
        (BJRItemCode.D_08_RISK, ChecklistItemStatus.SATISFIED, []),
        (BJRItemCode.D_09_LEGAL, ChecklistItemStatus.SATISFIED, []),
        (BJRItemCode.D_10_ORGAN, ChecklistItemStatus.SATISFIED, []),
        (
            BJRItemCode.D_11_DISCLOSE,
            ChecklistItemStatus.SATISFIED,
            [{"type": "ojk_disclosure", "id": str(EV_OJK_2)}],
        ),
        (BJRItemCode.POST_12_MONITOR, ChecklistItemStatus.SATISFIED, []),
        (BJRItemCode.POST_13_SPI, ChecklistItemStatus.SATISFIED, []),
        (BJRItemCode.POST_14_AUDITCOM, ChecklistItemStatus.SATISFIED, []),
        (BJRItemCode.POST_15_DEWAS, ChecklistItemStatus.SATISFIED, []),
        (BJRItemCode.POST_16_ARCHIVE, ChecklistItemStatus.WAIVED, []),
    ]


def _checklist_for_decision_3() -> list[dict]:
    """All 16 items not_started — fresh decision."""
    return [(item_code, ChecklistItemStatus.NOT_STARTED, []) for item_code in BJRItemCode]


_CHECKLISTS: dict[uuid.UUID, list[tuple[BJRItemCode, ChecklistItemStatus, list[dict]]]] = {
    DECISION_1_ID: _checklist_for_decision_1(),
    DECISION_2_ID: _checklist_for_decision_2(),
    DECISION_3_ID: _checklist_for_decision_3(),
}


async def seed_decisions(session: AsyncSession) -> int:
    """Upsert 3 seeded StrategicDecisions. Returns count inserted (not skipped)."""
    inserted = 0
    for spec in _DECISIONS:
        existing = await session.get(StrategicDecision, spec["id"])
        if existing is not None:
            continue
        session.add(StrategicDecision(**spec))
        inserted += 1
    await session.flush()
    logger.info("Decisions: %d inserted, %d already present", inserted, len(_DECISIONS) - inserted)
    return inserted


async def seed_evidence(session: AsyncSession) -> int:
    """Upsert seeded DecisionEvidenceRecord rows. Skips existing (decision, type, id, relationship)."""
    inserted = 0
    for spec in _EVIDENCE:
        result = await session.execute(
            select(DecisionEvidenceRecord).where(
                DecisionEvidenceRecord.decision_id == spec["decision_id"],
                DecisionEvidenceRecord.evidence_type == spec["evidence_type"],
                DecisionEvidenceRecord.evidence_id == spec["evidence_id"],
                DecisionEvidenceRecord.relationship_type == spec["relationship_type"],
            )
        )
        if result.scalar_one_or_none() is not None:
            continue
        session.add(DecisionEvidenceRecord(**spec, created_by=_SYS))
        inserted += 1
    await session.flush()
    logger.info(
        "Evidence rows: %d inserted, %d already present", inserted, len(_EVIDENCE) - inserted
    )
    return inserted


async def seed_checklist(session: AsyncSession) -> int:
    """Upsert seeded BJRChecklistItemRecord rows. Skips existing (decision, item_code)."""
    inserted = 0
    total = 0
    for decision_id, items in _CHECKLISTS.items():
        for item_code, status, evidence_refs in items:
            total += 1
            result = await session.execute(
                select(BJRChecklistItemRecord).where(
                    BJRChecklistItemRecord.decision_id == decision_id,
                    BJRChecklistItemRecord.item_code == item_code.value,
                )
            )
            if result.scalar_one_or_none() is not None:
                continue
            session.add(
                BJRChecklistItemRecord(
                    decision_id=decision_id,
                    phase=_phase_for(item_code),
                    item_code=item_code.value,
                    status=status.value,
                    evidence_refs=evidence_refs or None,
                )
            )
            inserted += 1
    await session.flush()
    logger.info("Checklist rows: %d inserted, %d already present", inserted, total - inserted)
    return inserted


async def seed_all(session: AsyncSession) -> dict[str, int]:
    """Run the full seed: decisions → evidence → checklist. Return stats."""
    decisions = await seed_decisions(session)
    evidence = await seed_evidence(session)
    checklist = await seed_checklist(session)
    return {"decisions": decisions, "evidence": evidence, "checklist": checklist}


async def main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo BJR decisions + evidence + checklist.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be inserted without committing.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.dry_run:
        logger.info(
            "DRY RUN — would upsert %d decisions, %d evidence rows, %d checklist rows total",
            len(_DECISIONS),
            len(_EVIDENCE),
            sum(len(items) for items in _CHECKLISTS.values()),
        )
        for spec in _DECISIONS:
            logger.info(
                "  %s — '%s' (status=%s, readiness=%s)",
                spec["id"],
                spec["title"],
                spec["status"],
                spec.get("bjr_readiness_score"),
            )
        return 0

    try:
        async with get_session() as session:
            stats = await seed_all(session)
            logger.info("Seed complete: %s", stats)
            logger.info(
                "Next step: run the graph backfill to populate Neo4j — "
                "python3 scripts/bjr_graph_backfill.py"
            )
    finally:
        await dispose_engine()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
