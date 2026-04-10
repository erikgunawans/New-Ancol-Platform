"""Async token bucket rate limiter for Gemini API calls during batch processing.

Implements a per-model token bucket that refills at a fixed rate,
preventing Gemini API quota exhaustion during bulk document processing.
"""

from __future__ import annotations

import asyncio
import time


class TokenBucketRateLimiter:
    """Async token bucket rate limiter.

    Args:
        rate: Tokens added per second (requests/sec).
        max_tokens: Maximum bucket capacity (burst size).
    """

    def __init__(self, rate: float, max_tokens: int) -> None:
        self._rate = rate
        self._max_tokens = max_tokens
        self._tokens = float(max_tokens)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._max_tokens, self._tokens + elapsed * self._rate)
        self._last_refill = now

    async def acquire(self, tokens: int = 1) -> float:
        """Acquire tokens, waiting if necessary.

        Returns the time spent waiting (seconds).
        """
        waited = 0.0
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return waited
                deficit = tokens - self._tokens
                wait_time = deficit / self._rate
            # Release lock before sleeping so other coroutines aren't blocked
            waited += wait_time
            await asyncio.sleep(wait_time)

    @property
    def available_tokens(self) -> float:
        self._refill()
        return self._tokens


# Pre-configured limiters per model tier
# Gemini 2.5 Flash: 2000 RPM = ~33 RPS, burst 50
# Gemini 2.5 Pro: 1000 RPM = ~16 RPS, burst 25
_limiters: dict[str, TokenBucketRateLimiter] = {}


def get_rate_limiter(model: str) -> TokenBucketRateLimiter:
    """Get or create a rate limiter for a Gemini model."""
    if model not in _limiters:
        if "pro" in model.lower():
            _limiters[model] = TokenBucketRateLimiter(rate=16.0, max_tokens=25)
        else:
            _limiters[model] = TokenBucketRateLimiter(rate=33.0, max_tokens=50)
    return _limiters[model]
