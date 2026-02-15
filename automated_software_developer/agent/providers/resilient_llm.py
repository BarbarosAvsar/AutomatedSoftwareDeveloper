"""Resilient provider wrapper with retry/backoff and fallback handling."""

from __future__ import annotations

import logging
import time
from typing import Any

from automated_software_developer.agent.providers.base import LLMProvider
from automated_software_developer.agent.providers.mock_provider import MockProvider

logger = logging.getLogger(__name__)


class ResilientLLM:
    """Wrap an LLM provider with bounded retries and fallback provider."""

    def __init__(
        self,
        primary: LLMProvider,
        fallback: LLMProvider | None = None,
        *,
        max_retries: int = 3,
        base_delay_seconds: float = 0.25,
        max_delay_seconds: float = 2.0,
    ) -> None:
        """Initialize resilient wrapper with retry parameters."""
        if max_retries <= 0:
            raise ValueError("max_retries must be greater than zero.")
        if base_delay_seconds <= 0 or max_delay_seconds <= 0:
            raise ValueError("retry delay values must be positive.")
        self.primary = primary
        self.fallback = fallback or MockProvider([{}])
        self.max_retries = max_retries
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Generate JSON with retries, then fallback if needed."""
        error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return self.primary.generate_json(system_prompt, user_prompt, seed=seed)
            except Exception as exc:  # noqa: BLE001
                error = exc
                if attempt >= self.max_retries:
                    break
                delay = min(self.base_delay_seconds * (2 ** (attempt - 1)), self.max_delay_seconds)
                logger.warning(
                    "Primary provider failed (attempt %s/%s): %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                time.sleep(delay)

        logger.warning("Falling back after primary provider failures: %s", error)
        return self.fallback.generate_json(system_prompt, user_prompt, seed=seed)
