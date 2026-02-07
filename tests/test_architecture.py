"""Tests for architecture synthesis artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from automated_software_developer.agent.architecture import ArchitecturePlanner
from automated_software_developer.agent.models import RefinedRequirements
from automated_software_developer.agent.providers.mock_provider import MockProvider


def _refinement_payload() -> dict[str, object]:
    return {
        "project_name": "Architecture Demo",
        "product_brief": "Demo project for architecture planning.",
        "personas": ["Developer"],
        "stories": [
            {
                "id": "story-1",
                "title": "Demo story",
                "story": "As a developer, I want a demo so that planning can occur.",
                "acceptance_criteria": ["Given the demo, when it runs, then it succeeds."],
                "nfr_tags": [],
                "dependencies": [],
                "verification_commands": [],
            }
        ],
        "nfrs": {
            "security": [],
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
                "assumption": "Demo only.",
                "testable_criterion": "Given demo, when checks run, then it passes.",
            }
        ],
        "stack_rationale": "Python for demos.",
        "global_verification_commands": ["python -m pytest -q"],
    }


def test_architecture_artifacts(tmp_path: Path) -> None:
    provider = MockProvider(
        responses=[
            {
                "overview": "System uses a web layer and storage layer.",
                "components": [
                    {
                        "id": "web",
                        "name": "Web Layer",
                        "responsibilities": ["Handle requests"],
                        "interfaces": ["HTTP"],
                        "dependencies": ["storage"],
                    },
                    {
                        "id": "storage",
                        "name": "Storage Layer",
                        "responsibilities": ["Persist data"],
                        "interfaces": ["Filesystem"],
                        "dependencies": [],
                    },
                    {
                        "id": "worker",
                        "name": "Worker",
                        "responsibilities": ["Background tasks"],
                        "interfaces": ["Queue"],
                        "dependencies": ["storage"],
                    },
                ],
                "adrs": [
                    {
                        "id": "adr-001",
                        "title": "Local storage",
                        "status": "accepted",
                        "context": "Local artifacts are sufficient.",
                        "decision": "Use local filesystem.",
                        "consequences": ["Simple setup"],
                    }
                ],
            }
        ]
    )
    planner = ArchitecturePlanner(provider)
    refined = RefinedRequirements.from_dict(_refinement_payload())
    plan = planner.create_plan(refined=refined, repo_guidelines=None)
    artifacts = planner.write_artifacts(plan, tmp_path)

    assert artifacts.architecture_doc.exists()
    assert artifacts.components_json.exists()
    assert (artifacts.adrs_dir / "adr-001.md").exists()

    payload = json.loads(artifacts.components_json.read_text(encoding="utf-8"))
    edges = payload["dependency_graph"]["edges"]
    assert {"from": "web", "to": "storage"} in edges
    assert {"from": "worker", "to": "storage"} in edges
