"""Tests for daemon mode workflows."""

from __future__ import annotations

import json
from pathlib import Path

from automated_software_developer.agent.daemon import CompanyDaemon, DaemonConfig
from automated_software_developer.agent.providers.mock_provider import MockProvider


def _mock_responses() -> list[dict[str, object]]:
    verify = (
        "python -c \"from pathlib import Path; "
        "assert Path('artifact.txt').read_text(encoding='utf-8').strip() == 'ok'\""
    )
    return [
        {
            "project_name": "Daemon Project",
            "product_brief": "Build artifact",
            "personas": ["Operator"],
            "stories": [
                {
                    "id": "story-1",
                    "title": "Create artifact",
                    "story": "As an operator I want artifact output so that checks pass",
                    "acceptance_criteria": ["artifact.txt contains ok"],
                    "nfr_tags": ["reliability"],
                    "dependencies": [],
                    "verification_commands": [verify],
                }
            ],
            "nfrs": {
                "security": ["No secrets"],
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
            "global_verification_commands": [verify],
        },
        {
            "overview": "Simple architecture",
            "components": [
                {
                    "id": "core",
                    "name": "Core",
                    "responsibilities": ["Write artifact"],
                    "interfaces": ["cli"],
                    "dependencies": [],
                }
            ],
            "adrs": [
                {
                    "id": "ADR-001",
                    "title": "Use text file",
                    "status": "accepted",
                    "context": "Need simple output",
                    "decision": "Write artifact.txt",
                    "consequences": ["Simple IO"],
                }
            ],
        },
        {
            "summary": "Create artifact",
            "operations": [
                {"op": "write_file", "path": "artifact.txt", "content": "ok\n"},
                {"op": "write_file", "path": "README.md", "content": "# Daemon Project\n"},
            ],
            "verification_commands": [],
        },
    ]


def test_daemon_cycle_creates_project_and_postmortem(tmp_path: Path) -> None:
    requirements_dir = tmp_path / "requirements"
    projects_dir = tmp_path / "projects"
    registry_path = tmp_path / "registry.jsonl"
    incidents_path = tmp_path / "incidents.jsonl"
    requirements_dir.mkdir()
    requirements_file = requirements_dir / "daemon_project.md"
    requirements_file.write_text("Build artifact", encoding="utf-8")

    incident_signals = [
        {
            "project_id": "daemon_project",
            "source": "monitoring",
            "severity": "medium",
            "summary": "error spike",
            "proposed_fix": "apply patch",
        }
    ]
    incident_signals_path = tmp_path / "incident_signals.json"
    incident_signals_path.write_text(json.dumps(incident_signals), encoding="utf-8")

    provider = MockProvider(_mock_responses())
    config = DaemonConfig(
        requirements_dir=requirements_dir,
        projects_dir=projects_dir,
        registry_path=registry_path,
        incidents_path=incidents_path,
        incident_signals_path=incident_signals_path,
    )
    daemon = CompanyDaemon(provider=provider, config=config)
    processed = daemon.run_once()
    assert "daemon_project" in processed

    postmortems = list((projects_dir / "daemon_project" / ".autosd" / "postmortems").glob("*.md"))
    assert postmortems
