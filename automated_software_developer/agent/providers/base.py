"""Provider abstraction for model interactions."""

from __future__ import annotations

from typing import Any, Protocol


class LLMProvider(Protocol):
    """Interface implemented by all model providers."""

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Generate structured JSON from prompt pair."""
        ...
