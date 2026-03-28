"""Async retry helper with exponential backoff and jitter."""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Awaitable, Callable, Sequence, Type

import httpx

logger = logging.getLogger(__name__)

# Exceptions worth retrying by default (transient network / server errors)
DEFAULT_RETRYABLE: tuple[Type[Exception], ...] = (
    httpx.HTTPStatusError,
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    asyncio.TimeoutError,
    ConnectionError,
)


def _is_retryable_status(exc: BaseException) -> bool:
    """Return True for HTTP 429 and 5xx errors only."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or code >= 500
    return True


def _get_retry_after(exc: BaseException) -> float | None:
    """Extract Retry-After header value if present (HTTP 429)."""
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        header = exc.response.headers.get("Retry-After")
        if header:
            try:
                return float(header)
            except ValueError:
                pass
    return None


async def retry_with_backoff(
    coro_factory: Callable[[], Awaitable[Any]],
    *,
    max_retries: int = 3,
    base_delay: float = 5.0,
    max_delay: float = 120.0,
    retryable_exceptions: Sequence[Type[Exception]] = DEFAULT_RETRYABLE,
    label: str = "",
) -> Any:
    """Call *coro_factory()* with retries on transient failures.

    *coro_factory* is a zero-arg callable that returns a new awaitable each
    time (you cannot reuse a consumed coroutine).

    Returns the result on success or raises the last exception after all
    retries are exhausted.
    """
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 2):  # attempt 1 = first try
        try:
            return await coro_factory()
        except tuple(retryable_exceptions) as exc:
            if not _is_retryable_status(exc):
                raise

            last_exc = exc

            if attempt > max_retries:
                break  # no more retries

            retry_after = _get_retry_after(exc)
            delay = retry_after or min(base_delay * (2 ** (attempt - 1)), max_delay)
            jitter = random.uniform(0, delay * 0.25)
            total_delay = delay + jitter

            tag = f" [{label}]" if label else ""
            logger.warning(
                f"Retry {attempt}/{max_retries}{tag}: "
                f"{type(exc).__name__}: {exc} — waiting {total_delay:.1f}s"
            )
            await asyncio.sleep(total_delay)

    raise last_exc  # type: ignore[misc]


__all__ = ["retry_with_backoff", "DEFAULT_RETRYABLE"]
