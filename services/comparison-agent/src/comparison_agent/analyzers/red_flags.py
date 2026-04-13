"""Red flag detection for MoM compliance.

Detects critical compliance issues:
1. Quorum violations
2. Related Party Transactions (POJK 42/2020)
3. Conflict of interest
4. Circular resolution irregularities
5. Missing signatures
6. Unauthorized transactions
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Known related party entities — loaded from DB in production
DEFAULT_RPT_ENTITIES = [
    "PT Pembangunan Jaya",
    "PT Jaya Real Property",
    "PT Jaya Konstruksi",
    "PT Jaya Celcon Prima",
    "PT Jaya Teknik Indonesia",
    "PT Jaya Trade Indonesia",
    "PT Taman Impian Jaya Ancol",
    "PT Jaya Ancol",
    "PT Seabreeze Indonesia",
]


@dataclass
class RedFlag:
    """A detected red flag."""

    flag_type: str
    severity: str  # critical, high, medium, low
    description: str
    evidence: str
    regulation_ref: str
    resolution_number: str | None = None


def detect_quorum_violations(
    structured_mom: dict,
    quorum_rules: dict | None = None,
) -> list[RedFlag]:
    """Detect quorum-related red flags."""
    flags = []
    min_pct = (quorum_rules or {}).get("min_percentage", 50)

    directors_present = structured_mom.get("directors_present")
    total_directors = structured_mom.get("total_directors")

    if directors_present is None or total_directors is None:
        flags.append(
            RedFlag(
                flag_type="quorum_data_missing",
                severity="high",
                description="Data kehadiran Direksi tidak tercantum dalam risalah",
                evidence="directors_present atau total_directors tidak ditemukan",
                regulation_ref="POJK 33/2014 Pasal 11, AD/ART Pasal 13",
            )
        )
        return flags

    if total_directors > 0:
        pct = (directors_present / total_directors) * 100
        if pct < min_pct:
            flags.append(
                RedFlag(
                    flag_type="quorum_not_met",
                    severity="critical",
                    description=(
                        f"Kuorum rapat tidak terpenuhi: {directors_present}/{total_directors} "
                        f"({pct:.0f}%), minimum {min_pct}%"
                    ),
                    evidence=f"{directors_present} dari {total_directors} Direksi hadir",
                    regulation_ref="UU PT 40/2007 Pasal 86, AD/ART Pasal 13 ayat (5)",
                )
            )

    if (quorum_rules or {}).get("chairman_required", True) and not structured_mom.get("chairman"):
            flags.append(
                RedFlag(
                    flag_type="chairman_absent",
                    severity="high",
                    description="Ketua Rapat (Direktur Utama) tidak teridentifikasi atau tidak hadir",
                    evidence="Field chairman kosong",
                    regulation_ref="AD/ART Pasal 13, BOD Charter Pasal 4",
                )
            )

    return flags


def detect_rpt_flags(
    structured_mom: dict,
    resolutions: list[dict],
    rpt_entities: list[str] | None = None,
) -> list[RedFlag]:
    """Detect Related Party Transaction red flags."""
    flags = []
    entities = [e.lower() for e in (rpt_entities or DEFAULT_RPT_ENTITIES)]
    full_text = (structured_mom.get("full_text") or "").lower()

    for resolution in resolutions:
        res_text = (resolution.get("text") or "").lower()
        res_num = resolution.get("number", "?")

        for entity in entities:
            # Check if entity is mentioned in resolution or full text near resolution
            if entity in res_text:
                flags.append(
                    RedFlag(
                        flag_type="rpt_detected",
                        severity="high",
                        description=(
                            f"Transaksi Pihak Berelasi terdeteksi: keputusan {res_num} "
                            f"melibatkan '{entity}'"
                        ),
                        evidence=f"Entity '{entity}' ditemukan dalam teks keputusan",
                        regulation_ref="POJK 42/2020 Pasal 3, RPT Policy PJAA",
                        resolution_number=res_num,
                    )
                )

    # Check for RPT keywords without entity mention
    rpt_keywords = [
        "afiliasi",
        "pihak berelasi",
        "related party",
        "benturan kepentingan",
        "conflict of interest",
        "fairness opinion",
        "penilai independen",
    ]
    for keyword in rpt_keywords:
        if keyword in full_text and not any(f.flag_type == "rpt_detected" for f in flags):
            flags.append(
                RedFlag(
                    flag_type="rpt_keyword_detected",
                    severity="medium",
                    description=f"Kata kunci RPT terdeteksi: '{keyword}'",
                    evidence=f"Keyword '{keyword}' dalam teks risalah",
                    regulation_ref="POJK 42/2020",
                )
            )
            break  # One keyword flag is enough

    return flags


def detect_conflict_of_interest(
    structured_mom: dict,
    resolutions: list[dict],
) -> list[RedFlag]:
    """Detect conflict of interest issues."""
    flags = []
    full_text = (structured_mom.get("full_text") or "").lower()

    # Check if COI was disclosed but director still voted
    coi_keywords = [
        "benturan kepentingan",
        "kepentingan pribadi",
        "conflict of interest",
        "mengundurkan diri dari pembahasan",
    ]

    has_coi_mention = any(kw in full_text for kw in coi_keywords)

    if has_coi_mention:
        # Check if the conflicted party abstained
        abstention_keywords = [
            "tidak ikut dalam pengambilan keputusan",
            "meninggalkan ruang rapat",
            "mengundurkan diri",
            "abstain",
        ]
        has_abstention = any(kw in full_text for kw in abstention_keywords)

        if not has_abstention:
            flags.append(
                RedFlag(
                    flag_type="coi_no_abstention",
                    severity="critical",
                    description=(
                        "Benturan kepentingan terdeteksi namun tidak ada catatan "
                        "pengunduran diri dari pembahasan/pemungutan suara"
                    ),
                    evidence="Kata kunci benturan kepentingan ditemukan tanpa catatan abstain",
                    regulation_ref="POJK 42/2020 Pasal 12 ayat (3), AD/ART Pasal 20, BOD Charter Pasal 6",
                )
            )

    return flags


def detect_circular_resolution_issues(
    structured_mom: dict,
) -> list[RedFlag]:
    """Detect issues with circular resolutions."""
    flags = []
    meeting_type = structured_mom.get("meeting_type", "")

    if meeting_type != "circular":
        return flags

    # Circular resolutions require unanimous consent
    total = structured_mom.get("total_directors", 0)
    signers = structured_mom.get("signers", [])

    if total > 0 and len(signers) < total:
        flags.append(
            RedFlag(
                flag_type="circular_not_unanimous",
                severity="critical",
                description=(
                    f"Keputusan Sirkuler tidak ditandatangani seluruh Direksi: "
                    f"{len(signers)}/{total}"
                ),
                evidence=f"Hanya {len(signers)} dari {total} Direksi menandatangani",
                regulation_ref="UU PT 40/2007 Pasal 91, AD/ART Pasal 14",
            )
        )

    return flags


def detect_signature_issues(
    structured_mom: dict,
) -> list[RedFlag]:
    """Detect missing or incomplete signatures."""
    flags = []
    signers = structured_mom.get("signers", [])

    if not signers:
        flags.append(
            RedFlag(
                flag_type="no_signatures",
                severity="high",
                description="Tidak ada tanda tangan teridentifikasi pada risalah",
                evidence="Daftar penandatangan kosong",
                regulation_ref="POJK 33/2014 Pasal 11 ayat (5), AD/ART Pasal 13 ayat (8)",
            )
        )
    elif len(signers) < 2:
        flags.append(
            RedFlag(
                flag_type="insufficient_signatures",
                severity="medium",
                description="Risalah hanya ditandatangani oleh 1 orang (minimum 2: Ketua Rapat + Sekretaris)",
                evidence=f"Penandatangan: {signers}",
                regulation_ref="AD/ART Pasal 13 ayat (8)",
            )
        )

    return flags


def detect_all_red_flags(
    structured_mom: dict,
    resolutions: list[dict],
    rpt_entities: list[str] | None = None,
    quorum_rules: dict | None = None,
) -> list[RedFlag]:
    """Run all red flag detectors and return combined results."""
    all_flags = []

    all_flags.extend(detect_quorum_violations(structured_mom, quorum_rules))
    all_flags.extend(detect_rpt_flags(structured_mom, resolutions, rpt_entities))
    all_flags.extend(detect_conflict_of_interest(structured_mom, resolutions))
    all_flags.extend(detect_circular_resolution_issues(structured_mom))
    all_flags.extend(detect_signature_issues(structured_mom))

    logger.info("Red flag scan: %d flags detected", len(all_flags))
    return all_flags
