"""Review agent module for orchestrator decomposition."""

from __future__ import annotations

from automated_software_developer.agent.models import StoryExecutionState


class ReviewAgent:
    """Encapsulates review decisions for story completion."""

    def needs_retry(self, state: StoryExecutionState) -> bool:
        """Return whether a story execution should be retried."""
        return state.status != "completed"
