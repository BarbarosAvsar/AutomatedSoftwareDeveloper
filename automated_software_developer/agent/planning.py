"""Planning stage for the autonomous development agent."""

from __future__ import annotations

from automated_software_developer.agent.backlog import StoryBacklog
from automated_software_developer.agent.models import DevelopmentPlan, RefinedRequirements
from automated_software_developer.agent.prompts import (
    PLANNING_SYSTEM_PROMPT,
    build_planning_user_prompt,
)
from automated_software_developer.agent.providers.base import LLMProvider


class Planner:
    """Produces structured development plans from requirements."""

    def __init__(self, provider: LLMProvider) -> None:
        """Initialize planner with language model provider."""
        self.provider = provider

    def create_plan(
        self,
        requirements: str,
        repo_guidelines: str | None = None,
        *,
        seed: int | None = None,
    ) -> DevelopmentPlan:
        """Generate and validate a development plan."""
        response = self.provider.generate_json(
            system_prompt=PLANNING_SYSTEM_PROMPT,
            user_prompt=build_planning_user_prompt(requirements, repo_guidelines),
            seed=seed,
        )
        return DevelopmentPlan.from_dict(response)

    def create_backlog(self, refined_requirements: RefinedRequirements) -> StoryBacklog:
        """Construct a story backlog from refined requirements."""
        return StoryBacklog.from_refined_requirements(refined_requirements)
