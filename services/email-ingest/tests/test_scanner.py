"""Tests for email scanner logic."""

from __future__ import annotations

from email_ingest.scanner import (
    _detect_mom_type,
    _extract_meeting_date,
    _get_content_type,
    _is_mom_attachment,
)


class TestFilenameDetection:
    """Tests for MoM filename pattern matching."""

    def test_risalah_pdf(self):
        assert _is_mom_attachment("Risalah Rapat BOD 2026.pdf", "application/pdf")

    def test_notulen_docx(self):
        assert _is_mom_attachment(
            "Notulen_Direksi_Jan2026.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    def test_minutes_pdf(self):
        assert _is_mom_attachment("Minutes_of_Meeting.pdf", "application/pdf")

    def test_rups_scan(self):
        assert _is_mom_attachment("RUPST_2026_scan.pdf", "application/pdf")

    def test_non_mom_pdf(self):
        assert not _is_mom_attachment("Financial_Report_Q1.pdf", "application/pdf")

    def test_non_mom_spreadsheet(self):
        assert not _is_mom_attachment(
            "data.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_image_mom(self):
        assert _is_mom_attachment("Risalah_Rapat.jpg", "image/jpeg")

    def test_rejected_mimetype(self):
        assert not _is_mom_attachment("Risalah.zip", "application/zip")


class TestMomTypeDetection:
    """Tests for MoM type detection from subject/filename."""

    def test_regular(self):
        assert _detect_mom_type("Risalah Rapat Direksi", "rapat.pdf") == "regular"

    def test_circular(self):
        assert _detect_mom_type("Keputusan Sirkuler Direksi", "sirkuler.pdf") == "circular"

    def test_extraordinary(self):
        assert _detect_mom_type("RUPSLB 2026", "rupslb.pdf") == "extraordinary"

    def test_luar_biasa(self):
        assert _detect_mom_type("Rapat Luar Biasa", "rapat.pdf") == "extraordinary"


class TestMeetingDateExtraction:
    """Tests for meeting date extraction from email subjects."""

    def test_iso_date(self):
        assert _extract_meeting_date("Risalah Rapat 2026-01-15") == "2026-01-15"

    def test_indonesian_date(self):
        assert _extract_meeting_date("Risalah Rapat 15 Januari 2026") == "2026-01-15"

    def test_indonesian_date_december(self):
        assert _extract_meeting_date("Notulen 3 Desember 2025") == "2025-12-03"

    def test_no_date(self):
        assert _extract_meeting_date("Risalah Rapat Direksi") is None

    def test_mixed_text(self):
        result = _extract_meeting_date("FW: Risalah Rapat BOD 20 Maret 2026 — Final")
        assert result == "2026-03-20"


class TestContentType:
    """Tests for content type detection from filename."""

    def test_pdf(self):
        assert _get_content_type("Risalah.pdf") == "application/pdf"

    def test_docx(self):
        expected = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert _get_content_type("Notulen.docx") == expected

    def test_jpg(self):
        assert _get_content_type("scan.jpg") == "image/jpeg"

    def test_tiff(self):
        assert _get_content_type("scan.tiff") == "image/tiff"

    def test_unknown_extension_defaults_to_pdf(self):
        assert _get_content_type("file.xyz") == "application/pdf"

    def test_no_extension_defaults_to_pdf(self):
        assert _get_content_type("noext") == "application/pdf"
