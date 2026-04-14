# Contract PDF Generation & Frontend Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate professional PDF documents from contract drafts (currently markdown-only) and build frontend pages for contract detail view and draft generation/review.

**Architecture:** Reuse the existing WeasyPrint PDF pattern from `reporting-agent/generators/pdf.py`. Add a `drafting/pdf.py` module to `ancol-common` that converts DraftOutput into styled HTML, then renders PDF. Add two new API endpoints for PDF generation. Build two new Next.js pages: contract detail (`/contracts/[id]`) and draft generator (`/contracts/draft`).

**Tech Stack:** Python (WeasyPrint, f-string HTML templates), FastAPI, Next.js 15, React 19, Tailwind CSS

---

## File Structure

### Backend (PDF Generation)

| File | Action | Responsibility |
|------|--------|----------------|
| `packages/ancol-common/src/ancol_common/drafting/pdf.py` | Create | HTML template for contract PDFs + `render_contract_pdf()` |
| `services/api-gateway/src/api_gateway/routers/drafting.py` | Modify | Add `POST /drafting/pdf` endpoint |
| `services/api-gateway/tests/test_contract_pdf.py` | Create | Tests for PDF HTML generation + endpoint |

### Frontend (Contract Detail + Draft Generator)

| File | Action | Responsibility |
|------|--------|----------------|
| `web/src/app/(dashboard)/contracts/[id]/page.tsx` | Create | Contract detail page — metadata, clauses, parties, risk, obligations |
| `web/src/app/(dashboard)/contracts/draft/page.tsx` | Create | Draft generator form + preview + PDF download |
| `web/src/lib/api.ts` | Modify | Add `generateDraft()` and `generateDraftPdf()` API functions |
| `web/src/types/index.ts` | Modify | Add `DraftOutput` and `DraftFormData` types |
| `web/src/components/shared/sidebar.tsx` | Modify | Add "Buat Draf" link under Contract Management |

---

## Task 1: Contract PDF HTML Generator

**Files:**
- Create: `packages/ancol-common/src/ancol_common/drafting/pdf.py`
- Test: `services/api-gateway/tests/test_contract_pdf.py`

- [ ] **Step 1: Write the failing tests**

Create `services/api-gateway/tests/test_contract_pdf.py`:

```python
"""Tests for contract PDF HTML generation."""

from __future__ import annotations

import pytest
from ancol_common.schemas.contract import ContractClause, ContractParty, RiskLevel
from ancol_common.schemas.drafting import DraftOutput, DraftRequest


class TestContractPdfHtml:
    """Test generate_contract_html output."""

    def _make_request(self) -> DraftRequest:
        return DraftRequest(
            contract_type="vendor",
            parties=[
                ContractParty(
                    name="PT Pembangunan Jaya Ancol Tbk",
                    role="principal",
                    entity_type="internal",
                ),
                ContractParty(
                    name="PT Mitra Jaya",
                    role="counterparty",
                    entity_type="external",
                ),
            ],
            key_terms={"value": "500000000", "duration": "12 bulan"},
            language="id",
        )

    def _make_output(self) -> DraftOutput:
        return DraftOutput(
            contract_id="test-contract-123",
            draft_text="# PERJANJIAN PENYEDIAAN JASA\n\n## Pasal 1 — Ruang Lingkup\n\nIsi pasal.",
            clauses=[
                ContractClause(
                    clause_number="Pasal 1",
                    title="Ruang Lingkup",
                    text="Isi pasal.",
                    category="scope",
                    risk_level=RiskLevel.LOW,
                    is_from_library=True,
                    confidence=1.0,
                ),
                ContractClause(
                    clause_number="Pasal 2",
                    title="Pembayaran",
                    text="Pembayaran dalam 30 hari.",
                    category="payment_terms",
                    risk_level=RiskLevel.MEDIUM,
                    risk_reason="No late payment penalty defined",
                    is_from_library=True,
                    confidence=1.0,
                ),
            ],
            risk_assessment=[
                {"clause": "Pasal 2", "category": "payment_terms", "notes": "Missing penalty clause"},
            ],
        )

    def test_generates_valid_html(self):
        from ancol_common.drafting.pdf import generate_contract_html

        html = generate_contract_html(self._make_request(), self._make_output())
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    def test_includes_contract_title(self):
        from ancol_common.drafting.pdf import generate_contract_html

        html = generate_contract_html(self._make_request(), self._make_output())
        assert "PERJANJIAN PENYEDIAAN JASA" in html

    def test_includes_party_names(self):
        from ancol_common.drafting.pdf import generate_contract_html

        html = generate_contract_html(self._make_request(), self._make_output())
        assert "PT Pembangunan Jaya Ancol Tbk" in html
        assert "PT Mitra Jaya" in html

    def test_includes_clauses(self):
        from ancol_common.drafting.pdf import generate_contract_html

        html = generate_contract_html(self._make_request(), self._make_output())
        assert "Pasal 1" in html
        assert "Ruang Lingkup" in html
        assert "Isi pasal." in html

    def test_includes_risk_assessment(self):
        from ancol_common.drafting.pdf import generate_contract_html

        html = generate_contract_html(self._make_request(), self._make_output())
        assert "Missing penalty clause" in html

    def test_includes_risk_badges(self):
        from ancol_common.drafting.pdf import generate_contract_html

        html = generate_contract_html(self._make_request(), self._make_output())
        assert "RENDAH" in html
        assert "SEDANG" in html

    def test_includes_key_terms(self):
        from ancol_common.drafting.pdf import generate_contract_html

        html = generate_contract_html(self._make_request(), self._make_output())
        assert "500000000" in html
        assert "12 bulan" in html

    def test_render_contract_pdf_without_weasyprint(self, tmp_path):
        """When WeasyPrint is unavailable, falls back to HTML file."""
        from ancol_common.drafting.pdf import render_contract_pdf

        html = "<html><body>Test</body></html>"
        output = str(tmp_path / "test.pdf")
        result = render_contract_pdf(html, output)
        # Falls back to .html if WeasyPrint not installed locally
        assert result.endswith(".html") or result.endswith(".pdf")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
PYTHONPATH=packages/ancol-common/src:services/api-gateway/src python3 -m pytest services/api-gateway/tests/test_contract_pdf.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'ancol_common.drafting.pdf'`

- [ ] **Step 3: Implement the contract PDF HTML generator**

Create `packages/ancol-common/src/ancol_common/drafting/pdf.py`:

```python
"""Contract PDF generation — styled HTML + WeasyPrint rendering.

Generates professional bilingual contract documents from DraftOutput.
Follows the same pattern as reporting-agent/generators/pdf.py.
"""

from __future__ import annotations

import logging
from datetime import datetime
from html import escape

from ancol_common.schemas.drafting import DraftOutput, DraftRequest

logger = logging.getLogger(__name__)

CONTRACT_CSS = """
@page {
    size: A4;
    margin: 2.5cm;
    @top-center { content: "DRAF KONTRAK — RAHASIA"; font-size: 8pt; color: #999; }
    @bottom-center { content: "Halaman " counter(page) " dari " counter(pages); font-size: 8pt; }
}
body { font-family: 'Noto Sans', Arial, sans-serif; font-size: 10pt; line-height: 1.6; color: #333; }
h1 { color: #1a237e; font-size: 18pt; text-align: center; border-bottom: 2px solid #1a237e; padding-bottom: 8px; }
h2 { color: #283593; font-size: 13pt; margin-top: 24px; border-bottom: 1px solid #e0e0e0; padding-bottom: 4px; }
h3 { color: #3949ab; font-size: 11pt; margin-top: 16px; }
table { width: 100%; border-collapse: collapse; margin: 10px 0; }
th { background-color: #1a237e; color: white; padding: 8px; text-align: left; font-size: 9pt; }
td { padding: 6px 8px; border-bottom: 1px solid #e0e0e0; font-size: 9pt; }
tr:nth-child(even) { background-color: #f5f5f5; }
.clause-box { border: 1px solid #e0e0e0; border-radius: 4px; padding: 12px; margin: 10px 0; page-break-inside: avoid; }
.clause-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.clause-title { font-weight: bold; color: #1a237e; font-size: 11pt; }
.risk-badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 8pt; font-weight: bold; }
.risk-high { background-color: #ffebee; color: #c62828; }
.risk-medium { background-color: #fff3e0; color: #ef6c00; }
.risk-low { background-color: #e8f5e9; color: #2e7d32; }
.confidence { font-size: 8pt; color: #999; }
.meta-table td:first-child { font-weight: bold; width: 180px; color: #555; }
.risk-box { border-left: 3px solid #ef6c00; background-color: #fff8e1; padding: 8px 12px; margin: 6px 0; font-size: 9pt; }
.footer { font-size: 8pt; color: #999; margin-top: 30px; border-top: 1px solid #e0e0e0; padding-top: 10px; }
"""

TYPE_NAMES = {
    "nda": "PERJANJIAN KERAHASIAAN",
    "vendor": "PERJANJIAN PENYEDIAAN JASA",
    "sale_purchase": "PERJANJIAN JUAL BELI",
    "joint_venture": "PERJANJIAN USAHA PATUNGAN",
    "land_lease": "PERJANJIAN SEWA MENYEWA",
    "employment": "PERJANJIAN KERJA",
    "sop_board_resolution": "STANDAR OPERASIONAL PROSEDUR RAPAT",
}

ROLE_NAMES = {
    "principal": "PIHAK PERTAMA",
    "counterparty": "PIHAK KEDUA",
    "guarantor": "PENJAMIN",
}

RISK_LABELS = {"high": "TINGGI", "medium": "SEDANG", "low": "RENDAH"}


def generate_contract_html(request: DraftRequest, output: DraftOutput) -> str:
    """Generate styled HTML for a contract draft PDF.

    All dynamic values are HTML-escaped to prevent injection.
    """
    title = TYPE_NAMES.get(request.contract_type, "PERJANJIAN")
    now = datetime.now().strftime("%d %B %Y, %H:%M WIB")

    # Parties table rows
    parties_rows = ""
    for party in request.parties:
        role_label = ROLE_NAMES.get(party.role, escape(party.role.upper()))
        entity_note = " <em>(pihak berelasi)</em>" if party.entity_type == "related_party" else ""
        parties_rows += (
            f"<tr><td>{escape(role_label)}</td>"
            f"<td>{escape(party.name)}{entity_note}</td>"
            f"<td>{escape(party.contact_email or '-')}</td></tr>\n"
        )

    # Key terms rows
    terms_rows = ""
    for key, value in request.key_terms.items():
        label = escape(key.replace("_", " ").title())
        terms_rows += f"<tr><td>{label}</td><td>{escape(str(value))}</td></tr>\n"

    # Clause sections
    clauses_html = ""
    for clause in output.clauses:
        risk_class = f"risk-{clause.risk_level}" if clause.risk_level else ""
        risk_label = RISK_LABELS.get(clause.risk_level or "", "")
        risk_badge = (
            f'<span class="risk-badge {risk_class}">{escape(risk_label)}</span>'
            if clause.risk_level
            else ""
        )
        risk_reason = (
            f'<div class="risk-box">{escape(clause.risk_reason)}</div>'
            if clause.risk_reason
            else ""
        )
        source = "Perpustakaan Klausul" if clause.is_from_library else "Kustom"
        conf_pct = f"{clause.confidence * 100:.0f}%"

        clauses_html += f"""
        <div class="clause-box">
            <div class="clause-header">
                <span class="clause-title">{escape(clause.clause_number)} — {escape(clause.title)}</span>
                {risk_badge}
            </div>
            <p>{escape(clause.text)}</p>
            {risk_reason}
            <div class="confidence">Sumber: {source} | Kepercayaan: {conf_pct}</div>
        </div>
        """

    # Risk assessment section
    risk_html = ""
    for ra in output.risk_assessment:
        if "clause" in ra:
            risk_html += (
                f'<div class="risk-box"><strong>{escape(str(ra["clause"]))}</strong>'
                f' ({escape(str(ra.get("category", "")))}): '
                f'{escape(str(ra.get("notes", "")))}</div>\n'
            )
        elif "issue" in ra:
            risk_html += (
                f'<div class="risk-box"><strong>Konsistensi:</strong> '
                f'{escape(str(ra["issue"]))} — '
                f'<em>{escape(str(ra.get("suggestion", "")))}</em></div>\n'
            )

    html = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="utf-8">
    <title>Draf Kontrak — {escape(title)}</title>
    <style>{CONTRACT_CSS}</style>
</head>
<body>
    <h1>{escape(title)}</h1>
    <p style="text-align: center; color: #666;">PT Pembangunan Jaya Ancol Tbk</p>

    <h2>Informasi Kontrak</h2>
    <table class="meta-table">
        <tr><td>ID Kontrak</td><td>{escape(output.contract_id)}</td></tr>
        <tr><td>Tipe Kontrak</td><td>{escape(title)}</td></tr>
        <tr><td>Tanggal Draf</td><td>{now}</td></tr>
        <tr><td>Jumlah Pasal</td><td>{len(output.clauses)}</td></tr>
    </table>

    <h2>Para Pihak</h2>
    <table>
        <tr><th>Peran</th><th>Nama</th><th>Email</th></tr>
        {parties_rows}
    </table>

    {"<h2>Ketentuan Utama</h2><table class='meta-table'>" + terms_rows + "</table>" if terms_rows else ""}

    <h2>Klausul Kontrak</h2>
    {clauses_html}

    {"<h2>Penilaian Risiko</h2>" + risk_html if risk_html else ""}

    <div class="footer">
        Draf ini dihasilkan oleh Smart Drafting Engine — PJAA CLM System.<br>
        Draf bersifat advisory dan memerlukan review oleh tim legal sebelum penandatanganan.
    </div>
</body>
</html>"""

    return html


def render_contract_pdf(html: str, output_path: str) -> str:
    """Render contract HTML to PDF using WeasyPrint.

    Falls back to HTML file if WeasyPrint is not installed.
    """
    try:
        from weasyprint import HTML

        HTML(string=html).write_pdf(output_path)
        logger.info("Contract PDF generated: %s", output_path)
        return output_path
    except ImportError:
        logger.warning("WeasyPrint not installed — saving as HTML instead")
        html_path = output_path.replace(".pdf", ".html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        return html_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
PYTHONPATH=packages/ancol-common/src:services/api-gateway/src python3 -m pytest services/api-gateway/tests/test_contract_pdf.py -v
```

Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/ancol-common/src/ancol_common/drafting/pdf.py services/api-gateway/tests/test_contract_pdf.py
git commit -m "feat(clm): add contract PDF HTML generator with WeasyPrint rendering"
```

---

## Task 2: PDF Generation API Endpoint

**Files:**
- Modify: `services/api-gateway/src/api_gateway/routers/drafting.py`
- Test: `services/api-gateway/tests/test_contract_pdf.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `services/api-gateway/tests/test_contract_pdf.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch


class TestDraftPdfEndpoint:
    """Test the POST /api/drafting/pdf endpoint."""

    @pytest.fixture
    def mock_deps(self):
        """Mock DB session and drafting engine."""
        with (
            patch("api_gateway.routers.drafting.get_session") as mock_session_ctx,
            patch("api_gateway.routers.drafting.assemble_draft") as mock_assemble,
        ):
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_assemble.return_value = DraftOutput(
                contract_id="pdf-test-123",
                draft_text="# TEST\n\n## Pasal 1\n\nIsi.",
                clauses=[
                    ContractClause(
                        clause_number="Pasal 1",
                        title="Test",
                        text="Isi.",
                        category="scope",
                        confidence=1.0,
                    )
                ],
                risk_assessment=[],
            )

            yield {"session": mock_session, "assemble": mock_assemble}

    @pytest.mark.asyncio
    async def test_pdf_endpoint_returns_html(self, mock_deps):
        """Verify the endpoint returns HTML content (WeasyPrint may not be installed)."""
        from fastapi.testclient import TestClient
        from api_gateway.main import app

        client = TestClient(app)
        response = client.post(
            "/api/drafting/pdf",
            json={
                "contract_type": "vendor",
                "parties": [
                    {"name": "PT Ancol", "role": "principal", "entity_type": "internal"},
                    {"name": "PT Vendor", "role": "counterparty", "entity_type": "external"},
                ],
                "key_terms": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "html" in data
        assert "<!DOCTYPE html>" in data["html"]
        assert "contract_id" in data

    @pytest.mark.asyncio
    async def test_pdf_endpoint_includes_contract_id(self, mock_deps):
        from fastapi.testclient import TestClient
        from api_gateway.main import app

        client = TestClient(app)
        response = client.post(
            "/api/drafting/pdf",
            json={
                "contract_type": "nda",
                "parties": [
                    {"name": "PT Ancol", "role": "principal", "entity_type": "internal"},
                ],
            },
        )
        assert response.status_code == 200
        assert response.json()["contract_id"] == "pdf-test-123"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
PYTHONPATH=packages/ancol-common/src:services/api-gateway/src python3 -m pytest services/api-gateway/tests/test_contract_pdf.py::TestDraftPdfEndpoint -v
```

Expected: FAIL — 404 (endpoint doesn't exist)

- [ ] **Step 3: Add the PDF endpoint to the drafting router**

Add to `services/api-gateway/src/api_gateway/routers/drafting.py` after the existing `generate_draft` endpoint (after line 138). Also add the `assemble_draft` import at the module level (move from lazy to top-level alongside other imports):

```python
@router.post("/pdf")
async def generate_draft_pdf(
    _auth=require_permission("drafting:generate"),
    body: dict | None = None,
):
    """Generate a contract draft and return styled HTML for PDF rendering.

    Returns the HTML content that can be rendered to PDF client-side,
    plus the contract_id and clause metadata.
    """
    from ancol_common.drafting.engine import assemble_draft
    from ancol_common.drafting.pdf import generate_contract_html
    from ancol_common.schemas.contract import ContractParty
    from ancol_common.schemas.drafting import DraftRequest

    if body is None:
        body = {}
    request = DraftRequest(
        contract_type=body.get("contract_type", "vendor"),
        parties=[ContractParty(**p) for p in body.get("parties", [])],
        key_terms=body.get("key_terms", {}),
        clause_overrides=body.get("clause_overrides", []),
        language=body.get("language", "id"),
    )

    async with get_session() as session:
        result = await assemble_draft(session, request)

    html = generate_contract_html(request, result)

    return {
        "contract_id": result.contract_id,
        "html": html,
        "clauses": [c.model_dump() for c in result.clauses],
        "risk_assessment": result.risk_assessment,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
PYTHONPATH=packages/ancol-common/src:services/api-gateway/src python3 -m pytest services/api-gateway/tests/test_contract_pdf.py -v
```

Expected: All 10 tests PASS

- [ ] **Step 5: Run full API gateway test suite to verify no regressions**

Run:
```bash
PYTHONPATH=packages/ancol-common/src:services/api-gateway/src python3 -m pytest services/api-gateway/tests/ -q
```

Expected: 77+ tests pass, 0 failures

- [ ] **Step 6: Commit**

```bash
git add services/api-gateway/src/api_gateway/routers/drafting.py services/api-gateway/tests/test_contract_pdf.py
git commit -m "feat(clm): add POST /drafting/pdf endpoint for contract PDF generation"
```

---

## Task 3: Frontend Types and API Client Updates

**Files:**
- Modify: `web/src/types/index.ts`
- Modify: `web/src/lib/api.ts`

- [ ] **Step 1: Add DraftOutput and DraftFormData types**

Add to the end of `web/src/types/index.ts`:

```typescript
// Draft generation types
export interface DraftFormData {
  contract_type: ContractType;
  parties: Array<{
    name: string;
    role: "principal" | "counterparty" | "guarantor";
    entity_type: "internal" | "external" | "related_party";
    contact_email?: string;
  }>;
  key_terms: Record<string, string>;
  clause_overrides?: Array<Record<string, string>>;
  language?: "id" | "en";
}

export interface DraftResult {
  contract_id: string;
  draft_text: string;
  clauses: ContractClauseItem[];
  risk_assessment: Array<Record<string, string>>;
  gcs_draft_uri?: string;
}

export interface DraftPdfResult {
  contract_id: string;
  html: string;
  clauses: ContractClauseItem[];
  risk_assessment: Array<Record<string, string>>;
}
```

- [ ] **Step 2: Add API functions for draft generation and PDF**

Add to `web/src/lib/api.ts` after the existing drafting section (after line 190):

```typescript
export const generateDraft = (data: import("@/types").DraftFormData) =>
  fetchApi<import("@/types").DraftResult>("/api/drafting/generate", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const generateDraftPdf = (data: import("@/types").DraftFormData) =>
  fetchApi<import("@/types").DraftPdfResult>("/api/drafting/pdf", {
    method: "POST",
    body: JSON.stringify(data),
  });
```

- [ ] **Step 3: Commit**

```bash
git add web/src/types/index.ts web/src/lib/api.ts
git commit -m "feat(web): add draft generation types and API client functions"
```

---

## Task 4: Contract Detail Page

**Files:**
- Create: `web/src/app/(dashboard)/contracts/[id]/page.tsx`
- Modify: `web/src/app/(dashboard)/contracts/page.tsx` (make rows clickable)

- [ ] **Step 1: Create the contract detail page**

Create `web/src/app/(dashboard)/contracts/[id]/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getContract, getContractClauses, getContractRisk, getObligations } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { ContractSummary, ContractClauseItem, ObligationSummary } from "@/types";

const STATUS_LABELS: Record<string, string> = {
  draft: "Draf",
  pending_review: "Menunggu Review",
  in_review: "Dalam Review",
  approved: "Disetujui",
  executed: "Ditandatangani",
  active: "Aktif",
  expiring: "Akan Berakhir",
  expired: "Berakhir",
  terminated: "Dibatalkan",
  amended: "Diamandemen",
  failed: "Gagal",
};

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  pending_review: "bg-yellow-100 text-yellow-700",
  in_review: "bg-blue-100 text-blue-700",
  approved: "bg-green-100 text-green-700",
  executed: "bg-green-100 text-green-700",
  active: "bg-emerald-100 text-emerald-700",
  expiring: "bg-orange-100 text-orange-700",
  expired: "bg-red-100 text-red-700",
  terminated: "bg-red-100 text-red-700",
  amended: "bg-purple-100 text-purple-700",
  failed: "bg-red-100 text-red-700",
};

const TYPE_LABELS: Record<string, string> = {
  nda: "NDA",
  vendor: "Vendor",
  sale_purchase: "Jual Beli",
  joint_venture: "Joint Venture",
  land_lease: "Sewa Tanah",
  employment: "Ketenagakerjaan",
  sop_board_resolution: "SOP/SK Direksi",
};

const RISK_COLORS: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-yellow-100 text-yellow-700",
  low: "bg-green-100 text-green-700",
};

const OBL_STATUS_COLORS: Record<string, string> = {
  upcoming: "bg-blue-100 text-blue-700",
  due_soon: "bg-orange-100 text-orange-700",
  overdue: "bg-red-100 text-red-700",
  fulfilled: "bg-green-100 text-green-700",
  waived: "bg-gray-100 text-gray-700",
};

export default function ContractDetailPage() {
  const params = useParams();
  const router = useRouter();
  const contractId = params.id as string;

  const [contract, setContract] = useState<ContractSummary | null>(null);
  const [clauses, setClauses] = useState<ContractClauseItem[]>([]);
  const [obligations, setObligations] = useState<ObligationSummary[]>([]);
  const [riskData, setRiskData] = useState<{ risk_level: string; risk_score: number | null } | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"clauses" | "obligations" | "risk">("clauses");

  useEffect(() => {
    if (!contractId) return;
    setLoading(true);

    Promise.all([
      getContract(contractId),
      getContractClauses(contractId).catch(() => ({ clauses: [] })),
      getObligations(contractId).catch(() => ({ obligations: [] })),
      getContractRisk(contractId).catch(() => null),
    ])
      .then(([c, cl, ob, r]) => {
        setContract(c);
        setClauses(cl.clauses || []);
        setObligations(ob.obligations || []);
        if (r) setRiskData({ risk_level: r.risk_level, risk_score: r.risk_score });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [contractId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="text-gray-400">Memuat detail kontrak...</div>
      </div>
    );
  }

  if (!contract) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <div className="text-gray-400">Kontrak tidak ditemukan</div>
        <button onClick={() => router.push("/contracts")} className="text-sm text-blue-600 hover:underline">
          Kembali ke Daftar Kontrak
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-2">
        <button onClick={() => router.push("/contracts")} className="text-sm text-gray-400 hover:text-gray-600">
          Kontrak /
        </button>
        <span className="text-sm text-gray-600 truncate max-w-md">{contract.title}</span>
      </div>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{contract.title}</h1>
          <p className="text-sm text-gray-500 mt-1">
            {contract.contract_number || "Belum bernomor"} · {TYPE_LABELS[contract.contract_type] || contract.contract_type}
          </p>
        </div>
        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${STATUS_COLORS[contract.status] || "bg-gray-100"}`}>
          {STATUS_LABELS[contract.status] || contract.status}
        </span>
      </div>

      {/* Metadata cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <div className="text-xs text-gray-500 mb-1">Berlaku</div>
          <div className="text-sm font-medium">{contract.effective_date ? formatDate(contract.effective_date) : "-"}</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <div className="text-xs text-gray-500 mb-1">Berakhir</div>
          <div className="text-sm font-medium">{contract.expiry_date ? formatDate(contract.expiry_date) : "-"}</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <div className="text-xs text-gray-500 mb-1">Nilai Kontrak</div>
          <div className="text-sm font-medium">
            {contract.total_value ? `${contract.currency} ${contract.total_value.toLocaleString("id-ID")}` : "-"}
          </div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <div className="text-xs text-gray-500 mb-1">Risiko</div>
          <div className="flex items-center gap-2">
            {contract.risk_level ? (
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${RISK_COLORS[contract.risk_level]}`}>
                {contract.risk_level.toUpperCase()}
              </span>
            ) : (
              <span className="text-sm text-gray-400">-</span>
            )}
            {contract.risk_score != null && (
              <span className="text-xs text-gray-500">({contract.risk_score.toFixed(0)}/100)</span>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-6">
          {(["clauses", "obligations", "risk"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab === "clauses" && `Klausul (${clauses.length})`}
              {tab === "obligations" && `Kewajiban (${obligations.length})`}
              {tab === "risk" && "Analisis Risiko"}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === "clauses" && (
        <div className="space-y-3">
          {clauses.length === 0 ? (
            <div className="text-center py-12 text-gray-400">Belum ada klausul terekstrak</div>
          ) : (
            clauses.map((cl) => (
              <div key={cl.id} className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-gray-900">{cl.clause_number}</span>
                    <span className="text-sm font-medium text-gray-700">{cl.title}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {cl.risk_level && (
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${RISK_COLORS[cl.risk_level]}`}>
                        {cl.risk_level.toUpperCase()}
                      </span>
                    )}
                    <span className="text-xs text-gray-400">{(cl.confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
                <p className="text-sm text-gray-600 whitespace-pre-wrap">{cl.text}</p>
                {cl.risk_reason && (
                  <div className="mt-2 text-xs text-orange-700 bg-orange-50 rounded px-3 py-2">
                    {cl.risk_reason}
                  </div>
                )}
                {cl.category && (
                  <div className="mt-2 text-xs text-gray-400">Kategori: {cl.category}</div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {activeTab === "obligations" && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase">
                <th className="px-6 py-3">Tipe</th>
                <th className="px-6 py-3">Deskripsi</th>
                <th className="px-6 py-3">Jatuh Tempo</th>
                <th className="px-6 py-3">Penanggung Jawab</th>
                <th className="px-6 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {obligations.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-gray-400">
                    Belum ada kewajiban
                  </td>
                </tr>
              ) : (
                obligations.map((ob) => (
                  <tr key={ob.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm text-gray-600 capitalize">{ob.obligation_type.replace("_", " ")}</td>
                    <td className="px-6 py-4 text-sm text-gray-700 max-w-xs truncate">{ob.description}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">{formatDate(ob.due_date)}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{ob.responsible_party_name}</td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${OBL_STATUS_COLORS[ob.status] || "bg-gray-100"}`}>
                        {ob.status.replace("_", " ")}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === "risk" && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          {riskData ? (
            <div>
              <div className="flex items-center gap-4 mb-6">
                <div className="text-center">
                  <div className="text-3xl font-bold text-gray-900">
                    {riskData.risk_score != null ? riskData.risk_score.toFixed(0) : "-"}
                  </div>
                  <div className="text-xs text-gray-500">Skor Risiko / 100</div>
                </div>
                {riskData.risk_level && (
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${RISK_COLORS[riskData.risk_level]}`}>
                    {riskData.risk_level.toUpperCase()}
                  </span>
                )}
              </div>
              <h3 className="text-sm font-medium text-gray-700 mb-3">Risiko per Klausul</h3>
              <div className="space-y-2">
                {clauses
                  .filter((cl) => cl.risk_level && cl.risk_level !== "low")
                  .map((cl) => (
                    <div key={cl.id} className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-3">
                      <div>
                        <span className="text-sm font-medium text-gray-900">{cl.clause_number} — {cl.title}</span>
                        {cl.risk_reason && <p className="text-xs text-gray-500 mt-1">{cl.risk_reason}</p>}
                      </div>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${RISK_COLORS[cl.risk_level!]}`}>
                        {cl.risk_level!.toUpperCase()}
                      </span>
                    </div>
                  ))}
                {clauses.filter((cl) => cl.risk_level && cl.risk_level !== "low").length === 0 && (
                  <div className="text-sm text-gray-400 py-4 text-center">Tidak ada klausul berisiko tinggi/sedang</div>
                )}
              </div>
            </div>
          ) : (
            <div className="text-center py-12 text-gray-400">Data risiko belum tersedia</div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add clickable rows in contracts list page**

Modify `web/src/app/(dashboard)/contracts/page.tsx`:

At the top of the file, add import:
```tsx
import { useRouter } from "next/navigation";
```

Inside the component, add after the state declarations:
```tsx
const router = useRouter();
```

Replace the `<tr key={c.id} className="hover:bg-gray-50">` with:
```tsx
<tr key={c.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => router.push(`/contracts/${c.id}`)}>
```

- [ ] **Step 3: Verify the build compiles**

Run:
```bash
cd web && npm run build 2>&1 | tail -20
```

Expected: Build succeeds with no errors

- [ ] **Step 4: Commit**

```bash
git add web/src/app/\(dashboard\)/contracts/\[id\]/page.tsx web/src/app/\(dashboard\)/contracts/page.tsx
git commit -m "feat(web): add contract detail page with clauses, obligations, and risk tabs"
```

---

## Task 5: Draft Generator Page

**Files:**
- Create: `web/src/app/(dashboard)/contracts/draft/page.tsx`

- [ ] **Step 1: Create the draft generator page**

Create `web/src/app/(dashboard)/contracts/draft/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { generateDraft, generateDraftPdf } from "@/lib/api";
import type { DraftFormData, DraftResult, ContractType } from "@/types";

const CONTRACT_TYPES: Array<{ value: ContractType; label: string }> = [
  { value: "vendor", label: "Perjanjian Vendor" },
  { value: "nda", label: "NDA (Kerahasiaan)" },
  { value: "sale_purchase", label: "Jual Beli" },
  { value: "joint_venture", label: "Joint Venture" },
  { value: "land_lease", label: "Sewa Tanah" },
  { value: "employment", label: "Ketenagakerjaan" },
  { value: "sop_board_resolution", label: "SOP/SK Direksi" },
];

const PARTY_ROLES = [
  { value: "principal", label: "Pihak Pertama" },
  { value: "counterparty", label: "Pihak Kedua" },
  { value: "guarantor", label: "Penjamin" },
] as const;

const ENTITY_TYPES = [
  { value: "internal", label: "Internal" },
  { value: "external", label: "Eksternal" },
  { value: "related_party", label: "Pihak Berelasi" },
] as const;

interface PartyInput {
  name: string;
  role: "principal" | "counterparty" | "guarantor";
  entity_type: "internal" | "external" | "related_party";
  contact_email: string;
}

export default function DraftGeneratorPage() {
  const [contractType, setContractType] = useState<ContractType>("vendor");
  const [parties, setParties] = useState<PartyInput[]>([
    { name: "PT Pembangunan Jaya Ancol Tbk", role: "principal", entity_type: "internal", contact_email: "" },
    { name: "", role: "counterparty", entity_type: "external", contact_email: "" },
  ]);
  const [keyTerms, setKeyTerms] = useState<Array<{ key: string; value: string }>>([
    { key: "value", value: "" },
    { key: "duration", value: "" },
  ]);
  const [language, setLanguage] = useState<"id" | "en">("id");

  const [loading, setLoading] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [result, setResult] = useState<DraftResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  function buildFormData(): DraftFormData {
    const validParties = parties.filter((p) => p.name.trim());
    const terms: Record<string, string> = {};
    for (const t of keyTerms) {
      if (t.key.trim() && t.value.trim()) terms[t.key.trim()] = t.value.trim();
    }
    return {
      contract_type: contractType,
      parties: validParties.map((p) => ({
        name: p.name,
        role: p.role,
        entity_type: p.entity_type,
        contact_email: p.contact_email || undefined,
      })),
      key_terms: terms,
      language,
    };
  }

  async function handleGenerate() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = buildFormData();
      const res = await generateDraft(data);
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal membuat draf");
    } finally {
      setLoading(false);
    }
  }

  async function handleDownloadPdf() {
    setPdfLoading(true);
    try {
      const data = buildFormData();
      const res = await generateDraftPdf(data);
      const blob = new Blob([res.html], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal membuat PDF");
    } finally {
      setPdfLoading(false);
    }
  }

  function updateParty(index: number, field: keyof PartyInput, value: string) {
    setParties((prev) => prev.map((p, i) => (i === index ? { ...p, [field]: value } : p)));
  }

  function addParty() {
    setParties((prev) => [...prev, { name: "", role: "counterparty", entity_type: "external", contact_email: "" }]);
  }

  function removeParty(index: number) {
    setParties((prev) => prev.filter((_, i) => i !== index));
  }

  function addKeyTerm() {
    setKeyTerms((prev) => [...prev, { key: "", value: "" }]);
  }

  function removeKeyTerm(index: number) {
    setKeyTerms((prev) => prev.filter((_, i) => i !== index));
  }

  function renderDraftLine(line: string, i: number) {
    if (line.startsWith("# ")) return <h1 key={i} className="text-xl font-bold text-gray-900 mb-4">{line.slice(2)}</h1>;
    if (line.startsWith("## ")) return <h2 key={i} className="text-base font-semibold text-gray-800 mt-6 mb-2 border-b pb-1">{line.slice(3)}</h2>;
    if (line.startsWith("- ")) return <div key={i} className="text-sm text-gray-700 ml-4 mb-1">{line.slice(2)}</div>;
    if (line.trim() === "") return <div key={i} className="h-2" />;
    return <p key={i} className="text-sm text-gray-700">{line}</p>;
  }

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Buat Draf Kontrak</h1>

      <div className="space-y-6">
        {/* Contract Type */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-sm font-medium text-gray-700 mb-3">Tipe Kontrak</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {CONTRACT_TYPES.map((ct) => (
              <button
                key={ct.value}
                onClick={() => setContractType(ct.value)}
                className={`px-3 py-2 rounded-lg text-sm border transition-colors ${
                  contractType === ct.value
                    ? "border-blue-500 bg-blue-50 text-blue-700 font-medium"
                    : "border-gray-200 text-gray-600 hover:bg-gray-50"
                }`}
              >
                {ct.label}
              </button>
            ))}
          </div>
        </div>

        {/* Parties */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-gray-700">Para Pihak</h2>
            <button onClick={addParty} className="text-xs text-blue-600 hover:underline">+ Tambah Pihak</button>
          </div>
          <div className="space-y-3">
            {parties.map((party, i) => (
              <div key={i} className="grid grid-cols-12 gap-2 items-start">
                <input
                  className="col-span-4 border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  placeholder="Nama pihak"
                  value={party.name}
                  onChange={(e) => updateParty(i, "name", e.target.value)}
                />
                <select
                  className="col-span-2 border border-gray-300 rounded-lg px-2 py-2 text-sm"
                  value={party.role}
                  onChange={(e) => updateParty(i, "role", e.target.value)}
                >
                  {PARTY_ROLES.map((r) => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </select>
                <select
                  className="col-span-2 border border-gray-300 rounded-lg px-2 py-2 text-sm"
                  value={party.entity_type}
                  onChange={(e) => updateParty(i, "entity_type", e.target.value)}
                >
                  {ENTITY_TYPES.map((et) => (
                    <option key={et.value} value={et.value}>{et.label}</option>
                  ))}
                </select>
                <input
                  className="col-span-3 border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  placeholder="Email (opsional)"
                  value={party.contact_email}
                  onChange={(e) => updateParty(i, "contact_email", e.target.value)}
                />
                {parties.length > 1 && (
                  <button onClick={() => removeParty(i)} className="col-span-1 text-red-400 hover:text-red-600 py-2 text-center">x</button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Key Terms */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-gray-700">Ketentuan Utama</h2>
            <button onClick={addKeyTerm} className="text-xs text-blue-600 hover:underline">+ Tambah</button>
          </div>
          <div className="space-y-2">
            {keyTerms.map((term, i) => (
              <div key={i} className="flex gap-2 items-center">
                <input
                  className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  placeholder="Nama (misal: value, duration)"
                  value={term.key}
                  onChange={(e) =>
                    setKeyTerms((prev) => prev.map((t, j) => (j === i ? { ...t, key: e.target.value } : t)))
                  }
                />
                <input
                  className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  placeholder="Nilai (misal: 500000000, 12 bulan)"
                  value={term.value}
                  onChange={(e) =>
                    setKeyTerms((prev) => prev.map((t, j) => (j === i ? { ...t, value: e.target.value } : t)))
                  }
                />
                {keyTerms.length > 1 && (
                  <button onClick={() => removeKeyTerm(i)} className="text-red-400 hover:text-red-600">x</button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Language + Generate */}
        <div className="flex items-center gap-4">
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value as "id" | "en")}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
          >
            <option value="id">Bahasa Indonesia</option>
            <option value="en">English</option>
          </select>
          <button
            onClick={handleGenerate}
            disabled={loading || parties.filter((p) => p.name.trim()).length < 1}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Membuat draf..." : "Buat Draf"}
          </button>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">{error}</div>
        )}

        {/* Result preview */}
        {result && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Pratinjau Draf</h2>
              <div className="flex gap-2">
                <button
                  onClick={handleDownloadPdf}
                  disabled={pdfLoading}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50"
                >
                  {pdfLoading ? "Membuat PDF..." : "Buka sebagai PDF"}
                </button>
              </div>
            </div>
            <div className="p-6">
              {/* Safe text-based rendering of draft markdown */}
              <div className="prose prose-sm max-w-none">
                {result.draft_text.split("\n").map((line, i) => renderDraftLine(line, i))}
              </div>

              {/* Risk assessment */}
              {result.risk_assessment.length > 0 && (
                <div className="mt-8 border-t pt-6">
                  <h3 className="text-sm font-medium text-gray-700 mb-3">Penilaian Risiko</h3>
                  {result.risk_assessment.map((ra, i) => (
                    <div key={i} className="bg-orange-50 border-l-4 border-orange-400 rounded px-4 py-2 mb-2 text-sm">
                      {ra.clause && <span className="font-medium">{ra.clause}: </span>}
                      {ra.notes || ra.issue || ""}
                      {ra.suggestion && <span className="italic text-gray-500"> — {ra.suggestion}</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify the build compiles**

Run:
```bash
cd web && npm run build 2>&1 | tail -20
```

Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add web/src/app/\(dashboard\)/contracts/draft/page.tsx
git commit -m "feat(web): add draft generator page with form, preview, and PDF export"
```

---

## Task 6: Sidebar Navigation Update

**Files:**
- Modify: `web/src/components/shared/sidebar.tsx`

- [ ] **Step 1: Add "Buat Draf" link to the sidebar**

In `web/src/components/shared/sidebar.tsx`, the "Contract Management" items array (lines 20-24) currently is:

```typescript
items: [
  { href: "/contracts", label: "Kontrak", icon: "📋" },
  { href: "/obligations", label: "Kewajiban", icon: "⏰" },
  { href: "/approve", label: "Persetujuan", icon: "✍️" },
],
```

Change it to:

```typescript
items: [
  { href: "/contracts", label: "Kontrak", icon: "📋" },
  { href: "/contracts/draft", label: "Buat Draf", icon: "📝" },
  { href: "/obligations", label: "Kewajiban", icon: "⏰" },
  { href: "/approve", label: "Persetujuan", icon: "✍️" },
],
```

- [ ] **Step 2: Verify the build compiles**

Run:
```bash
cd web && npm run build 2>&1 | tail -20
```

Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add web/src/components/shared/sidebar.tsx
git commit -m "feat(web): add draft generator link to sidebar navigation"
```

---

## Task 7: Lint Check and Full Test Run

**Files:** None (verification only)

- [ ] **Step 1: Run ruff on all Python files**

Run:
```bash
ruff check packages/ services/ scripts/ corpus/scripts/
ruff format --check packages/ services/ scripts/ corpus/scripts/
```

Expected: 0 errors, 0 format issues

- [ ] **Step 2: Run all service tests**

Run:
```bash
for svc in extraction-agent legal-research-agent comparison-agent reporting-agent api-gateway batch-engine email-ingest regulation-monitor gemini-agent; do
  echo "=== $svc ===" && PYTHONPATH=packages/ancol-common/src:services/$svc/src python3 -m pytest services/$svc/tests/ -q
done
```

Expected: 264+ tests pass (original 264 + new contract PDF tests)

- [ ] **Step 3: Verify frontend builds cleanly**

Run:
```bash
cd web && npm run build
```

Expected: Build succeeds with no errors

- [ ] **Step 4: Final commit if any lint fixes were needed**

```bash
# Only if ruff auto-fixed anything:
ruff format packages/ services/ scripts/ corpus/scripts/
git add -A && git commit -m "style: ruff format fixes"
```

---

## Summary

| Task | What it does | Tests added |
|------|-------------|-------------|
| 1 | Contract PDF HTML generator (`drafting/pdf.py`) | 8 tests |
| 2 | PDF generation API endpoint (`POST /drafting/pdf`) | 2 tests |
| 3 | Frontend types + API client updates | — |
| 4 | Contract detail page (`/contracts/[id]`) | — |
| 5 | Draft generator page (`/contracts/draft`) | — |
| 6 | Sidebar navigation update | — |
| 7 | Lint + full test verification | — |

**Total new tests:** 10
**Total files created:** 4
**Total files modified:** 5

Confidence: 97%
Verification passes: 2
[Fixed between passes: removed dangerouslySetInnerHTML from draft preview, replaced with safe text-based rendering. Added html.escape() to all dynamic values in PDF HTML generator.]
