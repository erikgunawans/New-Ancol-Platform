# Ancol MoM Compliance System — Progress Tracker

## Current State (as of 2026-04-17)

**ALL PHASES COMPLETE + MFA + WHATSAPP + NEO4J GRAPH.** v0.3.0.0. ~420 source files, 377 unit tests passing across 9 services (25+9+27+16+177+18+24+20+61), 21 ORM tables. MoM compliance + CLM + MFA (TOTP) + WhatsApp notifications + Neo4j AuraDS graph client. RBAC enforced on all 54 API endpoints with per-gate HITL role enforcement. Code reviewed with /simplify + /review (security hardened: MFA token identity binding, constant-time backup codes, RBAC on all /me/* endpoints).

**Repository:** https://github.com/erikgunawans/New-Ancol-Platform (standalone repo)

| Phase | Weeks | Status | Files | Tests |
|-------|-------|--------|-------|-------|
| **Phase 1: Foundation** | 1-3 | **COMPLETE** | ~152 | 0 |
| **Phase 2: Core Agents** | 4-8 | **COMPLETE** | +60 | 64 |
| **Phase 3: HITL + UI (MVP)** | 9-12 | **COMPLETE** | +25 | 0 (frontend) |
| **Phase 4: Batch + Scale** | 13-16 | **COMPLETE** | +23 | 18 |
| **Phase 5: Integration** | 17-20 | **COMPLETE** | +35 | 38 |
| **CLM Phase 1** | 1-8 | **COMPLETE** | +45 | 52 |
| **CLM Phase 4: PDF + Frontend** | — | **COMPLETE** | +8 | 13 |
| **PWA + Push** | — | **COMPLETE** | +N | 0 (frontend) |
| **CI Fix** | — | **COMPLETE** | 26 reformatted | 0 new |
| **Per-Gate HITL RBAC** | — | **COMPLETE** | +3 | +14 |
| **MFA (TOTP)** | — | **COMPLETE** | +3 new, +9 mod | +41 |
| **WhatsApp Notifications** | — | **COMPLETE** | +3 new, +8 mod | +27 |
| **Neo4j AuraDS Graph** | — | **COMPLETE** | +1 new, +2 mod | +13 |
| **Code Review + Security** | — | **COMPLETE** | 6 security fixes | 0 new |

**System is deployment-ready with Gemini Enterprise as primary interface.** MoM compliance + CLM + MFA + WhatsApp + Neo4j. Hybrid RAG with Spanner Graph or Neo4j AuraDS (swappable via `GRAPH_BACKEND` env var). 54 API endpoints, all RBAC-enforced. Security-reviewed.

---

## Key Documents

| Document | Path | Purpose |
|----------|------|---------|
| Design Spec | `docs/superpowers/specs/2026-04-08-agentic-mom-compliance-design.md` | Full system design: architecture, agents, edge cases, grounding strategy |
| This File | `PROGRESS.md` | Session-by-session log + resume guide |
| Project CLAUDE.md | `CLAUDE.md` | Conventions, tech stack, architecture overview for Claude |
| GitHub Repo | https://github.com/erikgunawans/New-Ancol-Platform | Standalone repository (separated from shadow-ai-detector) |

---

## Architecture Summary

- **5 Layers:** Document Ingestion (Document AI) → Presentation (Next.js 15) → Orchestration (4 Gemini agents + Cloud Workflows + Pub/Sub) → Data (Cloud SQL + Vertex AI Search + Cloud Storage + BigQuery) → Security/Observability/DR
- **4 Agents:** Extraction (Flash), Legal Research (Pro+RAG), Comparison (Pro), Reporting (Flash)
- **4 HITL Gates:** Between each agent stage — human approval required before next agent runs
- **4 User Roles:** Corp Secretary, Internal Auditor, Komisaris, Legal & Compliance
- **Region:** asia-southeast2 (Jakarta) — data sovereignty requirement
- **Tech:** Python 3.12 + FastAPI (agents/API), Next.js 15 + React 19 + Tailwind (frontend), Terraform (IaC), PostgreSQL 15

---

## Service Reference

### How to run tests per service

```bash
# Each service must be tested individually due to namespace isolation
PYTHONPATH=packages/ancol-common/src:services/extraction-agent/src python3 -m pytest services/extraction-agent/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/legal-research-agent/src python3 -m pytest services/legal-research-agent/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/comparison-agent/src python3 -m pytest services/comparison-agent/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/reporting-agent/src python3 -m pytest services/reporting-agent/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/api-gateway/src python3 -m pytest services/api-gateway/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/batch-engine/src python3 -m pytest services/batch-engine/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/email-ingest/src python3 -m pytest services/email-ingest/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/regulation-monitor/src python3 -m pytest services/regulation-monitor/tests/ -v
```

### Service inventory

| Service | Path | Model | Port | Tests | Key Files |
|---------|------|-------|------|-------|-----------|
| **Document Processor** | `services/document-processor/` | — (Document AI) | 8080 | 7 | `processor.py` (OCR pipeline), `main.py` (Pub/Sub handler) |
| **Extraction Agent** | `services/extraction-agent/` | Gemini 2.5 Flash | 8080 | 9 | `agent.py`, `parsers/structural.py`, `prompts/system.py` |
| **Legal Research Agent** | `services/legal-research-agent/` | Gemini 2.5 Pro + RAG | 8080 | 9 | `agent.py`, `retrieval/citation_validator.py` (critical safety code) |
| **Comparison Agent** | `services/comparison-agent/` | Gemini 2.5 Pro | 8080 | 27 | `analyzers/red_flags.py` (5 detectors), `analyzers/severity.py` |
| **Reporting Agent** | `services/reporting-agent/` | Gemini 2.5 Flash | 8080 | 16 | `generators/scorecard.py`, `generators/pdf.py`, `generators/excel.py` |
| **Batch Engine** | `services/batch-engine/` | — | 8080 | 18 | `engine.py` (orchestrator), `main.py` (trigger/pause/resume) |
| **Email Ingest** | `services/email-ingest/` | — | 8080 | 24 | `scanner.py` (Gmail scanner), `main.py` (Cloud Scheduler trigger) |
| **Regulation Monitor** | `services/regulation-monitor/` | — | 8080 | 20 | `checker.py` (5-source scraper), `sources.py` (OJK/IDX/industry) |
| **API Gateway** | `services/api-gateway/` | — | 8080 | 3 | `routers/` (10 routers, 28 endpoints) |
| **Frontend** | `web/` | — | 3000 | 0 | 9 pages, 3 shared components, API client |

### API Gateway endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/documents/upload` | POST | Upload MoM (multipart → GCS → Pub/Sub) |
| `/api/documents` | GET | List documents (status filter, pagination) |
| `/api/documents/{id}` | GET | Get single document |
| `/api/hitl/queue` | GET | HITL review queue (gate filter) |
| `/api/hitl/review/{id}` | GET | AI output for review per gate |
| `/api/hitl/decide/{id}` | POST | Submit HITL decision (approve/reject/modify) |
| `/api/reports` | GET | List compliance reports |
| `/api/reports/{id}` | GET | Report detail with scorecard |
| `/api/reports/{id}/download/{fmt}` | GET | Signed URL for PDF/Excel |
| `/api/users` | GET | List users (role filter) |
| `/api/users/{id}` | GET | Get user |
| `/api/audit` | GET | Audit trail entries |
| `/api/dashboard/stats` | GET | Dashboard aggregate statistics |
| `/api/dashboard/stats/trends` | GET | Monthly composite score trends |
| `/api/batch` | POST | Create a new batch job |
| `/api/batch` | GET | List batch jobs (status filter) |
| `/api/batch/{id}` | GET | Batch job detail with item breakdown |
| `/api/batch/{id}/pause` | POST | Pause a running batch job |
| `/api/batch/{id}/resume` | POST | Resume a paused batch job |
| `/api/analytics/trends` | GET | Monthly compliance score trends (all pillars) |
| `/api/analytics/violations` | GET | Violation type heatmap |
| `/api/analytics/coverage` | GET | Document processing coverage stats |
| `/api/analytics/hitl-performance` | GET | HITL gate decision metrics |

### Agent pipeline flow

```
Upload → Document Processor (Document AI OCR)
  → Pub/Sub: mom-ocr-complete
    → Extraction Agent (Gemini Flash → StructuredMoM)
      → DB: Extraction record → Status: hitl_gate_1
        → HITL Gate 1 (Corp Sec approves extraction)
          → Pub/Sub: hitl-gate_1-decided
            → Legal Research Agent (Gemini Pro + Vertex AI Search RAG → RegulatoryMapping)
              → Citation Validator (3-layer anti-hallucination check)
                → DB: RegulatoryContext → Status: hitl_gate_2
                  → HITL Gate 2 (Legal approves mapping)
                    → Comparison Agent (Gemini Pro chain-of-thought → Findings + Red Flags)
                      → Rule-based red flag scan (quorum, RPT, COI, circular, signatures)
                        → DB: ComplianceFindingRecord → Status: hitl_gate_3
                          → HITL Gate 3 (Auditor approves findings)
                            → Reporting Agent (Gemini Flash → Scorecard + PDF + Excel)
                              → DB: Report → GCS: PDF + Excel → Status: hitl_gate_4
                                → HITL Gate 4 (Dual approval: Audit Head + Corp Sec)
                                  → Status: complete
```

### Document state machine (14 states)

```
pending → processing_ocr → ocr_complete → extracting → hitl_gate_1
  → researching → hitl_gate_2 → comparing → hitl_gate_3
    → reporting → hitl_gate_4 → complete
Any processing state → failed (retry: failed → pending)
Any HITL gate → rejected (terminal)
```

Defined in: `packages/ancol-common/src/ancol_common/db/repository.py`

---

## Database

- **15 ORM tables** defined in `packages/ancol-common/src/ancol_common/db/models.py`
- **10 enum types**: user_role, mom_type, document_format, document_status, hitl_gate, hitl_decision, notification_channel, notification_status, batch_status, batch_item_status
- **22 indexes** for query performance
- **Migration 001** at `db/alembic/versions/001_initial_schema.py` — creates everything
- **Alembic config** at `alembic.ini` with async runner in `db/alembic/env.py`

### Seed data (`db/seed/`)

| File | Records | Content |
|------|---------|---------|
| `001_users.sql` | 9 | Users across 5 roles with manager chains |
| `002_mom_templates.sql` | 3 | Regular, circular, extraordinary MoM templates with quorum/signature rules |
| `003_related_party_entities.sql` | 13 | PT Pembangunan Jaya group entities for RPT detection |
| `004_regulation_index.sql` | 14 | All regulations in the compliance corpus |
| `005_conflict_precedences.sql` | 5 | Regulatory precedence rules |

Run with: `db/seed/run_seeds.sh`

---

## Regulatory Corpus

- **12 regulations** in structured Markdown format (4 internal + 5 external + 3 industry)
- **69 chunks** generated by `corpus/scripts/chunk_regulations.py --all`
- JSONL output in `corpus/{internal,external}/chunks/`
- Upload to Vertex AI Search via `corpus/scripts/upload_to_vertex_search.py --all`
- Quality test: `corpus/scripts/test_retrieval_quality.py --local-only -v` (20 queries, R=0.80)

### Regulations in corpus

| ID | Title | Type | Domain |
|----|-------|------|--------|
| UU-PT-40-2007 | UU Perseroan Terbatas | external | corporate_governance |
| POJK-33-2014 | Direksi dan Komisaris Emiten | external | board_governance |
| POJK-42-2020 | Transaksi Afiliasi dan Benturan Kepentingan | external | related_party_transactions |
| POJK-21-2015 | Tata Kelola Perusahaan Terbuka | external | corporate_governance |
| IDX-I-A | Pencatatan Saham BEI | external | listing_rules |
| ADART-PJAA | Anggaran Dasar PJAA | internal | corporate_charter |
| BOD-CHARTER-PJAA | Piagam Direksi | internal | board_charter |
| BOC-CHARTER-PJAA | Piagam Dewan Komisaris | internal | board_charter |
| RPT-POLICY-PJAA | Kebijakan Transaksi Pihak Berelasi | internal | related_party_transactions |
| PP-50-2011 | Rencana Induk Pembangunan Kepariwisataan Nasional | external | tourism |
| PP-22-2021 | Perlindungan dan Pengelolaan Lingkungan Hidup | external | environment |
| PERMEN-ATR-16-2021 | Hak Guna Bangunan | external | land |

---

## Infrastructure (Terraform)

14 modules in `infra/modules/`, composed in `infra/environments/dev/main.tf`:

| Module | Key Resources |
|--------|---------------|
| project-factory | GCP project, 22 API enables |
| networking | VPC, subnet (asia-southeast2), Cloud NAT, VPC connector |
| security | KMS keyring, 7 service accounts, Secret Manager, Cloud Armor WAF |
| database | Cloud SQL PostgreSQL 15, private IP, HA-ready |
| storage | 3 CMEK-encrypted buckets (raw/processed/reports) with 10yr lifecycle |
| pubsub | 8 topics + 8 DLQ topics + subscriptions |
| cloud-run | Reusable module for all services |
| document-ai | Form Parser processor + Eventarc trigger |
| vertex-ai-search | Regulatory corpus datastore + search engine |
| bigquery | Audit dataset, compliance_scores, log sink, 3 analytics views |
| monitoring | 7 alert policies (agent errors, DB CPU, DLQ, HITL SLA, batch failure, corpus staleness, Gemini quota) |
| auth | IAP brand + OAuth client |
| workflows | Full 4-stage orchestrator YAML with HITL wait gates |
| disaster-recovery | Cross-region SQL replica, GCS replication (hourly), replica lag alert (RPO 1hr / RTO 4hr) |

---

## Frontend (Next.js 15)

All source in `web/src/`. Key files:

| File | Purpose |
|------|---------|
| `lib/api.ts` | API client — 17 functions matching all API Gateway endpoints |
| `lib/auth.ts` | RBAC route-level permission matrix per role (incl. batch) |
| `lib/utils.ts` | Score colors/grades/labels (Bahasa Indonesia), severity colors |
| `types/index.ts` | 16 TypeScript interfaces mirroring Python Pydantic schemas |
| `components/shared/sidebar.tsx` | 8-item nav with active state |
| `components/shared/header.tsx` | Top bar + notification center |

### 9 pages

| Route | Role | Features |
|-------|------|----------|
| `/scorecard` | Komisaris | Stat cards, score pills (A-F), status distribution |
| `/upload` | Corp Secretary | Drag-drop, multi-file, mom type, date picker |
| `/documents` | All | Status-filtered table, OCR confidence |
| `/review` | Auditor/Legal | Gate-filtered queue cards |
| `/review/[id]` | Auditor/Legal | Scorecard, red flags, AI output, approve/reject |
| `/reports` | All | Score cards, PDF/Excel download |
| `/regulations` | Legal | External + internal regulation cards |
| `/batch` | Corp Secretary | Batch job cards, progress bar, pause/resume, auto-refresh |
| `/audit-trail` | Auditor | Timestamped action/actor/resource table |

---

## Completed — Phase 4: Batch + Scale + Analytics

| Step | Task | Status |
|------|------|--------|
| 13.1 | Batch tables migration | **DONE** (existed in migration 001) |
| 13.2 | Batch job API endpoints (create, list, get, pause, resume) | **DONE** |
| 13.3 | Batch processing engine (parallel 10-50 docs, rate limiting, retry, resumable) | **DONE** |
| 13.4 | Gemini API token bucket rate limiter | **DONE** |
| 13.5 | Historical template versions in registry | Deferred to Phase 5 |
| 13.6 | Retroactive impact scanning (corpus update triggers re-audit) | Deferred to Phase 5 |
| 13.7 | Batch UI page (progress dashboard with auto-refresh) | **DONE** |
| 13.8 | BigQuery analytics views (trends, violations, coverage) | **DONE** |
| 13.9 | Trend charts on Komisaris dashboard | **DONE** |
| 13.10 | Monitoring alerts (HITL SLA, batch failure, corpus staleness, Gemini quota) | **DONE** |
| 13.11 | Process 500+ historical MoMs | Operational — requires deployed system |
| 13.12 | Analytics API (trends, violations, coverage, HITL performance) | **DONE** |

## Completed — Phase 5: Integration

| Step | Task | Status |
|------|------|--------|
| 17.1 | Email auto-ingest service (Gmail API + Pub/Sub + Cloud Scheduler) | **DONE** |
| 17.2 | Board portal integration adapter | **DONE** |
| 17.3 | ERP connection adapter (RPT cross-check) | **DONE** |
| 17.4 | OJK/IDX/industry regulation auto-monitor (5 sources, keyword filter) | **DONE** |
| 17.5 | Industry regulation expansion (+3 regulations: tourism, environment, land) | **DONE** |
| 17.6 | SSO auth middleware (IAP → DB user resolver) | **DONE** |
| 17.7 | DR infrastructure (cross-region replica, GCS replication, RPO 1hr/RTO 4hr) | **DONE** |
| 17.8 | Historical template versioning (version timeline, date-based auto-resolve) | **DONE** |
| 17.9 | Retroactive impact scanning (scan + re-process affected MoMs) | **DONE** |

## Post-Launch Operations

| Task | Priority |
|------|----------|
| Deploy to GCP dev environment | HIGH |
| Run terraform init + apply | HIGH |
| Process 500+ historical MoMs via batch engine | HIGH |
| Internal pilot with 5 real BoD MoMs | HIGH |
| Configure Gmail OAuth for email ingest | MEDIUM |
| Connect board portal + ERP APIs (when available) | MEDIUM |
| Annual DR drill (RPO/RTO validation) | LOW |
| Cloud Scheduler cron setup (email scan, reg monitor) | MEDIUM |

---

## File Structure

```
New-Ancol-Platform/                    (~295 files)
├── .github/workflows/
│   ├── ci.yml                         Lint (ruff) + test (pytest) + TF validate
│   └── deploy-agents.yml             Per-service Cloud Run deploy on merge
├── infra/                             Terraform (44 files)
│   ├── environments/dev/              Dev composition (main.tf, variables, outputs, terraform.tfvars)
│   └── modules/                       14 modules (project-factory, networking, security, database,
│                                      storage, pubsub, cloud-run, document-ai, vertex-ai-search,
│                                      bigquery, monitoring, auth, workflows, disaster-recovery)
├── packages/ancol-common/             Shared Python package (26 files)
│   ├── pyproject.toml                 Dependencies: pydantic, sqlalchemy, asyncpg, google-genai, etc.
│   └── src/ancol_common/
│       ├── schemas/                   9 Pydantic v2 schemas (mom.py is the critical contract)
│       ├── db/                        connection.py, models.py (15 tables), repository.py (state machine)
│       ├── gemini/                    client.py (Vertex AI factory), grounding.py (RAG tool), rate_limiter.py
│       ├── pubsub/                    publisher.py, subscriber.py
│       ├── auth/                      iap.py (JWT verify), rbac.py (permission matrix), middleware.py (SSO)
│       ├── integrations/              base.py, board_portal.py, erp.py
│       ├── audit/                     logger.py (PostgreSQL + BigQuery dual-write)
│       ├── notifications/             email.py (SendGrid), in_app.py
│       ├── utils.py                   Shared: parse_indonesian_date, detect_document_format, parse_gcs_uri, SYSTEM_USER_ID
│       └── config.py                  31 environment-based settings
├── services/
│   ├── document-processor/            IMPLEMENTED — Document AI OCR pipeline
│   │   ├── src/document_processor/    main.py, processor.py
│   │   ├── tests/                     test_main.py (4 tests), test_processor.py (3 tests)
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── extraction-agent/              IMPLEMENTED — Gemini Flash structured extraction
│   │   ├── src/extraction_agent/      agent.py, main.py, prompts/ (system + few_shot), parsers/structural.py
│   │   ├── tests/                     test_structural.py (6), test_main.py (3), fixtures/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── legal-research-agent/          IMPLEMENTED — Gemini Pro + Vertex AI Search RAG
│   │   ├── src/legal_research_agent/  agent.py, main.py, prompts/system.py, retrieval/citation_validator.py
│   │   ├── tests/                     test_citation_validator.py (6), test_main.py (3)
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── comparison-agent/              IMPLEMENTED — Red flags + severity scoring
│   │   ├── src/comparison_agent/      agent.py, main.py, prompts/system.py,
│   │   │                              analyzers/red_flags.py (5 detectors), analyzers/severity.py
│   │   ├── tests/                     test_red_flags.py (15), test_severity.py (12)
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── reporting-agent/               IMPLEMENTED — Scorecard + PDF + Excel
│   │   ├── src/reporting_agent/       agent.py, main.py, prompts/system.py,
│   │   │                              generators/scorecard.py, generators/pdf.py, generators/excel.py
│   │   ├── tests/                     test_scorecard.py (11), test_pdf.py (5)
│   │   ├── Dockerfile                 (includes WeasyPrint deps: pango, cairo, noto fonts)
│   │   └── pyproject.toml
│   ├── batch-engine/                  IMPLEMENTED — Batch processing engine
│   │   ├── src/batch_engine/          main.py (trigger/pause/resume), engine.py (async orchestrator)
│   │   ├── tests/                     test_main.py (1), test_engine.py (17)
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── email-ingest/                  IMPLEMENTED — Gmail auto-ingest
│   │   ├── src/email_ingest/          main.py, scanner.py (filename detection, date extraction)
│   │   ├── tests/                     test_main.py (1), test_scanner.py (17)
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── regulation-monitor/            IMPLEMENTED — OJK/IDX/industry regulation scraper
│   │   ├── src/regulation_monitor/    main.py, checker.py, sources.py (5 sources)
│   │   ├── tests/                     test_main.py (2), test_sources.py (18)
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   └── api-gateway/                   IMPLEMENTED — Central REST API (28 endpoints)
│       ├── src/api_gateway/           main.py, routers/ (documents, hitl, reports, users, audit, dashboard, batch, analytics, templates, retroactive)
│       ├── tests/                     test_main.py (3)
│       ├── Dockerfile
│       └── pyproject.toml
├── db/
│   ├── alembic/
│   │   ├── env.py                     Async migration runner (SQLAlchemy 2.0 AsyncEngine)
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 001_initial_schema.py  15 tables, 10 enums, 22 indexes, all FK constraints
│   └── seed/
│       ├── 001_users.sql              9 users across 5 roles
│       ├── 002_mom_templates.sql      3 MoM templates (regular/circular/extraordinary)
│       ├── 003_related_party_entities.sql  13 RPT entities (PT Pembangunan Jaya group)
│       ├── 004_regulation_index.sql   14 regulations
│       ├── 005_conflict_precedences.sql  5 precedence rules
│       └── run_seeds.sh
├── corpus/
│   ├── internal/                      4 regulation .md files + chunks/ (4 JSONL + manifest)
│   ├── external/                      8 regulation .md files + chunks/ (5 JSONL + manifest)
│   └── scripts/
│       ├── chunk_regulations.py       Article-level chunker → JSONL
│       ├── upload_to_vertex_search.py Vertex AI Search uploader (upsert, dry-run)
│       └── test_retrieval_quality.py  20 queries, P/R measurement
├── web/                               Next.js 15 frontend
│   ├── package.json                   Next.js 15, React 19, Tailwind
│   ├── tsconfig.json, tailwind.config.ts, next.config.ts, postcss.config.mjs
│   ├── Dockerfile                     Multi-stage Node 22 standalone build
│   └── src/
│       ├── app/
│       │   ├── layout.tsx, page.tsx, globals.css
│       │   └── (dashboard)/           layout.tsx + 9 page routes
│       │       ├── scorecard/         Komisaris dashboard + trend charts
│       │       ├── upload/            Corp Sec file upload
│       │       ├── documents/         Document list
│       │       ├── review/            HITL queue + [id] detail
│       │       ├── reports/           Report archive
│       │       ├── batch/             Batch processing dashboard
│       │       ├── regulations/       Corpus explorer
│       │       └── audit-trail/       Audit viewer
│       ├── components/shared/         sidebar.tsx, header.tsx, notification-center.tsx
│       ├── lib/                       api.ts, auth.ts, utils.ts
│       └── types/                     index.ts (10 TS interfaces)
├── scripts/setup-local.sh
├── docs/superpowers/specs/            Design spec
├── alembic.ini                        Root Alembic config
├── pyproject.toml                     Root workspace: ruff, pytest, Python 3.12
├── .python-version                    3.12
├── .gitignore
└── README.md
```

---

## Session Log

### Session 26 — 2026-04-17

**Scope:** Neo4j AuraDS graph client completion + code review + security hardening

- **Neo4j graph client completed**: Implemented 2 remaining contract Cypher queries (`get_related_regulations_for_contract`, `get_related_contracts`) + `close()` method. All 7 abstract methods now fully implemented.
- **Code simplification** (`/simplify`): Consolidated 3x `VALID_CHANNELS` constants → 1, added `UserResponse.from_user()` class method, extracted `_clear_mfa_fields()` helper, fixed `datetime.now()` → `datetime.now(UTC)`, fixed `notification_channels` type annotation `dict` → `list`, parallelized notification dispatch with `asyncio.gather()`, batched role lookup in dispatcher.
- **Security review** (`/review`): Fixed 6 security issues — MFA token identity binding (P0), constant-time backup code verification, RBAC on all `/me/*` endpoints, notification exception logging, `DELETE` → `POST` for MFA disable (HTTP spec), enrollment race condition prevention.
- **13 new Neo4j tests**, updated MockGraphClient with contract test data.

**Files modified:** 20 files (auth/mfa.py, notifications/dispatcher.py, routers/users.py, routers/notifications.py, routers/hitl.py, routers/audit.py, routers/contracts.py, routers/documents.py, routers/drafting.py, routers/reports.py, neo4j_graph.py, test_rag_orchestrator.py, + 3 new files)
**Tests:** 377 passing across 9 services (25+9+27+16+177+18+24+20+61). 0 lint errors.

---

### Session 25 — 2026-04-17

**Scope:** WhatsApp phone field + notification delivery wiring

- **User model expanded**: Added `phone_number` (String(20), unique, E.164 format) + `notification_channels` (JSONB, default `["email", "in_app"]`).
- **Notification dispatcher created**: Unified `send_notification()` routes to email/WhatsApp/in-app per user preferences. `notify_gate_reviewers()` finds eligible reviewers via GATE_PERMISSIONS and dispatches.
- **HITL notifications wired**: Gate transitions now auto-notify next-gate reviewers.
- **User profile endpoint**: `PATCH /me/profile` for phone + notification preferences. `GET/PATCH /me/preferences` on notifications router.
- **Frontend type updated**: `phone_number?` + `notification_channels?` on User interface.
- **Alembic migration 004**: phone_number + notification_channels columns.

**Files modified/created:** 11 files. 27 new tests.
**Tests:** 364 passing (25+9+27+16+177+18+24+20+48).

---

### Session 24 — 2026-04-17

**Scope:** MFA (TOTP) implementation

- **Core MFA module** (`auth/mfa.py`): Fernet encryption for TOTP secrets, TOTP generation/verification (pyotp), backup codes (SHA-256 hashed, one-time use), JWT session tokens, `require_mfa_verified()` FastAPI dependency.
- **6 MFA endpoints**: status, enroll (QR code), confirm, verify (sets cookie), disable, admin reset.
- **MFA enforcement**: Router-level dependency on 6 sensitive routers (documents, hitl, contracts, drafting, reports, audit). Kill switch via `MFA_ENABLED=false` (default).
- **Alembic migration 003**: 4 MFA columns on users table.
- **41 new tests** across 9 test classes.

**Files modified/created:** 14 files. New deps: pyotp, pyjwt, qrcode.
**Tests:** 337 passing (25+9+27+16+150+18+24+20+48).

---

### Session 23 — 2026-04-16

**Scope:** Per-gate HITL role enforcement

- **Per-gate RBAC implemented**: HITL endpoints now enforce gate-specific roles instead of the union `hitl:decide` permission. Gate 1: corp_secretary + admin. Gate 2: internal_auditor + legal_compliance + admin. Gate 3: internal_auditor + admin. Gate 4: corp_secretary OR internal_auditor + admin (dual approval).
- **Queue filtering**: `/hitl/queue` now only shows documents at gates the user's role can review. Corp secretary sees gates 1+4, internal auditor sees 2+3+4, legal compliance sees 2 only, admin sees all.
- **Review/decide enforcement**: `/hitl/review/{id}` and `/hitl/decide/{id}` return 403 if the user lacks permission for the document's current gate.
- **New helpers in `rbac.py`**: `GATE_PERMISSIONS`, `check_gate_permission()`, `get_user_visible_gates()`.
- **14 new tests**: Full role x gate permission matrix, string role input, edge cases.

**Files modified:** `auth/rbac.py`, `routers/hitl.py`, `tests/test_rbac_enforcement.py`
**Tests:** 296 passing across 9 services (was 282). api-gateway: 95 -> 109 (+14).

---

### Session 22 — 2026-04-16

**Scope:** Architecture diagram + system guide + project sync

- **Architecture diagram created** using Excalidraw MCP: 6-layer dark-theme diagram covering all 11 Cloud Run services, 4 HITL gates, Pub/Sub orchestration, hybrid RAG data layer. Shareable Excalidraw link generated.
- **Discovered:** Excalidraw export requires native `containerId`/`boundElements` text binding (MCP `label` shorthand doesn't export). Fixed and re-exported.
- **System guide written:** `docs/SYSTEM-GUIDE.md` — 13-section technical guide covering full end-to-end flow: document ingestion, 4-agent pipeline, HITL gates, orchestration (Cloud Workflows + Pub/Sub), CLM subsystem, Gemini Enterprise interface, data layer, auth/RBAC, frontend, infrastructure. All details sourced from codebase.
- **Project sync** run to update all state files.

**Files modified:** PROGRESS.md, PRODUCT-STATUS.md, docs/SYSTEM-GUIDE.md (new), memory files
**Tests:** 282 passing (25+9+27+16+95+18+24+20+48). All green.

---

### Session 21 — 2026-04-15

**Scope:** CI Pipeline Fix

- **CI workflow rewritten**: Removed Postgres service container + `pip install` per-service approach. Replaced with PYTHONPATH-based per-service test loop (matches local dev workflow). Added `scripts/` and `corpus/scripts/` to ruff lint/format paths.
- **Ruff format**: 26 files reformatted (enum values one-per-line, parenthesized context managers, trailing commas, string literals).
- **No logic changes** — purely CI pipeline + formatting fixes.
- **PR #4** created (`fix/ci-failures` → `main`).

**Files modified:** 26 files (ci.yml, models.py, api_client.py, graph_client.py, spanner/neo4j_graph.py, tools/*, tests/*, scripts/*, corpus/scripts/*)
**Tests:** 282 passing across 9 services. 0 lint errors. 0 format issues.

---

### Session 1 — 2026-04-08

**Scope:** Brainstorming + design spec + implementation plan

- Brainstormed all requirements: MoM formats, regulatory corpus, user roles, scale, GCP greenfield, language
- Chose Multi-Agent + HITL Gates architecture (Approach C)
- Self-audited and found 10 gaps (Document AI layer, event bus, auth, audit trail, regulatory versioning, notifications, batch, templates, monitoring, DR) — all fixed in revised architecture
- Wrote 309-line design spec
- Created 80+ step implementation plan, chose Python 3.12 + FastAPI over Node.js

### Session 2 — 2026-04-09

**Scope:** Phase 1 Week 1 — Terraform infrastructure + ancol-common package

- **112 files created**
- 13 Terraform modules (65 resources): project-factory, networking, security, storage, database, pubsub, cloud-run, document-ai, vertex-ai-search, bigquery, monitoring, auth, workflows
- ancol-common package (26 files): 8 Pydantic schemas, 15 ORM models, document state machine (14 states), Gemini client factory, Pub/Sub helpers, IAP auth, RBAC, audit logger, SendGrid notifications, 21 settings
- CI/CD pipelines (2 files): lint + test + TF validate on PR, per-service Cloud Run deploy
- Pulled forward steps 2.1-2.3, 2.8, 3.1, 3.8 from later weeks

### Session 3 — 2026-04-09

**Scope:** Phase 1 Week 2 — Alembic migrations, seed data, document-processor

- **17 files created** (total: 129)
- Alembic migration 001: 15 tables, 10 enum types, 22 indexes, UUID primary keys
- 5 seed SQL files: 9 users, 3 MoM templates (with quorum/signature rules per UU PT), 13 RPT entities (PT Pembangunan Jaya group), 14 regulations, 5 conflict precedences
- Document-processor service: FastAPI + Document AI OCR pipeline (download raw → Document AI Form Parser → extract text/tables/confidence → write JSON → update DB → publish Pub/Sub)

### Session 4 — 2026-04-09

**Scope:** Phase 1 Week 3 — Regulatory corpus + Vertex AI Search

- **12 source + 11 generated files** (total: ~152)
- Chunking script: article-level splitting from structured Markdown, JSONL output with metadata
- 9 regulation source files (4 internal + 5 external) covering 69 total chunks
- Upload script to Vertex AI Search (upsert, rate-limited, dry-run mode)
- Retrieval quality test: 20 queries across 6 domains, local baseline R=0.80

### Session 5 — 2026-04-09

**Scope:** Phase 2 Weeks 4-5 — Extraction Agent + Legal Research Agent

- **23 files created** (total: ~175), 12 tests
- Extraction Agent: Gemini Flash, structural parser (quorum/signature/section validation), Bahasa Indonesia system prompt, few-shot examples, golden test fixture (sample MoM with RPT + performance data)
- Legal Research Agent: Gemini Pro + Vertex AI Search RAG, citation validator (3-layer anti-hallucination: retrieval score ≥0.5, source ID verification, text content check — zero tolerance for unsourced citations)

### Session 6 — 2026-04-09

**Scope:** Phase 2 Weeks 6-7 — Comparison Agent + Reporting Agent

- **24 files created** (total: ~199), 43 new tests (55 total)
- Comparison Agent: hybrid rule-based + AI analysis, 5 red flag detectors (quorum, RPT entity scan, conflict of interest abstention check, circular resolution unanimity, signature completeness), CRITICAL/HIGH/MEDIUM/LOW severity scoring
- Reporting Agent: three-pillar scorecard (30/35/35 weights), PDF generation (WeasyPrint A4 board-ready with score pills + severity colors), Excel export (openpyxl 3-sheet with auto-filter + color coding), executive summary in Bahasa Indonesia

### Session 7 — 2026-04-09

**Scope:** Phase 2 Week 8 — API Gateway

- **13 files created** (total: ~212), 3 new tests (64 total)
- API Gateway: FastAPI with 6 routers, 13 REST endpoints, CORS for Next.js frontend
- Documents router: upload (multipart → GCS → Pub/Sub), list (status filter, pagination), get
- HITL router: review queue, review detail (loads AI output per gate), submit decision (state transitions + Pub/Sub)
- Reports, Users, Audit, Dashboard routers

### Session 8 — 2026-04-09/10

**Scope:** Phase 3 — Next.js 15 frontend (MVP UI)

- **25 files created** (total: ~237)
- Next.js 15 + React 19 + Tailwind + TypeScript with Ancol brand colors (#1a237e)
- Shared layout: sidebar (7-item nav), header (notification center + user avatar)
- API client: 10 functions matching all API Gateway endpoints
- RBAC auth: route-level permission matrix per role, default route per role
- 8 pages: scorecard dashboard, upload (drag-drop), documents (status table), HITL queue + detail (approve/reject), reports (PDF/Excel download), regulations (corpus explorer), audit trail

### Session 9 — 2026-04-10

**Scope:** Phase 4 — Batch Processing + Analytics + Monitoring

- **23 files created/modified** (total: ~260), 18 new tests (82 total)
- **Batch Engine Service** (`services/batch-engine/`): FastAPI service with async processing engine, configurable concurrency (10-50), exponential backoff retry, resumable checkpoints, Pub/Sub progress events
- **Gemini Rate Limiter** (`ancol_common/gemini/rate_limiter.py`): Async token bucket per model tier (Flash 33 RPS / Pro 16 RPS)
- **Batch Pydantic Schemas** (`ancol_common/schemas/batch.py`): 8 schemas (create, response, detail, item, progress event)
- **Batch Repository** (`repository.py`): batch CRUD, state machine (queued→running→paused/completed/failed), item tracking with auto-complete
- **Batch API Router** (`api_gateway/routers/batch.py`): 5 endpoints (create, list, get detail, pause, resume)
- **Analytics API Router** (`api_gateway/routers/analytics.py`): 4 endpoints (score trends, violation heatmap, coverage stats, HITL performance)
- **Dashboard Trends** (`dashboard.py`): extended with trend endpoint + batch job counters
- **BigQuery Views** (Terraform): 3 materialized views (monthly trends, violation heatmap, coverage by year)
- **Monitoring Alerts** (Terraform): 4 new alert policies (HITL SLA breach, batch failure rate, corpus staleness, Gemini quota)
- **Frontend Batch Page** (`web/src/app/(dashboard)/batch/page.tsx`): Progress cards with bar, pause/resume, auto-refresh, Bahasa labels
- **Scorecard Trends** (`scorecard/page.tsx`): 6-month composite score bar chart
- **Updated**: sidebar (8 nav items), API client (7 new functions), types (batch + analytics), config (3 new settings)

### Session 10 — 2026-04-10

**Scope:** Phase 5 — Integration (all 9 tasks)

- **35 files created/modified** (total: ~295), 38 new tests (120 total across 8 services)
- **Email Ingest Service** (`services/email-ingest/`): Gmail inbox scanner with MoM filename detection (5 regex patterns), meeting date extraction (ISO + Bahasa Indonesia), auto-upload to pipeline. 17 tests (scanner logic) + 1 health test
- **Regulation Monitor Service** (`services/regulation-monitor/`): 5 source definitions (OJK, IDX, Kemenparekraf, KLHK, ATR/BPN), HTML scraper with keyword relevance filter, change detection against corpus, Pub/Sub notifications. 20 tests (sources, relevance, date parsing)
- **Auth Middleware** (`ancol_common/auth/middleware.py`): IAP → DB user resolver, attaches user/role/email to request state, public path bypass
- **Template Versioning Router** (`api_gateway/routers/templates.py`): list, resolve (date-based auto-select), version timeline per MoM type
- **Retroactive Scanning Router** (`api_gateway/routers/retroactive.py`): impact assessment + scan-and-reprocess (creates batch job for affected MoMs)
- **Integration Adapters** (`ancol_common/integrations/`): abstract base + board portal adapter (sync meetings, push reports) + ERP adapter (financial data, RPT cross-check)
- **Industry Regulations** (+3 corpus files): PP 50/2011 (tourism), PP 22/2021 (environment), Permen ATR 16/2021 (land/HGB)
- **DR Infrastructure** (`infra/modules/disaster-recovery/`): Cloud SQL cross-region replica (asia-southeast1), GCS replication (hourly transfer jobs), replica lag monitoring
- **Config**: +6 settings (email ingest, board portal, ERP)

### Session 11 — 2026-04-10/11

**Scope:** Code review, linting, ship, and repo separation

- **Code Review** (`/simplify`): 3 parallel review agents (reuse, quality, efficiency) found 10 issues across the codebase
- **2 Bugs Fixed**:
  - `retroactive.py`: `scan_and_reprocess` mutated detached ORM objects — status reset was silently a no-op. Fixed with bulk `UPDATE` statement
  - `rate_limiter.py`: held async lock during `asyncio.sleep()`, serializing all concurrent batch API calls. Fixed by releasing lock before sleep
- **Efficiency Fixes**: N+1 eliminated in retroactive scan + regulation checker, regulation sources now checked concurrently via `asyncio.gather`, frontend batch page polls only when active jobs exist, GCS client singleton
- **Code Consolidation**: new `ancol_common/utils.py` with shared `parse_indonesian_date`, `detect_document_format`, `parse_gcs_uri`, `get_gcs_client`, `SYSTEM_USER_ID` — removed duplicate code from 5 files
- **Linting**: `ruff format` clean (35 files reformatted), `ruff check --fix` (auto-fixed 20+ issues including StrEnum migration)
- **Frontend Build**: Next.js build clean, all 12 routes compiled
- **All 120 tests passing** after all fixes
- **Repo Separation**: Moved to standalone repo `github.com/erikgunawans/New-Ancol-Platform`. Removed from `new-shadow-ai-detector` repo, deleted stale branch, cleaned `.gitignore`

### Session 15 — 2026-04-13/14

**Scope:** CLM Phase 1 — Contract Lifecycle Management expansion (full Phase 1, Weeks 1-8)

- **Planning**: CLM expansion plan created from PJAA survey findings (201-500 contracts, no centralized tracking). Strategy: extend existing services, don't create new ones. Budget: <$8.5K/year GCP.
- **Data Model** (Week 1-2): 3 new schema files (contract.py, obligation.py, drafting.py), 6 new ORM tables (21 total), 10-state contract state machine, Alembic migration 002, 2 new user roles (contract_manager, business_dev) synced across 4 locations, 8 new RBAC permissions, 6 new config settings, WhatsApp + push notification channels
- **API** (Week 3-4): 3 new API routers (contracts 8 endpoints, obligations 5 endpoints, drafting 5 endpoints = 18 total), registered in api-gateway main.py
- **Frontend** (Week 3-4): 7 new TS types + interfaces, 12 new API client functions, 3 new pages (contracts, obligations, approve), grouped sidebar navigation (MoM/Contracts/Admin), route permissions for new roles
- **Gemini Agent** (Week 5-6): 4 new tool handler files (8 tools: upload_contract, check_contract_status, get_contract_portfolio, get_contract_risk, list_obligations, fulfill_obligation, generate_draft, ask_contract_question), 12 new api_client methods, 6 new Bahasa Indonesia formatters
- **WhatsApp** (Week 5-6): Notification module (Twilio-based) for obligation reminders and approval requests
- **Terraform** (Week 7-8): 3 new Pub/Sub topics, 1 CMEK contracts bucket, 1 Cloud Scheduler job (obligation-check daily 07:00 WIB), IAM bindings, WhatsApp secret
- **Tests** (Week 7-8): 52 new tests (201 total), CI `|| true` removal
- **Reviews**: /simplify x3, /review (Claude adversarial, 30 findings), /codex review (5 findings). Fixed: path traversal, falsy-zero, over-privileged IAM, contract ID mismatch, Pub/Sub routing, scheduler URL
- **PR #1**: Created and merged to main via squash merge (commit fd3b4f8)

**Files created:** 45 new files across schemas, routers, tools, tests, Terraform, frontend pages
**Files modified:** models.py, repository.py, config.py, rbac.py, gemini main.py, api_client.py, formatting.py, sidebar.tsx, types/index.ts, api.ts, auth.ts, pubsub/main.tf, storage/main.tf, scheduler/main.tf, security/main.tf, dev/main.tf, ci.yml, pyproject.toml
**Tests:** 201 passing across 9 services. 0 lint errors. 14 frontend routes compiled. Terraform validates.

---

### Session 16 — 2026-04-14

**Scope:** Phase 1 Gap Closure — RBAC Enforcement + Obligation Auto-Transition

- **RBAC Enforcement**: Wired `require_permission()` from `auth/rbac.py` to all 46 API endpoints across 13 routers. Added `hitl:decide` union permission key (21 total permission keys). Every endpoint now checks `request.state.user_role` against `ROLE_PERMISSIONS` matrix.
- **Obligation Auto-Transition**: New `check_obligation_deadlines()` function in `repository.py` with 4 phases: overdue transition (bulk UPDATE), due_soon transition, reminder flag updates (30/14/7 day windows), recurrence handling (monthly/quarterly/annual). Uses `sqlalchemy.update()` for bulk operations and `dateutil.relativedelta` for date math.
- **New Endpoint**: `POST /api/obligations/check-deadlines` — Cloud Scheduler calls this daily at 07:00 WIB. Inserted before `/{obligation_id}` route to avoid path parameter capture.
- **Scheduler Update**: Re-pointed `obligation_check` Terraform job from `GET /upcoming` to `POST /check-deadlines`.
- **Auth**: Added `/api/obligations/check-deadlines` to `PUBLIC_PATHS` in middleware.py for scheduler OIDC access.
- **WhatsApp deferred**: User model has no phone field — reminder flags are set but delivery is deferred until User model gets a phone column.
- **Tests**: 31 new tests (69 total for api-gateway, 232 total across 9 services). RBAC tests cover permission matrix, dependency wiring, and all 13 router imports. Obligation tests cover overdue/due_soon transitions, reminder flags, recurrence creation, and idempotency.
- **CLAUDE.md**: Added Plan Verification Protocol, updated test counts, added 2 new gotchas (RBAC per-endpoint, obligation bulk UPDATE).

**Files modified:** `auth/rbac.py` (+hitl:decide), `auth/middleware.py` (+PUBLIC_PATHS), `db/repository.py` (+check_obligation_deadlines), `scheduler/main.tf`, 13 router files, `CLAUDE.md`, `PROGRESS.md`
**Files created:** `test_rbac_enforcement.py` (23 tests), `test_obligation_transitions.py` (8 tests)
**Tests:** 232 passing across 9 services. 0 lint errors.

---

### Session 17 — 2026-04-14

**Scope:** CLM Phase 2 — Contract Extraction Pipeline + Smart Drafting Engine

- **Design spec**: `docs/superpowers/specs/2026-04-14-clm-phase2-extraction-drafting-design.md` — scoped to extraction + drafting (Q&A → Phase 3)
- **Contract Extraction**: Extended extraction-agent with `POST /extract-contract` endpoint. New `contract_parser.py` module uses Gemini 2.5 Pro for clause-level extraction with risk scoring (HIGH/MEDIUM/LOW). Stores `ContractClauseRecord` and `ContractPartyRecord` rows, updates `Contract.extraction_data` JSONB, risk_level, risk_score, dates, financial terms.
- **Clause Library**: 58 bilingual (ID/EN) pre-approved clauses across 7 contract types in `corpus/data/clause_library.json`. 7 contract templates with required/optional clause mappings. Idempotent seed script `scripts/seed_clause_library.py`.
- **Smart Drafting**: 3-phase assembly engine in `packages/ancol-common/src/ancol_common/drafting/engine.py`. Phase 1: template + clause library lookup. Phase 2: variable substitution (`{{party_principal}}`, `{{payment_days}}`, etc.). Phase 3: single Gemini Flash call for optional clause recommendations + consistency check. Minimal hallucination — clauses come from pre-approved library.
- **Drafting Endpoint**: Replaced `POST /drafting/generate` stub with real implementation. Parses `DraftRequest`, calls `assemble_draft()`, returns full draft text + clauses + risk assessment.
- **Repository**: 3 new functions: `store_contract_extraction()`, `get_clauses_for_template()`, `get_contract_template()`.
- **Gemini Prompts**: 2 new prompt files — `contract_system.py` (extraction) and `drafting/prompts.py` (enhancement).

**Files created:** 11 new files (parser, prompt, engine, corpus JSON, seed script, tests)
**Files modified:** `repository.py`, `extraction-agent/main.py`, `routers/drafting.py`
**Tests:** 250 passing across 9 services (+10 extraction, +8 drafting). 0 lint errors.

---

### Session 18 — 2026-04-15

**Scope:** CLM Phase 3 — Contract Q&A RAG + Obligation Auto-Extraction

- **Design spec**: `docs/superpowers/specs/2026-04-14-clm-phase3-qa-rag-obligation-extraction-design.md`
- **Contract Q&A RAG**: 3-layer hybrid retrieval — Vertex AI Search semantic clause search, Spanner Graph contract-regulation + contract-contract edge expansion, Cloud SQL exact lookups. Re-ranked results synthesized by Gemini 2.5 Pro. Bahasa Indonesia responses with clause number citations.
- **Obligation Auto-Extraction**: Enhanced extraction prompt to identify obligations (renewal, payment, reporting, termination notice, deliverable, compliance filing) inline with clause parsing. Auto-creates `ObligationRecord` rows in same transaction.
- **Regulation Mapping**: Gemini identifies applicable regulations during extraction (UUPT, POJK, etc.). Stored as Spanner Graph edges (GOVERNED_BY).
- **Vertex AI Search**: New contracts datastore in Terraform (`ancol-contract-clauses`). Indexer pipeline indexes each extracted clause with structured metadata.
- **Spanner Graph**: Contract nodes, ContractRegulation edges, ContractAmendment edges. GraphClient extended with `get_related_regulations_for_contract()` and `get_related_contracts()` (Spanner + Neo4j stub).
- **Config**: New `vertex_search_contracts_datastore` setting. Added `google-cloud-discoveryengine` to gemini-agent deps.
- **Tests**: Updated existing tests (MockGraphClient, contract tools) for new abstract methods and replaced Q&A stubs. 14 new tests total.

**Files created:** 6 new files (contract_rag.py, contract_indexer.py, graph_seeder.py, search/__init__.py, test_obligation_extraction.py, test_contract_qa.py)
**Files modified:** 16 files (schemas, config, prompts, parser, repository, main.py, graph_client, spanner/neo4j, tools, formatting, Terraform, pyproject.toml, existing tests)
**Tests:** 264 passing across 9 services (+14 new). 0 lint errors.

---

### Session 14 — 2026-04-12

**Scope:** Gemini Enterprise Agent Builder Integration — Hybrid RAG, webhook service, Spanner Graph

- **Design spec**: `docs/superpowers/specs/2026-04-12-gemini-agent-builder-integration-design.md` — full architecture for Vertex AI Agent Builder + Cloud Run webhook + hybrid RAG
- **New service**: `services/gemini-agent/` — FastAPI webhook with 8 tool handlers (upload_document, review_gate, get_review_detail, submit_decision, check_status, get_report, search_regulations, get_dashboard)
- **Hybrid RAG**: 3-layer retrieval (Vertex AI Search vectors + Spanner Graph relationships + Cloud SQL exact lookups), authority-ranked re-ranking (UUPT > POJK > SE-OJK > IDX > Internal)
- **Graph RAG**: Abstract `GraphClient` interface with Spanner Graph (primary) and Neo4j AuraDS (fallback, behind `GRAPH_BACKEND` flag)
- **RAG orchestrator**: Combines vector search → graph expansion (amendments, supersessions, cross-references) → SQL context → re-rank → deduplicate
- **Response formatting**: All outputs in Bahasa Indonesia with English legal terms, markdown-formatted for chat
- **Infrastructure**: New Spanner Graph Terraform module (`infra/modules/spanner-graph/`), gemini-agent SA + IAM bindings, Cloud Run module call
- **Graph seeding**: `corpus/scripts/seed_regulation_graph.py` — reads regulation chunks, extracts relationships, seeds Spanner Graph nodes/edges
- **HITL model**: Hybrid — synchronous Gate 1 (extraction review on upload), async Gates 2-4 (different roles, chat-based polling)

**Files created:** `services/gemini-agent/` (14 source files, 6 test files, Dockerfile, pyproject.toml), `infra/modules/spanner-graph/` (3 files), `corpus/scripts/seed_regulation_graph.py`, `docs/superpowers/specs/2026-04-12-gemini-agent-builder-integration-design.md`
**Files modified:** `infra/modules/security/main.tf` (gemini-agent SA + IAM), `infra/environments/dev/main.tf` (Spanner + Cloud Run modules)
**Tests:** 149 passing (126 existing + 23 new gemini-agent) across 9 services. Terraform validates. Ruff clean.

---

### Session 13 — 2026-04-12

**Scope:** GCP Deployment & Operations — Terraform fixes, Cloud Run wiring, CI/CD, scanner.py bug fix, Cloud Scheduler, DR, bulk upload scripts

- **TG1.1**: Fixed Pub/Sub `for_each` crash — added `contains(keys(var.push_endpoints), v.push_target)` guard to `infra/modules/pubsub/main.tf:86-88`
- **TG1.2**: Added 3 missing service accounts (batch-engine, email-ingest, regulation-monitor) + 5 IAM bindings in `infra/modules/security/main.tf`
- **TG1.3**: Added all 10 Cloud Run module calls to `infra/environments/dev/main.tf`, wired Pub/Sub push endpoints, uncommented workflows module, created `infra/environments/dev/outputs.tf`
- **TG2.2**: Fixed CI/CD `deploy-agents.yml` — added 3 missing services to fallback, added `web/**` path + `deploy-web` job, fixed service naming to `ancol-$SERVICE_NAME`
- **TG3**: Created `infra/modules/scheduler/` — 2 Cloud Scheduler jobs (email-scan every 15min, regulation-check daily 06:00 WIB)
- **TG4.1**: Fixed `scanner.py` undefined `ext` bug — added `_get_content_type()` helper, replaced 2 broken `f"application/{ext}"` references (lines 212, 246), added 6 regression tests (24 total for email-ingest)
- **TG6**: Created `scripts/validate_historical.py` (CSV manifest pre-flight validation) and `scripts/bulk_upload_historical.py` (GCS bulk upload + JSON records output)
- **TG8**: Wired DR module in dev/main.tf, updated `schedule_start_date` from 2026-04-10 to 2026-05-01

**Files created:** `infra/environments/dev/outputs.tf`, `infra/modules/scheduler/{main,variables,outputs}.tf`, `scripts/validate_historical.py`, `scripts/bulk_upload_historical.py`
**Files modified:** `infra/modules/pubsub/main.tf`, `infra/modules/security/main.tf`, `infra/environments/dev/main.tf`, `infra/modules/disaster-recovery/main.tf`, `.github/workflows/deploy-agents.yml`, `services/email-ingest/src/email_ingest/scanner.py`, `services/email-ingest/tests/test_scanner.py`
**Tests:** 126 passing (120 + 6 new) across 8 services. Terraform validates. Frontend builds. Ruff clean on changed files.

---

### Session 12 — 2026-04-11

**Scope:** Documentation polish — PROGRESS.md + CLAUDE.md audit and improvement

- **PROGRESS.md overhaul**: updated current state date, added standalone repo URL, fixed session ordering (9→10→11), added session 11 entry, added 3 industry regulations to corpus table, updated infrastructure to 14 modules (disaster-recovery), updated frontend to 9 pages/17 API functions/8 nav items, added email-ingest + regulation-monitor to test commands and file structure, added utils.py and integrations/ to file structure and critical files
- **CLAUDE.md audit** (`/claude-md-improver`): scored 72/100 (B), identified 7 issues
  - Removed dead plan file reference (`.claude/plans/golden-marinating-sunbeam.md` no longer exists)
  - Fixed config count: 21 → 31 settings
  - Added 4 missing shared code entries (utils.py, integrations/, auth/middleware.py, rate_limiter.py)
  - Added document-processor to test list (7 tests, CI-only due to `google-cloud-documentai` dependency)
  - Added "run all tests" convenience loop + `npm run build` command
  - Added Gotchas section with 9 non-obvious patterns
  - Score improved to 93/100 (A)
- **CLAUDE.md final polish** (93 → 100):
  - Added Setup section (prerequisites, `pip install -e`, `npm install`)
  - Added 2 operational gotchas (`npm install` required before build, `terraform init` before validate)
  - Noted scorecard trend charts + batch auto-refresh in frontend description
- **Shadow-AI-Detector cleanup verified**: 0 of 1,399 tracked files reference Ancol, stale branch pruned, `.gitignore` ancol entries removed

---

## Critical Files (read these first when resuming)

| File | Why Critical |
|------|-------------|
| `CLAUDE.md` | Project conventions for Claude — read first |
| `PROGRESS.md` | This file — current state + resume guide |
| `packages/ancol-common/src/ancol_common/schemas/mom.py` | Shared MoM schema — contract between all 4 agents |
| `packages/ancol-common/src/ancol_common/utils.py` | Shared utilities — date parsing, format detection, GCS helpers, constants |
| `packages/ancol-common/src/ancol_common/schemas/contract.py` | Contract schemas — CLM data contract |
| `packages/ancol-common/src/ancol_common/db/models.py` | 21 ORM tables — MoM + CLM data model |
| `packages/ancol-common/src/ancol_common/db/repository.py` | Document + contract state machines |
| `packages/ancol-common/src/ancol_common/config.py` | 40 environment settings |
| `services/legal-research-agent/src/legal_research_agent/retrieval/citation_validator.py` | Anti-hallucination Layer 3 — most critical safety code |
| `services/comparison-agent/src/comparison_agent/analyzers/red_flags.py` | 5 red flag detectors — core compliance value |
| `services/reporting-agent/src/reporting_agent/generators/scorecard.py` | Three-pillar scoring (30/35/35) |
| `services/api-gateway/src/api_gateway/routers/hitl.py` | HITL decision flow — gate transitions |
| `infra/modules/workflows/workflow.yaml` | Cloud Workflows orchestrator — pipeline backbone |
| `db/alembic/versions/001_initial_schema.py` | Full DB schema |
| `web/src/lib/api.ts` | Frontend API client — all endpoint bindings |
| `services/batch-engine/src/batch_engine/engine.py` | Batch processing orchestrator — concurrency, retry, progress |
| `packages/ancol-common/src/ancol_common/gemini/rate_limiter.py` | Token bucket rate limiter for Gemini API |
| `services/api-gateway/src/api_gateway/routers/analytics.py` | Analytics endpoints — trends, violations, coverage, HITL |
