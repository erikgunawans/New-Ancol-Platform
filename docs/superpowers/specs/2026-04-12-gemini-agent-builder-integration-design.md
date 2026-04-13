# Gemini Enterprise Agent Builder Integration — Design Specification

**Project:** PT Pembangunan Jaya Ancol Tbk — MoM Compliance System
**Platform:** Google Cloud Platform — Vertex AI Agent Builder + Gemini Enterprise
**Architecture:** Webhook-based tool calling with Hybrid RAG
**Date:** 2026-04-12

---

## 1. Problem Statement

The Ancol MoM Compliance System currently uses a custom Next.js frontend for document upload, HITL review, and report viewing. The client wants to shift the primary interface to **Gemini Enterprise** — users interact with the compliance system through the Gemini chat, uploading documents, reviewing AI outputs, making HITL decisions, and viewing compliance results all within the conversational interface.

The existing 9 backend services (Document Processor, 4 Gemini agents, Batch Engine, Email Ingest, Regulation Monitor, API Gateway) remain unchanged. A new webhook service bridges Gemini's function calling to the existing API Gateway.

## 2. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Integration method | Vertex AI Agent Builder + Cloud Run webhook | Native Gemini Enterprise experience, managed agent hosting, clean separation between agent logic and backend |
| Alternative considered | Custom Gemini agent on Cloud Run (direct) | Rejected: doesn't plug into Gemini Enterprise natively, requires building conversation management |
| Alternative considered | Vertex AI Extensions | Rejected: insufficient control over hybrid HITL flow and agent behavior |
| HITL model | Hybrid — sync Gate 1, async Gates 2-4 | Gate 1 (extraction) is fast and done by the uploader. Gates 2-4 involve different roles and take longer |
| RAG strategy | Hybrid — Vertex AI Search + Graph RAG + SQL | Vector search alone misses regulation relationships (amendments, cross-references, authority chains) |
| Graph store (primary) | Cloud Spanner Graph | Google-native, same region (asia-southeast2), GQL support, no external vendor dependency |
| Graph store (fallback) | Neo4j AuraDS via GCP Marketplace | More mature graph traversal, ready if Spanner Graph GQL proves limiting |
| Language | Bahasa Indonesia (default) + English legal terms | Matches existing system conventions and user expectations |
| Frontend | Next.js becomes secondary analytics view | Dashboards/trend charts are better as visual pages; primary workflow moves to chat |

## 3. Agent Identity

**Name:** Ancol MoM Compliance Assistant
**Platform:** Vertex AI Agent Builder, accessible via Gemini Enterprise sidebar
**Language:** Bahasa Indonesia primary, English legal/regulatory terminology

**System prompt core directives:**
- You are a compliance auditor for PT Pembangunan Jaya Ancol Tbk (IDX: PJAA)
- You help users upload MoM documents, review AI-extracted data, make HITL decisions, and view compliance reports
- You never fabricate regulation citations — all legal references come from the grounded Vertex AI Search corpus and regulation knowledge graph
- You identify the user's role from IAP identity and restrict tool access accordingly
- When presenting extraction results, always show confidence scores and flag items below 80% confidence
- When presenting compliance findings, always include severity level and chain-of-thought reasoning

**Grounding:** Connected to existing Vertex AI Search datastore (`regulatory-corpus`, 69 chunks) + Hybrid RAG system for conversational regulation questions.

**Role-based tool access:**

| Role | Can use |
|------|---------|
| Corp Secretary | upload_document, check_status, review_gate (Gate 1), submit_decision (Gate 1), get_report |
| Internal Auditor | review_gate (all gates), get_review_detail, submit_decision (all gates), get_report, get_dashboard |
| Komisaris | get_report, get_dashboard, search_regulations |
| Legal & Compliance | review_gate (Gate 2 primary), get_review_detail, submit_decision, search_regulations |
| Admin | All tools |

## 4. Tool Definitions

### 4.1 `upload_document` (Synchronous Gate 1 flow)

**Trigger:** User drags/attaches a file in the Gemini chat
**Parameters:**
```json
{
  "file": "binary (from Gemini file upload)",
  "mom_type": "regular|circular|extraordinary (default: regular)",
  "meeting_date": "YYYY-MM-DD (optional, agent can ask)",
  "is_confidential": "boolean (default: false)"
}
```

**Flow:**
1. Webhook receives file, calls `POST /api/documents/upload` (multipart)
2. Webhook polls `GET /api/documents/{id}` every 10s, max 5 minutes
3. When status reaches `hitl_gate_1`:
   - Calls `GET /api/hitl/review/{id}`
   - Returns formatted extraction to agent: attendees, resolutions, quorum, flags
   - Agent asks user to approve/reject/modify
4. If extraction isn't done in 5 minutes, falls back to async: "Pemrosesan memerlukan waktu lebih lama. Saya akan memberitahu Anda saat Gate 1 siap."
5. On user decision, calls `POST /api/hitl/decide/{id}`

**Response to agent:** Formatted Bahasa Indonesia summary of extraction results with confidence indicators.

### 4.2 `review_gate` (Async HITL queue)

**Trigger:** "Apa yang perlu direview?", "What's pending?", or proactive check
**Parameters:**
```json
{
  "gate": "gate_1|gate_2|gate_3|gate_4 (optional, filters by gate)"
}
```

**Maps to:** `GET /api/hitl/queue?gate={gate}`
**Response:** List of documents awaiting review, filtered by user's role permissions.

### 4.3 `get_review_detail`

**Trigger:** User selects a document from the review queue
**Parameters:**
```json
{
  "document_id": "uuid"
}
```

**Maps to:** `GET /api/hitl/review/{document_id}`
**Response:** Gate-specific AI output formatted for chat:
- Gate 1: Extracted MoM structure, attendees, resolutions, deviation flags
- Gate 2: Regulation mappings with citations, coverage analysis
- Gate 3: Red flags with severity, chain-of-thought reasoning
- Gate 4: Full compliance scorecard, corrective suggestions, report preview

### 4.4 `submit_decision`

**Trigger:** "Approve", "Reject", "Saya ingin mengubah daftar peserta"
**Parameters:**
```json
{
  "document_id": "uuid",
  "decision": "approved|rejected|modified",
  "modified_data": "object (optional, for modifications)",
  "modification_summary": "string (optional)",
  "notes": "string (optional)"
}
```

**Maps to:** `POST /api/hitl/decide/{document_id}`
**Response:** Confirmation with next status. If approved at Gates 1-3, informs which team is next. If Gate 4 approved, announces completion.

### 4.5 `check_status`

**Trigger:** "Status risalah rapat Maret?", "Where is document X?"
**Parameters:**
```json
{
  "query": "string (filename, date, or document ID)"
}
```

**Maps to:** `GET /api/documents?status=*` with search logic in webhook, or `GET /api/documents/{id}` for direct ID lookup.
**Response:** Current state in the 14-state machine, time in current state, who's responsible next.

### 4.6 `get_report`

**Trigger:** "Tampilkan laporan compliance", "Show me the report for..."
**Parameters:**
```json
{
  "document_id": "uuid (optional)",
  "report_id": "uuid (optional)"
}
```

**Maps to:** `GET /api/reports/{id}`
**Response:** Formatted scorecard (3 pillars with scores), key findings, corrective suggestions, download links for PDF/Excel.

### 4.7 `search_regulations`

**Trigger:** "Apa yang diatur POJK 33/2014 tentang kuorum?", regulatory questions
**Parameters:**
```json
{
  "query": "string (natural language regulation question)"
}
```

**Flow:** Hybrid RAG orchestrator (see Section 5)
**Response:** Grounded answer with full citation chain, related regulations, amendment history.

### 4.8 `get_dashboard`

**Trigger:** "Overview compliance", "Berapa dokumen yang sudah selesai?"
**Parameters:**
```json
{
  "include_trends": "boolean (default: false)",
  "months": "int (default: 6, for trend data)"
}
```

**Maps to:** `GET /api/dashboard/stats` + optionally `GET /api/dashboard/stats/trends`
**Response:** Summary statistics, status breakdown, average scores, active batch jobs.

## 5. Hybrid RAG Architecture

### 5.1 Three-Layer Retrieval

| Layer | Technology | Data | Query type |
|-------|-----------|------|------------|
| Vector (semantic) | Vertex AI Search | 69 regulation chunks | Natural language similarity |
| Graph (relational) | Cloud Spanner Graph (primary) / Neo4j AuraDS (fallback) | ~200 regulation nodes, ~500 clause nodes, ~1000 edges | Relationship traversal |
| Structured (exact) | Cloud SQL (existing) | Documents, reports, scores | SQL exact lookups |

### 5.2 Knowledge Graph Schema

**Nodes:**

| Node type | Properties |
|-----------|-----------|
| `Regulation` | id, title, issuer (OJK/IDX/UUPT/Internal), effective_date, status (active/superseded/amended), authority_level (1-5) |
| `Clause` | id, regulation_id, clause_number, text_summary, domain |
| `Domain` | name (quorum, conflict_of_interest, reporting, signatures, etc.) |

**Edges:**

| Edge type | From → To | Properties |
|-----------|----------|-----------|
| `AMENDS` | Regulation → Regulation | effective_date, change_type (partial/full) |
| `SUPERSEDES` | Regulation → Regulation | effective_date |
| `REFERENCES` | Clause → Clause | reference_type (citation/definition/exception) |
| `BELONGS_TO` | Clause → Domain | — |
| `GOVERNS` | Regulation → Domain | scope |
| `CONFLICTS_WITH` | Clause → Clause | resolution_priority, resolution_note |

### 5.3 Authority Ranking

When results conflict, higher authority wins:
1. UUPT (Undang-Undang Perseroan Terbatas) — law
2. POJK (Peraturan OJK) — OJK regulation
3. SE-OJK (Surat Edaran OJK) — OJK circular
4. IDX Rules — stock exchange rules
5. Internal (AD/ART, Board Charter, SOP) — company internal

### 5.4 Retrieval Orchestration

```
query_regulations(user_query):
  1. Vertex AI Search → top 5 semantic matches (with relevance scores)
  2. Extract regulation_ids from vector results
  3. Graph traversal:
     - For each regulation_id:
       - Get amendment chain (what amends this? what does this amend?)
       - Get supersession chain (is this still active?)
       - Get cross-references (what else does this cite?)
       - Get related domains
  4. SQL lookup:
     - How many MoMs have been scored against these regulations?
     - What's the average compliance score for these rules?
  5. Re-rank by: relevance_score * recency_weight * authority_level
  6. Deduplicate, return top results with:
     - Full citation (regulation title, clause number, text)
     - Amendment history
     - Authority level
     - Practical context (how many MoMs affected, avg scores)
```

### 5.5 Graph Store Implementations

**Primary — Cloud Spanner Graph:**
- DDL: `CREATE PROPERTY GRAPH RegulationGraph` on existing Spanner instance
- Queries via GQL: `MATCH (r:Regulation)-[:AMENDS]->(t:Regulation) WHERE r.id = @id`
- Region: asia-southeast2 (same as all other services)
- Sizing: 1 processing unit (dev), auto-scaling for prod

**Fallback — Neo4j AuraDS:**
- Deployed via GCP Marketplace
- Cypher queries: `MATCH (r:Regulation)-[:AMENDS*1..3]->(chain) WHERE r.id = $id RETURN chain`
- Activated by setting `GRAPH_BACKEND=neo4j` + providing connection string via Secret Manager
- Same abstract `GraphClient` interface — swap is transparent to the rest of the system

**Abstract interface** (`rag/graph_client.py`):
```python
class GraphClient(ABC):
    async def query_related_regulations(self, regulation_id: str) -> list[RegulationNode]
    async def get_amendment_chain(self, regulation_id: str) -> list[AmendmentEdge]
    async def find_cross_references(self, clause_id: str) -> list[CrossReference]
    async def get_regulations_by_domain(self, domain: str) -> list[RegulationNode]
    async def check_active_status(self, regulation_id: str) -> bool
```

## 6. Webhook Service Architecture

### 6.1 Service Structure

```
services/gemini-agent/
├── src/gemini_agent/
│   ├── main.py              # FastAPI: POST /webhook, GET /health
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── upload.py         # upload_document (sync Gate 1 with polling)
│   │   ├── review.py         # review_gate, get_review_detail, submit_decision
│   │   ├── status.py         # check_status
│   │   ├── reports.py        # get_report
│   │   ├── regulations.py    # search_regulations (hybrid RAG orchestrator)
│   │   └── dashboard.py      # get_dashboard
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── orchestrator.py   # Combines vector + graph + SQL, re-ranks
│   │   ├── graph_client.py   # Abstract GraphClient interface
│   │   ├── spanner_graph.py  # Spanner Graph implementation
│   │   └── neo4j_graph.py    # Neo4j AuraDS implementation (behind flag)
│   ├── formatting.py         # JSON → rich Bahasa Indonesia chat text
│   └── api_client.py         # HTTP client for API Gateway (OIDC auth)
├── tests/
│   ├── test_webhook.py       # Webhook endpoint tests
│   ├── test_upload_tool.py   # Upload + sync Gate 1 flow
│   ├── test_review_tools.py  # HITL review/decide tools
│   ├── test_rag_orchestrator.py  # Hybrid RAG combination + re-ranking
│   ├── test_graph_client.py  # Graph store interface tests
│   └── test_formatting.py    # Response formatting tests
├── Dockerfile
└── pyproject.toml
```

### 6.2 Webhook Endpoint

`POST /webhook` receives Agent Builder tool calls:

```json
{
  "tool_call": {
    "name": "upload_document",
    "parameters": { ... }
  },
  "session_id": "string",
  "user_identity": {
    "email": "user@ancol.co.id",
    "role": "corp_secretary"
  }
}
```

Returns tool response:

```json
{
  "tool_response": {
    "name": "upload_document",
    "content": "formatted string or structured data for agent to relay"
  }
}
```

### 6.3 API Client

`api_client.py` wraps all calls to the existing API Gateway:
- Base URL from env: `API_GATEWAY_URL`
- OIDC token for service-to-service auth (gemini-agent SA → api-gateway)
- Retry with exponential backoff (3 retries, 1s/2s/4s)
- Timeout: 30s for most calls, 300s for upload polling

### 6.4 Response Formatting

`formatting.py` converts raw API JSON into chat-friendly Bahasa Indonesia:

| API response | Chat output |
|-------------|-------------|
| Extraction result | "**Risalah Rapat Direksi — 15 Maret 2026**\n\nPeserta (8 hadir dari 9):\n- Direktur Utama: Hadir\n..." |
| Scorecard | "**Skor Kepatuhan: 82/100**\n\nKelengkapan: 85 (30%)\nKepatuhan Hukum: 78 (35%)\nKualitas Tata Kelola: 84 (35%)" |
| Red flags | "**2 Temuan Kritis:**\n1. Kuorum tidak terpenuhi (hadir 4 dari min. 5)\n2. Tanda tangan Direktur Utama tidak ada" |
| Regulation query | "**POJK 33/2014 Pasal 15:**\n'Rapat Direksi sah apabila dihadiri...' \n\nDiamandemen oleh: POJK 18/2023 (berlaku 1 Jan 2024)" |

## 7. Infrastructure Changes

### 7.1 New Resources

| Resource | Purpose | Terraform |
|----------|---------|-----------|
| Cloud Run: `ancol-gemini-agent` | Webhook service | Existing `cloud-run` module, new call in `dev/main.tf` |
| Service Account: `gemini-agent` | Webhook identity | Add to `security/main.tf` |
| Cloud Spanner instance | Graph database for regulation relationships | New `infra/modules/spanner-graph/` |
| Vertex AI Agent Builder agent | Agent definition, tools, system prompt | New `infra/modules/agent-builder/` or manual console setup |
| IAM bindings | gemini-agent → invoke api-gateway, Agent Builder → invoke webhook | Add to `security/main.tf` |
| Secret Manager entry | Neo4j connection string (dormant) | Existing module |

### 7.2 New Terraform Module: `infra/modules/spanner-graph/`

```
infra/modules/spanner-graph/
├── main.tf       # Spanner instance, database, property graph DDL
├── variables.tf  # project_id, region, processing_units
└── outputs.tf    # instance_name, database_name
```

### 7.3 No Changes To

- Existing 9 Cloud Run services
- Cloud SQL (PostgreSQL)
- Pub/Sub (8 topics)
- Cloud Workflows
- Cloud Storage (3 buckets)
- Vertex AI Search datastore
- Next.js frontend (becomes secondary analytics view)
- Existing 126 tests

### 7.4 New Scripts

| Script | Purpose |
|--------|---------|
| `corpus/scripts/seed_regulation_graph.py` | Reads existing 69 regulation chunks, extracts relationships, seeds Spanner Graph nodes/edges |

## 8. Testing

~20 new tests in `services/gemini-agent/tests/`:

| Test file | Count | What it tests |
|-----------|-------|--------------|
| `test_webhook.py` | 3 | Health endpoint, webhook routing, auth rejection |
| `test_upload_tool.py` | 4 | File upload, polling loop, timeout fallback, Gate 1 sync flow |
| `test_review_tools.py` | 4 | Queue fetch, review detail, decision submit, role filtering |
| `test_rag_orchestrator.py` | 5 | Vector-only, graph-only, combined retrieval, re-ranking, authority resolution |
| `test_graph_client.py` | 2 | Spanner implementation, Neo4j implementation (mocked) |
| `test_formatting.py` | 3 | Scorecard formatting, extraction formatting, regulation formatting |

Total: ~21 tests. Existing 126 tests untouched. Target: 147 total.

## 9. Deployment Sequence

1. Deploy Spanner Graph instance + seed regulation data
2. Deploy `ancol-gemini-agent` Cloud Run service
3. Create Agent Builder agent with tool definitions + system prompt
4. Configure Gemini Enterprise to surface the agent
5. Test end-to-end: upload → extraction → Gate 1 → async Gates 2-4 → report

## 10. What the Next.js Frontend Becomes

The Next.js frontend is NOT removed. It becomes the **analytics and visualization companion**:
- Compliance trend charts (6-month line charts)
- Violation heatmaps
- Batch processing progress bars with auto-refresh
- Document archive browser
- Audit trail viewer

These are better as visual dashboards than chat responses. The agent can link to specific dashboard pages when relevant: "Lihat tren lengkap di dashboard: [link]".
