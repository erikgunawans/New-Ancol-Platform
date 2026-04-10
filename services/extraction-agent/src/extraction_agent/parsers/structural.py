"""Structural parser for MoM template validation.

Validates extracted data against the expected MoM template structure,
computes structural compliance score, and flags deviations.
"""

from __future__ import annotations

from ancol_common.schemas.extraction import TemplateConfig
from ancol_common.schemas.mom import DeviationFlag


def compute_structural_score(
    output: dict,
    template: TemplateConfig,
) -> tuple[float, list[DeviationFlag]]:
    """Compute structural compliance score (0-100) and identify deviations.

    Checks:
    1. Required sections present
    2. Quorum rules satisfied
    3. Signature rules satisfied
    4. Required fields populated
    """
    total_checks = 0
    passed_checks = 0
    flags: list[DeviationFlag] = []

    # 1. Required sections
    required_sections = template.required_sections
    found_sections = {s.get("section_name", "") for s in output.get("sections", [])}

    for section in required_sections:
        total_checks += 1
        if section in found_sections:
            passed_checks += 1
        else:
            flags.append(
                DeviationFlag(
                    field=f"section.{section}",
                    expected=f"Section '{section}' required by template",
                    actual=None,
                    severity="high",
                    description=f"Required section '{section}' not found in document",
                )
            )

    # 2. Quorum check
    quorum_rules = template.quorum_rules
    total_checks += 1

    directors_present = output.get("structured_mom", {}).get("directors_present")
    total_directors = output.get("structured_mom", {}).get("total_directors")

    if directors_present is not None and total_directors is not None and total_directors > 0:
        min_percentage = quorum_rules.get("min_percentage", 50)
        actual_percentage = (directors_present / total_directors) * 100

        if actual_percentage >= min_percentage:
            passed_checks += 1
        else:
            flags.append(
                DeviationFlag(
                    field="quorum",
                    expected=f"Minimum {min_percentage}% directors present",
                    actual=f"{actual_percentage:.0f}% ({directors_present}/{total_directors})",
                    severity="critical",
                    description=f"Quorum not met: {directors_present}/{total_directors} directors present ({actual_percentage:.0f}%), minimum {min_percentage}% required",
                )
            )

        # Chairman required check
        if quorum_rules.get("chairman_required", False):
            total_checks += 1
            chairman = output.get("structured_mom", {}).get("chairman")
            if chairman:
                passed_checks += 1
            else:
                flags.append(
                    DeviationFlag(
                        field="chairman",
                        expected="Chairman (Ketua Rapat) must be present",
                        actual=None,
                        severity="high",
                        description="Chairman not identified in meeting",
                    )
                )
    else:
        flags.append(
            DeviationFlag(
                field="quorum",
                expected="Director attendance data required",
                actual=None,
                severity="high",
                description="Cannot verify quorum: missing director count data",
            )
        )

    # 3. Signature check
    signature_rules = template.signature_rules
    total_checks += 1

    signers = output.get("structured_mom", {}).get("signers", [])
    required_signers = signature_rules.get("required_signers", [])

    if signers:
        passed_checks += 1
        if required_signers and "all_present" in required_signers:
            # All present directors must sign
            total_checks += 1
            if len(signers) >= (directors_present or 0):
                passed_checks += 1
            else:
                flags.append(
                    DeviationFlag(
                        field="signatures",
                        expected="All present directors must sign",
                        actual=f"{len(signers)} signers found",
                        severity="high",
                        description="Not all present directors have signed the minutes",
                    )
                )
    else:
        flags.append(
            DeviationFlag(
                field="signatures",
                expected="Signatures required on minutes",
                actual=None,
                severity="medium",
                description="No signers identified in document",
            )
        )

    # 4. Required fields
    required_fields = [
        ("meeting_date", "Tanggal rapat"),
        ("attendees", "Daftar hadir"),
        ("resolutions", "Keputusan rapat"),
    ]

    structured_mom = output.get("structured_mom", {})
    for field_name, label in required_fields:
        total_checks += 1
        value = structured_mom.get(field_name)
        if value and (not isinstance(value, list) or len(value) > 0):
            passed_checks += 1
        else:
            flags.append(
                DeviationFlag(
                    field=field_name,
                    expected=f"{label} is required",
                    actual=None,
                    severity="high",
                    description=f"Required field '{label}' is missing or empty",
                )
            )

    score = (passed_checks / max(total_checks, 1)) * 100
    return round(score, 1), flags


def identify_low_confidence_fields(
    field_confidence: dict[str, float],
    threshold: float = 0.8,
) -> list[str]:
    """Return field names with confidence below threshold."""
    return [field for field, conf in field_confidence.items() if conf < threshold]
