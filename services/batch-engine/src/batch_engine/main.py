"""Batch Engine — FastAPI service for bulk MoM processing.

Provides endpoints to trigger and monitor batch processing jobs.
Runs as a Cloud Run service, triggered by API Gateway or Cloud Scheduler.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from ancol_common.db.connection import dispose_engine, get_session
from ancol_common.db.repository import get_batch_job, transition_batch_status
from fastapi import FastAPI, HTTPException

from .engine import run_batch_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Track running batch jobs to prevent duplicate execution
_running_jobs: dict[str, asyncio.Task] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Batch Engine starting up")
    yield
    # Cancel any running batch jobs on shutdown
    for job_id, task in _running_jobs.items():
        task.cancel()
        logger.info("Cancelled running batch job %s", job_id)
    await dispose_engine()
    logger.info("Batch Engine shut down")


app = FastAPI(
    title="Ancol Batch Engine",
    description="Batch processing engine for bulk MoM compliance auditing",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "batch-engine",
        "version": "0.1.0",
        "running_jobs": len(_running_jobs),
    }


@app.post("/run/{job_id}")
async def trigger_batch_run(job_id: str):
    """Start processing a batch job.

    The job runs in the background. Use GET /status/{job_id} to check progress.
    """
    if job_id in _running_jobs and not _running_jobs[job_id].done():
        raise HTTPException(status_code=409, detail="Batch job is already running")

    async with get_session() as session:
        job = await get_batch_job(session, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Batch job not found")
        if job.status not in ("queued", "paused"):
            raise HTTPException(
                status_code=400,
                detail=f"Job is {job.status}, must be queued or paused to start",
            )

    task = asyncio.create_task(run_batch_job(job_id))
    _running_jobs[job_id] = task

    # Clean up completed tasks
    for jid in list(_running_jobs):
        if _running_jobs[jid].done():
            del _running_jobs[jid]

    return {"status": "started", "job_id": job_id}


@app.post("/pause/{job_id}")
async def pause_batch_job(job_id: str):
    """Pause a running batch job. It will stop after current items complete."""
    async with get_session() as session:
        success = await transition_batch_status(session, job_id, "paused")
        if not success:
            raise HTTPException(status_code=400, detail="Cannot pause job")

    return {"status": "paused", "job_id": job_id}


@app.post("/resume/{job_id}")
async def resume_batch_job(job_id: str):
    """Resume a paused batch job."""
    async with get_session() as session:
        job = await get_batch_job(session, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Batch job not found")
        if job.status != "paused":
            raise HTTPException(status_code=400, detail="Job is not paused")

    task = asyncio.create_task(run_batch_job(job_id))
    _running_jobs[job_id] = task

    return {"status": "resumed", "job_id": job_id}


@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Get current status of a batch job."""
    async with get_session() as session:
        job = await get_batch_job(session, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Batch job not found")

    is_running = job_id in _running_jobs and not _running_jobs[job_id].done()
    progress = (job.processed_count + job.failed_count) / max(job.total_documents, 1) * 100

    return {
        "job_id": str(job.id),
        "name": job.name,
        "status": job.status,
        "is_running": is_running,
        "total_documents": job.total_documents,
        "processed_count": job.processed_count,
        "failed_count": job.failed_count,
        "progress_pct": round(progress, 1),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
