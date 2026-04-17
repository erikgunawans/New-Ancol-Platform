"""RJPP (Rencana Jangka Panjang Perusahaan) themes registry.

Drives the PD-04-RJPP BJR checklist item. Decisions align to an RJPP theme
per Pergub DKI 10/2012. RJPP is a 5-year strategic plan.
"""

from __future__ import annotations

from datetime import datetime

from ancol_common.auth.rbac import require_permission
from ancol_common.db.connection import get_session
from ancol_common.db.models import RJPPTheme
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

router = APIRouter(prefix="/rjpp", tags=["RJPP Registry"])


class RJPPThemeResponse(BaseModel):
    id: str
    period_start_year: int
    period_end_year: int
    theme_name: str
    description: str | None = None
    target_metrics: dict | None = None
    approval_ref: str | None = None
    is_active: bool
    created_at: datetime


class RJPPThemeCreate(BaseModel):
    period_start_year: int = Field(ge=2020, le=2100)
    period_end_year: int = Field(ge=2020, le=2100)
    theme_name: str
    description: str | None = None
    target_metrics: dict = Field(default_factory=dict)
    approval_ref: str | None = None


class RJPPThemeUpdate(BaseModel):
    theme_name: str | None = None
    description: str | None = None
    target_metrics: dict | None = None
    approval_ref: str | None = None
    is_active: bool | None = None


class RJPPListResponse(BaseModel):
    themes: list[RJPPThemeResponse]
    total: int


def _to_response(r: RJPPTheme) -> RJPPThemeResponse:
    return RJPPThemeResponse(
        id=str(r.id),
        period_start_year=r.period_start_year,
        period_end_year=r.period_end_year,
        theme_name=r.theme_name,
        description=r.description,
        target_metrics=r.target_metrics,
        approval_ref=r.approval_ref,
        is_active=r.is_active,
        created_at=r.created_at,
    )


@router.post("", response_model=RJPPThemeResponse)
async def create_rjpp_theme(
    payload: RJPPThemeCreate,
    _auth=require_permission("rjpp:manage"),
):
    if payload.period_end_year < payload.period_start_year:
        raise HTTPException(422, "period_end_year must be >= period_start_year")
    async with get_session() as session:
        theme = RJPPTheme(
            period_start_year=payload.period_start_year,
            period_end_year=payload.period_end_year,
            theme_name=payload.theme_name,
            description=payload.description,
            target_metrics=payload.target_metrics,
            approval_ref=payload.approval_ref,
        )
        session.add(theme)
        await session.commit()
        await session.refresh(theme)
    return _to_response(theme)


@router.get("", response_model=RJPPListResponse)
async def list_rjpp_themes(
    _auth=require_permission("rjpp:view"),
    is_active: bool | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    async with get_session() as session:
        query = select(RJPPTheme)
        if is_active is not None:
            query = query.where(RJPPTheme.is_active == is_active)
        query = query.order_by(RJPPTheme.period_start_year.desc()).limit(limit)
        result = await session.execute(query)
        themes = list(result.scalars().all())
    return RJPPListResponse(themes=[_to_response(t) for t in themes], total=len(themes))


@router.get("/{rjpp_id}", response_model=RJPPThemeResponse)
async def get_rjpp_theme(
    rjpp_id: str,
    _auth=require_permission("rjpp:view"),
):
    async with get_session() as session:
        result = await session.execute(select(RJPPTheme).where(RJPPTheme.id == rjpp_id))
        theme = result.scalar_one_or_none()
    if theme is None:
        raise HTTPException(404, "RJPP theme not found")
    return _to_response(theme)


@router.patch("/{rjpp_id}", response_model=RJPPThemeResponse)
async def update_rjpp_theme(
    rjpp_id: str,
    payload: RJPPThemeUpdate,
    _auth=require_permission("rjpp:manage"),
):
    async with get_session() as session:
        result = await session.execute(select(RJPPTheme).where(RJPPTheme.id == rjpp_id))
        theme = result.scalar_one_or_none()
        if theme is None:
            raise HTTPException(404, "RJPP theme not found")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(theme, field, value)
        await session.commit()
        await session.refresh(theme)
    return _to_response(theme)
