"""Email Ingest — FastAPI service triggered by Cloud Scheduler.

Polls the Corporate Secretary's Gmail inbox for MoM attachments,
downloads them, uploads to GCS, and triggers the document pipeline.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from ancol_common.db.connection import dispose_engine
from fastapi import FastAPI, Request, Response

from .scanner import scan_inbox

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Email Ingest service starting up")
    yield
    await dispose_engine()
    logger.info("Email Ingest service shut down")


app = FastAPI(
    title="Ancol Email Ingest",
    description="Auto-ingest MoM documents from Gmail",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "email-ingest", "version": "0.1.0"}


@app.post("/scan")
async def trigger_scan(request: Request):
    """Trigger a Gmail inbox scan.

    Called by Cloud Scheduler on a cron schedule (e.g., every 15 minutes)
    or manually via the API.
    """
    logger.info("Starting email inbox scan")

    try:
        results = await scan_inbox(max_results=20)
        logger.info("Scan complete: %d documents ingested", len(results))
        return {
            "status": "ok",
            "documents_ingested": len(results),
            "documents": results,
        }
    except Exception:
        logger.exception("Email scan failed")
        return Response(status_code=500)
