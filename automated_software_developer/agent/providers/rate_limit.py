"""Rate limit handling utilities for model providers."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any


@dataclass(frozen=True)
class RateLimitEvent:
    """Captured rate limit event metadata for observability."""

    retry_after_seconds: float
    reset_at: datetime | None
    reason: str
    limit_header: str | None = None


@dataclass(frozen=True)
class RateLimitBackoff:
    """Backoff strategy configuration for rate limit retries."""

    max_retries: int = 4
    min_delay_seconds: float = 2.0
    max_delay_seconds: float = 30.0
    jitter_ratio: float = 0.15

    def next_delay(self, *, attempt: int, retry_after: float | None) -> float:
        """Return delay in seconds for given attempt and optional retry-after."""
        base: float = self.min_delay_seconds * (2 ** (attempt - 1))
        bounded: float = min(base, self.max_delay_seconds)
        if retry_after is not None:
            bounded = max(bounded, retry_after)
        jitter: float = bounded * self.jitter_ratio
        if jitter <= 0:
            return bounded
        random_fraction: float = float(secrets.randbelow(10_000)) / 10_000
        return bounded + (jitter * random_fraction)


def extract_rate_limit_event(error: Any) -> RateLimitEvent | None:
    """Parse retry headers from a provider error when available."""
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None) if response is not None else None
    if not headers:
        return None

    retry_after_value = _first_header(headers, ["retry-after"])
    reset_value = _first_header(
        headers,
        [
            "x-ratelimit-reset-requests",
            "x-ratelimit-reset-tokens",
            "x-ratelimit-reset",
        ],
    )
    retry_after_seconds = _parse_retry_after(retry_after_value) if retry_after_value else None
    reset_at = _parse_reset_at(reset_value) if reset_value else None

    if retry_after_seconds is None and reset_at is not None:
        retry_after_seconds = max(
            0.0,
            (reset_at - datetime.now(tz=UTC)).total_seconds(),
        )
    if retry_after_seconds is None:
        retry_after_seconds = 0.0

    return RateLimitEvent(
        retry_after_seconds=retry_after_seconds,
        reset_at=reset_at,
        reason=getattr(error, "message", None) or str(error),
        limit_header=retry_after_value or reset_value,
    )


def _first_header(headers: Any, keys: list[str]) -> str | None:
    """Return first matching header value for the given keys."""
    for key in keys:
        value = headers.get(key)
        if value:
            return str(value)
    return None


def _parse_retry_after(value: str) -> float | None:
    """Parse retry-after header into seconds."""
    if not value:
        return None
    stripped = value.strip()
    try:
        return float(stripped)
    except ValueError:
        parsed_date = _parse_http_date(stripped)
        if parsed_date is not None:
            return max(0.0, (parsed_date - datetime.now(tz=UTC)).total_seconds())
    return _parse_duration_seconds(stripped)


def _parse_reset_at(value: str) -> datetime | None:
    """Parse reset header into absolute time."""
    if not value:
        return None
    stripped = value.strip()
    parsed_date = _parse_http_date(stripped)
    if parsed_date is not None:
        return parsed_date
    duration_seconds = _parse_duration_seconds(stripped)
    if duration_seconds is None:
        return None
    return datetime.now(tz=UTC) + timedelta(seconds=duration_seconds)


def _parse_http_date(value: str) -> datetime | None:
    """Parse HTTP-date formatted string into datetime."""
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed is None:
        return None
    return parsed.astimezone(UTC)


def _parse_duration_seconds(value: str) -> float | None:
    """Parse a duration like '1s', '250ms', '2m' into seconds."""
    match = re.match(r"^(?P<number>\\d+(?:\\.\\d+)?)(?P<unit>ms|s|m|h)?$", value)
    if not match:
        return None
    number = float(match.group("number"))
    unit = match.group("unit") or "s"
    if unit == "ms":
        return number / 1000.0
    if unit == "m":
        return number * 60.0
    if unit == "h":
        return number * 3600.0
    return number
