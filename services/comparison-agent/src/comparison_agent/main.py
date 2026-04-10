"""Comparison Agent — FastAPI service (Agent 3).

Receives Pub/Sub push messages after HITL Gate 2 approval,
performs compliance comparison, stores findings, publishes event.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from ancol_common.db.connection import dispose_engine, get_session
from ancol_common.db.models import ComplianceFindingRecord, Extraction, RegulatoryContext
from ancol_common.db.repository import transition_document_status
from ancol_common.pubsub.publisher import publish_message
from ancol_common.pubsub.subscriber import PubSubPushMessage, decode_pubsub_message
from ancol_common.schemas.comparison import ComparisonInput
from ancol_common.schemas.mom import DocumentStatus
from fastapi import FastAPI, Request, Response

from .agent import compare_compliance

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Comparison Agent starting up")
    yield
    await dispose_engine()
    logger.info("Comparison Agent shut down")


app = FastAPI(
    title="Ancol Comparison Agent",
    description="Agent 3: Compliance comparison with chain-of-thought reasoning",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "comparison-agent", "version": "0.1.0"}


@app.post("/compare")
async def handle_pubsub_push(request: Request):
    """Handle Pub/Sub push after HITL Gate 2 approval.

    Expected payload:
    {
      "document_id": "uuid",
      "extraction_id": "uuid",
      "regulatory_context_id": "uuid"
    }
    """
    body = await request.json()

    try:
        push_message = PubSubPushMessage(**body)
        payload = decode_pubsub_message(push_message)
    except Exception:
        logger.exception("Failed to decode Pub/Sub message")
        return Response(status_code=400)

    document_id = payload.get("document_id")
    extraction_id = payload.get("extraction_id")
    regulatory_context_id = payload.get("regulatory_context_id")

    if not all([document_id, extraction_id, regulatory_context_id]):
        logger.error("Missing required fields: %s", payload)
        return Response(status_code=400)

    logger.info("Comparing compliance for document %s", document_id)

    try:
        async with get_session() as session:
            await transition_document_status(session, document_id, DocumentStatus.COMPARING)

        # Load data from DB
        extraction_data, reg_context_data, rpt_entities = await _load_comparison_data(
            extraction_id, regulatory_context_id
        )

        comparison_input = ComparisonInput(
            document_id=document_id,
            extraction_id=extraction_id,
            regulatory_context_id=regulatory_context_id,
            structured_mom_json=extraction_data["structured_mom"],
            regulatory_mapping_json=reg_context_data["regulatory_mapping"],
            related_party_entities=rpt_entities,
        )

        result = await compare_compliance(comparison_input)

        # Store findings
        async with get_session() as session:
            finding_record = ComplianceFindingRecord(
                document_id=document_id,
                regulatory_context_id=regulatory_context_id,
                agent_version=result.processing_metadata.agent_version,
                model_used=result.processing_metadata.model_used,
                findings=[
                    f.model_dump() if hasattr(f, "model_dump") else f for f in result.findings
                ],
                red_flags=result.red_flags.model_dump(),
                consistency_report=[
                    c.model_dump() if hasattr(c, "model_dump") else c
                    for c in result.consistency_report
                ],
                substantive_score=result.substantive_score,
                regulatory_score=result.regulatory_score,
                processing_time_ms=result.processing_metadata.processing_time_ms,
                prompt_tokens=result.processing_metadata.prompt_tokens,
                completion_tokens=result.processing_metadata.completion_tokens,
            )
            session.add(finding_record)
            await session.flush()
            findings_id = str(finding_record.id)

        async with get_session() as session:
            await transition_document_status(session, document_id, DocumentStatus.HITL_GATE_3)

        publish_message(
            "mom-compared",
            {
                "document_id": document_id,
                "findings_id": findings_id,
                "finding_count": len(result.findings),
                "red_flag_count": result.red_flags.total_count,
                "critical_count": result.red_flags.critical_count,
                "substantive_score": result.substantive_score,
                "regulatory_score": result.regulatory_score,
            },
        )

        logger.info("Comparison stored: doc=%s, findings=%s", document_id, findings_id)
        return {"status": "ok", "findings_id": findings_id}

    except Exception:
        logger.exception("Comparison failed for document %s", document_id)
        async with get_session() as session:
            await transition_document_status(session, document_id, DocumentStatus.FAILED)
        return Response(status_code=500)


async def _load_comparison_data(extraction_id: str, reg_context_id: str):
    """Load extraction and regulatory context from DB."""
    from ancol_common.db.models import RelatedPartyEntity
    from sqlalchemy import select

    async with get_session() as session:
        extraction = await session.get(Extraction, extraction_id)
        reg_context = await session.get(RegulatoryContext, reg_context_id)

        # Load RPT entities
        stmt = select(RelatedPartyEntity).where(RelatedPartyEntity.is_active.is_(True))
        result = await session.execute(stmt)
        rpt_entities = [
            {
                "entity_name": e.entity_name,
                "entity_type": e.entity_type,
                "relationship_description": e.relationship_description,
            }
            for e in result.scalars().all()
        ]

    extraction_data = {
        "structured_mom": extraction.structured_mom if extraction else {},
        "resolutions": extraction.resolutions if extraction else [],
    }
    reg_context_data = {
        "regulatory_mapping": reg_context.regulatory_mapping if reg_context else {},
    }

    return extraction_data, reg_context_data, rpt_entities
