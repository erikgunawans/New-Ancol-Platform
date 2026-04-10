"""Compliance scorecard calculation.

Three-pillar scoring: structural (30%) + substantive (35%) + regulatory (35%).
"""

from __future__ import annotations

from ancol_common.schemas.reporting import ComplianceScorecard


def compute_scorecard(
    structural_score: float,
    substantive_score: float,
    regulatory_score: float,
    historical_scores: list[dict] | None = None,
) -> ComplianceScorecard:
    """Compute the three-pillar compliance scorecard.

    Weights: structural=30%, substantive=35%, regulatory=35%
    """
    weights = {"structural": 0.30, "substantive": 0.35, "regulatory": 0.35}

    composite = (
        structural_score * weights["structural"]
        + substantive_score * weights["substantive"]
        + regulatory_score * weights["regulatory"]
    )
    composite = round(composite, 1)

    # Compute trends from historical data
    trend_3m = _compute_trend(composite, historical_scores, months=3)
    trend_6m = _compute_trend(composite, historical_scores, months=6)
    trend_12m = _compute_trend(composite, historical_scores, months=12)

    return ComplianceScorecard(
        structural_score=round(structural_score, 1),
        substantive_score=round(substantive_score, 1),
        regulatory_score=round(regulatory_score, 1),
        composite_score=composite,
        weights=weights,
        trend_3m=trend_3m,
        trend_6m=trend_6m,
        trend_12m=trend_12m,
    )


def get_score_grade(score: float) -> str:
    """Convert numeric score to letter grade."""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


def get_score_label(score: float) -> str:
    """Convert numeric score to Bahasa Indonesia label."""
    if score >= 90:
        return "Sangat Baik"
    elif score >= 80:
        return "Baik"
    elif score >= 70:
        return "Cukup"
    elif score >= 60:
        return "Kurang"
    else:
        return "Tidak Memenuhi"


def _compute_trend(
    current: float,
    historical: list[dict] | None,
    months: int,
) -> float | None:
    """Compute score trend over N months."""
    if not historical:
        return None

    relevant = [s for s in historical if s.get("months_ago", 0) <= months]

    if not relevant:
        return None

    avg_historical = sum(s.get("composite_score", 0) for s in relevant) / len(relevant)
    return round(current - avg_historical, 1)
