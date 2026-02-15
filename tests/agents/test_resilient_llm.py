"""Tests for resilient provider wrapper."""

from __future__ import annotations

from typing import Any

from automated_software_developer.agent.providers.mock_provider import MockProvider
from automated_software_developer.agent.providers.resilient_llm import ResilientLLM


class FailingProvider:
    """Provider that always fails for fallback tests."""

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Raise runtime errors for every invocation."""
        _ = (system_prompt, user_prompt, seed)
        raise RuntimeError("boom")


def test_resilient_llm_fallback_on_failure() -> None:
    """ResilientLLM should return fallback output after retries fail."""
    provider = ResilientLLM(
        primary=FailingProvider(),
        fallback=MockProvider([{"ok": True}]),
        max_retries=2,
        base_delay_seconds=0.001,
        max_delay_seconds=0.001,
    )
    output = provider.generate_json("sys", "usr")
    assert output == {"ok": True}
