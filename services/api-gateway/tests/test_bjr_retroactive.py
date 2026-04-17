"""Tests for the retroactive bundler — MoM → proposed Decision."""

from __future__ import annotations

from ancol_common.bjr.retroactive import (
    ProposedCandidate,
    ProposedDecisionDraft,
    _draft_title_and_type,
)


class _MockDocument:
    def __init__(self, filename: str, meeting_date=None, created_at=None):
        self.filename = filename
        self.meeting_date = meeting_date
        self.created_at = created_at


class _MockExtraction:
    def __init__(self, structured_mom: dict):
        self.structured_mom = structured_mom


class TestInitiativeTypeClassification:
    """The keyword heuristic classifies MoMs into initiative types."""

    def test_investment_keyword(self):
        doc = _MockDocument("mom-2026-06.pdf")
        ext = _MockExtraction({"agenda_items": ["Persetujuan investasi capex wahana baru"]})
        _, _, itype = _draft_title_and_type(doc, ext)
        assert itype == "investment"

    def test_partnership_keyword(self):
        doc = _MockDocument("mom-2026-04.pdf")
        ext = _MockExtraction({"agenda_items": ["Pembahasan joint venture hotel Ancol Beach City"]})
        _, _, itype = _draft_title_and_type(doc, ext)
        assert itype == "partnership"

    def test_major_contract_keyword(self):
        doc = _MockDocument("mom-2026-08.pdf")
        ext = _MockExtraction(
            {"agenda_items": ["Penandatanganan kontrak vendor IT transformation"]}
        )
        _, _, itype = _draft_title_and_type(doc, ext)
        assert itype == "major_contract"

    def test_divestment_keyword(self):
        doc = _MockDocument("mom-2026-09.pdf")
        ext = _MockExtraction({"agenda_items": ["Divestasi anak perusahaan non-inti"]})
        _, _, itype = _draft_title_and_type(doc, ext)
        assert itype == "divestment"

    def test_rups_keyword(self):
        doc = _MockDocument("mom-2026-03.pdf")
        ext = _MockExtraction({"agenda_items": ["Persiapan RUPS tahunan: pembagian dividen"]})
        _, _, itype = _draft_title_and_type(doc, ext)
        assert itype == "rups_item"

    def test_unknown_defaults_to_investment(self):
        doc = _MockDocument("mom-2026-05.pdf")
        ext = _MockExtraction({"agenda_items": ["Pembahasan operasional rutin"]})
        _, _, itype = _draft_title_and_type(doc, ext)
        # No strong signal — defaults to investment
        assert itype in ("investment", "major_contract", "partnership")


class TestDraftTitleExtraction:
    def test_uses_first_agenda_item(self):
        doc = _MockDocument("mom-2026.pdf")
        ext = _MockExtraction(
            {"agenda_items": ["Persetujuan investasi Dufan refurb", "Progress update"]}
        )
        title, desc, _ = _draft_title_and_type(doc, ext)
        assert "Dufan refurb" in title
        assert "Persetujuan investasi Dufan refurb" in desc

    def test_falls_back_to_filename(self):
        doc = _MockDocument("mom-2026-05.pdf")
        ext = _MockExtraction({"agenda_items": []})
        title, _, _ = _draft_title_and_type(doc, ext)
        assert title == "mom-2026-05.pdf"

    def test_handles_missing_extraction(self):
        doc = _MockDocument("mom-2026-05.pdf")
        title, desc, _itype = _draft_title_and_type(doc, None)
        assert title == "mom-2026-05.pdf"
        assert desc == "Auto-bundled from MoM document."

    def test_truncates_long_title(self):
        doc = _MockDocument("mom.pdf")
        long_agenda = "A" * 500
        ext = _MockExtraction({"agenda_items": [long_agenda]})
        title, _, _ = _draft_title_and_type(doc, ext)
        assert len(title) <= 200


class TestProposedDecisionDraftShape:
    def test_dataclass_construction(self):
        draft = ProposedDecisionDraft(
            source_document_id="doc-1",
            proposed_title="Test",
            proposed_description="Test desc",
            proposed_initiative_type="investment",
        )
        assert draft.rkab_candidates == []
        assert draft.rjpp_candidates == []

    def test_candidate_with_confidence(self):
        cand = ProposedCandidate(
            id="rkab-1", code="TP-01", name="Refurb", confidence=0.85, rationale="overlap 3/4"
        )
        assert cand.confidence == 0.85
        assert cand.rationale == "overlap 3/4"
