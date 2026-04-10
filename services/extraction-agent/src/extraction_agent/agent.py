"""Extraction Agent core logic — Agent 1.

Takes OCR text + template config, calls Gemini Flash for structured extraction,
validates against template, computes structural score.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime

from ancol_common.config import get_settings
from ancol_common.gemini.client import get_flash_model, get_gemini_client
from ancol_common.schemas.extraction import ExtractionInput, ExtractionOutput
from ancol_common.schemas.mom import ProcessingMetadata
from google.genai.types import GenerateContentConfig

from .parsers.structural import compute_structural_score, identify_low_confidence_fields
from .prompts.few_shot import get_few_shot_messages
from .prompts.system import EXTRACTION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

AGENT_VERSION = "0.1.0"


async def extract_mom(input_data: ExtractionInput) -> ExtractionOutput:
    """Run the full MoM extraction pipeline.

    Steps:
    1. Prepare prompt with OCR text + template context
    2. Call Gemini Flash for structured extraction
    3. Parse and validate JSON response
    4. Compute structural compliance score
    5. Identify low-confidence fields and deviations
    """
    start_time = time.time()
    get_settings()
    client = get_gemini_client()
    model = get_flash_model()

    # Build the user message with OCR text and template context
    user_message = _build_user_message(input_data)

    # Call Gemini Flash
    logger.info("Calling Gemini %s for document %s", model, input_data.document_id)

    response = client.models.generate_content(
        model=model,
        contents=[
            {"role": "user", "parts": [{"text": EXTRACTION_SYSTEM_PROMPT}]},
            *get_few_shot_messages(),
            {"role": "user", "parts": [{"text": user_message}]},
        ],
        config=GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
            max_output_tokens=8192,
        ),
    )

    processing_time_ms = int((time.time() - start_time) * 1000)

    # Parse response
    raw_json = response.text
    extracted = json.loads(raw_json)

    # Build processing metadata
    usage = response.usage_metadata
    metadata = ProcessingMetadata(
        agent_version=AGENT_VERSION,
        model_used=model,
        processing_time_ms=processing_time_ms,
        prompt_tokens=usage.prompt_token_count if usage else None,
        completion_tokens=usage.candidates_token_count if usage else None,
        timestamp=datetime.utcnow(),
    )

    # Compute structural score against template
    structural_score, deviation_flags = compute_structural_score(extracted, input_data.template)

    # Identify low-confidence fields
    field_confidence = extracted.get("field_confidence", {})
    low_confidence_fields = identify_low_confidence_fields(field_confidence)

    # Override computed fields
    extracted["document_id"] = input_data.document_id
    extracted["structural_score"] = structural_score
    extracted["deviation_flags"] = [f.model_dump() for f in deviation_flags]
    extracted["low_confidence_fields"] = low_confidence_fields
    extracted["processing_metadata"] = metadata.model_dump(mode="json")

    # Ensure required nested fields exist
    if "field_confidence" not in extracted:
        extracted["field_confidence"] = {}

    output = ExtractionOutput(**extracted)
    logger.info(
        "Extraction complete for %s: score=%.1f, deviations=%d, low_confidence=%d",
        input_data.document_id,
        structural_score,
        len(deviation_flags),
        len(low_confidence_fields),
    )
    return output


def _build_user_message(input_data: ExtractionInput) -> str:
    """Build the user prompt with OCR text and template context."""
    template = input_data.template
    sections_list = ", ".join(template.required_sections)

    msg = f"""Berikut adalah teks OCR dari risalah rapat yang perlu diekstrak.

## Konfigurasi Template
- Nama Template: {template.template_name}
- Jenis Rapat: {template.mom_type}
- Section yang Wajib: {sections_list}
- Aturan Kuorum: {json.dumps(template.quorum_rules, ensure_ascii=False)}
- Aturan Tanda Tangan: {json.dumps(template.signature_rules, ensure_ascii=False)}

## Informasi OCR
- Jumlah halaman: {len(input_data.page_confidences)}
- Confidence rata-rata OCR: {sum(input_data.page_confidences) / max(len(input_data.page_confidences), 1):.2f}

## Teks OCR Lengkap

{input_data.ocr_text}
"""

    if input_data.extracted_tables:
        msg += "\n## Tabel yang Terdeteksi\n\n"
        for i, table in enumerate(input_data.extracted_tables, 1):
            msg += f"### Tabel {i}\n{json.dumps(table, ensure_ascii=False, indent=2)}\n\n"

    return msg
