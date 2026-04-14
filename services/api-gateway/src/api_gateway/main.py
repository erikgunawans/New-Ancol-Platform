"""API Gateway — FastAPI central REST API.

Exposes all endpoints for the Ancol MoM Compliance System:
- Documents: upload, list, get, status tracking
- HITL: review queue, review detail, submit decisions
- Reports: list, get, download PDF/Excel
- Users: list, get
- Audit: immutable audit trail viewer
- Dashboard: aggregate statistics
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from ancol_common.db.connection import dispose_engine
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import (
    analytics,
    audit,
    batch,
    contracts,
    dashboard,
    documents,
    drafting,
    hitl,
    obligations,
    reports,
    retroactive,
    templates,
    users,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("API Gateway starting up")
    yield
    await dispose_engine()
    logger.info("API Gateway shut down")


app = FastAPI(
    title="Ancol MoM Compliance API",
    description=(
        "Central REST API for the Agentic AI MoM Compliance System"
        " — PT Pembangunan Jaya Ancol Tbk"
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.ancol.co.id"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(documents.router, prefix="/api")
app.include_router(hitl.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(batch.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(templates.router, prefix="/api")
app.include_router(retroactive.router, prefix="/api")
app.include_router(contracts.router, prefix="/api")
app.include_router(obligations.router, prefix="/api")
app.include_router(drafting.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "api-gateway", "version": "0.1.0"}


@app.get("/api")
async def api_root():
    return {
        "service": "Ancol MoM Compliance API",
        "version": "0.1.0",
        "endpoints": {
            "documents": "/api/documents",
            "hitl": "/api/hitl",
            "reports": "/api/reports",
            "users": "/api/users",
            "audit": "/api/audit",
            "dashboard": "/api/dashboard",
            "batch": "/api/batch",
            "analytics": "/api/analytics",
            "templates": "/api/templates",
            "retroactive": "/api/retroactive",
            "contracts": "/api/contracts",
            "obligations": "/api/obligations",
            "drafting": "/api/drafting",
        },
    }
