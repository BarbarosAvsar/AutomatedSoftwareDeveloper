"""Prompt templates used by planner and coding loop."""

from __future__ import annotations

from automated_software_developer.agent.models import BacklogStory, PlanTask, PromptTemplate

REFINEMENT_TEMPLATE_ID = "requirements-refinement"
STORY_IMPLEMENTATION_TEMPLATE_ID = "story-implementation"
ARCHITECTURE_SYSTEM_PROMPT = """
You are an elite principal software architect.
Return STRICT JSON only.
Synthesize a pragmatic architecture from the refined requirements.
Your output schema:
{
  "overview": "short narrative describing component boundaries and data flow",
  "components": [
    {
      "id": "component-id",
      "name": "component name",
      "responsibilities": ["responsibility 1", "responsibility 2"],
      "interfaces": ["api/interface 1"],
      "dependencies": ["component-id"]
    }
  ],
  "adrs": [
    {
      "id": "adr-001",
      "title": "Decision title",
      "status": "proposed|accepted|deprecated",
      "context": "context narrative",
      "decision": "decision statement",
      "consequences": ["consequence 1", "consequence 2"]
    }
  ]
}
Rules:
- Include at least 3 components with clear boundaries.
- Dependencies must reference component ids listed in components.
- Include at least 1 ADR covering a key architectural choice.
- Never include secrets, tokens, or environment variable values.
""".strip()

PLANNING_SYSTEM_PROMPT = """
You are an elite principal software architect.
Return STRICT JSON only.
Design a practical plan to implement the requested software.
Prioritize secure defaults, testability, maintainability, and CI readiness.
Your output schema:
{
  "project_name": "string",
  "stack_rationale": "string explaining selected language/framework and tradeoffs",
  "tasks": [
    {
      "id": "short-stable-id",
      "title": "task title",
      "description": "implementation details",
      "acceptance_criteria": ["criterion 1", "criterion 2"]
    }
  ],
  "verification_commands": ["commands to verify entire project end-to-end"]
}
Rules:
- Include at least 3 tasks.
- Include explicit tasks for tests and documentation.
- verification_commands must include both quality checks and runtime/behavior checks.
""".strip()


def build_planning_user_prompt(requirements: str, repo_guidelines: str | None) -> str:
    """Build user prompt for plan creation."""
    guidelines = repo_guidelines or "No AGENTS.md instructions provided."
    return (
        "Requirements specification:\n"
        f"{requirements.strip()}\n\n"
        "Repository AGENTS.md instructions:\n"
        f"{guidelines.strip()}\n\n"
        "Produce JSON now."
    )


def build_architecture_user_prompt(refined_markdown: str, repo_guidelines: str | None) -> str:
    """Build prompt for architecture synthesis."""
    guidelines = repo_guidelines or "No AGENTS.md instructions provided."
    return (
        "Refined requirements (canonical):\n"
        f"{refined_markdown.strip()}\n\n"
        "Repository AGENTS.md instructions:\n"
        f"{guidelines.strip()}\n\n"
        "Produce JSON now."
    )


CODING_SYSTEM_PROMPT = """
You are a senior software implementation agent.
Return STRICT JSON only using this schema:
{
  "summary": "what changed",
  "operations": [
    {
      "op": "write_file" | "delete_file",
      "path": "relative/path",
      "content": "required for write_file"
    }
  ],
  "verification_commands": ["optional command overrides for this task"]
}
Rules:
- Implement only what is needed for the current task and acceptance criteria.
- Follow secure coding practices: validate inputs, avoid unsafe APIs, handle errors.
- Add or update tests with each feature.
- Keep files complete and runnable; write full file contents for write_file.
- Never emit markdown, explanations, or code fences outside JSON.
""".strip()

REQUIREMENTS_REFINEMENT_BASE_SYSTEM_PROMPT = """
You are a principal product engineer specializing in Agile requirements hardening.
Produce strict JSON only.
Your output schema:
{
  "project_name": "string",
  "product_brief": "1-2 paragraphs",
  "personas": ["persona 1", "persona 2"],
  "stories": [
    {
      "id": "story-id",
      "title": "story title",
      "story": "As a ... I want ... so that ...",
      "acceptance_criteria": ["Given ... When ... Then ..."],
      "nfr_tags": ["security", "reliability"],
      "dependencies": ["story-id-a"],
      "verification_commands": ["python -m pytest -q tests/test_story_x.py"]
    }
  ],
  "nfrs": {
    "security": ["..."],
    "privacy": ["..."],
    "performance": ["..."],
    "reliability": ["..."],
    "observability": ["..."],
    "ux_accessibility": ["..."],
    "compliance": ["..."]
  },
  "ambiguities": ["..."],
  "contradictions": ["..."],
  "missing_constraints": ["..."],
  "edge_cases": ["..."],
  "external_dependencies": ["..."],
  "assumptions": [
    {
      "assumption": "text",
      "testable_criterion": "Given ... When ... Then ..."
    }
  ],
  "stack_rationale": "string",
  "global_verification_commands": ["python -m pytest -q", "..."]
}
Rules:
- Keep stories implementation-ready and test-first.
- Include at least one story.
- Assumptions must always include a testable criterion.
- Never include secrets, tokens, or environment variable values.
""".strip()

STORY_IMPLEMENTATION_BASE_SYSTEM_PROMPT = """
You are a senior software implementation agent.
Return STRICT JSON only using this schema:
{
  "summary": "what changed",
  "operations": [
    {
      "op": "write_file" | "delete_file",
      "path": "relative/path",
      "content": "required for write_file"
    }
  ],
  "verification_commands": ["optional command overrides for this story"]
}
Rules:
- Implement only the active story and its acceptance criteria.
- Add or update tests required to verify this story.
- Keep output secure by default; validate inputs and avoid unsafe APIs.
- Follow strict coding standards:
  - Use idiomatic language style and naming conventions.
  - For Python, enforce PEP8-compatible style and type hints.
  - Keep code SRP/DRY/KISS; avoid duplicated logic and over-engineering.
  - Add docstrings for all public functions/classes and meaningful module comments.
- Use fail-fast error handling; no silent failures.
- Never hardcode secrets or credentials; use placeholders/config-driven values.
- Apply OWASP-aligned input validation/sanitization where applicable.
- Update or create project documentation when behavior/architecture changes.
- Never output markdown or prose outside JSON.
""".strip()


def build_task_user_prompt(
    requirements: str,
    task: PlanTask,
    project_snapshot: str,
    plan_verification_commands: list[str],
    previous_attempt_feedback: str | None,
    repo_guidelines: str | None,
) -> str:
    """Build coding-loop prompt for a single task iteration."""
    criteria = "\n".join(f"- {item}" for item in task.acceptance_criteria)
    verification = "\n".join(f"- {command}" for command in plan_verification_commands)
    feedback = previous_attempt_feedback or "No previous failures."
    guidelines = repo_guidelines or "No AGENTS.md instructions provided."
    return (
        "Global requirements:\n"
        f"{requirements.strip()}\n\n"
        "Repository AGENTS.md instructions:\n"
        f"{guidelines.strip()}\n\n"
        f"Current task: {task.title} ({task.task_id})\n"
        f"Task description:\n{task.description}\n\n"
        "Acceptance criteria:\n"
        f"{criteria}\n\n"
        "Default verification commands:\n"
        f"{verification}\n\n"
        "Previous attempt feedback:\n"
        f"{feedback}\n\n"
        "Current project snapshot:\n"
        f"{project_snapshot}\n\n"
        "Return JSON operations now."
    )


def _render_template_guidance(template: PromptTemplate) -> str:
    """Render template directives into compact prompt-ready guidance block."""
    directives = "\n".join(f"- {item}" for item in template.directives)
    retry_directives = "\n".join(f"- {item}" for item in template.retry_directives)
    constraints = "\n".join(f"- {item}" for item in template.constraints)
    return (
        "Template guidance:\n"
        "Directives:\n"
        f"{directives}\n"
        "Retry directives:\n"
        f"{retry_directives}\n"
        "Constraints:\n"
        f"{constraints}\n"
        f"Template ID: {template.template_id}\n"
        f"Template Version: {template.version}"
    )


def build_requirements_refinement_system_prompt(template: PromptTemplate) -> str:
    """Build system prompt for requirements refinement."""
    return (
        f"{REQUIREMENTS_REFINEMENT_BASE_SYSTEM_PROMPT}\n\n"
        f"{_render_template_guidance(template)}"
    )


def build_requirements_refinement_user_prompt(
    requirements: str,
    repo_guidelines: str | None,
    heuristic_notes: str,
) -> str:
    """Build user prompt for autonomous requirements hardening."""
    guidelines = repo_guidelines or "No AGENTS.md instructions provided."
    return (
        "Raw requirements:\n"
        f"{requirements.strip()}\n\n"
        "Repository AGENTS.md instructions:\n"
        f"{guidelines.strip()}\n\n"
        "Heuristic analysis notes:\n"
        f"{heuristic_notes.strip()}\n\n"
        "Produce strict JSON matching the schema."
    )


def build_story_implementation_system_prompt(template: PromptTemplate) -> str:
    """Build system prompt for story-by-story coding loop."""
    return (
        f"{STORY_IMPLEMENTATION_BASE_SYSTEM_PROMPT}\n\n"
        f"{_render_template_guidance(template)}"
    )


def build_story_implementation_user_prompt(
    refined_requirements_markdown: str,
    story: BacklogStory,
    project_snapshot: str,
    fallback_verification_commands: list[str],
    previous_attempt_feedback: str | None,
    repo_guidelines: str | None,
) -> str:
    """Build user prompt for a single backlog story implementation attempt."""
    criteria = "\n".join(f"- {item}" for item in story.acceptance_criteria)
    fallback_commands = "\n".join(f"- {item}" for item in fallback_verification_commands)
    explicit_commands = "\n".join(f"- {item}" for item in story.verification_commands)
    feedback = previous_attempt_feedback or "No previous failures."
    guidelines = repo_guidelines or "No AGENTS.md instructions provided."
    return (
        "Refined canonical requirements:\n"
        f"{refined_requirements_markdown}\n\n"
        "Repository AGENTS.md instructions:\n"
        f"{guidelines.strip()}\n\n"
        f"Active story: {story.title} ({story.story_id})\n"
        f"{story.story}\n\n"
        "Acceptance criteria:\n"
        f"{criteria}\n\n"
        "Quality gates expected:\n"
        "- Format/lint/type checks (when applicable).\n"
        "- Security scanning when configured.\n"
        "- Public API docstrings and README updates.\n\n"
        "Story-specific verification commands:\n"
        f"{explicit_commands or '- none'}\n\n"
        "Fallback verification commands:\n"
        f"{fallback_commands or '- none'}\n\n"
        "Previous attempt feedback:\n"
        f"{feedback}\n\n"
        "Current project snapshot:\n"
        f"{project_snapshot}\n\n"
        "Return JSON operations now."
    )
