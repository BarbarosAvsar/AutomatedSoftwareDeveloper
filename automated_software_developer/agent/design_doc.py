"""Design document generation for generated project context continuity."""

from __future__ import annotations

from automated_software_developer.agent.backlog import StoryBacklog
from automated_software_developer.agent.models import RefinedRequirements


def build_design_doc_markdown(
    refined: RefinedRequirements,
    backlog: StoryBacklog,
    *,
    phase: str,
) -> str:
    """Build a concise living design document for the generated project."""
    lines: list[str] = [
        "# Internal Design Doc",
        "",
        "This document is maintained by the agent to preserve implementation context.",
        "",
        "## Project Name",
        refined.project_name,
        "",
        "## Phase",
        phase,
        "",
        "## Product Brief",
        refined.product_brief,
        "",
        "## Architecture Notes",
        "- Story-by-story backlog execution with bounded retries.",
        "- Requirements-first pipeline with canonical refinement artifact.",
        "- Verification stack: acceptance checks, automated tests, and quality gates.",
        "- Security posture: risk-reduced and hardened (not guaranteed secure).",
        "",
        "## Personas",
    ]
    lines.extend(f"- {persona}" for persona in refined.personas or ["General user"])

    lines.extend(["", "## Stories"])
    for story in backlog.stories:
        lines.extend(
            [
                f"- `{story.story_id}` [{story.status}] {story.title}",
                f"  - {story.story}",
                f"  - Attempts: {story.attempts}",
                f"  - Last error: {story.last_error or 'none'}",
            ]
        )

    lines.extend(["", "## Non-Functional Requirements"])
    for category, constraints in sorted(refined.nfrs.items()):
        if not constraints:
            continue
        lines.append(f"### {category}")
        lines.extend(f"- {item}" for item in constraints)
    if all(not constraints for constraints in refined.nfrs.values()):
        lines.append("- No explicit non-functional constraints captured.")

    lines.extend(["", "## Assumptions"])
    for item in refined.assumptions:
        lines.append(f"- {item.assumption}")
        lines.append(f"  - Test criterion: {item.testable_criterion}")

    lines.extend(["", "## Verification Strategy"])
    lines.extend(f"- `{command}`" for command in backlog.global_verification_commands)
    lines.append("")
    return "\n".join(lines)
