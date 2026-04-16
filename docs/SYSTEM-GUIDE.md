# Ancol MoM Compliance System — Technical Guide

> How the system works, end-to-end. From document upload to compliance report.
>
> Version: v0.2.0.0 | Last updated: 2026-04-16

---

## Table of Contents

1. [What This System Does](#1-what-this-system-does)
2. [System Overview](#2-system-overview)
3. [Document Ingestion](#3-document-ingestion)
4. [The Agent Pipeline](#4-the-agent-pipeline)
5. [Human-in-the-Loop Gates](#5-human-in-the-loop-gates)
6. [Orchestration](#6-orchestration)
7. [Contract Lifecycle Management](#7-contract-lifecycle-management)
8. [The Gemini Enterprise Interface](#8-the-gemini-enterprise-interface)
9. [Data Layer](#9-data-layer)
10. [Authentication & RBAC](#10-authentication--rbac)
11. [Frontend](#11-frontend)
12. [Infrastructure](#12-infrastructure)
13. [Key File Reference](#13-key-file-reference)

---

## 1. What This System Does

PT Pembangunan Jaya Ancol Tbk (IDX: PJAA) needs to audit its Board of Directors Minutes of Meetings (Risalah Rapat Direksi) against structural compliance standards, regulatory alignment, and substantive consistency.

The problem: 5+ years of historical MoMs in mixed formats (scans, PDFs, Word docs). Regulatory corpus scattered across physical copies, shared drives, and a DMS. Manual compliance auditing is slow and error-prone.

The solution: A multi-agent AI system on Google Cloud that automatically processes MoMs through four specialized Gemini agents, each gated by human approval, producing a three-pillar compliance scorecard.

**No compliance finding reaches the Board without human approval.** Every stage has a mandatory Human-in-the-Loop (HITL) gate.

---

## 2. System Overview

```
 User uploads MoM (email or manual)
         │
         ▼
 ┌─────────────────┐
 │ Document AI OCR  │  ← Document Processor (Cloud Run)
 └────────┬────────┘
          │ Pub/Sub: mom-ocr-complete
          ▼
 ┌─────────────────┐
 │ Extraction Agent │  ← Gemini 2.5 Flash
 │ (structure,      │
 │  attendees,      │
 │  resolutions)    │
 └────────┬────────┘
          │
       [HITL Gate 1] ← Corp Secretary reviews extraction
          │
          ▼
 ┌─────────────────┐
 │ Legal Research   │  ← Gemini 2.5 Pro + Vertex AI Search RAG
 │ Agent            │
 │ (regulation      │
 │  mapping)        │
 └────────┬────────┘
          │
       [HITL Gate 2] ← Internal Auditor / Legal reviews mapping
          │
          ▼
 ┌─────────────────┐
 │ Comparison Agent │  ← Gemini 2.5 Pro + rule-based red flags
 │ (compliance      │
 │  findings,       │
 │  severity)       │
 └────────┬────────┘
          │
       [HITL Gate 3] ← Internal Auditor reviews findings
          │
          ▼
 ┌─────────────────┐
 │ Reporting Agent  │  ← Gemini 2.5 Flash
 │ (scorecard,      │
 │  PDF report)     │
 └────────┬────────┘
          │
       [HITL Gate 4] ← Dual approval: Corp Sec + Internal Audit
          │
          ▼
    Final Report (PDF)
    visible to Komisaris
```

11 Cloud Run services. 4 Gemini agents. 4 HITL gates. 282 unit tests. All in `asia-southeast2` (Jakarta) for data sovereignty.

---

## 3. Document Ingestion

Documents enter the system through two paths.

### 3a. Email Ingest (automatic)

**Service:** `services/email-ingest/` | **Trigger:** Cloud Scheduler, every 15 minutes

1. `POST /scan` is triggered by cron.
2. `scanner.scan_inbox()` queries Gmail: `"has:attachment -label:MoM-Processed is:unread"`.
3. Each attachment is checked by `_is_mom_attachment()`:
   - Filename must match: `risalah|notulen|minutes|mom|rapat`, `rups|rupslb|rupst`, or `direksi|komisaris|board`.
   - MIME type must be PDF, Word, PNG, JPEG, or TIFF.
4. On match, `_upload_to_pipeline()`:
   - Generates a UUID `doc_id`.
   - Uploads to GCS: `gs://{bucket_raw}/email-ingest/{doc_id}/{filename}`.
   - Creates a `Document` record with `status=pending`.
   - MoM type is inferred from subject/filename: "sirkuler/circular", "luar biasa/extraordinary", or "regular".
   - Meeting date is parsed from the subject line via `parse_indonesian_date()`.
   - Publishes to Pub/Sub topic `ancol-mom-uploaded`.
5. Gmail message is labeled `MoM-Processed` to prevent re-scanning.

### 3b. Manual Upload (via API or Gemini chat)

**Endpoint:** `POST /api/documents/upload` | **Permission:** `documents:upload` (corp_secretary, admin)

- Accepts multipart form: file, `mom_type`, `meeting_date`, `is_confidential`, `uploaded_by`.
- Uploads to `gs://{bucket_raw}/uploads/{doc_id}/{filename}`.
- Same `Document` record creation and Pub/Sub publish as email ingest.
- Also accessible via the Gemini Enterprise chat interface (`upload_document` tool).

### 3c. Document Processing (OCR)

**Service:** `services/document-processor/` | **Trigger:** Pub/Sub push from `ancol-mom-uploaded`

1. Receives the Pub/Sub message, decodes `document_id` and GCS URI.
2. Transitions document status: `pending` -> `processing_ocr`.
3. Downloads the raw file from GCS.
4. Calls **Google Document AI Form Parser**: extracts full text, per-page blocks with confidence scores and bounding boxes, tables (header/body rows), detected languages.
5. Writes OCR JSON to `gs://{bucket_processed}/ocr/{document_id}/{base_name}.json`.
6. Updates the `Document` record: `gcs_processed_uri`, `ocr_confidence` (average block confidence), `page_count`.
7. Transitions: `processing_ocr` -> `ocr_complete`.
8. Publishes to `ancol-mom-ocr-complete` with `document_id`, `processed_uri`, `page_count`, `overall_confidence`, `processing_time_ms`.

---

## 4. The Agent Pipeline

Four agents process each MoM sequentially. Each is a separate FastAPI service on Cloud Run receiving Pub/Sub push messages.

### Document Status State Machine

```
pending -> processing_ocr -> ocr_complete -> extracting -> hitl_gate_1
  hitl_gate_1 -> researching (approved) | rejected
  researching -> hitl_gate_2
  hitl_gate_2 -> comparing (approved) | rejected
  comparing -> hitl_gate_3
  hitl_gate_3 -> reporting (approved) | rejected
  reporting -> hitl_gate_4
  hitl_gate_4 -> complete (approved) | rejected
  failed -> pending (retry)
```

Defined in `ancol_common.db.repository.VALID_TRANSITIONS`.

### Agent 1: Extraction Agent

**Service:** `services/extraction-agent/` | **Model:** Gemini 2.5 Flash | **Trigger:** `mom-ocr-complete`

**What it does:** Extracts structured data from the OCR text.

**Process:**
1. Loads OCR JSON from GCS.
2. Loads the `MomTemplate` configuration from DB (or default 8-section template: opening, attendance, quorum_verification, agenda, discussion, resolutions, closing, signatures).
3. Sends OCR text + tables + template to Gemini Flash (`temperature=0.1`, JSON response mode).
4. The system prompt (in Indonesian) instructs the model to extract:
   - Meeting metadata: date (ISO format), type, number, location.
   - Attendees: chairman, secretary, present/absent directors with titles.
   - Agenda items with section mappings.
   - Resolutions: numbered, with assignee and deadline.
   - Performance data and cross-references.
   - Signers.
5. Each field gets a confidence score (0.0-1.0). Fields below 0.8 are flagged as `low_confidence_fields`.
6. **Structural scoring** (`parsers/structural.compute_structural_score()`): checks required sections present, quorum met (`directors_present / total_directors >= 50%`), signatures present, required fields filled. Score = passed/total x 100.
7. Stores the result as an `Extraction` record (JSONB fields).
8. Transitions: `extracting` -> `hitl_gate_1`.
9. Publishes to `ancol-mom-extracted`.

### Agent 2: Legal Research Agent

**Service:** `services/legal-research-agent/` | **Model:** Gemini 2.5 Pro + Vertex AI Search RAG | **Trigger:** Cloud Workflows (after Gate 1 approval)

**What it does:** Maps each resolution to applicable regulations using RAG-grounded research.

**Process:**
1. Receives document_id + extraction_id from the workflow.
2. Uses Gemini 2.5 Pro with **Vertex AI Search grounding** (the `regulatory-corpus` datastore containing POJK, UU PT, BEI rules, and the company charter).
3. Temperature: `0.0` (maximum precision, zero creative liberty).
4. Input: meeting date, chairman, quorum status, each resolution with text/assignee/deadline.
5. Output: `regulatory_mapping` (per-resolution -> applicable clauses), `overlap_flags`, `conflict_flags`, `corpus_freshness`.

**Citation Validation** (3-layer anti-hallucination in `retrieval/citation_validator.py`):
1. `retrieval_score >= 0.5` (minimum relevance threshold).
2. `retrieval_source_id` must be non-empty (proves it came from the datastore, not hallucinated).
3. `clause_text` must be >= 10 characters.
4. **Zero tolerance:** `MAX_UNSOURCED_RATIO = 0.0`. If any citation fails, it is stripped from the output. No unsourced claims are allowed.

6. Stores as `RegulatoryContext` record.
7. Transitions: `researching` -> `hitl_gate_2`.
8. Publishes to `ancol-mom-researched`.

### Agent 3: Comparison Agent

**Service:** `services/comparison-agent/` | **Model:** Gemini 2.5 Pro + rule-based detectors | **Trigger:** Cloud Workflows (after Gate 2 approval)

**What it does:** Identifies compliance violations through a combination of hard-coded rules and AI analysis.

**Process (4 steps):**

**Step 1 — Rule-based red flag detection** (`analyzers/red_flags.detect_all_red_flags()`):

| Detector | What It Checks | Severity | Regulation |
|----------|---------------|----------|------------|
| Quorum violations | Directors present < 50%, chairman absent | CRITICAL / HIGH | UU PT 40/2007 Pasal 86 |
| Related-party transactions (RPT) | 9 known PJAA group entities + keywords (afiliasi, pihak berelasi, benturan kepentingan) | HIGH | POJK 42/2020 Pasal 3 |
| Conflict of interest | COI keywords without abstention keywords | CRITICAL | POJK 42/2020 Pasal 12 ayat (3) |
| Circular resolution issues | Non-unanimous circular resolutions | CRITICAL | UU PT 40/2007 Pasal 91 |
| Signature issues | Missing signatures, fewer than 2 signers | HIGH / MEDIUM | Company charter |

**Step 2 — Gemini Pro chain-of-thought analysis:**
- Temperature `0.1`, receives: full structured MoM + regulatory mapping + rule-based flags + related party entity list.
- Outputs: findings with `finding_id`, `resolution_number`, `regulation_id`, `compliance_status`, `severity`, `chain_of_thought`, `evidence_refs`.

**Step 3 — Merge:** AI findings supplemented with any rule-based flags not already caught.

**Step 4 — Scoring** (`analyzers/severity.py`):
- Regulatory score: starts at 100. CRITICAL: -25 (max -50 total), HIGH: -10, MEDIUM: -5, LOW: -2.
- Substantive score: starts at 100. -15 per inconsistency.

Stores as `ComplianceFindingRecord`. Transitions: `comparing` -> `hitl_gate_3`.

### Agent 4: Reporting Agent

**Service:** `services/reporting-agent/` | **Model:** Gemini 2.5 Flash | **Trigger:** Cloud Workflows (after Gate 3 approval)

**What it does:** Generates the final compliance report with scorecard, executive summary, and PDF.

**Process (3 steps):**

**Step 1 — Three-pillar scorecard** (`generators/scorecard.compute_scorecard()`):

| Pillar | Weight | What It Measures |
|--------|--------|-----------------|
| Structural Completeness | 30% | Required sections present, quorum met, signatures |
| Substantive Consistency | 35% | Internal consistency of resolutions, no contradictions |
| Regulatory Compliance | 35% | Adherence to POJK, UU PT, BEI rules, company charter |

- Composite = structural x 0.30 + substantive x 0.35 + regulatory x 0.35.
- Grades: A >= 90 (Sangat Baik), B >= 80 (Baik), C >= 70 (Cukup), D >= 60 (Kurang), F < 60 (Tidak Memenuhi).
- Historical trend calculation against 3-month, 6-month, 12-month windows.

**Step 2 — Executive summary** (Gemini Flash, temperature 0.3):
- 150-250 words, formal Bahasa Indonesia, board-ready.
- Corrective suggestions per CRITICAL/HIGH finding with `current_wording`, `suggested_wording`, `regulatory_basis`.

**Step 3 — HTML/PDF report** (`generators/pdf.generate_report_html()`):
- A4 page, Noto Sans/Arial, corporate blue (`#1a237e`).
- Header: "LAPORAN KEPATUHAN RISALAH RAPAT — RAHASIA" (Confidential).
- Scorecard pills with grade-colored backgrounds.
- Findings sorted by severity, corrective suggestions table.
- PDF rendered via WeasyPrint (falls back to HTML if not installed).
- Uploaded to `gs://{bucket_reports}/`.

Stores as `Report` record with dual-approval fields. Transitions: `reporting` -> `hitl_gate_4`.

---

## 5. Human-in-the-Loop Gates

Every agent output must be reviewed and approved before the pipeline proceeds. No exceptions.

### How It Works

**Review queue:** `GET /api/hitl/queue` — returns all documents currently waiting at any gate, ordered by oldest first. Requires `hitl:decide` permission.

**Review detail:** `GET /api/hitl/review/{document_id}` — returns the AI output for the current gate:
- Gate 1: Structured MoM extraction + deviation flags.
- Gate 2: Regulatory mapping with citations.
- Gate 3: Compliance findings + red flags + severity scores.
- Gate 4: Final report + scorecard + PDF preview.

**Submit decision:** `POST /api/hitl/decide/{document_id}`

```json
{
  "decision": "approved",       // or "rejected" or "modified"
  "reviewer_id": "uuid",
  "reviewer_role": "internal_auditor",
  "modified_data": null,         // optional: corrections to AI output
  "modification_summary": null,  // what was changed and why
  "notes": "Looks good."
}
```

### Decision outcomes

| Decision | Effect |
|----------|--------|
| `approved` | Pipeline proceeds to next agent |
| `modified` | Pipeline proceeds with human corrections applied (stored in `modified_data`) |
| `rejected` | Document status -> `rejected`. Pipeline stops. |

### Gate-to-role mapping

| Gate | Primary Reviewer | Why |
|------|-----------------|-----|
| Gate 1 (Extraction) | Corp Secretary | Knows the meeting firsthand, can verify attendees/resolutions |
| Gate 2 (Legal Research) | Internal Auditor or Legal & Compliance | Can validate regulation mappings |
| Gate 3 (Comparison) | Internal Auditor | Can assess severity of compliance findings |
| Gate 4 (Reporting) | Dual: Corp Secretary + Internal Auditor | Both must sign off before report is visible to Komisaris |

### SLA tracking

Each `HitlDecisionRecord` has a `sla_deadline` (default: 48 hours from creation) and `is_sla_breached` flag. Escalation fields (`escalated_to`, `escalation_reason`) are available for overdue reviews.

### How the workflow resumes

When a decision is submitted, the API Gateway publishes to `ancol-hitl-decided`. Cloud Workflows has a **pull subscription** (`ancol-hitl-decided-pull`) that blocks at each gate. On receiving the decision message, the workflow checks the decision and either proceeds or raises a 400 (rejected).

---

## 6. Orchestration

### Cloud Workflows

The pipeline is orchestrated by a Cloud Workflow (`infra/modules/workflows/workflow.yaml`) triggered by Pub/Sub.

**Execution sequence:**

| Step | Service Called | Auth | Next |
|------|--------------|------|------|
| 1. `call_extraction_agent` | `POST /extract` on extraction-agent | OIDC | Set status `hitl_gate_1` |
| 2. `wait_gate_1` | Pull from `ancol-hitl-decided-pull` | — | Check decision |
| 3. `call_legal_research_agent` | `POST /research` on legal-research-agent | OIDC | Set status `hitl_gate_2` |
| 4. `wait_gate_2` | Pull from `ancol-hitl-decided-pull` | — | Check decision |
| 5. `call_comparison_agent` | `POST /compare` on comparison-agent | OIDC | Set status `hitl_gate_3` |
| 6. `wait_gate_3` | Pull from `ancol-hitl-decided-pull` | — | Check decision |
| 7. `call_reporting_agent` | `POST /report` on reporting-agent | OIDC | Set status `hitl_gate_4` |
| 8. `wait_gate_4` | Pull from `ancol-hitl-decided-pull` | — | Check decision |
| 9. `complete` | `POST /api/internal/status` with `status: complete` | — | Done |

Each "wait" step blocks until the corresponding HITL decision arrives. If the decision is "rejected", the workflow raises a 400 error and stops.

### Pub/Sub Topics

11 topics with prefix `ancol-`, each with a dead-letter queue (`-dlq`), 24-hour message retention, 5-attempt max delivery, exponential backoff (10s-600s):

| Topic | Publisher | Consumer |
|-------|-----------|----------|
| `ancol-mom-uploaded` | Email Ingest / API Gateway | Document Processor |
| `ancol-mom-ocr-complete` | Document Processor | Extraction Agent |
| `ancol-mom-extracted` | Extraction Agent | API Gateway (HITL notify) |
| `ancol-mom-researched` | Legal Research Agent | API Gateway (HITL notify) |
| `ancol-mom-compared` | Comparison Agent | API Gateway (HITL notify) |
| `ancol-mom-reported` | Reporting Agent | API Gateway (HITL notify) |
| `ancol-hitl-pending` | API Gateway | API Gateway (queue update) |
| `ancol-hitl-decided` | API Gateway | Cloud Workflows (pull) |
| `ancol-contract-uploaded` | API Gateway | Extraction Agent |
| `ancol-contract-analyzed` | Extraction Agent | API Gateway |
| `ancol-obligation-reminder` | Obligation Scheduler | API Gateway |

### Batch Engine

**Service:** `services/batch-engine/` | For processing multiple MoMs at once.

- `POST /api/batch/start` — creates a `BatchJob` with list of document IDs.
- Token bucket rate limiter (`ancol_common.gemini.rate_limiter`) prevents Gemini API throttling.
- Concurrency control: processes N documents in parallel (configurable).
- Status tracking per-item with retry counts.
- Publishes progress to `ancol-batch-progress`.

---

## 7. Contract Lifecycle Management

Added in CLM Phases 1-4. Extends the system beyond MoM compliance to full contract lifecycle tracking.

### Contract Extraction

**Trigger:** `POST /extract-contract` on Extraction Agent, via `ancol-contract-uploaded` Pub/Sub.

1. OCR text is processed by `contract_parser.extract_contract()`.
2. Extracts: parties, clauses (with risk levels), key dates, financial terms, obligations.
3. Stores `ContractClauseRecord` and `ContractPartyRecord` rows.
4. Updates `Contract` with: `effective_date`, `expiry_date`, `total_value`, `currency`, `risk_level`, `risk_score`.
5. Creates `ObligationRecord` for each extracted obligation.
6. **Parallel post-processing:**
   - Indexes clauses into Vertex AI Search (`ancol-contract-clauses` datastore).
   - Seeds Spanner Graph edges: contract -> regulation, contract -> parent_contract.

### Contract Lifecycle States

```
draft -> pending_review -> in_review -> approved -> executed -> active
active -> expiring -> active (renew) | expired | terminated
active -> amended -> active
```

### Smart Drafting

**Endpoint:** `POST /api/drafting/generate`

- Input: `contract_type`, `parties`, `key_terms`, `clause_overrides`, `language`.
- Pulls template from `ContractTemplate` table.
- Pulls mandatory + optional clauses from `ClauseLibrary`.
- 7 supported contract types: NDA, vendor, sale/purchase, joint venture, land lease, employment, SOP/board resolution.
- `POST /api/drafting/pdf` generates a styled PDF.
- `GET /api/drafting/clause-library` browses the clause library (filterable by type, category, mandatory-only).

### Contract Q&A RAG

**Tool:** `ask_contract_question` via Gemini Enterprise chat.

3-layer retrieval:

| Layer | Source | Priority |
|-------|--------|----------|
| 1. Cloud SQL | Direct clause lookup for specific contract | Highest (relevance=1.0) |
| 2. Vertex AI Search | Semantic search across all contract clauses | Medium |
| 3. Spanner Graph | Amendment chains + linked regulations | Lowest |

Re-ranking: `cloud_sql(weight=3) > vector_search(2) > graph(1)` multiplied by relevance score. Top 15 chunks go to Gemini 2.5 Pro for synthesis.

### Obligation Tracking

**Daily scheduler** (07:00 WIB via `check_obligation_deadlines()`):

1. Overdue: `upcoming/due_soon` with `due_date <= today` -> `overdue`.
2. Due soon: `upcoming` with `due_date <= today + 30 days` -> `due_soon`.
3. Sends reminders at 30-day, 14-day, and 7-day marks.
4. Recurrence: fulfilled obligations with recurrence create a new `ObligationRecord` (monthly, quarterly, annual).

Obligation types: renewal, reporting, payment, termination_notice, deliverable, compliance_filing.

---

## 8. The Gemini Enterprise Interface

The primary user interface is Gemini Enterprise chat via Vertex AI Agent Builder. Users talk to a chatbot that can perform all system actions.

**Service:** `services/gemini-agent/` | **Entry:** `POST /webhook`

### How It Works

1. Vertex AI Agent Builder sends a webhook request: `{tool_call: {name, parameters}, user_identity: {role, email}}`.
2. The webhook checks RBAC: `ROLE_TOOL_ACCESS` maps each of the 7 roles to their allowed tools.
3. If denied: returns HTTP 200 with a denial message in Indonesian (Agent Builder requires 200 always).
4. If allowed: dispatches to the appropriate tool handler.

### Available Tools

| Tool | What It Does | Who Can Use It |
|------|-------------|----------------|
| `upload_document` | Upload a MoM for processing | corp_secretary, admin |
| `review_gate` | View the HITL review queue | corp_secretary, internal_auditor, legal_compliance, admin |
| `get_review_detail` | View AI output for a specific gate | Same as above |
| `submit_decision` | Approve/reject/modify at a gate | Same as above |
| `check_status` | Check document processing status | All roles |
| `get_report` | View a completed compliance report | komisaris (approved only), internal_auditor, corp_secretary, admin |
| `search_regulations` | Search the regulatory corpus | legal_compliance, internal_auditor, admin |
| `get_dashboard` | View compliance dashboard | komisaris, internal_auditor, corp_secretary, admin |
| `upload_contract` | Upload a contract for analysis | corp_secretary, legal_compliance, contract_manager, admin |
| `check_contract_status` | Check contract processing status | All with contracts access |
| `get_contract_portfolio` | View all contracts | All with contracts access |
| `get_contract_risk` | View risk analysis for a contract | All with contracts access |
| `list_obligations` | View obligation deadlines | contract_manager, legal_compliance, admin |
| `fulfill_obligation` | Mark an obligation as fulfilled | contract_manager, legal_compliance, admin |
| `generate_draft` | Generate a contract draft | legal_compliance, contract_manager, business_dev, admin |
| `ask_contract_question` | Ask a question about a contract (RAG) | All with contracts access |

### HITL in Gemini Chat

- **Gate 1 is synchronous:** The agent polls until extraction completes (~5 min max).
- **Gates 2-4 are asynchronous:** Different roles review at different times. Users initiate review via "Apa yang perlu direview?" (What needs to be reviewed?).

All tool handlers proxy to the API Gateway via `ApiClient` (configured by `API_GATEWAY_URL` env var). The Gemini Agent never accesses Cloud SQL or GCS directly.

---

## 9. Data Layer

### Cloud SQL (PostgreSQL 15)

21 ORM tables in `packages/ancol-common/src/ancol_common/db/models.py`. Key tables:

| Table | Purpose |
|-------|---------|
| `users` | 7 roles, Google identity, `manager_id` self-ref for escalation chains |
| `documents` | Full lifecycle (14 status values), GCS URIs, batch_job FK |
| `extractions` | Agent 1 output: JSONB structured_mom, attendees, resolutions, deviation_flags |
| `regulatory_contexts` | Agent 2 output: JSONB regulatory_mapping, overlap/conflict flags |
| `compliance_findings` | Agent 3 output: JSONB findings, red_flags, numeric scores |
| `reports` | Agent 4 output: 3 pillar scores + composite, GCS PDF/Excel URIs, dual-approval |
| `hitl_decisions` | Per-gate: decision, reviewer, SLA deadline, escalation fields |
| `audit_trail` | Append-only: actor, action, resource, IP address |
| `contracts` | 11-status lifecycle, risk fields, JSONB extraction_data |
| `contract_clauses` | Per-clause with risk_level, confidence, is_from_library flag |
| `contract_parties` | Per-contract party with related_party_entity FK |
| `obligations` | 5-status lifecycle, recurrence, 3 reminder-sent booleans |
| `clause_library` | Bilingual (ID/EN) approved clauses per contract type |
| `batch_jobs` / `batch_items` | Batch processing with concurrency and retry tracking |
| `mom_templates` | JSONB required sections, quorum rules, signature rules |
| `regulation_index` | Regulation metadata, Vertex AI datastore references |
| `related_party_entities` | PJAA group entities for RPT detection |
| `notifications` | 4 channels (email, in-app, WhatsApp, push) |

### Vertex AI Search

Two datastores:

| Datastore | Contents | Used By |
|-----------|----------|---------|
| `regulatory-corpus` | POJK, UU PT, BEI rules, company charter | Legal Research Agent (grounding tool) |
| `ancol-contract-clauses` | Indexed contract clauses | Contract Q&A RAG |

Both use: `QueryExpansionSpec.Condition.AUTO`, `SpellCorrectionSpec.Mode.AUTO`, `page_size=20`.

### Spanner Graph

Configurable backend via `GRAPH_BACKEND` env var (`spanner` default, `neo4j` alternative, `none` for vector-only).

**Graph client interface** (`rag/graph_client.GraphClient`):
- `get_amendment_chain(reg_id)` — regulation amendment history.
- `check_active_status(reg_id)` — is this regulation still in force?
- `find_cross_references(clause_id)` — clauses referencing each other.
- `get_related_regulations_for_contract(contract_id)` — regulations linked to a contract.
- `get_related_contracts(contract_id)` — amendment chain / related contracts.

**Re-ranking formula:** `relevance_score x recency_weight x authority_level`
- Authority: UU PT=5, POJK=4, SE-OJK=3, IDX rules=2, Internal charter=1.
- Recency: <=2 years=1.0, 2-5 years=0.8, older=0.6.

### GCS Buckets

| Bucket | Contents |
|--------|----------|
| `ancol-mom-raw` | Raw uploaded files |
| `ancol-mom-processed` | OCR JSON output |
| `ancol-mom-reports` | PDF/Excel compliance reports |
| `ancol-contracts` | Contract files |

---

## 10. Authentication & RBAC

### Authentication

**Google Cloud IAP** reads JWT from `X-Goog-IAP-JWT-Assertion` header. Email extracted from `X-Goog-Authenticated-User-Email`. User looked up in `users` table. Inactive users are rejected (403).

Dev fallback: `X-Dev-User-Email` header (with warning log, only in non-production).

### 7 User Roles

| Role | Primary Responsibility |
|------|----------------------|
| `corp_secretary` | Uploads MoMs, reviews Gate 1 and Gate 4, manages templates |
| `internal_auditor` | Reviews Gates 2-4, views dashboard and reports |
| `komisaris` | Views approved reports and dashboard (read-only) |
| `legal_compliance` | Reviews Gate 2, manages regulatory corpus, contract review |
| `contract_manager` | Manages contracts, fulfills obligations, generates drafts |
| `business_dev` | Generates contract drafts |
| `admin` | Full access to all endpoints |

### RBAC Enforcement

Every API endpoint uses `require_permission("key")` from `auth/rbac.py`.

Key permissions:

| Permission | Allowed Roles |
|-----------|---------------|
| `documents:upload` | corp_secretary, admin |
| `hitl:gate_1` | corp_secretary, admin |
| `hitl:gate_2` | internal_auditor, legal_compliance, admin |
| `hitl:gate_3` | internal_auditor, admin |
| `hitl:gate_4_corpsec` | corp_secretary, admin |
| `hitl:gate_4_audit` | internal_auditor, admin |
| `contracts:create` | corp_secretary, legal_compliance, contract_manager, admin |
| `contracts:approve` | legal_compliance, corp_secretary, admin |
| `drafting:generate` | legal_compliance, contract_manager, business_dev, admin |
| `reports:view_approved` | komisaris, internal_auditor, corp_secretary, legal_compliance, admin |

The Gemini Agent webhook has a separate RBAC layer (`ROLE_TOOL_ACCESS`) that maps roles to tool names. Denials return HTTP 200 with an Indonesian message (Vertex AI Agent Builder protocol requirement).

---

## 11. Frontend

**Stack:** Next.js 15, React 19, Tailwind CSS, shadcn/ui | **Path:** `web/`

16 routes organized in a grouped sidebar:

**MoM section:**
- Dashboard (compliance trends, heatmaps, batch progress)
- Document list
- HITL review queue
- Report viewer

**Contracts section:**
- Contract list
- Contract detail (clauses, risk, parties)
- Draft generator
- Obligation tracker

**Admin section:**
- User management
- Template configuration
- Regulation corpus management
- Audit trail

PWA-enabled (installable, offline-capable service worker, push notifications for HITL gate arrivals and obligation reminders).

---

## 12. Infrastructure

**Platform:** Google Cloud Platform, region `asia-southeast2` (Jakarta).

17 Terraform modules in `infra/modules/`:

| Module | GCP Service |
|--------|------------|
| `cloud-run` | 11 Cloud Run services (10 Python + 1 Next.js) |
| `cloud-sql` | PostgreSQL 15 instance |
| `pubsub` | 11 topics + subscriptions + DLQs |
| `workflows` | Cloud Workflows pipeline |
| `gcs` | 4 storage buckets |
| `vertex-ai-search` | 2 datastores (regulatory corpus, contract clauses) |
| `spanner` | Spanner Graph instance |
| `bigquery` | Analytics dataset |
| `iam` | Service accounts (prefixed `ancol-`) |
| `networking` | VPC, Cloud NAT |
| `secrets` | Secret Manager |
| `scheduler` | Cloud Scheduler (email scan, obligation check) |
| `monitoring` | Cloud Monitoring + alerting |
| `logging` | Structured logging |
| `document-ai` | Document AI processor |
| `agent-builder` | Vertex AI Agent Builder |
| `load-balancer` | Cloud Load Balancing + IAP |

Composed in `infra/environments/{env}/main.tf`.

---

## 13. Key File Reference

| What | Where |
|------|-------|
| Document state machine | `packages/ancol-common/src/ancol_common/db/repository.py` |
| Contract state machine | Same file, `CONTRACT_VALID_TRANSITIONS` |
| Status enums | `packages/ancol-common/src/ancol_common/schemas/mom.py` |
| ORM models (21 tables) | `packages/ancol-common/src/ancol_common/db/models.py` |
| RBAC permissions | `packages/ancol-common/src/ancol_common/auth/rbac.py` |
| Gemini tool access | `services/gemini-agent/src/gemini_agent/main.py` |
| Settings (34 env vars) | `packages/ancol-common/src/ancol_common/config.py` |
| Red flag detectors | `services/comparison-agent/src/comparison_agent/analyzers/red_flags.py` |
| Citation validator | `services/legal-research-agent/src/legal_research_agent/retrieval/citation_validator.py` |
| Scorecard engine | `services/reporting-agent/src/reporting_agent/generators/scorecard.py` |
| Hybrid RAG orchestrator | `services/gemini-agent/src/gemini_agent/rag/orchestrator.py` |
| Contract Q&A RAG | `services/gemini-agent/src/gemini_agent/rag/contract_rag.py` |
| Cloud Workflow | `infra/modules/workflows/workflow.yaml` |
| Pub/Sub topics | `infra/modules/pubsub/main.tf` |
| API routes | `services/api-gateway/src/api_gateway/routers/` |
| Extraction prompts | `services/extraction-agent/src/extraction_agent/prompts/` |
| Design spec (MoM) | `docs/superpowers/specs/2026-04-08-agentic-mom-compliance-design.md` |
| Design spec (Gemini Agent) | `docs/superpowers/specs/2026-04-12-gemini-agent-builder-integration-design.md` |
