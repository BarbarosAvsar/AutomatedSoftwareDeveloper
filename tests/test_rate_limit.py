"""Tests for provider rate-limit parsing helpers."""

from __future__ import annotations

import math

import pytest

from automated_software_developer.agent.providers.rate_limit import (
    RateLimitBackoff,
    extract_rate_limit_event,
)


class _Response:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


class _ProviderError(Exception):
    def __init__(self, headers: dict[str, str]) -> None:
        super().__init__("rate limited")
        self.response = _Response(headers)
        self.message = "rate limit"


def test_extract_rate_limit_event_supports_case_insensitive_headers() -> None:
    error = _ProviderError({"Retry-After": "1.5"})

    event = extract_rate_limit_event(error)

    assert event is not None
    assert event.retry_after_seconds == 1.5


def test_extract_rate_limit_event_parses_uppercase_duration_units() -> None:
    error = _ProviderError({"X-RateLimit-Reset": "250MS"})

    event = extract_rate_limit_event(error)

    assert event is not None
    assert event.retry_after_seconds == pytest.approx(0.25, abs=0.01)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("max_retries", -1, "max_retries must be non-negative"),
        ("min_delay_seconds", 0, "min_delay_seconds must be greater than zero"),
        (
            "max_delay_seconds",
            0.5,
            "max_delay_seconds must be greater than or equal to min_delay_seconds",
        ),
        ("jitter_ratio", -0.1, "jitter_ratio must be between 0 and 1 inclusive"),
        ("jitter_ratio", 1.1, "jitter_ratio must be between 0 and 1 inclusive"),
    ],
)
def test_rate_limit_backoff_rejects_invalid_config(
    field: str, value: float | int, message: str
) -> None:
    kwargs: dict[str, float | int] = {
        "max_retries": 4,
        "min_delay_seconds": 2,
        "max_delay_seconds": 30,
        "jitter_ratio": 0.15,
    }
    kwargs[field] = value

    with pytest.raises(ValueError, match=message):
        RateLimitBackoff(**kwargs)


@pytest.mark.parametrize(
    ("attempt", "retry_after", "message"),
    [
        (0, None, "attempt must be greater than or equal to 1"),
        (1, -0.1, "retry_after must be a non-negative finite number"),
        (1, math.inf, "retry_after must be a non-negative finite number"),
        (1, math.nan, "retry_after must be a non-negative finite number"),
    ],
)
def test_rate_limit_backoff_next_delay_rejects_invalid_inputs(
    attempt: int, retry_after: float | None, message: str
) -> None:
    backoff = RateLimitBackoff()

    with pytest.raises(ValueError, match=message):
        backoff.next_delay(attempt=attempt, retry_after=retry_after)
