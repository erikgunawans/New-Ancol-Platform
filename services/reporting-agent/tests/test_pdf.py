"""Tests for PDF/HTML report generation."""

from __future__ import annotations

from ancol_common.schemas.reporting import ComplianceScorecard
from reporting_agent.generators.pdf import generate_report_html


def _make_scorecard() -> ComplianceScorecard:
    return ComplianceScorecard(
        structural_score=85.0,
        substantive_score=90.0,
        regulatory_score=75.0,
        composite_score=83.5,
    )


def test_html_contains_scores():
    html = generate_report_html(
        document_id="test-001",
        meeting_date="2025-05-13",
        meeting_number="DIR/RR/005/V/2025",
        scorecard=_make_scorecard(),
        findings=[],
        corrective_suggestions=[],
        executive_summary="Ini adalah ringkasan eksekutif.",
    )
    assert "85" in html  # structural
    assert "90" in html  # substantive
    assert "75" in html  # regulatory
    assert "83" in html  # composite (rounded display)


def test_html_contains_metadata():
    html = generate_report_html(
        document_id="test-001",
        meeting_date="2025-05-13",
        meeting_number="DIR/RR/005/V/2025",
        scorecard=_make_scorecard(),
        findings=[],
        corrective_suggestions=[],
        executive_summary="Test summary.",
    )
    assert "DIR/RR/005/V/2025" in html
    assert "2025-05-13" in html
    assert "test-001" in html


def test_html_contains_findings():
    findings = [
        {
            "severity": "critical",
            "title": "Kuorum tidak terpenuhi",
            "resolution_number": "1",
            "regulation_id": "UU-PT-40-2007",
            "description": "Hanya 1 dari 5 Direksi hadir",
            "chain_of_thought": "Test reasoning",
        }
    ]
    html = generate_report_html(
        document_id="test-001",
        meeting_date="2025-05-13",
        meeting_number="DIR/RR/005",
        scorecard=_make_scorecard(),
        findings=findings,
        corrective_suggestions=[],
        executive_summary="Summary",
    )
    assert "CRITICAL" in html
    assert "Kuorum tidak terpenuhi" in html


def test_html_structure():
    html = generate_report_html(
        document_id="test-001",
        meeting_date="2025-05-13",
        meeting_number="DIR/RR/005",
        scorecard=_make_scorecard(),
        findings=[],
        corrective_suggestions=[],
        executive_summary="Summary",
    )
    assert "<!DOCTYPE html>" in html
    assert "</html>" in html
    assert "Scorecard Kepatuhan" in html
    assert "Ringkasan Eksekutif" in html
