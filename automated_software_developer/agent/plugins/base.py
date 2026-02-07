"""Plugin base classes for extensible automation hooks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PluginMetadata:
    """Metadata describing a plugin."""

    plugin_id: str
    name: str
    version: str = "0.1.0"


class Plugin:
    """Base class for plugins with hook methods."""

    metadata: PluginMetadata

    def on_refine(self, context: dict[str, Any]) -> None:
        """Hook executed during requirements refinement."""

    def on_plan(self, context: dict[str, Any]) -> None:
        """Hook executed during planning."""

    def on_implement(self, context: dict[str, Any]) -> None:
        """Hook executed during implementation."""

    def on_test(self, context: dict[str, Any]) -> None:
        """Hook executed during testing."""

    def on_deploy(self, context: dict[str, Any]) -> None:
        """Hook executed during deployment."""

    def on_review(self, context: dict[str, Any]) -> None:
        """Hook executed during review."""

    def on_retro(self, context: dict[str, Any]) -> None:
        """Hook executed during retrospective."""
