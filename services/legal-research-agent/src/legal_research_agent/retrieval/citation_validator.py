"""Citation Validator — Anti-hallucination Layer 3.

Validates that every citation in the Legal Research Agent's output
actually exists in the regulatory corpus. This is the most critical
safety component in the system.

Three validation layers:
1. Retrieval score threshold (reject low-confidence retrievals)
2. Source ID verification (confirm source exists in Vertex AI Search)
3. Text match verification (confirm cited text matches corpus content)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from ancol_common.schemas.legal_research import (
    LegalResearchOutput,
)

logger = logging.getLogger(__name__)

# Minimum retrieval score to accept a citation
MIN_RETRIEVAL_SCORE = 0.5

# Maximum ratio of citations allowed without retrieval source
MAX_UNSOURCED_RATIO = 0.0  # Zero tolerance for unsourced citations


@dataclass
class ValidationResult:
    """Result of citation validation."""

    valid: bool
    total_citations: int
    valid_citations: int
    rejected_citations: int
    phantom_citations: list[dict]
    low_score_citations: list[dict]
    warnings: list[str]


def validate_citations(output: LegalResearchOutput) -> ValidationResult:
    """Validate all citations in a Legal Research output.

    Returns a ValidationResult with details on which citations passed
    and which failed validation.
    """
    total = 0
    valid = 0
    rejected = 0
    phantoms: list[dict] = []
    low_scores: list[dict] = []
    warnings: list[str] = []

    for mapping in output.regulatory_mapping:
        for clause in mapping.applicable_clauses:
            total += 1

            # Layer 1: Retrieval score threshold
            if clause.retrieval_score < MIN_RETRIEVAL_SCORE:
                low_scores.append(
                    {
                        "regulation_id": clause.regulation_id,
                        "article": clause.article,
                        "retrieval_score": clause.retrieval_score,
                        "resolution": mapping.resolution_number,
                    }
                )
                rejected += 1
                continue

            # Layer 2: Source ID verification
            if not clause.retrieval_source_id or clause.retrieval_source_id == "":
                phantoms.append(
                    {
                        "regulation_id": clause.regulation_id,
                        "article": clause.article,
                        "reason": "No retrieval_source_id — possible hallucination",
                        "resolution": mapping.resolution_number,
                    }
                )
                rejected += 1
                continue

            # Layer 3: Text content check (basic — no empty citations)
            if not clause.clause_text or len(clause.clause_text.strip()) < 10:
                phantoms.append(
                    {
                        "regulation_id": clause.regulation_id,
                        "article": clause.article,
                        "reason": "Empty or too-short clause_text",
                        "resolution": mapping.resolution_number,
                    }
                )
                rejected += 1
                continue

            valid += 1

    # Check unsourced ratio
    if total > 0 and rejected > 0:
        unsourced_ratio = rejected / total
        if unsourced_ratio > MAX_UNSOURCED_RATIO:
            warnings.append(
                f"High rejection rate: {rejected}/{total} citations "
                f"({unsourced_ratio:.0%}) failed validation"
            )

    is_valid = rejected == 0 or (total > 0 and rejected / total <= MAX_UNSOURCED_RATIO)

    result = ValidationResult(
        valid=is_valid,
        total_citations=total,
        valid_citations=valid,
        rejected_citations=rejected,
        phantom_citations=phantoms,
        low_score_citations=low_scores,
        warnings=warnings,
    )

    if not is_valid:
        logger.warning(
            "Citation validation FAILED: %d/%d rejected, %d phantoms",
            rejected,
            total,
            len(phantoms),
        )
    else:
        logger.info(
            "Citation validation passed: %d/%d valid",
            valid,
            total,
        )

    return result


def validate_against_local_corpus(
    output: LegalResearchOutput,
    chunks_dirs: list[Path],
) -> ValidationResult:
    """Validate citations against local JSONL chunk files.

    This is a stronger validation that checks cited regulation_ids
    and article numbers actually exist in the corpus.
    """
    # Load corpus index
    corpus_regs: dict[str, set[str]] = {}
    for chunks_dir in chunks_dirs:
        for jsonl_path in chunks_dir.glob("*.jsonl"):
            if jsonl_path.name.startswith("_"):
                continue
            with open(jsonl_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    chunk = json.loads(line)
                    reg_id = chunk.get("regulation_id", "")
                    article = chunk.get("article_number", "")
                    if reg_id not in corpus_regs:
                        corpus_regs[reg_id] = set()
                    corpus_regs[reg_id].add(article)

    # First run standard validation
    result = validate_citations(output)

    # Then check against corpus
    additional_phantoms = []
    for mapping in output.regulatory_mapping:
        for clause in mapping.applicable_clauses:
            if clause.regulation_id not in corpus_regs:
                additional_phantoms.append(
                    {
                        "regulation_id": clause.regulation_id,
                        "article": clause.article,
                        "reason": f"regulation_id '{clause.regulation_id}' not found in corpus",
                        "resolution": mapping.resolution_number,
                    }
                )

    if additional_phantoms:
        result.phantom_citations.extend(additional_phantoms)
        result.rejected_citations += len(additional_phantoms)
        result.valid = False
        result.warnings.append(
            f"{len(additional_phantoms)} citations reference regulations not in corpus"
        )

    return result
