"""Reporting Agent — FastAPI service (Agent 4).

Receives Pub/Sub push messages after HITL Gate 3 approval,
generates scorecard + PDF + Excel reports, stores results.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from ancol_common.config import get_settings
from ancol_common.db.connection import dispose_engine, get_session
from ancol_common.db.models import ComplianceFindingRecord, Extraction, Report
from ancol_common.db.repository import transition_document_status
from ancol_common.pubsub.publisher import publish_message
from ancol_common.pubsub.subscriber import PubSubPushMessage, decode_pubsub_message
from ancol_common.schemas.mom import DocumentStatus
from ancol_common.schemas.reporting import ReportingInput
from fastapi import FastAPI, Request, Response
from google.cloud import storage

from .agent import generate_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Reporting Agent starting up")
    yield
    await dispose_engine()
    logger.info("Reporting Agent shut down")


app = FastAPI(
    title="Ancol Reporting Agent",
    description="Agent 4: Scorecard, PDF, Excel compliance report generation",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "reporting-agent", "version": "0.1.0"}


@app.post("/report")
async def handle_pubsub_push(request: Request):
    """Handle Pub/Sub push after HITL Gate 3 approval.

    Expected payload:
    {
      "document_id": "uuid",
      "findings_id": "uuid",
      "structural_score": 85.0
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
    findings_id = payload.get("findings_id")

    if not document_id or not findings_id:
        logger.error("Missing required fields: %s", payload)
        return Response(status_code=400)

    logger.info("Generating report for document %s", document_id)

    try:
        async with get_session() as session:
            await transition_document_status(session, document_id, DocumentStatus.REPORTING)

        # Load findings + extraction data
        findings_data, structural_score = await _load_findings_data(document_id, findings_id)

        reporting_input = ReportingInput(
            document_id=document_id,
            findings_id=findings_id,
            structural_score=structural_score,
            findings_json=findings_data,
        )

        result = await generate_report(reporting_input)

        # Upload PDF and Excel to GCS
        settings = get_settings()
        pdf_uri = await _upload_pdf(settings, document_id, result.detailed_findings_html)
        excel_uri = await _upload_excel(settings, document_id, result)

        # Store report
        async with get_session() as session:
            report = Report(
                document_id=document_id,
                findings_id=findings_id,
                agent_version=result.processing_metadata.agent_version,
                model_used=result.processing_metadata.model_used,
                structural_score=result.scorecard.structural_score,
                substantive_score=result.scorecard.substantive_score,
                regulatory_score=result.scorecard.regulatory_score,
                composite_score=result.scorecard.composite_score,
                score_weights=result.scorecard.weights,
                corrective_suggestions=[
                    cs.model_dump() if hasattr(cs, "model_dump") else cs
                    for cs in result.corrective_suggestions
                ],
                gcs_pdf_uri=pdf_uri,
                gcs_excel_uri=excel_uri,
                report_data=result.report_data,
                processing_time_ms=result.processing_metadata.processing_time_ms,
                prompt_tokens=result.processing_metadata.prompt_tokens,
                completion_tokens=result.processing_metadata.completion_tokens,
            )
            session.add(report)
            await session.flush()
            report_id = str(report.id)

        # Transition to HITL Gate 4 (final dual approval)
        async with get_session() as session:
            await transition_document_status(session, document_id, DocumentStatus.HITL_GATE_4)

        publish_message(
            "mom-reported",
            {
                "document_id": document_id,
                "report_id": report_id,
                "composite_score": result.scorecard.composite_score,
                "pdf_uri": pdf_uri,
                "excel_uri": excel_uri,
            },
        )

        logger.info("Report stored: doc=%s, report=%s", document_id, report_id)
        return {"status": "ok", "report_id": report_id}

    except Exception:
        logger.exception("Report generation failed for document %s", document_id)
        async with get_session() as session:
            await transition_document_status(session, document_id, DocumentStatus.FAILED)
        return Response(status_code=500)


async def _load_findings_data(document_id: str, findings_id: str) -> tuple[dict, float]:
    """Load findings and structural score from DB."""
    async with get_session() as session:
        findings = await session.get(ComplianceFindingRecord, findings_id)

        # Get structural score from extraction
        from sqlalchemy import select

        stmt = (
            select(Extraction)
            .where(Extraction.document_id == document_id)
            .order_by(Extraction.created_at.desc())
        )
        result = await session.execute(stmt)
        extraction = result.scalars().first()

    findings_data = {}
    structural_score = 0.0

    if findings:
        findings_data = {
            "findings": findings.findings,
            "red_flags": findings.red_flags,
            "consistency_report": findings.consistency_report,
            "substantive_score": float(findings.substantive_score or 0),
            "regulatory_score": float(findings.regulatory_score or 0),
        }

    if extraction:
        structural_score = float(extraction.structural_score or 0)

    return findings_data, structural_score


async def _upload_pdf(settings, document_id: str, html: str) -> str | None:
    """Render and upload PDF to GCS reports bucket."""
    import os
    import tempfile

    from .generators.pdf import render_pdf

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            output_path = render_pdf(html, tmp.name)

        gcs_key = f"reports/{document_id}/compliance-report.pdf"
        client = storage.Client()
        bucket = client.bucket(settings.bucket_reports)
        blob = bucket.blob(gcs_key)
        blob.upload_from_filename(output_path, content_type="application/pdf")
        os.unlink(output_path)

        uri = f"gs://{settings.bucket_reports}/{gcs_key}"
        logger.info("PDF uploaded: %s", uri)
        return uri
    except Exception:
        logger.exception("PDF upload failed")
        return None


async def _upload_excel(settings, document_id: str, result) -> str | None:
    """Generate and upload Excel to GCS reports bucket."""
    from .generators.excel import generate_excel

    try:
        excel_bytes = generate_excel(
            document_id=document_id,
            meeting_date="",
            meeting_number="",
            scorecard=result.scorecard.model_dump(),
            findings=result.report_data.get("findings", []),
            corrective_suggestions=result.report_data.get("corrective_suggestions", []),
        )

        gcs_key = f"reports/{document_id}/compliance-report.xlsx"
        client = storage.Client()
        bucket = client.bucket(settings.bucket_reports)
        blob = bucket.blob(gcs_key)
        blob.upload_from_string(
            excel_bytes,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        uri = f"gs://{settings.bucket_reports}/{gcs_key}"
        logger.info("Excel uploaded: %s", uri)
        return uri
    except Exception:
        logger.exception("Excel upload failed")
        return None
