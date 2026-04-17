"""Retroactive bundler — propose StrategicDecisions from existing MoMs.

v1 uses deterministic heuristics (agenda keyword extraction). A follow-up
phase will wrap this with Gemini Flash for richer classification.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ancol_common.db.models import Document, Extraction, RJPPTheme, RKABLineItem
from ancol_common.schemas.decision import InitiativeType


@dataclass
class ProposedCandidate:
    id: str
    code: str  # RKAB code or RJPP identifier
    name: str
    confidence: float
    rationale: str | None = None


@dataclass
class ProposedDecisionDraft:
    """Output of retroactive proposer: draft for human confirmation."""

    source_document_id: str
    proposed_title: str
    proposed_description: str
    proposed_initiative_type: str
    rkab_candidates: list[ProposedCandidate] = field(default_factory=list)
    rjpp_candidates: list[ProposedCandidate] = field(default_factory=list)
    reasoning: str | None = None


# Keyword → initiative_type heuristics (Bahasa Indonesia + English)
_INITIATIVE_KEYWORDS = {
    InitiativeType.INVESTMENT.value: ("investasi", "investment", "capex", "akuisisi", "buyout"),
    InitiativeType.PARTNERSHIP.value: (
        "kerjasama",
        "joint venture",
        "jv",
        "partnership",
        "kolaborasi",
    ),
    InitiativeType.MAJOR_CONTRACT.value: ("kontrak", "perjanjian", "contract", "agreement", "mou"),
    InitiativeType.DIVESTMENT.value: ("divestasi", "divestment", "penjualan aset", "asset sale"),
    InitiativeType.RUPS_ITEM.value: ("rups", "agm", "pemegang saham", "shareholder", "dividen"),
    InitiativeType.ORGANIZATIONAL_CHANGE.value: (
        "restrukturisasi",
        "reorganisasi",
        "merger",
        "spin off",
    ),
}


async def propose_from_mom(
    session: AsyncSession,
    document_id: str,
) -> ProposedDecisionDraft:
    """Propose a StrategicDecision from a completed MoM.

    Returns a draft + top candidate RKAB/RJPP matches. Caller (the user)
    confirms and POSTs to /api/decisions with their final selections.
    """
    doc_uuid = uuid.UUID(document_id)
    doc_result = await session.execute(select(Document).where(Document.id == doc_uuid))
    document = doc_result.scalar_one_or_none()
    if document is None:
        raise ValueError(f"Document {document_id} not found")

    ext_result = await session.execute(
        select(Extraction).where(Extraction.document_id == doc_uuid).limit(1)
    )
    extraction = ext_result.scalar_one_or_none()

    title, description, initiative_type = _draft_title_and_type(document, extraction)

    # Fiscal year for RKAB matching: meeting year, or doc upload year as fallback
    fiscal_year = (
        document.meeting_date.year
        if document.meeting_date
        else (document.created_at.year if document.created_at else 2026)
    )

    rkab_candidates = await _rank_rkab_candidates(session, title, description, fiscal_year)
    rjpp_candidates = await _rank_rjpp_candidates(session, title, description)

    return ProposedDecisionDraft(
        source_document_id=document_id,
        proposed_title=title,
        proposed_description=description,
        proposed_initiative_type=initiative_type,
        rkab_candidates=rkab_candidates,
        rjpp_candidates=rjpp_candidates,
        reasoning=(
            f"Classified as '{initiative_type}' from agenda keywords. "
            f"Fiscal year {fiscal_year} used for RKAB match."
        ),
    )


def _draft_title_and_type(
    document: Document, extraction: Extraction | None
) -> tuple[str, str, str]:
    """Derive (title, description, initiative_type) from MoM metadata."""
    agenda_items: list[str] = []
    if extraction is not None:
        structured = extraction.structured_mom or {}
        agenda_items = structured.get("agenda_items") or []

    first_agenda = agenda_items[0] if agenda_items else document.filename
    title = first_agenda[:200] if first_agenda else f"Decision from {document.filename}"
    description = (
        " | ".join(agenda_items[:3]) if agenda_items else "Auto-bundled from MoM document."
    )

    # Initiative type by keyword match
    haystack = f"{title} {description}".lower()
    for itype, keywords in _INITIATIVE_KEYWORDS.items():
        if any(kw in haystack for kw in keywords):
            return title, description, itype
    return title, description, InitiativeType.INVESTMENT.value  # default


async def _rank_rkab_candidates(
    session: AsyncSession,
    title: str,
    description: str,
    fiscal_year: int,
    top_n: int = 3,
) -> list[ProposedCandidate]:
    """Token-overlap match against active RKAB for the fiscal year."""
    result = await session.execute(
        select(RKABLineItem).where(
            RKABLineItem.fiscal_year == fiscal_year,
            RKABLineItem.is_active.is_(True),
        )
    )
    items = list(result.scalars().all())
    query_tokens = set(f"{title} {description}".lower().split())
    candidates: list[ProposedCandidate] = []
    for item in items:
        hay = f"{item.activity_name} {item.category} {item.description or ''}".lower()
        hay_tokens = set(hay.split())
        overlap = len(query_tokens & hay_tokens)
        denom = max(len(query_tokens), 1)
        confidence = min(overlap / denom, 1.0)
        if confidence > 0:
            candidates.append(
                ProposedCandidate(
                    id=str(item.id),
                    code=item.code,
                    name=item.activity_name,
                    confidence=round(confidence, 2),
                    rationale=f"Token overlap {overlap}/{denom}",
                )
            )
    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates[:top_n]


async def _rank_rjpp_candidates(
    session: AsyncSession,
    title: str,
    description: str,
    top_n: int = 3,
) -> list[ProposedCandidate]:
    """Token-overlap match against active RJPP themes."""
    result = await session.execute(select(RJPPTheme).where(RJPPTheme.is_active.is_(True)))
    themes = list(result.scalars().all())
    query_tokens = set(f"{title} {description}".lower().split())
    candidates: list[ProposedCandidate] = []
    for theme in themes:
        hay = f"{theme.theme_name} {theme.description or ''}".lower()
        hay_tokens = set(hay.split())
        overlap = len(query_tokens & hay_tokens)
        denom = max(len(query_tokens), 1)
        confidence = min(overlap / denom, 1.0)
        if confidence > 0:
            candidates.append(
                ProposedCandidate(
                    id=str(theme.id),
                    code=theme.approval_ref or "",
                    name=theme.theme_name,
                    confidence=round(confidence, 2),
                    rationale=f"Token overlap {overlap}/{denom}",
                )
            )
    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates[:top_n]
