# CLAUDE.md — Ancol MoM Compliance System

## Workflow

- **ALWAYS read `PROGRESS.md` at the start of every session** — it has the current state, what's done, what's next, and critical files to read first
- **ALWAYS update `PROGRESS.md` after completing any task** — add a session entry with scope, files created/modified, tests passing, and next steps so the next session can resume seamlessly

## Setup

```bash
# Prerequisites: Python 3.12, Node 22, ruff, Terraform
pip install -e packages/ancol-common        # install shared package locally
cd web && npm install && cd ..              # install frontend deps
```

## Commands

```bash
# Lint (Python)
ruff check packages/ services/ scripts/ corpus/scripts/
ruff format --check packages/ services/ scripts/ corpus/scripts/

# Test per service (must run individually due to namespace isolation)
PYTHONPATH=packages/ancol-common/src:services/extraction-agent/src python3 -m pytest services/extraction-agent/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/legal-research-agent/src python3 -m pytest services/legal-research-agent/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/comparison-agent/src python3 -m pytest services/comparison-agent/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/reporting-agent/src python3 -m pytest services/reporting-agent/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/api-gateway/src python3 -m pytest services/api-gateway/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/batch-engine/src python3 -m pytest services/batch-engine/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/email-ingest/src python3 -m pytest services/email-ingest/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/regulation-monitor/src python3 -m pytest services/regulation-monitor/tests/ -v
PYTHONPATH=packages/ancol-common/src:services/gemini-agent/src python3 -m pytest services/gemini-agent/tests/ -v
# document-processor: requires google-cloud-documentai (CI only)
# PYTHONPATH=packages/ancol-common/src:services/document-processor/src python3 -m pytest services/document-processor/tests/ -v

# Run all local tests (convenience)
for svc in extraction-agent legal-research-agent comparison-agent reporting-agent api-gateway batch-engine email-ingest regulation-monitor gemini-agent; do
  PYTHONPATH=packages/ancol-common/src:services/$svc/src python3 -m pytest services/$svc/tests/ -q
done

# Verify ORM models load (quick smoke test)
PYTHONPATH=packages/ancol-common/src python3 -c "from ancol_common.db.models import Base; print(f'{len(Base.metadata.tables)} tables')"

# Chunk regulations
python3 corpus/scripts/chunk_regulations.py --all

# Frontend
cd web && npm install && npm run dev
cd web && npm run build  # verify production build

# Terraform
cd infra/environments/dev && terraform validate
```

## Project

Agentic AI system on Gemini Enterprise for auditing Board of Directors Minutes of Meetings (MoM) at PT Pembangunan Jaya Ancol Tbk (IDX: PJAA). Multi-Agent + HITL architecture.

## Key Files

- **Design Spec (original):** `docs/superpowers/specs/2026-04-08-agentic-mom-compliance-design.md`
- **Design Spec (Gemini Agent):** `docs/superpowers/specs/2026-04-12-gemini-agent-builder-integration-design.md`
- **Product Status:** `PRODUCT-STATUS.md` — evolution from PRD to current state (living document)
- **Progress Tracker:** `PROGRESS.md` — session-by-session log with what's done and what's next
- **Repository:** https://github.com/erikgunawans/New-Ancol-Platform

## Tech Stack

- **Agents + API:** Python 3.12, FastAPI, Pydantic v2, google-genai SDK
- **Frontend:** Next.js 15, React 19, Tailwind CSS, shadcn/ui
- **Database:** PostgreSQL 15 (Cloud SQL), SQLAlchemy 2.0, Alembic
- **IaC:** Terraform (16 modules in `infra/modules/`)
- **CI/CD:** GitHub Actions
- **Region:** asia-southeast2 (Jakarta) — data sovereignty requirement

## Architecture

10 Python services on Cloud Run + 1 Next.js frontend:

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
10. **Frontend** (Next.js 15, React 19, Tailwind) — `web/` — analytics companion (trends, heatmaps, batch progress)

**Gemini Enterprise Interface (primary):**
11. **Gemini Agent** (Agent Builder webhook, hybrid RAG) — `services/gemini-agent/` — 8 tool handlers, Spanner Graph + Vertex AI Search + SQL retrieval

Orchestrated by Cloud Workflows (`infra/modules/workflows/workflow.yaml`) with HITL gates between each stage. Primary user interface is Gemini Enterprise chat via Vertex AI Agent Builder.

## Shared Code

All agents share `packages/ancol-common/` which contains:
- `schemas/` — 9 Pydantic v2 schemas (the contract between agents). **mom.py is the critical schema file.**
- `db/models.py` — 15 SQLAlchemy ORM models
- `db/repository.py` — Document state machine (14 states) + batch job CRUD
- `gemini/` — Client factory, Vertex AI Search grounding tool, token bucket rate limiter
- `auth/` — IAP JWT verification, RBAC permission matrix, SSO auth middleware
- `integrations/` — Board portal + ERP adapters (abstract base)
- `utils.py` — Shared helpers: `parse_indonesian_date`, `detect_document_format`, `parse_gcs_uri`, `SYSTEM_USER_ID`
- `config.py` — 34 environment-based settings

## Conventions

- Python: ruff for linting/formatting, pytest for testing
- Terraform: one module per GCP service, composed in `infra/environments/{env}/main.tf`
- Each agent has: `main.py` (FastAPI app), `agent.py` (core logic), `prompts/` (system + few-shot)
- Pub/Sub topics prefixed `ancol-` (e.g., `ancol-mom-uploaded`)
- Service accounts prefixed `ancol-` (e.g., `ancol-extraction-agent`)

## Testing

250 unit tests across 9 services (run locally). Each service tested individually:
- extraction-agent: 19 tests (structural parser, contract clause extraction, risk scoring, endpoints)
- legal-research-agent: 9 tests (citation validator, endpoints)
- comparison-agent: 27 tests (5 red flag detectors, severity scoring)
- reporting-agent: 16 tests (scorecard calc, PDF rendering)
- api-gateway: 77 tests (health, CORS, RBAC enforcement, obligation transitions, drafting engine, contract state machine, schemas)
- batch-engine: 18 tests (rate limiter, status transitions, schemas, health)
- email-ingest: 24 tests (filename detection, MoM type, date extraction, content type, health)
- regulation-monitor: 20 tests (sources, relevance filter, date parsing, endpoints)
- gemini-agent: 40 tests (webhook routing, upload flow, HITL tools, RAG orchestrator, graph client, formatting, contract tools)
- document-processor: 7 tests (requires `google-cloud-documentai` — runs in CI only)

## Current State

**ALL 5 PHASES + GEMINI AGENT + CLM PHASE 1-2 COMPLETE.** ~390 files, 250 tests locally (257 total incl. CI-only). RBAC enforced on all 46 API endpoints. Contract extraction pipeline + smart drafting engine. Check `PROGRESS.md` for full session history, `PRODUCT-STATUS.md` for product evolution.

## Gotchas

- **PYTHONPATH required for tests**: Each service has its own namespace. You must set `PYTHONPATH=packages/ancol-common/src:services/<svc>/src` before running pytest, or imports fail
- **Enums use StrEnum** (Python 3.12+): `mom.py` and `batch.py` use `StrEnum`, not `str, Enum`
- **Rate limiter releases lock before sleep**: The token bucket in `rate_limiter.py` deliberately releases the async lock before `asyncio.sleep()` to avoid serializing concurrent callers
- **Retroactive scan uses bulk UPDATE**: `retroactive.py` must use `sqlalchemy.update()` for document status reset, not ORM attribute mutation (documents may be detached from session)
- **GCS client is a singleton**: Use `get_gcs_client()` from `utils.py`, not `storage.Client()` directly
- **Format detection**: Use `detect_document_format()` from `utils.py`, not inline `format_map` dicts
- **System user UUID**: Use `SYSTEM_USER_ID` from `utils.py` (`a0000000-...`), not hardcoded strings
- **Frontend needs `npm install` first**: `web/node_modules/` is gitignored. Run `cd web && npm install` before `npm run dev` or `npm run build`
- **Terraform needs `init` before `validate`**: `terraform validate` fails without `terraform init` first (downloads provider plugins). Init requires a GCP backend config or `-backend=false` for local-only validation
- **Graph backend is swappable**: `GRAPH_BACKEND` env var controls Spanner Graph (default) vs Neo4j AuraDS. The `GraphClient` abstract interface in `rag/graph_client.py` makes the swap transparent
- **Gemini Agent uses API Gateway as proxy**: The webhook service never accesses Cloud SQL or GCS directly — all calls go through the existing API Gateway via `api_client.py`
- **HITL is hybrid in Gemini chat**: Gate 1 is synchronous (agent polls until extraction completes, ~5 min max). Gates 2-4 are async (different roles, user initiates review via "Apa yang perlu direview?")
- **Ruff must include `scripts/` directory**: Bulk upload and seed scripts live in `scripts/` and `corpus/scripts/` — include these paths when running `ruff check`
- **RBAC is per-endpoint**: Every API endpoint uses `require_permission("key")` from `auth/rbac.py`. When adding new endpoints, always add the `_auth=require_permission("...")` parameter
- **Obligation transitions are bulk UPDATE**: `check_obligation_deadlines()` in `repository.py` uses `sqlalchemy.update()` for status transitions, same pattern as `retroactive.py`

## Plan Verification Protocol

Every implementation plan MUST go through a verification loop before presenting to the user.

### Step 1: Create the initial plan
Write the plan as normal.

### Step 2: Self-verify
Before presenting, review the plan against these criteria:

| Check | Question |
|-------|----------|
| Completeness | Does every requirement from the user have a corresponding action item? |
| Correctness | Do the file paths, function names, and schemas match the actual codebase? |
| Ordering | Are dependencies respected — does step N depend on something from step N+1? |
| Side effects | Could any step break existing functionality? Have I checked the blast radius? |
| Verification | Is there a concrete way to verify each step worked (test command, curl, visual check)? |
| Existing code | Am I reusing existing utilities, or reinventing something that already exists? |

Rate confidence: 0-100%.

### Step 3: Loop if needed
If confidence < 95%:
1. List what's uncertain or weak
2. Investigate (read files, grep patterns, check schemas)
3. Update the plan with findings
4. Re-rate confidence
5. Repeat until confidence >= 95%

### Step 4: Report
Include at the bottom of every plan:
```
Confidence: XX%
Verification passes: N
[If any items were fixed: list what changed between passes]
```
