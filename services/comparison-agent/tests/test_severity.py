"""Tests for severity classification and scoring."""

from __future__ import annotations

from ancol_common.schemas.mom import FindingSeverity
from comparison_agent.analyzers.severity import (
    classify_severity,
    compute_regulatory_score,
    compute_substantive_score,
)


def test_classify_critical():
    assert classify_severity("quorum_not_met") == FindingSeverity.CRITICAL
    assert classify_severity("circular_not_unanimous") == FindingSeverity.CRITICAL
    assert classify_severity("coi_no_abstention") == FindingSeverity.CRITICAL


def test_classify_high():
    assert classify_severity("rpt_detected") == FindingSeverity.HIGH
    assert classify_severity("no_signatures") == FindingSeverity.HIGH


def test_classify_medium():
    assert classify_severity("insufficient_signatures") == FindingSeverity.MEDIUM
    assert classify_severity("rpt_keyword_detected") == FindingSeverity.MEDIUM


def test_classify_low():
    assert classify_severity("formatting_deviation") == FindingSeverity.LOW


def test_classify_unknown_defaults_medium():
    assert classify_severity("some_unknown_type") == FindingSeverity.MEDIUM


def test_regulatory_score_no_findings():
    assert compute_regulatory_score([]) == 100.0


def test_regulatory_score_one_critical():
    findings = [{"severity": "critical"}]
    score = compute_regulatory_score(findings)
    assert score == 75.0  # 100 - 25


def test_regulatory_score_critical_capped():
    findings = [{"severity": "critical"}] * 5
    score = compute_regulatory_score(findings)
    assert score == 50.0  # 100 - 50 (capped)


def test_regulatory_score_mixed():
    findings = [
        {"severity": "critical"},
        {"severity": "high"},
        {"severity": "medium"},
        {"severity": "low"},
    ]
    score = compute_regulatory_score(findings)
    # 100 - 25(critical) - 10(high) - 5(medium) - 2(low) = 58
    assert score == 58.0


def test_substantive_score_all_consistent():
    checks = [
        {"is_consistent": True},
        {"is_consistent": True},
    ]
    assert compute_substantive_score(checks) == 100.0


def test_substantive_score_one_inconsistent():
    checks = [
        {"is_consistent": True},
        {"is_consistent": False},
    ]
    assert compute_substantive_score(checks) == 85.0  # 100 - 15


def test_substantive_score_floor():
    checks = [{"is_consistent": False}] * 10
    assert compute_substantive_score(checks) == 0.0
