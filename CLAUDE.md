# CLAUDE.md — Ancol MoM Compliance System

## Workflow

- **ALWAYS read `PROGRESS.md` at the start of every session** — it has the current state, what's done, what's next, and critical files to read first
- **ALWAYS update `PROGRESS.md` after completing any task** — add a session entry with scope, files created/modified, tests passing, and next steps so the next session can resume seamlessly
- When working in git worktrees, immediately confirm the working directory and branch before starting any work. Do not spend session time on setup/exploration unless explicitly asked.
- When hitting API context limits or usage limits, immediately checkpoint progress and summarize remaining work in PROGRESS.md rather than retrying failed commands.
- For major dependency upgrades or SDK migrations, read the changelog/migration guide FIRST before attempting code changes. Do not assume old API signatures still work.
- When debugging frontend issues, always verify the backend is running and returning expected response shapes before investigating frontend code.

## Deployment

Before deploying to Vercel or GCP, always verify:
1. Correct project/target (Vercel project name or GCP project ID)
2. All env vars are set (cross-check against the Environment Variables table below)
3. Correct branch (`main` for this repo)
4. Run full CI locally: `ruff check packages/ services/ && /run-tests`

## Setup

```bash
# Prerequisites: Python 3.12, Node 22, ruff, Terraform
pip install -e packages/ancol-common        # install shared package locally
pip install neo4j>=5.15                     # optional: Neo4j graph backend
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
9. **API Gateway** (FastAPI, ~88 REST endpoints incl. BJR `decisions` + `rkab` + `rjpp` + `artifacts` routers) — `services/api-gateway/`
10. **Frontend** (Next.js 15, React 19, Tailwind) — `web/` — analytics companion (trends, heatmaps, batch progress)

**Gemini Enterprise Interface (primary):**
11. **Gemini Agent** (Agent Builder webhook, hybrid RAG) — `services/gemini-agent/` — 8 tool handlers, Spanner Graph + Vertex AI Search + SQL retrieval

Orchestrated by Cloud Workflows (`infra/modules/workflows/workflow.yaml`) with HITL gates between each stage. Primary user interface is Gemini Enterprise chat via Vertex AI Agent Builder.

## Shared Code

All agents share `packages/ancol-common/` which contains:
- `schemas/` — Pydantic v2 schemas (the contract between agents). **mom.py is the critical schema file.** Also `schemas/{decision,bjr,artifact}.py` for BJR (StrategicDecision, 16 item codes via `BJRItemCode`, 6 artifact types)
- `db/models.py` — 33 SQLAlchemy ORM models (21 core + 12 BJR tables)
- `db/repository.py` — Document state machine (14 states) + batch job CRUD + `DECISION_TRANSITIONS` (14 states) + `transition_decision_status()` for BJR
- `bjr/` — BJR scoring engine: `scorer.py` (pure dual-regime math), `evaluators.py` (16 checklist evaluators), `compute.py` (orchestrator + checklist upsert), `retroactive.py` (MoM → Decision proposer), `matching.py` (shared token-overlap ranker)
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

Always run the full CI pipeline locally before pushing: `ruff check packages/ services/ scripts/ corpus/scripts/` + `/run-tests`. Check all pip/npm deps are installed and no tests are skipped by assumption.

543 unit tests across 9 services (run locally). Use `/run-tests` skill or test individually:
- extraction-agent: 25 tests (structural parser, contract extraction, obligation extraction, risk scoring)
- legal-research-agent: 9 tests (citation validator, endpoints)
- comparison-agent: 27 tests (5 red flag detectors, severity scoring)
- reporting-agent: 16 tests (scorecard calc, PDF rendering)
- api-gateway: 343 tests (health, CORS, RBAC, per-gate HITL, MFA, WhatsApp, obligation transitions, drafting, schemas, contract PDF, BJR: rbac/schemas/state-machine/routers/scorer/decisions/retroactive/evaluators/compute)
- batch-engine: 18 tests (rate limiter, status transitions, schemas, health)
- email-ingest: 24 tests (filename detection, MoM type, date extraction, content type, health)
- regulation-monitor: 20 tests (sources, relevance filter, date parsing, endpoints)
- gemini-agent: 61 tests (webhook routing, upload flow, HITL tools, RAG orchestrator, graph client, Neo4j contract queries, contract Q&A RAG, formatting)
- document-processor: 7 tests (requires `google-cloud-documentai` — runs in CI only)

## Current State

**v0.4.0.0 — BJR orchestration layer shipped.** ~460 files, 543 tests locally across 9 services (25+9+27+16+343+18+24+20+61), 33 ORM tables, 88 API routes. MoM + CLM + MFA + WhatsApp + Neo4j + BJR (Business Judgment Rule) decision-level defensibility with dual-regime scoring + Gate 5 dual-approval. RBAC on all endpoints with per-gate HITL. Security reviewed + full /pre-ship pipeline + 6-agent pr-review-toolkit. Check `PROGRESS.md` for session history, `PRODUCT-STATUS.md` for product evolution.

## Automations

Hooks, skills, and agents are configured in `.claude/`:

- **Hooks** (`.claude/settings.json`): Auto-format with ruff on every edit. Blocks `.env` file edits.
- **Skills**: `/run-tests` (full 9-service test suite), `/new-endpoint` (scaffold with RBAC + MFA)
- **Agents**: `security-reviewer` (auth, crypto, data sovereignty audit)
- **MCP Servers**: `context7` (live library docs), `github` (issues, PRs, CI)
- **Knowledge Graph**: `graphify-out/graph.json` (2,924 nodes, 8,096 edges, 139 communities). Run `/graphify query "<question>"` to traverse. Run `/graphify --update` after code changes. See `docs/Graph-Question-List.md` for 55 curated high-impact questions across ARCH / SEC / PERF / ONBOARD / RISK / PRODUCT / EVOLUTION / BJR.

## Environment Variables (new features)

MFA, WhatsApp, and Neo4j require these env vars (all optional, features degrade gracefully without them):

| Variable | Purpose | Default |
|----------|---------|---------|
| `MFA_ENABLED` | Enable app-level MFA | `false` |
| `MFA_ENCRYPTION_KEY` | Fernet key for TOTP secrets | (required if MFA enabled) |
| `MFA_JWT_SECRET` | HMAC key for MFA session tokens | (required if MFA enabled) |
| `MFA_REQUIRED_ROLES` | Comma-separated roles requiring MFA | `admin,corp_secretary,internal_auditor,legal_compliance` |
| `WHATSAPP_API_TOKEN` | Twilio WhatsApp API token | (empty = WhatsApp disabled) |
| `WHATSAPP_API_URL` | Twilio API endpoint | (empty = WhatsApp disabled) |
| `GRAPH_BACKEND` | Graph backend: `spanner`, `neo4j`, `none` | `spanner` |
| `NEO4J_URI` | Neo4j connection URI | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | (empty) |
| `BJR_ENABLED` | Master kill switch for BJR orchestration layer | `true` |
| `BJR_GATE5_THRESHOLD` | Minimum readiness score to unlock Gate 5 | `85.0` |
| `BJR_GATE5_SLA_DAYS` | Days before Gate 5 SLA breach | `5` |
| `BJR_MATERIALITY_THRESHOLD_IDR` | Decision value (IDR) triggering OJK disclosure | `10000000000.0` |

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
- **MFA is off by default**: `MFA_ENABLED=false` in config. Enable with env var. MFA enforcement is per-router dependency (not middleware), so MFA endpoints (`/me/mfa/*`) are accessible without MFA (avoids chicken-and-egg). Requires `MFA_ENCRYPTION_KEY` (Fernet) and `MFA_JWT_SECRET` env vars.
- **MFA token is bound to IAP identity**: `require_mfa_verified()` compares JWT `sub` claim against current IAP email to prevent cookie theft reuse across users
- **Backup codes use constant-time comparison**: `verify_backup_code()` in `mfa.py` uses `hmac.compare_digest()` to prevent timing side-channels
- **WhatsApp is opt-in**: Default `notification_channels` is `["email", "in_app"]`. Users must explicitly enable WhatsApp via `/me/profile` endpoint with a valid E.164 phone number
- **VALID_CHANNELS constant lives in dispatcher**: `notifications/dispatcher.py` owns `VALID_CHANNELS` and `DEFAULT_CHANNELS`. Import from there, don't redefine.
- **UserResponse.from_user() class method**: Use `UserResponse.from_user(u)` instead of manually constructing UserResponse fields. Defined in `routers/users.py`.
- **Neo4j is fully implemented**: All 7 `GraphClient` methods have Cypher implementations. Switch with `GRAPH_BACKEND=neo4j` + `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` env vars. Driver needs explicit `close()` call.

### BJR-specific gotchas (load-bearing — don't break these)

- **BJR dual-regime scoring is `min(corporate, regional)`**: The #1 strategic risk from the matrix — a decision passing corporate (UU PT + OJK) but failing BUMD (PP + Pergub DKI) gets NO protection. Formula in `bjr/scorer.py` `compute_scores`. Never change to `max()` or an average.
- **`BJRItemCode` 16 values are a stable contract**: Used by agent output JSON, UI checklist, Decision Passport PDF, audit_trail. Renaming any value breaks all four. Enum in `schemas/bjr.py`.
- **CRITICAL items weight 2×**: `PD-03-RKAB`, `PD-05-COI`, `D-06-QUORUM`, `D-11-DISCLOSE`. Missing any disproportionately tanks the score. Gate 5 unlock also requires no CRITICAL in `flagged` state.
- **Gate 5 needs BOTH unique index AND `SELECT FOR UPDATE`**: Race fix = unique index on `bjr_gate5_decisions.decision_id` + `_ensure_gate5_row` uses `.with_for_update()` + `IntegrityError` fallback. Removing either brings back the duplicate-row race under concurrent half-approvals.
- **Gate 5 finalization: transition FIRST, then set approved**: `_maybe_finalize_gate5` in `routers/decisions.py` calls `transition_decision_status(BJR_LOCKED)` BEFORE setting `gate5.final_decision=approved`. Reversing the order reintroduces split-brain (Gate 5 approved but decision never locked).
- **`_extract_bool_field` distinguishes missing from False**: For D-06-QUORUM and D-07-SIGNED. Missing `quorum_met`/`signatures_complete` → NOT_STARTED with "re-extract" remediation (data gap). Explicit `False` → FLAGGED (real violation). Never collapse these states.
- **`compute_bjr` wraps each evaluator in try/except**: One failing evaluator produces a synthetic FLAGGED via `_EVALUATOR_METADATA` lookup; other 15 still run. Adding a 17th evaluator requires adding it to `_EVALUATOR_METADATA` in `bjr/compute.py` — drift-guard test in `test_bjr_compute.py::test_every_evaluator_has_metadata` enforces 1:1 mapping.
- **PD-05-COI requires 4-char minimum RPT names**: Short entity names like "PT"/"CV" would false-positive every attendee. Malformed `attendees` JSONB (non-list/dict shape) returns FLAGGED with "malformed" remediation — NEVER SATISFIED (that was a pre-merge silent-failure bug).
- **BJR engine is in-process, not a separate service**: Lives in `packages/ancol-common/bjr/`. Plan Phase 6.6 extracts as `services/bjr-agent/` Cloud Run service. Current caller: only `services/api-gateway/src/api_gateway/routers/decisions.py`.

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
