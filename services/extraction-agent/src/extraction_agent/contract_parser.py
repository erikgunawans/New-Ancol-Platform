"""Contract clause extraction via Gemini Pro.

Parses OCR text into structured clauses with risk scoring.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime

from ancol_common.gemini.client import get_gemini_client, get_pro_model
from ancol_common.schemas.contract import (
    ApplicableRegulation,
    ContractClause,
    ContractExtractionOutput,
    ContractParty,
    ExtractedObligation,
    RiskLevel,
)
from ancol_common.schemas.mom import ProcessingMetadata
from google.genai.types import GenerateContentConfig

from .prompts.contract_system import CONTRACT_EXTRACTION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

AGENT_VERSION = "0.1.0"


async def extract_contract(
    ocr_text: str,
    contract_id: str,
    contract_type: str,
) -> ContractExtractionOutput:
    """Parse contract OCR text into structured clauses with risk scoring.

    Args:
        ocr_text: Full OCR text from Document AI.
        contract_id: The contract record ID.
        contract_type: Contract type (nda, vendor, etc.).

    Returns:
        ContractExtractionOutput with clauses, parties, dates, financial terms.
    """
    start_time = time.time()
    client = get_gemini_client()
    model = get_pro_model()

    user_message = f"## Contract Type: {contract_type}\n\n## Contract Text (OCR)\n\n{ocr_text}"

    logger.info(
        "Calling Gemini %s for contract %s (type=%s, text_len=%d)",
        model,
        contract_id,
        contract_type,
        len(ocr_text),
    )

    response = client.models.generate_content(
        model=model,
        contents=[
            {"role": "user", "parts": [{"text": CONTRACT_EXTRACTION_SYSTEM_PROMPT}]},
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

    # Map extracted data to schema
    clauses = [
        ContractClause(
            clause_number=c.get("clause_number", ""),
            title=c.get("title", ""),
            text=c.get("text", ""),
            category=c.get("category", "other"),
            risk_level=RiskLevel(c["risk_level"]) if c.get("risk_level") else None,
            risk_reason=c.get("risk_reason"),
            confidence=c.get("confidence", 0.8),
        )
        for c in extracted.get("clauses", [])
    ]

    parties = [
        ContractParty(
            name=p.get("name", ""),
            role=p.get("role", "counterparty"),
            entity_type=p.get("entity_type", "external"),
        )
        for p in extracted.get("parties", [])
    ]

    key_dates = extracted.get("key_dates", {})
    financial_terms = extracted.get("financial_terms", {})
    risk_summary = extracted.get("risk_summary", {})

    obligations = [ExtractedObligation(**o) for o in extracted.get("obligations", [])]
    applicable_regulations = [
        ApplicableRegulation(**r) for r in extracted.get("applicable_regulations", [])
    ]

    output = ContractExtractionOutput(
        contract_id=contract_id,
        clauses=clauses,
        parties=parties,
        key_dates=key_dates,
        financial_terms=financial_terms,
        risk_summary=risk_summary,
        obligations=obligations,
        applicable_regulations=applicable_regulations,
        processing_metadata=metadata,
    )

    logger.info(
        "Contract extraction complete: contract=%s, clauses=%d, parties=%d, risk=%s",
        contract_id,
        len(clauses),
        len(parties),
        risk_summary.get("overall_risk_level", "unknown"),
    )

    return output
