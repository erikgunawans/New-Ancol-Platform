"""BJR-specific graph data models.

Kept separate from `graph_client.py` so the abstract interface stays tight.
These are lightweight dataclasses — the full data lives in Postgres; the
graph only carries references and relationship metadata.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from ancol_common.schemas.bjr import BJRItemCode


class Gate5Half(StrEnum):
    KOMISARIS = "komisaris"
    LEGAL = "legal"


@dataclass(frozen=True)
class DecisionNode:
    """Vertex representing a StrategicDecision in the knowledge graph."""

    id: uuid.UUID
    title: str
    status: str  # DecisionStatus enum value
    readiness_score: float | None
    corporate_score: float | None
    regional_score: float | None
    locked_at: datetime | None
    initiative_type: str
    origin: str  # "proactive" | "retroactive"
    created_at: datetime | None = None

    @property
    def is_locked(self) -> bool:
        return self.locked_at is not None


@dataclass(frozen=True)
class EvidenceNode:
    """Thin vertex representing an evidence artifact.

    The graph only carries the id + polymorphic type; full payload lives in
    Postgres tables (mom, contract, rkab_line_items, due_diligence_reports, etc.).
    """

    id: uuid.UUID
    type: str  # EvidenceType enum value

    def __post_init__(self) -> None:
        if not self.type:
            raise ValueError("EvidenceNode.type must be non-empty")


@dataclass(frozen=True)
class ChecklistItemNode:
    """One of the 16 BJRItemCode nodes.

    These are global singletons in the graph — created once at backfill and
    never modified. Evidence → ChecklistItem edges carry the per-decision
    semantics (see SATISFIES_ITEM edge in graph_client).
    """

    code: str  # BJRItemCode enum value


@dataclass(frozen=True)
class DocumentIndicator:
    """Per-decision BJR status for a single document.

    Returned by `GraphClient.get_document_indicators()`. Rendered in chat as
    the "indicator on support documents" feature (spec § 5.2).
    """

    decision_id: uuid.UUID
    decision_title: str
    status: str
    readiness_score: float | None
    is_locked: bool
    locked_at: datetime | None
    satisfied_items: list[BJRItemCode]
    missing_items: list[BJRItemCode]
    origin: str

    @property
    def state_emoji(self) -> str:
        if self.is_locked:
            return "🔒"
        if self.readiness_score is None:
            return "⚪"
        if self.readiness_score >= 85.0:
            return "🟢"
        return "🟡"


@dataclass(frozen=True)
class EvidenceSummary:
    """Per-evidence summary with the checklist items it satisfies for a decision.

    Returned by `GraphClient.get_decision_evidence()` (reverse of
    `get_document_indicators`).
    """

    evidence_id: uuid.UUID
    evidence_type: str
    title: str
    satisfies_items: list[BJRItemCode] = field(default_factory=list)


@dataclass(frozen=True)
class ApprovedByEdge:
    """Edge metadata for Decision -[APPROVED_BY]-> User."""

    decision_id: uuid.UUID
    user_id: uuid.UUID
    half: Gate5Half
    approved_at: datetime
