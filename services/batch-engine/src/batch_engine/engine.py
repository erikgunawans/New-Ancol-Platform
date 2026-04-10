"""Batch processing engine — orchestrates parallel document processing.

Processes batch jobs with configurable concurrency (10-50 docs),
exponential backoff retry, resumable checkpoints, and progress tracking.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from ancol_common.db.connection import get_session
from ancol_common.db.models import BatchItem, Document
from ancol_common.db.repository import (
    get_batch_job,
    get_next_batch_items,
    transition_batch_status,
    update_batch_item_status,
)
from ancol_common.gemini.rate_limiter import get_rate_limiter
from ancol_common.pubsub.publisher import publish_message

logger = logging.getLogger(__name__)

# Exponential backoff base delay (seconds)
RETRY_BASE_DELAY = 5.0
RETRY_MAX_DELAY = 120.0


async def run_batch_job(job_id: str) -> dict:
    """Execute a batch job: process all pending documents with concurrency control.

    Returns summary stats of the run.
    """
    async with get_session() as session:
        job = await get_batch_job(session, job_id)
        if not job:
            raise ValueError(f"Batch job {job_id} not found")

        if job.status not in ("queued", "paused"):
            raise ValueError(f"Batch job {job_id} is {job.status}, cannot start")

        await transition_batch_status(session, job_id, "running")
        concurrency = job.concurrency
        max_retries = job.max_retries

    logger.info("Starting batch job %s with concurrency=%d", job_id, concurrency)

    processed = 0
    failed = 0
    semaphore = asyncio.Semaphore(concurrency)

    while True:
        # Check if job was paused
        async with get_session() as session:
            job = await get_batch_job(session, job_id)
            if job and job.status == "paused":
                logger.info("Batch job %s paused, stopping", job_id)
                break

        # Get next batch of pending items
        async with get_session() as session:
            pending_items = await get_next_batch_items(session, job_id, limit=concurrency)

        if not pending_items:
            break

        # Process items concurrently with semaphore
        tasks = [
            _process_item_with_semaphore(
                semaphore, str(item.id), str(item.document_id), job_id, max_retries
            )
            for item in pending_items
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                failed += 1
                logger.error("Batch item failed: %s", result)
            elif result:
                processed += 1
            else:
                failed += 1

    # Finalize job status
    async with get_session() as session:
        job = await get_batch_job(session, job_id)
        if job and job.status == "running":
            await transition_batch_status(session, job_id, "completed")

    summary = {"job_id": job_id, "processed": processed, "failed": failed}
    logger.info("Batch job %s complete: %s", job_id, summary)
    return summary


async def _process_item_with_semaphore(
    semaphore: asyncio.Semaphore,
    item_id: str,
    document_id: str,
    job_id: str,
    max_retries: int,
) -> bool:
    """Process a single batch item with semaphore-limited concurrency."""
    async with semaphore:
        return await _process_single_item(item_id, document_id, job_id, max_retries)


async def _process_single_item(
    item_id: str,
    document_id: str,
    job_id: str,
    max_retries: int,
) -> bool:
    """Process a single document through the pipeline.

    Triggers document processing by resetting it to pending and publishing
    a mom-uploaded event. The existing agent pipeline handles the rest.
    """
    async with get_session() as session:
        await update_batch_item_status(session, item_id, "processing")

    try:
        # Rate limit Gemini API calls
        limiter = get_rate_limiter("gemini-2.5-flash")
        await limiter.acquire()

        # Reset document to pending to re-trigger the pipeline
        async with get_session() as session:
            doc = await session.get(Document, document_id)
            if not doc:
                raise ValueError(f"Document {document_id} not found")

            # Only re-process documents that are in a retriable state
            if doc.status in ("failed", "pending"):
                doc.status = "pending"
                doc.retry_count += 1
                gcs_raw_uri = doc.gcs_raw_uri
            elif doc.status == "complete":
                # Already processed — mark item complete
                async with get_session() as session2:
                    await update_batch_item_status(session2, item_id, "completed")
                _publish_progress(job_id, document_id, "completed")
                return True
            else:
                # Document is currently being processed — skip
                logger.info("Document %s is %s, skipping", document_id, doc.status)
                return True

        from ancol_common.utils import parse_gcs_uri

        bucket_name, blob_path = parse_gcs_uri(gcs_raw_uri)
        publish_message(
            "mom-uploaded",
            {
                "document_id": document_id,
                "bucket": bucket_name,
                "name": blob_path,
                "metadata": {"document_id": document_id, "batch_job_id": job_id},
            },
        )

        async with get_session() as session:
            await update_batch_item_status(session, item_id, "completed")

        _publish_progress(job_id, document_id, "completed")
        return True

    except Exception as e:
        logger.exception("Failed to process document %s", document_id)

        async with get_session() as session:
            item_result = await session.get(BatchItem, item_id)
            retry_count = item_result.retry_count if item_result else 0

            if retry_count < max_retries:
                # Retry with exponential backoff
                delay = min(RETRY_BASE_DELAY * (2**retry_count), RETRY_MAX_DELAY)
                logger.info(
                    "Retrying document %s in %.1fs (attempt %d/%d)",
                    document_id,
                    delay,
                    retry_count + 1,
                    max_retries,
                )
                if item_result:
                    item_result.retry_count += 1
                await update_batch_item_status(session, item_id, "retrying", str(e))

                await asyncio.sleep(delay)
                return await _process_single_item(item_id, document_id, job_id, max_retries)
            else:
                await update_batch_item_status(session, item_id, "failed", str(e))
                _publish_progress(job_id, document_id, "failed", str(e))
                return False


def _publish_progress(job_id: str, document_id: str, status: str, error: str | None = None) -> None:
    """Publish batch progress event to Pub/Sub."""
    try:
        publish_message(
            "batch-progress",
            {
                "batch_job_id": job_id,
                "document_id": document_id,
                "status": status,
                "error": error,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
    except Exception:
        logger.warning("Failed to publish batch progress event", exc_info=True)
