"""Tests for orchestrator execution mode behavior."""

from __future__ import annotations

from pathlib import Path

from automated_software_developer.agent.orchestrator import AgentConfig, SoftwareDevelopmentAgent
from automated_software_developer.agent.providers.mock_provider import MockProvider


def _planning_response() -> list[dict[str, object]]:
    return [
        {
            "project_name": "Planning Project",
            "product_brief": "Plan-first execution",
            "personas": ["Operator"],
            "stories": [
                {
                    "id": "story-1",
                    "title": "Create plan",
                    "story": "As an operator I want a plan so that implementation is predictable",
                    "acceptance_criteria": ["sprint_plan.json exists"],
                    "nfr_tags": ["reliability"],
                    "dependencies": [],
                    "verification_commands": [],
                }
            ],
            "nfrs": {
                "security": ["No secrets in logs"],
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
            "assumptions": [],
            "stack_rationale": "Python",
            "global_verification_commands": ["python -m pytest -q"],
        }
    ]


def test_auto_mode_runs_planning_only(tmp_path: Path) -> None:
    """Auto mode should resolve to planning and skip implementation loop."""
    provider = MockProvider(_planning_response())
    agent = SoftwareDevelopmentAgent(provider=provider, config=AgentConfig(execution_mode="auto"))
    summary = agent.run(requirements="Build planning artifacts.", output_dir=tmp_path)
    assert summary.selected_execution_mode == "planning"
    assert summary.requested_execution_mode == "auto"
    assert summary.tasks_completed == 0
    assert summary.verification_results == []
    assert (tmp_path / ".autosd" / "sprints").exists()
