# Changelog

All notable changes to the Ancol MoM Compliance System will be documented in this file.

## [0.4.2.0] - 2026-04-18

### Added — Phase 6.4a complete: BJR chat-first interface end-to-end

Closes out Phase 6.4a. The Gemini Enterprise chat interface is now the primary
BJR surface — a user asking "Bagaimana readiness akuisisi X?" routes through
webhook → chat-side RBAC → dispatcher → tool handler → API Gateway → Neo4j
graph → dual-regime scorecard. No web UI required for BJR read operations.

**Tasks landed across 4 PRs (#8, #9, #10, #11):**

- **Task 1** — `rag/` relocated to `packages/ancol-common/` for shared access from API Gateway
- **Task 2** — 7 BJR graph data models (`DecisionNode`, `EvidenceNode`, `ChecklistItemNode`, `DocumentIndicator`, `EvidenceSummary`, `Gate5Half`, `ApprovedByEdge`)
- **Task 3** — `GraphClient` ABC extended with 6 BJR methods (upsert decision/evidence/satisfies/approved + read indicators/evidence)
- **Task 4** — Full `Neo4jGraphClient` Cypher implementation with idempotent MERGE + graceful degradation
- **Task 6** — `GET /api/documents/{id}/bjr-indicators` endpoint + new `bjr:read` permission (8 roles) + module-level graph client factory
- **Task 7** — `bjr_decisions.py` chat tool handlers: `get_decision`, `list_decisions`, `list_my_decisions` + 7 api_client methods batched for Tasks 7-10
- **Task 8** — `bjr_readiness.py` chat tool handlers: `get_readiness` (dual-regime card), `get_checklist` (16-item per-phase grouping with CRITICAL highlighting)
- **Task 9** — `bjr_evidence.py` chat tool handlers: `show_document_indicators` (proactive, silent-when-empty per spec §5.2), `show_decision_evidence` (by evidence-type)
- **Task 10** — `bjr_passport.py` chat tool: `get_passport_url` with graceful 409 handling (decision not locked → "Gate 5 belum selesai" surfaced)
- **Task 11** — Dispatcher + RBAC wiring in `main.py`: 8 new tool routes + `_ROLE_ALLOWED_TOOLS` frozen matrix + `_role_allowed_tools(role)` helper + 2 new roles (`direksi`, `dewan_pengawas`). Inline fix: `_get_api_client` no longer passes invalid `environment=` kwarg to `ApiClient.__init__`.
- **Task 12** — `scripts/bjr_graph_backfill.py` idempotent PG→Neo4j backfill: reads `strategic_decisions` + `decision_evidence` + `bjr_checklists.evidence_refs` JSONB via ORM `select()`, upserts via existing GraphClient MERGE methods. Defensive handling for malformed refs and stale item_codes. Supports `--dry-run`.
- **Task 13** — Agent Builder region-verification runbook (blocker gate for 6.4b, pending GCP support ticket).

**Moderate PII scrubbing (spec §6.4)** in `formatting_bjr._format_idr`:
- `≥1T` → "Rp X,Y triliun"
- `≥1B` → "Rp X,Y miliar"
- `≥1M` → "Rp X juta"

**Per-role BJR tool matrix (spec §4.2):**

| Role | BJR tools | Note |
|---|---|---|
| `admin` | 8 (all) | |
| `corp_secretary` | 8 | BJR process owner |
| `legal_compliance` | 8 | |
| `internal_auditor` | 8 | audit needs full read |
| `business_dev` | 7 | no `get_passport_url` |
| `komisaris` | 7 | no `list_my_decisions` (not owners) |
| `dewan_pengawas` | 7 | same as komisaris |
| `direksi` | 6 | owners: `list_my_decisions` + core + passport |
| `contract_manager` | 0 | unchanged; BJR out of scope |

**Scripts/ becomes a Python package.** Added `scripts/__init__.py` +
`scripts/tests/__init__.py` + extended `pyproject.toml` `testpaths` to
include `scripts` so backfill tests run in CI. Existing scripts unaffected
(don't match pytest's `test_*.py` pattern).

### Fixed

- Latent `environment=` kwarg bug in `gemini_agent._get_api_client()` — would have crashed the first real webhook call in production because `ApiClient.__init__` only takes `base_url` + `timeout`. Caught during Task 11 refactor. (Task 11)
- `formatting_bjr._format_idr` and `format_readiness_card` now guard against `None` score values instead of crashing on `.1f` formatting. (Task 8)
- `format_decision_evidence` annotation simplified from `list[dict[str, Any]]` to `list[dict]` to avoid needing `typing.Any` import. (Task 9)

### Tests

- **+77 tests across Phase 6.4a** (from 543 to 620 total):
  - Task 6 api-gateway: +5 (endpoint happy path, RBAC denial, auth, 404, graph backend none)
  - Task 7 gemini-agent: +6 (decision handlers)
  - Task 8 gemini-agent: +5 (readiness handlers)
  - Task 9 gemini-agent: +6 (evidence handlers, silent-when-empty contract)
  - Task 10 gemini-agent: +4 (passport handler, 409 surface)
  - Task 11 gemini-agent: +23 (dispatcher routing + parametrized per-role RBAC + drift guards)
  - Task 12 scripts: +6 (column mapping, idempotency, JSONB refs, malformed skip, stale item_code skip, end-to-end)

- **Full regression green** across all 9 services + `ancol-common` + `scripts`: **620 passing**.

### Retrospective — what worked, what didn't

**Worked:**

- **TDD rhythm** scaled linearly across 7 tasks. Every feature shipped red → green → lint → commit with zero rework.
- **Plan batching on api_client** (Task 7 added 7 methods instead of 1, saving 3 future diffs).
- **Silent-when-empty contract** on `show_document_indicators` (spec §5.2) fell out of 3 distinct silent paths in the handler — explicit rather than accidental.
- **`/pre-ship` pipeline on PR #8** caught 11 real bugs (Evidence MERGE compound-key bug, APPROVED_BY re-key, test driver leak, etc.) before any reviewer saw the code.

**Didn't work:**

- **Plan-spec drift.** The 2026-04-17 plan document had **11 material drifts** against the real schema for Task 12 alone (wrong column names, wrong table name, wrong JSONB shape, wrong ORM class names). Caught only because the user explicitly demanded two rounds of verification. Lesson: **plan docs age against a moving schema; always verify against real code before execution.** Consider adding a "plan verification pass" step to the workflow — specifically: grep the exact identifiers the plan references, and stop if any are missing or renamed.

- **Carried concerns that didn't get addressed.** IDOR on `/api/documents/{id}/bjr-indicators`, graph factory duplication (now 4 callers), `decision_evidence` table has zero writers. These need their own PRs — deferring into "carried concerns" across multiple PRs risks becoming technical debt.

### Still pending for Phase 6.4a completeness

- **Deployment-time:** register 8 tools in Vertex AI Agent Builder console (one-time setup).
- **Deployment-time:** execute `docs/RUNBOOK-agent-builder-region-verification.md` via GCP support ticket (Task 13 blocker gate for any future 6.4b chat mutations).
- **Out-of-phase:** IDOR sign-off from `corp_secretary` on `/bjr-indicators` endpoint.
- **Out-of-phase:** `decision_evidence` table writers (Phase 6.5 historical migration).
- **Deferred:** Task 5 Spanner parity (de-risked; only needed if Spanner becomes primary).

## [0.4.1.0] - 2026-04-18

### Added — Phase 6.4a first-wave: BJR chat-read surface + graph data layer (partial)

First slice of the Gemini Enterprise primary-interface pivot for BJR. Ships
the shared RAG package relocation, BJR-specific graph data models, full
Neo4j Cypher implementation of 6 new graph methods, and the first API
surface (`GET /api/documents/{id}/bjr-indicators`) that powers the chat tool
`show_document_indicators`. 6 of 14 Phase 6.4a tasks complete; chat-tool
handlers (Tasks 7–11), Spanner parity (Task 5), and graph backfill script
(Task 12) land in follow-up PRs.

- **RAG package promoted to shared scope:** moved from `services/gemini-agent/src/gemini_agent/rag/` to `packages/ancol-common/src/ancol_common/rag/` so the API Gateway can consume `GraphClient` without cross-service imports. `gemini_agent.rag` is now a backward-compat shim.
- **6 new BJR graph models** in `ancol_common/rag/models.py`: `DecisionNode`, `EvidenceNode`, `ChecklistItemNode`, `DocumentIndicator`, `EvidenceSummary`, `Gate5Half`, `ApprovedByEdge`. Frozen dataclasses, zero runtime deps.
- **GraphClient ABC extended with 6 BJR methods:** `upsert_decision_node`, `upsert_supported_by_edge`, `upsert_satisfies_item_edge`, `upsert_approved_by_edge`, `get_document_indicators`, `get_decision_evidence`. Spanner implementations raise `NotImplementedError` (Task 5); Neo4j is fully implemented.
- **Neo4j Cypher implementation** of all 6 methods with idempotent MERGE semantics, per-decision edge keying via edge properties, and graceful degradation (reads return `[]`, writes log + swallow).
- **New read-only endpoint** `GET /api/documents/{document_id}/bjr-indicators` returns all BJR decisions a document supports, per-decision readiness score, lock state, and satisfied/missing 16-item checklist codes. Gated by new `bjr:read` RBAC permission (8 roles). Degrades to empty list on backend-down / backend-unimplemented / backend-error — chat tool treats as silent no-op.
- **Agent Builder region-verification runbook** at `docs/RUNBOOK-agent-builder-region-verification.md` — blocker gate for Phase 6.4b (confirms `asia-southeast2` pin before chat tool wiring).

### Changed — Correctness fixes from review pipeline

Fixes caught by `/simplify`, `/review`, and `/codex` cross-model review passes:

- **`Evidence` MERGE now keyed by id only.** Prior compound key `MERGE (ev:Evidence {id, type})` would create a duplicate Evidence node if the same id was re-upserted with a different type. Now `MERGE (ev:Evidence {id}) SET ev.type = $type` (correctness).
- **`APPROVED_BY` edge now keyed by `(decision_id, half)`, not `(decision_id, user_id, half)`.** Prior MERGE pattern meant re-approval by a DIFFERENT authorized user created a duplicate edge, violating the one-edge-per-half invariant. Now OPTIONAL MATCH + DELETE + `WITH DISTINCT` + CREATE, so re-approval replaces the prior edge exactly once regardless of how many stale edges existed.
- **Graph client instantiation is now failure-tolerant.** If `SpannerGraphClient()` / `Neo4jGraphClient()` raises during construction (missing deps, bad ADC credentials), `_get_graph_client()` logs and returns `None`; endpoint returns empty list instead of 500.
- **BJR endpoint wraps graph call in try/except** to catch `NotImplementedError` (Spanner stub) and generic exceptions at query time, matching the documented degradation contract.
- **Typed API response** — `BJRIndicatorResponse.satisfied_items` / `missing_items` now typed as `list[BJRItemCode]` so OpenAPI schema documents the 16 stable enum values. JSON wire format unchanged.
- **`BJRIndicatorsListResponse` now carries `total: int`** matching every other `*ListResponse` convention in the codebase.
- **Test fixture no longer leaks a real Neo4j driver.** `_make_client_with_mock_driver` now patches `neo4j.AsyncGraphDatabase.driver` during `__init__` so tests don't instantiate real connection pools.
- **Dropped unused `doc_type` parameter** from `get_document_indicators` across ABC + Neo4j + Spanner stub + call site + tests (YAGNI — Cypher never matched on it).
- **Stripped phase-tracking comments** across `rag/graph_client.py`, `neo4j_graph.py`, `spanner_graph.py` per repo convention.

### Tests

+31 new tests across three suites. Total: 19 `ancol-common` + 351 `api-gateway` + 61 `gemini-agent` = **431 passing** (from 377 + 61 at v0.4.0.0).

- `packages/ancol-common/tests/test_graph_client_bjr.py` — 9 tests covering the 6 Neo4j BJR methods + degradation + APPROVED_BY re-key invariant
- `packages/ancol-common/tests/test_rag_models.py` — dataclass shape tests
- `packages/ancol-common/tests/test_graph_client_interface.py` — ABC signature drift guard
- `services/api-gateway/tests/test_documents_bjr_indicators.py` — 7 endpoint tests: happy path, empty list, unauthenticated, invalid UUID, locked decision serialization, connection error degradation, NotImplementedError degradation
- `services/api-gateway/tests/test_bjr_rbac.py` — updated drift-guard (23 → 24 BJR permission keys)

## [0.4.0.0] - 2026-04-17

### Added — BJR (Business Judgment Rule) orchestration layer

New decision-level defensibility layer on top of MoM + CLM. PT PJAA's dual
legal regime (BUMD + Tbk) exposes Direksi to criminalization of business
losses; BJR proof per UU PT Pasal 97(5) is the statutory shield. This release
adds `StrategicDecision` as a new root entity that aggregates MoMs/contracts
plus 8 new artifact types into a 16-item proof checklist across 3 phases
(pre-decision, decision, post-decision).

- **New root entity:** `StrategicDecision` with 14-state machine (ideation → dd_in_progress → fs_in_progress → rkab_verified → board_proposed → organ_approval_pending → approved → executing → monitoring → bjr_gate_5 → bjr_locked → archived).
- **12 new database tables:** strategic_decisions, bjr_checklists, decision_evidence (polymorphic join), bjr_gate5_decisions, rkab_line_items, rjpp_themes, due_diligence_reports, feasibility_study_reports, spi_reports, audit_committee_reports, material_disclosures, organ_approvals.
- **2 new user roles:** `dewan_pengawas` (BUMD oversight per Pergub DKI 50/2018, distinct from `komisaris`) and `direksi` (self-service decision passport).
- **23 new RBAC permissions** covering decisions, Gate 5 dual-approval, registries (RKAB/RJPP), and all 6 artifact types.
- **16 evaluators** (12 fully auto / 3 AI-assist / 1 manual) that compute each checklist item from DB state, each citing its Indonesian regulatory basis (UU PT, POJK, Pergub DKI).
- **Dual-regime BJR Readiness Score:** `min(corporate_score, regional_score)` with CRITICAL items (PD-03-RKAB, PD-05-COI, D-06-QUORUM, D-11-DISCLOSE) weighted 2×. Encodes the document's #1 strategic risk — a decision passing corporate compliance but failing BUMD compliance gets NO BJR protection.
- **Gate 5 dual-approval flow:** Komisaris + Legal each approve independently (MFA required), with row-level locking to prevent duplicate records and a 5-day SLA. Final state transitions the decision to `bjr_locked` via the state machine.
- **Retroactive bundler** (`POST /api/decisions/retroactive-propose`): proposes a Decision from a completed MoM with initiative-type classification, plus top-3 RKAB/RJPP candidates via token-overlap matching.
- **26 new API endpoints** across `/api/decisions`, `/api/rkab`, `/api/rjpp`, and `/api/artifacts/*` (DD, FS, SPI, Audit Committee, Material Disclosures, Organ Approvals).
- **Regulatory corpus expansion:** 23 new regulations seeded with `regulatory_regime` + `layer` metadata — all 14 Pergub DKI (KepGub 96/2004 through SE Gub 13/2017), PP 54/2017 (BUMD), PP 23/2022 (BJR phases), UU 1/2025 (BUMN amendment), and 2 additional POJK.
- **2026 RKAB seed** with 10 illustrative line items across theme park, beach city, property, and corporate categories, plus RJPP 2025-2029 themes.
- **Design spec:** [docs/superpowers/specs/2026-04-17-bjr-integration-design.md](docs/superpowers/specs/2026-04-17-bjr-integration-design.md) — 13-section architecture doc.
- **127 new tests** (504 total across 9 services): scorer math + dual-regime enforcement, 14-state machine completeness, Gate 5 RBAC isolation (Komisaris cannot do Legal half; Direksi cannot self-approve), retroactive keyword classification, router registration, RBAC coverage for 23 BJR permissions, Pydantic schema validation for 16 item codes.
- **BJR_ENABLED env flag** as a kill switch, plus configurable thresholds (`BJR_GATE5_THRESHOLD=85.0`, `BJR_GATE5_SLA_DAYS=5`, `BJR_MATERIALITY_THRESHOLD_IDR=10e9`).

### Changed

- `users.role` enum extended with `dewan_pengawas` + `direksi` (via `ALTER TYPE ... ADD VALUE`).
- `regulation_index` gained `regulatory_regime` (corporate/regional_finance/listing/internal) and `layer` (uu/pp/pergub_dki/ojk_bei/internal) columns; existing 14 regulations backfilled.
- `StrategicDecision` state transitions added to `db/repository.py` via new `DECISION_TRANSITIONS` map and `transition_decision_status` function, mirroring the existing document-status pattern.
- `/decisions/dashboard` uses conditional aggregates (`func.count().filter()`) — 5 round-trips collapsed to 2.
- POST-13/14/15 evaluators now use PG `@>` operator against existing GIN indexes (`idx_spi_related_decisions`, `idx_auditcom_decisions`) instead of full-table fetches + Python filtering.
- POST-16-ARCHIVE batched per evidence_type (at most 8 queries) instead of N+1 per-row lookups.

### Fixed — caught during /pre-ship review passes

- **[P1]** Unique index on `bjr_gate5_decisions.decision_id` prevents duplicate Gate 5 rows under concurrent half-approvals; `_ensure_gate5_row` uses `SELECT ... FOR UPDATE` with IntegrityError fallback that properly distinguishes unique-race (retry) from FK violation (404).
- **[P1]** Gate 5 finalization now attempts the `bjr_gate_5 → bjr_locked` transition BEFORE setting `final_decision=approved` — prevents split-brain state where Gate 5 looks approved but decision stayed unlocked. Both half-approval endpoints also assert decision is in `bjr_gate_5` state upfront.
- **[P2]** Readiness response uses `is not None` for score fields — a valid computed 0.0 score is no longer misreported as null.
- **[P2]** PD-04-RJPP evaluator verifies `RJPPTheme.is_active=true`; inactive/superseded themes are flagged instead of silently accepted.
- **[P2]** Evidence-link endpoint narrowed exception handler to `IntegrityError` only — FK violations and invalid enum values no longer misreport as 409 "Duplicate evidence link".
- Raw-string comparisons replaced with enums throughout: `Gate5FinalDecision`, `OrganApprovalType`, `EvidenceType`, `RKABApprovalStatus`, `ChecklistItemStatus`.
- `_EVIDENCE_MODEL_MAP` now has an import-time completeness assertion against the `EvidenceType` enum — new enum values force a classification decision (archived vs non-archived) rather than silently failing POST-16-ARCHIVE.

### Deferred to subsequent releases

- Phase 6.4: Frontend UI (decisions dashboard, proactive wizard, retroactive bundler UI, Decision Passport PDF).
- Phase 6.5: Pub/Sub wiring (`bjr-evidence-changed`, `bjr-locked` topics), Gemini Enterprise chat tools, graph client extensions (Decision node + 5 edge types), historical migration for 500+ existing MoMs.
- Phase 6.6: Standalone `services/bjr-agent/` Cloud Run service that wraps the in-process `ancol_common.bjr` module; Terraform updates (6 Pub/Sub topics, CMEK passport bucket, scheduler, alert policies).

### Notes

- The prior MFA + WhatsApp + Per-gate HITL RBAC + Neo4j graph work shipped to `main` as commit `349a255` (tagged as v0.3.0.0 in PROGRESS.md) did not update the `VERSION` file or append a 0.3.0.0 CHANGELOG entry. This release jumps from the last tracked `VERSION` 0.2.0.0 straight to 0.4.0.0 to restore alignment.

## [0.2.0.0] - 2026-04-15

### Added
- Progressive Web App (PWA) support: installable on mobile devices with offline fallback
- Service worker with stale-while-revalidate caching for static assets and network-first for navigation
- Push notification infrastructure: VAPID-based Web Push API subscription with backend storage
- Notification center enhanced with push permission prompt, real-time in-app notification relay via service worker postMessage
- Backend push subscription endpoints (`/api/notifications/subscribe`, `/unsubscribe`, `/subscriptions`) with RBAC enforcement
- `notifications:manage` RBAC permission for all authenticated roles
- Offline fallback page in Bahasa Indonesia

### Fixed
- Push subscription validates backend response before reporting success (rolls back on failure)
- URL origin validation prevents javascript: URI injection from push payloads
- Service worker skipWaiting moved inside waitUntil chain (prevents offline.html cache race)
- Unsubscribe order corrected: server-first then local (prevents permanent desync)
- Removed maximumScale: 1 viewport restriction (WCAG 1.4.4 accessibility violation)

## [0.1.0.0] - 2026-04-15

### Added
- Contract PDF generation with styled A4 HTML output via WeasyPrint, including clause boxes with risk badges, party tables, key terms, and confidence scores
- `POST /api/drafting/pdf` endpoint for generating contract draft PDFs from the clause library and AI review
- Contract detail page (`/contracts/[id]`) with metadata cards, clause viewer, obligations table, and risk analysis tabs
- Draft generator page (`/contracts/draft`) with contract type picker, party builder, key terms editor, markdown preview, and PDF export
- "Buat Draf" sidebar link under Contract Management
- 13 new tests for PDF HTML generation and the drafting endpoint (277 total)
- Shared contract label constants (`web/src/lib/contracts.ts`) for status, type, risk, and obligation maps

### Fixed
- PDF export now reuses the previewed draft instead of re-drafting (prevents divergence between preview and export)
- Clause text in PDF preserves line breaks via `white-space: pre-wrap`
- Obligations permission errors (403) distinguished from empty data on contract detail page
- Blob URL memory leak on PDF export (revoked after 10 seconds)
- `window.open` for PDF export uses `noopener,noreferrer` to prevent opener reference leakage
- CSS class value in PDF HTML now HTML-escaped for defense-in-depth
- PDF fallback path handling uses `os.path.splitext` instead of fragile `.replace()`
