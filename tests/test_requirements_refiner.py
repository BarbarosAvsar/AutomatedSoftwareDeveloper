"""Tests for autonomous requirements refinement behavior."""

from __future__ import annotations

from automated_software_developer.agent.planning import Planner
from automated_software_developer.agent.providers.mock_provider import MockProvider
from automated_software_developer.agent.requirements_refiner import RequirementsRefiner


def _refiner_response() -> dict[str, object]:
    return {
        "project_name": "Todo Service",
        "product_brief": "Build a todo service for teams.",
        "personas": ["Developer", "Manager"],
        "stories": [
            {
                "id": "todo-create",
                "title": "Create todo",
                "story": "users create todos",
                "acceptance_criteria": ["todo endpoint creates records"],
                "nfr_tags": ["security"],
                "dependencies": [],
                "verification_commands": [],
            }
        ],
        "nfrs": {
            "security": ["Auth required for all mutations."],
            "privacy": [],
            "performance": [],
            "reliability": [],
            "observability": [],
            "ux_accessibility": [],
            "compliance": [],
        },
        "ambiguities": [],
        "contradictions": [],
        "missing_constraints": [],
        "edge_cases": [],
        "external_dependencies": [],
        "assumptions": [
            {
                "assumption": "Single tenant scope.",
                "testable_criterion": "single tenant scope is validated",
            }
        ],
        "stack_rationale": "Python for fast iteration.",
        "global_verification_commands": ["python -m pytest -q"],
    }


def test_refinement_normalizes_story_and_acceptance_criteria() -> None:
    provider = MockProvider(responses=[_refiner_response()])
    refiner = RequirementsRefiner(provider=provider)
    refined = refiner.refine(
        requirements="Build a fast todo API etc with auth",
        repo_guidelines=None,
        template=MockTemplate.requirements(),
    )

    story = refined.stories[0]
    assert story.story.lower().startswith("as a")
    assert "given" in story.acceptance_criteria[0].lower()
    assert "when" in story.acceptance_criteria[0].lower()
    assert "then" in story.acceptance_criteria[0].lower()
    assert refined.ambiguities
    markdown = refined.to_markdown()
    assert "## Product Brief" in markdown
    assert "## User Stories" in markdown
    assert "## Assumptions" in markdown


def test_backlog_consistency_from_refined_output() -> None:
    provider = MockProvider(responses=[_refiner_response()])
    refiner = RequirementsRefiner(provider=provider)
    refined = refiner.refine(
        requirements="Build a fast todo API etc with auth",
        repo_guidelines=None,
        template=MockTemplate.requirements(),
    )

    planner = Planner(provider=MockProvider(responses=[]))
    backlog = planner.create_backlog(refined)
    assert len(backlog.stories) == len(refined.stories)
    assert backlog.stories[0].story_id == refined.stories[0].story_id


class MockTemplate:
    """Helper factory for prompt template objects."""

    @staticmethod
    def requirements() -> object:
        from automated_software_developer.agent.models import PromptTemplate

        return PromptTemplate(
            template_id="requirements-refinement",
            version=1,
            directives=["Refine requirements."],
            retry_directives=["Retry with strict schema."],
            constraints=["Return JSON."],
        )
