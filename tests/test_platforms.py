"""Tests for platform adapter catalog and selection behavior."""

from __future__ import annotations

from pathlib import Path

from automated_software_developer.agent.models import RefinedRequirements
from automated_software_developer.agent.platforms.catalog import (
    adapter_catalog,
    build_capability_graph,
    select_platform_adapter,
)


def _refined_requirements(text: str) -> RefinedRequirements:
    return RefinedRequirements.from_dict(
        {
            "project_name": "Platform Project",
            "product_brief": text,
            "personas": ["Developer"],
            "stories": [
                {
                    "id": "story-1",
                    "title": "Deliver feature",
                    "story": f"As a user, I want {text} so that outcomes are achieved.",
                    "acceptance_criteria": [
                        "Given behavior, when tests run, then expected result is observed."
                    ],
                    "nfr_tags": ["reliability"],
                    "dependencies": [],
                    "verification_commands": [],
                }
            ],
            "nfrs": {
                "security": ["validate inputs"],
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
                    "assumption": "default assumptions",
                    "testable_criterion": (
                        "Given default assumptions, when checks run, then behavior is verified."
                    ),
                }
            ],
            "stack_rationale": "python",
            "global_verification_commands": ["python -m pytest -q"],
        }
    )


def test_adapter_selection_prefers_api_service_for_endpoint_requirements(tmp_path: Path) -> None:
    refined = _refined_requirements("Build a REST API service with endpoint monitoring")
    plan = select_platform_adapter(refined, project_dir=tmp_path)
    assert plan.adapter_id == "api_service"
    assert "docker" in plan.supported_deploy_targets


def test_adapter_selection_respects_preferred_override(tmp_path: Path) -> None:
    refined = _refined_requirements("Provide a web dashboard")
    plan = select_platform_adapter(refined, project_dir=tmp_path, preferred_adapter="cli_tool")
    assert plan.adapter_id == "cli_tool"


def test_capability_graph_contains_required_adapters() -> None:
    catalog = adapter_catalog()
    assert {"web_app", "api_service", "cli_tool", "desktop_app", "mobile_app"}.issubset(
        set(catalog)
    )
    graph = build_capability_graph()
    payload = graph.to_dict()
    assert "adapters" in payload
    assert "web_app" in payload["adapters"]
