"""Pure BJR readiness score formula.

Consumers pass in a list of (item_code, status) pairs; the scorer returns
corporate/regional/readiness scores plus the Gate 5 unlockability flag.
Kept dependency-free so it can be unit-tested without a database or Gemini.
"""

from __future__ import annotations

from dataclasses import dataclass

from ancol_common.schemas.bjr import (
    CORPORATE_ITEMS,
    CRITICAL_ITEMS,
    REGIONAL_ITEMS,
    BJRItemCode,
    ChecklistItemStatus,
)

# Scoring weights
_ITEM_SCORE_BY_STATUS: dict[str, int] = {
    ChecklistItemStatus.SATISFIED.value: 100,
    ChecklistItemStatus.WAIVED.value: 100,  # explicit waiver counts as satisfied
    ChecklistItemStatus.IN_PROGRESS.value: 50,
    ChecklistItemStatus.NOT_STARTED.value: 0,
    ChecklistItemStatus.FLAGGED.value: 0,
}

_CRITICAL_WEIGHT = 2
_NORMAL_WEIGHT = 1


@dataclass(frozen=True)
class ChecklistSnapshot:
    """A single item observation fed to the scorer."""

    item_code: str
    status: str


@dataclass(frozen=True)
class BJRScoreResult:
    """Output of `compute_scores` — shape mirrors the BJRReadinessScore schema."""

    bjr_readiness_score: float
    corporate_compliance_score: float
    regional_compliance_score: float
    satisfied_count: int
    flagged_count: int
    gate_5_unlockable: bool


def item_score(status: str) -> int:
    """Map a checklist item status to a 0-100 score."""
    return _ITEM_SCORE_BY_STATUS.get(status, 0)


def _weighted_avg(items: list[ChecklistSnapshot], scope: frozenset[str]) -> float:
    """Weighted mean of item scores within a regime scope (CRITICAL items = 2x).

    Returns 0.0 if no items fall in the scope.
    """
    numerator = 0
    denominator = 0
    for item in items:
        if item.item_code not in scope:
            continue
        weight = _CRITICAL_WEIGHT if item.item_code in CRITICAL_ITEMS else _NORMAL_WEIGHT
        numerator += item_score(item.status) * weight
        denominator += 100 * weight
    if denominator == 0:
        return 0.0
    return round(numerator / denominator * 100, 2)


def compute_scores(
    items: list[ChecklistSnapshot],
    gate_5_threshold: float = 85.0,
) -> BJRScoreResult:
    """Compute corporate, regional, and overall BJR readiness scores.

    The overall readiness score is `min(corporate, regional)` — encoding the
    dual-regime rule that a decision passing corporate compliance but failing
    regional finance compliance is NOT BJR-protected.

    Gate 5 unlock requires BOTH (readiness >= threshold) AND (no CRITICAL
    item in flagged state).
    """
    corporate_score = _weighted_avg(items, CORPORATE_ITEMS)
    regional_score = _weighted_avg(items, REGIONAL_ITEMS)
    readiness = round(min(corporate_score, regional_score), 2)

    satisfied = sum(
        1
        for i in items
        if i.status in {ChecklistItemStatus.SATISFIED.value, ChecklistItemStatus.WAIVED.value}
    )
    flagged = sum(1 for i in items if i.status == ChecklistItemStatus.FLAGGED.value)
    critical_flagged = any(
        i.item_code in CRITICAL_ITEMS and i.status == ChecklistItemStatus.FLAGGED.value
        for i in items
    )
    gate_5_unlockable = (readiness >= gate_5_threshold) and not critical_flagged

    return BJRScoreResult(
        bjr_readiness_score=readiness,
        corporate_compliance_score=corporate_score,
        regional_compliance_score=regional_score,
        satisfied_count=satisfied,
        flagged_count=flagged,
        gate_5_unlockable=gate_5_unlockable,
    )


def all_item_codes() -> list[str]:
    """Return the 16 stable item codes in checklist order."""
    return [code.value for code in BJRItemCode]
