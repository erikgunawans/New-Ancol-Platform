# BJR Gemini-Primary Phase 6.4a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship BJR chat read-only tooling + graph extensions so Gemini Enterprise chat can surface any BJR decision and render BJR indicators on every supporting document. Establish the prerequisites for Phases 6.4b (chat mutations) and 6.4c (step-up web).

**Architecture:** Relocate `GraphClient` from `services/gemini-agent/` to `packages/ancol-common/` so API Gateway can also use it. Extend `GraphClient` with a `Decision` node + 5 new edge types to model BJR evidence relationships. Add 4 read-only chat tool handlers in gemini-agent (`bjr_decisions`, `bjr_readiness`, `bjr_evidence`, `bjr_passport`) that proxy to existing v0.4.0.0 API Gateway routes. Add one new API Gateway endpoint, `GET /api/documents/{id}/bjr-indicators`, that backs the per-document indicator feature via graph traversal. No DB migrations in this phase (migration 006 is Phase 6.4c).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Neo4j 5.15 (`neo4j` driver), Spanner Graph (`google-cloud-spanner`), httpx (existing api_client), pytest (async), ruff.

**Spec:** [docs/superpowers/specs/2026-04-17-bjr-gemini-enterprise-primary-design.md](../specs/2026-04-17-bjr-gemini-enterprise-primary-design.md) §§ 4.1, 4.6, 5.2, 5.3, 9 (Phase 6.4a).

**Out of scope for this plan:** chat mutations (Phase 6.4b), step-up web + MFA JWT `jti` claim (Phase 6.4c), Pub/Sub wiring (Phase 6.5), historical migration (Phase 6.5), `services/bjr-agent/` extraction (Phase 6.6).

---

## File Structure

### New files (this phase only)

| Path | Responsibility |
|---|---|
| `packages/ancol-common/src/ancol_common/rag/__init__.py` | Re-exports from relocated RAG package |
| `packages/ancol-common/src/ancol_common/rag/graph_client.py` | **MOVED from** `services/gemini-agent/src/gemini_agent/rag/graph_client.py`. Abstract `GraphClient` + data models. Extended with 6 new BJR methods. |
| `packages/ancol-common/src/ancol_common/rag/spanner_graph.py` | **MOVED from** `services/gemini-agent/src/gemini_agent/rag/spanner_graph.py`. `SpannerGraphClient` impl. Extended with 6 new BJR methods. |
| `packages/ancol-common/src/ancol_common/rag/neo4j_graph.py` | **MOVED from** `services/gemini-agent/src/gemini_agent/rag/neo4j_graph.py`. `Neo4jGraphClient` impl. Extended with 6 new BJR methods. |
| `packages/ancol-common/src/ancol_common/rag/models.py` | **NEW** BJR-specific data model dataclasses (`DecisionNode`, `EvidenceNode`, `ChecklistItemNode`, `DocumentIndicator`, `EvidenceSummary`, `Gate5Half`). Keeps `graph_client.py` tight. |
| `packages/ancol-common/tests/test_graph_client_bjr.py` | **NEW** unit tests for the 6 new methods (Neo4j + Spanner parity). |
| `services/api-gateway/src/api_gateway/routers/documents.py` | **MODIFIED** — add `GET /api/documents/{id}/bjr-indicators`. |
| `services/api-gateway/tests/test_documents_bjr_indicators.py` | **NEW** integration tests for the new endpoint. |
| `services/gemini-agent/src/gemini_agent/tools/bjr_decisions.py` | **NEW** read-only BJR decision tool handlers. |
| `services/gemini-agent/src/gemini_agent/tools/bjr_readiness.py` | **NEW** readiness score + checklist tool handlers. |
| `services/gemini-agent/src/gemini_agent/tools/bjr_evidence.py` | **NEW** `show_document_indicators` + `show_decision_evidence`. |
| `services/gemini-agent/src/gemini_agent/tools/bjr_passport.py` | **NEW** `get_passport_url`. |
| `services/gemini-agent/src/gemini_agent/formatting_bjr.py` | **NEW** markdown/card formatters for BJR chat output with moderate PII scrubbing (`format_readiness_card`, `format_document_indicator`, `format_checklist_summary`, etc.). |
| `services/gemini-agent/tests/test_tools_bjr_decisions.py` | **NEW** |
| `services/gemini-agent/tests/test_tools_bjr_readiness.py` | **NEW** |
| `services/gemini-agent/tests/test_tools_bjr_evidence.py` | **NEW** |
| `services/gemini-agent/tests/test_tools_bjr_passport.py` | **NEW** |
| `services/gemini-agent/tests/test_formatting_bjr.py` | **NEW** formatter + PII scrubbing tests. |
| `scripts/bjr_graph_backfill.py` | **NEW** idempotent graph backfill from PG (`strategic_decisions`, `decision_evidence`, `bjr_checklist_items`). |
| `scripts/tests/test_bjr_graph_backfill.py` | **NEW** dry-run + idempotency tests (in-memory fake GraphClient). |
| `docs/RUNBOOK-agent-builder-region-verification.md` | **NEW** step-by-step procedure for the region-pinning blocker gate. |

### Modified files

| Path | Change |
|---|---|
| `services/gemini-agent/src/gemini_agent/rag/__init__.py` | Replace with re-export from `ancol_common.rag`. |
| `services/gemini-agent/src/gemini_agent/rag/graph_client.py` | Delete (moved). |
| `services/gemini-agent/src/gemini_agent/rag/spanner_graph.py` | Delete (moved). |
| `services/gemini-agent/src/gemini_agent/rag/neo4j_graph.py` | Delete (moved). |
| `services/gemini-agent/src/gemini_agent/rag/orchestrator.py` | Update imports: `from gemini_agent.rag.graph_client` → `from ancol_common.rag.graph_client`. Behavior unchanged. |
| `services/gemini-agent/src/gemini_agent/rag/contract_rag.py` | Same import update. |
| `services/gemini-agent/src/gemini_agent/main.py` | Dispatcher: +14 BJR tool name mappings. RBAC: extend each role's `allowed` set per spec § 4.2. |
| `services/gemini-agent/src/gemini_agent/api_client.py` | Add 6 new typed methods: `get_decision`, `list_decisions`, `get_readiness`, `get_checklist`, `get_bjr_indicators`, `get_passport_url`. |
| `services/gemini-agent/src/gemini_agent/formatting.py` | No changes — BJR formatters live in `formatting_bjr.py`. |
| `services/api-gateway/src/api_gateway/main.py` | No changes (router already registered). |

### Existing files read but not modified

- `packages/ancol-common/src/ancol_common/auth/rbac.py` — `require_permission` + permission matrix
- `packages/ancol-common/src/ancol_common/db/models.py` — read `StrategicDecision`, `BJRChecklistItem`, `DecisionEvidenceRecord` schemas
- `packages/ancol-common/src/ancol_common/schemas/bjr.py` — read `BJRItemCode` enum
- `packages/ancol-common/src/ancol_common/schemas/decision.py` — read `DecisionStatus` enum
- `services/api-gateway/src/api_gateway/routers/decisions.py` — existing BJR routes that chat tools wrap
- `services/gemini-agent/src/gemini_agent/tools/reports.py` — pattern reference for handler structure

### Regression gate

All existing 543 tests across 9 services must pass unchanged at every task boundary.

---

## Task 1: Relocate RAG package to `packages/ancol-common`

**Why:** `GraphClient` currently lives in `services/gemini-agent/src/gemini_agent/rag/`. API Gateway can't import it from there. Moving it to the shared `packages/ancol-common/` is a prerequisite for the `/api/documents/{id}/bjr-indicators` endpoint (Task 6) and avoids duplication.

**Files:**
- Move: `services/gemini-agent/src/gemini_agent/rag/graph_client.py` → `packages/ancol-common/src/ancol_common/rag/graph_client.py`
- Move: `services/gemini-agent/src/gemini_agent/rag/spanner_graph.py` → `packages/ancol-common/src/ancol_common/rag/spanner_graph.py`
- Move: `services/gemini-agent/src/gemini_agent/rag/neo4j_graph.py` → `packages/ancol-common/src/ancol_common/rag/neo4j_graph.py`
- Create: `packages/ancol-common/src/ancol_common/rag/__init__.py`
- Modify: `services/gemini-agent/src/gemini_agent/rag/__init__.py` (re-export shim)
- Modify: `services/gemini-agent/src/gemini_agent/rag/orchestrator.py` (import update)
- Modify: `services/gemini-agent/src/gemini_agent/rag/contract_rag.py` (import update)

- [ ] **Step 1: Verify baseline — existing gemini-agent tests pass**

Run:
```bash
PYTHONPATH=packages/ancol-common/src:services/gemini-agent/src python3 -m pytest services/gemini-agent/tests/ -q
```
Expected: all 61 tests pass. Record this as the baseline.

- [ ] **Step 2: Create the new rag package in ancol-common**

```bash
mkdir -p packages/ancol-common/src/ancol_common/rag
```

Create `packages/ancol-common/src/ancol_common/rag/__init__.py`:
```python
"""Knowledge graph abstraction shared by gemini-agent and api-gateway.

Re-exports the public `GraphClient` interface + implementations so
consumers don't have to reach into submodule paths.
"""

from __future__ import annotations

from ancol_common.rag.graph_client import (
    AmendmentEdge,
    ClauseNode,
    ContractNode,
    CrossReference,
    GraphClient,
    RegulationNode,
)

__all__ = [
    "GraphClient",
    "RegulationNode",
    "ClauseNode",
    "AmendmentEdge",
    "CrossReference",
    "ContractNode",
]
```

- [ ] **Step 3: Move `graph_client.py`**

```bash
git mv services/gemini-agent/src/gemini_agent/rag/graph_client.py packages/ancol-common/src/ancol_common/rag/graph_client.py
```

Edit the moved file: no content changes yet (imports are all stdlib + dataclasses).

- [ ] **Step 4: Move `spanner_graph.py` and `neo4j_graph.py`**

```bash
git mv services/gemini-agent/src/gemini_agent/rag/spanner_graph.py packages/ancol-common/src/ancol_common/rag/spanner_graph.py
git mv services/gemini-agent/src/gemini_agent/rag/neo4j_graph.py packages/ancol-common/src/ancol_common/rag/neo4j_graph.py
```

Update imports in each moved file. Replace `from gemini_agent.rag.graph_client import` with `from ancol_common.rag.graph_client import`.

Use Grep to find and fix:
```bash
```

Run:
```bash
grep -n "from gemini_agent.rag" packages/ancol-common/src/ancol_common/rag/*.py
```
Expected: no matches (all updated).

- [ ] **Step 5: Update gemini-agent's rag/__init__.py to re-export from ancol-common**

Replace `services/gemini-agent/src/gemini_agent/rag/__init__.py` content:
```python
"""gemini-agent RAG package.

GraphClient moved to ancol_common.rag in Phase 6.4a. This module
re-exports for backward-compatible imports within gemini-agent.
"""

from __future__ import annotations

from ancol_common.rag import (
    AmendmentEdge,
    ClauseNode,
    ContractNode,
    CrossReference,
    GraphClient,
    RegulationNode,
)
from gemini_agent.rag.contract_rag import ContractRAG
from gemini_agent.rag.orchestrator import RAGOrchestrator

__all__ = [
    "GraphClient",
    "RegulationNode",
    "ClauseNode",
    "AmendmentEdge",
    "CrossReference",
    "ContractNode",
    "ContractRAG",
    "RAGOrchestrator",
]
```

- [ ] **Step 6: Update orchestrator.py and contract_rag.py imports**

In `services/gemini-agent/src/gemini_agent/rag/orchestrator.py` and `services/gemini-agent/src/gemini_agent/rag/contract_rag.py`, replace:
- `from gemini_agent.rag.graph_client` → `from ancol_common.rag.graph_client`
- `from gemini_agent.rag.spanner_graph` → `from ancol_common.rag.spanner_graph`
- `from gemini_agent.rag.neo4j_graph` → `from ancol_common.rag.neo4j_graph`

Verify:
```bash
grep -rn "from gemini_agent.rag.graph_client\|from gemini_agent.rag.spanner_graph\|from gemini_agent.rag.neo4j_graph" services/gemini-agent/src/
```
Expected: no matches (orchestrator.py and contract_rag.py both updated).

- [ ] **Step 7: Run gemini-agent tests to confirm no regression**

Run:
```bash
PYTHONPATH=packages/ancol-common/src:services/gemini-agent/src python3 -m pytest services/gemini-agent/tests/ -q
```
Expected: all 61 tests pass (identical to baseline from Step 1).

- [ ] **Step 8: Run ancol-common package smoke test**

Run:
```bash
PYTHONPATH=packages/ancol-common/src python3 -c "from ancol_common.rag import GraphClient, RegulationNode; print('rag package imports OK')"
```
Expected: `rag package imports OK`.

- [ ] **Step 9: Commit the relocation**

```bash
git add packages/ancol-common/src/ancol_common/rag/ services/gemini-agent/src/gemini_agent/rag/
git commit -m "refactor: relocate rag/ package from gemini-agent to ancol-common

GraphClient + SpannerGraphClient + Neo4jGraphClient moved to the shared
ancol-common package so API Gateway can also import the abstraction.

gemini-agent's rag/__init__.py now re-exports from ancol_common.rag for
backward-compat. Zero behavior change; all 61 gemini-agent tests green."
```

---

## Task 2: Add BJR-specific graph data models

**Why:** `DecisionNode`, `EvidenceNode`, `DocumentIndicator`, etc. don't belong in `graph_client.py` (which should stay compact for the interface). Put them in a new `models.py` module.

**Files:**
- Create: `packages/ancol-common/src/ancol_common/rag/models.py`
- Create: `packages/ancol-common/tests/test_rag_models.py`

- [ ] **Step 1: Write failing test for the data models**

Create `packages/ancol-common/tests/test_rag_models.py`:
```python
"""Tests for BJR-specific graph data models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from ancol_common.rag.models import (
    DecisionNode,
    DocumentIndicator,
    EvidenceNode,
    EvidenceSummary,
    Gate5Half,
)
from ancol_common.schemas.bjr import BJRItemCode
from ancol_common.schemas.decision import DecisionStatus


def test_decision_node_required_fields() -> None:
    node = DecisionNode(
        id=uuid.uuid4(),
        title="Divestasi Hotel Jaya",
        status=DecisionStatus.BJR_LOCKED.value,
        readiness_score=94.0,
        corporate_score=94.0,
        regional_score=96.0,
        locked_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        initiative_type="divestment",
        origin="proactive",
    )
    assert node.is_locked is True


def test_decision_node_unlocked_state() -> None:
    node = DecisionNode(
        id=uuid.uuid4(),
        title="Akuisisi X",
        status=DecisionStatus.DD_IN_PROGRESS.value,
        readiness_score=None,
        corporate_score=None,
        regional_score=None,
        locked_at=None,
        initiative_type="acquisition",
        origin="proactive",
    )
    assert node.is_locked is False


def test_evidence_node_valid_type() -> None:
    node = EvidenceNode(id=uuid.uuid4(), type="mom")
    assert node.type == "mom"


def test_evidence_node_rejects_empty_type() -> None:
    with pytest.raises(ValueError, match="type"):
        EvidenceNode(id=uuid.uuid4(), type="")


def test_document_indicator_items() -> None:
    decision_id = uuid.uuid4()
    indicator = DocumentIndicator(
        decision_id=decision_id,
        decision_title="Acquisition X",
        status=DecisionStatus.DD_IN_PROGRESS.value,
        readiness_score=72.0,
        is_locked=False,
        locked_at=None,
        satisfied_items=[BJRItemCode.D_06_QUORUM],
        missing_items=[BJRItemCode.PD_01_DD, BJRItemCode.PD_05_COI],
        origin="proactive",
    )
    assert len(indicator.satisfied_items) == 1
    assert len(indicator.missing_items) == 2
    # Emoji state helper
    assert indicator.state_emoji == "🟡"


def test_document_indicator_locked_emoji() -> None:
    indicator = DocumentIndicator(
        decision_id=uuid.uuid4(),
        decision_title="Locked decision",
        status=DecisionStatus.BJR_LOCKED.value,
        readiness_score=95.0,
        is_locked=True,
        locked_at=datetime.now(timezone.utc),
        satisfied_items=[],
        missing_items=[],
        origin="proactive",
    )
    assert indicator.state_emoji == "🔒"


def test_evidence_summary_groups_by_item() -> None:
    ev_id = uuid.uuid4()
    summary = EvidenceSummary(
        evidence_id=ev_id,
        evidence_type="mom",
        title="MoM BOD #5/2026",
        satisfies_items=[BJRItemCode.D_06_QUORUM, BJRItemCode.D_07_SIGNED],
    )
    assert BJRItemCode.D_06_QUORUM in summary.satisfies_items


def test_gate5_half_values() -> None:
    assert Gate5Half.KOMISARIS == "komisaris"
    assert Gate5Half.LEGAL == "legal"
```

- [ ] **Step 2: Run the test to verify failure**

Run:
```bash
PYTHONPATH=packages/ancol-common/src python3 -m pytest packages/ancol-common/tests/test_rag_models.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'ancol_common.rag.models'`.

- [ ] **Step 3: Implement `models.py`**

Create `packages/ancol-common/src/ancol_common/rag/models.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify pass**

Run:
```bash
PYTHONPATH=packages/ancol-common/src python3 -m pytest packages/ancol-common/tests/test_rag_models.py -v
```
Expected: 7 PASS.

- [ ] **Step 5: Lint**

Run:
```bash
ruff check packages/ancol-common/src/ancol_common/rag/models.py packages/ancol-common/tests/test_rag_models.py
ruff format packages/ancol-common/src/ancol_common/rag/models.py packages/ancol-common/tests/test_rag_models.py
```
Expected: no errors, no formatting changes after format.

- [ ] **Step 6: Commit**

```bash
git add packages/ancol-common/src/ancol_common/rag/models.py packages/ancol-common/tests/test_rag_models.py
git commit -m "feat(rag): add BJR graph data models (DecisionNode, EvidenceNode, DocumentIndicator)

Lightweight dataclasses for the Decision + 5 edge types added in this
phase. Kept in a separate models.py so graph_client.py stays focused
on the abstract interface."
```

---

## Task 3: Extend `GraphClient` abstract interface with 6 new BJR methods

**Why:** The new graph shape in spec § 4.6 needs an abstract contract before any implementation. Both Neo4j and Spanner impls must satisfy the same interface (existing invariant — `GRAPH_BACKEND` env var is swappable).

**Files:**
- Modify: `packages/ancol-common/src/ancol_common/rag/graph_client.py`
- Modify: `packages/ancol-common/tests/test_rag_models.py` (optional, add interface smoke test)

- [ ] **Step 1: Write a failing interface test**

Create `packages/ancol-common/tests/test_graph_client_interface.py`:
```python
"""Abstract interface guard — ensures every GraphClient impl has the 6 new BJR methods."""

from __future__ import annotations

import inspect

from ancol_common.rag.graph_client import GraphClient


def test_graph_client_has_bjr_methods() -> None:
    """The 6 new BJR methods must exist and be abstract."""
    required = {
        "upsert_decision_node",
        "upsert_supported_by_edge",
        "upsert_satisfies_item_edge",
        "upsert_approved_by_edge",
        "get_document_indicators",
        "get_decision_evidence",
    }
    abstract = GraphClient.__abstractmethods__
    missing = required - abstract
    assert not missing, f"GraphClient missing abstract methods: {missing}"


def test_graph_client_method_signatures() -> None:
    """Signatures must match the spec § 4.6 so implementations align."""
    sig_get_indicators = inspect.signature(GraphClient.get_document_indicators)
    params = list(sig_get_indicators.parameters.keys())
    assert params == ["self", "doc_id", "doc_type"], params

    sig_get_evidence = inspect.signature(GraphClient.get_decision_evidence)
    params = list(sig_get_evidence.parameters.keys())
    assert params == ["self", "decision_id"], params
```

- [ ] **Step 2: Run test to verify failure**

Run:
```bash
PYTHONPATH=packages/ancol-common/src python3 -m pytest packages/ancol-common/tests/test_graph_client_interface.py -v
```
Expected: FAIL with `AssertionError: GraphClient missing abstract methods: {...}`.

- [ ] **Step 3: Extend `GraphClient` abstract with 6 new methods**

Open `packages/ancol-common/src/ancol_common/rag/graph_client.py` and append after the existing `get_related_contracts` method (keep the 7 existing methods unchanged):

```python
    # ── BJR extensions (added in Phase 6.4a) ──────────────────────────────
    # These back the decision-level defensibility features: per-document
    # indicators, decision evidence browsing, and Gate 5 approval audit.

    @abstractmethod
    async def upsert_decision_node(self, decision: "DecisionNode") -> None:
        """Create or update a Decision vertex.

        Idempotent: re-upserting the same decision_id updates the properties
        (status, readiness_score, locked_at) in place without duplicating.
        """

    @abstractmethod
    async def upsert_supported_by_edge(
        self,
        decision_id: "uuid.UUID",
        evidence: "EvidenceNode",
        linked_at: "datetime",
        linked_by: "uuid.UUID",
    ) -> None:
        """Create/update Decision-[SUPPORTED_BY]->Evidence edge.

        The Evidence vertex is upserted if it doesn't exist yet.
        """

    @abstractmethod
    async def upsert_satisfies_item_edge(
        self,
        evidence_id: "uuid.UUID",
        item_code: "BJRItemCode",
        decision_id: "uuid.UUID",
        evaluator_status: str,
    ) -> None:
        """Create/update Evidence-[SATISFIES_ITEM {decision_id}]->ChecklistItem edge.

        Multiple edges can exist between the same Evidence and ChecklistItem
        (one per decision) — the `decision_id` property on the edge disambiguates.
        `evaluator_status` is the current evaluator output for that item under
        that decision (satisfied|flagged|not_started).
        """

    @abstractmethod
    async def upsert_approved_by_edge(
        self,
        decision_id: "uuid.UUID",
        user_id: "uuid.UUID",
        half: "Gate5Half",
        approved_at: "datetime",
    ) -> None:
        """Create Decision-[APPROVED_BY {half, approved_at}]->User edge.

        One edge per Gate 5 half (Komisaris + Legal). Re-upserting the same
        (decision_id, half) tuple updates `approved_at` to the latest value —
        needed when Gate 5 is re-opened after a rejection and re-approved.
        """

    @abstractmethod
    async def get_document_indicators(
        self,
        doc_id: "uuid.UUID",
        doc_type: str,
    ) -> list["DocumentIndicator"]:
        """Return all BJR decisions this document supports, with per-decision status.

        One-hop query:
            MATCH (ev:Evidence {id: $doc_id})<-[:SUPPORTED_BY]-(d:Decision)
            OPTIONAL MATCH (ev)-[:SATISFIES_ITEM {decision_id: d.id}]->(item)
            RETURN d, collect(item.code) AS satisfied_items

        On connection failure, returns [] (graph is supplementary — API
        callers have a SQL fallback path).
        """

    @abstractmethod
    async def get_decision_evidence(
        self,
        decision_id: "uuid.UUID",
    ) -> list["EvidenceSummary"]:
        """Return all evidence linked to a decision, with per-evidence item codes.

        Reverse of `get_document_indicators`. Used by the chat tool
        `show_decision_evidence` to answer "what supports decision X?".
        """
```

Also add to the module imports at top of `graph_client.py`:
```python
import uuid
from datetime import datetime

from ancol_common.rag.models import (
    DecisionNode,
    DocumentIndicator,
    EvidenceNode,
    EvidenceSummary,
    Gate5Half,
)
from ancol_common.schemas.bjr import BJRItemCode
```

Remove the quotes from the abstract method signatures (use the actual imported types) once imports are in place. Example after cleanup:
```python
    @abstractmethod
    async def upsert_decision_node(self, decision: DecisionNode) -> None:
        ...
```

- [ ] **Step 4: Run test to verify pass**

Run:
```bash
PYTHONPATH=packages/ancol-common/src python3 -m pytest packages/ancol-common/tests/test_graph_client_interface.py -v
```
Expected: 2 PASS.

- [ ] **Step 5: Verify existing gemini-agent tests still pass**

The abstract additions break any concrete subclass that hasn't implemented them yet. `SpannerGraphClient` and `Neo4jGraphClient` won't yet — but we haven't instantiated them in gemini-agent tests without mocks. Confirm:

Run:
```bash
PYTHONPATH=packages/ancol-common/src:services/gemini-agent/src python3 -m pytest services/gemini-agent/tests/ -q
```
Expected: all 61 tests pass. (If any fail with `TypeError: Can't instantiate abstract class`, the impls in Task 4-5 will fix those; but gemini-agent tests use mocks, so should be green.)

- [ ] **Step 6: Lint**

```bash
ruff check packages/ancol-common/src/ancol_common/rag/graph_client.py packages/ancol-common/tests/test_graph_client_interface.py
ruff format packages/ancol-common/src/ancol_common/rag/graph_client.py packages/ancol-common/tests/test_graph_client_interface.py
```

- [ ] **Step 7: Commit**

```bash
git add packages/ancol-common/src/ancol_common/rag/graph_client.py packages/ancol-common/tests/test_graph_client_interface.py
git commit -m "feat(rag): extend GraphClient abstract with 6 BJR methods

New contract: upsert_decision_node, upsert_supported_by_edge,
upsert_satisfies_item_edge, upsert_approved_by_edge,
get_document_indicators, get_decision_evidence.

Interface-only — Neo4j and Spanner implementations follow in
Tasks 4 and 5. Abstract guard test in place."
```

---

## Task 4: Implement 6 new methods in `Neo4jGraphClient`

**Why:** Neo4j is the active backend in most dev/staging envs (per CLAUDE.md "Neo4j is fully implemented"). Ship Neo4j first because it's the path most likely exercised end-to-end in Phase 6.4a verification.

**Files:**
- Modify: `packages/ancol-common/src/ancol_common/rag/neo4j_graph.py`
- Create: `packages/ancol-common/tests/test_graph_client_bjr.py`

- [ ] **Step 1: Write failing tests for the 6 new methods (Neo4j only for now)**

Create `packages/ancol-common/tests/test_graph_client_bjr.py`:
```python
"""Unit tests for the 6 new BJR methods on GraphClient implementations.

Uses a real (embedded) Neo4j via `neo4j.unit.of.work` mock driver pattern
from the neo4j-python-driver test suite. For Spanner, we use a mock since
Spanner Graph doesn't have an embedded test harness.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from ancol_common.rag.models import (
    DecisionNode,
    DocumentIndicator,
    EvidenceNode,
    EvidenceSummary,
    Gate5Half,
)
from ancol_common.rag.neo4j_graph import Neo4jGraphClient
from ancol_common.schemas.bjr import BJRItemCode
from ancol_common.schemas.decision import DecisionStatus


def _make_client_with_mock_driver(records: list[dict]) -> Neo4jGraphClient:
    """Build a Neo4jGraphClient whose driver returns preset records."""
    client = Neo4jGraphClient(uri="bolt://dummy", user="neo4j", password="dummy")
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.data = AsyncMock(return_value=records)
    mock_session.run = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_driver = MagicMock()
    mock_driver.session = MagicMock(return_value=mock_session)
    client._driver = mock_driver  # noqa: SLF001 — test seam
    return client


@pytest.mark.asyncio
async def test_upsert_decision_node_generates_merge_cypher() -> None:
    client = _make_client_with_mock_driver([])
    now = datetime.now(timezone.utc)
    decision = DecisionNode(
        id=uuid.uuid4(),
        title="Divestasi Hotel Jaya",
        status=DecisionStatus.BJR_LOCKED.value,
        readiness_score=94.0,
        corporate_score=94.0,
        regional_score=96.0,
        locked_at=now,
        initiative_type="divestment",
        origin="proactive",
    )
    await client.upsert_decision_node(decision)

    # The call arg to session.run should be a MERGE on (d:Decision {id: $id})
    mock_session = client._driver.session.return_value
    first_call = mock_session.run.await_args_list[0]
    cypher = first_call.args[0]
    assert "MERGE (d:Decision {id:" in cypher
    assert "SET" in cypher  # properties set on match or create


@pytest.mark.asyncio
async def test_upsert_supported_by_edge_includes_metadata() -> None:
    client = _make_client_with_mock_driver([])
    decision_id = uuid.uuid4()
    ev = EvidenceNode(id=uuid.uuid4(), type="mom")
    user_id = uuid.uuid4()
    linked_at = datetime.now(timezone.utc)

    await client.upsert_supported_by_edge(
        decision_id=decision_id,
        evidence=ev,
        linked_at=linked_at,
        linked_by=user_id,
    )

    mock_session = client._driver.session.return_value
    cypher = mock_session.run.await_args_list[0].args[0]
    assert "MERGE (d)-[sb:SUPPORTED_BY]->(ev)" in cypher
    assert "sb.linked_at" in cypher
    assert "sb.linked_by" in cypher


@pytest.mark.asyncio
async def test_upsert_satisfies_item_edge_carries_decision_id() -> None:
    client = _make_client_with_mock_driver([])
    ev_id = uuid.uuid4()
    decision_id = uuid.uuid4()

    await client.upsert_satisfies_item_edge(
        evidence_id=ev_id,
        item_code=BJRItemCode.D_06_QUORUM,
        decision_id=decision_id,
        evaluator_status="satisfied",
    )

    mock_session = client._driver.session.return_value
    cypher = mock_session.run.await_args_list[0].args[0]
    # decision_id is part of the edge MATCH to disambiguate per-decision edges
    assert "SATISFIES_ITEM" in cypher
    assert "decision_id" in cypher
    params = mock_session.run.await_args_list[0].args[1] if len(mock_session.run.await_args_list[0].args) > 1 else mock_session.run.await_args_list[0].kwargs
    assert str(decision_id) in str(params)


@pytest.mark.asyncio
async def test_upsert_approved_by_edge_includes_half() -> None:
    client = _make_client_with_mock_driver([])

    await client.upsert_approved_by_edge(
        decision_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        half=Gate5Half.KOMISARIS,
        approved_at=datetime.now(timezone.utc),
    )

    mock_session = client._driver.session.return_value
    cypher = mock_session.run.await_args_list[0].args[0]
    assert "APPROVED_BY" in cypher
    assert "half" in cypher


@pytest.mark.asyncio
async def test_get_document_indicators_parses_records() -> None:
    decision_id = uuid.uuid4()
    records = [
        {
            "d_id": str(decision_id),
            "d_title": "Akuisisi Wahana",
            "d_status": DecisionStatus.DD_IN_PROGRESS.value,
            "d_readiness_score": 72.0,
            "d_locked_at": None,
            "d_origin": "proactive",
            "satisfied_items": [BJRItemCode.D_06_QUORUM.value],
        }
    ]
    client = _make_client_with_mock_driver(records)

    results = await client.get_document_indicators(
        doc_id=uuid.uuid4(),
        doc_type="mom",
    )

    assert len(results) == 1
    assert isinstance(results[0], DocumentIndicator)
    assert results[0].decision_id == decision_id
    assert results[0].is_locked is False
    assert BJRItemCode.D_06_QUORUM in results[0].satisfied_items


@pytest.mark.asyncio
async def test_get_document_indicators_handles_locked_decision() -> None:
    decision_id = uuid.uuid4()
    locked_at = datetime.now(timezone.utc)
    records = [
        {
            "d_id": str(decision_id),
            "d_title": "Divestasi Hotel Jaya",
            "d_status": DecisionStatus.BJR_LOCKED.value,
            "d_readiness_score": 94.0,
            "d_locked_at": locked_at.isoformat(),
            "d_origin": "proactive",
            "satisfied_items": [
                BJRItemCode.D_06_QUORUM.value,
                BJRItemCode.D_07_SIGNED.value,
            ],
        }
    ]
    client = _make_client_with_mock_driver(records)

    results = await client.get_document_indicators(
        doc_id=uuid.uuid4(),
        doc_type="mom",
    )

    assert len(results) == 1
    assert results[0].is_locked is True
    assert results[0].state_emoji == "🔒"
    assert len(results[0].satisfied_items) == 2


@pytest.mark.asyncio
async def test_get_decision_evidence_groups_by_evidence_id() -> None:
    ev_id = uuid.uuid4()
    records = [
        {
            "ev_id": str(ev_id),
            "ev_type": "mom",
            "ev_title": "MoM BOD #5/2026",
            "satisfies_items": [
                BJRItemCode.D_06_QUORUM.value,
                BJRItemCode.D_07_SIGNED.value,
            ],
        }
    ]
    client = _make_client_with_mock_driver(records)

    results = await client.get_decision_evidence(decision_id=uuid.uuid4())
    assert len(results) == 1
    assert isinstance(results[0], EvidenceSummary)
    assert results[0].evidence_id == ev_id
    assert len(results[0].satisfies_items) == 2


@pytest.mark.asyncio
async def test_get_document_indicators_returns_empty_on_connection_error() -> None:
    """Degradation contract: graph failures must not propagate to callers."""
    client = Neo4jGraphClient(uri="bolt://dummy", user="neo4j", password="dummy")
    failing_session = AsyncMock()
    failing_session.run = AsyncMock(side_effect=ConnectionError("bolt unreachable"))
    failing_session.__aenter__ = AsyncMock(return_value=failing_session)
    failing_session.__aexit__ = AsyncMock(return_value=None)
    client._driver = MagicMock()
    client._driver.session = MagicMock(return_value=failing_session)

    results = await client.get_document_indicators(
        doc_id=uuid.uuid4(),
        doc_type="mom",
    )
    assert results == []
```

- [ ] **Step 2: Run the test to verify failure**

Run:
```bash
PYTHONPATH=packages/ancol-common/src python3 -m pytest packages/ancol-common/tests/test_graph_client_bjr.py -v
```
Expected: 8 FAIL — methods don't exist on `Neo4jGraphClient` yet.

- [ ] **Step 3: Implement the 6 methods in `Neo4jGraphClient`**

Open `packages/ancol-common/src/ancol_common/rag/neo4j_graph.py`. Add the following methods to the class (place them after the existing `get_related_contracts` method):

```python
    # ── BJR extensions (Phase 6.4a) ───────────────────────────────────────

    async def upsert_decision_node(self, decision: DecisionNode) -> None:
        """Create or update a Decision vertex."""
        cypher = """
        MERGE (d:Decision {id: $id})
        SET d.title = $title,
            d.status = $status,
            d.readiness_score = $readiness_score,
            d.corporate_score = $corporate_score,
            d.regional_score = $regional_score,
            d.locked_at = $locked_at,
            d.initiative_type = $initiative_type,
            d.origin = $origin
        """
        params = {
            "id": str(decision.id),
            "title": decision.title,
            "status": decision.status,
            "readiness_score": decision.readiness_score,
            "corporate_score": decision.corporate_score,
            "regional_score": decision.regional_score,
            "locked_at": decision.locked_at.isoformat() if decision.locked_at else None,
            "initiative_type": decision.initiative_type,
            "origin": decision.origin,
        }
        try:
            async with self._driver.session() as session:
                await session.run(cypher, params)
        except Exception:
            logger.exception("upsert_decision_node failed for %s", decision.id)

    async def upsert_supported_by_edge(
        self,
        decision_id: uuid.UUID,
        evidence: EvidenceNode,
        linked_at: datetime,
        linked_by: uuid.UUID,
    ) -> None:
        """Create/update Decision-[SUPPORTED_BY]->Evidence edge."""
        cypher = """
        MATCH (d:Decision {id: $decision_id})
        MERGE (ev:Evidence {id: $evidence_id, type: $evidence_type})
        MERGE (d)-[sb:SUPPORTED_BY]->(ev)
        SET sb.linked_at = $linked_at,
            sb.linked_by = $linked_by
        """
        params = {
            "decision_id": str(decision_id),
            "evidence_id": str(evidence.id),
            "evidence_type": evidence.type,
            "linked_at": linked_at.isoformat(),
            "linked_by": str(linked_by),
        }
        try:
            async with self._driver.session() as session:
                await session.run(cypher, params)
        except Exception:
            logger.exception("upsert_supported_by_edge failed %s→%s", decision_id, evidence.id)

    async def upsert_satisfies_item_edge(
        self,
        evidence_id: uuid.UUID,
        item_code: BJRItemCode,
        decision_id: uuid.UUID,
        evaluator_status: str,
    ) -> None:
        """Create/update Evidence-[SATISFIES_ITEM {decision_id}]->ChecklistItem edge.

        Multiple edges may exist between the same (evidence, item) — one per
        decision. The decision_id property on the edge disambiguates, so we
        MATCH on that key.
        """
        cypher = """
        MATCH (ev:Evidence {id: $evidence_id})
        MERGE (item:ChecklistItem {code: $item_code})
        MERGE (ev)-[si:SATISFIES_ITEM {decision_id: $decision_id}]->(item)
        SET si.evaluator_status = $evaluator_status
        """
        params = {
            "evidence_id": str(evidence_id),
            "item_code": item_code.value,
            "decision_id": str(decision_id),
            "evaluator_status": evaluator_status,
        }
        try:
            async with self._driver.session() as session:
                await session.run(cypher, params)
        except Exception:
            logger.exception(
                "upsert_satisfies_item_edge failed %s→%s for decision %s",
                evidence_id, item_code.value, decision_id,
            )

    async def upsert_approved_by_edge(
        self,
        decision_id: uuid.UUID,
        user_id: uuid.UUID,
        half: Gate5Half,
        approved_at: datetime,
    ) -> None:
        """Create Decision-[APPROVED_BY {half, approved_at}]->User edge.

        Keyed on (decision_id, half) so re-approving a half (after rejection)
        updates approved_at in place rather than adding a duplicate edge.
        """
        cypher = """
        MATCH (d:Decision {id: $decision_id})
        MERGE (u:User {id: $user_id})
        MERGE (d)-[ab:APPROVED_BY {half: $half}]->(u)
        SET ab.approved_at = $approved_at
        """
        params = {
            "decision_id": str(decision_id),
            "user_id": str(user_id),
            "half": half.value,
            "approved_at": approved_at.isoformat(),
        }
        try:
            async with self._driver.session() as session:
                await session.run(cypher, params)
        except Exception:
            logger.exception("upsert_approved_by_edge failed %s/%s", decision_id, half)

    async def get_document_indicators(
        self,
        doc_id: uuid.UUID,
        doc_type: str,
    ) -> list[DocumentIndicator]:
        """Return all decisions this doc supports + per-decision checklist coverage."""
        cypher = """
        MATCH (ev:Evidence {id: $doc_id})
        MATCH (ev)<-[:SUPPORTED_BY]-(d:Decision)
        OPTIONAL MATCH (ev)-[si:SATISFIES_ITEM {decision_id: d.id}]->(item:ChecklistItem)
        WITH d, collect(DISTINCT item.code) AS satisfied_items
        RETURN d.id AS d_id, d.title AS d_title, d.status AS d_status,
               d.readiness_score AS d_readiness_score,
               d.locked_at AS d_locked_at, d.origin AS d_origin,
               satisfied_items
        """
        try:
            async with self._driver.session() as session:
                result = await session.run(cypher, {"doc_id": str(doc_id)})
                records = await result.data()
        except Exception:
            logger.exception("get_document_indicators failed for %s/%s", doc_id, doc_type)
            return []

        out: list[DocumentIndicator] = []
        for rec in records:
            satisfied = [BJRItemCode(c) for c in (rec["satisfied_items"] or []) if c]
            # Missing items inferred from 16 - satisfied
            all_items = set(BJRItemCode)
            missing = sorted(all_items - set(satisfied), key=lambda c: c.value)
            locked_at_raw = rec.get("d_locked_at")
            locked_at = datetime.fromisoformat(locked_at_raw) if locked_at_raw else None
            out.append(
                DocumentIndicator(
                    decision_id=uuid.UUID(rec["d_id"]),
                    decision_title=rec["d_title"],
                    status=rec["d_status"],
                    readiness_score=rec.get("d_readiness_score"),
                    is_locked=locked_at is not None,
                    locked_at=locked_at,
                    satisfied_items=satisfied,
                    missing_items=missing,
                    origin=rec.get("d_origin", "proactive"),
                )
            )
        return out

    async def get_decision_evidence(
        self,
        decision_id: uuid.UUID,
    ) -> list[EvidenceSummary]:
        """Return all evidence for a decision + which items each satisfies."""
        cypher = """
        MATCH (d:Decision {id: $decision_id})-[:SUPPORTED_BY]->(ev:Evidence)
        OPTIONAL MATCH (ev)-[si:SATISFIES_ITEM {decision_id: $decision_id}]->(item:ChecklistItem)
        WITH ev, collect(DISTINCT item.code) AS satisfies_items
        RETURN ev.id AS ev_id, ev.type AS ev_type,
               coalesce(ev.title, '') AS ev_title,
               satisfies_items
        """
        try:
            async with self._driver.session() as session:
                result = await session.run(cypher, {"decision_id": str(decision_id)})
                records = await result.data()
        except Exception:
            logger.exception("get_decision_evidence failed for decision %s", decision_id)
            return []

        return [
            EvidenceSummary(
                evidence_id=uuid.UUID(rec["ev_id"]),
                evidence_type=rec["ev_type"],
                title=rec["ev_title"] or f"{rec['ev_type']}:{rec['ev_id'][:8]}",
                satisfies_items=[
                    BJRItemCode(c) for c in (rec["satisfies_items"] or []) if c
                ],
            )
            for rec in records
        ]
```

Add the following imports at the top of `neo4j_graph.py` (keep existing imports):
```python
import uuid
from datetime import datetime

from ancol_common.rag.models import (
    DecisionNode,
    DocumentIndicator,
    EvidenceNode,
    EvidenceSummary,
    Gate5Half,
)
from ancol_common.schemas.bjr import BJRItemCode
```

- [ ] **Step 4: Run tests to verify pass**

Run:
```bash
PYTHONPATH=packages/ancol-common/src python3 -m pytest packages/ancol-common/tests/test_graph_client_bjr.py -v
```
Expected: 8 PASS.

- [ ] **Step 5: Run interface test + all existing gemini-agent tests**

Run:
```bash
PYTHONPATH=packages/ancol-common/src python3 -m pytest packages/ancol-common/tests/test_graph_client_interface.py -v
PYTHONPATH=packages/ancol-common/src:services/gemini-agent/src python3 -m pytest services/gemini-agent/tests/ -q
```
Expected: all PASS.

- [ ] **Step 6: Lint**

```bash
ruff check packages/ancol-common/src/ancol_common/rag/neo4j_graph.py packages/ancol-common/tests/test_graph_client_bjr.py
ruff format packages/ancol-common/src/ancol_common/rag/neo4j_graph.py packages/ancol-common/tests/test_graph_client_bjr.py
```

- [ ] **Step 7: Commit**

```bash
git add packages/ancol-common/src/ancol_common/rag/neo4j_graph.py packages/ancol-common/tests/test_graph_client_bjr.py
git commit -m "feat(rag): Neo4jGraphClient — implement 6 BJR methods

Decision upsert, 3 edge upserts (SUPPORTED_BY, SATISFIES_ITEM,
APPROVED_BY), and 2 query methods (get_document_indicators,
get_decision_evidence). Connection errors log and return [] to
preserve the 'graph is supplementary' degradation contract.

8 unit tests covering MERGE semantics, property writes, edge
keying, and connection-error degradation."
```

---

## Task 5: Implement 6 new methods in `SpannerGraphClient`

**Why:** Parity with Neo4j — `GRAPH_BACKEND=spanner` must work identically. Spanner Graph uses GQL (Google Graph Query Language), not Cypher, but the abstract contract is identical.

**Files:**
- Modify: `packages/ancol-common/src/ancol_common/rag/spanner_graph.py`
- Modify: `packages/ancol-common/tests/test_graph_client_bjr.py` (add Spanner parity block)

- [ ] **Step 1: Extend the test file with Spanner parity tests**

Append to `packages/ancol-common/tests/test_graph_client_bjr.py`:

```python
# ── Spanner parity ─────────────────────────────────────────────────────
#
# Spanner Graph runs inside Cloud Spanner; there's no embedded harness,
# so we mock the internal `_database.execute_sql` call.

from ancol_common.rag.spanner_graph import SpannerGraphClient


def _make_spanner_client_with_mock(rows: list[tuple]) -> SpannerGraphClient:
    client = SpannerGraphClient(
        project_id="test", instance_id="test", database_id="test"
    )
    mock_db = MagicMock()
    snapshot_cm = MagicMock()
    result_iter = MagicMock()
    result_iter.__iter__.return_value = iter(rows)
    snapshot_cm.__enter__ = MagicMock(return_value=MagicMock(
        execute_sql=MagicMock(return_value=result_iter)
    ))
    snapshot_cm.__exit__ = MagicMock(return_value=None)
    mock_db.snapshot = MagicMock(return_value=snapshot_cm)
    mock_db.run_in_transaction = MagicMock()
    client._database = mock_db  # noqa: SLF001
    return client


@pytest.mark.asyncio
async def test_spanner_upsert_decision_node_runs_dml() -> None:
    client = _make_spanner_client_with_mock([])
    decision = DecisionNode(
        id=uuid.uuid4(),
        title="Test",
        status=DecisionStatus.BJR_LOCKED.value,
        readiness_score=90.0,
        corporate_score=90.0,
        regional_score=92.0,
        locked_at=datetime.now(timezone.utc),
        initiative_type="acquisition",
        origin="proactive",
    )
    await client.upsert_decision_node(decision)
    client._database.run_in_transaction.assert_called_once()


@pytest.mark.asyncio
async def test_spanner_get_document_indicators_parses_rows() -> None:
    decision_id = uuid.uuid4()
    rows = [
        (
            str(decision_id),
            "Test Decision",
            DecisionStatus.DD_IN_PROGRESS.value,
            72.0,
            None,
            "proactive",
            [BJRItemCode.D_06_QUORUM.value],
        )
    ]
    client = _make_spanner_client_with_mock(rows)
    results = await client.get_document_indicators(
        doc_id=uuid.uuid4(), doc_type="mom"
    )
    assert len(results) == 1
    assert results[0].decision_id == decision_id
    assert not results[0].is_locked
    assert BJRItemCode.D_06_QUORUM in results[0].satisfied_items


@pytest.mark.asyncio
async def test_spanner_get_document_indicators_empty_on_error() -> None:
    client = SpannerGraphClient(
        project_id="test", instance_id="test", database_id="test"
    )
    mock_db = MagicMock()
    mock_db.snapshot = MagicMock(side_effect=ConnectionError("spanner down"))
    client._database = mock_db
    results = await client.get_document_indicators(
        doc_id=uuid.uuid4(), doc_type="mom"
    )
    assert results == []
```

- [ ] **Step 2: Run tests to verify failure**

Run:
```bash
PYTHONPATH=packages/ancol-common/src python3 -m pytest packages/ancol-common/tests/test_graph_client_bjr.py -v -k "spanner"
```
Expected: 3 FAIL — methods not yet on `SpannerGraphClient`.

- [ ] **Step 3: Implement the 6 methods in `SpannerGraphClient`**

Open `packages/ancol-common/src/ancol_common/rag/spanner_graph.py`. Add after the existing `get_related_contracts` method:

```python
    # ── BJR extensions (Phase 6.4a) ───────────────────────────────────────
    #
    # Spanner Graph is written as GQL inside standard Spanner DML/DQL.
    # Nodes live in `Decision`, `Evidence`, `ChecklistItem` tables with
    # property-graph annotations; edges live in `DecisionEvidence`,
    # `EvidenceItem`, `DecisionApproval` edge tables.

    async def upsert_decision_node(self, decision: DecisionNode) -> None:
        """Create or update a Decision vertex."""
        def _tx(txn):
            txn.execute_update(
                """
                MERGE INTO Decision (id, title, status, readiness_score,
                    corporate_score, regional_score, locked_at,
                    initiative_type, origin)
                USING (SELECT @id AS id) src ON Decision.id = src.id
                WHEN MATCHED THEN UPDATE SET
                    title=@title, status=@status,
                    readiness_score=@readiness_score,
                    corporate_score=@corporate_score,
                    regional_score=@regional_score,
                    locked_at=@locked_at,
                    initiative_type=@initiative_type,
                    origin=@origin
                WHEN NOT MATCHED THEN INSERT (id, title, status, readiness_score,
                    corporate_score, regional_score, locked_at,
                    initiative_type, origin)
                    VALUES (@id, @title, @status, @readiness_score,
                    @corporate_score, @regional_score, @locked_at,
                    @initiative_type, @origin)
                """,
                params={
                    "id": str(decision.id),
                    "title": decision.title,
                    "status": decision.status,
                    "readiness_score": decision.readiness_score,
                    "corporate_score": decision.corporate_score,
                    "regional_score": decision.regional_score,
                    "locked_at": decision.locked_at,
                    "initiative_type": decision.initiative_type,
                    "origin": decision.origin,
                },
                param_types={
                    "id": spanner.param_types.STRING,
                    "title": spanner.param_types.STRING,
                    "status": spanner.param_types.STRING,
                    "readiness_score": spanner.param_types.FLOAT64,
                    "corporate_score": spanner.param_types.FLOAT64,
                    "regional_score": spanner.param_types.FLOAT64,
                    "locked_at": spanner.param_types.TIMESTAMP,
                    "initiative_type": spanner.param_types.STRING,
                    "origin": spanner.param_types.STRING,
                },
            )
        try:
            self._database.run_in_transaction(_tx)
        except Exception:
            logger.exception("Spanner upsert_decision_node failed for %s", decision.id)

    async def upsert_supported_by_edge(
        self,
        decision_id: uuid.UUID,
        evidence: EvidenceNode,
        linked_at: datetime,
        linked_by: uuid.UUID,
    ) -> None:
        """Insert/update DecisionEvidence edge row."""
        def _tx(txn):
            # Ensure Evidence vertex exists
            txn.execute_update(
                """
                INSERT INTO Evidence (id, type)
                VALUES (@id, @type)
                ON CONFLICT (id) DO NOTHING
                """,
                params={"id": str(evidence.id), "type": evidence.type},
                param_types={
                    "id": spanner.param_types.STRING,
                    "type": spanner.param_types.STRING,
                },
            )
            txn.execute_update(
                """
                MERGE INTO DecisionEvidence (decision_id, evidence_id, linked_at, linked_by)
                USING (SELECT @decision_id AS decision_id, @evidence_id AS evidence_id) src
                ON DecisionEvidence.decision_id = src.decision_id
                   AND DecisionEvidence.evidence_id = src.evidence_id
                WHEN MATCHED THEN UPDATE SET linked_at=@linked_at, linked_by=@linked_by
                WHEN NOT MATCHED THEN INSERT (decision_id, evidence_id, linked_at, linked_by)
                    VALUES (@decision_id, @evidence_id, @linked_at, @linked_by)
                """,
                params={
                    "decision_id": str(decision_id),
                    "evidence_id": str(evidence.id),
                    "linked_at": linked_at,
                    "linked_by": str(linked_by),
                },
                param_types={
                    "decision_id": spanner.param_types.STRING,
                    "evidence_id": spanner.param_types.STRING,
                    "linked_at": spanner.param_types.TIMESTAMP,
                    "linked_by": spanner.param_types.STRING,
                },
            )
        try:
            self._database.run_in_transaction(_tx)
        except Exception:
            logger.exception(
                "Spanner upsert_supported_by_edge failed %s→%s",
                decision_id, evidence.id,
            )

    async def upsert_satisfies_item_edge(
        self,
        evidence_id: uuid.UUID,
        item_code: BJRItemCode,
        decision_id: uuid.UUID,
        evaluator_status: str,
    ) -> None:
        """Insert/update EvidenceItem edge row."""
        def _tx(txn):
            txn.execute_update(
                """
                INSERT INTO ChecklistItem (code)
                VALUES (@code) ON CONFLICT (code) DO NOTHING
                """,
                params={"code": item_code.value},
                param_types={"code": spanner.param_types.STRING},
            )
            txn.execute_update(
                """
                MERGE INTO EvidenceItem (evidence_id, item_code, decision_id, evaluator_status)
                USING (SELECT @evidence_id AS ei, @item_code AS ic, @decision_id AS di) src
                ON EvidenceItem.evidence_id = src.ei
                   AND EvidenceItem.item_code = src.ic
                   AND EvidenceItem.decision_id = src.di
                WHEN MATCHED THEN UPDATE SET evaluator_status=@evaluator_status
                WHEN NOT MATCHED THEN INSERT (evidence_id, item_code, decision_id, evaluator_status)
                    VALUES (@evidence_id, @item_code, @decision_id, @evaluator_status)
                """,
                params={
                    "evidence_id": str(evidence_id),
                    "item_code": item_code.value,
                    "decision_id": str(decision_id),
                    "evaluator_status": evaluator_status,
                },
                param_types={
                    "evidence_id": spanner.param_types.STRING,
                    "item_code": spanner.param_types.STRING,
                    "decision_id": spanner.param_types.STRING,
                    "evaluator_status": spanner.param_types.STRING,
                },
            )
        try:
            self._database.run_in_transaction(_tx)
        except Exception:
            logger.exception(
                "Spanner upsert_satisfies_item_edge failed %s→%s decision %s",
                evidence_id, item_code.value, decision_id,
            )

    async def upsert_approved_by_edge(
        self,
        decision_id: uuid.UUID,
        user_id: uuid.UUID,
        half: Gate5Half,
        approved_at: datetime,
    ) -> None:
        """Insert/update DecisionApproval edge row."""
        def _tx(txn):
            txn.execute_update(
                """
                MERGE INTO DecisionApproval (decision_id, half, user_id, approved_at)
                USING (SELECT @decision_id AS di, @half AS h) src
                ON DecisionApproval.decision_id = src.di AND DecisionApproval.half = src.h
                WHEN MATCHED THEN UPDATE SET user_id=@user_id, approved_at=@approved_at
                WHEN NOT MATCHED THEN INSERT (decision_id, half, user_id, approved_at)
                    VALUES (@decision_id, @half, @user_id, @approved_at)
                """,
                params={
                    "decision_id": str(decision_id),
                    "half": half.value,
                    "user_id": str(user_id),
                    "approved_at": approved_at,
                },
                param_types={
                    "decision_id": spanner.param_types.STRING,
                    "half": spanner.param_types.STRING,
                    "user_id": spanner.param_types.STRING,
                    "approved_at": spanner.param_types.TIMESTAMP,
                },
            )
        try:
            self._database.run_in_transaction(_tx)
        except Exception:
            logger.exception(
                "Spanner upsert_approved_by_edge failed %s/%s", decision_id, half,
            )

    async def get_document_indicators(
        self,
        doc_id: uuid.UUID,
        doc_type: str,
    ) -> list[DocumentIndicator]:
        """Return all decisions this doc supports with per-decision checklist coverage."""
        sql = """
        SELECT d.id, d.title, d.status, d.readiness_score, d.locked_at, d.origin,
               ARRAY(
                   SELECT ei.item_code FROM EvidenceItem ei
                   WHERE ei.evidence_id = de.evidence_id
                     AND ei.decision_id = de.decision_id
               ) AS satisfied_items
        FROM DecisionEvidence de
        JOIN Decision d ON d.id = de.decision_id
        WHERE de.evidence_id = @doc_id
        """
        try:
            with self._database.snapshot() as snap:
                rows = snap.execute_sql(
                    sql,
                    params={"doc_id": str(doc_id)},
                    param_types={"doc_id": spanner.param_types.STRING},
                )
                records = list(rows)
        except Exception:
            logger.exception(
                "Spanner get_document_indicators failed for %s/%s", doc_id, doc_type,
            )
            return []

        out: list[DocumentIndicator] = []
        for row in records:
            d_id, title, status, readiness, locked_at, origin, sat_raw = row
            satisfied = [BJRItemCode(c) for c in (sat_raw or []) if c]
            all_items = set(BJRItemCode)
            missing = sorted(all_items - set(satisfied), key=lambda c: c.value)
            out.append(
                DocumentIndicator(
                    decision_id=uuid.UUID(d_id),
                    decision_title=title,
                    status=status,
                    readiness_score=readiness,
                    is_locked=locked_at is not None,
                    locked_at=locked_at,
                    satisfied_items=satisfied,
                    missing_items=missing,
                    origin=origin or "proactive",
                )
            )
        return out

    async def get_decision_evidence(
        self,
        decision_id: uuid.UUID,
    ) -> list[EvidenceSummary]:
        """Return all evidence linked to a decision with per-evidence satisfied items."""
        sql = """
        SELECT ev.id, ev.type, COALESCE(ev.title, '') AS title,
               ARRAY(
                   SELECT ei.item_code FROM EvidenceItem ei
                   WHERE ei.evidence_id = ev.id AND ei.decision_id = @decision_id
               ) AS satisfies_items
        FROM DecisionEvidence de
        JOIN Evidence ev ON ev.id = de.evidence_id
        WHERE de.decision_id = @decision_id
        """
        try:
            with self._database.snapshot() as snap:
                rows = snap.execute_sql(
                    sql,
                    params={"decision_id": str(decision_id)},
                    param_types={"decision_id": spanner.param_types.STRING},
                )
                records = list(rows)
        except Exception:
            logger.exception(
                "Spanner get_decision_evidence failed for decision %s", decision_id,
            )
            return []

        return [
            EvidenceSummary(
                evidence_id=uuid.UUID(rec[0]),
                evidence_type=rec[1],
                title=rec[2] or f"{rec[1]}:{rec[0][:8]}",
                satisfies_items=[BJRItemCode(c) for c in (rec[3] or []) if c],
            )
            for rec in records
        ]
```

Add to imports at top of `spanner_graph.py`:
```python
import uuid
from datetime import datetime

from ancol_common.rag.models import (
    DecisionNode,
    DocumentIndicator,
    EvidenceNode,
    EvidenceSummary,
    Gate5Half,
)
from ancol_common.schemas.bjr import BJRItemCode
```

- [ ] **Step 4: Run tests to verify pass**

Run:
```bash
PYTHONPATH=packages/ancol-common/src python3 -m pytest packages/ancol-common/tests/test_graph_client_bjr.py -v
```
Expected: all 11 tests (8 Neo4j + 3 Spanner) PASS.

- [ ] **Step 5: Lint**

```bash
ruff check packages/ancol-common/src/ancol_common/rag/spanner_graph.py packages/ancol-common/tests/test_graph_client_bjr.py
ruff format packages/ancol-common/src/ancol_common/rag/spanner_graph.py packages/ancol-common/tests/test_graph_client_bjr.py
```

- [ ] **Step 6: Commit**

```bash
git add packages/ancol-common/src/ancol_common/rag/spanner_graph.py packages/ancol-common/tests/test_graph_client_bjr.py
git commit -m "feat(rag): SpannerGraphClient — implement 6 BJR methods

GQL-via-DML impl that matches the Neo4j semantics: idempotent node
upserts, edge upserts keyed for per-decision disambiguation, and
error-degradation returning [].

3 parity tests covering DML execution, row parsing, and
error-degradation contract."
```

---

## Task 6: Add `GET /api/documents/{id}/bjr-indicators` endpoint

**Why:** The chat tool `show_document_indicators` calls this endpoint. It's a thin wrapper over `graph_client.get_document_indicators` that validates the document exists in SQL first and enforces RBAC.

**Files:**
- Modify: `services/api-gateway/src/api_gateway/routers/documents.py`
- Create: `services/api-gateway/tests/test_documents_bjr_indicators.py`

- [ ] **Step 1: Write failing integration test**

Create `services/api-gateway/tests/test_documents_bjr_indicators.py`:
```python
"""Integration tests for GET /api/documents/{id}/bjr-indicators."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from ancol_common.rag.models import DocumentIndicator
from ancol_common.schemas.bjr import BJRItemCode
from ancol_common.schemas.decision import DecisionStatus
from api_gateway.main import app


@pytest.fixture
def client_with_mocked_graph(monkeypatch):
    """TestClient with a mocked get_graph_client that returns preset indicators."""
    mock_graph = AsyncMock()
    decision_id = uuid.uuid4()
    mock_graph.get_document_indicators = AsyncMock(
        return_value=[
            DocumentIndicator(
                decision_id=decision_id,
                decision_title="Test Decision",
                status=DecisionStatus.DD_IN_PROGRESS.value,
                readiness_score=72.0,
                is_locked=False,
                locked_at=None,
                satisfied_items=[BJRItemCode.D_06_QUORUM],
                missing_items=[BJRItemCode.PD_01_DD],
                origin="proactive",
            )
        ]
    )
    from api_gateway.routers import documents
    monkeypatch.setattr(documents, "_get_graph_client", lambda: mock_graph)
    return TestClient(app), mock_graph, decision_id


def test_bjr_indicators_returns_list_for_authorized_user(
    client_with_mocked_graph, authed_headers_corp_sec,
):
    client, mock_graph, decision_id = client_with_mocked_graph
    doc_id = uuid.uuid4()

    response = client.get(
        f"/api/documents/{doc_id}/bjr-indicators",
        headers=authed_headers_corp_sec,
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["indicators"]) == 1
    assert body["indicators"][0]["decision_id"] == str(decision_id)
    assert body["indicators"][0]["readiness_score"] == 72.0
    assert "D-06-QUORUM" in body["indicators"][0]["satisfied_items"]


def test_bjr_indicators_returns_empty_list_when_graph_backend_off(
    monkeypatch, authed_headers_corp_sec,
):
    """If GRAPH_BACKEND=none, endpoint still returns 200 with empty list (SQL fallback stub)."""
    monkeypatch.setenv("GRAPH_BACKEND", "none")
    from api_gateway.routers import documents
    monkeypatch.setattr(documents, "_get_graph_client", lambda: None)
    doc_id = uuid.uuid4()
    client = TestClient(app)
    response = client.get(
        f"/api/documents/{doc_id}/bjr-indicators",
        headers=authed_headers_corp_sec,
    )
    assert response.status_code == 200
    assert response.json()["indicators"] == []


def test_bjr_indicators_rejects_unauthenticated(authed_headers_none):
    client = TestClient(app)
    doc_id = uuid.uuid4()
    response = client.get(f"/api/documents/{doc_id}/bjr-indicators")
    assert response.status_code in (401, 403)


def test_bjr_indicators_enforces_rbac(authed_headers_no_bjr_read):
    """A role without bjr:read permission is rejected."""
    client = TestClient(app)
    doc_id = uuid.uuid4()
    response = client.get(
        f"/api/documents/{doc_id}/bjr-indicators",
        headers=authed_headers_no_bjr_read,
    )
    assert response.status_code == 403


def test_bjr_indicators_invalid_uuid_returns_422(authed_headers_corp_sec):
    client = TestClient(app)
    response = client.get(
        "/api/documents/not-a-uuid/bjr-indicators",
        headers=authed_headers_corp_sec,
    )
    assert response.status_code == 422
```

Note: `authed_headers_corp_sec`, `authed_headers_none`, and `authed_headers_no_bjr_read` fixtures need to exist in `services/api-gateway/tests/conftest.py`. Check if present; if not, see next sub-step.

- [ ] **Step 2: Add missing fixtures if needed**

Run:
```bash
grep -n "authed_headers_corp_sec\|authed_headers_none" services/api-gateway/tests/conftest.py 2>&1 | head -5
```

If fixtures missing, append to `services/api-gateway/tests/conftest.py`:
```python
import pytest

@pytest.fixture
def authed_headers_corp_sec() -> dict[str, str]:
    """IAP headers as a corp_secretary user (has bjr:read)."""
    return {
        "X-Goog-Authenticated-User-Email": "corpsec@ancol.test",
        "X-Goog-Authenticated-User-Id": "test-user-corpsec",
    }

@pytest.fixture
def authed_headers_none() -> dict[str, str]:
    return {}

@pytest.fixture
def authed_headers_no_bjr_read() -> dict[str, str]:
    """IAP headers as a user with no BJR read permission."""
    return {
        "X-Goog-Authenticated-User-Email": "no-bjr@ancol.test",
        "X-Goog-Authenticated-User-Id": "test-user-no-bjr",
    }
```

Also verify the conftest seeds test users with those exact emails + roles. If not, adapt to the existing pattern (read the existing conftest to confirm the real fixture shape).

- [ ] **Step 3: Run test to verify failure**

```bash
PYTHONPATH=packages/ancol-common/src:services/api-gateway/src python3 -m pytest services/api-gateway/tests/test_documents_bjr_indicators.py -v
```
Expected: FAIL with `404` or `AttributeError: module 'api_gateway.routers.documents' has no attribute '_get_graph_client'`.

- [ ] **Step 4: Add the endpoint to `documents.py`**

Open `services/api-gateway/src/api_gateway/routers/documents.py`. Add near existing imports:
```python
import os
import uuid
from ancol_common.rag.graph_client import GraphClient
from ancol_common.rag.models import DocumentIndicator
from ancol_common.auth.rbac import require_permission
```

Add a graph client factory (module-level, one instance shared across requests):
```python
_graph_client_singleton: GraphClient | None = None


def _get_graph_client() -> GraphClient | None:
    """Return the configured GraphClient, or None if GRAPH_BACKEND=none."""
    global _graph_client_singleton
    backend = os.getenv("GRAPH_BACKEND", "spanner").lower()
    if backend == "none":
        return None
    if _graph_client_singleton is not None:
        return _graph_client_singleton
    if backend == "neo4j":
        from ancol_common.rag.neo4j_graph import Neo4jGraphClient
        _graph_client_singleton = Neo4jGraphClient(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
        )
    else:
        from ancol_common.rag.spanner_graph import SpannerGraphClient
        _graph_client_singleton = SpannerGraphClient(
            project_id=os.getenv("GCP_PROJECT_ID", ""),
            instance_id=os.getenv("SPANNER_INSTANCE_ID", ""),
            database_id=os.getenv("SPANNER_DATABASE_ID", ""),
        )
    return _graph_client_singleton
```

Add the new endpoint (place near other document GET routes in the same file):
```python
class BJRIndicatorResponse(BaseModel):
    """Single decision indicator for a document."""

    decision_id: UUID
    decision_title: str
    status: str
    readiness_score: float | None
    is_locked: bool
    locked_at: datetime | None
    satisfied_items: list[str]
    missing_items: list[str]
    origin: str


class BJRIndicatorsListResponse(BaseModel):
    indicators: list[BJRIndicatorResponse]


@router.get(
    "/{document_id}/bjr-indicators",
    response_model=BJRIndicatorsListResponse,
    summary="BJR decision indicators for a document",
)
async def get_document_bjr_indicators(
    document_id: uuid.UUID,
    _auth=Depends(require_permission("bjr:read")),
) -> BJRIndicatorsListResponse:
    """Return the set of BJR decisions this document supports, each with
    current readiness state + satisfied/missing checklist items.

    Used by the Gemini Enterprise chat tool `show_document_indicators` to
    proactively enrich every document mention with BJR context.

    Degradation: when GRAPH_BACKEND=none, returns an empty list (the chat
    tool handles this as "no BJR context available" silently). A future
    follow-up may add a SQL fallback path via decision_evidence table.
    """
    graph = _get_graph_client()
    if graph is None:
        return BJRIndicatorsListResponse(indicators=[])

    # `doc_type` is unused by the current graph query (it matches on id alone)
    # but is preserved in the signature for future type-aware routing.
    indicators = await graph.get_document_indicators(document_id, doc_type="")

    return BJRIndicatorsListResponse(
        indicators=[
            BJRIndicatorResponse(
                decision_id=ind.decision_id,
                decision_title=ind.decision_title,
                status=ind.status,
                readiness_score=ind.readiness_score,
                is_locked=ind.is_locked,
                locked_at=ind.locked_at,
                satisfied_items=[c.value for c in ind.satisfied_items],
                missing_items=[c.value for c in ind.missing_items],
                origin=ind.origin,
            )
            for ind in indicators
        ]
    )
```

Ensure `require_permission` is granted a new key `bjr:read`. Open `packages/ancol-common/src/ancol_common/auth/rbac.py` and:

1. Add `"bjr:read"` to the permissions set.
2. Add it to the permission matrix for these roles: `admin`, `corp_secretary`, `legal_compliance`, `internal_auditor`, `business_dev`, `komisaris`, `dewan_pengawas`, `direksi`. (All BJR-touching roles — only `direksi` and `komisaris` get read-only in spec § 4.2, but the *endpoint* is read-only so all are safe.)

- [ ] **Step 5: Run test to verify pass**

```bash
PYTHONPATH=packages/ancol-common/src:services/api-gateway/src python3 -m pytest services/api-gateway/tests/test_documents_bjr_indicators.py -v
```
Expected: 5 PASS.

- [ ] **Step 6: Run the full api-gateway suite**

```bash
PYTHONPATH=packages/ancol-common/src:services/api-gateway/src python3 -m pytest services/api-gateway/tests/ -q
```
Expected: 343 → 348 (or similar; +5 new tests). Zero regressions in existing tests.

- [ ] **Step 7: Lint**

```bash
ruff check services/api-gateway/src/api_gateway/routers/documents.py services/api-gateway/tests/test_documents_bjr_indicators.py packages/ancol-common/src/ancol_common/auth/rbac.py
ruff format services/api-gateway/src/api_gateway/routers/documents.py services/api-gateway/tests/test_documents_bjr_indicators.py packages/ancol-common/src/ancol_common/auth/rbac.py
```

- [ ] **Step 8: Commit**

```bash
git add services/api-gateway/src/api_gateway/routers/documents.py services/api-gateway/tests/test_documents_bjr_indicators.py packages/ancol-common/src/ancol_common/auth/rbac.py
git commit -m "feat(api-gateway): GET /api/documents/{id}/bjr-indicators

New read-only endpoint backing the chat 'document indicator' feature.
Wraps graph_client.get_document_indicators, enforces bjr:read RBAC
(granted to all BJR-touching roles), degrades to empty list when
GRAPH_BACKEND=none.

5 integration tests covering happy path, GRAPH_BACKEND=none
degradation, unauthenticated, RBAC denial, and invalid UUID."
```

---

## Task 7: `bjr_decisions.py` chat tool handlers (read-only)

**Why:** Three tools — `list_decisions`, `get_decision`, `list_my_decisions`. They proxy to existing API Gateway routes (`GET /api/decisions`, `GET /api/decisions/{id}`, `GET /api/decisions?owner_id=me`). Moderate PII scrubbing applied in output formatting.

**Files:**
- Create: `services/gemini-agent/src/gemini_agent/tools/bjr_decisions.py`
- Create: `services/gemini-agent/tests/test_tools_bjr_decisions.py`
- Modify: `services/gemini-agent/src/gemini_agent/api_client.py`

- [ ] **Step 1: Write failing test**

Create `services/gemini-agent/tests/test_tools_bjr_decisions.py`:
```python
"""Unit tests for BJR decision read-only chat tool handlers."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from gemini_agent.tools.bjr_decisions import (
    handle_get_decision,
    handle_list_decisions,
    handle_list_my_decisions,
)


@pytest.fixture
def user_corp_sec() -> dict:
    return {"email": "corpsec@ancol.test", "role": "corp_secretary"}


@pytest.fixture
def api_mock():
    api = AsyncMock()
    return api


@pytest.mark.asyncio
async def test_get_decision_formats_response(api_mock, user_corp_sec):
    decision_id = uuid.uuid4()
    api_mock.get_decision = AsyncMock(
        return_value={
            "id": str(decision_id),
            "title": "Akuisisi PT Wahana Baru",
            "status": "dd_in_progress",
            "readiness_score": 72.0,
            "corporate_score": 72.0,
            "regional_score": 78.0,
            "initiative_type": "acquisition",
            "estimated_value_idr": 150_000_000_000,
            "origin": "proactive",
            "created_at": "2026-03-01T10:00:00+07:00",
            "owner_id": "user-xyz",
        }
    )
    out = await handle_get_decision(
        {"decision_id": str(decision_id)}, api_mock, user_corp_sec
    )
    assert "Akuisisi PT Wahana Baru" in out
    assert "72" in out  # readiness score shown
    assert "Rp 150 miliar" in out or "Rp 150,0 miliar" in out  # scrubbed IDR


@pytest.mark.asyncio
async def test_get_decision_missing_id_returns_error(api_mock, user_corp_sec):
    out = await handle_get_decision({}, api_mock, user_corp_sec)
    assert "decision_id" in out.lower()
    api_mock.get_decision.assert_not_called()


@pytest.mark.asyncio
async def test_get_decision_handles_api_404(api_mock, user_corp_sec):
    api_mock.get_decision = AsyncMock(side_effect=Exception("404"))
    out = await handle_get_decision(
        {"decision_id": str(uuid.uuid4())}, api_mock, user_corp_sec
    )
    assert "gagal" in out.lower() or "tidak dapat" in out.lower() or "error" in out.lower()


@pytest.mark.asyncio
async def test_list_decisions_default_limit(api_mock, user_corp_sec):
    api_mock.list_decisions = AsyncMock(
        return_value={
            "items": [
                {
                    "id": str(uuid.uuid4()),
                    "title": f"Decision {i}",
                    "status": "ideation",
                    "readiness_score": None,
                    "initiative_type": "acquisition",
                    "origin": "proactive",
                    "created_at": "2026-04-01T10:00:00+07:00",
                }
                for i in range(10)
            ],
            "total": 10,
        }
    )
    out = await handle_list_decisions({}, api_mock, user_corp_sec)
    # Confirm the tool used the default limit
    call = api_mock.list_decisions.await_args
    assert call.kwargs.get("limit") in (20, 10, None)  # implementation choice
    assert "10" in out  # total count rendered


@pytest.mark.asyncio
async def test_list_decisions_status_filter(api_mock, user_corp_sec):
    api_mock.list_decisions = AsyncMock(return_value={"items": [], "total": 0})
    await handle_list_decisions(
        {"status": "bjr_locked"}, api_mock, user_corp_sec
    )
    call = api_mock.list_decisions.await_args
    assert call.kwargs.get("status") == "bjr_locked"


@pytest.mark.asyncio
async def test_list_my_decisions_passes_user_email(api_mock, user_corp_sec):
    api_mock.list_decisions = AsyncMock(return_value={"items": [], "total": 0})
    await handle_list_my_decisions({}, api_mock, user_corp_sec)
    call = api_mock.list_decisions.await_args
    # Either owner_email or owner_id should be set to the current user
    kw = call.kwargs
    assert kw.get("owner_email") == "corpsec@ancol.test" or "me" in str(kw)
```

- [ ] **Step 2: Run test to verify failure**

```bash
PYTHONPATH=packages/ancol-common/src:services/gemini-agent/src python3 -m pytest services/gemini-agent/tests/test_tools_bjr_decisions.py -v
```
Expected: 6 FAIL — handlers don't exist yet.

- [ ] **Step 3: Add api_client methods**

Open `services/gemini-agent/src/gemini_agent/api_client.py`. Add three methods (place near existing GET methods, following the pattern of `get_report`):

```python
    async def get_decision(self, decision_id: str) -> dict:
        """GET /api/decisions/{id}"""
        return await self._request("GET", f"/api/decisions/{decision_id}")

    async def list_decisions(
        self,
        *,
        status: str | None = None,
        owner_email: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        """GET /api/decisions with optional filters."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if owner_email:
            params["owner_email"] = owner_email
        return await self._request("GET", "/api/decisions", params=params)

    async def get_readiness(self, decision_id: str) -> dict:
        """GET /api/decisions/{id}/readiness"""
        return await self._request("GET", f"/api/decisions/{decision_id}/readiness")

    async def get_checklist(self, decision_id: str) -> dict:
        """GET /api/decisions/{id}/checklist"""
        return await self._request("GET", f"/api/decisions/{decision_id}/checklist")

    async def get_bjr_indicators(self, doc_id: str) -> dict:
        """GET /api/documents/{id}/bjr-indicators"""
        return await self._request("GET", f"/api/documents/{doc_id}/bjr-indicators")

    async def get_decision_evidence(self, decision_id: str) -> dict:
        """GET /api/decisions/{id}/evidence"""
        return await self._request("GET", f"/api/decisions/{decision_id}/evidence")

    async def get_passport_url(self, decision_id: str) -> dict:
        """GET /api/decisions/{id}/passport/signed-url"""
        return await self._request(
            "GET", f"/api/decisions/{decision_id}/passport/signed-url"
        )
```

- [ ] **Step 4: Create `bjr_decisions.py` handler**

Create `services/gemini-agent/src/gemini_agent/tools/bjr_decisions.py`:
```python
"""Read-only BJR decision chat tool handlers.

Three tools:
- `get_decision(decision_id)` — full decision detail
- `list_decisions(status?, limit?)` — paginated list
- `list_my_decisions()` — decisions owned by the current user

All output is chat-formatted with moderate PII scrubbing (spec § 6.4):
large IDR values rounded to `Rp X miliar`; conflicted party names
appear as initials elsewhere (not in this handler).
"""

from __future__ import annotations

import logging

from gemini_agent.api_client import ApiClient
from gemini_agent.formatting_bjr import (
    format_decision_detail,
    format_decision_list,
)

logger = logging.getLogger(__name__)


async def handle_get_decision(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Fetch a single BJR decision by ID."""
    decision_id: str = (params.get("decision_id") or "").strip()
    if not decision_id:
        return "Error: Harap berikan `decision_id` untuk mengambil decision."

    logger.info("Fetching decision: %s", decision_id)
    try:
        decision = await api.get_decision(decision_id)
    except Exception:
        logger.exception("Failed to fetch decision %s", decision_id)
        return f"Gagal mengambil decision `{decision_id}`. Pastikan ID sudah benar."

    return format_decision_detail(decision)


async def handle_list_decisions(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """List BJR decisions with optional status filter."""
    status: str | None = params.get("status")
    limit = int(params.get("limit", 20))

    logger.info("Listing decisions: status=%s limit=%s", status, limit)
    try:
        result = await api.list_decisions(status=status, limit=limit)
    except Exception:
        logger.exception("Failed to list decisions")
        return "Gagal mengambil daftar decision. Coba lagi nanti."

    return format_decision_list(result)


async def handle_list_my_decisions(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """List decisions owned by the current user."""
    owner_email = user.get("email", "")
    limit = int(params.get("limit", 20))

    logger.info("Listing my decisions for %s", owner_email)
    try:
        result = await api.list_decisions(
            owner_email=owner_email,
            limit=limit,
        )
    except Exception:
        logger.exception("Failed to list my decisions for %s", owner_email)
        return "Gagal mengambil decision Anda. Coba lagi nanti."

    return format_decision_list(result, personalized_for=owner_email)
```

- [ ] **Step 5: Create `formatting_bjr.py` with the two formatters used by Task 7**

Create `services/gemini-agent/src/gemini_agent/formatting_bjr.py`:
```python
"""Markdown/card formatters for BJR chat responses.

All formatters apply moderate PII scrubbing (spec § 6.4):
- IDR values > 1,000,000,000 rounded to "Rp X,Y miliar"
- IDR values > 1,000,000,000,000 rounded to "Rp X,Y triliun"
- Small values shown at full precision
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _format_idr(value: int | float | None) -> str:
    """Moderate PII scrubbing for IDR values."""
    if value is None:
        return "—"
    v = float(value)
    if v >= 1_000_000_000_000:
        return f"Rp {v / 1_000_000_000_000:.1f} triliun".replace(".", ",")
    if v >= 1_000_000_000:
        return f"Rp {v / 1_000_000_000:.1f} miliar".replace(".", ",")
    if v >= 1_000_000:
        return f"Rp {v / 1_000_000:.0f} juta"
    return f"Rp {v:,.0f}"


def _state_emoji(status: str, is_locked: bool, readiness: float | None) -> str:
    if is_locked or status == "bjr_locked":
        return "🔒"
    if readiness is None:
        return "⚪"
    if readiness >= 85.0:
        return "🟢"
    return "🟡"


def format_decision_detail(decision: dict) -> str:
    """Render a single decision as a multi-line markdown card."""
    title = decision.get("title", "(Tidak ada judul)")
    status = decision.get("status", "unknown")
    readiness = decision.get("readiness_score")
    corp_score = decision.get("corporate_score")
    reg_score = decision.get("regional_score")
    initiative = decision.get("initiative_type", "—")
    value_idr = decision.get("estimated_value_idr")
    locked_at = decision.get("locked_at")
    is_locked = status == "bjr_locked" or locked_at is not None

    emoji = _state_emoji(status, is_locked, readiness)
    lines = [
        f"{emoji} **{title}**",
        f"Status: `{status}` • Initiative: `{initiative}`",
    ]
    if readiness is not None:
        reg_str = f"{reg_score:.0f}" if reg_score is not None else "—"
        corp_str = f"{corp_score:.0f}" if corp_score is not None else "—"
        lines.append(
            f"Readiness: **{readiness:.0f}/100** "
            f"(Corporate: {corp_str}, Regional: {reg_str})"
        )
    if value_idr:
        lines.append(f"Estimated value: {_format_idr(value_idr)}")
    if is_locked and locked_at:
        lines.append(f"🔒 Locked at: {locked_at}")
    return "\n".join(lines)


def format_decision_list(result: dict, personalized_for: str | None = None) -> str:
    """Render a list of decisions as a compact markdown table."""
    items = result.get("items", [])
    total = result.get("total", len(items))

    if not items:
        suffix = f" untuk {personalized_for}" if personalized_for else ""
        return f"Tidak ada decision ditemukan{suffix}."

    header = f"**{total} decision**" + (
        f" milik {personalized_for}" if personalized_for else ""
    ) + ":\n"
    rows: list[str] = [header]
    for d in items:
        emoji = _state_emoji(
            d.get("status", ""),
            d.get("status") == "bjr_locked",
            d.get("readiness_score"),
        )
        readiness = d.get("readiness_score")
        r_str = f"{readiness:.0f}/100" if readiness is not None else "—"
        rows.append(
            f"- {emoji} `{d.get('id', '?')[:8]}` — **{d.get('title', '—')}** "
            f"(readiness {r_str}, status `{d.get('status', '?')}`)"
        )
    return "\n".join(rows)
```

- [ ] **Step 6: Run tests to verify pass**

```bash
PYTHONPATH=packages/ancol-common/src:services/gemini-agent/src python3 -m pytest services/gemini-agent/tests/test_tools_bjr_decisions.py -v
```
Expected: 6 PASS.

- [ ] **Step 7: Lint**

```bash
ruff check services/gemini-agent/src/gemini_agent/tools/bjr_decisions.py services/gemini-agent/src/gemini_agent/formatting_bjr.py services/gemini-agent/tests/test_tools_bjr_decisions.py services/gemini-agent/src/gemini_agent/api_client.py
ruff format services/gemini-agent/src/gemini_agent/tools/bjr_decisions.py services/gemini-agent/src/gemini_agent/formatting_bjr.py services/gemini-agent/tests/test_tools_bjr_decisions.py services/gemini-agent/src/gemini_agent/api_client.py
```

- [ ] **Step 8: Commit**

```bash
git add services/gemini-agent/src/gemini_agent/tools/bjr_decisions.py services/gemini-agent/src/gemini_agent/formatting_bjr.py services/gemini-agent/tests/test_tools_bjr_decisions.py services/gemini-agent/src/gemini_agent/api_client.py
git commit -m "feat(gemini-agent): bjr_decisions read-only tool handlers

get_decision, list_decisions, list_my_decisions tool handlers that
proxy to existing API Gateway routes. Moderate PII scrubbing (IDR
rounding to miliar/triliun) in formatting_bjr.format_decision_detail
and format_decision_list.

6 unit tests covering happy path, missing param, 404 handling,
default limit, status filter, and owner_email filtering."
```

---

## Task 8: `bjr_readiness.py` chat tool handlers

**Why:** Two tools — `get_readiness(decision_id)` and `get_checklist(decision_id)`. They render the dual-regime score and 16-item checklist as compact chat cards.

**Files:**
- Create: `services/gemini-agent/src/gemini_agent/tools/bjr_readiness.py`
- Create: `services/gemini-agent/tests/test_tools_bjr_readiness.py`
- Modify: `services/gemini-agent/src/gemini_agent/formatting_bjr.py` (add `format_readiness_card`, `format_checklist_summary`)

- [ ] **Step 1: Write failing test**

Create `services/gemini-agent/tests/test_tools_bjr_readiness.py`:
```python
"""Unit tests for bjr_readiness chat tool handlers."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from gemini_agent.tools.bjr_readiness import (
    handle_get_checklist,
    handle_get_readiness,
)


@pytest.fixture
def user_corp_sec() -> dict:
    return {"email": "corpsec@ancol.test", "role": "corp_secretary"}


@pytest.fixture
def api_mock():
    return AsyncMock()


@pytest.mark.asyncio
async def test_get_readiness_shows_dual_regime(api_mock, user_corp_sec):
    did = uuid.uuid4()
    api_mock.get_readiness = AsyncMock(
        return_value={
            "decision_id": str(did),
            "readiness_score": 72.0,
            "corporate_score": 72.0,
            "regional_score": 88.0,
            "gate_5_unlockable": False,
            "critical_items_flagged": ["PD-03-RKAB"],
            "missing_items": ["PD-01-DD", "PD-05-COI"],
            "satisfied_items": [
                "PD-02-FS", "PD-04-RJPP", "D-06-QUORUM", "D-07-SIGNED",
            ],
        }
    )
    out = await handle_get_readiness({"decision_id": str(did)}, api_mock, user_corp_sec)
    # dual-regime must show min() = 72 highlighted
    assert "72" in out
    assert "88" in out  # regional score also shown
    assert "PD-03-RKAB" in out  # CRITICAL flagged


@pytest.mark.asyncio
async def test_get_readiness_unlocked_shows_gate5_ready(api_mock, user_corp_sec):
    did = uuid.uuid4()
    api_mock.get_readiness = AsyncMock(
        return_value={
            "decision_id": str(did),
            "readiness_score": 92.0,
            "corporate_score": 92.0,
            "regional_score": 95.0,
            "gate_5_unlockable": True,
            "critical_items_flagged": [],
            "missing_items": [],
            "satisfied_items": [],
        }
    )
    out = await handle_get_readiness({"decision_id": str(did)}, api_mock, user_corp_sec)
    assert "Gate 5" in out
    assert "ready" in out.lower() or "siap" in out.lower()


@pytest.mark.asyncio
async def test_get_readiness_missing_id(api_mock, user_corp_sec):
    out = await handle_get_readiness({}, api_mock, user_corp_sec)
    assert "decision_id" in out.lower()


@pytest.mark.asyncio
async def test_get_checklist_groups_by_phase(api_mock, user_corp_sec):
    did = uuid.uuid4()
    api_mock.get_checklist = AsyncMock(
        return_value={
            "items": [
                {"code": "PD-01-DD", "status": "not_started", "phase": "pre-decision"},
                {"code": "PD-02-FS", "status": "satisfied", "phase": "pre-decision"},
                {"code": "PD-03-RKAB", "status": "flagged", "phase": "pre-decision"},
                {"code": "D-06-QUORUM", "status": "satisfied", "phase": "decision"},
                {"code": "POST-13-MONITOR", "status": "not_started", "phase": "post-decision"},
            ],
        }
    )
    out = await handle_get_checklist({"decision_id": str(did)}, api_mock, user_corp_sec)
    # Three phases rendered
    assert "pre-decision" in out.lower() or "Pre-decision" in out
    assert "decision" in out.lower()
    assert "post-decision" in out.lower() or "Post-decision" in out


@pytest.mark.asyncio
async def test_get_checklist_flags_critical_items(api_mock, user_corp_sec):
    did = uuid.uuid4()
    api_mock.get_checklist = AsyncMock(
        return_value={
            "items": [
                {"code": "PD-03-RKAB", "status": "flagged", "phase": "pre-decision"},
                {"code": "PD-05-COI", "status": "not_started", "phase": "pre-decision"},
            ],
        }
    )
    out = await handle_get_checklist({"decision_id": str(did)}, api_mock, user_corp_sec)
    # CRITICAL items marked prominently
    assert "CRITICAL" in out or "⚠" in out or "🚨" in out
```

- [ ] **Step 2: Run test to verify failure**

```bash
PYTHONPATH=packages/ancol-common/src:services/gemini-agent/src python3 -m pytest services/gemini-agent/tests/test_tools_bjr_readiness.py -v
```
Expected: 5 FAIL — handlers don't exist.

- [ ] **Step 3: Extend `formatting_bjr.py` with two new formatters**

Append to `services/gemini-agent/src/gemini_agent/formatting_bjr.py`:

```python
CRITICAL_ITEMS = frozenset({"PD-03-RKAB", "PD-05-COI", "D-06-QUORUM", "D-11-DISCLOSE"})


def format_readiness_card(readiness: dict) -> str:
    """Render readiness score + missing/flagged items as a chat card."""
    score = readiness.get("readiness_score")
    corp = readiness.get("corporate_score")
    reg = readiness.get("regional_score")
    unlockable = readiness.get("gate_5_unlockable", False)
    flagged_critical = readiness.get("critical_items_flagged", [])
    missing = readiness.get("missing_items", [])

    emoji = "🟢" if unlockable else "🟡"
    lines = [
        f"{emoji} **BJR Readiness: {score:.0f}/100**",
        f"Corporate: {corp:.0f} • Regional: {reg:.0f}  (min = readiness)",
    ]
    if unlockable:
        lines.append("✅ **Gate 5 siap dibuka** — both regimes ≥ 85, no CRITICAL flagged.")
    else:
        lines.append("🔒 **Gate 5 belum bisa dibuka.**")
        if flagged_critical:
            flagged_str = ", ".join(f"`{c}`" for c in flagged_critical)
            lines.append(f"  🚨 CRITICAL items flagged: {flagged_str}")
        if missing:
            top_missing = [f"`{c}`" for c in missing[:5]]
            extra = f" (+{len(missing)-5} more)" if len(missing) > 5 else ""
            lines.append(f"  ⚠ Missing items: {', '.join(top_missing)}{extra}")
    return "\n".join(lines)


_ITEM_STATUS_EMOJI = {
    "satisfied": "✓",
    "flagged": "⚠",
    "not_started": "○",
    "in_progress": "…",
}


def format_checklist_summary(checklist: dict) -> str:
    """Render the 16-item checklist grouped by phase."""
    items = checklist.get("items", [])
    by_phase: dict[str, list[dict]] = {
        "pre-decision": [],
        "decision": [],
        "post-decision": [],
    }
    for item in items:
        phase = (item.get("phase") or "").lower()
        if phase not in by_phase:
            continue
        by_phase[phase].append(item)

    lines = ["**16-item BJR checklist:**"]
    for phase, title in [
        ("pre-decision", "Pre-decision"),
        ("decision", "Decision"),
        ("post-decision", "Post-decision"),
    ]:
        phase_items = by_phase[phase]
        if not phase_items:
            continue
        satisfied_count = sum(1 for it in phase_items if it.get("status") == "satisfied")
        lines.append(f"\n**{title}** — {satisfied_count}/{len(phase_items)} satisfied")
        for it in phase_items:
            code = it.get("code", "?")
            status = it.get("status", "unknown")
            emoji = _ITEM_STATUS_EMOJI.get(status, "?")
            marker = "  🚨 CRITICAL" if code in CRITICAL_ITEMS and status == "flagged" else ""
            lines.append(f"  {emoji} `{code}` ({status}){marker}")
    return "\n".join(lines)
```

- [ ] **Step 4: Create `bjr_readiness.py`**

Create `services/gemini-agent/src/gemini_agent/tools/bjr_readiness.py`:
```python
"""BJR readiness-score + checklist chat tool handlers (read-only)."""

from __future__ import annotations

import logging

from gemini_agent.api_client import ApiClient
from gemini_agent.formatting_bjr import (
    format_checklist_summary,
    format_readiness_card,
)

logger = logging.getLogger(__name__)


async def handle_get_readiness(params: dict, api: ApiClient, user: dict) -> str:
    """Fetch dual-regime BJR readiness for a decision."""
    decision_id: str = (params.get("decision_id") or "").strip()
    if not decision_id:
        return "Error: Harap berikan `decision_id` untuk melihat readiness score."

    try:
        readiness = await api.get_readiness(decision_id)
    except Exception:
        logger.exception("get_readiness failed for %s", decision_id)
        return f"Gagal mengambil readiness untuk `{decision_id}`."

    return format_readiness_card(readiness)


async def handle_get_checklist(params: dict, api: ApiClient, user: dict) -> str:
    """Fetch the 16-item BJR checklist for a decision."""
    decision_id: str = (params.get("decision_id") or "").strip()
    if not decision_id:
        return "Error: Harap berikan `decision_id` untuk melihat checklist."

    try:
        checklist = await api.get_checklist(decision_id)
    except Exception:
        logger.exception("get_checklist failed for %s", decision_id)
        return f"Gagal mengambil checklist untuk `{decision_id}`."

    return format_checklist_summary(checklist)
```

- [ ] **Step 5: Run tests to verify pass**

```bash
PYTHONPATH=packages/ancol-common/src:services/gemini-agent/src python3 -m pytest services/gemini-agent/tests/test_tools_bjr_readiness.py -v
```
Expected: 5 PASS.

- [ ] **Step 6: Lint + commit**

```bash
ruff check services/gemini-agent/src/gemini_agent/tools/bjr_readiness.py services/gemini-agent/src/gemini_agent/formatting_bjr.py services/gemini-agent/tests/test_tools_bjr_readiness.py
ruff format services/gemini-agent/src/gemini_agent/tools/bjr_readiness.py services/gemini-agent/src/gemini_agent/formatting_bjr.py services/gemini-agent/tests/test_tools_bjr_readiness.py

git add services/gemini-agent/src/gemini_agent/tools/bjr_readiness.py services/gemini-agent/src/gemini_agent/formatting_bjr.py services/gemini-agent/tests/test_tools_bjr_readiness.py
git commit -m "feat(gemini-agent): bjr_readiness tool handlers

get_readiness renders dual-regime score + flagged CRITICAL items +
missing items. get_checklist groups the 16-item checklist by phase
(pre-decision/decision/post-decision) with status emoji and
CRITICAL-item highlighting.

5 unit tests covering dual-regime display, Gate 5 readiness state,
missing decision_id, phase grouping, and CRITICAL highlighting."
```

---

## Task 9: `bjr_evidence.py` chat tool handlers

**Why:** Two tools — `show_document_indicators(doc_id, doc_type)` and `show_decision_evidence(decision_id)`. The first is the user-specific ask; it's called proactively (per Agent Builder system prompt in Phase 6.4b).

**Files:**
- Create: `services/gemini-agent/src/gemini_agent/tools/bjr_evidence.py`
- Create: `services/gemini-agent/tests/test_tools_bjr_evidence.py`
- Modify: `services/gemini-agent/src/gemini_agent/formatting_bjr.py` (add `format_document_indicators` + `format_decision_evidence`)

- [ ] **Step 1: Write failing tests**

Create `services/gemini-agent/tests/test_tools_bjr_evidence.py`:
```python
"""Unit tests for bjr_evidence chat tool handlers."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from gemini_agent.tools.bjr_evidence import (
    handle_show_decision_evidence,
    handle_show_document_indicators,
)


@pytest.fixture
def user() -> dict:
    return {"email": "x@ancol.test", "role": "business_dev"}


@pytest.fixture
def api_mock():
    return AsyncMock()


@pytest.mark.asyncio
async def test_show_document_indicators_renders_one_decision(api_mock, user):
    doc_id = uuid.uuid4()
    api_mock.get_bjr_indicators = AsyncMock(
        return_value={
            "indicators": [
                {
                    "decision_id": str(uuid.uuid4()),
                    "decision_title": "Divestasi Hotel Jaya",
                    "status": "bjr_locked",
                    "readiness_score": 94.0,
                    "is_locked": True,
                    "locked_at": "2026-04-01T09:00:00+07:00",
                    "satisfied_items": ["D-06-QUORUM", "D-07-SIGNED"],
                    "missing_items": [],
                    "origin": "proactive",
                }
            ]
        }
    )
    out = await handle_show_document_indicators(
        {"doc_id": str(doc_id), "doc_type": "mom"}, api_mock, user
    )
    assert "Divestasi Hotel Jaya" in out
    assert "🔒" in out
    assert "D-06-QUORUM" in out or "✓" in out


@pytest.mark.asyncio
async def test_show_document_indicators_silently_omits_when_empty(api_mock, user):
    """Spec § 5.2: empty indicator list is silent (empty string), never noisy."""
    api_mock.get_bjr_indicators = AsyncMock(return_value={"indicators": []})
    out = await handle_show_document_indicators(
        {"doc_id": str(uuid.uuid4()), "doc_type": "mom"}, api_mock, user
    )
    assert out == ""


@pytest.mark.asyncio
async def test_show_document_indicators_handles_multiple_decisions(api_mock, user):
    api_mock.get_bjr_indicators = AsyncMock(
        return_value={
            "indicators": [
                {
                    "decision_id": str(uuid.uuid4()),
                    "decision_title": "Decision 1",
                    "status": "bjr_locked",
                    "readiness_score": 95.0,
                    "is_locked": True,
                    "locked_at": "2026-04-01T09:00:00+07:00",
                    "satisfied_items": ["D-06-QUORUM"],
                    "missing_items": [],
                    "origin": "proactive",
                },
                {
                    "decision_id": str(uuid.uuid4()),
                    "decision_title": "Decision 2",
                    "status": "dd_in_progress",
                    "readiness_score": 72.0,
                    "is_locked": False,
                    "locked_at": None,
                    "satisfied_items": ["D-06-QUORUM"],
                    "missing_items": ["PD-01-DD", "PD-05-COI"],
                    "origin": "proactive",
                },
            ]
        }
    )
    out = await handle_show_document_indicators(
        {"doc_id": str(uuid.uuid4()), "doc_type": "mom"}, api_mock, user
    )
    assert "Decision 1" in out
    assert "Decision 2" in out
    assert "🔒" in out
    assert "🟡" in out


@pytest.mark.asyncio
async def test_show_document_indicators_missing_doc_id_returns_empty(api_mock, user):
    """Proactive tool: silent when arguments are invalid — Gemini may still
    attempt the call when it misidentifies a doc reference."""
    out = await handle_show_document_indicators(
        {"doc_type": "mom"}, api_mock, user
    )
    assert out == ""
    api_mock.get_bjr_indicators.assert_not_called()


@pytest.mark.asyncio
async def test_show_decision_evidence_renders_by_phase(api_mock, user):
    did = uuid.uuid4()
    api_mock.get_decision_evidence = AsyncMock(
        return_value={
            "evidence": [
                {
                    "evidence_id": str(uuid.uuid4()),
                    "evidence_type": "dd_report",
                    "title": "DD Report #42",
                    "satisfies_items": ["PD-01-DD"],
                },
                {
                    "evidence_id": str(uuid.uuid4()),
                    "evidence_type": "mom",
                    "title": "MoM BOD #5/2026",
                    "satisfies_items": ["D-06-QUORUM", "D-07-SIGNED"],
                },
            ]
        }
    )
    out = await handle_show_decision_evidence(
        {"decision_id": str(did)}, api_mock, user
    )
    assert "DD Report #42" in out
    assert "MoM BOD #5/2026" in out
    assert "PD-01-DD" in out


@pytest.mark.asyncio
async def test_show_decision_evidence_missing_id_returns_error(api_mock, user):
    out = await handle_show_decision_evidence({}, api_mock, user)
    assert "decision_id" in out.lower()
```

- [ ] **Step 2: Run tests to verify failure**

```bash
PYTHONPATH=packages/ancol-common/src:services/gemini-agent/src python3 -m pytest services/gemini-agent/tests/test_tools_bjr_evidence.py -v
```
Expected: 6 FAIL.

- [ ] **Step 3: Extend `formatting_bjr.py`**

Append to `services/gemini-agent/src/gemini_agent/formatting_bjr.py`:

```python
def format_document_indicators(indicators: list[dict]) -> str:
    """Render per-document BJR indicators as a chat card.

    Returns empty string if the list is empty — chat response stays silent
    when a document has no BJR context (spec § 5.2).
    """
    if not indicators:
        return ""

    lines = [f"\nSupports {len(indicators)} strategic decision(s):"]
    for ind in indicators[:5]:  # truncate to 5 for chat readability
        is_locked = ind.get("is_locked", False)
        readiness = ind.get("readiness_score")
        emoji = _state_emoji(ind.get("status", ""), is_locked, readiness)
        title = ind.get("decision_title", "(untitled)")

        if is_locked:
            lines.append(f"\n  {emoji} **{title}**")
            lines.append(f"     readiness {readiness:.0f}/100 • LOCKED {ind.get('locked_at', '')[:10]}")
        else:
            r_str = f"{readiness:.0f}/100" if readiness is not None else "—"
            lines.append(f"\n  {emoji} **{title}**")
            lines.append(f"     readiness {r_str} • status `{ind.get('status', '?')}`")

        sat = ind.get("satisfied_items", [])
        missing = ind.get("missing_items", [])
        if sat:
            sat_str = " ".join(f"`{c}` ✓" for c in sat[:4])
            extra = f" (+{len(sat)-4} more)" if len(sat) > 4 else ""
            lines.append(f"     Satisfies: {sat_str}{extra}")
        if missing:
            miss_str = " ".join(f"`{c}` ⚠" for c in missing[:4])
            extra = f" (+{len(missing)-4} more)" if len(missing) > 4 else ""
            lines.append(f"     Missing:   {miss_str}{extra}")

    if len(indicators) > 5:
        lines.append(f"\n_(+{len(indicators) - 5} more decision(s) — ask for details)_")
    return "\n".join(lines)


def format_decision_evidence(payload: dict) -> str:
    """Render decision -> evidence list grouped by evidence type."""
    items: list[dict[str, Any]] = payload.get("evidence", [])
    if not items:
        return "Belum ada evidence terhubung ke decision ini."

    by_type: dict[str, list[dict]] = {}
    for ev in items:
        by_type.setdefault(ev.get("evidence_type", "other"), []).append(ev)

    lines = ["**Evidence untuk decision ini:**"]
    for ev_type, evs in by_type.items():
        lines.append(f"\n**{ev_type}** ({len(evs)}):")
        for ev in evs:
            sat = ev.get("satisfies_items", [])
            sat_str = " ".join(f"`{c}`" for c in sat) if sat else "_(belum dipetakan ke item)_"
            lines.append(f"  - **{ev.get('title', '—')}** — {sat_str}")
    return "\n".join(lines)
```

- [ ] **Step 4: Create `bjr_evidence.py`**

Create `services/gemini-agent/src/gemini_agent/tools/bjr_evidence.py`:
```python
"""BJR evidence chat tool handlers (read-only).

Two tools:
- `show_document_indicators(doc_id, doc_type)` — proactive indicator on
  every document mention (see spec § 5.2). Silent when the doc has no
  BJR context.
- `show_decision_evidence(decision_id)` — inverse: list all evidence
  linked to a decision, grouped by evidence type.
"""

from __future__ import annotations

import logging

from gemini_agent.api_client import ApiClient
from gemini_agent.formatting_bjr import (
    format_decision_evidence,
    format_document_indicators,
)

logger = logging.getLogger(__name__)


async def handle_show_document_indicators(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Proactive BJR indicator for a document.

    Returns empty string when the doc_id is missing or no decisions
    reference the document. This is intentional — the LLM calls this
    speculatively whenever it mentions a doc; a silent response means
    "no BJR context here" and the conversation continues unaltered.
    """
    doc_id: str = (params.get("doc_id") or "").strip()
    if not doc_id:
        return ""

    try:
        payload = await api.get_bjr_indicators(doc_id)
    except Exception:
        logger.exception("get_bjr_indicators failed for doc %s", doc_id)
        return ""

    indicators = payload.get("indicators", [])
    return format_document_indicators(indicators)


async def handle_show_decision_evidence(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """List all evidence linked to a decision, grouped by evidence type."""
    decision_id: str = (params.get("decision_id") or "").strip()
    if not decision_id:
        return "Error: Harap berikan `decision_id`."

    try:
        payload = await api.get_decision_evidence(decision_id)
    except Exception:
        logger.exception("get_decision_evidence failed for %s", decision_id)
        return f"Gagal mengambil evidence untuk `{decision_id}`."

    return format_decision_evidence(payload)
```

- [ ] **Step 5: Run tests to verify pass**

```bash
PYTHONPATH=packages/ancol-common/src:services/gemini-agent/src python3 -m pytest services/gemini-agent/tests/test_tools_bjr_evidence.py -v
```
Expected: 6 PASS.

- [ ] **Step 6: Lint + commit**

```bash
ruff check services/gemini-agent/src/gemini_agent/tools/bjr_evidence.py services/gemini-agent/src/gemini_agent/formatting_bjr.py services/gemini-agent/tests/test_tools_bjr_evidence.py
ruff format services/gemini-agent/src/gemini_agent/tools/bjr_evidence.py services/gemini-agent/src/gemini_agent/formatting_bjr.py services/gemini-agent/tests/test_tools_bjr_evidence.py

git add services/gemini-agent/src/gemini_agent/tools/bjr_evidence.py services/gemini-agent/src/gemini_agent/formatting_bjr.py services/gemini-agent/tests/test_tools_bjr_evidence.py
git commit -m "feat(gemini-agent): bjr_evidence tool handlers

show_document_indicators returns a markdown-formatted card listing
every decision a document supports + satisfied/missing items. Empty
list returns empty string (silent — spec § 5.2 proactive model).
Truncates at 5 decisions for chat readability.

show_decision_evidence is the reverse: list all evidence for a
decision grouped by evidence type, with per-evidence item codes.

6 unit tests covering single decision, empty-silent, multi-decision,
missing doc_id (silent), evidence grouping, and missing decision_id."
```

---

## Task 10: `bjr_passport.py` chat tool handler

**Why:** Single tool — `get_passport_url(decision_id)` — returns a signed GCS URL to the locked decision's Passport PDF. Only works for locked decisions.

**Files:**
- Create: `services/gemini-agent/src/gemini_agent/tools/bjr_passport.py`
- Create: `services/gemini-agent/tests/test_tools_bjr_passport.py`

- [ ] **Step 1: Write failing test**

Create `services/gemini-agent/tests/test_tools_bjr_passport.py`:
```python
"""Unit tests for bjr_passport chat tool handler."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from gemini_agent.tools.bjr_passport import handle_get_passport_url


@pytest.fixture
def user() -> dict:
    return {"email": "direksi@ancol.test", "role": "direksi"}


@pytest.fixture
def api_mock():
    return AsyncMock()


@pytest.mark.asyncio
async def test_get_passport_url_returns_signed_link(api_mock, user):
    did = uuid.uuid4()
    api_mock.get_passport_url = AsyncMock(
        return_value={
            "signed_url": "https://storage.googleapis.com/bucket/passport-x.pdf?sig=abc",
            "expires_at": "2026-04-18T09:00:00+07:00",
        }
    )
    out = await handle_get_passport_url({"decision_id": str(did)}, api_mock, user)
    assert "storage.googleapis.com" in out
    assert "expires" in out.lower() or "valid" in out.lower() or "berlaku" in out.lower()


@pytest.mark.asyncio
async def test_get_passport_url_missing_id(api_mock, user):
    out = await handle_get_passport_url({}, api_mock, user)
    assert "decision_id" in out.lower()
    api_mock.get_passport_url.assert_not_called()


@pytest.mark.asyncio
async def test_get_passport_url_decision_not_locked(api_mock, user):
    """API returns 409 Conflict when decision is not locked yet."""
    from httpx import HTTPStatusError

    api_mock.get_passport_url = AsyncMock(
        side_effect=HTTPStatusError(
            "409 Conflict",
            request=None,
            response=AsyncMock(status_code=409, text="decision not locked"),
        )
    )
    out = await handle_get_passport_url(
        {"decision_id": str(uuid.uuid4())}, api_mock, user
    )
    assert "belum" in out.lower() or "not locked" in out.lower() or "tidak" in out.lower()


@pytest.mark.asyncio
async def test_get_passport_url_generic_error(api_mock, user):
    api_mock.get_passport_url = AsyncMock(side_effect=Exception("boom"))
    out = await handle_get_passport_url(
        {"decision_id": str(uuid.uuid4())}, api_mock, user
    )
    assert "gagal" in out.lower() or "error" in out.lower()
```

- [ ] **Step 2: Run test to verify failure**

```bash
PYTHONPATH=packages/ancol-common/src:services/gemini-agent/src python3 -m pytest services/gemini-agent/tests/test_tools_bjr_passport.py -v
```
Expected: 4 FAIL.

- [ ] **Step 3: Create `bjr_passport.py`**

Create `services/gemini-agent/src/gemini_agent/tools/bjr_passport.py`:
```python
"""BJR Decision Passport URL tool handler.

Returns a signed GCS URL to a locked decision's Passport PDF. The URL
is short-lived (typically 1h TTL). Direksi/Legal/Komisaris use this
for legal-defensibility downloads.
"""

from __future__ import annotations

import logging

from httpx import HTTPStatusError

from gemini_agent.api_client import ApiClient

logger = logging.getLogger(__name__)


async def handle_get_passport_url(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Fetch a signed Passport PDF URL for a locked decision."""
    decision_id: str = (params.get("decision_id") or "").strip()
    if not decision_id:
        return "Error: Harap berikan `decision_id` untuk mengambil Passport PDF."

    try:
        result = await api.get_passport_url(decision_id)
    except HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        if status == 409:
            return (
                f"Decision `{decision_id}` belum terkunci (Gate 5 belum selesai). "
                "Passport PDF akan tersedia setelah decision di-lock."
            )
        if status == 404:
            return f"Decision `{decision_id}` tidak ditemukan."
        logger.exception("get_passport_url HTTP error for %s", decision_id)
        return f"Gagal mengambil Passport untuk `{decision_id}`."
    except Exception:
        logger.exception("get_passport_url failed for %s", decision_id)
        return f"Gagal mengambil Passport untuk `{decision_id}`."

    url = result.get("signed_url", "")
    expires = result.get("expires_at", "")
    return (
        f"📄 **Decision Passport PDF siap:**\n{url}\n"
        f"Link berlaku sampai: {expires}"
    )
```

- [ ] **Step 4: Run tests to verify pass**

```bash
PYTHONPATH=packages/ancol-common/src:services/gemini-agent/src python3 -m pytest services/gemini-agent/tests/test_tools_bjr_passport.py -v
```
Expected: 4 PASS.

- [ ] **Step 5: Lint + commit**

```bash
ruff check services/gemini-agent/src/gemini_agent/tools/bjr_passport.py services/gemini-agent/tests/test_tools_bjr_passport.py
ruff format services/gemini-agent/src/gemini_agent/tools/bjr_passport.py services/gemini-agent/tests/test_tools_bjr_passport.py

git add services/gemini-agent/src/gemini_agent/tools/bjr_passport.py services/gemini-agent/tests/test_tools_bjr_passport.py
git commit -m "feat(gemini-agent): bjr_passport.get_passport_url tool handler

Returns a signed GCS URL for a locked decision's Passport PDF. Gracefully
handles 409 Conflict (decision not locked yet) and 404 Not Found with
user-friendly Indonesian error messages. Generic error fallback for
unexpected exceptions.

4 unit tests."
```

---

## Task 11: Dispatcher + RBAC wiring in `main.py`

**Why:** The 10 new tools need to route from the webhook dispatcher to their handlers, and each role's `allowed` set needs to include the right tools per spec § 4.2.

**Files:**
- Modify: `services/gemini-agent/src/gemini_agent/main.py`
- Create: `services/gemini-agent/tests/test_main_bjr_dispatch.py`

- [ ] **Step 1: Write failing dispatcher + RBAC tests**

Create `services/gemini-agent/tests/test_main_bjr_dispatch.py`:
```python
"""Dispatcher + RBAC contract tests for the new BJR tool handlers."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from gemini_agent.main import _dispatch_tool, _role_allowed_tools


@pytest.mark.asyncio
async def test_dispatch_get_decision_routes_to_handler(monkeypatch):
    called = {}
    async def fake_handle_get_decision(params, api, user):
        called["ok"] = True
        return "ok"
    monkeypatch.setattr(
        "gemini_agent.tools.bjr_decisions.handle_get_decision",
        fake_handle_get_decision,
    )
    api = AsyncMock()
    user = {"email": "x@a.test", "role": "admin"}
    result = await _dispatch_tool(
        "get_decision", {"decision_id": str(uuid.uuid4())}, api, user
    )
    assert called.get("ok") is True
    assert result == "ok"


@pytest.mark.asyncio
async def test_dispatch_unknown_tool_raises():
    api = AsyncMock()
    user = {"email": "x@a.test", "role": "admin"}
    with pytest.raises(ValueError, match="Unknown tool"):
        await _dispatch_tool("nonexistent_tool", {}, api, user)


@pytest.mark.parametrize(
    "role,tool,should_allow",
    [
        # admin has everything
        ("admin", "get_decision", True),
        ("admin", "get_readiness", True),
        ("admin", "show_document_indicators", True),
        ("admin", "get_passport_url", True),
        # business_dev: read decisions, read readiness, see indicators
        ("business_dev", "get_decision", True),
        ("business_dev", "show_document_indicators", True),
        # direksi: only passport + readiness for own decisions
        ("direksi", "get_passport_url", True),
        ("direksi", "get_readiness", True),
        ("direksi", "list_my_decisions", True),
        # corp_secretary: all read-only BJR tools
        ("corp_secretary", "show_document_indicators", True),
        ("corp_secretary", "show_decision_evidence", True),
        # komisaris: read-only, passport, indicators
        ("komisaris", "get_readiness", True),
        ("komisaris", "show_document_indicators", True),
        ("komisaris", "get_passport_url", True),
        # dewan_pengawas: same as komisaris
        ("dewan_pengawas", "get_readiness", True),
        # legal_compliance: read
        ("legal_compliance", "show_document_indicators", True),
        # internal_auditor: read
        ("internal_auditor", "show_decision_evidence", True),
    ],
)
def test_role_has_bjr_tool(role: str, tool: str, should_allow: bool):
    allowed = _role_allowed_tools(role)
    assert (tool in allowed) == should_allow, f"{role} should {'have' if should_allow else 'not have'} {tool}"


def test_all_bjr_tools_in_admin_allowed():
    admin_tools = _role_allowed_tools("admin")
    expected_bjr_tools = {
        "get_decision", "list_decisions", "list_my_decisions",
        "get_readiness", "get_checklist",
        "show_document_indicators", "show_decision_evidence",
        "get_passport_url",
    }
    missing = expected_bjr_tools - admin_tools
    assert not missing, f"admin missing BJR tools: {missing}"
```

- [ ] **Step 2: Run test to verify failure**

```bash
PYTHONPATH=packages/ancol-common/src:services/gemini-agent/src python3 -m pytest services/gemini-agent/tests/test_main_bjr_dispatch.py -v
```
Expected: FAIL — `_role_allowed_tools` may not exist (check `main.py`); BJR tool names unknown to dispatcher.

- [ ] **Step 3: Open `main.py` and review the existing dispatcher**

Run:
```bash
grep -n "def _dispatch_tool\|tool_name ==\|allowed = \|allowed_tools" services/gemini-agent/src/gemini_agent/main.py
```

Confirm the existing structure (current shape: `if tool_name == "foo": return await handle_foo(...)`). The existing code likely has an inline `allowed` set per role inside `_handle_tool_call`. If no `_role_allowed_tools` helper exists yet, extract it now.

- [ ] **Step 4: Add BJR tools to dispatcher + refactor RBAC into `_role_allowed_tools`**

Open `services/gemini-agent/src/gemini_agent/main.py`.

Add these imports near the top with other tool imports:
```python
from gemini_agent.tools.bjr_decisions import (
    handle_get_decision,
    handle_list_decisions,
    handle_list_my_decisions,
)
from gemini_agent.tools.bjr_readiness import (
    handle_get_checklist,
    handle_get_readiness,
)
from gemini_agent.tools.bjr_evidence import (
    handle_show_decision_evidence,
    handle_show_document_indicators,
)
from gemini_agent.tools.bjr_passport import handle_get_passport_url
```

In `_dispatch_tool`, append these branches after the existing `if tool_name == "..."` chain (before `raise ValueError`):
```python
    # BJR read-only tools (Phase 6.4a)
    if tool_name == "get_decision":
        return await handle_get_decision(params, api, user)
    if tool_name == "list_decisions":
        return await handle_list_decisions(params, api, user)
    if tool_name == "list_my_decisions":
        return await handle_list_my_decisions(params, api, user)
    if tool_name == "get_readiness":
        return await handle_get_readiness(params, api, user)
    if tool_name == "get_checklist":
        return await handle_get_checklist(params, api, user)
    if tool_name == "show_document_indicators":
        return await handle_show_document_indicators(params, api, user)
    if tool_name == "show_decision_evidence":
        return await handle_show_decision_evidence(params, api, user)
    if tool_name == "get_passport_url":
        return await handle_get_passport_url(params, api, user)
```

Extract the role-to-allowed-tools mapping into a module-level dict. Near the top of `main.py` (after imports, before `_dispatch_tool`):
```python
# Role → allowed tool names. Chat-side RBAC: dispatcher rejects disallowed
# calls with a structured error. Server-side RBAC (require_permission in
# API Gateway) is the authoritative check; this is a first-line defense.
_ROLE_ALLOWED_TOOLS: dict[str, frozenset[str]] = {
    # Non-BJR baseline tools (keep existing list; edit to include your current set)
    # --- The list below MUST match what the existing main.py already has ---
    # (Read existing _role_allowed_tools or inline allowed assignments and
    #  replicate the baseline here before adding BJR tools below.)
}


def _role_allowed_tools(role: str) -> frozenset[str]:
    """Return the set of tool names a role may invoke from chat."""
    return _ROLE_ALLOWED_TOOLS.get(role, frozenset())
```

Now define the baseline + BJR union. (Replace the placeholder dict above with this full definition once you've confirmed the existing non-BJR tools. Example with baseline = empty; if baseline exists, merge with `| {non_bjr_tools}`.)

```python
_BJR_READ_TOOLS = frozenset({
    "get_decision", "list_decisions", "list_my_decisions",
    "get_readiness", "get_checklist",
    "show_document_indicators", "show_decision_evidence",
    "get_passport_url",
})

_BJR_INDICATOR_TOOLS = frozenset({
    "show_document_indicators", "show_decision_evidence",
})

# Per spec § 4.2 — what each role sees
_ROLE_ALLOWED_TOOLS = {
    "admin": _BJR_READ_TOOLS | _EXISTING_ADMIN_BASELINE,  # define _EXISTING_ADMIN_BASELINE by reading current code
    "business_dev": _BJR_READ_TOOLS - {"get_passport_url"} | _EXISTING_BUSINESS_DEV_BASELINE,
    "corp_secretary": _BJR_READ_TOOLS | _EXISTING_CORP_SEC_BASELINE,
    "legal_compliance": _BJR_READ_TOOLS | _EXISTING_LEGAL_BASELINE,
    "internal_auditor": _BJR_READ_TOOLS | _EXISTING_AUDITOR_BASELINE,
    "komisaris": frozenset({
        "get_decision", "list_decisions",
        "get_readiness", "get_checklist",
        "show_document_indicators", "show_decision_evidence",
        "get_passport_url",
    }) | _EXISTING_KOMISARIS_BASELINE,
    "dewan_pengawas": frozenset({
        "get_decision", "list_decisions",
        "get_readiness", "get_checklist",
        "show_document_indicators", "show_decision_evidence",
        "get_passport_url",
    }) | _EXISTING_DEWAN_BASELINE,
    "direksi": frozenset({
        "list_my_decisions", "get_decision",
        "get_readiness", "get_checklist",
        "show_document_indicators",
        "get_passport_url",
    }) | _EXISTING_DIREKSI_BASELINE,
}
```

**CRITICAL:** replace each `_EXISTING_<ROLE>_BASELINE` placeholder with the actual baseline tool set from the current `main.py`. Do this by reading the file and inlining. Do NOT commit placeholders.

Update the existing RBAC check in the webhook handler to use `_role_allowed_tools`:
```python
user_role = user.get("role", "")
allowed = _role_allowed_tools(user_role)
if tool_name not in allowed:
    logger.warning("Access denied: role=%s tool=%s", user_role, tool_name)
    # ... existing denial response unchanged ...
```

- [ ] **Step 5: Run tests to verify pass**

```bash
PYTHONPATH=packages/ancol-common/src:services/gemini-agent/src python3 -m pytest services/gemini-agent/tests/test_main_bjr_dispatch.py -v
```
Expected: all PASS.

Run full gemini-agent suite:
```bash
PYTHONPATH=packages/ancol-common/src:services/gemini-agent/src python3 -m pytest services/gemini-agent/tests/ -q
```
Expected: existing 61 + new BJR tests (28 new: 6+5+6+4+7) = ~89 total. Zero regressions.

- [ ] **Step 6: Lint + commit**

```bash
ruff check services/gemini-agent/src/gemini_agent/main.py services/gemini-agent/tests/test_main_bjr_dispatch.py
ruff format services/gemini-agent/src/gemini_agent/main.py services/gemini-agent/tests/test_main_bjr_dispatch.py

git add services/gemini-agent/src/gemini_agent/main.py services/gemini-agent/tests/test_main_bjr_dispatch.py
git commit -m "feat(gemini-agent): wire 8 BJR read-only tools into dispatcher + RBAC

8 new tool name routes added to _dispatch_tool. RBAC extracted into
_ROLE_ALLOWED_TOOLS module constant + _role_allowed_tools helper,
with per-role allowed sets per spec § 4.2.

7 dispatcher tests + 18 RBAC parametrized cases. All 543 baseline
tests pass unchanged."
```

---

## Task 12: Graph backfill script

**Why:** The graph needs to be populated from existing PG state (`strategic_decisions`, `decision_evidence`, `bjr_checklist_items`) before the chat tools can meaningfully show indicators. Script must be idempotent (re-run safe) and fast (<5 min for current volume).

**Files:**
- Create: `scripts/bjr_graph_backfill.py`
- Create: `scripts/tests/test_bjr_graph_backfill.py`

- [ ] **Step 1: Write failing tests**

Create `scripts/tests/__init__.py` (empty) and `scripts/tests/test_bjr_graph_backfill.py`:

```python
"""Tests for the BJR graph backfill script."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from scripts.bjr_graph_backfill import (
    backfill_all,
    backfill_decision_edges,
    backfill_decisions,
)


class _FakeGraphClient:
    """In-memory GraphClient for backfill tests."""

    def __init__(self) -> None:
        self.decisions: dict = {}
        self.supported_by: list = []
        self.satisfies_item: list = []

    async def upsert_decision_node(self, decision) -> None:
        self.decisions[str(decision.id)] = decision

    async def upsert_supported_by_edge(
        self, decision_id, evidence, linked_at, linked_by,
    ) -> None:
        self.supported_by.append((str(decision_id), str(evidence.id), evidence.type))

    async def upsert_satisfies_item_edge(
        self, evidence_id, item_code, decision_id, evaluator_status,
    ) -> None:
        self.satisfies_item.append((str(evidence_id), item_code.value, str(decision_id)))

    async def upsert_approved_by_edge(self, *args, **kwargs) -> None:
        pass

    # Unused methods — required by ABC
    async def query_related_regulations(self, *a, **k): return []
    async def get_amendment_chain(self, *a, **k): return []
    async def find_cross_references(self, *a, **k): return []
    async def get_regulations_by_domain(self, *a, **k): return []
    async def check_active_status(self, *a, **k): return True
    async def get_related_regulations_for_contract(self, *a, **k): return []
    async def get_related_contracts(self, *a, **k): return []
    async def get_document_indicators(self, *a, **k): return []
    async def get_decision_evidence(self, *a, **k): return []


@pytest.mark.asyncio
async def test_backfill_decisions_upserts_all(monkeypatch):
    # Fake session that yields 3 decisions on fetch_all
    fake_decisions = [
        _fake_decision_row(),
        _fake_decision_row(),
        _fake_decision_row(),
    ]
    session = _fake_session_with_decisions(fake_decisions)
    graph = _FakeGraphClient()
    count = await backfill_decisions(session, graph)
    assert count == 3
    assert len(graph.decisions) == 3


@pytest.mark.asyncio
async def test_backfill_is_idempotent():
    """Running backfill twice must produce the same final graph state."""
    fake_decisions = [_fake_decision_row()]
    graph = _FakeGraphClient()
    session1 = _fake_session_with_decisions(fake_decisions)
    await backfill_decisions(session1, graph)
    count_1 = len(graph.decisions)
    session2 = _fake_session_with_decisions(fake_decisions)
    await backfill_decisions(session2, graph)
    count_2 = len(graph.decisions)
    assert count_1 == count_2  # upsert semantics ensure no duplication


@pytest.mark.asyncio
async def test_backfill_all_wires_decisions_and_edges():
    """End-to-end: backfill_all populates decisions + edges."""
    fake_decisions = [_fake_decision_row()]
    fake_evidence = [_fake_evidence_row()]
    fake_checklist = [_fake_checklist_row()]
    session = _fake_full_session(fake_decisions, fake_evidence, fake_checklist)
    graph = _FakeGraphClient()
    stats = await backfill_all(session, graph)
    assert stats["decisions"] == 1
    assert stats["edges"] >= 1
    assert len(graph.decisions) == 1
    assert len(graph.supported_by) >= 1


# ── Fixtures ────────────────────────────────────────────────────────────

def _fake_decision_row():
    return {
        "id": uuid.uuid4(),
        "title": "Test Decision",
        "status": "ideation",
        "readiness_score": None,
        "corporate_score": None,
        "regional_score": None,
        "locked_at": None,
        "initiative_type": "acquisition",
        "origin": "proactive",
    }


def _fake_evidence_row():
    return {
        "decision_id": uuid.uuid4(),
        "evidence_type": "mom",
        "evidence_id": uuid.uuid4(),
        "linked_by": uuid.uuid4(),
        "created_at": datetime.now(timezone.utc),
    }


def _fake_checklist_row():
    return {
        "decision_id": uuid.uuid4(),
        "item_code": "D-06-QUORUM",
        "status": "satisfied",
        "evidence_ids": [uuid.uuid4()],
    }


def _fake_session_with_decisions(rows):
    session = AsyncMock()
    result = AsyncMock()
    result.mappings = AsyncMock(return_value=[{**r} for r in rows])
    result.fetchall = AsyncMock(return_value=rows)
    session.execute = AsyncMock(return_value=result)
    return session


def _fake_full_session(decisions, evidence, checklist):
    """Session whose execute returns different rowsets depending on query."""
    session = AsyncMock()

    async def fake_execute(stmt, *args, **kwargs):
        result = AsyncMock()
        stmt_str = str(stmt).lower()
        if "strategic_decisions" in stmt_str:
            result.mappings = AsyncMock(return_value=decisions)
        elif "decision_evidence" in stmt_str:
            result.mappings = AsyncMock(return_value=evidence)
        elif "bjr_checklist_items" in stmt_str:
            result.mappings = AsyncMock(return_value=checklist)
        else:
            result.mappings = AsyncMock(return_value=[])
        result.fetchall = AsyncMock(return_value=[])
        return result

    session.execute = fake_execute
    return session
```

- [ ] **Step 2: Run tests to verify failure**

```bash
PYTHONPATH=packages/ancol-common/src:scripts python3 -m pytest scripts/tests/test_bjr_graph_backfill.py -v
```
Expected: 3 FAIL — `ModuleNotFoundError: No module named 'scripts.bjr_graph_backfill'`.

- [ ] **Step 3: Create the backfill script**

Create `scripts/__init__.py` (empty) if it doesn't exist, then `scripts/bjr_graph_backfill.py`:

```python
"""BJR graph backfill — populate Decision + edges from existing PG state.

Idempotent — safe to re-run. Uses the standard GraphClient upsert methods
which MERGE rather than INSERT. Total runtime: a few minutes for the
current ~0-10 decision volume; will scale to ~500+ after Phase 6.5
historical migration.

Usage:
    PYTHONPATH=packages/ancol-common/src python3 scripts/bjr_graph_backfill.py [--dry-run]

Environment: uses same DATABASE_URL + graph backend envs as the rest of
the system (see packages/ancol-common/src/ancol_common/config.py).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ancol_common.config import get_settings
from ancol_common.rag.graph_client import GraphClient
from ancol_common.rag.models import DecisionNode, EvidenceNode
from ancol_common.schemas.bjr import BJRItemCode

logger = logging.getLogger(__name__)


def _build_graph_client() -> GraphClient:
    """Construct the GraphClient based on GRAPH_BACKEND env."""
    backend = os.getenv("GRAPH_BACKEND", "spanner").lower()
    if backend == "neo4j":
        from ancol_common.rag.neo4j_graph import Neo4jGraphClient
        return Neo4jGraphClient(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
        )
    if backend == "spanner":
        from ancol_common.rag.spanner_graph import SpannerGraphClient
        return SpannerGraphClient(
            project_id=os.getenv("GCP_PROJECT_ID", ""),
            instance_id=os.getenv("SPANNER_INSTANCE_ID", ""),
            database_id=os.getenv("SPANNER_DATABASE_ID", ""),
        )
    raise ValueError(f"Unknown GRAPH_BACKEND={backend!r}; expected neo4j|spanner")


async def backfill_decisions(session: AsyncSession, graph: GraphClient) -> int:
    """Read strategic_decisions and upsert Decision nodes. Return count."""
    stmt = text("""
        SELECT id, title, status, readiness_score, corporate_score,
               regional_score, locked_at, initiative_type, origin, created_at
        FROM strategic_decisions
    """)
    result = await session.execute(stmt)
    rows = result.mappings()
    # Support both sync-style list and async iterator returns
    rows = rows if isinstance(rows, list) else await (rows if hasattr(rows, '__aiter__') else _as_list(rows))

    count = 0
    for row in rows:
        decision = DecisionNode(
            id=row["id"],
            title=row["title"],
            status=row["status"],
            readiness_score=row.get("readiness_score"),
            corporate_score=row.get("corporate_score"),
            regional_score=row.get("regional_score"),
            locked_at=row.get("locked_at"),
            initiative_type=row["initiative_type"],
            origin=row.get("origin", "proactive"),
            created_at=row.get("created_at"),
        )
        await graph.upsert_decision_node(decision)
        count += 1
    logger.info("Backfilled %d Decision nodes", count)
    return count


async def backfill_decision_edges(
    session: AsyncSession,
    graph: GraphClient,
) -> int:
    """Read decision_evidence + bjr_checklist_items, upsert edges."""
    # SUPPORTED_BY edges
    stmt_ev = text("""
        SELECT decision_id, evidence_type, evidence_id,
               linked_by, created_at
        FROM decision_evidence
    """)
    result = await session.execute(stmt_ev)
    ev_rows = result.mappings()
    ev_rows = ev_rows if isinstance(ev_rows, list) else await _as_list(ev_rows)
    supported_count = 0
    for row in ev_rows:
        ev = EvidenceNode(id=row["evidence_id"], type=row["evidence_type"])
        await graph.upsert_supported_by_edge(
            decision_id=row["decision_id"],
            evidence=ev,
            linked_at=row["created_at"],
            linked_by=row["linked_by"],
        )
        supported_count += 1

    # SATISFIES_ITEM edges (from bjr_checklist_items + their evidence_ids)
    stmt_items = text("""
        SELECT decision_id, item_code, status, evidence_ids
        FROM bjr_checklist_items
    """)
    result = await session.execute(stmt_items)
    item_rows = result.mappings()
    item_rows = item_rows if isinstance(item_rows, list) else await _as_list(item_rows)
    satisfies_count = 0
    for row in item_rows:
        evidence_ids = row.get("evidence_ids") or []
        for ev_id in evidence_ids:
            await graph.upsert_satisfies_item_edge(
                evidence_id=ev_id,
                item_code=BJRItemCode(row["item_code"]),
                decision_id=row["decision_id"],
                evaluator_status=row["status"],
            )
            satisfies_count += 1

    total = supported_count + satisfies_count
    logger.info(
        "Backfilled %d SUPPORTED_BY + %d SATISFIES_ITEM edges",
        supported_count, satisfies_count,
    )
    return total


async def backfill_all(session: AsyncSession, graph: GraphClient) -> dict[str, int]:
    """Run the full backfill: decisions then edges. Return stats."""
    decisions = await backfill_decisions(session, graph)
    edges = await backfill_decision_edges(session, graph)
    return {"decisions": decisions, "edges": edges}


async def _as_list(iter_or_list: Any) -> list[Any]:
    """Normalize SQLAlchemy result.mappings() across versions."""
    if isinstance(iter_or_list, list):
        return iter_or_list
    out: list[Any] = []
    async for item in iter_or_list:
        out.append(item)
    return out


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    graph = _build_graph_client()

    async with AsyncSession(engine) as session:
        if args.dry_run:
            logger.info("DRY RUN — counting source rows only")
            result = await session.execute(text("SELECT COUNT(*) FROM strategic_decisions"))
            n_decisions = result.scalar_one()
            result = await session.execute(text("SELECT COUNT(*) FROM decision_evidence"))
            n_edges = result.scalar_one()
            result = await session.execute(text("SELECT COUNT(*) FROM bjr_checklist_items"))
            n_items = result.scalar_one()
            logger.info(
                "Would backfill: %d decisions, %d SUPPORTED_BY edges, %d checklist rows",
                n_decisions, n_edges, n_items,
            )
            return 0

        stats = await backfill_all(session, graph)
        logger.info("Backfill complete: %s", stats)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 4: Run tests to verify pass**

```bash
PYTHONPATH=packages/ancol-common/src:scripts python3 -m pytest scripts/tests/test_bjr_graph_backfill.py -v
```
Expected: 3 PASS.

- [ ] **Step 5: Dry-run smoke test**

If you have a dev DB with sample data:
```bash
PYTHONPATH=packages/ancol-common/src python3 scripts/bjr_graph_backfill.py --dry-run
```
Expected: logs row counts without crashing.

If no dev DB is available, skip the smoke test (tests cover the logic).

- [ ] **Step 6: Lint + commit**

```bash
ruff check scripts/bjr_graph_backfill.py scripts/tests/test_bjr_graph_backfill.py
ruff format scripts/bjr_graph_backfill.py scripts/tests/test_bjr_graph_backfill.py

git add scripts/bjr_graph_backfill.py scripts/tests/test_bjr_graph_backfill.py scripts/__init__.py scripts/tests/__init__.py
git commit -m "feat(scripts): BJR graph backfill from PG (idempotent)

Reads strategic_decisions, decision_evidence, bjr_checklist_items
and upserts Decision nodes + SUPPORTED_BY + SATISFIES_ITEM edges.
Uses MERGE semantics from graph_client — re-running produces the
same final state.

Supports --dry-run for row-count check without writes.

3 unit tests with in-memory FakeGraphClient: happy path, idempotency,
end-to-end decisions + edges wiring."
```

---

## Task 13: Vertex AI Agent Builder region verification (blocker gate)

**Why:** Data sovereignty requires `asia-southeast2` (Jakarta). This must be verified before Phase 6.4b starts — the whole chat-first approach depends on it.

**Files:**
- Create: `docs/RUNBOOK-agent-builder-region-verification.md`

- [ ] **Step 1: Create the runbook**

Create `docs/RUNBOOK-agent-builder-region-verification.md`:
```markdown
# Runbook: Vertex AI Agent Builder — Region Verification

**Why:** BJR design places Gemini Enterprise as primary UI. All chat payloads
include sensitive BJR context (RKAB values, DD findings, COI names). Indonesian
data sovereignty law + internal policy pin all personal + financial data to
`asia-southeast2` (Jakarta). We must confirm Agent Builder respects this.

**Owner:** Erik Gunawan + Platform team
**When:** Week 1 of Phase 6.4a
**Blocker:** Phase 6.4b does NOT start until this is complete.

## What to verify

1. **Agent resource location.** The Vertex AI Agent Builder agent must be
   created in `asia-southeast2` (not `global`, not `us-central1`).
2. **Model routing.** The Gemini model the agent uses must serve from
   `asia-southeast2`. If a model is only available in `asia-southeast1`
   (Singapore), escalate for approval before use.
3. **Conversation storage.** Whether Agent Builder retains chat history
   in-region. Confirm in writing with GCP support.
4. **Tool-call payload routing.** Our webhook is a Cloud Run service we
   deploy to `asia-southeast2` — this part is under our control.
5. **Logging region.** Cloud Logging sinks for Agent Builder events must
   also be regional.

## Steps

1. **Open a GCP Support case** (Premium/Enhanced tier).
   - Subject: "Data residency confirmation: Vertex AI Agent Builder + Gemini in asia-southeast2"
   - Attach this runbook.
   - Ask specifically for written confirmation on points 1-5 above.
2. **In parallel, check the public documentation:**
   - https://cloud.google.com/vertex-ai/docs/general/locations
   - https://cloud.google.com/agent-builder/docs/locations
   - Record findings in `docs/region-verification-findings.md` (new).
3. **If all five points verified in-region:** mark this blocker resolved.
   Move to Phase 6.4b.
4. **If any point lives outside asia-southeast2:**
   a. Escalate to TAM (Technical Account Manager).
   b. Option: use `asia-southeast1` (Singapore) if legal approves — needs
      written sign-off from Legal & Compliance + Dewan Pengawas.
   c. Option: self-host a proxy agent (NOT recommended — high maintenance).
   d. Option: revert to web-primary plan (original Phase 6.4 scope).

## Exit criteria

- [ ] GCP support ticket reply received with in-region confirmation for
      points 1, 2, 3, 5. Point 4 is self-verified (our Cloud Run config).
- [ ] Region findings documented in `docs/region-verification-findings.md`.
- [ ] Screenshot of Agent Builder console showing region attached to
      this runbook.
- [ ] If any item uses `asia-southeast1` fallback: written Legal sign-off
      filed in `docs/legal-approvals/`.

## Rollback / escalation tree

| Finding | Action |
|---|---|
| All 5 in `asia-southeast2` | ✅ proceed to 6.4b |
| Model only in `asia-southeast1` | Legal approval → proceed |
| Conversation storage outside region | Escalate; likely revert to web-primary |
| No in-region option at all | Revert to original web-primary Phase 6.4 plan |
```

- [ ] **Step 2: Commit**

```bash
git add docs/RUNBOOK-agent-builder-region-verification.md
git commit -m "docs: runbook for Agent Builder region verification (blocker gate)

Single-page runbook that Platform team uses to verify Vertex AI Agent
Builder is pinned to asia-southeast2. Gates Phase 6.4b. Includes
escalation tree covering partial-region findings and rollback to
web-primary plan."
```

---

## Task 14: End-of-phase regression + sign-off

- [ ] **Step 1: Run every service's full test suite**

```bash
for svc in extraction-agent legal-research-agent comparison-agent reporting-agent api-gateway batch-engine email-ingest regulation-monitor gemini-agent; do
  echo "=== $svc ==="
  PYTHONPATH=packages/ancol-common/src:services/$svc/src python3 -m pytest services/$svc/tests/ -q
done
```
Expected: all previous 543 + new ~48 tests pass (25 gemini-agent + 5 api-gateway + 13 ancol-common graph + ~7 new fixtures + 3 scripts). Zero regressions.

- [ ] **Step 2: Lint everything that was touched**

```bash
ruff check packages/ services/ scripts/
ruff format --check packages/ services/ scripts/
```
Expected: no errors.

- [ ] **Step 3: ORM smoke test**

```bash
PYTHONPATH=packages/ancol-common/src python3 -c "from ancol_common.db.models import Base; print(f'{len(Base.metadata.tables)} tables')"
```
Expected: `33 tables` (unchanged from v0.4.0.0; no migration this phase).

- [ ] **Step 4: Graph-client smoke test**

```bash
PYTHONPATH=packages/ancol-common/src python3 -c "
from ancol_common.rag import GraphClient
required = {'upsert_decision_node', 'upsert_supported_by_edge', 'upsert_satisfies_item_edge', 'upsert_approved_by_edge', 'get_document_indicators', 'get_decision_evidence'}
missing = required - GraphClient.__abstractmethods__
assert not missing, missing
print('OK: 6 BJR methods on GraphClient abstract')
"
```

- [ ] **Step 5: Update PROGRESS.md**

Open `PROGRESS.md` and append a new checkpoint section at the top (below Current State):
```markdown
## Checkpoint 2026-04-XX (Phase 6.4a — BJR chat read-only + graph)

- **Scope:** Gemini Enterprise chat tools for BJR decision read-only
  (get/list/readiness/checklist/indicators/evidence/passport). GraphClient
  relocated from gemini-agent to ancol-common. 6 new BJR graph methods
  on Neo4j + Spanner. New API Gateway endpoint
  `GET /api/documents/{id}/bjr-indicators`. Idempotent graph backfill
  script. Agent Builder region verification runbook.
- **Files changed:** 20 new + 8 modified. Tests: +48 (591 total).
- **Next:** Phase 6.4b (chat mutations) once region verification completes.
```

- [ ] **Step 6: Commit the checkpoint**

```bash
git add PROGRESS.md
git commit -m "docs: PROGRESS.md checkpoint — Phase 6.4a complete"
```

- [ ] **Step 7: Verify HEAD state**

```bash
git log --oneline -20
git status
```
Expected: clean working tree, ~14 new commits since the pre-phase HEAD.

---

## Summary

At the end of this plan:

- Gemini Enterprise chat can surface any BJR decision: detail, readiness, 16-item checklist, linked evidence, Passport PDF URL.
- Every document mention in chat can render a BJR indicator showing which decisions it supports + per-decision status + satisfied/missing items (once the Agent Builder system prompt directive lands in Phase 6.4b).
- `GraphClient` lives in `packages/ancol-common/rag/` and has 6 new BJR methods on both Neo4j and Spanner.
- `/api/documents/{id}/bjr-indicators` endpoint is live with proper RBAC.
- Graph is backfillable from PG idempotently.
- Data-sovereignty blocker is formalized with an owner and exit criteria.
- 543 existing tests still pass; +48 new tests added.
- Zero DB migrations. Zero changes to BJR scoring engine. Zero changes to existing API routes (except one new one).

**Out of scope (next phases):**
- Chat mutations (create decision, link evidence, retroactive bundling) — Phase 6.4b
- Agent Builder system prompt updates for proactive indicator behavior — Phase 6.4b
- Step-up web + Gate 5 flow — Phase 6.4c
- Migration 006 (step_up_tokens + audit_trail extensions) — Phase 6.4c
- `create_mfa_token` extension to add `jti` claim — Phase 6.4c
- Pub/Sub wiring + historical migration — Phase 6.5
- Load tests — Phase 6.5
- `services/bjr-agent/` extraction — Phase 6.6

---

**Plan confidence: 92%** after self-review (see below).

## Self-review (writing-plans post-check)

**Spec coverage:**
- ✅ Chat read-only tools (§ 9 Phase 6.4a bullet 1-4) → Tasks 7-10
- ✅ GraphClient relocation (§ 9 Phase 6.4a bullet 5) → Task 1
- ✅ Graph extensions (§ 4.6) → Tasks 2-5
- ✅ `/api/documents/{id}/bjr-indicators` (§ 4.1 line 103) → Task 6
- ✅ `scripts/bjr_graph_backfill.py` → Task 12
- ✅ Dispatcher + RBAC updates → Task 11
- ✅ Region verification blocker → Task 13
- ✅ Layer 1 + Layer 3 + Layer 4 tests → distributed across Tasks 2-11

**Placeholder scan:** two placeholder patterns appear in Task 11 Step 4 (`_EXISTING_<ROLE>_BASELINE`). These are deliberately flagged — the implementer must read the current `main.py` and inline the actual baselines. The plan instructs this explicitly and forbids committing placeholders. Not a plan-failure, but worth calling out.

**Type consistency:** `DecisionNode`, `EvidenceNode`, `DocumentIndicator`, `EvidenceSummary`, `Gate5Half`, `BJRItemCode`, `DecisionStatus` used consistently across all tasks. `get_document_indicators(doc_id, doc_type)` signature identical in every reference. Method names match between abstract (Task 3), Neo4j impl (Task 4), Spanner impl (Task 5), API endpoint (Task 6), api_client (Task 7), tool handlers (Task 9).

**Known fragilities the implementer should watch:**
1. **Task 11 placeholders:** as above — must inline baselines before commit.
2. **Task 12 DB schema assumption:** backfill expects `bjr_checklist_items.evidence_ids` to be a JSONB array of UUIDs. Verify against actual schema before first run; may need `json_array_elements` unnesting.
3. **Task 5 Spanner DML syntax:** `MERGE INTO ... USING ... ON ... WHEN MATCHED` is Spanner DML syntax; if the current Spanner tables aren't set up for MERGE, the implementer needs to convert to `INSERT OR UPDATE` depending on Spanner's current capability. Worth a smoke test against a Spanner emulator.
4. **Task 6 `authed_headers_*` fixtures:** the plan assumes these exist OR can be added. If the existing conftest uses a different pattern (e.g., direct mocking of `require_permission`), the implementer should adapt to match.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-17-bjr-gemini-primary-phase-6-4a.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
