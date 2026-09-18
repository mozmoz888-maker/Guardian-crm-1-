"""Exponential backoff retry logic for rate-limit / 5xx errors."""
from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

import config
from .exceptions import RetryableError, RetryExhaustedError

T = TypeVar("T")


def is_retryable_status(status_code: int | None) -> bool:
    if status_code is None:
        return False
    return status_code == 429 or 500 <= status_code < 600


def compute_backoff(attempt: int) -> float:
    """attempt is 0-indexed. attempt 0 -> base^0, attempt 1 -> base^1, ..."""
    base_delay = config.EXPONENTIAL_BASE ** attempt
    jitter = random.uniform(0, config.RETRY_JITTER_MAX_SECONDS)
    return base_delay + jitter


def call_with_retry(
    fn: Callable[[], T],
    max_retries: int = config.MAX_RETRIES,
    logger=None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> T:
    """Call ``fn`` (no-arg callable) with exponential-backoff retry.

    Retries only on RetryableError (raised by the LLM client wrapper for
    HTTP 429 / 5xx). Any other exception propagates immediately, since
    retrying a malformed request or an auth failure would never help.
    """
    last_error: Exception | None = None
    attempts_made = 0

    for attempt in range(max_retries + 1):  # +1 = initial try, then max_retries retries
        attempts_made = attempt + 1
        try:
            return fn()
        except RetryableError as exc:
            last_error = exc
            if attempt >= max_retries:
                break
            delay = compute_backoff(attempt)
            if logger:
                logger.warning(
                    "Retryable error (attempt %d/%d): %s. Backing off %.2fs.",
                    attempt + 1, max_retries + 1, exc, delay,
                )
            sleep_fn(delay)

    raise RetryExhaustedError(
        f"Exhausted {attempts_made} attempt(s); last error: {last_error}",
        last_error=last_error,
        attempts=attempts_made,
    )
