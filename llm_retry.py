from __future__ import annotations

import os
import re
import time
from typing import Callable, TypeVar


T = TypeVar("T")


def call_with_rate_limit_retries(create_call: Callable[[], T]) -> T:
    max_attempts = _read_positive_int_env("WRITERLM_RATE_LIMIT_RETRIES", default=6)
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return create_call()
        except Exception as exc:
            last_error = exc
            if not _is_rate_limit_error(exc) or attempt >= max_attempts:
                raise
            time.sleep(_retry_delay_seconds(exc, attempt=attempt))

    assert last_error is not None
    raise last_error


def _is_rate_limit_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return True

    message = str(exc).lower()
    return "rate limit" in message or "rate_limit" in message


def _retry_delay_seconds(exc: Exception, *, attempt: int) -> float:
    retry_after = _retry_after_from_headers(exc)
    if retry_after is not None:
        return retry_after

    message = str(exc)
    match = re.search(r"try again in\s+([0-9]+(?:\.[0-9]+)?)s", message, re.IGNORECASE)
    if match:
        return min(max(float(match.group(1)) + 0.25, 0.5), 90.0)

    return min(2.0 * attempt, 30.0)


def _retry_after_from_headers(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None

    value = headers.get("retry-after") or headers.get("Retry-After")
    if value is None:
        return None

    try:
        return min(max(float(value) + 0.25, 0.5), 90.0)
    except ValueError:
        return None


def _read_positive_int_env(name: str, *, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default
