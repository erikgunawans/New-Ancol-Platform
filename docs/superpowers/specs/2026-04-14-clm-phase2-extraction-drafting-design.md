# CLM Phase 2: Contract Extraction + Smart Drafting

## Context

Phase 1 delivered the CLM data model (6 tables, 18 API endpoints, 8 Gemini tools) and Phase 1 gap closure added RBAC enforcement + obligation auto-transition. The infrastructure is complete but the AI features are stubs. Phase 2 fills the two highest-impact gaps: (1) AI-powered extraction of clauses and risk from uploaded contracts, and (2) smart drafting that assembles contracts from pre-approved clause libraries with minimal Gemini usage.

**User decisions:**
- Scope: Extraction + Drafting only (Q&A + obligation extraction → Phase 3)
- Extraction: Extend existing extraction-agent (no new service)
- Drafting: Template fill + AI review (grounded in clause library, minimal hallucination)
- Clause library: JSON corpus file + loader script
- HITL: Zero gates for extraction, one gate for drafting

**Design spec will be committed to:** `docs/superpowers/specs/2026-04-14-clm-phase2-extraction-drafting-design.md`

---

## Sub-project A: Contract Extraction Pipeline

### A1. Message Routing in extraction-agent

**File:** `services/extraction-agent/src/extraction_agent/main.py`

Add a new endpoint `POST /extract-contract` for contract Pub/Sub messages. The existing `POST /extract` continues to handle MoM messages unchanged.

```python
@app.post("/extract-contract")
async def handle_contract_pubsub_push(request: Request):
    # Decode Pub/Sub message
    # Extract contract_id, gcs_raw_uri from payload
    # Load raw file from GCS
    # Call Document AI for OCR (reuse _load_ocr_output pattern)
    # Call contract_parser.extract_contract()
    # Store ContractClauseRecord rows + ContractPartyRecord rows
    # Update Contract.extraction_data, risk_level, risk_score
    # No HITL gate transition — contract stays in draft
    # Publish "contract-extracted" event
```

The `contract-uploaded` Pub/Sub subscription push endpoint should point to `/extract-contract` in the Terraform config.

### A2. Contract Parser Module

**File:** `services/extraction-agent/src/extraction_agent/contract_parser.py` (NEW)

```python
async def extract_contract(ocr_text: str, contract_type: str) -> ContractExtractionOutput:
    """Parse contract OCR text into structured clauses with risk scoring."""
```

Uses Gemini 2.5 Pro via existing `ancol_common.gemini.client` factory. Sends OCR text + contract type + system prompt → gets structured JSON matching `ContractExtractionOutput` schema.

**Risk scoring logic:**
- HIGH: Missing standard protections (no indemnification, no termination clause, unlimited liability), unfavorable terms (auto-renewal without notice, unilateral amendment rights)
- MEDIUM: Non-standard terms that deviate from clause library templates, ambiguous language
- LOW: Standard clauses matching library templates

**Output mapping:**
- `ContractExtractionOutput.clauses` → stored as `ContractClauseRecord` rows
- `ContractExtractionOutput.parties` → stored as `ContractPartyRecord` rows  
- `ContractExtractionOutput.key_dates` → updates `Contract.effective_date`, `Contract.expiry_date`
- `ContractExtractionOutput.financial_terms` → updates `Contract.total_value`, `Contract.currency`
- `ContractExtractionOutput.risk_summary` → updates `Contract.risk_level`, `Contract.risk_score`
- Full output → stored in `Contract.extraction_data` JSONB

### A3. Gemini Prompt for Contract Extraction

**File:** `services/extraction-agent/src/extraction_agent/prompts/contract_system.py` (NEW)

System prompt instructs Gemini to:
1. Identify all parties (name, role, entity type)
2. Extract every clause with number, title, full text, category
3. Identify key dates (effective, expiry, renewal deadlines)
4. Extract financial terms (value, currency, payment schedule)
5. Score each clause risk: HIGH/MEDIUM/LOW with reason
6. Output as JSON matching `ContractExtractionOutput` schema
7. All text in original language (Bahasa Indonesia or English as-found)

Model: Gemini 2.5 Pro (precision matters for legal extraction)
Temperature: 0.1 (near-deterministic for structured extraction)
Response format: JSON mode with schema enforcement

### A4. Pub/Sub + Terraform Wiring

**File:** `infra/modules/pubsub/main.tf` — Verify `contract-uploaded` topic has a push subscription pointing to extraction-agent's `/extract-contract` endpoint.

**File:** `infra/environments/dev/main.tf` — Add push endpoint mapping if missing.

### A5. Repository Functions

**File:** `packages/ancol-common/src/ancol_common/db/repository.py`

Add:
```python
async def store_contract_extraction(
    session: AsyncSession,
    contract_id: str,
    extraction: ContractExtractionOutput,
) -> None:
    """Store extraction results: clauses, parties, metadata updates."""
```

This function:
1. Bulk-inserts `ContractClauseRecord` rows from `extraction.clauses`
2. Bulk-inserts `ContractPartyRecord` rows from `extraction.parties`
3. Updates `Contract` fields: `extraction_data`, `risk_level`, `risk_score`, `effective_date`, `expiry_date`, `total_value`, `currency`

### A6. Tests

**File:** `services/extraction-agent/tests/test_contract_parser.py` (NEW, ~10 tests)

1. Basic clause extraction from sample vendor contract text
2. Party identification (principal + counterparty)
3. Risk scoring: HIGH for missing indemnification clause
4. Risk scoring: LOW for standard confidentiality clause
5. Key date extraction (effective + expiry)
6. Financial term extraction (value + currency)
7. Multi-clause contract with mixed risk levels
8. Edge case: contract with no explicit clause numbering
9. Edge case: bilingual contract (mixed ID/EN text)
10. Malformed input (empty text) returns empty extraction

---

## Sub-project B: Clause Library Seeding

### B1. JSON Corpus File

**File:** `corpus/data/clause_library.json` (NEW)

Array of ~50-70 clause objects covering 7 contract types:

| Contract Type | Clauses | Key Categories |
|---------------|---------|----------------|
| NDA | 8 | confidentiality, term, breach, return_materials, non_solicitation, injunctive_relief, governing_law, dispute_resolution |
| Vendor | 10 | scope, payment_terms, warranty, termination, liability, indemnification, audit_rights, confidentiality, force_majeure, governing_law |
| Sale-Purchase | 8 | price, delivery, inspection, warranty, title_transfer, force_majeure, governing_law, dispute_resolution |
| Joint Venture | 10 | purpose, governance, capital_contribution, profit_sharing, management, exit, intellectual_property, confidentiality, dispute_resolution, dissolution |
| Land Lease | 8 | premises, rent, duration, maintenance, improvements, renewal, termination, governing_law |
| Employment | 8 | duties, compensation, benefits, termination, non_compete, confidentiality, intellectual_property, governing_law |
| Board Resolution | 6 | quorum, voting, abstention, minutes, amendments, governing_law |

Each clause entry:
```json
{
  "contract_type": "vendor",
  "clause_category": "payment_terms",
  "title_id": "Ketentuan Pembayaran",
  "title_en": "Payment Terms",
  "text_id": "Pembayaran akan dilakukan dalam waktu ...",
  "text_en": "Payment shall be made within ...",
  "risk_notes": "Verify payment timeline aligns with company cash flow cycle",
  "is_mandatory": true,
  "version": 1
}
```

### B2. Loader Script

**File:** `scripts/seed_clause_library.py` (NEW)

Reads `corpus/data/clause_library.json`, upserts into `ClauseLibrary` table. Idempotent — uses `(contract_type, clause_category, version)` as natural key. Skips rows that already exist with same version.

```bash
PYTHONPATH=packages/ancol-common/src python3 scripts/seed_clause_library.py
```

### B3. Contract Template Seeding

The `ContractTemplate` table also needs seed data with `required_clauses` and `optional_clauses` JSONB referencing clause categories. Add template entries to the same loader or a separate `seed_contract_templates.py` script.

Each template defines:
```json
{
  "name": "Standard Vendor Agreement",
  "contract_type": "vendor",
  "required_clauses": ["scope", "payment_terms", "warranty", "termination", "governing_law"],
  "optional_clauses": ["audit_rights", "indemnification", "force_majeure", "confidentiality", "liability"],
  "default_terms": {"payment_days": 30, "warranty_months": 12, "notice_days": 30}
}
```

---

## Sub-project C: Smart Drafting Agent

### C1. Draft Assembly Engine

**File:** `packages/ancol-common/src/ancol_common/drafting/engine.py` (NEW)

```python
async def assemble_draft(
    session: AsyncSession,
    request: DraftRequest,
) -> DraftOutput:
    """Assemble a contract draft from template + clause library + AI review."""
```

**Three phases:**

**Phase 1 — Template + Clause lookup:**
- Query `ContractTemplate` for the requested `contract_type`
- For each required clause category, query `ClauseLibrary` for the latest active clause
- For each optional clause, prepare for AI recommendation

**Phase 2 — Variable substitution:**
- Replace placeholders in clause text with actual party names, dates, values from `DraftRequest.key_terms`
- Placeholder format: `{{party_principal}}`, `{{effective_date}}`, `{{total_value}}`, etc.
- For `clause_overrides` in the request, use the override text instead of library text

**Phase 3 — AI enhancement (single Gemini call):**
- Input: assembled required clauses + list of available optional clauses + contract context
- Gemini recommends: which optional clauses to include (with reasoning), any consistency issues in the assembled text
- Model: Gemini 2.5 Flash (fast, low cost — this is recommendation, not extraction)
- Temperature: 0.3 (some creativity for recommendations)

**Output:**
- `DraftOutput.draft_text`: Full assembled contract in Bahasa Indonesia (or English per request language)
- `DraftOutput.clauses`: List of clauses used with `is_from_library=True` and `library_clause_id` references
- `DraftOutput.risk_assessment`: Per-clause risk notes from the library
- `DraftOutput.gcs_draft_uri`: After storing to GCS

### C2. Wire Drafting Endpoint

**File:** `services/api-gateway/src/api_gateway/routers/drafting.py`

Replace the `generate_draft` stub (lines 106-124) with:
1. Parse `DraftRequest` from request body
2. Call `assemble_draft(session, request)`
3. Store draft text to GCS: `gs://ancol-contracts/drafts/{contract_id}/draft-v1.md`
4. Create `Contract` record with status `draft`, `template_id`, `gcs_draft_uri`
5. Create `ContractClauseRecord` rows with `is_from_library=True`
6. Return `DraftOutput`

### C3. Wire Gemini Tool Handler

**File:** `services/gemini-agent/src/gemini_agent/tools/drafting.py`

The handler already calls `api.generate_draft(body)` and formats with `format_draft_output()`. Once the API endpoint returns real data, this handler works as-is. May need minor adjustments to the response format.

### C4. Gemini Prompt for Draft Enhancement

**File:** `packages/ancol-common/src/ancol_common/drafting/prompts.py` (NEW)

System prompt for the draft enhancement call:
- Context: contract type, parties, required clauses already assembled
- Task: recommend optional clauses, check consistency
- Output format: JSON with `recommended_optional_clauses: [{"category": ..., "reason": ...}]` and `consistency_notes: [{"issue": ..., "suggestion": ...}]`
- Language: respond in same language as the draft

### C5. GCS Storage

Store drafts in the existing contracts bucket: `gs://{bucket_contracts}/drafts/{contract_id}/draft-v{version}.md`

Use `get_gcs_client()` singleton from `utils.py`.

### C6. Tests

**File:** `services/api-gateway/tests/test_drafting_engine.py` (NEW, ~8 tests)

1. Template lookup finds correct template for contract type
2. Required clauses assembled from library
3. Variable substitution replaces placeholders
4. Missing clause library entry raises appropriate error
5. Clause override replaces library clause
6. Draft output contains all required clauses
7. GCS URI format is correct
8. Empty key_terms still produces valid draft

---

## Verification

```bash
# Lint
ruff check packages/ services/ scripts/ corpus/scripts/
ruff format --check packages/ services/ scripts/ corpus/scripts/

# Extraction agent tests
PYTHONPATH=packages/ancol-common/src:services/extraction-agent/src python3 -m pytest services/extraction-agent/tests/ -v

# API gateway tests (includes drafting engine)
PYTHONPATH=packages/ancol-common/src:services/api-gateway/src python3 -m pytest services/api-gateway/tests/ -v

# Clause library loader
PYTHONPATH=packages/ancol-common/src python3 scripts/seed_clause_library.py --dry-run

# Smoke: import new modules
PYTHONPATH=packages/ancol-common/src python3 -c "from ancol_common.drafting.engine import assemble_draft; print('OK')"
PYTHONPATH=packages/ancol-common/src:services/extraction-agent/src python3 -c "from extraction_agent.contract_parser import extract_contract; print('OK')"

# Full test suite
for svc in extraction-agent legal-research-agent comparison-agent reporting-agent api-gateway batch-engine email-ingest regulation-monitor gemini-agent; do
  PYTHONPATH=packages/ancol-common/src:services/$svc/src python3 -m pytest services/$svc/tests/ -q
done
```

---

## Execution Order

```
Sub-project B (Clause Library):  B1 → B2 → B3           [no dependencies]
Sub-project A (Extraction):      A3 → A2 → A5 → A1 → A4 → A6
Sub-project C (Drafting):        C4 → C1 → C2 → C3 → C5 → C6  [depends on B]
```

B and A can run in parallel. C depends on B (needs clause library seeded).

---

## Files Summary

| Status | File | Description |
|--------|------|-------------|
| NEW | `services/extraction-agent/src/extraction_agent/contract_parser.py` | Contract clause extraction logic |
| NEW | `services/extraction-agent/src/extraction_agent/prompts/contract_system.py` | Gemini prompt for extraction |
| NEW | `services/extraction-agent/tests/test_contract_parser.py` | ~10 extraction tests |
| NEW | `corpus/data/clause_library.json` | 50-70 pre-approved clauses |
| NEW | `scripts/seed_clause_library.py` | JSON → DB loader |
| NEW | `packages/ancol-common/src/ancol_common/drafting/engine.py` | Draft assembly engine |
| NEW | `packages/ancol-common/src/ancol_common/drafting/prompts.py` | Gemini prompt for draft enhancement |
| NEW | `packages/ancol-common/src/ancol_common/drafting/__init__.py` | Package init |
| NEW | `services/api-gateway/tests/test_drafting_engine.py` | ~8 drafting tests |
| MODIFY | `services/extraction-agent/src/extraction_agent/main.py` | Add /extract-contract endpoint |
| MODIFY | `services/api-gateway/src/api_gateway/routers/drafting.py` | Wire generate endpoint |
| MODIFY | `packages/ancol-common/src/ancol_common/db/repository.py` | Add store_contract_extraction, clause library queries |
| MODIFY | `PROGRESS.md` | Session entry |
| MODIFY | `CLAUDE.md` | Update test counts |

---

## Out of Scope (Phase 3)

- Contract Q&A RAG (3-layer hybrid search)
- Obligation auto-extraction from contract clauses
- Contract-to-regulation graph edges in Spanner
- PDF generation of drafts (drafts are markdown for now)
- Vertex AI Search indexing of contract text
- User model phone field + WhatsApp delivery

---

## Plan Verification Protocol

```
Confidence: 95%
Verification passes: 2

Pass 1:
- Confirmed ContractExtractionOutput schema exists with correct fields
- Confirmed ContractClauseRecord has library_clause_id FK to clause_library
- Confirmed Contract model has extraction_data JSONB, risk_level, risk_score fields
- Confirmed extraction-agent main.py pattern (Pub/Sub decode → process → store → publish)
- Confirmed DraftRequest/DraftOutput schemas exist with correct structure
- Confirmed gemini-agent drafting tool already calls api.generate_draft()

Pass 2:
- Verified ContractTemplate has required_clauses/optional_clauses JSONB fields
- Verified ClauseLibrary model has contract_type, clause_category, version, is_active fields
- Verified Contract.gcs_draft_uri field exists for storing draft location
- Verified existing _load_ocr_output helper can be reused for contract OCR loading
- Noted: contract-uploaded Pub/Sub topic already wired in contracts.py upload endpoint
```
