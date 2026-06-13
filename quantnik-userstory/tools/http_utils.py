"""HTTP utilities: retry-with-backoff and error classification.

Used by all Jira / Confluence callers to:
- transparently retry transient failures (5xx, 429, network errors)
- classify HTTP errors into stable categories so the API surface can return
  consistent error codes and messages.
"""

from __future__ import annotations

import logging
import os
import random
import time
from typing import Any, Callable, Optional

import requests

logger = logging.getLogger(__name__)


# Public error category constants.  Returned via classify_http_error() so
# callers can map them to HTTP status codes / user-facing messages.
ERROR_AUTH = "auth"               # 401, 403
ERROR_NOT_FOUND = "not_found"     # 404
ERROR_RATE_LIMITED = "rate_limit" # 429
ERROR_TRANSIENT = "transient"     # 5xx, network errors
ERROR_PERMANENT = "permanent"     # 4xx (other than the above)
ERROR_UNKNOWN = "unknown"


_DEFAULT_MAX_ATTEMPTS = int(os.getenv("HTTP_MAX_ATTEMPTS", "3"))
_DEFAULT_BASE_BACKOFF = float(os.getenv("HTTP_BASE_BACKOFF_SECONDS", "1.0"))
_DEFAULT_TIMEOUT = float(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))


def http_request_with_retry(
    method: str,
    url: str,
    *,
    max_attempts: Optional[int] = None,
    base_backoff: Optional[float] = None,
    timeout: Optional[float] = None,
    sleep: Callable[[float], None] = time.sleep,
    **kwargs: Any,
) -> requests.Response:
    """Issue an HTTP request, retrying transient failures with exponential backoff.

    Retries on:
    - requests.exceptions.ConnectionError / Timeout / ChunkedEncodingError
    - HTTP 408, 425, 429, 500, 502, 503, 504

    Honors the `Retry-After` header on 429 / 503 responses when present.

    Returns the final ``requests.Response`` (which may still be a non-2xx
    response if all retries are exhausted).  Raises only when the final
    attempt itself raises a non-retryable exception.
    """

    attempts = max(1, max_attempts if max_attempts is not None else _DEFAULT_MAX_ATTEMPTS)
    backoff = base_backoff if base_backoff is not None else _DEFAULT_BASE_BACKOFF
    request_timeout = timeout if timeout is not None else _DEFAULT_TIMEOUT
    kwargs.setdefault("timeout", request_timeout)

    retryable_status = {408, 425, 429, 500, 502, 503, 504}
    last_exception: Optional[BaseException] = None
    last_response: Optional[requests.Response] = None

    for attempt in range(1, attempts + 1):
        try:
            response = requests.request(method, url, **kwargs)
            last_response = response
            if response.status_code not in retryable_status or attempt == attempts:
                return response

            # Honor Retry-After for 429/503 when present.
            wait = _compute_retry_wait(response, attempt, backoff)
            logger.warning(
                "HTTP %s %s returned %s — retry %d/%d in %.2fs",
                method, url, response.status_code, attempt, attempts, wait,
            )
            sleep(wait)
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
        ) as exc:
            last_exception = exc
            if attempt == attempts:
                raise
            wait = backoff * (2 ** (attempt - 1)) + random.uniform(0, 0.25)
            logger.warning(
                "HTTP %s %s raised %s — retry %d/%d in %.2fs",
                method, url, type(exc).__name__, attempt, attempts, wait,
            )
            sleep(wait)

    # Defensive: should not be reached.
    if last_response is not None:
        return last_response
    if last_exception is not None:
        raise last_exception
    raise RuntimeError("http_request_with_retry exited unexpectedly")


def _compute_retry_wait(response: requests.Response, attempt: int, base_backoff: float) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except (TypeError, ValueError):
            pass
    # Exponential backoff with jitter
    return base_backoff * (2 ** (attempt - 1)) + random.uniform(0, 0.25)


def classify_http_error(status_code: int) -> str:
    """Map a Jira/Confluence HTTP status to a coarse category."""
    if status_code in (401, 403):
        return ERROR_AUTH
    if status_code == 404:
        return ERROR_NOT_FOUND
    if status_code == 429:
        return ERROR_RATE_LIMITED
    if 500 <= status_code < 600:
        return ERROR_TRANSIENT
    if 400 <= status_code < 500:
        return ERROR_PERMANENT
    return ERROR_UNKNOWN


def category_to_http_status(category: str) -> int:
    """Map an internal error category to an outward HTTP status code."""
    return {
        ERROR_AUTH: 502,        # upstream auth misconfig — surfaces as bad gateway
        ERROR_NOT_FOUND: 404,
        ERROR_RATE_LIMITED: 503,
        ERROR_TRANSIENT: 502,
        ERROR_PERMANENT: 400,
    }.get(category, 500)
