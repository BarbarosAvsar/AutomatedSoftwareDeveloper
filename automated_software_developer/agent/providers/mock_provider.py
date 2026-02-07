"""Test provider that returns queued JSON responses."""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from typing import Any


class MockProvider:
    """A deterministic provider for unit/integration tests."""

    def __init__(self, responses: Iterable[dict[str, Any]]) -> None:
        """Initialize mock provider with queued JSON responses."""
        self._responses = [deepcopy(item) for item in responses]
        self.prompts: list[tuple[str, str]] = []

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Return next queued response and record prompts."""
        self.prompts.append((system_prompt, user_prompt))
        if not self._responses:
            raise RuntimeError("MockProvider has no remaining responses.")
        return deepcopy(self._responses.pop(0))
