"""Contract PDF generation using WeasyPrint.

Generates styled A4 HTML for contract drafts, suitable for PDF rendering
via WeasyPrint. Falls back to .html output if WeasyPrint is not installed.

Pattern follows services/reporting-agent/src/reporting_agent/generators/pdf.py.
"""

from __future__ import annotations

import logging
from html import escape

from ancol_common.schemas.contract import ContractClause, RiskLevel
from ancol_common.schemas.drafting import DraftOutput, DraftRequest

logger = logging.getLogger(__name__)

# -- Constants --

TYPE_NAMES: dict[str, str] = {
    "nda": "PERJANJIAN KERAHASIAAN",
    "vendor": "PERJANJIAN PENYEDIAAN JASA",
    "sale_purchase": "PERJANJIAN JUAL BELI",
    "joint_venture": "PERJANJIAN USAHA PATUNGAN",
    "land_lease": "PERJANJIAN SEWA MENYEWA",
    "employment": "PERJANJIAN KERJA",
    "sop_board_resolution": "STANDAR OPERASIONAL PROSEDUR RAPAT",
}

ROLE_NAMES: dict[str, str] = {
    "principal": "PIHAK PERTAMA",
    "counterparty": "PIHAK KEDUA",
    "guarantor": "PENJAMIN",
}

RISK_LABELS: dict[str, str] = {
    "low": "RENDAH",
    "medium": "SEDANG",
    "high": "TINGGI",
}

CONTRACT_CSS = (
    "\n"
    "@page {\n"
    "    size: A4;\n"
    "    margin: 2cm;\n"
    '    @top-center { content: "DRAFT KONTRAK"; font-size: 8pt; color: #999; }\n'
    "    @bottom-center { content: counter(page); font-size: 8pt; }\n"
    "}\n"
    "body {\n"
    "    font-family: 'Noto Sans', Arial, sans-serif;\n"
    "    font-size: 10pt; line-height: 1.6; color: #333;\n"
    "}\n"
    "h1 {\n"
    "    color: #1a237e; font-size: 18pt;\n"
    "    border-bottom: 2px solid #1a237e;\n"
    "    padding-bottom: 5px; text-align: center;\n"
    "}\n"
    "h2 {\n"
    "    color: #283593; font-size: 14pt; margin-top: 20px;\n"
    "    border-bottom: 1px solid #e0e0e0; padding-bottom: 4px;\n"
    "}\n"
    "h3 { color: #3949ab; font-size: 12pt; }\n"
    "table { width: 100%; border-collapse: collapse; margin: 10px 0; }\n"
    "th {\n"
    "    background-color: #1a237e; color: white;\n"
    "    padding: 8px; text-align: left; font-size: 9pt;\n"
    "}\n"
    "td {\n"
    "    padding: 6px 8px;\n"
    "    border-bottom: 1px solid #e0e0e0; font-size: 9pt;\n"
    "}\n"
    "tr:nth-child(even) { background-color: #f5f5f5; }\n"
    ".clause-box {\n"
    "    border: 1px solid #e0e0e0; border-radius: 4px;\n"
    "    padding: 12px; margin: 10px 0;\n"
    "    page-break-inside: avoid;\n"
    "}\n"
    ".clause-header {\n"
    "    display: flex; justify-content: space-between;\n"
    "    align-items: center; margin-bottom: 8px;\n"
    "}\n"
    ".clause-title { font-weight: bold; color: #1a237e; font-size: 11pt; }\n"
    ".badge {\n"
    "    display: inline-block; padding: 2px 8px;\n"
    "    border-radius: 12px; font-size: 8pt; font-weight: bold;\n"
    "}\n"
    ".badge-low { background-color: #e8f5e9; color: #2e7d32; }\n"
    ".badge-medium { background-color: #fff3e0; color: #ef6c00; }\n"
    ".badge-high { background-color: #ffebee; color: #c62828; }\n"
    ".clause-text { font-size: 10pt; line-height: 1.5; }\n"
    ".risk-section { margin-top: 20px; }\n"
    ".risk-item {\n"
    "    border-left: 3px solid #ef6c00; padding: 8px 12px;\n"
    "    margin: 8px 0; background-color: #fff8e1;\n"
    "}\n"
    ".key-terms-table td:first-child { font-weight: bold; width: 30%; }\n"
    ".parties-table td:first-child { font-weight: bold; width: 30%; }\n"
    ".confidence { font-size: 8pt; color: #888; margin-top: 6px; }\n"
)


def _risk_badge(risk_level: RiskLevel | None) -> str:
    """Render a risk-level badge as HTML."""
    if risk_level is None:
        return ""
    label = escape(RISK_LABELS.get(risk_level.value, risk_level.value.upper()))
    css_class = f"badge badge-{risk_level.value}"
    return f'<span class="{css_class}">{label}</span>'


def _render_clause(clause: ContractClause) -> str:
    """Render a single clause box."""
    badge = _risk_badge(clause.risk_level)
    risk_reason = ""
    if clause.risk_reason:
        risk_reason = (
            f'<div style="font-size:8pt;color:#666;margin-top:4px;">'
            f"<em>{escape(clause.risk_reason)}</em></div>"
        )

    num = escape(clause.clause_number)
    title = escape(clause.title)
    text = escape(clause.text)
    source = "Perpustakaan Klausul" if clause.is_from_library else "Kustom"
    conf_pct = f"{clause.confidence * 100:.0f}%"

    return f"""
    <div class="clause-box">
        <div class="clause-header">
            <span class="clause-title">{num} &mdash; {title}</span>
            {badge}
        </div>
        <div class="clause-text">{text}</div>
        {risk_reason}
        <div class="confidence">Sumber: {source} | Kepercayaan: {conf_pct}</div>
    </div>"""


def _render_parties_table(request: DraftRequest) -> str:
    """Render the parties table."""
    rows = ""
    for party in request.parties:
        role_label = escape(ROLE_NAMES.get(party.role, party.role.upper()))
        entity_note = " (pihak berelasi)" if party.entity_type == "related_party" else ""
        rows += (
            f"<tr>"
            f"<td>{role_label}</td>"
            f"<td>{escape(party.name)}{escape(entity_note)}</td>"
            f"<td>{escape(party.entity_type)}</td>"
            f"</tr>\n"
        )

    return f"""
    <table class="parties-table">
        <tr><th>Peran</th><th>Nama</th><th>Tipe</th></tr>
        {rows}
    </table>"""


def _render_key_terms(key_terms: dict) -> str:
    """Render key terms as a table."""
    if not key_terms:
        return "<p>Tidak ada ketentuan utama.</p>"

    rows = ""
    for key, value in key_terms.items():
        rows += f"<tr><td>{escape(str(key))}</td><td>{escape(str(value))}</td></tr>\n"

    return f"""
    <table class="key-terms-table">
        <tr><th>Ketentuan</th><th>Nilai</th></tr>
        {rows}
    </table>"""


def _render_risk_assessment(risk_assessment: list[dict]) -> str:
    """Render the risk assessment section."""
    if not risk_assessment:
        return "<p>Tidak ada catatan risiko.</p>"

    items = ""
    for item in risk_assessment:
        clause_label = escape(str(item.get("clause", "")))
        category = escape(str(item.get("category", "")))
        notes = escape(str(item.get("notes", item.get("issue", ""))))
        suggestion = item.get("suggestion")

        items += f"""
        <div class="risk-item">
            <strong>{clause_label}</strong> ({category})<br>
            {notes}"""
        if suggestion:
            items += f"<br><em>Saran: {escape(str(suggestion))}</em>"
        items += "\n        </div>"

    return items


def generate_contract_html(request: DraftRequest, output: DraftOutput) -> str:
    """Generate styled A4 HTML for a contract draft.

    All dynamic values are HTML-escaped via ``html.escape()`` to prevent XSS.

    Args:
        request: The original draft request (parties, key terms, contract type).
        output: The generated draft output (clauses, risk assessment).

    Returns:
        A complete HTML5 document string suitable for WeasyPrint PDF rendering.
    """
    contract_title = escape(TYPE_NAMES.get(request.contract_type, "PERJANJIAN"))
    contract_id = escape(output.contract_id)

    parties_table = _render_parties_table(request)
    key_terms_table = _render_key_terms(request.key_terms)

    # Render clauses
    clauses_html = ""
    for clause in output.clauses:
        clauses_html += _render_clause(clause)

    # Render risk assessment
    risk_html = _render_risk_assessment(output.risk_assessment)

    html = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="utf-8">
    <title>{contract_title} &mdash; {contract_id}</title>
    <style>{CONTRACT_CSS}</style>
</head>
<body>
    <h1>{contract_title}</h1>
    <p style="text-align:center;"><strong>PT Pembangunan Jaya Ancol Tbk</strong></p>

    <h2>Informasi Kontrak</h2>
    <table>
        <tr><td><strong>Contract ID</strong></td><td>{contract_id}</td></tr>
        <tr><td><strong>Jenis Kontrak</strong></td><td>{contract_title}</td></tr>
        <tr><td><strong>Bahasa</strong></td><td>{escape(request.language)}</td></tr>
    </table>

    <h2>Para Pihak</h2>
    {parties_table}

    <h2>Ketentuan Utama</h2>
    {key_terms_table}

    <h2>Pasal-Pasal ({len(output.clauses)} pasal)</h2>
    {clauses_html if output.clauses else "<p>Tidak ada pasal.</p>"}

    <h2>Penilaian Risiko</h2>
    <div class="risk-section">
    {risk_html}
    </div>

    <hr>
    <p style="font-size: 8pt; color: #999;">
        Draft ini dihasilkan oleh Agentic AI Contract Drafting System.
        Seluruh pasal bersifat draft dan memerlukan review oleh tim legal.
    </p>
</body>
</html>"""

    return html


def render_contract_pdf(html: str, output_path: str) -> str:
    """Render HTML to PDF using WeasyPrint.

    Falls back to saving as .html if WeasyPrint is not installed.

    Args:
        html: The HTML string to render.
        output_path: Desired output file path (e.g. ``/tmp/contract.pdf``).

    Returns:
        The actual output file path (may be .html if WeasyPrint is unavailable).
    """
    try:
        from weasyprint import HTML

        HTML(string=html).write_pdf(output_path)
        logger.info("Contract PDF generated: %s", output_path)
        return output_path
    except ImportError:
        logger.warning("WeasyPrint not installed — saving contract as HTML instead")
        html_path = output_path.replace(".pdf", ".html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        return html_path
