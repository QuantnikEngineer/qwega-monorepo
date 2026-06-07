"""
Resilience utilities: circuit breaker, semaphore limiter, async wrappers.

Provides production-grade fault tolerance for external service calls
(Vertex AI, Qdrant) without requiring Redis or external dependencies.
"""
import asyncio
import functools
import random
import time
from enum import Enum
from typing import Any, Callable

from app.core.logging import logger


# ── Semaphore limiter ─────────────────────────────────────────────────────────
# Limits concurrent calls to external services (e.g., Vertex AI).

_LLM_SEMAPHORE = asyncio.Semaphore(10)        # max 10 concurrent LLM calls
_EMBEDDING_SEMAPHORE = asyncio.Semaphore(20)   # max 20 concurrent embedding calls


async def with_llm_semaphore(coro):
    """Run a coroutine with LLM concurrency limit."""
    async with _LLM_SEMAPHORE:
        return await coro


async def with_embedding_semaphore(coro):
    """Run a coroutine with embedding concurrency limit."""
    async with _EMBEDDING_SEMAPHORE:
        return await coro


# ── Circuit Breaker ───────────────────────────────────────────────────────────

class CircuitState(Enum):
    CLOSED = "closed"         # normal operation
    OPEN = "open"             # failing, reject fast
    HALF_OPEN = "half_open"   # testing recovery


class CircuitBreaker:
    """
    Simple circuit breaker for external service calls.

    - CLOSED: all calls pass through.
    - After ``failure_threshold`` consecutive failures → OPEN.
    - OPEN: calls are rejected immediately for ``recovery_timeout`` seconds.
    - After timeout → HALF_OPEN: one call allowed through.
      - If it succeeds → CLOSED.
      - If it fails → back to OPEN.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute func through the circuit breaker."""
        current_state = self.state

        if current_state == CircuitState.OPEN:
            logger.warning("circuit_open", breaker=self.name)
            raise CircuitOpenError(f"Circuit breaker '{self.name}' is OPEN")

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except CircuitOpenError:
            raise
        except Exception as e:
            await self._on_failure()
            raise

    async def _on_success(self):
        async with self._lock:
            self._failure_count = 0
            if self._state != CircuitState.CLOSED:
                logger.info("circuit_closed", breaker=self.name)
                self._state = CircuitState.CLOSED

    async def _on_failure(self):
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "circuit_opened",
                    breaker=self.name,
                    failures=self._failure_count,
                )


class CircuitOpenError(Exception):
    pass


# ── Shared breakers ──────────────────────────────────────────────────────────

vertex_breaker = CircuitBreaker("vertex_ai", failure_threshold=5, recovery_timeout=30.0)
qdrant_breaker = CircuitBreaker("qdrant", failure_threshold=5, recovery_timeout=15.0)


# ── Async wrapper for blocking calls ─────────────────────────────────────────

async def run_in_thread(func: Callable, *args, **kwargs) -> Any:
    """
    Run a blocking/CPU-bound function in a thread pool executor
    to avoid blocking the async event loop.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, functools.partial(func, *args, **kwargs)
    )


# ── Retry with backoff ────────────────────────────────────────────────────────

async def retry_async(
    func: Callable,
    *args,
    max_retries: int = 3,
    backoff_base: float = 2.0,
    **kwargs,
) -> Any:
    """Retry an async callable with exponential backoff + jitter."""
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = (backoff_base ** attempt) + random.uniform(0, 1)
            logger.warning("retry", attempt=attempt + 1, wait=round(wait, 2), error=str(e))
            await asyncio.sleep(wait)
