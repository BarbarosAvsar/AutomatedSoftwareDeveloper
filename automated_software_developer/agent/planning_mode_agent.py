"""Execution-mode selector for planning-first automation policy."""

from __future__ import annotations

from dataclasses import dataclass

from automated_software_developer.agent.config_validation import validate_execution_mode


@dataclass(frozen=True)
class PlanningModeDecision:
    """Resolved execution mode chosen by planning policy."""

    requested_mode: str
    selected_mode: str
    reason: str


class PlanningModeSelectorAgent:
    """Resolves execution mode with deterministic planning-first auto behavior."""

    def select(self, *, requested_mode: str, requirements: str) -> PlanningModeDecision:
        """Resolve the requested mode into a concrete execution mode."""
        del requirements
        mode = validate_execution_mode(requested_mode)
        if mode == "auto":
            return PlanningModeDecision(
                requested_mode=mode,
                selected_mode="planning",
                reason="auto mode enforces planning-first execution.",
            )
        return PlanningModeDecision(
            requested_mode=mode,
            selected_mode=mode,
            reason=f"execution mode explicitly set to '{mode}'.",
        )
