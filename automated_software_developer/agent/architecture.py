"""Architecture synthesis and artifact generation helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from automated_software_developer.agent.models import (
    ArchitectureComponent,
    ArchitectureDecision,
    ArchitecturePlan,
    RefinedRequirements,
)
from automated_software_developer.agent.prompts import (
    ARCHITECTURE_SYSTEM_PROMPT,
    build_architecture_user_prompt,
)
from automated_software_developer.agent.providers.base import LLMProvider


@dataclass(frozen=True)
class DependencyEdge:
    """Dependency graph edge linking components."""

    source: str
    target: str

    def to_dict(self) -> dict[str, str]:
        """Serialize dependency edge to dict."""
        return {"from": self.source, "to": self.target}


@dataclass(frozen=True)
class ArchitectureArtifacts:
    """Paths for architecture-related artifacts."""

    architecture_doc: Path
    components_json: Path
    adrs_dir: Path
    adr_files: list[Path]


class ArchitecturePlanner:
    """Creates architecture artifacts from refined requirements."""

    def __init__(self, provider: LLMProvider) -> None:
        """Initialize planner with language model provider."""
        self.provider = provider

    def create_plan(
        self,
        refined: RefinedRequirements,
        repo_guidelines: str | None = None,
        *,
        seed: int | None = None,
    ) -> ArchitecturePlan:
        """Generate architecture plan from refined requirements."""
        response = self.provider.generate_json(
            system_prompt=ARCHITECTURE_SYSTEM_PROMPT,
            user_prompt=build_architecture_user_prompt(refined.to_markdown(), repo_guidelines),
            seed=seed,
        )
        return ArchitecturePlan.from_dict(response)

    def write_artifacts(
        self,
        plan: ArchitecturePlan,
        output_dir: Path,
    ) -> ArchitectureArtifacts:
        """Write architecture artifacts to the project workspace."""
        architecture_dir = output_dir / ".autosd" / "architecture"
        adrs_dir = architecture_dir / "adrs"
        architecture_dir.mkdir(parents=True, exist_ok=True)
        adrs_dir.mkdir(parents=True, exist_ok=True)

        architecture_doc = architecture_dir / "architecture.md"
        components_json = architecture_dir / "components.json"

        architecture_doc.write_text(_render_architecture_markdown(plan), encoding="utf-8")
        components_payload = {
            "components": [component.to_dict() for component in plan.components],
            "dependency_graph": {
                "edges": [edge.to_dict() for edge in _build_dependency_graph(plan.components)]
            },
        }
        components_json.write_text(json.dumps(components_payload, indent=2), encoding="utf-8")

        adr_files: list[Path] = []
        for decision in plan.decisions:
            adr_path = adrs_dir / f"{decision.adr_id}.md"
            adr_path.write_text(_render_adr_markdown(decision), encoding="utf-8")
            adr_files.append(adr_path)

        return ArchitectureArtifacts(
            architecture_doc=architecture_doc,
            components_json=components_json,
            adrs_dir=adrs_dir,
            adr_files=adr_files,
        )


def _build_dependency_graph(
    components: list[ArchitectureComponent],
) -> list[DependencyEdge]:
    """Build dependency edges for a set of components."""
    edges: list[DependencyEdge] = []
    for component in components:
        for dependency in component.dependencies:
            edges.append(DependencyEdge(source=component.component_id, target=dependency))
    return edges


def _render_architecture_markdown(plan: ArchitecturePlan) -> str:
    """Render architecture overview markdown."""
    lines: list[str] = [
        "# Architecture Overview",
        "",
        plan.overview,
        "",
        "## Components",
    ]
    for component in plan.components:
        lines.extend(
            [
                "",
                f"### {component.component_id}: {component.name}",
                "Responsibilities:",
                *(f"- {item}" for item in component.responsibilities),
                "Interfaces:",
                *(f"- {item}" for item in component.interfaces or ["none"]),
                "Dependencies:",
                *(f"- {item}" for item in component.dependencies or ["none"]),
            ]
        )
    lines.append("")
    return "\n".join(lines)


def _render_adr_markdown(decision: ArchitectureDecision) -> str:
    """Render ADR markdown content."""
    lines = [
        f"# ADR {decision.adr_id}: {decision.title}",
        "",
        f"Status: {decision.status}",
        "",
        "## Context",
        decision.context,
        "",
        "## Decision",
        decision.decision,
        "",
        "## Consequences",
        *(f"- {item}" for item in decision.consequences),
        "",
    ]
    return "\n".join(lines)
