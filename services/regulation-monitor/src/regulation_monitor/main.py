"""Regulation Monitor — FastAPI service triggered by Cloud Scheduler.

Checks OJK, IDX, and industry regulation sources for new/amended
regulations and notifies the Legal team when changes are detected.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from ancol_common.db.connection import dispose_engine
from fastapi import FastAPI

from .checker import check_all_sources
from .sources import ALL_SOURCES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Regulation Monitor starting up")
    yield
    await dispose_engine()
    logger.info("Regulation Monitor shut down")


app = FastAPI(
    title="Ancol Regulation Monitor",
    description="Auto-monitor OJK/IDX/industry regulation sources for changes",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "regulation-monitor",
        "version": "0.1.0",
        "monitored_sources": len(ALL_SOURCES),
    }


@app.post("/check")
async def trigger_check():
    """Trigger a regulation change check across all sources.

    Called by Cloud Scheduler (e.g., daily at 06:00 WIB) or manually.
    """
    logger.info("Starting regulation check across %d sources", len(ALL_SOURCES))

    changes = await check_all_sources()

    return {
        "status": "ok",
        "sources_checked": len(ALL_SOURCES),
        "changes_detected": len(changes),
        "changes": changes,
    }


@app.get("/sources")
async def list_sources():
    """List all monitored regulation sources."""
    return {
        "sources": [
            {
                "id": s.source_id,
                "name": s.name,
                "domain": s.domain,
                "url": f"{s.base_url}{s.search_path}",
                "keywords": s.keywords,
            }
            for s in ALL_SOURCES
        ],
    }
