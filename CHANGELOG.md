# Changelog

All notable changes to the Ancol MoM Compliance System will be documented in this file.

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
