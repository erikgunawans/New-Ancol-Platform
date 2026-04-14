"""Extraction Agent — FastAPI service (Agent 1).

Receives Pub/Sub push messages (mom-ocr-complete), runs structured extraction
via Gemini Flash, stores results, publishes mom-extracted event.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from ancol_common.db.connection import dispose_engine, get_session
from ancol_common.db.models import Document, Extraction
from ancol_common.db.repository import transition_document_status
from ancol_common.pubsub.publisher import publish_message
from ancol_common.pubsub.subscriber import PubSubPushMessage, decode_pubsub_message
from ancol_common.schemas.mom import DocumentStatus
from fastapi import FastAPI, Request, Response

from .agent import extract_mom
from .contract_parser import extract_contract

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Extraction Agent starting up")
    yield
    await dispose_engine()
    logger.info("Extraction Agent shut down")


app = FastAPI(
    title="Ancol Extraction Agent",
    description="Agent 1: Structural extraction from OCR text using Gemini Flash",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "extraction-agent", "version": "0.1.0"}


@app.post("/extract")
async def handle_pubsub_push(request: Request):
    """Handle Pub/Sub push from mom-ocr-complete topic.

    Expected payload:
    {
      "document_id": "uuid",
      "processed_uri": "gs://bucket/ocr/doc-id/doc.json",
      "page_count": 5,
      "overall_confidence": 0.95
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
    processed_uri = payload.get("processed_uri")

    if not document_id or not processed_uri:
        logger.error("Missing document_id or processed_uri: %s", payload)
        return Response(status_code=400)

    logger.info("Extracting document %s from %s", document_id, processed_uri)

    try:
        # Transition to extracting
        async with get_session() as session:
            await transition_document_status(session, document_id, DocumentStatus.EXTRACTING)

        # Load OCR output from GCS
        ocr_data = await _load_ocr_output(processed_uri)

        # Load template for this document
        template_config = await _get_template_config(document_id)

        # Build extraction input
        from ancol_common.schemas.extraction import ExtractionInput

        extraction_input = ExtractionInput(
            document_id=document_id,
            ocr_text=ocr_data.get("full_text", ""),
            layout_map={},
            extracted_tables=[
                table for page in ocr_data.get("pages", []) for table in page.get("tables", [])
            ],
            page_confidences=[
                sum(b.get("confidence", 0) for b in page.get("blocks", []))
                / max(len(page.get("blocks", [])), 1)
                for page in ocr_data.get("pages", [])
            ],
            template=template_config,
        )

        # Run extraction
        result = await extract_mom(extraction_input)

        # Store extraction result in DB
        async with get_session() as session:
            extraction = Extraction(
                document_id=document_id,
                agent_version=result.processing_metadata.agent_version,
                model_used=result.processing_metadata.model_used,
                structured_mom=result.structured_mom.model_dump(mode="json"),
                attendees=[a.model_dump() for a in result.attendees],
                resolutions=[r.model_dump(mode="json") for r in result.resolutions],
                performance_data=result.performance_data.model_dump()
                if result.performance_data
                else None,
                structural_score=result.structural_score,
                field_confidence=result.field_confidence,
                deviation_flags=[d.model_dump() for d in result.deviation_flags],
                low_confidence_fields=result.low_confidence_fields,
                processing_time_ms=result.processing_metadata.processing_time_ms,
                prompt_tokens=result.processing_metadata.prompt_tokens,
                completion_tokens=result.processing_metadata.completion_tokens,
            )
            session.add(extraction)
            await session.flush()
            extraction_id = str(extraction.id)

        # Transition to HITL Gate 1
        async with get_session() as session:
            await transition_document_status(session, document_id, DocumentStatus.HITL_GATE_1)

        # Publish extraction complete event
        publish_message(
            "mom-extracted",
            {
                "document_id": document_id,
                "extraction_id": extraction_id,
                "structural_score": result.structural_score,
                "deviation_count": len(result.deviation_flags),
                "low_confidence_count": len(result.low_confidence_fields),
            },
        )

        logger.info(
            "Extraction stored: doc=%s, extraction=%s, score=%.1f",
            document_id,
            extraction_id,
            result.structural_score,
        )
        return {"status": "ok", "extraction_id": extraction_id}

    except Exception:
        logger.exception("Extraction failed for document %s", document_id)
        async with get_session() as session:
            await transition_document_status(session, document_id, DocumentStatus.FAILED)
        return Response(status_code=500)


@app.post("/extract-contract")
async def handle_contract_pubsub_push(request: Request):
    """Handle Pub/Sub push from contract-uploaded topic.

    Expected payload:
    {
      "contract_id": "uuid",
      "bucket": "ancol-contracts",
      "name": "uploads/contract-id/file.pdf",
      "contract_type": "vendor"
    }
    """
    body = await request.json()

    try:
        push_message = PubSubPushMessage(**body)
        payload = decode_pubsub_message(push_message)
    except Exception:
        logger.exception("Failed to decode Pub/Sub message for contract extraction")
        return Response(status_code=400)

    contract_id = payload.get("contract_id")
    bucket = payload.get("bucket")
    name = payload.get("name")
    contract_type = payload.get("contract_type", "vendor")

    if not contract_id or not bucket or not name:
        logger.error("Missing contract_id, bucket, or name: %s", payload)
        return Response(status_code=400)

    gcs_uri = f"gs://{bucket}/{name}"
    logger.info("Extracting contract %s from %s", contract_id, gcs_uri)

    try:
        # Load the raw document text via OCR helper
        ocr_data = await _load_ocr_output(gcs_uri)
        ocr_text = ocr_data.get("full_text", "") if isinstance(ocr_data, dict) else str(ocr_data)

        # Run contract extraction
        result = await extract_contract(
            ocr_text=ocr_text,
            contract_id=contract_id,
            contract_type=contract_type,
        )

        # Store results in database
        from ancol_common.db.repository import store_contract_extraction

        async with get_session() as session:
            await store_contract_extraction(
                session=session,
                contract_id=contract_id,
                extraction_data=result.model_dump(mode="json"),
                clauses=[c.model_dump() for c in result.clauses],
                parties=[p.model_dump() for p in result.parties],
                key_dates=result.key_dates,
                financial_terms=result.financial_terms,
                risk_summary=result.risk_summary,
            )

        # Publish extraction complete event
        publish_message(
            "contract-extracted",
            {
                "contract_id": contract_id,
                "clause_count": len(result.clauses),
                "party_count": len(result.parties),
                "risk_level": result.risk_summary.get("overall_risk_level", "unknown"),
                "risk_score": result.risk_summary.get("overall_risk_score"),
            },
        )

        logger.info(
            "Contract extraction stored: contract=%s, clauses=%d, risk=%s",
            contract_id,
            len(result.clauses),
            result.risk_summary.get("overall_risk_level", "unknown"),
        )
        return {"status": "ok", "contract_id": contract_id, "clause_count": len(result.clauses)}

    except Exception:
        logger.exception("Contract extraction failed for %s", contract_id)
        # Update contract status to failed
        from ancol_common.db.repository import transition_contract_status

        async with get_session() as session:
            await transition_contract_status(session, contract_id, "failed", "Extraction failed")
        return Response(status_code=500)


async def _load_ocr_output(processed_uri: str) -> dict:
    """Load OCR JSON from GCS processed bucket."""
    import json

    from google.cloud import storage

    # Parse gs://bucket/path
    parts = processed_uri.replace("gs://", "").split("/", 1)
    bucket_name = parts[0]
    blob_name = parts[1] if len(parts) > 1 else ""

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    content = blob.download_as_text()
    return json.loads(content)


async def _get_template_config(document_id: str):
    """Load the MoM template configuration for a document."""

    from ancol_common.db.models import MomTemplate
    from ancol_common.schemas.extraction import TemplateConfig

    async with get_session() as session:
        # Get document's template
        doc = await session.get(Document, document_id)
        if doc and doc.template_id:
            template = await session.get(MomTemplate, doc.template_id)
            if template:
                return TemplateConfig(
                    template_id=str(template.id),
                    template_name=template.name,
                    mom_type=template.mom_type,
                    required_sections=[
                        s["name"]
                        for s in template.required_sections.get("sections", [])
                        if s.get("required", False)
                    ],
                    quorum_rules=template.quorum_rules,
                    signature_rules=template.signature_rules,
                    field_definitions=template.field_definitions,
                )

    # Fallback: default regular template
    return TemplateConfig(
        template_id="default",
        template_name="Default Regular Meeting",
        mom_type="regular",
        required_sections=[
            "opening",
            "attendance",
            "quorum_verification",
            "agenda",
            "discussion",
            "resolutions",
            "closing",
            "signatures",
        ],
        quorum_rules={"min_percentage": 50, "chairman_required": True},
        signature_rules={"required_signers": ["chairman", "secretary"]},
        field_definitions={},
    )
