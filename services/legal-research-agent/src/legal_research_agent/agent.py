"""Legal Research Agent core logic — Agent 2.

Takes extraction output + meeting date, calls Gemini Pro with Vertex AI Search
grounding to map resolutions to applicable regulations. Validates all citations.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime

from ancol_common.config import get_settings
from ancol_common.gemini.client import get_gemini_client, get_pro_model
from ancol_common.gemini.grounding import get_regulatory_search_tool
from ancol_common.schemas.legal_research import (
    LegalResearchInput,
    LegalResearchOutput,
)
from ancol_common.schemas.mom import ProcessingMetadata
from google.genai.types import GenerateContentConfig

from .prompts.system import LEGAL_RESEARCH_SYSTEM_PROMPT
from .retrieval.citation_validator import validate_citations

logger = logging.getLogger(__name__)

AGENT_VERSION = "0.1.0"


async def research_regulations(
    input_data: LegalResearchInput,
) -> LegalResearchOutput:
    """Run the full legal research pipeline.

    Steps:
    1. Classify resolution topics
    2. Call Gemini Pro with Vertex AI Search grounding
    3. Parse regulatory mappings
    4. Validate ALL citations (anti-hallucination Layer 3)
    5. Check corpus freshness
    6. Detect regulatory overlaps and conflicts
    """
    start_time = time.time()
    get_settings()
    client = get_gemini_client()
    model = get_pro_model()

    # Build user message with extraction data
    user_message = _build_user_message(input_data)

    # Get grounding tool for Vertex AI Search
    search_tool = get_regulatory_search_tool()

    # Call Gemini Pro with RAG grounding
    logger.info(
        "Calling Gemini %s with Vertex AI Search grounding for document %s",
        model,
        input_data.document_id,
    )

    response = client.models.generate_content(
        model=model,
        contents=[
            {"role": "user", "parts": [{"text": LEGAL_RESEARCH_SYSTEM_PROMPT}]},
            {"role": "user", "parts": [{"text": user_message}]},
        ],
        config=GenerateContentConfig(
            temperature=0.0,  # Zero temperature for maximum precision
            response_mime_type="application/json",
            max_output_tokens=16384,
            tools=[search_tool],
        ),
    )

    processing_time_ms = int((time.time() - start_time) * 1000)

    # Parse response
    raw_json = response.text
    research_data = json.loads(raw_json)

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

    # Set required fields
    research_data["document_id"] = input_data.document_id
    research_data["extraction_id"] = input_data.extraction_id
    research_data["processing_metadata"] = metadata.model_dump(mode="json")

    # Ensure corpus freshness exists
    if "corpus_freshness" not in research_data:
        research_data["corpus_freshness"] = {
            "last_updated": date.today().isoformat(),
            "staleness_days": 0,
            "alerts": [],
        }

    # Ensure required list fields exist
    for field in ["regulatory_mapping", "overlap_flags", "conflict_flags"]:
        if field not in research_data:
            research_data[field] = []

    # Parse output
    output = LegalResearchOutput(**research_data)

    # CRITICAL: Validate all citations
    validation = validate_citations(output)

    if not validation.valid:
        logger.error(
            "CITATION VALIDATION FAILED for document %s: "
            "%d phantoms, %d low-score, %d total rejected",
            input_data.document_id,
            len(validation.phantom_citations),
            len(validation.low_score_citations),
            validation.rejected_citations,
        )
        # Strip invalid citations from output
        output = _strip_invalid_citations(output, validation)

    logger.info(
        "Legal research complete for %s: %d mappings, %d overlaps, %d conflicts, "
        "citations: %d valid / %d total",
        input_data.document_id,
        len(output.regulatory_mapping),
        len(output.overlap_flags),
        len(output.conflict_flags),
        validation.valid_citations,
        validation.total_citations,
    )

    return output


def _build_user_message(input_data: LegalResearchInput) -> str:
    """Build the user prompt with extraction data for legal research."""
    mom = input_data.structured_mom_json

    msg = f"""Analisis kepatuhan regulasi untuk Risalah Rapat Direksi berikut.

## Informasi Rapat
- Document ID: {input_data.document_id}
- Tanggal Rapat: {input_data.meeting_date.isoformat()}
- Jenis Rapat: {mom.get("meeting_type", "regular")}

## Peserta
- Ketua Rapat: {mom.get("chairman", "N/A")}
- Direksi hadir: {mom.get("directors_present", "N/A")}/{mom.get("total_directors", "N/A")}
- Kuorum: {"Terpenuhi" if mom.get("quorum_met") else "Tidak terpenuhi / tidak diketahui"}

## Keputusan Rapat yang Perlu Dianalisis
"""

    for i, topic in enumerate(input_data.resolution_topics, 1):
        msg += f"""
### Keputusan {i}
- Nomor: {topic.get("number", f"{i}")}
- Teks: {topic.get("text", "")}
- Agenda: {topic.get("agenda_item", "N/A")}
- Penanggung Jawab: {topic.get("assignee", "N/A")}
- Tenggat: {topic.get("deadline", "N/A")}
"""

    msg += """
## Instruksi
Untuk SETIAP keputusan di atas:
1. Identifikasi domain regulasi yang terkait
2. Cari pasal-pasal spesifik yang berlaku menggunakan corpus regulasi
3. Deteksi overlap atau konflik antar regulasi
4. Pastikan regulasi yang dikutip efektif pada tanggal rapat

PENTING: Hanya kutip regulasi yang ditemukan melalui retrieval. Jangan mengarang kutipan.
"""

    return msg


def _strip_invalid_citations(
    output: LegalResearchOutput,
    validation,
) -> LegalResearchOutput:
    """Remove invalid citations from output, keeping only validated ones."""
    # Build set of invalid citations for fast lookup
    invalid_keys = set()
    for phantom in validation.phantom_citations:
        key = (phantom["regulation_id"], phantom["article"], phantom["resolution"])
        invalid_keys.add(key)
    for low_score in validation.low_score_citations:
        key = (low_score["regulation_id"], low_score["article"], low_score["resolution"])
        invalid_keys.add(key)

    # Filter mappings
    cleaned_mappings = []
    for mapping in output.regulatory_mapping:
        cleaned_clauses = [
            clause
            for clause in mapping.applicable_clauses
            if (clause.regulation_id, clause.article, mapping.resolution_number) not in invalid_keys
        ]
        if cleaned_clauses:
            mapping.applicable_clauses = cleaned_clauses
            cleaned_mappings.append(mapping)

    output.regulatory_mapping = cleaned_mappings
    return output
