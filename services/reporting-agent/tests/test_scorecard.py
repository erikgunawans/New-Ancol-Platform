"""Tests for scorecard calculation."""

from __future__ import annotations

from reporting_agent.generators.scorecard import (
    compute_scorecard,
    get_score_grade,
    get_score_label,
)


def test_perfect_scores():
    sc = compute_scorecard(100.0, 100.0, 100.0)
    assert sc.composite_score == 100.0
    assert sc.weights == {"structural": 0.30, "substantive": 0.35, "regulatory": 0.35}


def test_weighted_calculation():
    # 80*0.3 + 90*0.35 + 70*0.35 = 24 + 31.5 + 24.5 = 80.0
    sc = compute_scorecard(80.0, 90.0, 70.0)
    assert sc.composite_score == 80.0


def test_zero_scores():
    sc = compute_scorecard(0.0, 0.0, 0.0)
    assert sc.composite_score == 0.0


def test_asymmetric_weights():
    # Structural weighted less (30%) vs substantive+regulatory (70%)
    sc1 = compute_scorecard(0.0, 100.0, 100.0)  # No structural
    sc2 = compute_scorecard(100.0, 0.0, 0.0)  # Only structural
    assert sc1.composite_score == 70.0
    assert sc2.composite_score == 30.0


def test_trends_without_history():
    sc = compute_scorecard(85.0, 90.0, 80.0)
    assert sc.trend_3m is None
    assert sc.trend_6m is None
    assert sc.trend_12m is None


def test_trends_with_history():
    history = [
        {"months_ago": 1, "composite_score": 70.0},
        {"months_ago": 2, "composite_score": 75.0},
    ]
    sc = compute_scorecard(85.0, 90.0, 80.0, historical_scores=history)
    # Current composite = 85*0.3 + 90*0.35 + 80*0.35 = 25.5+31.5+28 = 85.0
    # Avg historical (3m) = (70+75)/2 = 72.5
    # Trend = 85.0 - 72.5 = 12.5
    assert sc.trend_3m == 12.5


def test_grade_a():
    assert get_score_grade(95) == "A"
    assert get_score_grade(90) == "A"


def test_grade_b():
    assert get_score_grade(85) == "B"
    assert get_score_grade(80) == "B"


def test_grade_c():
    assert get_score_grade(75) == "C"


def test_grade_d():
    assert get_score_grade(65) == "D"


def test_grade_f():
    assert get_score_grade(50) == "F"


def test_labels():
    assert get_score_label(95) == "Sangat Baik"
    assert get_score_label(85) == "Baik"
    assert get_score_label(75) == "Cukup"
    assert get_score_label(65) == "Kurang"
    assert get_score_label(50) == "Tidak Memenuhi"
