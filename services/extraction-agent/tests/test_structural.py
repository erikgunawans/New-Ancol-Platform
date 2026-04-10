"""Tests for structural parser and template validation."""

from __future__ import annotations

from ancol_common.schemas.extraction import TemplateConfig
from extraction_agent.parsers.structural import (
    compute_structural_score,
    identify_low_confidence_fields,
)


def _make_template() -> TemplateConfig:
    return TemplateConfig(
        template_id="test-template",
        template_name="Test Regular Meeting",
        mom_type="regular",
        required_sections=["opening", "attendance", "resolutions", "signatures"],
        quorum_rules={"min_percentage": 50, "chairman_required": True},
        signature_rules={"required_signers": ["chairman", "secretary"]},
        field_definitions={},
    )


def test_perfect_score():
    """All required sections present, quorum met, signatures present."""
    output = {
        "sections": [
            {"section_name": "opening"},
            {"section_name": "attendance"},
            {"section_name": "resolutions"},
            {"section_name": "signatures"},
        ],
        "structured_mom": {
            "directors_present": 4,
            "total_directors": 5,
            "chairman": "Budi Karya",
            "meeting_date": "2025-03-20",
            "attendees": [{"name": "Budi"}],
            "resolutions": [{"number": "1", "text": "Approved"}],
            "signers": ["Budi Karya", "Ratna Sari"],
        },
    }
    score, flags = compute_structural_score(output, _make_template())
    assert score >= 90.0, f"Expected >= 90, got {score}"
    assert len(flags) == 0, f"Expected no flags, got {flags}"


def test_missing_section():
    """One required section missing."""
    output = {
        "sections": [
            {"section_name": "opening"},
            {"section_name": "attendance"},
            {"section_name": "signatures"},
            # "resolutions" missing
        ],
        "structured_mom": {
            "directors_present": 3,
            "total_directors": 5,
            "chairman": "Budi",
            "meeting_date": "2025-03-20",
            "attendees": [{"name": "Budi"}],
            "resolutions": [{"number": "1", "text": "OK"}],
            "signers": ["Budi", "Sari"],
        },
    }
    score, flags = compute_structural_score(output, _make_template())
    assert score < 100.0
    section_flags = [f for f in flags if "resolutions" in f.field]
    assert len(section_flags) == 1


def test_quorum_not_met():
    """Quorum not met — should flag as critical."""
    output = {
        "sections": [
            {"section_name": "opening"},
            {"section_name": "attendance"},
            {"section_name": "resolutions"},
            {"section_name": "signatures"},
        ],
        "structured_mom": {
            "directors_present": 1,
            "total_directors": 5,
            "chairman": "Budi",
            "meeting_date": "2025-03-20",
            "attendees": [{"name": "Budi"}],
            "resolutions": [],
            "signers": ["Budi"],
        },
    }
    _score, flags = compute_structural_score(output, _make_template())
    quorum_flags = [f for f in flags if f.field == "quorum"]
    assert len(quorum_flags) == 1
    assert quorum_flags[0].severity == "critical"


def test_no_chairman():
    """Chairman required but not identified."""
    output = {
        "sections": [
            {"section_name": "opening"},
            {"section_name": "attendance"},
            {"section_name": "resolutions"},
            {"section_name": "signatures"},
        ],
        "structured_mom": {
            "directors_present": 4,
            "total_directors": 5,
            "chairman": None,
            "meeting_date": "2025-03-20",
            "attendees": [{"name": "Budi"}],
            "resolutions": [{"number": "1", "text": "OK"}],
            "signers": ["Someone"],
        },
    }
    _score, flags = compute_structural_score(output, _make_template())
    chairman_flags = [f for f in flags if f.field == "chairman"]
    assert len(chairman_flags) == 1


def test_low_confidence_fields():
    """Fields below threshold should be flagged."""
    confidence = {
        "meeting_date": 0.95,
        "chairman": 0.6,
        "resolutions": 0.45,
        "attendees": 0.9,
    }
    low = identify_low_confidence_fields(confidence, threshold=0.8)
    assert "chairman" in low
    assert "resolutions" in low
    assert "meeting_date" not in low
    assert "attendees" not in low


def test_empty_confidence():
    """Empty confidence dict should return empty list."""
    assert identify_low_confidence_fields({}) == []
