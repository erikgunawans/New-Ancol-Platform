# Agentic AI MoM Compliance System — Design Specification

**Project:** PT Pembangunan Jaya Ancol Tbk — Board of Directors MoM Audit System
**Platform:** Google Cloud Platform (Gemini Enterprise)
**Architecture:** Multi-Agent + Human-in-the-Loop Gates
**Date:** 2026-04-08

---

## 1. Problem Statement

PT Pembangunan Jaya Ancol Tbk requires a system to audit Board of Directors (BoD) Minutes of Meetings (MoM) against structural compliance standards, substantive consistency, and regulatory alignment. The company has 5+ years of historical MoMs in mixed formats (scans, PDFs, Word documents) and a regulatory corpus scattered across physical copies, shared drives, and document management systems. The audit must cover both internal regulations (AD/ART, Board Charters, SOPs) and external regulations (OJK, UU PT, IDX, industry-specific).

## 2. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | Multi-Agent + HITL | Compliance findings must have human sign-off. Fully automated audit is a liability for a Tbk company. |
| Cloud | GCP (greenfield) | This project drives GCP adoption. Gemini Enterprise is the AI backbone. |
| Region | asia-southeast2 (Jakarta) | Data sovereignty. BoD-level data must not leave Indonesia. |
| Integration | Phased (standalone MVP → progressive) | De-risks GCP adoption. Proves value before complex integrations. |
| Language | Bahasa Indonesia primary + English legal terms | Gemini 2.5 handles Bahasa well. Bilingual NER required. |
| Agents | 4 specialized (Extraction, Legal Research, Comparison, Reporting) | Each independently scalable, testable, and auditable. |
| HITL | Gates at every stage | No compliance finding reaches the Board without human approval. |
| Models | Flash for parsing/reporting, Pro for legal reasoning/comparison | Cost-optimized: Flash is 5x cheaper for structured tasks; Pro needed for chain-of-thought reasoning. |

## 3. System Architecture

### 3.1 Layer 0: Document Ingestion & Pre-Processing

**Google Document AI** handles all document format normalization before agents process content.

Components:
- **Upload Portal**: Drag-and-drop + bulk upload UI for Corporate Secretary. Phase 5 adds email auto-ingest.
- **Document AI Processor**: OCR engine, layout parser, table extractor, handwriting recognition. Configured with custom model trained on 10-20 sample MoMs.
- **Cloud Storage**: Raw documents in `ancol-mom-raw/`, processed output in `ancol-mom-processed/`.
- **MoM Template Registry**: Versioned templates with effective date ranges. Defines required fields, meeting protocols, and valid format variations per era.

Processing flow:
1. Document uploaded to Cloud Storage
2. Cloud Storage event triggers Document AI processing
3. Document AI outputs: OCR text, layout map, extracted tables, per-page confidence scores
4. Pages below 70% confidence auto-flagged; documents below 60% overall are rejected with rescan request
5. Output stored in `ancol-mom-processed/` and Pub/Sub message published to `mom.uploaded`

### 3.2 Layer 1: Presentation (Role-Based UIs)

Single Next.js 15 application on Cloud Run with four role-specific views, protected by Identity-Aware Proxy (IAP) and Cloud Identity SSO.

**Roles and views:**

| Role | View | Capabilities |
|------|------|-------------|
| Corporate Secretary (`corp_secretary`) | Upload & Track | Upload MoMs (single/bulk), track processing status, review extractions (HITL Gate 1), approve final reports (Gate 4 co-sign) |
| Internal Auditor (`internal_auditor`) | Review Queue | HITL review queue (Gates 2-3), approve/reject/modify findings, annotate with notes, sign off on reports (Gate 4 co-sign) |
| Komisaris (`komisaris`) | Dashboard | Compliance scorecard (3 pillars), trend charts (6/12 month), board-pack PDF download, read-only access to approved reports |
| Legal & Compliance (`legal_compliance`) | Regulatory Mapper | Corpus explorer (search regulations), clause mapping per MoM, regulatory version timeline, review regulatory mapping (HITL Gate 2) |

**Shared components:**
- Immutable audit trail viewer (who did what, when)
- Document archive browser
- Notification center (in-app)
- Confidential section handling (RBAC-controlled visibility)

**Supporting services:**
- **Notification Service**: Email via SendGrid, in-app notifications, SLA tracking with 48h escalation to reviewer's manager
- **WebSocket**: Live status updates during processing

### 3.3 Layer 2: Orchestration & Agents

#### 3.3.1 Workflow Orchestrator

**Cloud Workflows** manages the agent pipeline with two modes:

- **Real-time mode**: Single MoM, sequential agent processing with HITL gates
- **Batch mode**: Historical backlog, parallel processing via Cloud Batch (10-50 concurrent documents)

**Cloud Pub/Sub Event Bus** (8 topics + DLQ per topic):
- `mom.uploaded` — Document AI complete, ready for extraction
- `mom.extracted` — Extraction complete, pending HITL Gate 1
- `mom.researched` — Legal research complete, pending HITL Gate 2
- `mom.compared` — Comparison complete, pending HITL Gate 3
- `mom.reported` — Report generated, pending HITL Gate 4
- `hitl.pending` — New item awaiting human review
- `hitl.decided` — Human decision made, resume pipeline
- `batch.progress` — Batch processing status updates

**Per-document state machine** (Cloud SQL):
`pending → extracting → hitl_gate_1 → researching → hitl_gate_2 → comparing → hitl_gate_3 → reporting → hitl_gate_4 → complete | failed`

#### 3.3.2 Agent 1: Extraction Agent

- **Runtime**: Cloud Run
- **Model**: Gemini 2.5 Flash
- **Input**: Document AI output (OCR text + layout map + tables) + MoM Template Registry rules
- **Processing**:
  1. Structural parsing — identify sections (header, agenda, attendees, discussions, resolutions, signatures)
  2. Bilingual entity extraction — directors (with titles), dates, financial figures, resolution text, cross-references to prior MoMs
  3. Substantive structuring — parse "Result of the Month" into performance data JSON, parse "Result of the Meeting" into resolution array, link agenda → discussion → resolution
  4. Structural compliance check — validate against template, check quorum, verify signatures, flag missing required fields
- **Output**: Structured MoM JSON, structural compliance sub-score, per-field confidence scores, deviation flags
- **HITL Gate 1**: Corporate Secretary reviews. Low-confidence extractions (<80%) are auto-flagged for mandatory review.

#### 3.3.3 Agent 2: Legal Research Agent

- **Runtime**: Cloud Run
- **Model**: Gemini 2.5 Pro + Vertex AI Search (RAG)
- **Input**: Approved structured MoM JSON + meeting date
- **Processing**:
  1. Topic classification — classify each resolution by regulatory domain (corporate governance, finance, property, tourism, related-party transactions, capital markets)
  2. Time-aware RAG retrieval — query Vertex AI Search filtered by meeting date. Retrieve from internal corpus (AD/ART version, Board Charter, SOPs) and external corpus (OJK, UU PT, IDX, industry). Each result tagged with `{source, version, effective_date, expiry_date, clause_id}`
  3. Regulatory context assembly — compile applicable clauses per resolution, flag regulatory overlaps and conflicts, note pending regulatory changes
  4. Corpus freshness check — alert if corpus is >30 days stale
- **Output**: Regulatory context package per resolution, applicable clause list with citations, overlap/conflict flags, corpus freshness report
- **HITL Gate 2**: Legal & Compliance team reviews regulatory mapping. Highest hallucination risk area — critical human checkpoint.
- **Grounding**: Strict RAG-only. System prompt prohibits parametric knowledge for regulations. Every citation linked to a retrieval source ID.

#### 3.3.4 Agent 3: Comparison & Reasoning Agent

- **Runtime**: Cloud Run
- **Model**: Gemini 2.5 Pro
- **Input**: Approved MoM JSON + approved regulatory context package + historical comparison data
- **Processing**:
  1. Substantive consistency check — compare "Result of the Month" data vs prior months (do trends make sense?), verify resolutions reference correct data, detect copy-paste from prior MoMs
  2. Regulatory cross-reference — for each resolution × applicable clause, classify as COMPLIANT / PARTIAL / NON-COMPLIANT / SILENT. Generate chain-of-thought reasoning with specific clause and paragraph references
  3. Red flag detection — quorum issues, undisclosed conflict of interest, related-party transactions without proper procedure (POJK 42/2020), missed deadlines, circular resolutions without documentation, missing mandatory agenda items, voting irregularities
  4. Severity scoring — CRITICAL (direct regulatory violation, OJK exposure), HIGH (significant compliance gap), MEDIUM (partial compliance), LOW (minor procedural deviation)
- **Output**: Compliance findings array with severity, chain-of-thought reasoning per finding, red flag list with evidence, substantive consistency report
- **HITL Gate 3**: Internal Audit — the most critical human checkpoint. Every finding confirmed or overridden. Every override logged to immutable audit trail.
- **Related-party entity list**: Maintained list of PT Pembangunan Jaya group companies, subsidiaries, affiliates, and directors' declared interests for automatic RPT detection.

#### 3.3.5 Agent 4: Reporting Agent

- **Runtime**: Cloud Run
- **Model**: Gemini 2.5 Flash
- **Input**: Approved compliance findings + structural sub-score + historical scorecard data + report template config
- **Processing**:
  1. Compliance scorecard — structural (0-100), substantive (0-100), regulatory (0-100), weighted composite. Trend comparison vs last 3/6/12 months
  2. Corrective wording suggestions — for each non-compliant/partial finding: current wording, issue explanation, suggested correction, regulatory basis. Generated in Bahasa Indonesia using few-shot examples
  3. Report assembly — executive summary (1 page, Komisaris-ready), detailed findings (Internal Audit depth), regulatory mapping table (Legal reference), corrective action tracker (Corp Sec follow-up), appendix with full evidence chain
  4. Multi-format export — PDF (formal board report), Excel (findings + pivot tables), JSON (machine-readable), dashboard data push
- **Output**: Compliance scorecard, corrective wording, board-ready PDF, Excel export, dashboard update
- **HITL Gate 4**: Joint approval by Head of Internal Audit (findings accuracy) + Corporate Secretary (corrective wording, board-readiness). Only after both approve does the report become visible to Komisaris.

#### 3.3.6 Batch Processing Engine

- **Runtime**: Cloud Batch
- **Purpose**: Process 500+ historical MoMs from 5-year backlog
- **Design**:
  - Parallel processing: 10-50 documents concurrently
  - Gemini API rate limiting and quota management
  - Per-document independent state tracking
  - Retry queue: max 3 retries with exponential backoff
  - Permanent failures go to manual review queue
  - Resumable: crashed batch picks up from last checkpoint
  - Priority queue: newest documents processed first
  - Progress dashboard: processed/pending/failed counts, estimated completion time

### 3.4 Layer 3: Data & Knowledge

| Store | Technology | Contents | Purpose |
|-------|-----------|----------|---------|
| Structured data | Cloud SQL (PostgreSQL 15) | MoM structured JSON, HITL decisions, job state, user/role data, template registry | Transactional data, audit trail |
| Regulatory corpus | Vertex AI Search (vector store) | Chunked regulations with metadata: `{regulation_id, article, effective_date, expiry_date, version, domain}` | RAG grounding for Legal Research Agent |
| Document storage | Cloud Storage | Raw MoMs, OCR output, generated reports, template files | Lifecycle: hot → warm → cold (10+ year retention) |
| Analytics | BigQuery | Compliance analytics, trend data, immutable audit log sink | Dashboards, historical analysis, audit evidence |

**Regulatory corpus contents (Phase 1):**
- Internal: AD/ART (latest version), Board of Directors Charter, Board of Commissioners Charter
- External: UU PT No. 40/2007 (key articles), POJK 33/2014 (BoD/BoC for Tbk), POJK 42/2020 (related-party transactions), IDX Listing Rules (material transaction chapters)

**Regulatory corpus expansion (Phase 5):**
- Kemenparekraf (tourism regulations)
- KLHK (environmental regulations)
- ATR/BPN (land/property regulations)
- Automated OJK/IDX circular monitoring

**Version control**: Every regulation chunk tagged with effective date and expiry date. Historical MoMs are audited against the regulation version active at the meeting date. When regulations are updated, retroactive impact scanning re-audits affected MoMs.

### 3.5 Layer 4: Security, Observability & DR

#### Security
- **VPC Service Controls**: All services within asia-southeast2 perimeter
- **Cloud KMS**: AES-256-GCM encryption at rest for all data stores
- **Identity-Aware Proxy (IAP)**: Zero-trust access to Cloud Run services
- **Cloud Identity SSO**: Integrated with company identity provider (Phase 5: Active Directory/Google Workspace)
- **RBAC**: 4 roles with least-privilege access. Confidential MoM sections visible only to authorized roles
- **Secret Manager**: API keys, service account credentials
- **Cloud Armor**: WAF + DDoS protection on external endpoints

#### Immutable Audit Trail
- **Cloud Audit Logs**: Every document upload, every AI inference, every HITL decision logged
- **BigQuery sink**: Audit logs exported to BigQuery for long-term immutable storage
- **Chain of custody**: For any finding, the system can prove: "AI Agent X produced finding Y at timestamp T1, Human Z reviewed and approved at timestamp T2, using regulation corpus version V"
- **Tamper protection**: Audit log BigQuery dataset is append-only with deletion restrictions

#### Observability
- **Cloud Monitoring dashboards**: Agent processing times, error rates, HITL queue depth, batch progress, Gemini API quota usage
- **Alert policies**: HITL SLA breach (48h), agent failure, corpus staleness (>30 days), Gemini quota approaching limit
- **Per-agent SLA tracking**: Extraction <30s, Legal Research <60s, Comparison <90s, Reporting <30s

#### Disaster Recovery
- **Backup**: Cross-zone Cloud SQL snapshots (hourly), Cloud Storage versioning
- **RPO**: 1 hour (maximum data loss)
- **RTO**: 4 hours (maximum recovery time)
- **Retention**: 10+ years for MoM documents and audit trails (UU PT corporate record requirements)
- **DR drill**: Annual recovery test (Phase 5)

## 4. Edge Cases

### Structural

| ID | Scenario | Severity | Handling |
|----|----------|----------|----------|
| E1 | Quorum not met | CRITICAL | Extraction Agent counts attendees → Comparison Agent checks against AD/ART quorum rules → all resolutions marked potentially invalid |
| E2 | Circular resolution (Keputusan Sirkuler) | CRITICAL | Separate validation path: UU PT Pasal 91 unanimity check instead of quorum rules. Flag if any director did not sign |
| E3 | Missing/illegible signatures on scans | HIGH | Document AI signature detection → confidence <70% forces mandatory HITL review for manual signer confirmation |
| E4 | Template drift over 5+ years | HIGH | Versioned template registry with date ranges. Unknown formats trigger HITL classification |

### Regulatory

| ID | Scenario | Severity | Handling |
|----|----------|----------|----------|
| E5 | Conflicting regulations (e.g., OJK vs AD/ART deadlines) | CRITICAL | Flag both with CONFLICT marker. Default lex superior hierarchy. Route to Legal HITL. Maintain learned conflict precedence registry |
| E6 | Regulatory transition / grace period | CRITICAL | Corpus stores effective_date + grace_period_end. Dual-version retrieval during transition. Legal HITL confirms which standard applies |
| E7 | Undisclosed related-party transaction | HIGH | Related-party entity list (PT Pembangunan Jaya group). Auto-detect RPT even when not labeled. Flag missing disclosure, independent commissioner approval, fairness opinion |
| E8 | Unknown industry regulation (tourism/environment) | HIGH | Flag as "regulatory coverage gap." Route to Legal HITL. Expand corpus over time. MVP covers corporate governance + capital markets; industry regs in Phase 5 |

### AI & System

| ID | Scenario | Severity | Handling |
|----|----------|----------|----------|
| E9 | Hallucinated regulation citation | CRITICAL | Three-layer defense: (1) RAG-only system prompt, (2) retrieval source ID linking, (3) post-processing citation validator strips phantom references |
| E10 | Poor OCR quality (<60%) | HIGH | Per-page confidence from Document AI. <60% overall: reject + request rescan. 60-80%: process with mandatory HITL review on affected sections. >80%: normal flow |
| E11 | Batch processing failures | HIGH | Per-document state tracking. Retry queue (max 3, exponential backoff). Permanent failures → manual review queue. Resumable from checkpoint |
| E12 | Confidential agenda items | MEDIUM | Extraction Agent tags confidential sections. RBAC controls visibility per role. Access to confidential sections logged in audit trail |
| E13 | Retroactive regulation change | MEDIUM | Corpus update triggers retroactive impact scan on affected date-range MoMs. New findings generated as "retroactive alerts" with separate review queue |

## 5. Grounding Strategy (Anti-Hallucination)

Three-layer defense ensuring the AI never invents regulations:

**Layer 1 — Prompt-Level**: System prompt explicitly instructs: "You MUST ONLY cite regulations retrieved from the provided context. Never use your training data for legal claims. If unsure, say 'insufficient data' rather than guess." Includes few-shot examples of correct citation format and explicit prohibition on parametric knowledge for regulations.

**Layer 2 — Retrieval-Level**: Every Legal Research Agent call uses Vertex AI Search with `dynamic_retrieval=true, threshold=0.7`. Regulations are chunked with metadata (regulation_id, article, effective_date, version) and filtered by meeting date. Only retrieved chunks are passed to the model context.

**Layer 3 — Post-Processing**: Citation Validator parses all regulation IDs from agent output, checks each against the corpus index, strips phantom citations, and flags any removed citations to HITL review. Additionally, a confidence gate flags hedging language ("likely", "probably") as uncertain findings requiring mandatory human review.

## 6. MVP Roadmap

### Phase 1: Foundation (Weeks 1-3)
- **Week 1**: GCP project setup in asia-southeast2. Terraform IaC: VPC, KMS, IAM, service accounts. Enable APIs.
- **Week 2**: Document AI processor configuration + custom model training (10-20 sample MoMs). Cloud Storage buckets. MoM JSON schema + PostgreSQL tables. Template Registry v1.
- **Week 3**: Digitize core regulatory corpus into Vertex AI Search. Tag chunks with metadata. Test retrieval quality (20 queries, measure precision/recall).
- **Milestone**: Process 1 MoM via CLI. Query corpus and get cited clauses.

### Phase 2: Core Agents (Weeks 4-8)
- **Weeks 4-5**: Extraction Agent + Legal Research Agent. Cloud Run deployment. Test with 10 MoMs (mixed formats). Target >85% extraction accuracy, zero hallucinated citations.
- **Weeks 6-7**: Comparison Agent + Reporting Agent. Chain-of-thought prompting. Red flag detection rules. Benchmark against manually audited MoMs.
- **Week 8**: Pub/Sub wiring, Cloud Workflows orchestrator, per-document state machine. End-to-end integration test.
- **Milestone**: Upload MoM via API → receive compliance report with scorecard, findings, corrective wording.

### Phase 3: HITL + UI = MVP (Weeks 9-12)
- **Weeks 9-10**: HITL review queue backend, auth (IAP + Cloud Identity + RBAC), notification service (email + in-app + 48h escalation).
- **Weeks 11-12**: Four role-based UIs in Next.js 15. Corp Sec upload/track, Internal Audit review queue, Komisaris dashboard, Legal regulatory mapper. Immutable audit trail viewer.
- **Milestone**: Full working system. Internal pilot with real BoD MoMs. All data encrypted, access controlled, audit trail complete.

### Phase 4: Batch + Scale (Weeks 13-16)
- Cloud Batch engine for historical backlog (10-50 concurrent docs). Historical template support. Retroactive impact scanning. BigQuery analytics and trend dashboards. Cloud Monitoring + alerting.
- **Milestone**: 500+ historical MoMs processed. 5-year compliance trend visible.

### Phase 5: Integration (Weeks 17-20+)
- Email auto-ingest, board portal integration, ERP connection for financial cross-checking, OJK/IDX regulation auto-monitor, industry regulation expansion (tourism, environment, land), SSO integration, DR validation.
- **Milestone**: Fully integrated, continuously running compliance audit system.

## 7. Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, React 19, Tailwind CSS |
| Backend / Agents | Cloud Run (Python or Node.js) |
| AI Models | Gemini 2.5 Flash (extraction, reporting), Gemini 2.5 Pro (legal research, comparison) |
| Document Processing | Google Document AI (OCR, layout, tables) |
| RAG / Vector Store | Vertex AI Search |
| Orchestration | Cloud Workflows + Cloud Pub/Sub (8 topics + DLQ) |
| Batch Processing | Cloud Batch |
| Database | Cloud SQL (PostgreSQL 15) |
| Object Storage | Cloud Storage (lifecycle: hot → warm → cold) |
| Analytics | BigQuery |
| Auth | Identity-Aware Proxy + Cloud Identity SSO + RBAC |
| Encryption | Cloud KMS (AES-256-GCM) |
| Network | VPC Service Controls (asia-southeast2) |
| Monitoring | Cloud Monitoring + Cloud Audit Logs |
| Infrastructure | Terraform |
| Notifications | SendGrid (email) + in-app + Cloud Tasks (escalation) |

## 8. Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Extraction accuracy | >85% field-level accuracy | Compare agent output vs manual extraction on 20 MoMs |
| Citation accuracy | Zero hallucinated regulations | Post-processing validator catch rate |
| Red flag detection | >90% recall vs manual audit | Benchmark against Internal Audit's manual findings on 10 MoMs |
| Processing time (single MoM) | <5 minutes end-to-end (excluding HITL wait) | Agent SLA monitoring |
| Batch throughput | 50+ MoMs/day | Batch processing metrics |
| HITL turnaround | <48 hours per gate | SLA tracking with escalation |
| System uptime | 99.5% | Cloud Monitoring |
| Audit trail completeness | 100% of actions logged | Audit log coverage check |
