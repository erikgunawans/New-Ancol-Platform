"""Tests for response formatting to Bahasa Indonesia chat text."""

from __future__ import annotations

from gemini_agent.formatting import (
    format_dashboard,
    format_document_status,
    format_scorecard,
)


class TestFormatScorecard:
    def test_basic_scorecard(self):
        data = {
            "structural": 85.0,
            "substantive": 78.0,
            "regulatory": 82.0,
            "composite": 81.5,
        }
        result = format_scorecard(data)
        assert "Scorecard" in result
        assert "85.0%" in result
        assert "78.0%" in result

    def test_scorecard_handles_none(self):
        data = {
            "structural_score": None,
            "substantive_score": None,
            "regulatory_score": None,
            "composite_score": None,
        }
        result = format_scorecard(data)
        assert "0.0%" in result or "Scorecard" in result


class TestFormatDocumentStatus:
    def test_pending_status(self):
        data = {
            "id": "abc-123",
            "filename": "Risalah_Rapat.pdf",
            "status": "pending",
            "mom_type": "regular",
            "created_at": "2026-04-10T10:00:00",
        }
        result = format_document_status(data)
        assert "Risalah_Rapat.pdf" in result
        assert "Menunggu" in result or "pending" in result


class TestFormatDashboard:
    def test_dashboard_stats(self):
        data = {
            "total_documents": 42,
            "pending_review": 5,
            "completed": 30,
            "failed": 2,
            "rejected": 1,
            "avg_composite_score": 78.5,
        }
        result = format_dashboard(data)
        assert "42" in result
        assert "30" in result
