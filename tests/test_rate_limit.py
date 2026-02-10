"""Tests for provider rate-limit parsing helpers."""

from __future__ import annotations

import pytest

from automated_software_developer.agent.providers.rate_limit import extract_rate_limit_event


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
