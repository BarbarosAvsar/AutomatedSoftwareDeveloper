"""Deterministic replay tests for end-to-end orchestration artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path

from automated_software_developer.agent.orchestrator import AgentConfig, SoftwareDevelopmentAgent
from automated_software_developer.agent.providers.mock_provider import MockProvider


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verification_command() -> str:
    return (
        'python -c "from pathlib import Path; '
        "assert Path('artifact.txt').read_text(encoding='utf-8').strip() == 'ok'\""
    )


def _provider() -> MockProvider:
    return MockProvider(
        responses=[
            {
                "project_name": "Replay Project",
                "product_brief": "Create and validate a deterministic artifact file.",
                "personas": ["Engineer"],
                "stories": [
                    {
                        "id": "story-1",
                        "title": "Write deterministic artifact",
                        "story": "As an engineer I want deterministic outputs.",
                        "acceptance_criteria": [
                            "Given output generation, when run completes, "
                            "then artifact.txt contains ok"
                        ],
                        "nfr_tags": ["reliability"],
                        "dependencies": [],
                        "verification_commands": [_verification_command()],
                    }
                ],
                "nfrs": {
                    "security": [],
                    "privacy": [],
                    "performance": [],
                    "reliability": ["deterministic outputs"],
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
                "global_verification_commands": [_verification_command()],
            },
            {
                "overview": "single component",
                "components": [
                    {
                        "id": "core",
                        "name": "Core",
                        "responsibilities": ["Write artifact"],
                        "interfaces": ["fs"],
                        "dependencies": [],
                    }
                ],
                "adrs": [
                    {
                        "id": "adr-001",
                        "title": "Local deterministic output",
                        "status": "accepted",
                        "context": "Test run needs deterministic files.",
                        "decision": "Use static artifact content.",
                        "consequences": ["Stable replay"],
                    }
                ],
            },
            {
                "summary": "Write deterministic file.",
                "operations": [
                    {
                        "op": "write_file",
                        "path": "artifact.txt",
                        "content": "ok\n",
                    },
                    {
                        "op": "write_file",
                        "path": "README.md",
                        "content": "# Replay Project\n",
                    },
                    {
                        "op": "write_file",
                        "path": "requirements.txt",
                        "content": "typer==0.21.1\n",
                    },
                ],
                "verification_commands": [],
            },
            {
                "summary": "Write deterministic file.",
                "operations": [
                    {
                        "op": "write_file",
                        "path": "artifact.txt",
                        "content": "ok\n",
                    },
                    {
                        "op": "write_file",
                        "path": "README.md",
                        "content": "# Replay Project\n",
                    },
                    {
                        "op": "write_file",
                        "path": "requirements.txt",
                        "content": "typer==0.21.1\n",
                    },
                ],
                "verification_commands": [],
            },
            {
                "summary": "Write deterministic file.",
                "operations": [
                    {
                        "op": "write_file",
                        "path": "artifact.txt",
                        "content": "ok\n",
                    },
                    {
                        "op": "write_file",
                        "path": "README.md",
                        "content": "# Replay Project\n",
                    },
                    {
                        "op": "write_file",
                        "path": "requirements.txt",
                        "content": "typer==0.21.1\n",
                    },
                ],
                "verification_commands": [],
            },
            {
                "summary": "Write deterministic file.",
                "operations": [
                    {
                        "op": "write_file",
                        "path": "artifact.txt",
                        "content": "ok\n",
                    },
                    {
                        "op": "write_file",
                        "path": "README.md",
                        "content": "# Replay Project\n",
                    },
                    {
                        "op": "write_file",
                        "path": "requirements.txt",
                        "content": "typer==0.21.1\n",
                    },
                ],
                "verification_commands": [],
            },
        ]
    )


def test_orchestrator_replay_produces_stable_artifact_hashes(tmp_path: Path) -> None:
    first = tmp_path / "run-a"
    second = tmp_path / "run-b"
    config = AgentConfig(reproducible=True, prompt_seed_base=99)

    first_agent = SoftwareDevelopmentAgent(provider=_provider(), config=config)
    second_agent = SoftwareDevelopmentAgent(provider=_provider(), config=config)

    first_agent.run(requirements="replay", output_dir=first)
    second_agent.run(requirements="replay", output_dir=second)

    artifact_paths = [
        Path("artifact.txt"),
        Path(".autosd/backlog.json"),
        Path(".autosd/refined_requirements.md"),
        Path(".autosd/progress.json"),
    ]
    for rel_path in artifact_paths:
        assert _hash_file(first / rel_path) == _hash_file(second / rel_path)
