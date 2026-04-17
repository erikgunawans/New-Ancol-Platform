# Graph Question List

> Live document. Updated alongside project development.
> Last updated: 2026-04-17 (post-BJR merge) | Graph: **2,924 nodes, 8,096 edges, 139 communities**
>
> Run any question: `/graphify query "<question>"`
> Update graph after code changes: `/graphify --update`
>
> **Changes since last update (v0.4.0.0 BJR merge):** +790 nodes, +2,868 edges, +16 communities. New god nodes: `BJRItemCode` (85), `StrategicDecision` (83), `ChecklistItemStatus` (89). New hyperedges: *BJR Dual-Regime Defense Stack*, *4-Agent MoM Pipeline with HITL*, *Hybrid RAG 3-Layer Retrieval*.

---

## How to use this list

Each question is tagged with its **impact category** and **graph traversal type**. Pick the ones relevant to your current work. After running a query, note the answer date and any follow-up questions that emerge.

**Impact categories:**
- **ARCH** — Architecture decisions, blast radius, coupling
- **SEC** — Security, auth flows, attack surface
- **PERF** — Performance, hot paths, bottlenecks
- **ONBOARD** — New developer understanding, knowledge transfer
- **RISK** — Hidden dependencies, single points of failure
- **PRODUCT** — Feature coverage, regulatory compliance gaps

---

## 1. Architecture & Blast Radius (ARCH)

### 1.1 God Node Impact Analysis

| # | Question | Why it matters | Status |
|---|----------|---------------|--------|
| 1 | How does `Document` (169 edges) flow through the entire system from upload to final report? | Document is the #1 connected entity. Edge count grew +58 after BJR (now referenced as evidence in decision_evidence polymorphic join). Any schema change cascades across 10+ communities. | Traced 2026-04-17 |
| 2 | Why does the `Extraction Agent` bridge 9 different communities? | Highest betweenness centrality (0.176). It's the system's gravitational center. Understanding WHY reveals architectural coupling that may need decoupling as the system scales. | Traced 2026-04-17 |
| 3 | What happens if `ProcessingMetadata` (92 edges) changes its schema? | Fourth most connected node. Carries extraction results through the entire pipeline. A field rename here breaks 4 agents silently. | |
| 4 | Which services would break if `UserRole` enum (139 edges) adds a new role? | RBAC touches every service. Edge count grew +38 after BJR (added `dewan_pengawas` + `direksi` which required 23 new permission keys). A new role needs handling in ROLE_PERMISSIONS, GATE_PERMISSIONS, MFA required roles, notification channel defaults, and frontend route guards. | |
| 5 | What is the full dependency chain of `get_session()` (78 edges, betweenness 0.095)? | DB session factory connects 8 communities. If connection pooling changes or async session behavior shifts, what breaks? | |
| 5a | **NEW:** What breaks if any of `BJRItemCode`'s 16 values (85 edges) are renamed? | BJRItemCode is the stable contract between BJR Agent output, UI checklist, Passport PDF, and audit_trail. Graph shows it bridges 6+ communities: BJR Artifact Schemas, 4 Gemini Agents Pipeline, BJR Artifacts CRUD, Retroactive Bundler, BJR Router Tests. Rename = silent breakage across all 4. Flagged in CLAUDE.md but worth visualizing. | |
| 5b | **NEW:** What is the blast radius of `StrategicDecision` (83 edges) schema changes? | New BJR root entity. Connects to 12 new tables as evidence provider. Adding/removing a field touches: 16 evaluators (each reads `decision.X`), scorer, compute orchestrator, decisions router, Gate 5 flow, Passport PDF. | |
| 5c | **NEW:** How does `ChecklistItemStatus` (89 edges) propagate between scorer + evaluators + compute + UI? | 5 status values (not_started/in_progress/satisfied/waived/flagged) drive the dual-regime score. Adding a sixth would cascade to `_ITEM_SCORE_BY_STATUS`, `_extract_bool_field`, every evaluator's return, and UI rendering. | |

### 1.2 Cross-Community Coupling

| # | Question | Why it matters | Status |
|---|----------|---------------|--------|
| 6 | What are ALL the edges between the Agent Pipeline (c1) and Contract Schemas (c6)? | These are separate domains (MoM compliance vs CLM) sharing data structures. Tight coupling here means CLM changes can break MoM processing. (Note: community IDs shifted after BJR merge — c1 is now "4 Gemini Agents Pipeline", c6 is "Contract Schemas") | |
| 7 | How does the Notification Dispatch community (c0) connect to HITL gates? | Notifications were wired to gate transitions in session 25. The graph reveals whether the coupling is clean (via events) or leaky (via direct imports). | |
| 8 | Which communities does `ApiClient` (now in c4 "Frontend API Client") bridge? | The Gemini Agent's API client proxies all calls. If it goes down, which features degrade? | |
| 9 | Is there a hidden coupling between Email Ingest (c13) and Batch Processing (c11)? | Both create documents but through different paths. Are there shared assumptions about document state? | |
| 9a | **NEW:** What cross-community edges exist between BJR communities (c2, c5, c9, c10, c17, c19) and the pre-BJR core? | BJR was shipped as an "orchestration layer on top" per the plan. The graph can verify whether it actually sits on top (few back-edges into core) or leaks into it (many back-edges → tight coupling). | |
| 9b | **NEW:** Which nodes sit in the *BJR Matrix + Governance Doctrine* community (c9) but have no edges to any code community? | The BJR matrix doc contains 28 regulatory citations. Citations without a corresponding code evaluator = uncovered compliance risk. | |

### 1.3 Module Boundaries

| # | Question | Why it matters | Status |
|---|----------|---------------|--------|
| 10 | What is the shortest path from `Neo4jGraphClient` to `WhatsApp notification`? | These should be completely independent. If a path exists, there's unexpected coupling. | |
| 11 | Can the Regulation Monitor (c13) function without the API Gateway (c1)? | Independence test. If regulation monitoring depends on the API gateway, a gateway outage stops compliance monitoring. | |
| 12 | What nodes exist in BOTH the MoM pipeline and the CLM pipeline? | Shared nodes are integration points. Too many shared nodes = the systems can't evolve independently. | |

---

## 2. Security & Auth (SEC)

| # | Question | Why it matters | Status |
|---|----------|---------------|--------|
| 13 | Trace every path from an unauthenticated request to database write. | The MFA + IAP + RBAC layers should make this impossible. The graph can verify there are no bypass paths. | |
| 14 | Which endpoints does `User` (108 edges) connect to that DON'T have `require_permission`? | After the /review security fixes, all endpoints should have RBAC. Now 88 routes — graph can verify completeness. Edge count grew +32 after BJR added 26 new endpoints. | |
| 15 | What is the full trust boundary around `mfa_secret_encrypted`? | Trace every function that reads, writes, or transforms the encrypted TOTP secret. Any function outside `auth/mfa.py` touching this is a leak. | |
| 16 | How does `GATE_PERMISSIONS` connect to `notify_gate_reviewers`? | The RBAC gate map drives who gets notified. If these diverge, the wrong people get WhatsApp alerts about documents they can't review. | |
| 16a | **NEW:** Gate 5 dual-approval: trace `bjr:gate_5_komisaris` + `bjr:gate_5_legal` permission paths and verify role isolation. | These two permissions MUST never overlap (Komisaris cannot sign the Legal half and vice versa). RBAC tests assert this at permission-matrix level; the graph verifies there's no code path that bypasses the check. | |
| 16b | **NEW:** What functions touch `decisions.py` `_maybe_finalize_gate5` + `transition_decision_status(BJR_LOCKED)`? | The state-machine-first-then-set-approved fix (from /codex review) depends on this ordering. Any refactor that breaks the order reintroduces the split-brain bug. | |
| 16c | **NEW:** Who can access `gcs_passport_uri` on a locked decision? | Decision Passport PDF is legal-defense evidence. Trace the `decisions:passport` permission path — who can generate it, who can download, who can see the URL. MFA should be required. | |

---

## 3. Performance & Hot Paths (PERF)

| # | Question | Why it matters | Status |
|---|----------|---------------|--------|
| 17 | What is the critical path from document upload to `hitl_gate_1`? | This is the user-facing latency. Every node on this path adds to the time between "upload" and "ready for review." | |
| 18 | Which functions in the hot path call `get_session()` multiple times? | Unnecessary DB session creation on every request. The graph can find functions that open sessions redundantly. | |
| 19 | What is the fan-out of `notify_gate_reviewers`? | When a document enters a gate, how many users get notified via how many channels? If 10 users x 3 channels = 30 async HTTP calls per gate transition. | |
| 20 | Which graph queries in the RAG orchestrator are sequential vs parallel? | The orchestrator uses `asyncio.gather` for some queries. The graph reveals if any calls are accidentally sequential. | |
| 20a | **NEW:** Trace `compute_bjr` through its 16 sequential evaluator calls — which can be parallelized? | Evaluators share the session (SQLAlchemy async sessions are not concurrent-safe), but many read disjoint data. The /simplify agent recommended prefetching `mom_ids` + `extractions` into `EvaluationContext` to eliminate 5× redundant queries. Graph can confirm which evaluators read what. | |
| 20b | **NEW:** What is the query plan of `/api/rkab/match`? | Current implementation loads ALL active RKAB line items for a year, scores them in Python via `rank_by_token_overlap`. At 100+ RKAB entries, this gets slow. Graph reveals the call tree — is there a DB-side filter that could narrow the candidate set first? | |

---

## 4. New Developer Onboarding (ONBOARD)

| # | Question | Why it matters | Status |
|---|----------|---------------|--------|
| 21 | Explain the `Document` state machine (14 states) and which service owns each transition. | A new developer needs to understand the state machine before touching any agent code. The graph traces which service triggers which transition. | |
| 22 | What are the 5 most important files a new developer should read first? | The god nodes + bridge nodes point to the architectural spine. Reading these files first gives 80% understanding. After BJR: `models.py`, `mom.py` (UserRole + shared types), `bjr/scorer.py` (dual-regime formula), `bjr/evaluators.py` (16 evaluators), `decisions.py` (Gate 5 flow). | |
| 23 | How does data flow from a Gemini Enterprise chat message to a compliance report? | End-to-end trace through the webhook, tool handlers, API client, agents, and HITL gates. This is the "explain the whole system" question. | |
| 24 | What is the relationship between `ancol-common` schemas and each service? | The shared package is the contract between services. Understanding which schemas each service consumes prevents breaking changes. | |
| 24a | **NEW:** Explain the `StrategicDecision` 14-state machine — from `ideation` to `bjr_locked`. | New mental model after v0.4.0.0. Mirrors the Document state machine but operates at decision level. Back-edges allowed (ideation ← dd_in_progress ← fs_in_progress ← rkab_verified). Terminal states: archived, rejected, cancelled. | |
| 24b | **NEW:** How does the BJR Readiness Score flow from the 16 evaluators to the `/decisions/{id}/readiness` endpoint? | Map the full chain: evaluator → EvaluatorResult → ChecklistSnapshot → compute_scores → BJRScoreResult → decision row → ReadinessResponse. Understanding this chain is prerequisite for Phase 6.4 frontend work. | |
| 24c | **NEW:** How does `StrategicDecision` relate to existing `Document` and `Contract`? | BJR plan framed Decision as "orchestration layer on top" that aggregates MoMs + contracts as evidence. Graph reveals the actual coupling via `DecisionEvidenceRecord` polymorphic join. Critical for understanding the architectural boundary. | |

---

## 5. Risk & Single Points of Failure (RISK)

| # | Question | Why it matters | Status |
|---|----------|---------------|--------|
| 25 | What are the single points of failure in the system? | Nodes with high betweenness AND high degree that have no redundancy. If `get_session()` or `ApiClient` fails, what's the blast radius? | |
| 26 | Which Alembic migrations have the widest impact? | Migration 003 (MFA) and 004 (phone/notifications) touch the User table, which connects to 108+ nodes. Migration 005 (BJR) creates 12 new tables + 13 new enums — largest impact to date. A failure here is catastrophic. | |
| 27 | What happens if the Vertex AI Search datastore is unavailable? | RAG depends on vector search. Trace the fallback path. Does the system degrade gracefully or hard-fail? | |
| 28 | If Spanner Graph goes down, does the system still function? | The graph backend is swappable (`GRAPH_BACKEND=none`). But does the code actually handle `None` graph client everywhere? | |
| 28a | **NEW:** If `BJR_ENABLED=false`, what degrades vs hard-fails? | The kill switch is supposed to make BJR completely inert. Graph verifies that every BJR router + evaluator call is gated. If any path bypasses the flag, turning it off won't actually stop BJR. | |
| 28b | **NEW:** What is the blast radius of removing the unique index on `bjr_gate5_decisions.decision_id`? | This was added during /review to fix a race. Without it, two concurrent Gate 5 half-approvals for the same decision could both INSERT, creating duplicate rows. The row-lock + IntegrityError fallback in `_ensure_gate5_row` DEPENDS on the unique constraint existing. | |
| 28c | **NEW:** If one of the 16 evaluators raises at runtime, does the rest of the compute succeed? | Yes (regression test in `test_bjr_compute.py::test_failing_evaluator_produces_synthetic_flagged`), but the graph can show which evaluators share data with the failing one — those are indirectly blast-affected. | |

---

## 6. Regulatory Compliance & Product (PRODUCT)

| # | Question | Why it matters | Status |
|---|----------|---------------|--------|
| 29 | Which Indonesian regulations (POJK, UUPT, IDX) are connected to which red flag detectors? | Compliance completeness: every regulation should map to at least one detector. Missing connections = uncovered compliance risks. | |
| 30 | How does the GCG governance matrix connect to the 4-agent pipeline? | The matrix defines what to check. The agents do the checking. Trace the connection to verify nothing falls through the cracks. | |
| 31 | Which BOD/BOC charter requirements are covered by the extraction agent vs not? | The charters define what MoM content is required. If the extraction agent doesn't extract a required field, that's a product gap. | |
| 32 | What is the connection between obligation reminders and WhatsApp delivery? | After session 25, obligation deadlines should trigger notifications. Trace the full path from `check_obligation_deadlines()` to `send_obligation_reminder()`. | |
| 32a | **NEW:** Which of the 28 BJR matrix regulations are covered by BJR evaluators, and which are orphans? | The BJR matrix cites 28 regulations across 4 layers (UU, PP, Pergub DKI, OJK/BEI). Each evaluator declares a `regulation_basis` list. Cross-reference: matrix ∩ evaluator citations = covered. matrix \ evaluator citations = gaps. | |
| 32b | **NEW:** Does the dual-regime scoring actually block a decision that passes corporate but fails regional? | This is the #1 claim of the BJR doc. Graph can trace PD-03-RKAB (REGIONAL only, 2× CRITICAL) through `compute_scores` → `min(corporate, regional)` → `gate_5_unlockable`. If any code path short-circuits this, the dual-regime defense is bypassed. | |
| 32c | **NEW:** Dewan Pengawas vs Komisaris: can the same user hold both roles? | Ancol has both organs per Pergub 50/2018 + POJK 21/2015. System treats them as distinct roles. If a single person actually sits on both (common in practice), does the `User.role` single-field model block them from participating in both flows? | |
| 32d | **NEW:** Is the Decision Passport PDF generation actually wired to Gate 5 lock? | Plan says: both halves approve → state transitions to bjr_locked → trigger Passport PDF. Phase 6.4 deferred the PDF generator. Graph should currently show NO edge between `_maybe_finalize_gate5` and any PDF generator. When 6.4 ships, this edge should appear. | |

---

## 7. Evolution & Refactoring (future)

| # | Question | Why it matters | Status |
|---|----------|---------------|--------|
| 33 | Which communities have the lowest cohesion scores? | Low cohesion = the community is a grab-bag, not a real module. These are candidates for splitting or reorganizing. | |
| 34 | If we extract `auth/` into a standalone microservice, what breaks? | The auth module (RBAC, MFA, IAP) is used by every router. Trace all consumers to estimate extraction cost. | |
| 35 | What would it take to make the Contract pipeline fully independent from the MoM pipeline? | They share `ancol-common`, `Document` model, `get_session()`, and state machine. Quantify the shared surface. | |
| 36 | Which INFERRED edges in the graph should be verified or removed? | 167 inferred edges on `Document`, 137 on `UserRole`, 106 on `User`, 88 on `ProcessingMetadata`. Some may be false positives. Systematic verification improves graph accuracy. | |
| 37 | **NEW:** What is the extraction cost of moving `packages/ancol-common/bjr/` to a standalone `services/bjr-agent/` Cloud Run service? | Plan Phase 6.6. In-process module vs separate service trade-off. Graph can count cross-module edges to quantify. All consumers are the `decisions` router; the scorer is already pure + dependency-free. Should be a low-effort extraction. | |
| 38 | **NEW:** If we apply the `6× artifact CRUD factory` refactor flagged by the /simplify agent, which tests break? | `artifacts.py` has 6 near-identical CRUD blocks for DD/FS/SPI/AuditCom/Disclosure/OrganApproval. ~300 LOC reduction possible. Graph can enumerate every test + caller that asserts on the current handler structure. | |
| 39 | **NEW:** What would a `Literal[Gate5FinalDecision.APPROVED, REJECTED]` type swap break? | Type-design-analyzer flagged `Gate5HalfRequest.decision: str` as leaky. Changing to `Literal` enum would tighten validation but breaks any caller that sends the raw string "pending" (which should be rejected anyway). Graph traces all call sites. | |

---

## 8. BJR-Specific (NEW — post-v0.4.0.0)

| # | Question | Why it matters | Status |
|---|----------|---------------|--------|
| 40 | Trace PD-05-COI evaluator: where do the RPT entity list + extraction.attendees data flows meet? | This evaluator was the site of a silent-failure bug (malformed attendees → false SATISFIED). Understanding the data flow prevents re-introduction. Graph shows: `eval_pd_05_coi` → `_linked_evidence_ids` → `Extraction.attendees` ⋈ `RelatedPartyEntity.entity_name`. | |
| 41 | Which evaluators call `_extract_bool_field` (new helper from review fixes)? | Should be 2: `eval_d_06_quorum` + `eval_d_07_signed`. If a future evaluator adds a bool-from-JSONB check without using this helper, the missing-vs-False distinction is lost. Graph enforces the convention. | |
| 42 | How does `_EVALUATOR_METADATA` stay in sync with `EVALUATORS`? | The drift guard in `test_bjr_compute.py` asserts 1:1 mapping. If a developer adds a 17th evaluator without the metadata entry, the synthetic-failure result says "UNKNOWN" item_code. Graph visualizes the dependency. | |
| 43 | What are the data paths that touch `CRITICAL_ITEMS` + `CORPORATE_ITEMS` + `REGIONAL_ITEMS` frozensets? | These three frozensets in `bjr/scorer.py` encode the classification of each of the 16 items. Changing membership silently re-weights the score. Graph shows all readers (scorer + tests + potential future readers). | |
| 44 | Where does `DECISION_TRANSITIONS` validate the state machine vs where does it skip validation? | The 14-state machine has some back-edges. The new `bjr_gate_5 → rejected` transition added in the PR review fix. If any code path sets `decision.status = "X"` directly (bypassing `transition_decision_status`), that's a state-machine bypass. | |
| 45 | Which evidence types touch `_EVIDENCE_MODEL_MAP` vs `_NON_ARCHIVED_EVIDENCE_TYPES`? | POST-16-ARCHIVE checks gcs_uri on every linked artifact. Registry types (RKAB, RJPP) are non-archived. The import-time assertion guards against drift. Graph should show these two frozensets cover all 10 `EvidenceType` values exhaustively. | |
| 46 | Retroactive bundler: which initiative-type keywords actually fire for real MoMs? | `_INITIATIVE_KEYWORDS` has 6 types × ~5 keywords each (Bahasa + English). After historical migration ships (Phase 6.5), can measure which keywords match real data and which are dead. Graph can highlight dead keyword branches. | |
| 47 | What is the relationship between `RKABLineItem.embedding` column (reserved for v2) and the current `rank_by_token_overlap`? | The embedding column exists in the schema but is unused. v2 will populate it via Vertex AI text-embedding-004 and swap out token overlap. Graph should show NO edges to the `embedding` column today — if any appear, something's prematurely using it. | |

---

## Query Log

Track answers here as questions are explored:

| Date | # | Question | Key Finding | Follow-up |
|------|---|----------|-------------|-----------|
| 2026-04-17 | 2 | Extraction Agent bridges 9 communities | First agent in pipeline, output schema shared by all downstream. Schema change = 9 communities affected. | Q3: ProcessingMetadata impact |
| 2026-04-17 | 1 | Document lifecycle | 111 edges, 7 communities, 14-state machine. Never touches Graph Client directly (clean separation). | Q21: State machine detail |
| 2026-04-17 | (auto-detected via `/graphify --update`) | BJR god nodes emerged | Post-BJR merge: `BJRItemCode` (85 edges, bridges 6 communities), `StrategicDecision` (83), `ChecklistItemStatus` (89). `UserRole` grew +38 edges from 2 new roles. `Document` grew +58 from being evidence in decision_evidence. | Q5a (BJRItemCode rename blast radius); Q5b (StrategicDecision schema changes) |
| 2026-04-17 | (auto-detected) | 3 new hyperedges emerged | *BJR Dual-Regime Defense Stack*, *4-Agent MoM Pipeline with HITL*, *Hybrid RAG 3-Layer Retrieval*. These are group-level relationships that pairwise edges don't capture. | Q32b (trace dual-regime `min()`); Q24b (readiness score flow) |
| 2026-04-17 | (auto-detected) | Cross-doc surprise: PRODUCT-STATUS ↔ GRAPH_REPORT | `Hybrid RAG: Vertex AI Search + Spanner Graph + Cloud SQL` (PRODUCT-STATUS.md narrative) semantically matches the emergent hyperedge in GRAPH_REPORT.md. The product story and the code structure agree — good sign. | — |
| 2026-04-17 | (auto-detected) | Cross-layer surprise: TS frontend calls Python backend | `subscribeToPush()` (web/src/lib/push.ts) → `subscribe()` (api-gateway/notifications.py). Confirms the push notification contract holds across the language boundary. | — |
| 2026-04-17 | (auto-detected) | `FindingSeverity` is load-bearing across comparison agent | Three independent uses: severity scorer, red flag classifier, tests. The enum is a shared contract; moving it breaks all three. | Q4 pattern: also consider `FindingSeverity` for the "add a new role"-style blast radius analysis |
| | | | | |

---

## How to add new questions

When you discover something surprising during development:

1. Run `/graphify query "<what surprised you>"`
2. If the answer reveals a non-obvious connection, add the question to the relevant section above
3. Tag it with impact category and note the date
4. Run `/graphify --update` after major code changes to keep the graph current
