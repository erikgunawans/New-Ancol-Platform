"""PDF report generation using WeasyPrint + Jinja2.

Generates board-ready compliance reports in Bahasa Indonesia.
"""

from __future__ import annotations

import logging
from datetime import datetime

from ancol_common.schemas.reporting import ComplianceScorecard, CorrectiveSuggestion

from .scorecard import get_score_grade, get_score_label

logger = logging.getLogger(__name__)

REPORT_CSS = """
@page {
    size: A4;
    margin: 2cm;
    @top-center { content: "LAPORAN KEPATUHAN RISALAH RAPAT — RAHASIA"; font-size: 8pt; color: #999; }
    @bottom-center { content: "Halaman " counter(page) " dari " counter(pages); font-size: 8pt; }
}
body { font-family: 'Noto Sans', Arial, sans-serif; font-size: 10pt; line-height: 1.5; color: #333; }
h1 { color: #1a237e; font-size: 18pt; border-bottom: 2px solid #1a237e; padding-bottom: 5px; }
h2 { color: #283593; font-size: 14pt; margin-top: 20px; }
h3 { color: #3949ab; font-size: 12pt; }
table { width: 100%; border-collapse: collapse; margin: 10px 0; }
th { background-color: #1a237e; color: white; padding: 8px; text-align: left; font-size: 9pt; }
td { padding: 6px 8px; border-bottom: 1px solid #e0e0e0; font-size: 9pt; }
tr:nth-child(even) { background-color: #f5f5f5; }
.score-card { display: flex; justify-content: space-around; margin: 20px 0; }
.score-pill { text-align: center; padding: 15px; border-radius: 8px; min-width: 120px; }
.score-value { font-size: 24pt; font-weight: bold; }
.score-label { font-size: 9pt; color: #666; margin-top: 5px; }
.grade-a { background-color: #e8f5e9; color: #2e7d32; }
.grade-b { background-color: #e3f2fd; color: #1565c0; }
.grade-c { background-color: #fff3e0; color: #ef6c00; }
.grade-d { background-color: #fce4ec; color: #c62828; }
.grade-f { background-color: #ffebee; color: #b71c1c; }
.severity-critical { color: #b71c1c; font-weight: bold; }
.severity-high { color: #e65100; font-weight: bold; }
.severity-medium { color: #ef6c00; }
.severity-low { color: #2e7d32; }
.finding-box { border: 1px solid #e0e0e0; border-radius: 4px; padding: 10px; margin: 8px 0; }
.finding-box.critical { border-left: 4px solid #b71c1c; }
.finding-box.high { border-left: 4px solid #e65100; }
.cot { background-color: #f5f5f5; padding: 8px; margin: 5px 0; font-size: 9pt; border-radius: 4px; }
"""


def generate_report_html(
    document_id: str,
    meeting_date: str,
    meeting_number: str,
    scorecard: ComplianceScorecard,
    findings: list[dict],
    corrective_suggestions: list[CorrectiveSuggestion],
    executive_summary: str,
) -> str:
    """Generate the full HTML report for PDF rendering."""
    grade = get_score_grade(scorecard.composite_score)
    grade_class = f"grade-{grade.lower()}"
    now = datetime.now().strftime("%d %B %Y, %H:%M WIB")

    # Scorecard section
    scorecard_html = f"""
    <div class="score-card">
        <div class="score-pill {_grade_class(scorecard.structural_score)}">
            <div class="score-value">{scorecard.structural_score:.0f}</div>
            <div class="score-label">Struktural (30%)</div>
        </div>
        <div class="score-pill {_grade_class(scorecard.substantive_score)}">
            <div class="score-value">{scorecard.substantive_score:.0f}</div>
            <div class="score-label">Substantif (35%)</div>
        </div>
        <div class="score-pill {_grade_class(scorecard.regulatory_score)}">
            <div class="score-value">{scorecard.regulatory_score:.0f}</div>
            <div class="score-label">Regulasi (35%)</div>
        </div>
        <div class="score-pill {grade_class}">
            <div class="score-value">{scorecard.composite_score:.0f}</div>
            <div class="score-label">Komposit — {get_score_label(scorecard.composite_score)}</div>
        </div>
    </div>
    """

    # Findings table
    findings_html = ""
    for f in sorted(findings, key=lambda x: _severity_order(x.get("severity", "low"))):
        severity = f.get("severity", "medium")
        severity_class = f"severity-{severity}"
        box_class = f"finding-box {severity}" if severity in ("critical", "high") else "finding-box"
        findings_html += f"""
        <div class="{box_class}">
            <strong class="{severity_class}">[{severity.upper()}]</strong> {f.get("title", "")}
            <br><em>Keputusan: {f.get("resolution_number", "N/A")} | Regulasi: {f.get("regulation_id", "N/A")}</em>
            <p>{f.get("description", "")}</p>
            <div class="cot"><strong>Analisis:</strong> {f.get("chain_of_thought", "")}</div>
        </div>
        """

    # Corrective suggestions
    corrections_html = ""
    for cs in corrective_suggestions:
        corrections_html += f"""
        <div class="finding-box">
            <h3>Temuan: {cs.finding_id}</h3>
            <p><strong>Permasalahan:</strong> {cs.issue_explanation}</p>
            <p><strong>Redaksi Saat Ini:</strong> <em>{cs.current_wording}</em></p>
            <p><strong>Saran Perbaikan:</strong> {cs.suggested_wording}</p>
            <p><em>Dasar Regulasi: {cs.regulatory_basis}</em></p>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="utf-8">
    <title>Laporan Kepatuhan Risalah Rapat — {meeting_number}</title>
    <style>{REPORT_CSS}</style>
</head>
<body>
    <h1>Laporan Kepatuhan Risalah Rapat Direksi</h1>
    <p><strong>PT Pembangunan Jaya Ancol Tbk</strong></p>
    <table>
        <tr><td><strong>Nomor Rapat</strong></td><td>{meeting_number}</td></tr>
        <tr><td><strong>Tanggal Rapat</strong></td><td>{meeting_date}</td></tr>
        <tr><td><strong>Document ID</strong></td><td>{document_id}</td></tr>
        <tr><td><strong>Tanggal Laporan</strong></td><td>{now}</td></tr>
    </table>

    <h2>Ringkasan Eksekutif</h2>
    <p>{executive_summary}</p>

    <h2>Scorecard Kepatuhan</h2>
    {scorecard_html}

    <h2>Temuan Kepatuhan ({len(findings)} temuan)</h2>
    {findings_html if findings else "<p>Tidak ada temuan kepatuhan.</p>"}

    <h2>Saran Perbaikan Redaksi</h2>
    {corrections_html if corrective_suggestions else "<p>Tidak ada saran perbaikan.</p>"}

    <hr>
    <p style="font-size: 8pt; color: #999;">
        Laporan ini dihasilkan oleh Agentic AI MoM Compliance System.
        Temuan bersifat advisory dan memerlukan validasi oleh tim legal dan kepatuhan.
    </p>
</body>
</html>"""

    return html


def render_pdf(html: str, output_path: str) -> str:
    """Render HTML to PDF using WeasyPrint.

    Returns the output path. Falls back to HTML-only if WeasyPrint unavailable.
    """
    try:
        from weasyprint import HTML

        HTML(string=html).write_pdf(output_path)
        logger.info("PDF generated: %s", output_path)
        return output_path
    except ImportError:
        logger.warning("WeasyPrint not installed — saving as HTML instead")
        html_path = output_path.replace(".pdf", ".html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        return html_path


def _grade_class(score: float) -> str:
    grade = get_score_grade(score)
    return f"grade-{grade.lower()}"


def _severity_order(severity: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(severity, 4)
