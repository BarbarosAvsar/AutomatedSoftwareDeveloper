"""Data models for the autonomous software development workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _require_string(value: Any, field_name: str) -> str:
    """Validate and return a non-empty string."""
    if not isinstance(value, str):
        raise ValueError(f"Expected '{field_name}' to be a string.")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"Expected '{field_name}' to be non-empty.")
    return cleaned


def _require_string_list(value: Any, field_name: str) -> list[str]:
    """Validate a list of non-empty strings."""
    if not isinstance(value, list):
        raise ValueError(f"Expected '{field_name}' to be a list.")
    normalized: list[str] = []
    for index, item in enumerate(value):
        normalized.append(_require_string(item, f"{field_name}[{index}]"))
    return normalized


def _require_dict(value: Any, field_name: str) -> dict[str, Any]:
    """Validate and return a dictionary object."""
    if not isinstance(value, dict):
        raise ValueError(f"Expected '{field_name}' to be an object.")
    return value


def _require_optional_string_list(value: Any, field_name: str) -> list[str]:
    """Validate an optional list of strings."""
    if value is None:
        return []
    return _require_string_list(value, field_name)


def _normalize_list_dict(value: Any, field_name: str) -> list[dict[str, Any]]:
    """Validate list of dict objects."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"Expected '{field_name}' to be a list.")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"Expected '{field_name}[{index}]' to be an object.")
        normalized.append(item)
    return normalized


@dataclass(frozen=True)
class PlanTask:
    """Represents a single implementation task in the development plan."""

    task_id: str
    title: str
    description: str
    acceptance_criteria: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanTask:
        """Create a task from model-produced JSON."""
        return cls(
            task_id=_require_string(data.get("id"), "id"),
            title=_require_string(data.get("title"), "title"),
            description=_require_string(data.get("description"), "description"),
            acceptance_criteria=_require_string_list(
                data.get("acceptance_criteria", []),
                "acceptance_criteria",
            ),
        )


@dataclass(frozen=True)
class AssumptionItem:
    """A documented assumption paired with a testable criterion."""

    assumption: str
    testable_criterion: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssumptionItem:
        """Create assumption item from model JSON."""
        return cls(
            assumption=_require_string(data.get("assumption"), "assumption"),
            testable_criterion=_require_string(
                data.get("testable_criterion"),
                "testable_criterion",
            ),
        )


@dataclass(frozen=True)
class RefinedStory:
    """Story-level refined requirement with acceptance criteria and checks."""

    story_id: str
    title: str
    story: str
    acceptance_criteria: list[str]
    nfr_tags: list[str]
    dependencies: list[str]
    verification_commands: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RefinedStory:
        """Create a refined story from model JSON."""
        story = _require_string(data.get("story"), "story")
        if not story.lower().startswith("as a"):
            raise ValueError("Story text must follow 'As a ... I want ... so that ...' format.")
        return cls(
            story_id=_require_string(data.get("id"), "id"),
            title=_require_string(data.get("title"), "title"),
            story=story,
            acceptance_criteria=_require_string_list(
                data.get("acceptance_criteria", []),
                "acceptance_criteria",
            ),
            nfr_tags=_require_optional_string_list(data.get("nfr_tags"), "nfr_tags"),
            dependencies=_require_optional_string_list(data.get("dependencies"), "dependencies"),
            verification_commands=_require_optional_string_list(
                data.get("verification_commands"),
                "verification_commands",
            ),
        )


@dataclass(frozen=True)
class RefinedRequirements:
    """Canonical refined requirements artifact used for backlog execution."""

    project_name: str
    product_brief: str
    personas: list[str]
    stories: list[RefinedStory]
    nfrs: dict[str, list[str]]
    ambiguities: list[str]
    contradictions: list[str]
    missing_constraints: list[str]
    edge_cases: list[str]
    external_dependencies: list[str]
    assumptions: list[AssumptionItem]
    stack_rationale: str
    global_verification_commands: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RefinedRequirements:
        """Create validated refined requirements from model JSON."""
        stories_raw = _normalize_list_dict(data.get("stories"), "stories")
        if not stories_raw:
            raise ValueError("Refinement output must include at least one story.")
        stories = [RefinedStory.from_dict(item) for item in stories_raw]

        nfrs_raw = _require_dict(data.get("nfrs", {}), "nfrs")
        nfrs: dict[str, list[str]] = {}
        for key, value in nfrs_raw.items():
            nfrs[_require_string(key, "nfrs key")] = _require_string_list(value, f"nfrs[{key}]")

        assumptions_raw = _normalize_list_dict(data.get("assumptions"), "assumptions")
        assumptions = [AssumptionItem.from_dict(item) for item in assumptions_raw]
        if not assumptions:
            assumptions = [
                AssumptionItem(
                    assumption="No additional unstated constraints beyond provided requirements.",
                    testable_criterion=(
                        "Given provided requirements, when checks pass, then generated software "
                        "satisfies explicitly requested scope."
                    ),
                )
            ]

        verification_commands = _require_optional_string_list(
            data.get("global_verification_commands"),
            "global_verification_commands",
        )
        if not verification_commands:
            verification_commands = ["python -m pytest -q"]

        return cls(
            project_name=_require_string(data.get("project_name"), "project_name"),
            product_brief=_require_string(data.get("product_brief"), "product_brief"),
            personas=_require_optional_string_list(data.get("personas"), "personas"),
            stories=stories,
            nfrs=nfrs,
            ambiguities=_require_optional_string_list(data.get("ambiguities"), "ambiguities"),
            contradictions=_require_optional_string_list(
                data.get("contradictions"),
                "contradictions",
            ),
            missing_constraints=_require_optional_string_list(
                data.get("missing_constraints"),
                "missing_constraints",
            ),
            edge_cases=_require_optional_string_list(data.get("edge_cases"), "edge_cases"),
            external_dependencies=_require_optional_string_list(
                data.get("external_dependencies"),
                "external_dependencies",
            ),
            assumptions=assumptions,
            stack_rationale=_require_string(data.get("stack_rationale"), "stack_rationale"),
            global_verification_commands=verification_commands,
        )

    def to_markdown(self) -> str:
        """Render canonical refined requirements artifact."""
        personas_text = (
            "\n".join(f"- {persona}" for persona in self.personas)
            if self.personas
            else "- General user"
        )
        sections: list[str] = [
            "# Refined Requirements",
            "",
            "## Project Name",
            self.project_name,
            "",
            "## Product Brief",
            self.product_brief,
            "",
            "## Personas / Actors",
            personas_text,
            "",
            "## User Stories",
        ]
        for story in self.stories:
            sections.extend(
                [
                    "",
                    f"### {story.story_id}: {story.title}",
                    story.story,
                    "",
                    "Acceptance Criteria (Given/When/Then):",
                    *(f"- {criterion}" for criterion in story.acceptance_criteria),
                    "",
                    "NFR Tags:",
                    *(f"- {tag}" for tag in story.nfr_tags or ["none"]),
                    "",
                    "Dependencies:",
                    *(f"- {dep}" for dep in story.dependencies or ["none"]),
                ]
            )

        sections.extend(["", "## Non-Functional Requirements"])
        if self.nfrs:
            for category, items in self.nfrs.items():
                sections.append(f"### {category}")
                sections.extend(f"- {item}" for item in items)
        else:
            sections.append("- No additional NFRs identified.")

        sections.extend(
            [
                "",
                "## Ambiguities",
                *(f"- {item}" for item in self.ambiguities or ["none"]),
                "",
                "## Contradictions",
                *(f"- {item}" for item in self.contradictions or ["none"]),
                "",
                "## Missing Constraints",
                *(f"- {item}" for item in self.missing_constraints or ["none"]),
                "",
                "## Edge Cases",
                *(f"- {item}" for item in self.edge_cases or ["none"]),
                "",
                "## External Dependencies",
                *(f"- {item}" for item in self.external_dependencies or ["none"]),
                "",
                "## Assumptions",
            ]
        )
        for item in self.assumptions:
            sections.append(f"- Assumption: {item.assumption}")
            sections.append(f"  - Testable criterion: {item.testable_criterion}")

        sections.extend(
            ["", "## Stack Rationale", self.stack_rationale, "", "## Global Verification Commands"]
        )
        sections.extend(f"- `{command}`" for command in self.global_verification_commands)
        sections.append("")
        return "\n".join(sections)


@dataclass(frozen=True)
class BacklogStory:
    """Story item scheduled and tracked by the sprint loop."""

    story_id: str
    title: str
    story: str
    acceptance_criteria: list[str]
    nfr_tags: list[str]
    dependencies: list[str]
    verification_commands: list[str]
    status: str = "pending"
    attempts: int = 0
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize backlog story for persistence."""
        return {
            "id": self.story_id,
            "title": self.title,
            "story": self.story,
            "acceptance_criteria": self.acceptance_criteria,
            "nfr_tags": self.nfr_tags,
            "dependencies": self.dependencies,
            "verification_commands": self.verification_commands,
            "status": self.status,
            "attempts": self.attempts,
            "last_error": self.last_error,
        }

    @classmethod
    def from_refined_story(cls, story: RefinedStory) -> BacklogStory:
        """Convert a refined story into backlog story format."""
        return cls(
            story_id=story.story_id,
            title=story.title,
            story=story.story,
            acceptance_criteria=story.acceptance_criteria,
            nfr_tags=story.nfr_tags,
            dependencies=story.dependencies,
            verification_commands=story.verification_commands,
        )


@dataclass(frozen=True)
class StoryExecutionState:
    """Execution state for a story attempt."""

    story_id: str
    attempt: int
    status: str
    verification_results: list[CommandResult]
    error: str | None = None


@dataclass(frozen=True)
class PromptTemplate:
    """Versioned prompt template used by coding and refinement stages."""

    template_id: str
    version: int
    directives: list[str]
    retry_directives: list[str]
    constraints: list[str]


@dataclass(frozen=True)
class DevelopmentPlan:
    """Structured plan generated from input requirements."""

    project_name: str
    stack_rationale: str
    tasks: list[PlanTask]
    verification_commands: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DevelopmentPlan:
        """Create a validated development plan from JSON."""
        task_items = data.get("tasks")
        if not isinstance(task_items, list) or not task_items:
            raise ValueError("Expected at least one task in planning output.")
        tasks = [PlanTask.from_dict(item) for item in task_items]
        verification_commands = _require_string_list(
            data.get("verification_commands", []),
            "verification_commands",
        )
        if not verification_commands:
            raise ValueError("Planning output must include verification_commands.")
        return cls(
            project_name=_require_string(data.get("project_name"), "project_name"),
            stack_rationale=_require_string(data.get("stack_rationale"), "stack_rationale"),
            tasks=tasks,
            verification_commands=verification_commands,
        )


@dataclass(frozen=True)
class ChangeOperation:
    """File mutation generated by the coding model."""

    op: str
    path: str
    content: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChangeOperation:
        """Create a file operation from JSON with validation."""
        op = _require_string(data.get("op"), "op")
        path = _require_string(data.get("path"), "path")
        if op not in {"write_file", "delete_file"}:
            raise ValueError(f"Unsupported operation '{op}'.")
        content: str | None = None
        if op == "write_file":
            content = _require_string(data.get("content"), "content")
        return cls(op=op, path=path, content=content)


@dataclass(frozen=True)
class ExecutionBundle:
    """Proposed file operations plus optional verification overrides."""

    summary: str
    operations: list[ChangeOperation]
    verification_commands: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionBundle:
        """Create a validated execution bundle from model JSON output."""
        operation_data = data.get("operations")
        if not isinstance(operation_data, list) or not operation_data:
            raise ValueError("Execution output must include at least one operation.")
        operations = [ChangeOperation.from_dict(item) for item in operation_data]

        verification_commands_raw = data.get("verification_commands", [])
        if verification_commands_raw and not isinstance(verification_commands_raw, list):
            raise ValueError("verification_commands must be a list when provided.")
        verification_commands = (
            _require_string_list(verification_commands_raw, "verification_commands")
            if verification_commands_raw
            else []
        )
        return cls(
            summary=_require_string(data.get("summary"), "summary"),
            operations=operations,
            verification_commands=verification_commands,
        )


@dataclass(frozen=True)
class CommandResult:
    """Result of executing a shell command during validation."""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float

    @property
    def passed(self) -> bool:
        """Whether the command completed successfully."""
        return self.exit_code == 0


@dataclass
class TaskProgress:
    """Runtime state for a task in progress."""

    task: PlanTask
    status: str = "pending"
    attempts: int = 0
    last_error: str | None = None
    results: list[CommandResult] = field(default_factory=list)


@dataclass(frozen=True)
class RunSummary:
    """Final summary returned by the orchestrator."""

    output_dir: Path
    project_name: str
    stack_rationale: str
    tasks_total: int
    tasks_completed: int
    changed_files: list[str]
    verification_results: list[CommandResult]
    refined_spec_path: Path | None = None
    backlog_path: Path | None = None
    design_doc_path: Path | None = None
    sprint_log_path: Path | None = None
    journal_path: Path | None = None
    platform_plan_path: Path | None = None
    capability_graph_path: Path | None = None
