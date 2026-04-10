"""Severity scoring for compliance findings.

Classifies findings as CRITICAL / HIGH / MEDIUM / LOW based on
regulatory impact, financial exposure, and governance implications.
"""

from __future__ import annotations

from ancol_common.schemas.mom import FindingSeverity

# Severity rules by finding characteristics
SEVERITY_RULES: list[dict] = [
    # CRITICAL: Immediate regulatory risk, potential sanctions
    {
        "severity": FindingSeverity.CRITICAL,
        "conditions": [
            "quorum_not_met",
            "circular_not_unanimous",
            "coi_no_abstention",
            "unauthorized_material_transaction",
        ],
        "description": "Immediate regulatory violation risk",
    },
    # HIGH: Significant compliance gap, requires remediation
    {
        "severity": FindingSeverity.HIGH,
        "conditions": [
            "rpt_detected",
            "no_signatures",
            "chairman_absent",
            "quorum_data_missing",
            "missing_required_section",
            "rpt_no_disclosure",
            "rpt_no_fairness_opinion",
        ],
        "description": "Significant compliance gap requiring remediation",
    },
    # MEDIUM: Non-critical but should be addressed
    {
        "severity": FindingSeverity.MEDIUM,
        "conditions": [
            "insufficient_signatures",
            "rpt_keyword_detected",
            "incomplete_attendance_record",
            "missing_dissenting_opinion",
            "late_minutes_distribution",
        ],
        "description": "Non-critical gap, should be addressed",
    },
    # LOW: Best practice recommendations
    {
        "severity": FindingSeverity.LOW,
        "conditions": [
            "formatting_deviation",
            "minor_template_deviation",
            "optional_section_missing",
        ],
        "description": "Best practice recommendation",
    },
]


def classify_severity(flag_type: str) -> FindingSeverity:
    """Classify a red flag type into a severity level."""
    for rule in SEVERITY_RULES:
        if flag_type in rule["conditions"]:
            return rule["severity"]
    return FindingSeverity.MEDIUM  # Default


def compute_regulatory_score(findings: list[dict]) -> float:
    """Compute regulatory compliance score (0-100) from findings.

    Scoring:
    - Start at 100
    - CRITICAL: -25 per finding (capped at -50)
    - HIGH: -10 per finding
    - MEDIUM: -5 per finding
    - LOW: -2 per finding
    - Minimum score: 0
    """
    score = 100.0
    critical_penalty = 0

    for finding in findings:
        severity = finding.get("severity", "medium")

        if severity == "critical":
            critical_penalty += 25
        elif severity == "high":
            score -= 10
        elif severity == "medium":
            score -= 5
        elif severity == "low":
            score -= 2

    # Cap critical penalty at 50
    score -= min(critical_penalty, 50)

    return max(0.0, round(score, 1))


def compute_substantive_score(consistency_checks: list[dict]) -> float:
    """Compute substantive consistency score (0-100).

    Scoring:
    - Start at 100
    - Each inconsistency: -15
    - Minimum score: 0
    """
    score = 100.0
    inconsistent_count = sum(
        1 for check in consistency_checks if not check.get("is_consistent", True)
    )
    score -= inconsistent_count * 15
    return max(0.0, round(score, 1))
