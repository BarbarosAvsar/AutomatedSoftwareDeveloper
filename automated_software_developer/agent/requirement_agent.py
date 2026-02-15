"""Requirement agent module for orchestrator decomposition."""

from __future__ import annotations

from automated_software_developer.agent.models import PromptTemplate, RefinedRequirements
from automated_software_developer.agent.requirements_refiner import RequirementsRefiner


class RequirementAgent:
    """Encapsulates requirements refinement behavior."""

    def __init__(self, refiner: RequirementsRefiner) -> None:
        """Store requirements refiner dependency."""
        self._refiner = refiner

    def refine(
        self,
        *,
        requirements: str,
        repo_guidelines: str | None,
        template: PromptTemplate,
        seed: int | None,
    ) -> RefinedRequirements:
        """Refine requirements into canonical structured artifacts."""
        return self._refiner.refine(
            requirements=requirements,
            repo_guidelines=repo_guidelines,
            template=template,
            seed=seed,
        )
