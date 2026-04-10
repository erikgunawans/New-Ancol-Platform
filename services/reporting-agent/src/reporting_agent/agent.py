"""Reporting Agent core logic — Agent 4.

Takes findings + scores, generates executive summary via Gemini Flash,
produces corrective suggestions, renders PDF and Excel reports.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime

from ancol_common.gemini.client import get_flash_model, get_gemini_client
from ancol_common.schemas.mom import ProcessingMetadata
from ancol_common.schemas.reporting import ReportingInput, ReportingOutput
from google.genai.types import GenerateContentConfig

from .generators.scorecard import compute_scorecard
from .prompts.system import REPORTING_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

AGENT_VERSION = "0.1.0"


async def generate_report(input_data: ReportingInput) -> ReportingOutput:
    """Run the full reporting pipeline.

    Steps:
    1. Compute three-pillar scorecard
    2. Call Gemini Flash for executive summary + corrective suggestions
    3. Generate HTML for PDF rendering
    """
    start_time = time.time()
    client = get_gemini_client()
    model = get_flash_model()

    findings = input_data.findings_json.get("findings", [])
    red_flags = input_data.findings_json.get("red_flags", {})
    input_data.findings_json.get("consistency_report", [])

    # Step 1: Compute scorecard
    substantive_score = input_data.findings_json.get("substantive_score", 100.0)
    regulatory_score = input_data.findings_json.get("regulatory_score", 100.0)

    scorecard = compute_scorecard(
        structural_score=input_data.structural_score,
        substantive_score=substantive_score,
        regulatory_score=regulatory_score,
        historical_scores=input_data.historical_scores,
    )

    # Step 2: Call Gemini Flash
    user_message = _build_user_message(input_data, scorecard, findings, red_flags)

    logger.info("Calling Gemini %s for report generation on %s", model, input_data.document_id)

    response = client.models.generate_content(
        model=model,
        contents=[
            {"role": "user", "parts": [{"text": REPORTING_SYSTEM_PROMPT}]},
            {"role": "user", "parts": [{"text": user_message}]},
        ],
        config=GenerateContentConfig(
            temperature=0.3,
            response_mime_type="application/json",
            max_output_tokens=8192,
        ),
    )

    processing_time_ms = int((time.time() - start_time) * 1000)

    report_data = json.loads(response.text)

    usage = response.usage_metadata
    metadata = ProcessingMetadata(
        agent_version=AGENT_VERSION,
        model_used=model,
        processing_time_ms=processing_time_ms,
        prompt_tokens=usage.prompt_token_count if usage else None,
        completion_tokens=usage.candidates_token_count if usage else None,
        timestamp=datetime.utcnow(),
    )

    # Step 3: Generate HTML
    from .generators.pdf import generate_report_html

    executive_summary = report_data.get("executive_summary", "")
    corrective_suggestions = report_data.get("corrective_suggestions", [])

    html = generate_report_html(
        document_id=input_data.document_id,
        meeting_date=report_data.get("meeting_date", ""),
        meeting_number=report_data.get("meeting_number", ""),
        scorecard=scorecard,
        findings=findings,
        corrective_suggestions=[],  # Raw dicts, not parsed yet
        executive_summary=executive_summary,
    )

    output = ReportingOutput(
        document_id=input_data.document_id,
        scorecard=scorecard,
        corrective_suggestions=corrective_suggestions,
        executive_summary=executive_summary,
        detailed_findings_html=html,
        report_data={
            "scorecard": scorecard.model_dump(),
            "findings": findings,
            "red_flags": red_flags,
            "corrective_suggestions": corrective_suggestions,
        },
        processing_metadata=metadata,
    )

    logger.info(
        "Report generated for %s: composite=%.1f, suggestions=%d",
        input_data.document_id,
        scorecard.composite_score,
        len(corrective_suggestions),
    )

    return output


def _build_user_message(input_data, scorecard, findings, red_flags) -> str:
    """Build user prompt for Gemini to generate summary + corrections."""
    critical_findings = [f for f in findings if f.get("severity") == "critical"]
    high_findings = [f for f in findings if f.get("severity") == "high"]

    msg = f"""Hasilkan ringkasan eksekutif dan saran perbaikan untuk risalah rapat berikut.

## Scorecard
- Struktural: {scorecard.structural_score:.0f}/100
- Substantif: {scorecard.substantive_score:.0f}/100
- Regulasi: {scorecard.regulatory_score:.0f}/100
- Komposit: {scorecard.composite_score:.0f}/100

## Statistik Temuan
- Total: {len(findings)}
- Critical: {len(critical_findings)}
- High: {len(high_findings)}
- Red flags: {red_flags.get("total_count", 0)} (critical: {red_flags.get("critical_count", 0)})

## Temuan Detail
{json.dumps(findings, ensure_ascii=False, indent=2)}

## Instruksi
1. Tulis executive_summary (150-250 kata, Bahasa Indonesia, formal, board-ready)
2. Buat corrective_suggestions untuk setiap temuan CRITICAL dan HIGH
"""
    return msg
