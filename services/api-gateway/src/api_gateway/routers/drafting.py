"""Drafting API — contract templates and clause library."""

from __future__ import annotations

import uuid

from ancol_common.auth.rbac import require_permission
from ancol_common.db.connection import get_session
from ancol_common.db.models import ClauseLibrary, ContractTemplate
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

router = APIRouter(prefix="/drafting", tags=["Drafting"])


class TemplateResponse(BaseModel):
    id: str
    name: str
    contract_type: str
    version: int
    description: str | None = None
    required_clauses: dict | None = None
    optional_clauses: dict | None = None
    default_terms: dict | None = None
    is_active: bool


class ClauseLibraryResponse(BaseModel):
    id: str
    contract_type: str
    clause_category: str
    title_id: str
    title_en: str | None = None
    text_id: str
    text_en: str | None = None
    risk_notes: str | None = None
    is_mandatory: bool
    version: int


@router.get("/templates")
async def list_templates(
    _auth=require_permission("drafting:generate"),
    contract_type: str | None = Query(None),
):
    """List available contract templates."""
    async with get_session() as session:
        query = select(ContractTemplate).where(ContractTemplate.is_active.is_(True))
        if contract_type:
            query = query.where(ContractTemplate.contract_type == contract_type)
        query = query.order_by(ContractTemplate.contract_type, ContractTemplate.version.desc())
        result = await session.execute(query)
        templates = result.scalars().all()

    return {
        "templates": [
            TemplateResponse(
                id=str(t.id),
                name=t.name,
                contract_type=t.contract_type,
                version=t.version,
                description=t.description,
                required_clauses=t.required_clauses,
                optional_clauses=t.optional_clauses,
                default_terms=t.default_terms,
                is_active=t.is_active,
            )
            for t in templates
        ],
        "total": len(templates),
    }


@router.get("/templates/{contract_type}")
async def get_template(contract_type: str, _auth=require_permission("drafting:generate")):
    """Get the latest active template for a contract type."""
    async with get_session() as session:
        result = await session.execute(
            select(ContractTemplate)
            .where(
                ContractTemplate.contract_type == contract_type,
                ContractTemplate.is_active.is_(True),
            )
            .order_by(ContractTemplate.version.desc())
            .limit(1)
        )
        template = result.scalar_one_or_none()
        if not template:
            raise HTTPException(
                status_code=404,
                detail=f"No active template for type: {contract_type}",
            )

    return TemplateResponse(
        id=str(template.id),
        name=template.name,
        contract_type=template.contract_type,
        version=template.version,
        description=template.description,
        required_clauses=template.required_clauses,
        optional_clauses=template.optional_clauses,
        default_terms=template.default_terms,
        is_active=template.is_active,
    )


@router.post("/generate")
async def generate_draft(
    _auth=require_permission("drafting:generate"),
    body: dict | None = None,
):
    """Generate a contract draft from template + clause library + AI review."""
    from ancol_common.drafting.engine import assemble_draft
    from ancol_common.schemas.contract import ContractParty
    from ancol_common.schemas.drafting import DraftRequest

    # Parse request
    if body is None:
        body = {}
    request = DraftRequest(
        contract_type=body.get("contract_type", "vendor"),
        parties=[ContractParty(**p) for p in body.get("parties", [])],
        key_terms=body.get("key_terms", {}),
        clause_overrides=body.get("clause_overrides", []),
        language=body.get("language", "id"),
    )

    async with get_session() as session:
        result = await assemble_draft(session, request)

    return {
        "contract_id": result.contract_id,
        "draft_text": result.draft_text,
        "clauses": [c.model_dump() for c in result.clauses],
        "risk_assessment": result.risk_assessment,
        "gcs_draft_uri": result.gcs_draft_uri,
    }


@router.get("/clause-library")
async def list_clause_library(
    _auth=require_permission("drafting:generate"),
    contract_type: str | None = Query(None),
    category: str | None = Query(None),
    mandatory_only: bool = Query(False),
):
    """Browse the pre-approved clause library."""
    async with get_session() as session:
        query = select(ClauseLibrary).where(ClauseLibrary.is_active.is_(True))
        if contract_type:
            query = query.where(ClauseLibrary.contract_type == contract_type)
        if category:
            query = query.where(ClauseLibrary.clause_category == category)
        if mandatory_only:
            query = query.where(ClauseLibrary.is_mandatory.is_(True))
        query = query.order_by(ClauseLibrary.contract_type, ClauseLibrary.clause_category)
        result = await session.execute(query)
        clauses = result.scalars().all()

    return {
        "clauses": [
            ClauseLibraryResponse(
                id=str(cl.id),
                contract_type=cl.contract_type,
                clause_category=cl.clause_category,
                title_id=cl.title_id,
                title_en=cl.title_en,
                text_id=cl.text_id,
                text_en=cl.text_en,
                risk_notes=cl.risk_notes,
                is_mandatory=cl.is_mandatory,
                version=cl.version,
            )
            for cl in clauses
        ],
        "total": len(clauses),
    }


@router.get("/clause-library/{clause_id}")
async def get_clause(clause_id: str, _auth=require_permission("drafting:generate")):
    """Get a single clause from the library."""
    async with get_session() as session:
        result = await session.execute(
            select(ClauseLibrary).where(ClauseLibrary.id == uuid.UUID(clause_id))
        )
        clause = result.scalar_one_or_none()
        if not clause:
            raise HTTPException(status_code=404, detail="Clause not found")

    return ClauseLibraryResponse(
        id=str(clause.id),
        contract_type=clause.contract_type,
        clause_category=clause.clause_category,
        title_id=clause.title_id,
        title_en=clause.title_en,
        text_id=clause.text_id,
        text_en=clause.text_en,
        risk_notes=clause.risk_notes,
        is_mandatory=clause.is_mandatory,
        version=clause.version,
    )
