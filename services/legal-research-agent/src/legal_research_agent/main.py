"""Legal Research Agent — FastAPI service (Agent 2).

Receives Pub/Sub push messages after HITL Gate 1 approval,
maps resolutions to applicable regulations via Gemini Pro + Vertex AI Search,
validates citations, stores results, publishes event.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date

from ancol_common.db.connection import dispose_engine, get_session
from ancol_common.db.models import Extraction, RegulatoryContext
from ancol_common.db.repository import transition_document_status
from ancol_common.pubsub.publisher import publish_message
from ancol_common.pubsub.subscriber import PubSubPushMessage, decode_pubsub_message
from ancol_common.schemas.legal_research import LegalResearchInput
from ancol_common.schemas.mom import DocumentStatus
from fastapi import FastAPI, Request, Response

from .agent import research_regulations

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Legal Research Agent starting up")
    yield
    await dispose_engine()
    logger.info("Legal Research Agent shut down")


app = FastAPI(
    title="Ancol Legal Research Agent",
    description="Agent 2: Regulatory mapping via Gemini Pro + Vertex AI Search RAG",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "legal-research-agent", "version": "0.1.0"}


@app.post("/research")
async def handle_pubsub_push(request: Request):
    """Handle Pub/Sub push after HITL Gate 1 approval.

    Expected payload:
    {
      "document_id": "uuid",
      "extraction_id": "uuid"
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

    if not document_id or not extraction_id:
        logger.error("Missing document_id or extraction_id: %s", payload)
        return Response(status_code=400)

    logger.info("Researching regulations for document %s", document_id)

    try:
        # Transition to researching
        async with get_session() as session:
            await transition_document_status(session, document_id, DocumentStatus.RESEARCHING)

        # Load extraction data
        extraction_data = await _load_extraction(document_id, extraction_id)
        if not extraction_data:
            logger.error("Extraction %s not found for document %s", extraction_id, document_id)
            return Response(status_code=404)

        structured_mom = extraction_data["structured_mom"]
        meeting_date_str = structured_mom.get("meeting_date", date.today().isoformat())

        # Build resolution topics from extraction
        resolution_topics = [
            {
                "number": r.get("number", str(i)),
                "text": r.get("text", ""),
                "assignee": r.get("assignee"),
                "deadline": r.get("deadline"),
                "agenda_item": r.get("agenda_item"),
            }
            for i, r in enumerate(extraction_data.get("resolutions", []), 1)
        ]

        # Build input
        research_input = LegalResearchInput(
            document_id=document_id,
            extraction_id=extraction_id,
            structured_mom_json=structured_mom,
            meeting_date=date.fromisoformat(meeting_date_str),
            resolution_topics=resolution_topics,
        )

        # Run research
        result = await research_regulations(research_input)

        # Store result
        async with get_session() as session:
            reg_context = RegulatoryContext(
                document_id=document_id,
                extraction_id=extraction_id,
                agent_version=result.processing_metadata.agent_version,
                model_used=result.processing_metadata.model_used,
                regulatory_mapping=[m.model_dump(mode="json") for m in result.regulatory_mapping],
                overlap_flags=[f.model_dump() for f in result.overlap_flags],
                conflict_flags=[f.model_dump() for f in result.conflict_flags],
                corpus_freshness=result.corpus_freshness.model_dump(mode="json"),
                processing_time_ms=result.processing_metadata.processing_time_ms,
                prompt_tokens=result.processing_metadata.prompt_tokens,
                completion_tokens=result.processing_metadata.completion_tokens,
            )
            session.add(reg_context)
            await session.flush()
            context_id = str(reg_context.id)

        # Transition to HITL Gate 2
        async with get_session() as session:
            await transition_document_status(session, document_id, DocumentStatus.HITL_GATE_2)

        # Publish event
        publish_message(
            "mom-researched",
            {
                "document_id": document_id,
                "extraction_id": extraction_id,
                "regulatory_context_id": context_id,
                "mapping_count": len(result.regulatory_mapping),
                "overlap_count": len(result.overlap_flags),
                "conflict_count": len(result.conflict_flags),
            },
        )

        logger.info(
            "Research stored: doc=%s, context=%s, mappings=%d",
            document_id,
            context_id,
            len(result.regulatory_mapping),
        )
        return {"status": "ok", "regulatory_context_id": context_id}

    except Exception:
        logger.exception("Legal research failed for document %s", document_id)
        async with get_session() as session:
            await transition_document_status(session, document_id, DocumentStatus.FAILED)
        return Response(status_code=500)


async def _load_extraction(document_id: str, extraction_id: str) -> dict | None:
    """Load extraction output from DB."""
    async with get_session() as session:
        extraction = await session.get(Extraction, extraction_id)
        if not extraction or str(extraction.document_id) != document_id:
            return None

        return {
            "structured_mom": extraction.structured_mom,
            "attendees": extraction.attendees,
            "resolutions": extraction.resolutions,
            "performance_data": extraction.performance_data,
        }
