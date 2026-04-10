"""Tests for the citation validator — the most critical safety component."""

from __future__ import annotations

from datetime import date

from ancol_common.schemas.legal_research import (
    ApplicableClause,
    CorpusFreshness,
    LegalResearchOutput,
    RegulatoryMapping,
)
from ancol_common.schemas.mom import ProcessingMetadata
from legal_research_agent.retrieval.citation_validator import validate_citations


def _make_clause(
    regulation_id: str = "POJK-42-2020",
    article: str = "Pasal 3",
    text: str = "Perusahaan Terbuka wajib mengumumkan keterbukaan informasi...",
    score: float = 0.85,
    source_id: str = "source-123",
) -> ApplicableClause:
    return ApplicableClause(
        regulation_id=regulation_id,
        article=article,
        clause_text=text,
        effective_date=date(2020, 7, 1),
        source_type="external",
        domain="related_party_transactions",
        retrieval_score=score,
        retrieval_source_id=source_id,
    )


def _make_output(clauses: list[ApplicableClause]) -> LegalResearchOutput:
    return LegalResearchOutput(
        document_id="test-doc",
        extraction_id="test-extraction",
        regulatory_mapping=[
            RegulatoryMapping(
                resolution_number="1",
                resolution_summary="Test resolution",
                regulatory_domains=["related_party_transactions"],
                applicable_clauses=clauses,
            )
        ],
        overlap_flags=[],
        conflict_flags=[],
        corpus_freshness=CorpusFreshness(
            last_updated=date.today(),
            staleness_days=0,
        ),
        processing_metadata=ProcessingMetadata(
            agent_version="0.1.0",
            model_used="gemini-2.5-pro",
        ),
    )


def test_valid_citations_pass():
    """All citations with valid scores and source IDs should pass."""
    output = _make_output(
        [
            _make_clause(score=0.9, source_id="src-1"),
            _make_clause(
                regulation_id="UU-PT-40-2007", article="Pasal 98", score=0.85, source_id="src-2"
            ),
        ]
    )
    result = validate_citations(output)
    assert result.valid is True
    assert result.total_citations == 2
    assert result.valid_citations == 2
    assert result.rejected_citations == 0


def test_phantom_citation_no_source_id():
    """Citation without source ID should be flagged as phantom."""
    output = _make_output(
        [
            _make_clause(source_id=""),  # No source!
        ]
    )
    result = validate_citations(output)
    assert result.valid is False
    assert len(result.phantom_citations) == 1
    assert "No retrieval_source_id" in result.phantom_citations[0]["reason"]


def test_low_score_rejected():
    """Citations below minimum retrieval score should be rejected."""
    output = _make_output(
        [
            _make_clause(score=0.3),  # Below 0.5 threshold
        ]
    )
    result = validate_citations(output)
    assert result.valid is False
    assert len(result.low_score_citations) == 1
    assert result.rejected_citations == 1


def test_empty_clause_text_rejected():
    """Citations with empty or too-short text should be flagged."""
    output = _make_output(
        [
            _make_clause(text=""),  # Empty text
        ]
    )
    result = validate_citations(output)
    assert result.valid is False
    assert len(result.phantom_citations) == 1


def test_mixed_valid_and_invalid():
    """Mix of valid and invalid citations — overall should fail."""
    output = _make_output(
        [
            _make_clause(score=0.9, source_id="src-1"),  # Valid
            _make_clause(score=0.3, source_id="src-2"),  # Low score
            _make_clause(score=0.9, source_id=""),  # No source
        ]
    )
    result = validate_citations(output)
    assert result.valid is False
    assert result.valid_citations == 1
    assert result.rejected_citations == 2


def test_empty_mappings_pass():
    """Output with no mappings should pass (nothing to validate)."""
    output = LegalResearchOutput(
        document_id="test",
        extraction_id="test",
        regulatory_mapping=[],
        overlap_flags=[],
        conflict_flags=[],
        corpus_freshness=CorpusFreshness(last_updated=date.today(), staleness_days=0),
        processing_metadata=ProcessingMetadata(agent_version="0.1.0", model_used="test"),
    )
    result = validate_citations(output)
    assert result.valid is True
    assert result.total_citations == 0
