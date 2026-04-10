"""Core document processing logic: Document AI OCR + GCS output + DB update + Pub/Sub."""

from __future__ import annotations

import json
import logging
import time
import uuid

from ancol_common.config import get_settings
from ancol_common.db.connection import get_session
from ancol_common.db.models import Document
from ancol_common.db.repository import transition_document_status
from ancol_common.pubsub.publisher import publish_message
from ancol_common.schemas.mom import DocumentStatus
from google.cloud import documentai_v1 as documentai
from google.cloud import storage

logger = logging.getLogger(__name__)


async def process_document(
    bucket: str,
    object_name: str,
    document_id: str | None,
    content_type: str,
    file_size: int,
) -> dict:
    """Full OCR pipeline for a single document.

    1. Transition status to processing_ocr
    2. Download raw file from GCS
    3. Call Document AI Form Parser for OCR
    4. Extract text, tables, and page-level confidence
    5. Write structured OCR output to processed bucket
    6. Update document record with results
    7. Transition status to ocr_complete
    8. Publish mom-ocr-complete event to Pub/Sub
    """
    settings = get_settings()
    start_time = time.time()

    # Step 1: Update status to processing_ocr
    if document_id:
        async with get_session() as session:
            await transition_document_status(session, document_id, DocumentStatus.PROCESSING_OCR)

    # Step 2: Download raw file from GCS
    storage_client = storage.Client()
    raw_bucket = storage_client.bucket(bucket)
    blob = raw_bucket.blob(object_name)
    raw_content = blob.download_as_bytes()
    logger.info("Downloaded %d bytes from gs://%s/%s", len(raw_content), bucket, object_name)

    # Step 3: Call Document AI
    docai_client = documentai.DocumentProcessorServiceClient()
    processor_name = settings.document_ai_processor

    if not processor_name:
        processor_name = (
            f"projects/{settings.gcp_project}/locations/{settings.gcp_region}"
            f"/processors/document-ai-form-parser"
        )

    mime_type = _resolve_mime_type(content_type, object_name)

    request = documentai.ProcessRequest(
        name=processor_name,
        raw_document=documentai.RawDocument(content=raw_content, mime_type=mime_type),
    )

    result = docai_client.process_document(request=request)
    document = result.document
    logger.info("Document AI processed: %d pages", len(document.pages))

    # Step 4: Extract structured OCR data
    ocr_output = _extract_ocr_output(document)

    # Step 5: Write to processed bucket
    processed_uri = _write_processed_output(settings, object_name, ocr_output, document_id)

    # Step 6: Update document record
    processing_time_ms = int((time.time() - start_time) * 1000)

    if document_id:
        async with get_session() as session:
            from sqlalchemy import update

            stmt = (
                update(Document)
                .where(Document.id == document_id)
                .values(
                    gcs_processed_uri=processed_uri,
                    ocr_confidence=ocr_output["overall_confidence"],
                    page_count=ocr_output["page_count"],
                )
            )
            await session.execute(stmt)

    # Step 7: Transition to ocr_complete
    if document_id:
        async with get_session() as session:
            await transition_document_status(session, document_id, DocumentStatus.OCR_COMPLETE)

    # Step 8: Publish event
    event_data = {
        "document_id": document_id or str(uuid.uuid4()),
        "processed_uri": processed_uri,
        "page_count": ocr_output["page_count"],
        "overall_confidence": ocr_output["overall_confidence"],
        "processing_time_ms": processing_time_ms,
    }
    publish_message("mom-ocr-complete", event_data)

    return {
        "document_id": document_id,
        "processed_uri": processed_uri,
        "page_count": ocr_output["page_count"],
        "overall_confidence": ocr_output["overall_confidence"],
        "processing_time_ms": processing_time_ms,
    }


def _resolve_mime_type(content_type: str, object_name: str) -> str:
    """Resolve MIME type from content type header or file extension."""
    if content_type and content_type != "application/octet-stream":
        return content_type

    ext = object_name.rsplit(".", 1)[-1].lower() if "." in object_name else ""
    mime_map = {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "tiff": "image/tiff",
        "tif": "image/tiff",
        "gif": "image/gif",
        "bmp": "image/bmp",
        "webp": "image/webp",
    }
    return mime_map.get(ext, "application/pdf")


def _extract_ocr_output(document: documentai.Document) -> dict:
    """Extract structured data from Document AI response."""
    pages = []
    total_confidence = 0.0

    for page in document.pages:
        page_data = {
            "page_number": page.page_number,
            "width": page.dimension.width if page.dimension else 0,
            "height": page.dimension.height if page.dimension else 0,
            "blocks": [],
            "tables": [],
            "detected_languages": [],
        }

        # Extract text blocks with confidence
        for block in page.blocks:
            block_text = _get_text_from_layout(block.layout, document.text)
            confidence = block.layout.confidence if block.layout else 0.0
            total_confidence += confidence

            page_data["blocks"].append(
                {
                    "text": block_text,
                    "confidence": round(confidence, 4),
                    "bounding_box": _get_bounding_box(block.layout),
                }
            )

        # Extract tables
        for table in page.tables:
            table_data = {
                "header_rows": [],
                "body_rows": [],
            }

            for row in table.header_rows:
                table_data["header_rows"].append(
                    [_get_text_from_layout(cell.layout, document.text) for cell in row.cells]
                )

            for row in table.body_rows:
                table_data["body_rows"].append(
                    [_get_text_from_layout(cell.layout, document.text) for cell in row.cells]
                )

            page_data["tables"].append(table_data)

        # Detected languages
        for lang in page.detected_languages:
            page_data["detected_languages"].append(
                {
                    "language_code": lang.language_code,
                    "confidence": round(lang.confidence, 4),
                }
            )

        pages.append(page_data)

    page_count = len(pages)
    total_blocks = sum(len(p["blocks"]) for p in pages)
    overall_confidence = round(total_confidence / max(total_blocks, 1), 4)

    return {
        "full_text": document.text,
        "page_count": page_count,
        "overall_confidence": overall_confidence,
        "pages": pages,
    }


def _get_text_from_layout(layout, full_text: str) -> str:
    """Extract text content from a Document AI layout element."""
    if not layout or not layout.text_anchor or not layout.text_anchor.text_segments:
        return ""

    segments = []
    for segment in layout.text_anchor.text_segments:
        start = int(segment.start_index) if segment.start_index else 0
        end = int(segment.end_index) if segment.end_index else 0
        segments.append(full_text[start:end])
    return "".join(segments).strip()


def _get_bounding_box(layout) -> list[dict] | None:
    """Extract bounding box vertices from layout."""
    if not layout or not layout.bounding_poly or not layout.bounding_poly.vertices:
        return None

    return [{"x": v.x, "y": v.y} for v in layout.bounding_poly.vertices]


def _write_processed_output(
    settings, object_name: str, ocr_output: dict, document_id: str | None
) -> str:
    """Write OCR output JSON to the processed bucket."""
    storage_client = storage.Client()
    processed_bucket = storage_client.bucket(settings.bucket_processed)

    # Use document_id as filename prefix if available, else derive from source
    base_name = object_name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    output_key = f"ocr/{document_id or base_name}/{base_name}.json"

    blob = processed_bucket.blob(output_key)
    blob.upload_from_string(
        json.dumps(ocr_output, ensure_ascii=False, default=str),
        content_type="application/json",
    )

    processed_uri = f"gs://{settings.bucket_processed}/{output_key}"
    logger.info("Wrote OCR output to %s", processed_uri)
    return processed_uri
