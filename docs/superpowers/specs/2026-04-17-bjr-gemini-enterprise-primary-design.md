# Gemini Enterprise as Primary BJR Interface — Design Specification

**Project:** PT Pembangunan Jaya Ancol Tbk — MoM Compliance System
**Platform:** Google Cloud Platform — Vertex AI Agent Builder + Gemini Enterprise
**Architecture:** Chat-first surface for BJR with minimal step-up web pages for MFA-gated actions
**Date:** 2026-04-17
**Target Release:** v0.5.0.0
**Supersedes:** Original Phase 6.4 web-UI-first plan in [2026-04-17-bjr-integration-design.md](2026-04-17-bjr-integration-design.md) § 10

---

## 1. Problem Statement

The BJR orchestration layer shipped in v0.4.0.0 ([2026-04-17-bjr-integration-design.md](2026-04-17-bjr-integration-design.md)) delivered 26 API endpoints, dual-regime scoring, Gate 5 dual-approval, and the 16-item proof checklist. The backend is complete. **The user-facing surface is not.**

The original Phase 6.4 plan builds a Next.js web UI as the primary BJR surface (decision dashboard, proactive wizard, retroactive bundler, Decision Passport PDF). Gemini Enterprise chat tools for BJR are deferred to Phase 6.5 — later and explicitly secondary.

The user has requested a reversal: **Gemini Enterprise should be the primary interface for BJR**, matching the existing architectural principle ([PRODUCT-STATUS.md](../../../PRODUCT-STATUS.md) § v1.0) that Gemini Enterprise is the primary interface for the whole system. The web UI should shrink to a minimal secondary surface.

Constraints that must not be broken:

- **Non-repudiation for Gate 5 approval** (UU PT Pasal 97(5), PP 23/2022) — approver identity must bind to a cryptographic MFA event, not a chat message
- **Independent dual approval** (Komisaris + Legal) — neither can impersonate the other
- **Auditable trail** for every state transition — `audit_trail` table must correlate to a verifiable identity
- **Data sovereignty** — all personal and financial data must reside in asia-southeast2
- **MFA JWT bound to IAP sub claim** (existing invariant in [auth/mfa.py](../../../packages/ancol-common/src/ancol_common/auth/mfa.py)) — must not be weakened
- **16-item `BJRItemCode` contract** ([schemas/bjr.py](../../../packages/ancol-common/src/ancol_common/schemas/bjr.py)) — stable across agent JSON, chat tools, Passport PDF, audit_trail

This spec describes how to move BJR's primary interface into Gemini Enterprise chat while preserving all six constraints above, using a **chat-first with step-up** pattern.

## 2. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary surface | Gemini Enterprise chat (new BJR tool handlers in existing `services/gemini-agent/`) | Matches existing system's "Gemini Enterprise as primary UI" principle. Single conversational surface for 95% of flows. |
| MFA-gated actions | Step-up to minimal single-screen web pages via WhatsApp push link | Preserves existing MFA-bound-to-IAP invariant. Matches Indonesian banking pattern (Klik BCA, BRImo). Defensible to OJK/BPK auditors without novel precedent. |
| Alternative considered | 100% chat including MFA-in-chat | Rejected: requires extending MFA binding to Workspace identity (new threat model surface), first-BUMD regulatory defense posture, TOTP typed into persistent chat history. +2 weeks eng, external counsel review. |
| Alternative considered | Chat-aware web-primary (original Phase 6.4 plan) | Rejected: contradicts user intent; chat becomes convenience tier, not the face. |
| Step-up token signing | HMAC-SHA256 JWT via existing `MFA_JWT_SECRET` + PG `step_up_tokens` nonce table | Zero new secrets. Reuses existing HMAC infrastructure. Single-use enforced at DB layer. ~150 LOC. |
| Alternative considered | GCP KMS asymmetric signing | Rejected: +2-3 days Terraform, higher per-call cost, no multi-verifier scenarios today. Upgrade path preserved if needed. |
| Gate 5 notification order | Parallel — Komisaris and Legal both notified at Gate 5 entry | Matches existing `bjr_gate5_decisions` schema (independent half columns). Faster throughput within 5-day SLA. |
| Document indicator trigger | Proactive on every document mention | Matches user intent ("indicator on all support documents"). Implemented via Agent Builder system prompt directive, not hardcoded flow. |
| Indicator data source | Graph query (Decision node + 5 new edge types) | 1-hop Cypher; fast (<50ms). SQL fallback when `GRAPH_BACKEND=none`. |
| PII scrubbing | Moderate — chat shows rounded IDR (`Rp X miliar`) + initialed conflicted names; full precision in Passport PDF + step-up pages | Balances visibility and transcript leak risk. Full data preserved in defensible artifacts. |
| Chat RBAC | 100% server-side via existing `require_permission` | Client-side or Agent-Builder-side gating is bypassable. Preserves existing auth invariant. |
| Existing `services/bjr-agent/` extraction | Deferred to Phase 6.6 as originally planned | Chat-first shift is additive; does not change in-process vs service boundary for BJR scoring engine. |

## 3. Architecture

```
USER
  │
  ├──► Gemini Enterprise chat (Vertex AI Agent Builder)
  │         │
  │         └──► services/gemini-agent/ webhook (existing)
  │                   │
  │                   ├──► ~25 NEW BJR tool handlers (bjr_decisions, bjr_readiness,
  │                   │    bjr_evidence, bjr_gate5, bjr_retroactive, bjr_artifacts,
  │                   │    bjr_rkab, bjr_passport) — marshal to API Gateway
  │                   │
  │                   └──► api_client.py → services/api-gateway/ (existing 26 BJR routes)
  │                                        │
  │                                        ├──► packages/ancol-common/bjr/ (unchanged)
  │                                        ├──► NEW: bjr/step_up.py (signed-link service)
  │                                        ├──► NEW: routers/step_up.py (issue/verify/consume)
  │                                        ├──► rag/graph_client.py (EXTENDED: Decision node + 5 edges)
  │                                        └──► notifications/dispatcher.py (existing)
  │
  └──► WhatsApp push link (for Gate 5, material disclosure, MFA enrollment only)
           │
           └──► web/app/step-up/{intent}/[token] (NEW, 3 Next.js pages)
                     │
                     └──► POST /step-up/consume → API Gateway → state transition
                              │                                    │
                              MFA TOTP verify ◄───── uses existing auth/mfa.py
                              (MFA JWT bound to IAP sub, unchanged)
```

**Surface split:**

| Surface | Scope | % of BJR UX |
|---|---|---|
| Gemini Enterprise chat | create/edit decisions, link evidence, readiness, checklist, per-document BJR indicators, retroactive bundling, RKAB matching, DD/FS/SPI upload initiation, Q&A over regulations and past decisions | ~95% |
| Step-up web (minimal) | Gate 5 half-approvals (Komisaris + Legal), material disclosure filing, MFA enrollment | ~5% |
| Power-user web (rare) | Decision Passport PDF viewer, bulk retroactive review over 50+ MoMs | Fallback |

**What stays unchanged from v0.4.0.0:** BJR scoring engine (`scorer.py`, `evaluators.py`, `compute.py`), 16-item `BJRItemCode` contract, 12 BJR DB tables, 26 API endpoints, 543 existing tests, `_maybe_finalize_gate5` transition-first ordering, unique index + `SELECT FOR UPDATE` on Gate 5 race.

**What is deleted:** stub pages at `web/app/bjr/decisions/`, `web/app/bjr/wizard/`, `web/app/bjr/retroactive/` (scaffolded earlier but never wired — see PROGRESS.md memory S27).

## 4. Component Design

### 4.1 New BJR chat tool handlers

Location: `services/gemini-agent/src/gemini_agent/tools/bjr_*.py`

Each handler is thin — ~30 lines, marshals params, calls `api_client.py` to existing API Gateway endpoint, formats response for chat rendering.

| File | Tool names | Underlying endpoints |
|---|---|---|
| `bjr_decisions.py` | `create_decision`, `list_decisions`, `get_decision`, `update_decision`, `list_my_decisions` | `POST/GET/PATCH /api/decisions*` |
| `bjr_readiness.py` | `get_readiness`, `get_checklist`, `get_checklist_item_detail` | `GET /api/decisions/{id}/readiness`, `/checklist` |
| `bjr_evidence.py` | `link_evidence`, `unlink_evidence`, `show_document_indicators`, `show_decision_evidence` | `POST /api/decisions/{id}/evidence`, `DELETE /api/decisions/{id}/evidence/{evid}`, `GET /api/documents/{id}/bjr-indicators` (NEW) |
| `bjr_gate5.py` | `request_gate5_approval`, `check_gate5_status` | `POST /api/decisions/{id}/gate5/request` (NEW), `GET /api/decisions/{id}/gate5` |
| `bjr_retroactive.py` | `propose_retroactive_bundle`, `confirm_retroactive_decision` | `POST /api/decisions/retroactive-propose`, `POST /api/decisions/retroactive-confirm` |
| `bjr_artifacts.py` | `upload_dd_report`, `upload_fs_report`, `upload_spi_report`, `upload_audit_committee_report`, `file_material_disclosure_draft`, `submit_organ_approval` | `POST /api/artifacts/*` |
| `bjr_rkab.py` | `match_rkab_line_items`, `list_rjpp_themes` | `POST /api/rkab/match`, `GET /api/rjpp/themes` |
| `bjr_passport.py` | `get_passport_url` | `GET /api/decisions/{id}/passport/signed-url` |

Tool-response formatting uses helpers in `services/gemini-agent/src/gemini_agent/formatting.py` (existing). New helpers added for BJR-specific formatting: `format_readiness_card`, `format_checklist_summary`, `format_document_indicator`, `format_gate5_status`. PII scrubbing (§ 6.4) is applied in these helpers.

### 4.2 Dispatcher & RBAC

Location: `services/gemini-agent/src/gemini_agent/main.py`

The existing dispatcher (lines 116-211) gains ~25 new tool name → handler mappings. The RBAC `allowed` set per role (lines 229-248) is extended:

| Role | New tools allowed |
|---|---|
| `business_dev` | all `bjr_decisions.*`, `bjr_evidence.link_evidence`, `bjr_rkab.*`, `bjr_readiness.get_readiness` for own decisions, `bjr_artifacts.upload_dd_report`, `bjr_artifacts.upload_fs_report` |
| `corp_secretary` | all `bjr_evidence.*`, `bjr_gate5.request_gate5_approval`, `bjr_artifacts.file_material_disclosure_draft`, `bjr_readiness.*` (read) |
| `legal_compliance` | `bjr_readiness.*` (read), `bjr_evidence.show_*` (read), `bjr_gate5.check_gate5_status`, all `bjr_passport.*` |
| `internal_auditor` | all `bjr_retroactive.*`, `bjr_artifacts.upload_spi_report`, `bjr_artifacts.upload_audit_committee_report`, `bjr_readiness.*` (read) |
| `komisaris` | `bjr_readiness.*` (read), `bjr_decisions.list_decisions`, `bjr_gate5.check_gate5_status`, `bjr_passport.get_passport_url` |
| `dewan_pengawas` | same as `komisaris` + `bjr_artifacts.submit_organ_approval` |
| `direksi` | `bjr_passport.get_passport_url` (own), `bjr_readiness.*` (own decisions) |
| `admin` | all |

Note: tools named `*.request_gate5_approval` exist for initiators (corp_sec, business_dev). The *approval* itself (Komisaris/Legal half) never happens via chat tool — it happens on the step-up web page only. This is how non-repudiation is preserved.

### 4.3 Step-up signed-link service

Location: `packages/ancol-common/src/ancol_common/bjr/step_up.py` (NEW, ~150 LOC)

Three public functions:

```python
def issue_token(
    sub: str,                    # IAP email of target approver
    intent: StepUpIntent,        # enum: gate5_komisaris|gate5_legal|material_disclosure|mfa_enroll
    resource_id: UUID,           # decision_id or similar
    session: AsyncSession,
    ttl_hours: int = 24,
) -> IssuedToken  # (token_jwt, token_jti, expires_at)

def verify_token(
    token: str,
    expected_intent: StepUpIntent,
    session: AsyncSession,
) -> TokenClaims  # raises StepUpError on fail

def consume_token(
    token: str,
    expected_intent: StepUpIntent,
    session: AsyncSession,
) -> TokenClaims  # atomic; raises StepUpError if already consumed
```

**Token structure:** HMAC-SHA256 JWT with claims `{sub, intent, resource_id, nonce (jti), iat, exp}`. Signing key: existing `settings.MFA_JWT_SECRET`. Algorithm: `HS256`.

**Single-use enforcement:** On `consume_token`, atomically `UPDATE step_up_tokens SET consumed_at=now() WHERE jti=... AND consumed_at IS NULL RETURNING *`. Zero rows returned → already consumed → raise `StepUpError('already_consumed')`.

**Clock skew tolerance:** ±60 seconds on `iat`/`exp` per PyJWT default.

**Failure modes:** expired, consumed, signature_mismatch, intent_mismatch, sub_mismatch (when step-up page re-verifies current IAP session).

### 4.4 Step-up router

Location: `services/api-gateway/src/api_gateway/routers/step_up.py` (NEW)

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `POST` | `/api/step-up/issue` | Internal: called by BJR routers (e.g., `decisions.request_gate5_approval`). Issues token + sends WhatsApp. | IAP + RBAC `step_up:issue` (granted to admin + system) |
| `GET` | `/step-up/verify` | Public: step-up page server-component calls this to validate token + fetch decision summary. | Token in query string + IAP session match on `sub` |
| `POST` | `/step-up/consume` | Public: step-up page submits TOTP + decision here. | Token + TOTP + IAP session match |

The two public routes live at `/step-up/*` (not `/api/step-up/*`) so the Next.js pages can call them without the `/api` prefix rewrite. Rate-limited (10 req/min per IP).

### 4.5 Step-up web pages

Location: `web/app/step-up/`

Three single-screen pages, each ~200 LOC:

- `web/app/step-up/gate5-komisaris/[token]/page.tsx`
- `web/app/step-up/gate5-legal/[token]/page.tsx`
- `web/app/step-up/material-disclosure/[token]/page.tsx`

Plus one non-token-gated page:

- `web/app/mfa-enroll/page.tsx` (NEW — MFA enrollment is currently API-only per CLAUDE.md gotcha "MFA endpoints are accessible without MFA to avoid chicken-and-egg"; this page adds the missing UI surface)

**Page structure (identical pattern across all three token-gated pages):**

1. Server component fetches `/step-up/verify?token=<token>` on render
2. Displays: decision title + initiative type + readiness score + 16-item summary (🔒🟢🟡🔴)
3. Single action button: "Approve as {Role}" (or "Reject")
4. Single TOTP input field (6 digits, numeric keyboard on mobile)
5. On submit: `POST /step-up/consume` with `{totp, decision: approved|rejected}`
6. Success: auto-close after 3s + confirmation toast
7. Error: inline error + retry (up to 3x MFA failures per existing lockout policy)

**No navigation.** No sidebar, no header links, no "other actions." Monofunctional by design.

**Accessibility:** WCAG 2.1 AA. Focus lands on TOTP field on page load. Submit on Enter. Error messages screen-reader-friendly.

### 4.6 Graph schema extensions

Location: `packages/ancol-common/src/ancol_common/rag/graph_client.py`

Extends the existing `GraphClient` abstract interface with 6 new methods, implemented in both `SpannerGraphClient` and `Neo4jGraphClient`:

```python
async def upsert_decision_node(self, d: StrategicDecision) -> None
async def upsert_decision_evidence_edge(self, decision_id: UUID, evidence: EvidenceRef) -> None
async def upsert_satisfies_item_edge(self, evidence_id: UUID, item_code: BJRItemCode, decision_id: UUID) -> None
async def upsert_approved_by_edge(self, decision_id: UUID, user_id: UUID, half: Gate5Half) -> None
async def get_document_indicators(self, doc_id: UUID, doc_type: EvidenceType) -> list[DocumentIndicator]
async def get_decision_evidence(self, decision_id: UUID) -> list[EvidenceSummary]
```

**Node schema:**

```cypher
(d:Decision {
  id: UUID,
  title: string,
  status: string,            // DecisionStatus enum value
  readiness_score: float?,   // nullable if not computed
  corporate_score: float?,
  regional_score: float?,
  locked_at: timestamp?,
  initiative_type: string,
  origin: string,            // proactive|retroactive
  created_at: timestamp
})

(ev:Evidence {
  id: UUID,
  type: string               // EvidenceType enum: mom|contract|rkab_line|dd_report|...
})
// Note: Evidence nodes are thin; full data lives in PG. Graph only carries refs.

(item:ChecklistItem {
  code: string               // BJRItemCode enum value, e.g., PD-03-RKAB
})
// 16 nodes total, created once in migration; immutable.
```

**Edge schema:**

```cypher
(d)-[:SUPPORTED_BY {linked_at, linked_by}]->(ev)
(ev)-[:SATISFIES_ITEM {decision_id, evaluator_status}]->(item)
(d)-[:APPROVED_BY {half: "komisaris"|"legal", approved_at}]->(u:User)
(d)-[:DERIVED_FROM]->(m:MoM)              // only for retroactive decisions
(d)-[:REFERENCES_RKAB]->(rl:RKABLineItem)
```

**Backfill script:** `scripts/bjr_graph_backfill.py` (NEW). Reads `strategic_decisions`, `decision_evidence`, `bjr_checklist_items` tables; emits nodes + edges idempotently (re-run is safe). Completes in ~minutes for current volume; must complete before 6.4a ships.

### 4.7 `bjr_gate5.request_gate5_approval` flow

End-to-end path from chat tool to WhatsApp delivery:

```
User (business_dev) in chat: "Submit decision X for Gate 5 approval"
   │
   ▼
gemini-agent.tools.bjr_gate5.handle_request_gate5_approval(decision_id=X)
   │
   ▼ api_client.post("/api/decisions/X/gate5/request")
   │
   ▼ services/api-gateway/routers/decisions.py::request_gate5_approval()
   │   (NEW endpoint — wraps existing logic)
   │   Preconditions verified:
   │     - decision in bjr_gate_5 state
   │     - readiness_score >= BJR_GATE5_THRESHOLD (85.0)
   │     - no CRITICAL item flagged
   │     - no existing non-consumed tokens for this decision
   │   RBAC: require_permission("bjr:gate5_request")
   │
   ├──► Identify approvers from org chart + RBAC:
   │      komisaris_user = find_active_user_with_role('komisaris')
   │      legal_user = find_active_user_with_role('legal_compliance')
   │    (If multiple users per role → use pre-configured primary per decision initiative type)
   │
   ├──► step_up.issue_token(komisaris_user.iap_email, intent=GATE5_KOMISARIS, X, ttl=24h)
   │    step_up.issue_token(legal_user.iap_email, intent=GATE5_LEGAL, X, ttl=24h)
   │    (two rows into step_up_tokens table)
   │
   ├──► notifications.dispatcher.send_step_up(
   │        to=komisaris_user,
   │        channel='whatsapp',
   │        template='gate5_komisaris',
   │        link=f"{base_url}/step-up/gate5-komisaris/{tokenK}",
   │        decision_title=...
   │    )
   │    (same for legal_user)
   │
   ├──► Insert audit_trail: action='gate5_requested', by=initiator,
   │                       komisaris=..., legal=..., token_jtis=[...]
   │
   └──► Return to chat:
        "Gate 5 approval requests sent to Komisaris (Budi S.) and
         Legal (Siti R.) via WhatsApp. Approval SLA: 5 days. I'll
         notify you when both halves complete."
```

Same flow applies to material disclosure — `bjr_artifacts.file_material_disclosure_draft` issues a single step-up token (intent=`material_disclosure`) to the corp_secretary, who completes filing on the step-up page with MFA.

## 5. Data Flows

### 5.1 Gate 5 dual approval (chat-first with step-up)

```
STEP 1 — Request issued from chat (see § 4.7)
STEP 2 — Komisaris taps WhatsApp link
────────────────────────────────────
K opens /step-up/gate5-komisaris/{tokenK} in browser
   │
   ▼ Next.js server component: GET /step-up/verify?token={tokenK}
   │   API Gateway validates:
   │     - HMAC signature valid
   │     - not expired (exp > now)
   │     - not consumed (step_up_tokens.consumed_at IS NULL)
   │     - intent == 'gate5_komisaris' (matches URL)
   │     - K's current IAP session email == token.sub
   │   Returns: {decision_summary, checklist_status, risk_breakdown}
   │
   ▼ Page renders:
   │   ┌────────────────────────────────────────┐
   │   │ Decision: "Akuisisi PT Wahana Baru"    │
   │   │ Initiative type: Acquisition          │
   │   │ Readiness: 88/100 (Regional: 92, Corp: 88) │
   │   │                                        │
   │   │ 16-item checklist:                     │
   │   │   Pre-decision: 5/5 ✓                  │
   │   │   Decision:      5/5 ✓                 │
   │   │   Post-decision: 6/6 ✓                 │
   │   │   (tap to expand)                      │
   │   │                                        │
   │   │ [  Approve as Komisaris  ]            │
   │   │                                        │
   │   │ TOTP: [ _ _ _ _ _ _ ]                  │
   │   │                                        │
   │   │ Reject instead                         │
   │   └────────────────────────────────────────┘
   │
   ▼ K enters TOTP, clicks Approve
   │
   ▼ POST /step-up/consume?token={tokenK}
   │   body: {totp: "123456", decision: "approved"}
   │   API Gateway:
   │     1. verify_token(intent=GATE5_KOMISARIS)
   │     2. Re-verify K's IAP session == token.sub
   │     3. mfa.verify_totp(K.user_id, totp) → returns MFA JWT bound to K's IAP sub
   │     4. require_permission("bjr:gate5_komisaris")
   │     5. TX begin; SELECT ... FOR UPDATE on decisions.id=X; assert state == bjr_gate_5
   │     6. UPDATE step_up_tokens SET consumed_at=now() WHERE jti=tokenK_jti AND consumed_at IS NULL
   │        → if zero rows: raise 409 (race; someone else consumed)
   │     7. _ensure_gate5_row(decision_id=X) — existing idempotent helper
   │        (unique index on bjr_gate5_decisions.decision_id + IntegrityError fallback)
   │     8. UPDATE bjr_gate5_decisions
   │          SET komisaris_decision='approved',
   │              komisaris_id=K.user_id,
   │              komisaris_at=now(),
   │              komisaris_mfa_jti=mfa_jwt.jti
   │          WHERE decision_id=X
   │     9. INSERT audit_trail (action='gate5_komisaris_approved',
   │                            user_id=K, decision_id=X,
   │                            step_up_token_jti=tokenK_jti,
   │                            mfa_jwt_jti=mfa_jwt.jti,
   │                            chat_session_id=... if present)
   │     10. graph_client.upsert_approved_by_edge(decision_id=X, user_id=K, half=KOMISARIS)
   │     11. _maybe_finalize_gate5(decision_id=X)  — see STEP 4
   │   TX commit
   │
   ▼ Page shows "Approved. Closing..." + auto-close after 3s
     WhatsApp confirmation to K
     In-app notification to originator

STEP 3 — Legal taps WhatsApp link
─────────────────────────────────
Identical flow to STEP 2 with intent=GATE5_LEGAL, permission=bjr:gate5_legal,
updates legal_* columns. Also triggers _maybe_finalize_gate5().

STEP 4 — Finalization (triggered by the half that completes SECOND)
────────────────────────────────────────────────────────────────────
_maybe_finalize_gate5(decision_id=X):
    gate5 = SELECT * FROM bjr_gate5_decisions WHERE decision_id=X
    IF gate5.komisaris_decision=='approved' AND gate5.legal_decision=='approved':
        # CRITICAL ORDERING (existing CLAUDE.md gotcha):
        transition_decision_status(X, DecisionStatus.BJR_LOCKED)  # FIRST
        UPDATE bjr_gate5_decisions
          SET final_decision='approved', locked_at=now()
          WHERE decision_id=X                                      # THEN
        INSERT audit_trail (action='bjr_gate5_finalized', decision_id=X, ...)
        publish_pubsub('bjr-locked', {decision_id: X, locked_at: ...})
        # Passport PDF generation is async, driven by Pub/Sub consumer in Phase 6.5
        enqueue_cloud_task('generate_passport_pdf', decision_id=X)
        # Fanout:
        notify_chat_user(originator, "Decision X locked. Passport pending (typically <2min).")
        notify_whatsapp([direksi_responsible_for_X], "Decision X approved and locked.")
    ELIF 'rejected' IN [gate5.komisaris_decision, gate5.legal_decision]:
        transition_decision_status(X, DecisionStatus.REJECTED)
        notify(originator + approvers, "Decision X rejected at Gate 5")
```

**Invariants preserved (from v0.4.0.0 CLAUDE.md gotchas):**

- Gate 5 unique index on `bjr_gate5_decisions.decision_id` + `SELECT FOR UPDATE` — still in force at STEP 2 point 5 and 7
- Transition first, then set `final_decision=approved` — STEP 4 ordering unchanged
- MFA JWT bound to IAP `sub` — STEP 2 point 3 uses existing `mfa.verify_totp` which emits IAP-bound JWT; no change to binding logic
- Row-locked Gate 5 row — existing `_ensure_gate5_row` pattern

**New invariants introduced:**

- Step-up token single-use: DB-level via atomic `UPDATE ... WHERE consumed_at IS NULL`
- Token sub matches current IAP session: re-verified at both `/verify` and `/consume`
- Intent matches URL: a token issued for `gate5_komisaris` cannot consume `gate5_legal` endpoint

### 5.2 Document indicator (proactive enrichment)

```
User (any role) in chat: "Show me MoM BOD #5/2026"
   │
   ▼ Gemini LLM identifies document reference
   │
   ▼ LLM calls get_report(doc_id=...)  — existing tool
   │   Returns: doc metadata (title, date, status, etc.)
   │
   ▼ LLM (per system prompt directive) ALSO calls
   │ show_document_indicators(doc_id=..., doc_type='mom')
   │   → api_client.get(f"/api/documents/{id}/bjr-indicators")
   │   → graph_client.get_document_indicators(id, type)
   │      MATCH (ev:Evidence {id: $doc_id})
   │      MATCH (ev)<-[:SUPPORTED_BY]-(d:Decision)
   │      OPTIONAL MATCH (ev)-[si:SATISFIES_ITEM {decision_id: d.id}]->(item:ChecklistItem)
   │      RETURN d, collect(item.code) AS satisfied_items
   │   → Enriches with current DB state (readiness, gate5 status)
   │   → Returns list[DocumentIndicator]
   │
   ▼ LLM merges both tool responses into chat reply:
     ┌────────────────────────────────────────────────┐
     │ 📄 MoM BOD #5/2026 (2026-04-15)                 │
     │ Corp Sec: Rahmat  •  Status: Complete           │
     │                                                │
     │ Supports 2 strategic decisions:                │
     │                                                │
     │   🔒 Divestasi Hotel Jaya Ancol                 │
     │      readiness 94/100 • LOCKED 2026-04-01      │
     │      Passport: [ download ]                    │
     │      Satisfies: D-06-QUORUM ✓ D-07-SIGNED ✓    │
     │                                                │
     │   🟡 Akuisisi PT Wahana Baru                    │
     │      readiness 72/100 • awaiting DD            │
     │      Gate 5 not unlocked                        │
     │      Satisfies: D-06-QUORUM ✓                   │
     │      Missing:   PD-05-COI ⚠  PD-01-DD ⚠         │
     │                                                │
     │ Tap a decision to drill in, or ask             │
     │ "why is Akuisisi Wahana stuck?"                │
     └────────────────────────────────────────────────┘
```

**Agent Builder system prompt addition** (critical for proactive behavior):

> "Whenever you retrieve or reference a specific document (MoM, contract, RKAB line, DD/FS/SPI report, audit committee report, material disclosure, organ approval), you must immediately also call `show_document_indicators(doc_id, doc_type)` and weave the result into your reply. This applies to listing results, search results, and explicit lookups. Do not ask the user for permission. If the tool returns an empty indicator list, omit the BJR section silently."

**Performance & caching:**

- Graph query: <50ms p95 for 1-hop from evidence node
- Indicator enrichment query (decision state, readiness): cacheable per decision_id for 5 minutes via Redis (existing cache infra)
- Tool response size: ≤3KB typical, ≤8KB worst case (decision with 16 satisfied items + 16 missing)
- Fallback when `GRAPH_BACKEND=none`: SQL query `SELECT ... FROM decision_evidence JOIN strategic_decisions ... WHERE evidence_id=?` with composite index on `decision_evidence(evidence_id, evidence_type)` (add in migration 006)

### 5.3 Reverse indicator: decision → all evidence

Same graph shape, reverse direction:

```
User in chat: "What evidence supports decision X?"
  → bjr_evidence.show_decision_evidence(decision_id=X)
  → graph: MATCH (d:Decision {id: X})-[:SUPPORTED_BY]->(ev:Evidence)
  → groups evidence by item code it satisfies
  → Returns:
     Evidence for "Akuisisi PT Wahana Baru":

     Pre-decision:
       PD-01-DD: ⚠ missing — needs Due Diligence report
       PD-02-FS: ✓ FS Report #42 (uploaded 2026-03-15 by Budi)
       PD-03-RKAB: ✓ RKAB Line 2026-014 (Acquisition budget Rp 150 miliar)
       PD-04-RJPP: ✓ RJPP theme "Portfolio expansion 2025-2029"
       PD-05-COI: ⚠ needs review — found potential COI with Direksi Andi

     Decision:
       D-06-QUORUM: ✓ MoM BOD #5/2026 quorum met
       D-07-SIGNED: ✓ MoM BOD #5/2026 signatures complete
       ... (etc, 16 items)
```

## 6. Security & Compliance

### 6.1 Identity chain

Every BJR-touching action resolves to a single authenticated user via this chain:

```
Google Workspace SSO
  ↓ (SAML/OIDC session)
Vertex AI Agent Builder auth context (user email + groups)
  ↓ (webhook headers signed by Agent Builder)
services/gemini-agent/ main.py (reads user from X-Goog-Authenticated-User-Email)
  ↓ (IAP JWT attached to outbound API Gateway call)
services/api-gateway/ auth/iap.py (verifies IAP JWT, extracts sub + email)
  ↓ (require_permission check)
RBAC permission matrix (auth/rbac.py)
  ↓ (MFA step-up for MFA-gated actions only)
auth/mfa.py verify_totp + issue MFA JWT bound to sub
  ↓
audit_trail INSERT with full correlation IDs
```

**No anonymous operations.** Every mutation writes `audit_trail` with `user_id`, and — where applicable — `step_up_token_jti`, `mfa_jwt_jti`, `chat_session_id`, `chat_tool_name`.

### 6.2 Audit trail extensions

Migration 006 adds 4 nullable columns to existing `audit_trail`:

```sql
ALTER TABLE audit_trail ADD COLUMN chat_session_id VARCHAR(128);
ALTER TABLE audit_trail ADD COLUMN chat_tool_name VARCHAR(64);
ALTER TABLE audit_trail ADD COLUMN step_up_token_jti UUID;
ALTER TABLE audit_trail ADD COLUMN mfa_jwt_jti UUID;
-- existing: user_id, action, resource_type, resource_id, payload_json, created_at
```

**Auditor query:** "Show me all Gate 5 approvals in Q2 2026 with full provenance":

```sql
SELECT at.created_at, at.user_id, u.display_name, at.action,
       at.chat_session_id, at.chat_tool_name,
       at.step_up_token_jti, sut.issued_at AS token_issued,
       at.mfa_jwt_jti, me.method AS mfa_method, me.device_fingerprint,
       g.decision_id, g.komisaris_decision, g.legal_decision
FROM audit_trail at
LEFT JOIN step_up_tokens sut ON sut.jti = at.step_up_token_jti
LEFT JOIN mfa_events me ON me.jti = at.mfa_jwt_jti
LEFT JOIN bjr_gate5_decisions g ON g.decision_id = at.resource_id
LEFT JOIN users u ON u.id = at.user_id
WHERE at.action IN ('gate5_komisaris_approved','gate5_legal_approved','gate5_finalized')
  AND at.created_at BETWEEN '2026-04-01' AND '2026-06-30'
ORDER BY at.created_at;
```

Every row is reconstructible: who (user + MFA device), when (token + approval timestamps), where (chat session if applicable), what (decision + half), how (step-up flow).

### 6.3 Step-up token threat model

| Threat | Mitigation |
|---|---|
| Token theft via WhatsApp forward or screenshot | `sub` claim binds to target user's IAP email. Step-up page re-verifies current IAP session matches `sub`. Token useless to anyone else. |
| Token replay after first use | PG `step_up_tokens.consumed_at` with atomic UPDATE; second consume returns 0 rows. |
| Token forgery | HMAC-SHA256 with `MFA_JWT_SECRET` (32-byte random, rotated quarterly via KMS Secret Manager). |
| MITM between WhatsApp and browser | HTTPS + HSTS on `ancol.app`. WhatsApp links use `https://` only. |
| Social engineering ("click this urgent Gate 5 link") | MFA TOTP required even after clicking. Attacker needs physical access to approver's authenticator app AND valid IAP session. |
| Token lifetime attack (approver approves stale state) | Decision state re-checked at `/consume` (`SELECT FOR UPDATE`); if state changed between issue and consume, returns 409 and invalidates token. |
| Endpoint DDoS | Rate limit 10 req/min per IP on `/step-up/*` (existing FastAPI rate limit middleware). |
| Brute force TOTP on step-up page | Existing MFA lockout policy: 3 failures → 5-min lockout; 10 failures/hour → 1-hour lockout + admin alert. |
| Session fixation (attacker pre-provisions IAP session) | IAP sessions are Google-signed; cannot be forged without Google compromise. |

### 6.4 PII scrubbing policy (moderate)

Applied in `services/gemini-agent/src/gemini_agent/formatting.py` helpers:

| Data | Chat representation | Full-precision location |
|---|---|---|
| IDR values ≤ 1,000,000 | Full precision: `Rp 500.000` | (same) |
| IDR values > 1B | Rounded: `Rp 1,5 miliar` (1 decimal) | Passport PDF, step-up pages |
| IDR values > 1T | Rounded: `Rp 2,3 triliun` | Passport PDF, step-up pages |
| Person names (conflicted parties in COI) | Initials + role: `A.K. (Direksi)` | DD report PDF, Passport PDF |
| Person names (approvers, originators, staff) | Full name (they authored the action; not PII redaction context) | (same) |
| RPT entity names | Full name (legitimately published relationships) | (same) |
| DD findings | Risk rating + 1-sentence summary | Full report PDF (signed URL) |
| Contract values | Rounded as above | Contract PDF (signed URL) |

Scrubbing is applied **only in chat rendering**. Underlying APIs return full precision; responsibility for scrubbing lives in the chat tool handler's formatting step.

### 6.5 Data sovereignty

**Required configuration** (verified at start of Phase 6.4a — see § 9):

- Vertex AI Agent Builder resource deployed in `asia-southeast2`
- Gemini model routing pinned to `asia-southeast2` (fallback: `asia-southeast1` Singapore only if Jakarta unavailable for specific model; requires approval)
- Agent conversation storage (if Google retains any) in `asia-southeast2`
- Tool call payloads never leave region (webhook is a Cloud Run service in Jakarta)

**Verification procedure:** open GCP support ticket before Phase 6.4a week 1, confirm in writing. If any component is not region-pinned, escalate to GCP TAM or pivot to Option C (web-primary) before Phase 6.4b starts.

### 6.6 Chat transcript retention

Chat conversations persist in Google Workspace. Sensitive data flowing through chat includes RKAB line values, DD/FS findings, COI names (scrubbed per § 6.4), Gate 5 rationale.

**Three layers of protection (operational, not code):**

1. **Workspace admin retention policy:** 7-year retention for chats labeled `#BJR` (matches UU PT Pasal 100 records requirement), auto-delete after.
2. **Vault legal hold:** enabled for all BJR-related chats during active audits; overrides auto-delete.
3. **Moderate PII scrubbing in tool responses** (§ 6.4): reduces transcript sensitivity without sacrificing usability.

Operational kickoff (separate from code work): Workspace admin applies retention policy and legal hold infrastructure before 6.5 ships. Documented in `docs/RUNBOOK-BJR-RETENTION.md` (NEW).

### 6.7 RBAC enforcement

100% server-side. Never client-side or Agent-Builder-side.

- Webhook dispatcher (`main.py`) checks `allowed` set before dispatching — first line of defense.
- API Gateway `require_permission(key)` — second line of defense.
- If dispatcher forgets a tool, API Gateway still rejects.
- If Agent Builder exposes a tool to the wrong role, server rejects with 403.

This layered design means a misconfigured Agent Builder (e.g., tool exposed to Direksi that should only be for Komisaris) cannot escalate privileges — server still denies. The Agent Builder config is a UX optimization, not a security boundary.

## 7. Database Changes

### 7.1 Migration 006 — step_up_tokens + audit_trail extensions

```sql
CREATE TABLE step_up_tokens (
    jti         UUID PRIMARY KEY,
    sub         VARCHAR(255) NOT NULL,                 -- IAP email of target
    intent      VARCHAR(32)  NOT NULL,                 -- step_up_intent enum
    resource_id UUID         NOT NULL,                 -- decision_id or similar
    issued_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ  NOT NULL,
    consumed_at TIMESTAMPTZ  NULL,
    consumed_by_ip INET      NULL,
    issued_by_user UUID      NOT NULL REFERENCES users(id),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_step_up_tokens_sub_intent ON step_up_tokens (sub, intent, consumed_at);
CREATE INDEX idx_step_up_tokens_resource ON step_up_tokens (resource_id);
CREATE INDEX idx_step_up_tokens_expires ON step_up_tokens (expires_at) WHERE consumed_at IS NULL;

CREATE TYPE step_up_intent AS ENUM (
    'gate5_komisaris', 'gate5_legal', 'material_disclosure', 'mfa_enroll'
);

ALTER TABLE audit_trail ADD COLUMN chat_session_id VARCHAR(128);
ALTER TABLE audit_trail ADD COLUMN chat_tool_name VARCHAR(64);
ALTER TABLE audit_trail ADD COLUMN step_up_token_jti UUID;
ALTER TABLE audit_trail ADD COLUMN mfa_jwt_jti UUID;

CREATE INDEX idx_audit_trail_step_up ON audit_trail (step_up_token_jti) WHERE step_up_token_jti IS NOT NULL;
CREATE INDEX idx_audit_trail_mfa_jwt ON audit_trail (mfa_jwt_jti) WHERE mfa_jwt_jti IS NOT NULL;
CREATE INDEX idx_audit_trail_chat_session ON audit_trail (chat_session_id) WHERE chat_session_id IS NOT NULL;
```

**Rollback:** `DROP INDEX ...; ALTER TABLE audit_trail DROP COLUMN ...; DROP TABLE step_up_tokens; DROP TYPE step_up_intent;`

### 7.2 No additional indexes needed

The existing `idx_evidence_polymorphic` on `decision_evidence(evidence_type, evidence_id)` (from migration 005) already supports the SQL fallback query pattern in § 5.2 efficiently. The column ordering works for `WHERE evidence_id=? AND evidence_type=?` because PostgreSQL's planner uses the index for both equality predicates.

### 7.3 New Pydantic schemas

Location: `packages/ancol-common/src/ancol_common/schemas/step_up.py` (NEW)

```python
class StepUpIntent(StrEnum):
    GATE5_KOMISARIS = "gate5_komisaris"
    GATE5_LEGAL     = "gate5_legal"
    MATERIAL_DISCLOSURE = "material_disclosure"
    MFA_ENROLL      = "mfa_enroll"

class StepUpTokenClaims(BaseModel):
    sub: EmailStr
    intent: StepUpIntent
    resource_id: UUID
    jti: UUID
    iat: int
    exp: int

class IssuedToken(BaseModel):
    token: str           # JWT
    jti: UUID
    expires_at: datetime

class StepUpVerifyResponse(BaseModel):
    intent: StepUpIntent
    resource_id: UUID
    decision_summary: DecisionSummaryResponse | None
    checklist_summary: ChecklistSummaryResponse | None
    expires_at: datetime

class DocumentIndicator(BaseModel):
    decision_id: UUID
    decision_title: str
    status: DecisionStatus
    readiness_score: float | None
    is_locked: bool
    locked_at: datetime | None
    satisfied_items: list[BJRItemCode]
    missing_items: list[BJRItemCode]
    origin: DecisionOrigin  # proactive|retroactive
```

## 8. Testing Strategy

**Regression gate:** all 543 existing tests must pass unchanged at every phase. New work is additive.

### 8.1 Layer 1 — Unit tests (~55 new)

- `packages/ancol-common/tests/test_step_up.py` (~25): issuance, HMAC verification, expiration, replay rejection, wrong-user rejection, intent mismatch rejection, clock skew (±60s), atomic consume under concurrency (asyncio.gather two consumes → one wins), nonce uniqueness across 10k tokens.
- `services/gemini-agent/tests/test_tools_bjr_*.py` (~25): one handler per BJR tool. Mock `api_client` responses, verify param marshaling + response formatting + error paths.
- `services/gemini-agent/tests/test_formatting_bjr.py` (~10): PII scrubbing (IDR rounding, name initialing), indicator rendering, checklist summary compactness, tool response size ≤32KB.
- `services/gemini-agent/tests/test_indicator_rendering.py` (~5): empty indicator list (silent), 1-decision indicator, multi-decision indicator, truncation at 5+ decisions.

### 8.2 Layer 2 — Integration tests with DB (~25 new)

Extends existing `services/api-gateway/tests/_bjr_fixtures.py` helper module:

- `test_gate5_chat_flow_happy_path`: initiator → tokens issued → K consumes → L consumes → finalization → Passport enqueued.
- `test_gate5_parallel_race`: K and L consume within same event loop tick; row-lock resolves; finalize runs exactly once.
- `test_gate5_rejection_flows`: K rejects; K approves, L rejects; both reject independently.
- `test_gate5_token_lifecycle`: expired, already-consumed, wrong-user (cookie swap), wrong-intent, tampered signature, clock-skew boundary.
- `test_gate5_audit_trail_correlation`: every step writes correlated rows across `audit_trail` + `step_up_tokens` + `bjr_gate5_decisions` + `mfa_events`.
- `test_retroactive_bundle_chat_flow`: propose → confirm in chat → decision created with `origin='retroactive'`.
- `test_material_disclosure_chat_flow`: draft in chat → step-up token → MFA → filed state + audit_trail.
- `test_state_race_detection`: decision rejected between token issue and consume → 409 returned.

### 8.3 Layer 3 — Graph tests (~10 new)

- `test_graph_decision_node_upsert`: create, update, re-upsert idempotency.
- `test_graph_edges`: all 5 edge types, with property validation.
- `test_graph_indicator_query_correctness`: deterministic output for a known fixture (20 decisions, 100 evidence nodes).
- `test_graph_indicator_query_perf`: p95 <50ms on 10k-node synthetic graph.
- `test_graph_backfill_idempotency`: run backfill script 3x → same node+edge count.
- `test_graph_backend_parity`: Neo4j and Spanner implementations return identical results for the same fixture.

### 8.4 Layer 4 — Webhook contract tests (~10 new)

Extends `services/gemini-agent/tests/test_main.py`:

- Dispatch: each of 25 new tool names routes to correct handler.
- RBAC denial: each role's disallowed tool returns structured error.
- Per-role `allowed` sets: assert contents match § 4.2 table.
- Tool response size: representative large payload (20-item indicator) stays under 32KB.

### 8.5 Load tests (Phase 6.5)

k6 or Locust script, run in staging:

- **Gate 5 concurrency:** 20 simultaneous `request_gate5_approval` → verify `step_up_tokens` INSERT throughput, WhatsApp dispatcher queue handles rate, no deadlocks. Target: p99 end-to-end <500ms.
- **Indicator load:** 100 concurrent `show_document_indicators` calls → verify graph query cache hit rate >80%, p95 <100ms.
- **Finalization concurrency:** 50 decisions all reaching Gate 5 finalization within 1 minute → verify Pub/Sub backlog stays <30s, no Passport generation lost.

### 8.6 Manual staging validation

Automated testing cannot cover:

- **Actual Gemini Enterprise tool-calling behavior.** Scripted conversation: "Create decision X, link MoM Y, request Gate 5." Verify LLM correctly invokes `create_decision` → `link_evidence` → `request_gate5_approval` in sequence.
- **Proactive indicator rendering.** Scripted: "Show me contract Z." Verify `get_contract` + `show_document_indicators` both fire without user prompt.
- **WhatsApp delivery.** 3 test phone numbers receiving step-up links; click each, verify page loads, complete with MFA.
- **Step-up link UX on mobile.** iOS Safari, Android Chrome, WhatsApp in-app browser.
- **Agent Builder region pinning evidence.** Screenshots of configuration, GCP support ticket response.

## 9. Phasing

### Phase 6.4a — Chat read-only + graph extensions (2 weeks)

**Deliverables:**
- `services/gemini-agent/src/gemini_agent/tools/bjr_decisions.py` (read-only: `list`, `get`, `list_my_decisions`)
- `services/gemini-agent/src/gemini_agent/tools/bjr_readiness.py`
- `services/gemini-agent/src/gemini_agent/tools/bjr_evidence.py` (`show_document_indicators`, `show_decision_evidence`)
- `services/gemini-agent/src/gemini_agent/tools/bjr_passport.py`
- `packages/ancol-common/src/ancol_common/rag/graph_client.py` extensions (all 6 new methods, Neo4j + Spanner impls)
- `scripts/bjr_graph_backfill.py`
- Dispatcher + RBAC updates in `main.py`
- Layer 1 tests (~30), Layer 3 tests (~10), Layer 4 tests (~5)
- Delete `web/app/bjr/decisions/`, `web/app/bjr/wizard/`, `web/app/bjr/retroactive/` scaffolds
- **Blocker gate:** Vertex AI Agent Builder region verification complete (§ 6.5)

**Exit criteria:** chat can surface any existing decision + render indicators on all documents linked to it; all existing 543 tests pass; region verification complete.

### Phase 6.4b — Chat mutations (2 weeks)

**Deliverables:**
- `bjr_decisions.py` mutations (`create`, `update`)
- `bjr_evidence.py` mutations (`link_evidence`, `unlink_evidence`)
- `bjr_retroactive.py` (`propose_retroactive_bundle`, `confirm_retroactive_decision`)
- `bjr_rkab.py` (`match_rkab_line_items`, `list_rjpp_themes`)
- `bjr_artifacts.py` (DD/FS/SPI/AuditCom upload + organ approval)
- Agent Builder system prompt update: proactive `show_document_indicators` directive + PII scrubbing rules
- Layer 1 tests completion (~25 more), Layer 4 tests (~5 more)

**Exit criteria:** chat can create, edit, link evidence, retroactive-bundle without touching web UI; proactive indicators fire automatically in staging.

### Phase 6.4c — Step-up web + signed-link service (1-2 weeks)

**Deliverables:**
- `packages/ancol-common/src/ancol_common/bjr/step_up.py` (signed-link service)
- `packages/ancol-common/src/ancol_common/schemas/step_up.py`
- Migration 006 (step_up_tokens + audit_trail columns)
- `services/api-gateway/src/api_gateway/routers/step_up.py`
- `services/api-gateway/src/api_gateway/routers/decisions.py` — new `request_gate5_approval` endpoint
- `web/app/step-up/gate5-komisaris/[token]/page.tsx`
- `web/app/step-up/gate5-legal/[token]/page.tsx`
- `web/app/step-up/material-disclosure/[token]/page.tsx`
- `web/app/mfa-enroll/page.tsx` (NEW — no prior MFA UI existed)
- `services/api-gateway/src/api_gateway/notifications/dispatcher.py` — `step_up_whatsapp` channel
- `bjr_gate5.py` chat tool (`request_gate5_approval`, `check_gate5_status`)
- Layer 2 integration tests (~25)
- Kill switch: `STEP_UP_ENABLED` env var (default true in staging, false in prod)

**Exit criteria:** full Gate 5 flow works end-to-end in staging; all integration tests pass; brief external legal counsel on step-up design.

### Phase 6.5 — Integration + E2E + historical migration (2 weeks)

**Deliverables:**
- Pub/Sub topics + Cloud Tasks: `bjr-evidence-changed`, `bjr-locked`, `bjr-gate5-requested`, `bjr-passport-generate`
- Passport PDF generation async worker (WeasyPrint, CMEK bucket, signed URL)
- Historical migration: 500+ existing MoMs → retroactive Decisions via batch mode of `bjr/retroactive.py`
- Graph backfill full run with historical data
- Load tests: k6/Locust scripts per § 8.5
- Manual staging validation per § 8.6
- WhatsApp E2E with 3 test numbers
- `docs/RUNBOOK-BJR-RETENTION.md` drafted + shared with Workspace admin

**Exit criteria:** staging carries ≥500 decisions (mix of proactive + retroactive); Gate 5 load test green; WhatsApp delivery verified; Workspace retention policy activated.

### Phase 6.6 — Extract, polish, ship (1-2 weeks)

**Deliverables:**
- Extract `packages/ancol-common/bjr/` → new `services/bjr-agent/` Cloud Run service (as originally planned in v0.4.0.0 spec)
- Terraform: 3 new Pub/Sub topics, CMEK Passport bucket, step-up LB route, WhatsApp scaling config
- `/review` + `/codex` + `/simplify` on all new code (est. ~6500 LOC)
- Security review: step-up threat model, audit trail completeness, data sovereignty evidence
- External legal review sign-off (parallel to engineering; briefed at end of 6.4c)
- Staging soak (1 week minimum)
- Production deploy behind `BJR_ENABLED=true` + `STEP_UP_ENABLED=true`
- CHANGELOG + PROGRESS.md updates
- Version bump to v0.5.0.0

**Exit criteria:** production deploy green; 1-week soak passes without Gate 5 incidents; external counsel sign-off received.

### Total timeline

**8-10 weeks** from approval to production. Compared to original Phase 6.4-6.6 plan (11-12 weeks web-first): slightly faster because graph extensions fold into 6.4a rather than 6.5, and we skip building a full Next.js BJR dashboard.

## 10. Verification

Per-phase smoke tests to run before declaring the phase complete.

### Phase 6.4a

```bash
# All existing tests green
ruff check packages/ services/ scripts/ corpus/scripts/
ruff format --check packages/ services/ scripts/ corpus/scripts/
for svc in extraction-agent legal-research-agent comparison-agent reporting-agent api-gateway batch-engine email-ingest regulation-monitor gemini-agent; do
  PYTHONPATH=packages/ancol-common/src:services/$svc/src python3 -m pytest services/$svc/tests/ -q
done

# New chat tools work via webhook simulation
PYTHONPATH=packages/ancol-common/src:services/gemini-agent/src python3 -m pytest services/gemini-agent/tests/test_tools_bjr_decisions.py -v
PYTHONPATH=packages/ancol-common/src:services/gemini-agent/src python3 -m pytest services/gemini-agent/tests/test_tools_bjr_readiness.py -v
PYTHONPATH=packages/ancol-common/src:services/gemini-agent/src python3 -m pytest services/gemini-agent/tests/test_tools_bjr_evidence.py -v

# Graph extensions work
PYTHONPATH=packages/ancol-common/src python3 -m pytest packages/ancol-common/tests/test_graph_client_bjr.py -v

# Backfill script runs clean
PYTHONPATH=packages/ancol-common/src python3 scripts/bjr_graph_backfill.py --dry-run

# Region verification: screenshot of GCP console + support ticket response attached to 6.4a completion checklist
```

### Phase 6.4c

```bash
# Integration tests for Gate 5 chat flow
PYTHONPATH=packages/ancol-common/src:services/api-gateway/src python3 -m pytest services/api-gateway/tests/test_gate5_chat_flow.py -v
PYTHONPATH=packages/ancol-common/src python3 -m pytest packages/ancol-common/tests/test_step_up.py -v

# Manual: walk through Gate 5 flow in staging with 2 test users (Komisaris + Legal)
# Expected: chat initiates, 2 WhatsApp links arrive, each opens a step-up page,
#   TOTP completes approval, chat + WhatsApp receive finalization notification

# Lint + types
ruff check packages/ services/
cd web && npm run build && npm run lint
```

### Phase 6.5

```bash
# Load test
k6 run scripts/load_tests/gate5_concurrency.js
# Target: p99 end-to-end < 500ms at 20 concurrent Gate 5 requests

# Historical migration
PYTHONPATH=packages/ancol-common/src python3 scripts/bjr_retroactive_backfill.py --env=staging
# Expected: ≥500 decisions created, all reachable via chat

# Pub/Sub wiring
gcloud pubsub topics list --filter='name ~ bjr-'
# Expected: bjr-locked, bjr-evidence-changed, bjr-gate5-requested, bjr-passport-generate

# Indicator query cache
redis-cli KEYS 'indicator:doc:*' | wc -l   # should show populated cache after load test
```

### Phase 6.6

```bash
# Full /pre-ship pipeline
/run-tests
/review
/codex

# Staging soak metrics (after 1 week)
gcloud logging read 'resource.type="cloud_run_revision" AND
  resource.labels.service_name="ancol-gemini-agent" AND
  severity=ERROR' --limit=100 --format=json
# Expected: zero Gate 5 finalization errors, zero step_up token race errors

# Production deploy via standard GitHub Actions workflow
# Feature flag: BJR_ENABLED=true + STEP_UP_ENABLED=true in prod env vars
```

## 11. Rollback

**Per-phase rollback:**

- Any phase: revert commits on `main`. Migrations 006-007 have full downgrades.
- Feature flags in prod: set `STEP_UP_ENABLED=false` → step-up routers reject all requests with 503; chat tools gracefully handle by returning "Gate 5 approval temporarily unavailable; contact admin."
- `BJR_ENABLED=false` kill switch (existing from v0.4.0.0) disables all BJR chat tools + routers.

**Data rollback:**

- `step_up_tokens` is append-only (one row per issuance); dropping the table destroys issuance history but does NOT affect any decision state (approval state lives in `bjr_gate5_decisions`).
- `audit_trail` new columns are nullable; dropping reverts to v0.4.0.0 shape.
- Graph extensions: new Decision/Evidence nodes and edges can be deleted with idempotent cleanup script `scripts/bjr_graph_cleanup.py` (to be written alongside backfill).

**User-facing rollback:**

- If chat-first design has unforeseen UX issues, operations can route users back to the old Phase 6.4 web UI by:
  - Re-enabling the deleted `web/app/bjr/*` scaffolds (git revert)
  - Setting feature flag `BJR_CHAT_FIRST=false` in Agent Builder system prompt (removes proactive indicator directive)
- Chat tools remain available as secondary surface

## 12. Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Vertex AI Agent Builder not region-pinned to asia-southeast2 | **Critical** | Verify in week 1 of 6.4a. If blocked: escalate to GCP TAM; fallback to web-primary plan (reverts to original Phase 6.4). |
| External legal review requires novel defensibility changes | High | Brief counsel at end of 6.4c so they have 4 weeks. Design (step-up + existing banking-pattern parallel) is chosen specifically to minimize novelty. |
| Workspace retention policy not activated before production | High | Ops kickoff at plan approval (not engineering blocker). Retention policy is a Workspace admin action; technical work is documentation + runbook. |
| Proactive indicator spam (every doc mention triggers a tool call) → token cost or latency | Medium | Redis caching per-doc for 5min. Monitor tool-call volume in staging; tune system prompt if cost/latency exceeds budget. |
| WhatsApp delivery failures in Indonesia | Medium | Existing dispatcher has email fallback. Chat surfaces delivery status to originator. |
| Gate 5 step-up page bad UX on mobile WhatsApp in-app browser | Medium | Test in 6.5 with 3 phone/browser combos. Simplify page to WCAG-AA minimal form. |
| 16-item checklist display exceeds Agent Builder 32KB tool response limit | Low | Paginate to 5 items per response with "show more" pattern; truncate evidence refs to IDs + URLs. |
| Token signature key rotation breaks in-flight tokens | Low | Support dual keys during rotation (accept old + new for 1h); documented in runbook. |
| Chat session ID leakage to audit_trail creates PII concern | Low | `chat_session_id` is an opaque Google-assigned ID, not user PII. Verified with Workspace security docs. |
| Graph query performance degrades with 10k+ decisions | Low | Index on evidence_id in both backends. Cache. Monitor and re-tune if p95 exceeds target. |

## 13. Deferred

- **Rich card UI in chat.** Agent Builder supports card/structured responses but capabilities vary. If native rich cards become richer later, chat indicators can upgrade from markdown to cards without changing the underlying tool contract.
- **Voice input.** Out of scope; Gemini Enterprise may add over time.
- **Multi-decision bulk Gate 5.** Current flow is per-decision. A "approve 5 decisions at once" step-up page is deferred to v2 unless concrete demand appears.
- **Mobile app native integration.** Step-up pages work in mobile browsers today. A dedicated mobile app is deferred to v2.
- **Gemini Enterprise embedded in custom domain.** Users currently reach Gemini Enterprise at a Google-hosted URL. Embedding inside `ancol.app/chat` for single-domain UX is deferred to v2.
- **Real-time presence in chat.** ("Budi is reviewing decision X right now") — deferred; not required by any regulation.

## 14. Open Questions

1. **Who owns the Vertex AI Agent Builder region verification in week 1 of 6.4a?** — likely Erik + Platform team; confirm at plan approval.
2. **External legal counsel engagement timing.** — brief at end of 6.4c or earlier?
3. **WhatsApp sender number(s).** — current dispatcher uses Twilio sandbox; production needs an approved business number. Procurement lead time?
4. **MFA enrollment UX consistency.** — current `web/app/settings/mfa/` flow vs new `web/app/mfa-enroll/` page; consolidate or keep separate?

These are not blockers for writing the implementation plan but should be answered before Phase 6.4c.
