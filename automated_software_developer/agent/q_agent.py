"""Quality agent module for orchestrator decomposition."""

from __future__ import annotations

from automated_software_developer.agent.models import CommandResult


class QAgent:
    """Evaluates quality gate command outcomes."""

    def passed(self, results: list[CommandResult]) -> bool:
        """Return true when all command results passed."""
        return all(item.passed for item in results)
