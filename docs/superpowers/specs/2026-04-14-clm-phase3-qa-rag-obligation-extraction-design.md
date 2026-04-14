# CLM Phase 3: Contract Q&A RAG + Obligation Auto-Extraction

**Date:** 2026-04-14
**Status:** Approved
**Depends on:** Phase 2 (contract extraction pipeline + smart drafting)

---

## 1. Problem Statement

Phase 2 delivered contract extraction and smart drafting, but two critical gaps remain:

1. **No contract Q&A.** Users can't ask natural-language questions about their contracts. The `handle_ask_contract_question` Gemini tool returns a Phase 2 stub. PJAA's #1 survey pain point was institutional knowledge loss — people leave, and contract knowledge leaves with them.

2. **No obligation auto-extraction.** When contracts are extracted, obligations (renewal dates, payment deadlines, reporting cadences) are not identified. Users must manually create obligation records. This means the obligation tracker (with auto-transition + WhatsApp reminders) sits empty for uploaded contracts.

---

## 2. User Decisions

- **Scope:** Both Q&A RAG and obligation extraction in one phase
- **Vector search:** Full Vertex AI Search integration (not PostgreSQL full-text)
- **Graph:** Both contract-regulation and contract-contract edges in Spanner Graph
- **Obligation extraction:** Inline with contract extraction (same Gemini call, same transaction)

---

## 3. Architecture

Three workstreams sharing the extraction pipeline:

```
Contract Upload → extraction-agent
  ├─ Gemini 2.5 Pro extraction (enhanced prompt)
  │   ├─ Clauses + risk scoring (existing)
  │   ├─ Obligations (new: renewal, payment, reporting, etc.)
  │   └─ Applicable regulations (new: UUPT, POJK, etc.)
  │
  ├─ Store in Cloud SQL (existing + obligations)
  ├─ Index in Vertex AI Search (new)
  └─ Seed Spanner Graph edges (new)

User Q&A → gemini-agent/contract_qa tool
  ├─ Layer 1: Vertex AI Search (semantic clause search)
  ├─ Layer 2: Spanner Graph (expand: contract↔regulation, contract↔contract)
  ├─ Layer 3: Cloud SQL (exact contract/clause lookup)
  ├─ Re-rank (direct clauses > related > regulations)
  └─ Gemini synthesize answer (Bahasa Indonesia + citations)
```

---

## 4. Workstream 1: Vertex AI Search Indexing

### 4.1 Terraform

**File:** `infra/modules/vertex-search/main.tf` (extend existing or create)

New Vertex AI Search datastore:
- Name: `ancol-contract-clauses`
- Type: unstructured documents
- Region: `asia-southeast2` (Jakarta, data sovereignty)
- Solution type: `SOLUTION_TYPE_SEARCH`

If the module already exists for MoM, add a second datastore resource. If not, create the module with both datastores.

**Variables:** datastore name, project_id, region (reuse existing patterns from other infra modules).

### 4.2 Contract Clause Indexer

**File:** `packages/ancol-common/src/ancol_common/search/contract_indexer.py` (NEW)

```python
async def index_contract_clauses(
    contract_id: str,
    clauses: list[dict],
    contract_type: str,
    contract_title: str,
) -> int:
    """Index extracted clauses into Vertex AI Search. Returns count indexed."""
```

Each clause becomes one document in the datastore:
```json
{
  "id": "{contract_id}_{clause_number}",
  "content": "{clause_text}",
  "structData": {
    "contract_id": "uuid",
    "contract_title": "Perjanjian Vendor PT XYZ",
    "contract_type": "vendor",
    "clause_number": "Pasal 3",
    "clause_category": "payment_terms",
    "risk_level": "low",
    "title": "Ketentuan Pembayaran"
  }
}
```

Uses the `discoveryengine` client from `google-cloud-discoveryengine` SDK. Import pattern follows existing Vertex AI Search usage in the MoM RAG system (`gemini-agent/src/gemini_agent/rag/`).

**Package init:** `packages/ancol-common/src/ancol_common/search/__init__.py` (NEW)

### 4.3 Integration Point

**File:** `services/extraction-agent/src/extraction_agent/main.py`

After `store_contract_extraction()` succeeds in `handle_contract_pubsub_push`, call:
```python
from ancol_common.search.contract_indexer import index_contract_clauses

indexed = await index_contract_clauses(
    contract_id=contract_id,
    clauses=[c.model_dump() for c in result.clauses],
    contract_type=contract_type,
    contract_title=result.key_dates.get("title", ""),
)
```

Indexing failure should log a warning but not fail the extraction (best-effort).

---

## 5. Workstream 2: Obligation Auto-Extraction

### 5.1 Enhanced Extraction Prompt

**File:** `services/extraction-agent/src/extraction_agent/prompts/contract_system.py`

Add to the extraction system prompt output schema:

```json
"obligations": [
  {
    "obligation_type": "renewal|reporting|payment|termination_notice|deliverable|compliance_filing",
    "description": "string",
    "due_date": "YYYY-MM-DD|null",
    "recurrence": "monthly|quarterly|annual|null",
    "responsible_party": "string"
  }
],
"applicable_regulations": [
  {
    "regulation_id": "string (e.g., 'UUPT 40/2007', 'POJK 23/2023')",
    "relevance": "string (brief explanation of why this regulation applies)"
  }
]
```

Prompt instructions for obligation detection:
- Scan for renewal clauses → extract opt-out deadline as `due_date`, set `recurrence` if recurring
- Scan for payment terms → extract first payment date, set `recurrence` based on schedule
- Scan for reporting requirements → extract deadline, set `recurrence`
- Scan for termination notice periods → compute `due_date` from expiry minus notice period
- Scan for deliverable deadlines → extract each as a separate obligation
- If date cannot be determined from text, set `due_date` to null

Prompt instructions for regulation identification:
- Identify Indonesian laws and regulations referenced in the contract text
- Also identify regulations that should apply based on contract type and parties (e.g., UUPT for any PT, POJK for public companies, UU Ketenagakerjaan for employment contracts)
- Use standard identifiers: "UU [number]/[year]", "POJK [number]/[year]", "PP [number]/[year]"

### 5.2 Schema Update

**File:** `packages/ancol-common/src/ancol_common/schemas/contract.py`

Add to `ContractExtractionOutput`:
```python
class ExtractedObligation(BaseModel):
    obligation_type: str  # matches ObligationType values
    description: str
    due_date: date | None = None
    recurrence: str | None = None  # monthly, quarterly, annual
    responsible_party: str

class ApplicableRegulation(BaseModel):
    regulation_id: str
    relevance: str

class ContractExtractionOutput(BaseModel):
    # ... existing fields ...
    obligations: list[ExtractedObligation] = []
    applicable_regulations: list[ApplicableRegulation] = []
```

### 5.3 Contract Parser Update

**File:** `services/extraction-agent/src/extraction_agent/contract_parser.py`

Parse `obligations` and `applicable_regulations` from Gemini response, map to new schema classes.

### 5.4 Repository Update

**File:** `packages/ancol-common/src/ancol_common/db/repository.py`

Extend `store_contract_extraction()` to:
1. Create `ObligationRecord` rows from `extraction.obligations` using existing `create_obligation()` pattern
2. Set `responsible_party_name` from the extracted party name
3. Compute `responsible_user_id` if party name matches a known user (best-effort lookup)

### 5.5 Tests

**File:** `services/extraction-agent/tests/test_obligation_extraction.py` (NEW, ~6 tests)

1. Renewal obligation extracted from contract with renewal clause
2. Payment obligation with recurrence detected
3. No obligations from simple NDA (no financial terms)
4. Multiple obligations from complex vendor contract
5. Due date computation from termination notice period
6. Obligation type mapping to correct ObligationType values

---

## 6. Workstream 3: Contract Q&A RAG

### 6.1 RAG Orchestrator

**File:** `services/gemini-agent/src/gemini_agent/rag/contract_rag.py` (NEW)

```python
async def answer_contract_question(
    question: str,
    contract_id: str | None,
    api: ApiClient,
) -> dict:
    """3-layer RAG for contract Q&A. Returns answer + citations."""
```

**Layer 1 — Vertex AI Search:**
```python
from ancol_common.gemini.grounding import search_vertex_ai

results = await search_vertex_ai(
    query=question,
    datastore="ancol-contract-clauses",
    top_k=10,
)
```

Uses existing `search_vertex_ai` helper from `ancol_common.gemini.grounding` (already used by MoM RAG). If the function needs a datastore parameter, extend it.

**Layer 2 — Spanner Graph:**
For each clause hit from Layer 1, expand relationships:
```python
from gemini_agent.rag.graph_client import get_graph_client

graph = get_graph_client()
# Get contract-regulation edges
regulations = await graph.get_related_regulations(contract_id)
# Get contract-contract edges (amendments, renewals)
related_contracts = await graph.get_related_contracts(contract_id)
```

Extend `GraphClient` interface with two new methods:
- `get_related_regulations(contract_id) -> list[dict]`
- `get_related_contracts(contract_id) -> list[dict]`

**Layer 3 — Cloud SQL:**
If `contract_id` is provided, fetch the full contract + all clauses directly:
```python
contract = await api.get_contract(contract_id)
clauses = await api.get_contract_clauses(contract_id)
```

**Re-ranking:**
Combine results from all 3 layers. Priority:
1. Direct clause matches (from the specified contract, if any)
2. Semantic matches from Vertex AI Search
3. Related contract clauses (from graph expansion)
4. Regulation references (from graph)

Deduplicate by clause ID. Limit to top 15 chunks for Gemini context.

**Gemini synthesis:**
Send the re-ranked chunks + user question to Gemini 2.5 Pro. System prompt instructs:
- Answer in Bahasa Indonesia with English legal terms
- Cite specific clause numbers and contract titles
- If uncertain, say so explicitly
- Do not hallucinate or infer beyond the provided context

### 6.2 Wire the Stub

**File:** `services/gemini-agent/src/gemini_agent/tools/contract_qa.py`

Replace the Phase 2 stub with:
```python
from gemini_agent.rag.contract_rag import answer_contract_question

async def handle_ask_contract_question(params, api, user):
    question = params.get("question", "")
    contract_id = params.get("contract_id")

    if not question:
        return "Error: Mohon berikan pertanyaan Anda."

    result = await answer_contract_question(question, contract_id, api)
    return format_contract_qa_response(result)
```

### 6.3 Response Formatter

**File:** `services/gemini-agent/src/gemini_agent/formatting.py`

Add `format_contract_qa_response(result: dict) -> str`:

Output format:
```
**Jawaban:**
{answer text}

**Sumber:**
- {contract_title}, {clause_number}: "{clause_excerpt}" (risiko: {risk_level})
- {regulation_id}: {relevance}

**Kontrak Terkait:**
- {related_contract_title} ({relationship_type})
```

### 6.4 Graph Seeding for Contracts

**File:** `packages/ancol-common/src/ancol_common/search/graph_seeder.py` (NEW)

```python
async def seed_contract_graph(
    contract_id: str,
    contract_type: str,
    contract_title: str,
    parent_contract_id: str | None,
    applicable_regulations: list[dict],
) -> dict:
    """Create Spanner Graph nodes and edges for a contract."""
```

Creates:
- Contract node: `(contract_id, title, type, status)`
- Contract→Regulation edges: for each applicable regulation identified by Gemini
- Contract→Contract edges: if `parent_contract_id` is set (amendment/renewal chain)

**Integration:** Called from `handle_contract_pubsub_push` after `store_contract_extraction()`, alongside indexing. Best-effort (log warning on failure).

### 6.5 GraphClient Extension

**File:** `services/gemini-agent/src/gemini_agent/rag/graph_client.py`

Add two abstract methods:
```python
async def get_related_regulations(self, contract_id: str) -> list[dict]
async def get_related_contracts(self, contract_id: str) -> list[dict]
```

Implement in both `SpannerGraphClient` and `Neo4jGraphClient` (or stub the Neo4j one).

### 6.6 Tests

**File:** `services/gemini-agent/tests/test_contract_qa.py` (NEW, ~8 tests)

1. Basic question returns answer with citations
2. Contract-specific question fetches clauses from DB
3. Empty question returns error message
4. No search results returns "information not found" response
5. Regulation references included in response
6. Related contracts from graph expansion included
7. Response is in Bahasa Indonesia
8. Citations reference specific clause numbers

---

## 7. Execution Order

```
Step 1 (parallel, no deps):
  - 4.1 Terraform (Vertex AI Search datastore)
  - 5.1 Enhanced extraction prompt
  - 5.2 Schema update (ExtractedObligation, ApplicableRegulation)

Step 2 (depends on Step 1):
  - 4.2 Contract clause indexer
  - 5.3 Contract parser update
  - 5.4 Repository update (obligations + graph seeding call)
  - 6.4 Graph seeder
  - 6.5 GraphClient extension

Step 3 (depends on Step 2):
  - 4.3 Integration (indexing in extraction pipeline)
  - 6.1 RAG orchestrator
  - 6.2 Wire contract_qa stub
  - 6.3 Response formatter

Step 4 (depends on Step 3):
  - 5.5 Obligation extraction tests
  - 6.6 Q&A RAG tests

Step 5:
  - Verification (lint, full test suite)
  - Docs update
```

---

## 8. Files Summary

| Status | File | Description |
|--------|------|-------------|
| NEW | `infra/modules/vertex-search/contracts.tf` | Terraform for contracts search datastore |
| NEW | `packages/ancol-common/src/ancol_common/search/__init__.py` | Search package init |
| NEW | `packages/ancol-common/src/ancol_common/search/contract_indexer.py` | Vertex AI Search indexing |
| NEW | `packages/ancol-common/src/ancol_common/search/graph_seeder.py` | Spanner Graph node/edge creation |
| NEW | `services/gemini-agent/src/gemini_agent/rag/contract_rag.py` | 3-layer RAG orchestrator |
| NEW | `services/extraction-agent/tests/test_obligation_extraction.py` | ~6 obligation extraction tests |
| NEW | `services/gemini-agent/tests/test_contract_qa.py` | ~8 Q&A RAG tests |
| MODIFY | `packages/ancol-common/src/ancol_common/schemas/contract.py` | Add ExtractedObligation, ApplicableRegulation |
| MODIFY | `services/extraction-agent/src/extraction_agent/prompts/contract_system.py` | Add obligations + regulations |
| MODIFY | `services/extraction-agent/src/extraction_agent/contract_parser.py` | Parse obligations + regulations |
| MODIFY | `packages/ancol-common/src/ancol_common/db/repository.py` | Obligation creation + graph seeding |
| MODIFY | `services/extraction-agent/src/extraction_agent/main.py` | Add indexing + graph seeding calls |
| MODIFY | `services/gemini-agent/src/gemini_agent/tools/contract_qa.py` | Replace stub with RAG |
| MODIFY | `services/gemini-agent/src/gemini_agent/formatting.py` | Add format_contract_qa_response |
| MODIFY | `services/gemini-agent/src/gemini_agent/rag/graph_client.py` | Add contract graph methods |
| MODIFY | `PROGRESS.md` | Session entry |
| MODIFY | `CLAUDE.md` | Update test counts, current state |

---

## 9. Out of Scope (Phase 4+)

- PDF generation of drafted contracts
- PWA manifest + push notifications
- MFA
- Per-gate HITL role enforcement
- User model phone field + WhatsApp delivery
- Neo4j AuraDS implementation of contract graph methods (stub only)
