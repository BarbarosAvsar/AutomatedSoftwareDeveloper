"""Provider abstraction for model interactions."""

from __future__ import annotations

from typing import Any, Protocol


class LLMProvider(Protocol):
    """Interface implemented by all model providers."""

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Generate structured JSON from prompt pair."""
        ...
