"""Draft assembly engine — template fill + AI review.

Assembles contracts from pre-approved clause library entries with variable
substitution, then optionally calls Gemini for optional clause recommendations
and consistency checks.
"""

from __future__ import annotations

import json
import logging
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ancol_common.db.repository import get_clauses_for_template, get_contract_template
from ancol_common.schemas.contract import ContractClause
from ancol_common.schemas.drafting import DraftOutput, DraftRequest

logger = logging.getLogger(__name__)


async def assemble_draft(
    session: AsyncSession,
    request: DraftRequest,
) -> DraftOutput:
    """Assemble a contract draft from template + clause library + AI review.

    Phase 1: Template + clause lookup
    Phase 2: Variable substitution
    Phase 3: AI enhancement (optional clause recommendations)
    """
    contract_id = str(uuid.uuid4())

    # Phase 1: Template + clause lookup
    template = await get_contract_template(session, request.contract_type)
    if not template:
        raise ValueError(f"No active template for contract type: {request.contract_type}")

    required_categories = template.required_clauses or []
    optional_categories = template.optional_clauses or []
    all_categories = required_categories + optional_categories

    library_clauses = await get_clauses_for_template(session, request.contract_type, all_categories)

    # Index by category (latest version wins — query is ordered by version desc)
    clause_by_category: dict = {}
    for lc in library_clauses:
        if lc.clause_category not in clause_by_category:
            clause_by_category[lc.clause_category] = lc

    # Phase 2: Assemble required clauses with variable substitution
    assembled_clauses: list[ContractClause] = []
    draft_sections: list[str] = []
    clause_num = 1

    # Build substitution context from request
    sub_context = _build_substitution_context(request)

    # Check for clause overrides (user-customized clauses)
    override_map = {}
    for override in request.clause_overrides:
        cat = override.get("category")
        if cat:
            override_map[cat] = override

    for category in required_categories:
        if category in override_map:
            # User provided a custom clause
            override = override_map[category]
            clause_text = override.get("text", "")
            title = override.get("title", category.replace("_", " ").title())
        elif category in clause_by_category:
            lc = clause_by_category[category]
            title = lc.title_id if request.language == "id" else (lc.title_en or lc.title_id)
            clause_text = lc.text_id if request.language == "id" else (lc.text_en or lc.text_id)
        else:
            logger.warning("No clause found for required category: %s", category)
            continue

        # Apply variable substitution
        clause_text = _substitute_variables(clause_text, sub_context)

        pasal = f"Pasal {clause_num}" if request.language == "id" else f"Article {clause_num}"
        draft_sections.append(f"## {pasal} — {title}\n\n{clause_text}")

        assembled_clauses.append(
            ContractClause(
                clause_number=pasal,
                title=title,
                text=clause_text,
                category=category,
                is_from_library=category not in override_map,
                confidence=1.0,
            )
        )
        clause_num += 1

    # Phase 3: AI enhancement (optional clause recommendations)
    ai_recommendations = await _get_ai_recommendations(
        request, assembled_clauses, optional_categories, clause_by_category
    )

    # Include AI-recommended optional clauses
    for rec in ai_recommendations.get("recommended_optional_clauses", []):
        cat = rec.get("category")
        if cat in clause_by_category and cat not in [c.category for c in assembled_clauses]:
            lc = clause_by_category[cat]
            title = lc.title_id if request.language == "id" else (lc.title_en or lc.title_id)
            clause_text = lc.text_id if request.language == "id" else (lc.text_en or lc.text_id)
            clause_text = _substitute_variables(clause_text, sub_context)

            pasal = f"Pasal {clause_num}" if request.language == "id" else f"Article {clause_num}"
            draft_sections.append(
                f"## {pasal} — {title}\n\n{clause_text}\n\n"
                f"*Rekomendasi AI: {rec.get('reason', '')}*"
            )

            assembled_clauses.append(
                ContractClause(
                    clause_number=pasal,
                    title=title,
                    text=clause_text,
                    category=cat,
                    is_from_library=True,
                    confidence=0.9,
                )
            )
            clause_num += 1

    # Build full draft text
    header = _build_draft_header(request)
    draft_text = header + "\n\n" + "\n\n".join(draft_sections)

    # Build risk assessment from library risk notes
    risk_assessment = []
    for clause in assembled_clauses:
        if clause.category in clause_by_category:
            lc = clause_by_category[clause.category]
            if lc.risk_notes:
                risk_assessment.append(
                    {
                        "clause": clause.clause_number,
                        "category": clause.category,
                        "notes": lc.risk_notes,
                    }
                )

    # Add consistency notes from AI
    for note in ai_recommendations.get("consistency_notes", []):
        risk_assessment.append(
            {
                "type": "consistency",
                "issue": note.get("issue"),
                "suggestion": note.get("suggestion"),
            }
        )

    return DraftOutput(
        contract_id=contract_id,
        draft_text=draft_text,
        clauses=assembled_clauses,
        risk_assessment=risk_assessment,
    )


def _build_substitution_context(request: DraftRequest) -> dict:
    """Build variable substitution context from request."""
    context = dict(request.key_terms)

    # Add party names
    for party in request.parties:
        if party.role == "principal":
            context["party_principal"] = party.name
        elif party.role == "counterparty":
            context["party_counterparty"] = party.name
        elif party.role == "guarantor":
            context["party_guarantor"] = party.name

    return context


def _substitute_variables(text: str, context: dict) -> str:
    """Replace {{variable}} placeholders with values from context."""

    def replacer(match):
        key = match.group(1)
        return str(context.get(key, match.group(0)))

    return re.sub(r"\{\{(\w+)\}\}", replacer, text)


def _build_draft_header(request: DraftRequest) -> str:
    """Build the contract header with party names and title."""
    type_names = {
        "nda": "PERJANJIAN KERAHASIAAN",
        "vendor": "PERJANJIAN PENYEDIAAN JASA",
        "sale_purchase": "PERJANJIAN JUAL BELI",
        "joint_venture": "PERJANJIAN USAHA PATUNGAN",
        "land_lease": "PERJANJIAN SEWA MENYEWA",
        "employment": "PERJANJIAN KERJA",
        "sop_board_resolution": "STANDAR OPERASIONAL PROSEDUR RAPAT",
    }
    title = type_names.get(request.contract_type, "PERJANJIAN")

    parties_text = ""
    for party in request.parties:
        role_map = {
            "principal": "PIHAK PERTAMA",
            "counterparty": "PIHAK KEDUA",
            "guarantor": "PENJAMIN",
        }
        role_label = role_map.get(party.role, party.role.upper())
        parties_text += f"- **{role_label}**: {party.name}"
        if party.entity_type == "related_party":
            parties_text += " *(pihak berelasi)*"
        parties_text += "\n"

    return f"# {title}\n\n{parties_text}"


async def _get_ai_recommendations(
    request: DraftRequest,
    assembled_clauses: list[ContractClause],
    optional_categories: list[str],
    clause_by_category: dict,
) -> dict:
    """Call Gemini for optional clause recommendations and consistency check."""
    try:
        from google.genai.types import GenerateContentConfig

        from ancol_common.drafting.prompts import DRAFT_ENHANCEMENT_SYSTEM_PROMPT
        from ancol_common.gemini.client import get_flash_model, get_gemini_client

        client = get_gemini_client()
        model = get_flash_model()

        # Build context for Gemini
        assembled_summary = "\n".join(
            f"- {c.clause_number}: {c.title} ({c.category})" for c in assembled_clauses
        )
        optional_summary = "\n".join(
            f"- {cat}: {clause_by_category[cat].title_id}"
            for cat in optional_categories
            if cat in clause_by_category
        )

        user_message = (
            f"## Contract Type: {request.contract_type}\n"
            f"## Parties: {', '.join(p.name for p in request.parties)}\n"
            f"## Key Terms: {json.dumps(request.key_terms, ensure_ascii=False)}\n\n"
            f"## Assembled Required Clauses:\n{assembled_summary}\n\n"
            f"## Available Optional Clauses:\n{optional_summary}"
        )

        response = client.models.generate_content(
            model=model,
            contents=[
                {"role": "user", "parts": [{"text": DRAFT_ENHANCEMENT_SYSTEM_PROMPT}]},
                {"role": "user", "parts": [{"text": user_message}]},
            ],
            config=GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json",
                max_output_tokens=2048,
            ),
        )

        return json.loads(response.text)

    except Exception:
        logger.warning("AI enhancement failed, proceeding without recommendations", exc_info=True)
        return {"recommended_optional_clauses": [], "consistency_notes": []}
