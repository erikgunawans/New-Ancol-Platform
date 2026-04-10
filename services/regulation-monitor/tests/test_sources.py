"""Tests for regulation source definitions and checker logic."""

from __future__ import annotations

from regulation_monitor.checker import _is_relevant, _parse_indonesian_date
from regulation_monitor.sources import (
    ALL_SOURCES,
    IDX_SOURCE,
    KEMENPAREKRAF_SOURCE,
    KLHK_SOURCE,
    OJK_SOURCE,
    PRIORITY_SOURCES,
)


class TestRegulationSources:
    """Tests for regulation source configuration."""

    def test_all_sources_count(self):
        assert len(ALL_SOURCES) == 5

    def test_priority_sources(self):
        assert len(PRIORITY_SOURCES) == 2
        assert OJK_SOURCE in PRIORITY_SOURCES
        assert IDX_SOURCE in PRIORITY_SOURCES

    def test_ojk_keywords(self):
        assert "emiten" in OJK_SOURCE.keywords
        assert "corporate governance" in OJK_SOURCE.keywords

    def test_idx_keywords(self):
        assert "pencatatan saham" in IDX_SOURCE.keywords

    def test_kemenparekraf_domain(self):
        assert KEMENPAREKRAF_SOURCE.domain == "tourism"

    def test_klhk_domain(self):
        assert KLHK_SOURCE.domain == "environment"

    def test_all_have_base_url(self):
        for source in ALL_SOURCES:
            assert source.base_url.startswith("https://")

    def test_all_have_unique_ids(self):
        ids = [s.source_id for s in ALL_SOURCES]
        assert len(ids) == len(set(ids))


class TestRelevanceFilter:
    """Tests for keyword-based relevance filtering."""

    def test_relevant_ojk(self):
        entry = {"title": "POJK tentang Direksi dan Komisaris Emiten"}
        assert _is_relevant(entry, OJK_SOURCE.keywords)

    def test_irrelevant_ojk(self):
        entry = {"title": "POJK tentang Asuransi Jiwa"}
        assert not _is_relevant(entry, OJK_SOURCE.keywords)

    def test_relevant_idx(self):
        entry = {"title": "Peraturan Pencatatan Saham di Bursa"}
        assert _is_relevant(entry, IDX_SOURCE.keywords)

    def test_relevant_tourism(self):
        entry = {"title": "Standar Usaha Taman Rekreasi"}
        assert _is_relevant(entry, KEMENPAREKRAF_SOURCE.keywords)

    def test_relevant_environment(self):
        entry = {"title": "Pengelolaan Limbah di Kawasan Pesisir"}
        assert _is_relevant(entry, KLHK_SOURCE.keywords)


class TestDateParsing:
    """Tests for Indonesian date parsing."""

    def test_standard_format(self):
        assert _parse_indonesian_date("15 Januari 2026") == "2026-01-15"

    def test_december(self):
        assert _parse_indonesian_date("3 Desember 2025") == "2025-12-03"

    def test_iso_format(self):
        assert _parse_indonesian_date("2026-03-20") == "2026-03-20"

    def test_no_date(self):
        assert _parse_indonesian_date("No date here") is None

    def test_embedded_date(self):
        result = _parse_indonesian_date("Diterbitkan pada 10 Oktober 2025 oleh OJK")
        assert result == "2025-10-10"
