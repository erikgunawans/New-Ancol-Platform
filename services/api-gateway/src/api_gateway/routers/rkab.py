"""RKAB (Rencana Kerja dan Anggaran Bisnis) line items registry.

Drives the PD-03-RKAB BJR checklist item. A strategic decision outside an
approved RKAB voids BJR protection per Pergub DKI 127/2019.

The /match endpoint returns candidate RKAB line items for a given decision
title/description. v1 uses simple substring matching; Phase 6.3 upgrades to
Gemini Flash classification with confidence scoring.
"""

from __future__ import annotations

from datetime import date, datetime

from ancol_common.auth.rbac import require_permission
from ancol_common.bjr.matching import rank_by_token_overlap
from ancol_common.db.connection import get_session
from ancol_common.db.models import RKABLineItem
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

router = APIRouter(prefix="/rkab", tags=["RKAB Registry"])


class RKABLineItemResponse(BaseModel):
    id: str
    fiscal_year: int
    code: str
    category: str
    activity_name: str
    description: str | None = None
    budget_idr: float
    approval_status: str
    rups_approval_date: date | None = None
    is_active: bool
    effective_from: date | None = None
    effective_until: date | None = None
    created_at: datetime


class RKABLineItemCreate(BaseModel):
    fiscal_year: int = Field(ge=2020, le=2100)
    code: str = Field(min_length=1, max_length=100)
    category: str
    activity_name: str
    description: str | None = None
    budget_idr: float = Field(ge=0.0)
    approval_status: str = "draft"
    rups_approval_date: date | None = None


class RKABLineItemUpdate(BaseModel):
    activity_name: str | None = None
    description: str | None = None
    budget_idr: float | None = Field(default=None, ge=0.0)
    approval_status: str | None = None
    rups_approval_date: date | None = None
    is_active: bool | None = None


class RKABMatchRequest(BaseModel):
    decision_title: str
    decision_description: str | None = None
    fiscal_year: int


class RKABMatchCandidate(BaseModel):
    rkab_line_id: str
    code: str
    activity_name: str
    confidence: float
    rationale: str | None = None


class RKABMatchResponse(BaseModel):
    candidates: list[RKABMatchCandidate]
    best_match: RKABMatchCandidate | None = None


class RKABListResponse(BaseModel):
    items: list[RKABLineItemResponse]
    total: int


def _to_response(r: RKABLineItem) -> RKABLineItemResponse:
    return RKABLineItemResponse(
        id=str(r.id),
        fiscal_year=r.fiscal_year,
        code=r.code,
        category=r.category,
        activity_name=r.activity_name,
        description=r.description,
        budget_idr=float(r.budget_idr),
        approval_status=r.approval_status,
        rups_approval_date=r.rups_approval_date,
        is_active=r.is_active,
        effective_from=r.effective_from,
        effective_until=r.effective_until,
        created_at=r.created_at,
    )


@router.post("", response_model=RKABLineItemResponse)
async def create_rkab_line(
    payload: RKABLineItemCreate,
    _auth=require_permission("rkab:manage"),
):
    async with get_session() as session:
        item = RKABLineItem(
            fiscal_year=payload.fiscal_year,
            code=payload.code,
            category=payload.category,
            activity_name=payload.activity_name,
            description=payload.description,
            budget_idr=payload.budget_idr,
            approval_status=payload.approval_status,
            rups_approval_date=payload.rups_approval_date,
        )
        session.add(item)
        await session.commit()
        await session.refresh(item)
    return _to_response(item)


@router.get("", response_model=RKABListResponse)
async def list_rkab_lines(
    _auth=require_permission("rkab:view"),
    fiscal_year: int | None = Query(None),
    is_active: bool | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    async with get_session() as session:
        query = select(RKABLineItem)
        if fiscal_year is not None:
            query = query.where(RKABLineItem.fiscal_year == fiscal_year)
        if is_active is not None:
            query = query.where(RKABLineItem.is_active == is_active)
        query = query.order_by(RKABLineItem.fiscal_year.desc(), RKABLineItem.code).limit(limit)
        result = await session.execute(query)
        items = list(result.scalars().all())
    return RKABListResponse(items=[_to_response(r) for r in items], total=len(items))


@router.get("/{rkab_id}", response_model=RKABLineItemResponse)
async def get_rkab_line(
    rkab_id: str,
    _auth=require_permission("rkab:view"),
):
    async with get_session() as session:
        result = await session.execute(
            select(RKABLineItem).where(RKABLineItem.id == rkab_id)
        )
        item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "RKAB line item not found")
    return _to_response(item)


@router.patch("/{rkab_id}", response_model=RKABLineItemResponse)
async def update_rkab_line(
    rkab_id: str,
    payload: RKABLineItemUpdate,
    _auth=require_permission("rkab:manage"),
):
    async with get_session() as session:
        result = await session.execute(
            select(RKABLineItem).where(RKABLineItem.id == rkab_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise HTTPException(404, "RKAB line item not found")
        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(item, field, value)
        await session.commit()
        await session.refresh(item)
    return _to_response(item)


@router.post("/match", response_model=RKABMatchResponse)
async def match_rkab(
    payload: RKABMatchRequest,
    _auth=require_permission("rkab:view"),
):
    """Return candidate RKAB line items for a decision title/description.

    v1 implementation: case-insensitive token overlap against activity_name +
    category. Phase 6.3 replaces this with Gemini Flash classification.
    """
    async with get_session() as session:
        result = await session.execute(
            select(RKABLineItem).where(
                RKABLineItem.fiscal_year == payload.fiscal_year,
                RKABLineItem.is_active.is_(True),
            )
        )
        items = list(result.scalars().all())

    matches = rank_by_token_overlap(
        query=f"{payload.decision_title} {payload.decision_description or ''}",
        items=items,
        haystack_of=lambda r: f"{r.activity_name} {r.category} {r.description or ''}",
        top_n=3,
    )
    top = [
        RKABMatchCandidate(
            rkab_line_id=str(m.item.id),
            code=m.item.code,
            activity_name=m.item.activity_name,
            confidence=m.confidence,
            rationale=m.rationale,
        )
        for m in matches
    ]
    return RKABMatchResponse(
        candidates=top,
        best_match=top[0] if top and top[0].confidence >= 0.3 else None,
    )
