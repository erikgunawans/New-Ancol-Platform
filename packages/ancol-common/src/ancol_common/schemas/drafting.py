"""Smart drafting schemas for contract template generation."""

from __future__ import annotations

from pydantic import BaseModel

from .contract import ContractClause, ContractParty, ContractType


class ClauseLibraryEntry(BaseModel):
    """A pre-approved clause from the clause library."""

    id: str
    contract_type: ContractType
    clause_category: str  # "termination", "indemnification", "confidentiality", etc.
    title_id: str  # Bahasa Indonesia title
    title_en: str | None = None
    text_id: str  # Bahasa Indonesia clause text
    text_en: str | None = None
    risk_notes: str | None = None
    is_mandatory: bool = False
    version: int = 1


class DraftRequest(BaseModel):
    """Request to generate a contract draft from a template."""

    contract_type: ContractType
    parties: list[ContractParty]
    key_terms: dict = {}  # {"value": ..., "duration": ..., "location": ...}
    clause_overrides: list[dict] = []  # user-customized clauses
    language: str = "id"  # "id" or "en"


class DraftOutput(BaseModel):
    """Generated contract draft output."""

    contract_id: str
    draft_text: str
    clauses: list[ContractClause] = []
    risk_assessment: list[dict] = []
    gcs_draft_uri: str | None = None
