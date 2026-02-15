"""Planner agent module for orchestrator decomposition."""

from __future__ import annotations

from automated_software_developer.agent.backlog import StoryBacklog
from automated_software_developer.agent.models import RefinedRequirements
from automated_software_developer.agent.planning import Planner


class PlannerAgent:
    """Wraps planning decisions for backlog creation."""

    def __init__(self, planner: Planner) -> None:
        """Store planner dependency."""
        self._planner = planner

    def create_backlog(self, refined: RefinedRequirements) -> StoryBacklog:
        """Create a story backlog from refined requirements."""
        return self._planner.create_backlog(refined)
