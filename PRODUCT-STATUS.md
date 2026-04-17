# PRODUCT-STATUS.md — Ancol MoM Compliance System

> Live document tracking the evolution from initial PRD to current product state.
> Last updated: 2026-04-17 evening (v0.4.0.0 shipped; Phase 6.4a started — chat-first BJR pivot)

---

## Product Identity

| Field | Value |
|-------|-------|
| **Product** | Ancol MoM Compliance System |
| **Company** | PT Pembangunan Jaya Ancol Tbk (IDX: PJAA) |
| **Platform** | Google Cloud Platform — Gemini Enterprise |
| **Region** | asia-southeast2 (Jakarta) — data sovereignty requirement |
| **Repository** | <https://github.com/erikgunawans/New-Ancol-Platform> |

---

## 1. Original PRD (2026-04-08)

**Problem:** PJAA needs to audit Board of Directors Minutes of Meetings (MoM) against structural compliance standards, substantive consistency, and regulatory alignment. 5+ years of historical MoMs in mixed formats (scans, PDFs, Word). Regulatory corpus scattered across physical copies, shared drives, and DMS.

**Initial requirements:**

- Multi-agent AI system on Gemini Enterprise for automated MoM auditing
- 4 specialized agents: Extraction, Legal Research, Comparison, Reporting
- Human-in-the-Loop gates at every stage (no compliance finding reaches the Board without human approval)
- 4 user roles: Corporate Secretary, Internal Auditor, Komisaris, Legal & Compliance
- Three-pillar compliance scorecard: Completeness (30%), Legal Compliance (35%), Governance Quality (35%)
- Batch processing for 500+ historical MoMs
- Data sovereignty: all data stays in Indonesia (asia-southeast2)

**Original design spec:** `docs/superpowers/specs/2026-04-08-agentic-mom-compliance-design.md`

---

## 2. Product Evolution Timeline

### v0.1 — Foundation (Phase 1, Sessions 1-3)

**Date:** 2026-04-08 to 2026-04-09
**What was built:**

- Shared package `ancol-common` — 9 Pydantic schemas, 15 ORM models, document state machine (14 states), Gemini client factory, config (31 settings)
- 14 Terraform modules: project-factory, networking, security, storage, database, pubsub, vertex-ai-search, bigquery, cloud-run, monitoring, workflows, document-ai, auth
- Regulation corpus: 69 chunks from OJK, IDX, UUPT, GCG guidelines, chunked for Vertex AI Search
- Database schema: 15 tables, 10 enum types, 22 indexes via Alembic
- Seed data: 9 users, 3 templates, 13 RPT entities, 14 regulations, 5 conflict precedences

**Key decision:** Chose `google-genai` SDK over `vertexai` SDK for Gemini access — simpler API, native Vertex AI support.

| Metric | Value |
|--------|-------|
| Files | ~152 |
| Tests | 0 |
| Services | 0 (infra + shared code only) |

---

### v0.2 — Core Agents (Phase 2, Sessions 4-7)

**Date:** 2026-04-09
**What was built:**

- 4 Gemini agent services on FastAPI:
  - **Extraction Agent** (Gemini 2.5 Flash) — structural parser, attendee extraction, resolution parsing, confidence scoring
  - **Legal Research Agent** (Gemini 2.5 Pro) — Vertex AI Search RAG grounding, citation validator (anti-hallucination Layer 3)
  - **Comparison Agent** (Gemini 2.5 Pro) — 5 red flag detectors (quorum, conflict of interest, RPT, missing signatures, procedural), severity scoring
  - **Reporting Agent** (Gemini 2.5 Flash) — scorecard calculator (30/35/35 weighting), PDF/Excel generators, executive summary in Bahasa Indonesia
- Document Processor service (Document AI OCR)
- API Gateway (28 REST endpoints across 10 routers)
- Cloud Workflows orchestrator (YAML) with 4-stage pipeline + HITL gates

**Key decision:** Flash for parsing/reporting (5x cheaper), Pro for legal reasoning/comparison (chain-of-thought needed).

| Metric | Value |
|--------|-------|
| Files | ~212 |
| Tests | 64 |
| Services | 6 |

---

### v0.3 — HITL + UI MVP (Phase 3, Sessions 7-8)

**Date:** 2026-04-09 to 2026-04-10
**What was built:**

- Next.js 15 frontend with React 19, Tailwind CSS, shadcn/ui
- 9 pages: Dashboard, Documents, Upload, HITL Review, Reports, Analytics, Batch, Settings, Login
- Role-based views via IAP + Cloud Identity SSO
- HITL review queue with approve/reject/modify flow
- Compliance scorecard with 6-month trend charts
- Batch page with auto-refresh progress bars

**Key decision:** Single Next.js app with role-based routing (not separate apps per role).

| Metric | Value |
|--------|-------|
| Files | ~237 |
| Tests | 64 (frontend untested) |
| Services | 7 (+ frontend) |

---

### v0.4 — Batch + Scale (Phase 4, Sessions 8-9)

**Date:** 2026-04-10
**What was built:**

- Batch Engine service — async orchestrator with rate limiter, concurrent processing (up to 50 docs)
- Token bucket rate limiter for Gemini API QPM control
- Batch job state machine: queued → running → paused → completed/failed
- Retroactive impact scanning (when regulations change, identify affected MoMs)
- Pause/resume support for batch jobs

**Key decision:** Rate limiter releases async lock before sleep to avoid serializing concurrent callers.

| Metric | Value |
|--------|-------|
| Files | ~260 |
| Tests | 82 |
| Services | 8 |

---

### v0.5 — Integration Services (Phase 5, Sessions 9-11)

**Date:** 2026-04-10 to 2026-04-11
**What was built:**

- Email Ingest service — Gmail API scanner, Cloud Scheduler (every 15 min), MoM filename detection, meeting date extraction, auto-upload to pipeline
- Regulation Monitor service — 5-source scraper (OJK, IDX, BAPEPAM-LK, industry, internal), relevance filtering, daily checks at 06:00 WIB
- Board Portal + ERP adapters (abstract base, graceful degradation when not configured)
- Auth middleware: IAP JWT verification, RBAC permission matrix, SSO
- Disaster Recovery module: Cross-region SQL replica, GCS replication (RPO 1hr / RTO 4hr)
- Analytics endpoints: trends, violations heatmap, coverage stats, HITL performance

**Key decision:** Email ingest scans every 15 minutes (not real-time push) because Corporate Secretary's Gmail is polled, not a webhook target.

| Metric | Value |
|--------|-------|
| Files | ~295 |
| Tests | 120 |
| Services | 10 |

---

### v0.6 — Deployment & Operations (Session 13)

**Date:** 2026-04-12
**What was built:**

- Fixed Terraform bugs: Pub/Sub `for_each` crash, 3 missing service accounts
- Wired all 10 Cloud Run services in `dev/main.tf`
- Cloud Scheduler module (email scan + regulation check)
- Fixed scanner.py `ext` NameError bug
- CI/CD pipeline fixes: 3 missing services, web frontend job, service naming
- Bulk upload scripts: `validate_historical.py` + `bulk_upload_historical.py`
- DR module wired with schedule dates

**Key decision:** Bulk upload uses CSV manifest → GCS → JSON records pattern (validate → upload → register → batch process).

| Metric | Value |
|--------|-------|
| Files | ~305 |
| Tests | 126 |
| Services | 10 |

---

### v1.0 — Gemini Enterprise as Primary Interface (Session 14)

**Date:** 2026-04-12
**What was built:**

- **Architecture pivot:** Primary interface moved from Next.js to Gemini Enterprise chat
- Vertex AI Agent Builder agent: "Ancol MoM Compliance Assistant"
- Webhook service (`gemini-agent`) — 8 tool handlers bridging Gemini function calling to API Gateway
- **Hybrid RAG** (3-layer retrieval):
  - Layer 1: Vertex AI Search (semantic vector, 69 regulation chunks)
  - Layer 2: Spanner Graph (regulation relationships — amendments, supersessions, cross-references, ~200 nodes, ~1000 edges)
  - Layer 3: Cloud SQL (exact lookups — MoMs per regulation, historical scores)
- Authority-ranked re-ranking: UUPT > POJK > SE-OJK > IDX > Internal
- Graph store abstraction: Spanner Graph (primary) + Neo4j AuraDS (fallback, behind feature flag)
- Conversational HITL: Gate 1 synchronous in chat, Gates 2-4 async with role-based polling
- Response formatting: all outputs in Bahasa Indonesia, markdown for chat
- Next.js frontend retained as analytics companion (trends, heatmaps, batch progress)

**Key decisions:**

- Vertex AI Agent Builder (not custom agent or Extensions) — native Gemini Enterprise sidebar experience
- Hybrid HITL — sync Gate 1 because uploader is present, async Gates 2-4 because different roles
- Spanner Graph over Neo4j — Google-native, same region, no vendor dependency, with Neo4j as documented fallback

| Metric | Value |
|--------|-------|
| Files | ~330 |
| Tests | 149 |
| Services | 11 |

---

## 3. Current Product State

### Architecture (v1.0)

```
User (Gemini Enterprise Chat)
  → Vertex AI Agent Builder ("Ancol MoM Compliance Assistant")
    → Webhook Service (gemini-agent, Cloud Run)
      → API Gateway (28 endpoints)
        → Document AI (OCR)
        → 4 Gemini Agents (Extraction, Legal Research, Comparison, Reporting)
        → Batch Engine (historical processing)
      → Hybrid RAG (Vertex AI Search + Spanner Graph + Cloud SQL)
    ← Formatted results in Bahasa Indonesia
  ← Compliance scorecard, findings, regulation Q&A in chat
  
Secondary: Next.js dashboard (analytics, trend charts, batch progress)
Background: Email Ingest (Gmail, every 15min), Regulation Monitor (OJK/IDX, daily 06:00 WIB)
```

### Services (11 Cloud Run)

| # | Service | Tech | Purpose |
|---|---------|------|---------|
| 1 | API Gateway | FastAPI | 28 REST endpoints, auth middleware |
| 2 | Document Processor | Document AI | OCR, text extraction |
| 3 | Extraction Agent | Gemini 2.5 Flash | MoM structure, attendees, resolutions |
| 4 | Legal Research Agent | Gemini 2.5 Pro + RAG | Regulation mapping, citation validation |
| 5 | Comparison Agent | Gemini 2.5 Pro | 5 red flag detectors, severity scoring |
| 6 | Reporting Agent | Gemini 2.5 Flash | Scorecard, PDF/Excel, executive summary |
| 7 | Batch Engine | Python | Async orchestrator, rate limiter |
| 8 | Email Ingest | Gmail API | Auto-scan inbox every 15 min |
| 9 | Regulation Monitor | Scraper | 5-source daily regulation check |
| 10 | Web Frontend | Next.js 15 | Analytics companion (secondary UI) |
| 11 | Gemini Agent | FastAPI | Webhook for Agent Builder, hybrid RAG |

### Quality Metrics

| Metric | Value |
|--------|-------|
| Source files | ~330 |
| Unit tests | 149 (across 9 testable services) |
| Terraform modules | 15 |
| GCP services used | Cloud Run, Cloud SQL, Cloud Storage, Pub/Sub, Cloud Workflows, Vertex AI Search, Vertex AI (Gemini), Cloud Spanner, BigQuery, Document AI, Cloud Scheduler, Cloud KMS, IAP, Cloud Armor, Secret Manager |
| Regulation corpus | 69 chunks, ~200 graph nodes, ~1000 edges |
| API endpoints | 28 |
| Document states | 14 |
| User roles | 5 (Corp Secretary, Internal Auditor, Komisaris, Legal & Compliance, Admin) |

---

## 4. What's Next

### Near-term (deployment)

- [ ] `terraform apply` — provision all GCP resources (~80+ resources)
- [ ] Build and deploy all 11 Cloud Run service images
- [ ] Run Alembic migration + seed data
- [ ] Seed Spanner Graph with regulation relationships
- [ ] Seed Vertex AI Search corpus (69 chunks)
- [ ] Configure Vertex AI Agent Builder agent in console
- [ ] Internal pilot: 5 real MoMs through full pipeline
- [ ] Gmail OAuth for email-ingest service

### Mid-term (pilot → production)

- [ ] Bulk upload 500+ historical MoMs
- [ ] Board Portal API integration (when APIs become available)
- [ ] ERP integration for RPT data
- [ ] Neo4j AuraDS evaluation (if Spanner Graph GQL proves limiting)
- [ ] Production environment (`infra/environments/prod/`)
- [ ] Load testing: concurrent batch processing at scale

### Long-term (product maturity)

- [ ] Custom Document AI model trained on 10-20 sample MoMs
- [ ] Multi-language support (English MoMs for international subsidiaries)
- [ ] Automated regulation corpus updates (Regulation Monitor → Vertex AI Search)
- [ ] Compliance prediction model (predict likely findings before full analysis)
- [ ] Mobile companion (Komisaris views on tablet)

---

## 5. Design Specs

| Date | Title | Path |
|------|-------|------|
| 2026-04-08 | Agentic MoM Compliance System (original PRD) | `docs/superpowers/specs/2026-04-08-agentic-mom-compliance-design.md` |
| 2026-04-12 | Gemini Enterprise Agent Builder Integration | `docs/superpowers/specs/2026-04-12-gemini-agent-builder-integration-design.md` |

### v0.4.1-dev — Phase 6.4 direction chosen: chat-first with step-up (in progress)

**Date:** 2026-04-17 evening

**What was decided:**

Pivoted Phase 6.4 from "web-UI-first BJR dashboard" to "Gemini Enterprise chat as primary BJR surface, with minimal web step-up for MFA-gated actions."

- **Scope shift:** Original Phase 6.4 = build full Next.js BJR dashboard + wizard + retroactive bundler UI on web. New scope = BJR tool handlers in `services/gemini-agent/`, new `/api/documents/{id}/bjr-indicators` endpoint, minimal 3-screen step-up web for Gate 5 dual-approval + material disclosure + MFA enrollment only.
- **Why:** Matches existing architectural principle (#6 below) that Gemini Enterprise is the primary interface for MoM + CLM. Preserves MFA-bound-to-IAP invariant without extending it to Workspace identity. Matches Indonesian banking pattern (Klik BCA, BRImo) — defensible to OJK/BPK auditors.
- **New phase structure:** 6.4a (chat read-only + graph, 2wk) → 6.4b (chat mutations, 2wk) → 6.4c (step-up web, 1-2wk) → 6.5 (integration + historical migration, 2wk) → 6.6 (extract `services/bjr-agent/` + ship, 1-2wk). Total 8-10 weeks.
- **Status:** Design spec + Phase 6.4a plan committed to `feat/bjr-gemini-primary-phase-6-4a`. Task 1 of 14 (rag/ package relocation to `packages/ancol-common/`) shipped. 13 tasks remain.

**Design spec:** `docs/superpowers/specs/2026-04-17-bjr-gemini-enterprise-primary-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-04-17-bjr-gemini-primary-phase-6-4a.md`

---

## 6. Key Design Principles

1. **No compliance finding without human approval.** Every AI output goes through a HITL gate before affecting scores or reports.
2. **Never fabricate citations.** All regulation references are grounded in Vertex AI Search corpus + Spanner Graph. Layer 3 anti-hallucination via citation validator.
3. **Data stays in Indonesia.** All infrastructure in asia-southeast2 (Jakarta). No data leaves the region.
4. **Authority hierarchy for conflicts.** When regulations conflict: UUPT (law) > POJK > SE-OJK > IDX > Internal.
5. **Bahasa Indonesia first.** All user-facing output in Bahasa Indonesia, English legal terms preserved as-is.
6. **Gemini-native experience.** Primary interaction through Gemini Enterprise chat, not a custom UI.
