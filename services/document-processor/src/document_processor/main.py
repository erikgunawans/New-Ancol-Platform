"""Document Processor — FastAPI service for Document AI OCR pipeline.

Receives Cloud Storage events (via Eventarc/Pub/Sub), triggers Document AI OCR,
writes processed output to GCS, updates document status, publishes to Pub/Sub.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from ancol_common.db.connection import dispose_engine
from ancol_common.pubsub.subscriber import PubSubPushMessage, decode_pubsub_message
from fastapi import FastAPI, Request, Response

from .processor import process_document

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Document processor starting up")
    yield
    await dispose_engine()
    logger.info("Document processor shut down")


app = FastAPI(
    title="Ancol Document Processor",
    description="OCR pipeline: Cloud Storage → Document AI → Pub/Sub",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "document-processor"}


@app.post("/process")
async def handle_pubsub_push(request: Request):
    """Handle Pub/Sub push from Eventarc (Cloud Storage object.finalize event).

    Expected payload structure from Eventarc/Cloud Storage notification:
    {
      "message": {
        "data": base64({
          "bucket": "ancol-mom-raw",
          "name": "uploads/document.pdf",
          "contentType": "application/pdf",
          "size": "123456",
          "metadata": {"document_id": "uuid", "uploaded_by": "uuid"}
        }),
        "message_id": "...",
        "publish_time": "...",
        "attributes": {"eventType": "OBJECT_FINALIZE", ...}
      },
      "subscription": "projects/.../subscriptions/..."
    }
    """
    body = await request.json()

    try:
        push_message = PubSubPushMessage(**body)
        payload = decode_pubsub_message(push_message)
    except Exception:
        logger.exception("Failed to decode Pub/Sub message")
        return Response(status_code=400)

    bucket = payload.get("bucket", "")
    object_name = payload.get("name", "")
    document_id = payload.get("metadata", {}).get("document_id")

    if not bucket or not object_name:
        logger.error("Missing bucket or object name in payload: %s", payload)
        return Response(status_code=400)

    logger.info("Processing: gs://%s/%s (document_id=%s)", bucket, object_name, document_id)

    try:
        result = await process_document(
            bucket=bucket,
            object_name=object_name,
            document_id=document_id,
            content_type=payload.get("contentType", "application/pdf"),
            file_size=int(payload.get("size", 0)),
        )
        logger.info("Processing complete: %s", result)
        return {"status": "ok", "result": result}
    except Exception:
        logger.exception("Failed to process document: gs://%s/%s", bucket, object_name)
        return Response(status_code=500)
