# Business Judgment Rule (BJR) Integration — Design Specification

**Project:** PT Pembangunan Jaya Ancol Tbk — MoM Compliance System
**Platform:** Google Cloud Platform
**Architecture:** Decision-level orchestration layer on top of existing MoM + CLM pipelines
**Date:** 2026-04-17
**Target Release:** v0.4.0.0

---

## 1. Problem Statement

PT Pembangunan Jaya Ancol Tbk is a **BUMD** (owned by Pemprov DKI Jakarta) **and** a public-listed company on IDX. This dual status exposes Direksi to **two legal regimes concurrently** — corporate law (UU PT + OJK/BEI) and regional finance law (UU Pemda + PP BUMD + Pergub DKI). A normal business loss can be re-qualified as *regional finance loss* under the BUMD/keuangan daerah framework, exposing directors to criminal liability.

The only statutory defense is the **Business Judgment Rule (BJR)** — UU PT Pasal 97 ayat (5), reinforced by PP 23/2022. To invoke BJR, Direksi must prove cumulatively, per decision:

- **Pre-decision:** Due Diligence, Feasibility Study, activity is in approved RKAB, activity aligns with RJPP, no Direksi conflict of interest.
- **Decision:** Valid quorum, signed minutes, risk analysis captured, legal review of contracts, Komisaris/Dewas approval where required, OJK/BEI material disclosure when applicable.
- **Post-decision:** Monitoring mechanism defined, SPI oversight active, Komite Audit informed, periodic reports to Dewas, full archival.

**16 items cumulative, citing 28 regulations across 4 layers (UU / PP / Pergub DKI / OJK-BEI). Missing any critical item — particularly "activity in approved RKAB" — voids BJR protection entirely.**

The existing MoM Compliance System (v0.3.0.0) audits Minutes of Meeting for document-level compliance. BJR demands a **decision-level defensibility bundle**. One strategic decision typically aggregates: 1 RKAB line + 1 Feasibility Study + 1 Due Diligence + N MoMs + N contracts + post-decision monitoring. The current system captures only part of this and does not model decisions as first-class entities.

This spec describes adding BJR as an **orchestration layer on top of existing MoM + CLM**. A new `StrategicDecision` entity becomes the root; existing MoMs, contracts, and compliance findings become evidence. A 5th Gemini agent computes a BJR Readiness Score, and a dual-approval Gate 5 locks the decision into an immutable "Decision Passport" PDF for legal defense.

## 2. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Integration pattern | Orchestration layer above MoM + CLM | Preserves working v0.3.0.0 code. MoM/CLM become evidence providers. Additive, reversible. |
| Alternative considered | Foundational rearchitecture (StrategicDecision as root everywhere) | Rejected: high risk (rewrites 54 endpoints + 21 tables), destroys existing momentum. |
| Alternative considered | Lightweight checklist attached per-MoM | Rejected: doesn't model that one decision spans multiple documents; reduces BJR to paperwork generation. |
| Decision boundary | Business initiative (aggregates 1 RKAB + DD + FS + N MoMs + N contracts + monitoring) | Matches BJR's "defensibility bundle" concept. Narrow boundaries (per-resolution) produce noise; broader boundaries produce false grouping. |
| Timing mode | Proactive + Retroactive | Proactive: BD/Direksi file decisions before meetings, system guides DD/FS/RKAB checks. Retroactive: Legal/Auditor bundle completed MoMs into decisions for compliance recovery. |
| Scoring model | Dual-regime: `bjr_readiness_score = min(corporate, regional)` | Encodes the document's #1 strategic risk — a decision passing corporate but failing BUMD is NOT protected. |
| Gate 5 table | Separate `bjr_gate5_decisions` (not extending `hitl_decisions`) | Existing `HitlDecisionRecord.document_id NOT NULL`; Gate 5 is decision-scoped with dual-approver columns. Cleaner than polymorphism. |
| Gate 5 orchestration | Pub/Sub driven — NOT Cloud Workflows | Cloud Workflows orchestrates the per-document pipeline. Gate 5 is decision-level and event-driven. Keeping them separate avoids tangling layers. |
| RKAB matching | Gemini Flash classification (v1), pgvector reserved for v2 | Cheap + explainable. Embedding column in schema but unused until v2 upgrade. |
| New roles | `dewan_pengawas` + `direksi` (distinct from `komisaris`) | Ancol has BOTH Dewan Pengawas (BUMD per Pergub 50/2018) AND Dewan Komisaris (Tbk per POJK 21/2015). System previously conflated. |
| Kill switch | `BJR_ENABLED=true` env var | Feature flag for staged rollout and emergency rollback. |

## 3. Architecture

```
EXISTING MoM pipeline (unchanged):
 Upload → OCR → Extract → Gate 1 → Research → Gate 2 → Compare → Gate 3 → Report → Gate 4 → complete

EXISTING CLM pipeline (unchanged):
 Contract upload → extraction → clause library match → obligation auto-extract → approval workflow

NEW BJR layer (decision-level, sits above both):
 StrategicDecision (business initiative)
   ├─ RKAB line item FK (activity-in-plan anchor)
   ├─ RJPP theme FK (long-term alignment)
   ├─ BJRChecklist (16 items, 3 phases)
   ├─ DecisionEvidence (polymorphic → MoM | Contract | DD | FS | SPI | AuditCom | OJKDisclosure | OrganApproval)
   ├─ BJR Compliance Agent (Gemini 2.5 Pro) → Readiness Score + gap list
   ├─ Gate 5 (Komisaris + Legal dual approval) → bjr_locked
   └─ Decision Passport PDF (legal defense bundle, CMEK, 10yr retention)

Triggers:
 Pub/Sub bjr-evidence-changed → BJR Agent recomputes → notifications on score change
 Nightly Cloud Scheduler → full recompute for all non-archived decisions
 Manual: user clicks "Compute BJR" on Decision page
```

## 4. Data Model — 12 New Tables

All tables are defined in [packages/ancol-common/src/ancol_common/db/models.py](../../packages/ancol-common/src/ancol_common/db/models.py); created by [db/alembic/versions/005_bjr_schema.py](../../db/alembic/versions/005_bjr_schema.py).

### 4.1 Root + Orchestration

| Table | Role |
|-------|------|
| `strategic_decisions` | Root entity — one business initiative. Holds `bjr_readiness_score`, `corporate_compliance_score`, `regional_compliance_score`, `is_bjr_locked`, passport URI. |
| `bjr_checklists` | 16 items per decision. Stable `item_code` (e.g. `PD-01-DD`) — contract between agent output, UI, PDF, audit trail. |
| `decision_evidence` | Polymorphic join. `evidence_type` enum routes to the correct evidence table. Unique constraint prevents duplicate links. |
| `bjr_gate5_decisions` | Dual-approval (Komisaris half + Legal half). Final state locks the decision. |

### 4.2 Registries

| Table | Role |
|-------|------|
| `rkab_line_items` | Annual business plan (fiscal_year, code, activity, budget_idr, approval_status). The BJR #2 strategic risk: "activity not in RKAB voids protection". |
| `rjpp_themes` | 5-year long-term plan themes. Decisions align to a theme. |

### 4.3 Evidence Artifacts

| Table | Role | BJR Item |
|-------|------|----------|
| `due_diligence_reports` | First-class DD artifact | PD-01-DD |
| `feasibility_study_reports` | First-class FS artifact | PD-02-FS |
| `spi_reports` | Sistem Pengendalian Internal oversight | POST-13-SPI |
| `audit_committee_reports` | Komite Audit activity | POST-14-AUDITCOM |
| `material_disclosures` | OJK/BEI filings (with on-time flag) | D-11-DISCLOSE |
| `organ_approvals` | Komisaris / Dewas / RUPS approvals | D-10-ORGAN |

### 4.4 Modified Tables

- **`users.role`** enum: +`dewan_pengawas`, +`direksi`
- **`regulation_index`**: +`regulatory_regime` (corporate/regional_finance/listing/internal), +`layer` (uu/pp/pergub_dki/ojk_bei/internal) with indexes. Backfilled in migration.
- **`hitl_decisions`**: unchanged. Gate 5 uses its own table.

## 5. State Machines

### 5.1 StrategicDecision — 14 states

Defined in [repository.py](../../packages/ancol-common/src/ancol_common/db/repository.py) `DECISION_TRANSITIONS`:

```
ideation → dd_in_progress → fs_in_progress → rkab_verified
  → board_proposed → organ_approval_pending → approved → executing
  → monitoring → bjr_gate_5 → bjr_locked → archived
Terminal: rejected, cancelled
Back-edges allowed: ideation ← dd_in_progress ← fs_in_progress ← rkab_verified
                    monitoring ← bjr_gate_5 (if Gate 5 sends back for more evidence)
```

### 5.2 Gate 5 Dual-Approval

```
StrategicDecision.status = "monitoring" + bjr_readiness_score ≥ BJR_GATE5_THRESHOLD (85.0)
  → bjr_gate5_decisions row created with final_decision=pending, sla_deadline=now()+5d
  → notify Komisaris (bjr:gate_5_komisaris) + Legal (bjr:gate_5_legal)
  → each reviewer independently POSTs their half (MFA required)
  → when both approve: final_decision=approved, locked_at=now()
    → StrategicDecision.is_bjr_locked=true, status→"bjr_locked"
    → Pub/Sub bjr-locked → reporting-agent generates Decision Passport PDF
    → passport uploaded to bjr-passports bucket (CMEK, 10yr lifecycle)
  → if either rejects: final_decision=rejected, decision status→"monitoring"
```

## 6. BJR Readiness Score

16 checklist items, 3 phases, 4 CRITICAL items weighted 2×, dual-regime enforcement:

```python
def item_score(status):
    return {"satisfied": 100, "waived": 100, "in_progress": 50, "not_started": 0, "flagged": 0}[status]

CRITICAL_ITEMS  = {PD-03-RKAB, PD-05-COI, D-06-QUORUM, D-11-DISCLOSE}
CORPORATE_ITEMS = {PD-01, PD-02, PD-05, D-06, D-07, D-08, D-09, D-11, POST-16}
REGIONAL_ITEMS  = {PD-03, PD-04, PD-05, D-10, POST-12, POST-13, POST-14, POST-15, POST-16}

corporate_score = weighted_avg(items, scope=CORPORATE_ITEMS, critical_weight=2)
regional_score  = weighted_avg(items, scope=REGIONAL_ITEMS, critical_weight=2)
bjr_readiness_score = min(corporate_score, regional_score)  # dual-regime enforcement

gate_5_unlockable = (bjr_readiness_score >= BJR_GATE5_THRESHOLD)
                    and (no item in CRITICAL_ITEMS is "flagged")
```

The `min()` captures the document's #1 strategic risk: passing corporate (UU PT + OJK) without satisfying regional (PP BUMD + Pergub DKI) leaves Direksi unprotected against Pemprov DKI re-qualification as *regional finance loss*.

Definitions are in [bjr.py](../../packages/ancol-common/src/ancol_common/schemas/bjr.py). The constants `CRITICAL_ITEMS`, `CORPORATE_ITEMS`, `REGIONAL_ITEMS` live there as frozensets — the BJR Agent, the UI checklist component, and the Passport PDF all import these.

## 7. 16 Checklist Items — Automation Profile

| `item_code` | Phase | Regime | Weight | Automation | Source |
|-------------|-------|--------|--------|------------|--------|
| PD-01-DD | pre | corp | 1× | **Auto** | `due_diligence_reports.reviewed_by_legal IS NOT NULL` |
| PD-02-FS | pre | corp | 1× | **Auto** | `feasibility_study_reports.reviewed_by_finance IS NOT NULL` |
| PD-03-RKAB | pre | **regional** | **2× CRITICAL** | **AI match** | Gemini Flash classifies decision vs `rkab_line_items` (fiscal_year), threshold 0.75 |
| PD-04-RJPP | pre | regional | 1× | **AI match** | Theme match vs `rjpp_themes`, threshold 0.70 |
| PD-05-COI | pre | corp+regional | **2× CRITICAL** | **Auto** | Reuse [red_flags.py](../../services/comparison-agent/src/comparison_agent/analyzers/red_flags.py) RPT detector on linked MoM Direksi list |
| D-06-QUORUM | decision | corp | **2× CRITICAL** | **Auto** | Existing quorum validator on linked MoM |
| D-07-SIGNED | decision | corp | 1× | **Auto** | Existing signature completeness check |
| D-08-RISK | decision | corp | 1× | **AI** | Gemini scans MoM full_text for risk language |
| D-09-LEGAL | decision | corp | 1× | **Auto** | Linked `contracts.reviewed_by IS NOT NULL` |
| D-10-ORGAN | decision | regional/corp | 1× | **Auto** | `organ_approvals.decision_id=X` present where AD threshold requires |
| D-11-DISCLOSE | decision | listing | **2× CRITICAL** | **Auto** | value > `BJR_MATERIALITY_THRESHOLD_IDR` → require `material_disclosures.is_on_time=true` |
| POST-12-MONITOR | post | regional | 1× | **Manual** | User attaches monitoring plan |
| POST-13-SPI | post | regional | 1× | **Auto** | `spi_reports.related_decision_ids @> ARRAY[X]` ≥ 1 within 90d |
| POST-14-AUDITCOM | post | regional | 1× | **Auto** | `audit_committee_reports.decisions_reviewed @> ARRAY[X]` |
| POST-15-DEWAS | post | regional | 1× | **Auto** | `spi_reports.sent_to_dewas_at` frequency check |
| POST-16-ARCHIVE | post | corp+regional | 1× | **Auto** | All linked artifacts have non-null `gcs_uri` |

**12 fully auto, 3 AI-assist, 1 manual.** Item codes are **stable contracts** used by: `BJRAgentOutput.checklist[*].item_code`, UI component keys, Passport PDF section IDs, audit_trail detail.

## 8. Regulatory Corpus Expansion (+20 regs, ~120 chunks)

Seeded in [db/seed/004_regulation_index.sql](../../db/seed/004_regulation_index.sql) with `regulatory_regime` + `layer` metadata. Corpus .md content in `corpus/external/` is a BD/Legal content task (separate from this engineering phase).

- **UU layer (+4):** UU-23-2014 (Pemda), UU-19-2003 (BUMN), UU-1-2025 (Perubahan BUMN — critical post-2025), UU-6-2023 (Cipta Kerja)
- **PP layer (+3):** PP-54-2017 (BUMD induk), PP-23-2022 (BJR phases explicit), PP-45-2005 (legacy)
- **Pergub DKI layer (+14):** all tagged `regulatory_regime=regional_finance`
  - KepGub 96/2004, KepGub 4/2004 (BUMD health)
  - Pergub 109/2011, Pergub 10/2012 (RJPP), Pergub 204/2016 (Procurement)
  - Pergub 5/2018, Pergub 50/2018 (Dewan Pengawas), Pergub 79/2019 (Remuneration)
  - Pergub 127/2019 (RKAB — **critical for PD-03**)
  - Pergub 131/2019 (Pembinaan), Pergub 1/2020 (SPI), Pergub 13/2020 (Komite Audit)
  - Pergub 92/2020 (Investasi), SE Gub 13/2017 (LHKPN)
- **POJK layer (+2):** POJK-34-2014 (Komite Nominasi-Remunerasi), POJK-35-2014 (Sekretaris Perusahaan)

Backfill of existing 14 regs with `regulatory_regime` + `layer` is in the same seed. Corpus chunking uses existing [chunk_regulations.py](../../corpus/scripts/chunk_regulations.py) unchanged.

## 9. User Roles & RBAC

| Role | New? | BJR capability |
|------|------|----------------|
| `business_dev` | existing | Create/edit StrategicDecisions (proactive owner per BJR doc's "PIC") |
| `corp_secretary` | existing | Link evidence, file material disclosures |
| `legal_compliance` | existing | Review DD reports; Gate 5 Legal half |
| `internal_auditor` | existing | Submit SPI reports; retroactive bundling |
| `komisaris` | existing | Gate 5 Komisaris half; view all BJR dashboards |
| `dewan_pengawas` | **NEW** | BUMD-side oversight; approve Pergub-50 decisions; receive SPI reports |
| `direksi` | **NEW** | Self-service decision passport download |
| `admin` | existing | Full access |

~20 new permission keys in [rbac.py](../../packages/ancol-common/src/ancol_common/auth/rbac.py): `decisions:create`, `decisions:list`, `decisions:edit`, `decisions:link_evidence`, `decisions:passport`, `decisions:retroactive_bundle`, `bjr:compute`, `bjr:gate_5_komisaris`, `bjr:gate_5_legal`, `rkab:view`, `rkab:manage`, `rjpp:view`, `rjpp:manage`, `dd:create`, `dd:review`, `fs:create`, `fs:review`, `spi:submit`, `spi:view`, `audit_committee:submit`, `audit_committee:view`, `material_disclosure:file`, `organ_approval:sign`.

## 10. Phasing (12 weeks across 6 sub-phases)

| Sub-phase | Weeks | Deliverable |
|-----------|-------|-------------|
| **6.1 Foundation** | 1–3 | **THIS PHASE** — spec, corpus seed, regulatory_regime/layer, +2 roles, RBAC, 12 new tables via migration 005, Pydantic schemas, state machine |
| 6.2 Artifact entities | 3–5 | RKAB/RJPP/DD/FS/SPI/AuditCom/MaterialDisclosure/OrganApproval CRUD routers + repository helpers + 40 tests |
| 6.3 BJR Agent + Gate 5 | 5–7 | `services/bjr-agent/` Gemini Pro service + scoring + dual-regime + Gate 5 + MFA + retroactive bundler + 40 tests |
| 6.4 UI + Passport PDF | 7–9 | Decision dashboard + proactive wizard + retroactive UI + Decision Passport PDF generator |
| 6.5 Integration + E2E | 9–11 | Pub/Sub wiring + Gemini Enterprise chat tools + graph extensions + historical migration + load test |
| 6.6 Polish + Ship | 11–12 | /review + /codex + /simplify + security review + Terraform + staging deploy |

## 11. Verification (Phase 6.1)

```bash
# Table count jumps from 21 to 33
PYTHONPATH=packages/ancol-common/src python3 -c "from ancol_common.db.models import Base; assert len(Base.metadata.tables) == 33; print('OK')"

# Lint
ruff check packages/ services/ scripts/ corpus/scripts/
ruff format --check packages/ services/ scripts/ corpus/scripts/

# Existing 377 tests still pass (no regressions)
for svc in extraction-agent legal-research-agent comparison-agent reporting-agent api-gateway batch-engine email-ingest regulation-monitor gemini-agent; do
  PYTHONPATH=packages/ancol-common/src:services/$svc/src python3 -m pytest services/$svc/tests/ -q
done

# Pydantic schemas load cleanly
PYTHONPATH=packages/ancol-common/src python3 -c "
from ancol_common.schemas.decision import StrategicDecisionCreate, DecisionStatus, InitiativeType
from ancol_common.schemas.bjr import BJRItemCode, CRITICAL_ITEMS, CORPORATE_ITEMS, REGIONAL_ITEMS
from ancol_common.schemas.artifact import DDRiskRating, OrganApprovalType, SPIReportType
assert len(BJRItemCode) == 16
assert len(CRITICAL_ITEMS) == 4
print('OK: 16 BJR items, 4 critical')
"

# State machine
PYTHONPATH=packages/ancol-common/src python3 -c "
from ancol_common.db.repository import DECISION_TRANSITIONS
assert 'ideation' in DECISION_TRANSITIONS
assert 'bjr_locked' in DECISION_TRANSITIONS
print('OK: decision state machine registered')
"
```

## 12. Rollback

Migration 005 has a full `downgrade()` that drops all 12 new tables and reverts regulation_index columns. Environment kill switch `BJR_ENABLED=false` disables all BJR routers without touching the schema. PostgreSQL enum additions (`dewan_pengawas`, `direksi` on `user_role`) cannot be cleanly removed — they remain harmless after downgrade unless a user references them.

## 13. Deferred to v2

1. Multi-role users (staff holding both Direksi and BD hats)
2. RKAB mid-year revision retroactivity semantics
3. Komisaris ↔ Dewan Pengawas person overlap (same individual on both organs)
4. RUPS-as-entity (currently represented as `organ_approvals.approval_type='rups'`)
5. pgvector-based RKAB semantic matching (embedding column reserved in schema)
6. Pemprov DKI-facing read-only dashboard
