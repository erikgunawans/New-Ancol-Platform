"""Tests for the batch processing engine logic."""

from __future__ import annotations

import asyncio
from datetime import UTC

import pytest
from ancol_common.gemini.rate_limiter import TokenBucketRateLimiter, get_rate_limiter


class TestTokenBucketRateLimiter:
    """Tests for the async token bucket rate limiter."""

    @pytest.mark.asyncio
    async def test_initial_tokens(self):
        limiter = TokenBucketRateLimiter(rate=10.0, max_tokens=20)
        assert limiter.available_tokens == 20.0

    @pytest.mark.asyncio
    async def test_acquire_reduces_tokens(self):
        limiter = TokenBucketRateLimiter(rate=10.0, max_tokens=20)
        waited = await limiter.acquire(5)
        assert waited == 0.0
        # Allow tiny refill between acquire and check
        assert limiter.available_tokens <= 15.1

    @pytest.mark.asyncio
    async def test_acquire_waits_when_empty(self):
        limiter = TokenBucketRateLimiter(rate=100.0, max_tokens=2)
        await limiter.acquire(2)  # Drain the bucket
        waited = await limiter.acquire(1)  # Should wait
        assert waited > 0

    @pytest.mark.asyncio
    async def test_refill_over_time(self):
        limiter = TokenBucketRateLimiter(rate=1000.0, max_tokens=10)
        await limiter.acquire(10)  # Drain
        await asyncio.sleep(0.02)  # Wait for refill
        assert limiter.available_tokens > 0

    @pytest.mark.asyncio
    async def test_max_tokens_cap(self):
        limiter = TokenBucketRateLimiter(rate=1000.0, max_tokens=5)
        await asyncio.sleep(0.1)  # Over-refill
        assert limiter.available_tokens <= 5.0

    def test_get_rate_limiter_flash(self):
        limiter = get_rate_limiter("gemini-2.5-flash")
        assert limiter._rate == 33.0
        assert limiter._max_tokens == 50

    def test_get_rate_limiter_pro(self):
        limiter = get_rate_limiter("gemini-2.5-pro")
        assert limiter._rate == 16.0
        assert limiter._max_tokens == 25

    def test_get_rate_limiter_singleton(self):
        l1 = get_rate_limiter("test-model-singleton")
        l2 = get_rate_limiter("test-model-singleton")
        assert l1 is l2


class TestBatchStatusTransitions:
    """Tests for batch job status transition validation."""

    def test_valid_transitions(self):
        from ancol_common.db.repository import VALID_BATCH_TRANSITIONS

        assert "running" in VALID_BATCH_TRANSITIONS["queued"]
        assert "paused" in VALID_BATCH_TRANSITIONS["running"]
        assert "completed" in VALID_BATCH_TRANSITIONS["running"]
        assert "failed" in VALID_BATCH_TRANSITIONS["running"]
        assert "running" in VALID_BATCH_TRANSITIONS["paused"]
        assert VALID_BATCH_TRANSITIONS["completed"] == []

    def test_retry_from_failed(self):
        from ancol_common.db.repository import VALID_BATCH_TRANSITIONS

        assert "queued" in VALID_BATCH_TRANSITIONS["failed"]

    def test_cannot_transition_from_completed(self):
        from ancol_common.db.repository import VALID_BATCH_TRANSITIONS

        assert VALID_BATCH_TRANSITIONS["completed"] == []


class TestBatchSchemas:
    """Tests for batch Pydantic schemas."""

    def test_batch_job_create_validation(self):
        from ancol_common.schemas.batch import BatchJobCreate

        job = BatchJobCreate(
            name="Historical MoM Batch",
            document_ids=["id1", "id2", "id3"],
            concurrency=20,
        )
        assert job.name == "Historical MoM Batch"
        assert len(job.document_ids) == 3
        assert job.concurrency == 20
        assert job.max_retries == 3  # default

    def test_batch_job_create_defaults(self):
        from ancol_common.schemas.batch import BatchJobCreate, BatchPriorityOrder

        job = BatchJobCreate(name="Test", document_ids=["id1"])
        assert job.concurrency == 10
        assert job.max_retries == 3
        assert job.priority_order == BatchPriorityOrder.NEWEST_FIRST

    def test_batch_job_create_concurrency_bounds(self):
        from ancol_common.schemas.batch import BatchJobCreate

        with pytest.raises(Exception):
            BatchJobCreate(name="Test", document_ids=["id1"], concurrency=0)

        with pytest.raises(Exception):
            BatchJobCreate(name="Test", document_ids=["id1"], concurrency=100)

    def test_batch_job_create_empty_docs(self):
        from ancol_common.schemas.batch import BatchJobCreate

        with pytest.raises(Exception):
            BatchJobCreate(name="Test", document_ids=[])

    def test_batch_progress_event(self):
        from ancol_common.schemas.batch import BatchProgressEvent

        event = BatchProgressEvent(
            batch_job_id="job-1",
            document_id="doc-1",
            status="completed",
            processed_count=5,
            total_documents=10,
        )
        assert event.processed_count == 5
        assert event.error is None

    def test_batch_job_response(self):
        from datetime import datetime

        from ancol_common.schemas.batch import BatchJobResponse

        resp = BatchJobResponse(
            id="job-1",
            name="Test Batch",
            status="running",
            concurrency=10,
            max_retries=3,
            priority_order="newest_first",
            total_documents=100,
            processed_count=45,
            failed_count=5,
            progress_pct=50.0,
            created_by="user-1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert resp.progress_pct == 50.0
        assert resp.status == "running"
