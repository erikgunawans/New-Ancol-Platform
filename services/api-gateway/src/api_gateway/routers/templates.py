"""Templates API — version registry, timeline, auto-select by meeting date."""

from __future__ import annotations

from datetime import date

from ancol_common.db.connection import get_session
from ancol_common.db.models import MomTemplate
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

router = APIRouter(prefix="/templates", tags=["Templates"])


class TemplateResponse(BaseModel):
    id: str
    name: str
    version: int
    mom_type: str
    effective_from: date
    effective_until: date | None = None
    is_active: bool
    required_sections: dict
    quorum_rules: dict
    signature_rules: dict


class TemplateListResponse(BaseModel):
    templates: list[TemplateResponse]
    total: int


class TemplateTimelineEntry(BaseModel):
    version: int
    effective_from: date
    effective_until: date | None = None
    is_current: bool


class TemplateTimelineResponse(BaseModel):
    mom_type: str
    timeline: list[TemplateTimelineEntry]


def _template_to_response(t: MomTemplate) -> TemplateResponse:
    return TemplateResponse(
        id=str(t.id),
        name=t.name,
        version=t.version,
        mom_type=t.mom_type,
        effective_from=t.effective_from,
        effective_until=t.effective_until,
        is_active=t.is_active,
        required_sections=t.required_sections,
        quorum_rules=t.quorum_rules,
        signature_rules=t.signature_rules,
    )


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    mom_type: str | None = Query(None),
    active_only: bool = Query(True),
):
    """List all MoM templates, optionally filtered by type."""
    async with get_session() as session:
        query = select(MomTemplate).order_by(
            MomTemplate.mom_type, MomTemplate.effective_from.desc()
        )
        if mom_type:
            query = query.where(MomTemplate.mom_type == mom_type)
        if active_only:
            query = query.where(MomTemplate.is_active.is_(True))

        result = await session.execute(query)
        templates = result.scalars().all()

    return TemplateListResponse(
        templates=[_template_to_response(t) for t in templates],
        total=len(templates),
    )


@router.get("/resolve", response_model=TemplateResponse)
async def resolve_template(
    mom_type: str = Query(..., description="MoM type: regular, circular, extraordinary"),
    meeting_date: date = Query(..., description="Meeting date to find the applicable template"),
):
    """Auto-resolve the correct template version for a given meeting date.

    Selects the template with the latest effective_from that is <= meeting_date
    and whose effective_until is null or >= meeting_date.
    """
    async with get_session() as session:
        query = (
            select(MomTemplate)
            .where(
                MomTemplate.mom_type == mom_type,
                MomTemplate.effective_from <= meeting_date,
                MomTemplate.is_active.is_(True),
            )
            .order_by(MomTemplate.effective_from.desc())
            .limit(1)
        )
        result = await session.execute(query)
        template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=404,
            detail=f"No template found for {mom_type} meetings on {meeting_date}",
        )

    # Check effective_until if set
    if template.effective_until and meeting_date > template.effective_until:
        raise HTTPException(
            status_code=404,
            detail=f"Template expired on {template.effective_until}. Meeting date {meeting_date} is out of range.",
        )

    return _template_to_response(template)


@router.get("/timeline/{mom_type}", response_model=TemplateTimelineResponse)
async def get_template_timeline(mom_type: str):
    """Get the version timeline for a MoM type — shows how templates evolved over time."""
    today = date.today()

    async with get_session() as session:
        result = await session.execute(
            select(MomTemplate)
            .where(MomTemplate.mom_type == mom_type)
            .order_by(MomTemplate.effective_from.asc())
        )
        templates = result.scalars().all()

    if not templates:
        raise HTTPException(status_code=404, detail=f"No templates for type: {mom_type}")

    timeline = [
        TemplateTimelineEntry(
            version=t.version,
            effective_from=t.effective_from,
            effective_until=t.effective_until,
            is_current=(
                t.effective_from <= today
                and (t.effective_until is None or t.effective_until >= today)
                and t.is_active
            ),
        )
        for t in templates
    ]

    return TemplateTimelineResponse(mom_type=mom_type, timeline=timeline)
