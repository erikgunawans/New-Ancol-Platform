# CLAUDE.md — Ancol MoM Compliance System

## Workflow

- **ALWAYS read `PROGRESS.md` at the start of every session** — it has the current state, what's done, what's next, and critical files to read first
- **ALWAYS update `PROGRESS.md` after completing any task** — add a session entry with scope, files created/modified, tests passing, and next steps so the next session can resume seamlessly
- Check the implementation plan at `.claude/plans/golden-marinating-sunbeam.md` for the full step-by-step breakdown

## Commands

```bash
# Lint (Python)
ruff check packages/ services/
ruff format --check packages/ services/

# Test per service (must run individually due to namespace isolation)
PYTHONPATH=packages/ancol-common/src:services/extraction-agent/src pytest services/extraction-agent/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/legal-research-agent/src pytest services/legal-research-agent/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/comparison-agent/src pytest services/comparison-agent/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/reporting-agent/src pytest services/reporting-agent/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/api-gateway/src pytest services/api-gateway/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/batch-engine/src pytest services/batch-engine/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/email-ingest/src pytest services/email-ingest/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/regulation-monitor/src pytest services/regulation-monitor/tests/ -v

# Verify ORM models load (quick smoke test)
PYTHONPATH=packages/ancol-common/src python3 -c "from ancol_common.db.models import Base; print(f'{len(Base.metadata.tables)} tables')"

# Chunk regulations
python3 corpus/scripts/chunk_regulations.py --all

# Frontend
cd web && npm install && npm run dev

# Terraform
cd infra/environments/dev && terraform validate
```

## Project

Agentic AI system on Gemini Enterprise for auditing Board of Directors Minutes of Meetings (MoM) at PT Pembangunan Jaya Ancol Tbk (IDX: PJAA). Multi-Agent + HITL architecture.

## Key Files

- **Design Spec:** `docs/superpowers/specs/2026-04-08-agentic-mom-compliance-design.md`
- **Implementation Plan:** `.claude/plans/golden-marinating-sunbeam.md`
- **Progress Tracker:** `PROGRESS.md` — session-by-session log with what's done and what's next

## Tech Stack

- **Agents + API:** Python 3.12, FastAPI, Pydantic v2, google-genai SDK
- **Frontend:** Next.js 15, React 19, Tailwind CSS, shadcn/ui
- **Database:** PostgreSQL 15 (Cloud SQL), SQLAlchemy 2.0, Alembic
- **IaC:** Terraform (14 modules in `infra/modules/`)
- **CI/CD:** GitHub Actions
- **Region:** asia-southeast2 (Jakarta) — data sovereignty requirement

## Architecture

9 Python services on Cloud Run + 1 Next.js frontend:

**Document Processing:**
1. **Document Processor** (Document AI) — `services/document-processor/`

**4 Gemini Agents (each a FastAPI service receiving Pub/Sub push messages):**
2. **Extraction Agent** (Gemini 2.5 Flash) — `services/extraction-agent/`
3. **Legal Research Agent** (Gemini 2.5 Pro + Vertex AI Search RAG) — `services/legal-research-agent/`
4. **Comparison Agent** (Gemini 2.5 Pro) — `services/comparison-agent/`
5. **Reporting Agent** (Gemini 2.5 Flash) — `services/reporting-agent/`

**Batch Processing:**
6. **Batch Engine** (async orchestrator, rate limiter) — `services/batch-engine/`

**Integration Services:**
7. **Email Ingest** (Gmail API scanner, Cloud Scheduler) — `services/email-ingest/`
8. **Regulation Monitor** (OJK/IDX/industry scraper) — `services/regulation-monitor/`

**API + Frontend:**
9. **API Gateway** (FastAPI, 28 REST endpoints) — `services/api-gateway/`
10. **Frontend** (Next.js 15, React 19, Tailwind) — `web/`

Orchestrated by Cloud Workflows (`infra/modules/workflows/workflow.yaml`) with HITL gates between each stage.

## Shared Code

All agents share `packages/ancol-common/` which contains:
- `schemas/` — Pydantic models (the contract between agents). **mom.py is the critical schema file.**
- `db/models.py` — 15 SQLAlchemy ORM models
- `db/repository.py` — Document state machine (14 states)
- `gemini/` — Client factory + Vertex AI Search grounding tool
- `config.py` — 21 environment-based settings

## Conventions

- Python: ruff for linting/formatting, pytest for testing
- Terraform: one module per GCP service, composed in `infra/environments/{env}/main.tf`
- Each agent has: `main.py` (FastAPI app), `agent.py` (core logic), `prompts/` (system + few-shot)
- Pub/Sub topics prefixed `ancol-` (e.g., `ancol-mom-uploaded`)
- Service accounts prefixed `ancol-` (e.g., `ancol-extraction-agent`)

## Testing

120 unit tests across 8 services. Each service tested individually:
- extraction-agent: 9 tests (structural parser, endpoints)
- legal-research-agent: 9 tests (citation validator, endpoints)
- comparison-agent: 27 tests (5 red flag detectors, severity scoring)
- reporting-agent: 16 tests (scorecard calc, PDF rendering)
- api-gateway: 3 tests (health, API root, CORS)
- batch-engine: 18 tests (rate limiter, status transitions, schemas, health)
- email-ingest: 18 tests (filename detection, MoM type, date extraction, health)
- regulation-monitor: 20 tests (sources, relevance filter, date parsing, endpoints)

## Current State

**ALL 5 PHASES COMPLETE.** ~295 files, 120 tests across 8 services. System is feature-complete. Check `PROGRESS.md` for full details.
