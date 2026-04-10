"""Comparison Agent core logic — Agent 3.

Takes extraction + regulatory context, calls Gemini Pro for chain-of-thought
compliance analysis, runs red flag detection, computes severity scores.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime

from ancol_common.gemini.client import get_gemini_client, get_pro_model
from ancol_common.schemas.comparison import ComparisonInput, ComparisonOutput, RedFlagSummary
from ancol_common.schemas.mom import ProcessingMetadata
from google.genai.types import GenerateContentConfig

from .analyzers.red_flags import detect_all_red_flags
from .analyzers.severity import (
    compute_regulatory_score,
    compute_substantive_score,
)
from .prompts.system import COMPARISON_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

AGENT_VERSION = "0.1.0"


async def compare_compliance(input_data: ComparisonInput) -> ComparisonOutput:
    """Run the full compliance comparison pipeline.

    Steps:
    1. Run rule-based red flag detectors
    2. Call Gemini Pro for chain-of-thought compliance analysis
    3. Merge rule-based and AI-detected findings
    4. Compute substantive and regulatory scores
    """
    start_time = time.time()
    client = get_gemini_client()
    model = get_pro_model()

    # Step 1: Rule-based red flag detection
    structured_mom = input_data.structured_mom_json
    resolutions = structured_mom.get("resolutions", [])
    rpt_entities = [e.get("entity_name", "") for e in input_data.related_party_entities]

    rule_flags = detect_all_red_flags(
        structured_mom=structured_mom,
        resolutions=resolutions,
        rpt_entities=rpt_entities or None,
    )

    # Step 2: Call Gemini Pro for AI-driven analysis
    user_message = _build_user_message(input_data, rule_flags)

    logger.info("Calling Gemini %s for comparison on document %s", model, input_data.document_id)

    response = client.models.generate_content(
        model=model,
        contents=[
            {"role": "user", "parts": [{"text": COMPARISON_SYSTEM_PROMPT}]},
            {"role": "user", "parts": [{"text": user_message}]},
        ],
        config=GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
            max_output_tokens=16384,
        ),
    )

    processing_time_ms = int((time.time() - start_time) * 1000)

    # Parse response
    comparison_data = json.loads(response.text)

    # Build metadata
    usage = response.usage_metadata
    metadata = ProcessingMetadata(
        agent_version=AGENT_VERSION,
        model_used=model,
        processing_time_ms=processing_time_ms,
        prompt_tokens=usage.prompt_token_count if usage else None,
        completion_tokens=usage.candidates_token_count if usage else None,
        timestamp=datetime.utcnow(),
    )

    # Step 3: Merge findings
    findings = comparison_data.get("findings", [])
    consistency_report = comparison_data.get("consistency_report", [])

    # Enrich findings from rule-based flags
    for flag in rule_flags:
        already_found = any(f.get("red_flag_type") == flag.flag_type for f in findings)
        if not already_found:
            findings.append(
                {
                    "finding_id": f"rule-{flag.flag_type}-{len(findings)}",
                    "resolution_number": flag.resolution_number or "general",
                    "regulation_id": flag.regulation_ref.split(",")[0].strip()
                    if flag.regulation_ref
                    else "",
                    "clause_id": flag.regulation_ref,
                    "compliance_status": "non_compliant",
                    "severity": flag.severity,
                    "title": flag.description[:100],
                    "description": flag.description,
                    "chain_of_thought": f"Rule-based detection: {flag.evidence}",
                    "evidence_refs": [flag.evidence],
                    "is_red_flag": True,
                    "red_flag_type": flag.flag_type,
                }
            )

    # Step 4: Build red flag summary
    red_flag_findings = [f for f in findings if f.get("is_red_flag")]
    critical_count = sum(1 for f in red_flag_findings if f.get("severity") == "critical")

    red_flags = RedFlagSummary(
        total_count=len(red_flag_findings),
        critical_count=critical_count,
        flags=[
            {
                "type": f.get("red_flag_type", "unknown"),
                "description": f.get("description", ""),
                "evidence": f.get("chain_of_thought", ""),
            }
            for f in red_flag_findings
        ],
    )

    # Compute scores
    regulatory_score = compute_regulatory_score(findings)
    substantive_score = compute_substantive_score(consistency_report)

    # Build output
    comparison_data["document_id"] = input_data.document_id
    comparison_data["findings"] = findings
    comparison_data["red_flags"] = red_flags.model_dump()
    comparison_data["consistency_report"] = consistency_report
    comparison_data["substantive_score"] = substantive_score
    comparison_data["regulatory_score"] = regulatory_score
    comparison_data["processing_metadata"] = metadata.model_dump(mode="json")

    output = ComparisonOutput(**comparison_data)

    logger.info(
        "Comparison complete for %s: %d findings, %d red flags (%d critical), "
        "substantive=%.1f, regulatory=%.1f",
        input_data.document_id,
        len(findings),
        red_flags.total_count,
        critical_count,
        substantive_score,
        regulatory_score,
    )

    return output


def _build_user_message(input_data: ComparisonInput, rule_flags: list) -> str:
    """Build user message with extraction + regulatory data."""
    mom = input_data.structured_mom_json
    reg = input_data.regulatory_mapping_json

    msg = f"""Analisis kepatuhan untuk Risalah Rapat Direksi berikut.

## Data Risalah (dari Extraction Agent)
{json.dumps(mom, ensure_ascii=False, indent=2)}

## Pemetaan Regulasi (dari Legal Research Agent)
{json.dumps(reg, ensure_ascii=False, indent=2)}

## Red Flags Terdeteksi (dari rule-based scanner)
"""

    if rule_flags:
        for flag in rule_flags:
            msg += f"- [{flag.severity.upper()}] {flag.flag_type}: {flag.description}\n"
    else:
        msg += "- Tidak ada red flag dari scanner otomatis\n"

    if input_data.related_party_entities:
        msg += "\n## Daftar Entitas Pihak Berelasi\n"
        for entity in input_data.related_party_entities:
            msg += (
                f"- {entity.get('entity_name', '')}: {entity.get('relationship_description', '')}\n"
            )

    msg += """
## Instruksi
1. Lakukan pemeriksaan kepatuhan menyeluruh (struktural + substantif + regulasi)
2. Untuk setiap temuan, sertakan chain_of_thought yang menjelaskan penalaran
3. Tandai red flags yang terdeteksi
4. Periksa konsistensi data keuangan dan tindak lanjut rapat sebelumnya
"""

    return msg
