"""Tests for contract PDF HTML generation."""

from __future__ import annotations

from ancol_common.schemas.contract import ContractClause, ContractParty, RiskLevel
from ancol_common.schemas.drafting import DraftOutput, DraftRequest


def _make_request(**kwargs) -> DraftRequest:
    """Build a minimal DraftRequest for testing."""
    defaults = {
        "contract_type": "vendor",
        "parties": [
            ContractParty(name="PT Ancol Tbk", role="principal", entity_type="internal"),
            ContractParty(name="PT Mitra Sejahtera", role="counterparty", entity_type="external"),
        ],
        "key_terms": {"value": "Rp 500.000.000", "duration": "12 bulan"},
        "language": "id",
    }
    defaults.update(kwargs)
    return DraftRequest(**defaults)


def _make_output(**kwargs) -> DraftOutput:
    """Build a minimal DraftOutput for testing."""
    defaults = {
        "contract_id": "contract-test-001",
        "draft_text": "# PERJANJIAN PENYEDIAAN JASA\n\nDraft text here.",
        "clauses": [
            ContractClause(
                clause_number="Pasal 1",
                title="Ruang Lingkup",
                text="Penyedia setuju menyediakan layanan.",
                category="scope",
                risk_level=RiskLevel.LOW,
                risk_reason="Standard scope clause",
            ),
            ContractClause(
                clause_number="Pasal 2",
                title="Pembayaran",
                text="Pembayaran dalam 30 hari.",
                category="payment_terms",
                risk_level=RiskLevel.MEDIUM,
                risk_reason="No late payment penalty specified",
            ),
        ],
        "risk_assessment": [
            {
                "clause": "Pasal 2",
                "category": "payment_terms",
                "notes": "No late payment penalty specified",
            },
        ],
    }
    defaults.update(kwargs)
    return DraftOutput(**defaults)


class TestGenerateContractHtml:
    """Test generate_contract_html produces valid styled HTML."""

    def test_valid_html_output(self):
        """HTML output must be a valid HTML5 document."""
        from ancol_common.drafting.pdf import generate_contract_html

        request = _make_request()
        output = _make_output()
        html = generate_contract_html(request, output)

        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html
        assert "<head>" in html
        assert "<body>" in html
        assert "utf-8" in html

    def test_contract_title(self):
        """HTML must contain the Indonesian contract type name."""
        from ancol_common.drafting.pdf import generate_contract_html

        request = _make_request(contract_type="vendor")
        output = _make_output()
        html = generate_contract_html(request, output)

        assert "PERJANJIAN PENYEDIAAN JASA" in html

    def test_party_names(self):
        """HTML must contain party names with role labels."""
        from ancol_common.drafting.pdf import generate_contract_html

        request = _make_request()
        output = _make_output()
        html = generate_contract_html(request, output)

        assert "PT Ancol Tbk" in html
        assert "PT Mitra Sejahtera" in html
        assert "PIHAK PERTAMA" in html
        assert "PIHAK KEDUA" in html

    def test_clauses_present(self):
        """HTML must render each clause with number and title."""
        from ancol_common.drafting.pdf import generate_contract_html

        request = _make_request()
        output = _make_output()
        html = generate_contract_html(request, output)

        assert "Pasal 1" in html
        assert "Ruang Lingkup" in html
        assert "Pasal 2" in html
        assert "Pembayaran" in html
        assert "Penyedia setuju menyediakan layanan." in html

    def test_risk_assessment_section(self):
        """HTML must include a risk assessment section with notes."""
        from ancol_common.drafting.pdf import generate_contract_html

        request = _make_request()
        output = _make_output()
        html = generate_contract_html(request, output)

        assert "Penilaian Risiko" in html
        assert "No late payment penalty specified" in html

    def test_risk_badges(self):
        """Risk level badges must use Indonesian labels RENDAH/SEDANG/TINGGI."""
        from ancol_common.drafting.pdf import generate_contract_html

        request = _make_request()
        output = _make_output()
        html = generate_contract_html(request, output)

        # LOW -> RENDAH, MEDIUM -> SEDANG
        assert "RENDAH" in html
        assert "SEDANG" in html

    def test_key_terms(self):
        """HTML must display key terms from the request."""
        from ancol_common.drafting.pdf import generate_contract_html

        request = _make_request(key_terms={"value": "Rp 500.000.000", "duration": "12 bulan"})
        output = _make_output()
        html = generate_contract_html(request, output)

        assert "Rp 500.000.000" in html
        assert "12 bulan" in html

    def test_clause_source_label_from_library(self):
        """Clause with is_from_library=True must show 'Perpustakaan Klausul' label."""
        from ancol_common.drafting.pdf import generate_contract_html
        from ancol_common.schemas.contract import ContractClause, RiskLevel

        output = _make_output(
            clauses=[
                ContractClause(
                    clause_number="Pasal 1",
                    title="Kerahasiaan",
                    text="Para pihak setuju menjaga kerahasiaan.",
                    category="confidentiality",
                    risk_level=RiskLevel.LOW,
                    is_from_library=True,
                    confidence=1.0,
                ),
            ]
        )
        html = generate_contract_html(_make_request(), output)

        assert "Perpustakaan Klausul" in html
        assert "Kustom" not in html.split("Perpustakaan Klausul")[1].split("</div>")[0]

    def test_clause_confidence_percentage(self):
        """Each clause must display its confidence as a formatted percentage."""
        from ancol_common.drafting.pdf import generate_contract_html
        from ancol_common.schemas.contract import ContractClause, RiskLevel

        output = _make_output(
            clauses=[
                ContractClause(
                    clause_number="Pasal 1",
                    title="Ruang Lingkup",
                    text="Penyedia setuju menyediakan layanan.",
                    category="scope",
                    risk_level=RiskLevel.LOW,
                    is_from_library=False,
                    confidence=0.85,
                ),
            ]
        )
        html = generate_contract_html(_make_request(), output)

        assert "85%" in html
        assert "Kepercayaan: 85%" in html

    def test_html_escaping(self):
        """Dynamic values must be HTML-escaped to prevent XSS."""
        from ancol_common.drafting.pdf import generate_contract_html

        request = _make_request(
            parties=[
                ContractParty(
                    name='PT <script>alert("xss")</script>',
                    role="principal",
                    entity_type="internal",
                ),
                ContractParty(name="PT Normal", role="counterparty", entity_type="external"),
            ],
            key_terms={"value": '<img onerror="hack" src=x>'},
        )
        output = _make_output()
        html = generate_contract_html(request, output)

        assert "<script>" not in html
        assert "&lt;script&gt;" in html
        assert '<img onerror' not in html
        assert "&lt;img onerror" in html


class TestRenderContractPdf:
    """Test render_contract_pdf with WeasyPrint fallback."""

    def test_weasyprint_fallback(self, tmp_path):
        """When WeasyPrint is not installed, fall back to saving .html."""
        from ancol_common.drafting.pdf import render_contract_pdf

        html = "<html><body>test</body></html>"
        output_path = str(tmp_path / "contract.pdf")
        result = render_contract_pdf(html, output_path)

        # Should fall back to .html since WeasyPrint is likely not installed in test env
        assert result.endswith(".html")
        with open(result) as f:
            assert f.read() == html
