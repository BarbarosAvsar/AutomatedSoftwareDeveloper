"""Pipeline truth map and schema definitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class PipelineStep:
    """Represents a single pipeline step definition."""

    step_id: str
    name: str
    description: str
    substeps: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable representation."""
        return {
            "id": self.step_id,
            "name": self.name,
            "description": self.description,
            "substeps": list(self.substeps),
        }


@dataclass(frozen=True)
class PipelineDefinition:
    """Defines a pipeline and its ordered steps."""

    pipeline_id: str
    name: str
    steps: tuple[PipelineStep, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable representation."""
        return {
            "id": self.pipeline_id,
            "name": self.name,
            "steps": [step.to_dict() for step in self.steps],
        }


PIPELINE_STATUS_VALUES: tuple[str, ...] = (
    "not_started",
    "in_progress",
    "blocked",
    "completed",
    "failed",
)


PIPELINE_EVENT_SCHEMA: dict[str, Any] = {
    "title": "PipelineEvent",
    "type": "object",
    "required": ["event_id", "timestamp", "pipeline", "step", "status"],
    "properties": {
        "event_id": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"},
        "pipeline": {"type": "string"},
        "step": {"type": "string"},
        "status": {"type": "string", "enum": list(PIPELINE_STATUS_VALUES)},
        "message": {"type": "string"},
        "metadata": {"type": "object"},
    },
}


def pipeline_truth_map() -> tuple[PipelineDefinition, ...]:
    """Return the authoritative pipeline truth map."""
    return (
        PipelineDefinition(
            pipeline_id="generator",
            name="Generator Pipeline",
            steps=(
                PipelineStep(
                    step_id="refine",
                    name="Refine",
                    description="Refine raw requirements into validated stories.",
                    substeps=("draft", "refine", "validate", "lock"),
                ),
                PipelineStep(
                    step_id="plan",
                    name="Plan",
                    description="Build architecture and backlog plans.",
                    substeps=("architecture", "backlog", "sprint_planning"),
                ),
                PipelineStep(
                    step_id="sprint",
                    name="Sprint",
                    description="Execute sprint stories with bounded retries.",
                    substeps=("stories_in_progress", "stories_completed"),
                ),
                PipelineStep(
                    step_id="gates",
                    name="Gates",
                    description="Run quality, test, and security gates.",
                    substeps=("tests", "quality_gates", "security_scans"),
                ),
                PipelineStep(
                    step_id="release",
                    name="Release",
                    description="Package artifacts and version outputs.",
                    substeps=("version_tag", "artifacts"),
                ),
                PipelineStep(
                    step_id="deploy",
                    name="Deploy",
                    description="Deploy to environments per policy.",
                    substeps=("dev", "staging", "production"),
                ),
                PipelineStep(
                    step_id="monitor",
                    name="Monitor",
                    description="Monitor health checks and alerts.",
                    substeps=("health_checks",),
                ),
                PipelineStep(
                    step_id="learn",
                    name="Learn",
                    description="Capture retrospectives and template learnings.",
                    substeps=("retrospective", "template_proposals"),
                ),
            ),
        ),
        PipelineDefinition(
            pipeline_id="ci",
            name="CI Pipeline",
            steps=(
                PipelineStep(
                    step_id="workflow_lint",
                    name="Workflow Lint",
                    description="Validate workflow syntax and policy compliance.",
                ),
                PipelineStep(
                    step_id="lint",
                    name="Lint",
                    description="Run ruff or equivalent lint checks.",
                ),
                PipelineStep(
                    step_id="typecheck",
                    name="Typecheck",
                    description="Run mypy or equivalent type checks.",
                ),
                PipelineStep(
                    step_id="test",
                    name="Test",
                    description="Run unit and integration tests.",
                ),
                PipelineStep(
                    step_id="conformance",
                    name="Conformance",
                    description="Execute generator conformance fixtures.",
                ),
            ),
        ),
    )


def generator_progress_definition() -> list[dict[str, Any]]:
    """Return generator pipeline steps mapped for progress tracking."""
    return [
        {
            "name": "Requirements",
            "weight": 1.0,
            "steps": ("draft", "refine", "validate", "lock"),
        },
        {
            "name": "Planning",
            "weight": 1.0,
            "steps": ("architecture", "backlog", "sprint_planning"),
        },
        {
            "name": "Implementation",
            "weight": 2.0,
            "steps": ("stories_in_progress", "stories_completed"),
        },
        {
            "name": "Verification",
            "weight": 1.0,
            "steps": ("tests", "quality_gates", "security_scans"),
        },
        {
            "name": "Release",
            "weight": 1.0,
            "steps": ("version_tag", "artifacts"),
        },
        {
            "name": "Deployment",
            "weight": 1.0,
            "steps": ("dev", "staging", "production"),
        },
        {
            "name": "Monitoring",
            "weight": 1.0,
            "steps": ("health_checks",),
        },
        {
            "name": "Learning",
            "weight": 1.0,
            "steps": ("retrospective", "template_proposals"),
        },
    ]


def pipeline_event_payload(
    *,
    pipeline: str,
    step: str,
    status: str,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a pipeline event payload with validation."""
    if status not in PIPELINE_STATUS_VALUES:
        raise ValueError("status must be a valid pipeline status.")
    payload: dict[str, Any] = {
        "event_id": f"{pipeline}:{step}:{datetime.now(tz=UTC).isoformat()}",
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "pipeline": pipeline,
        "step": step,
        "status": status,
    }
    if message:
        payload["message"] = message
    if metadata:
        payload["metadata"] = metadata
    return payload


def validate_pipeline_event(payload: dict[str, Any]) -> None:
    """Validate required fields for pipeline events."""
    for field in PIPELINE_EVENT_SCHEMA["required"]:
        if field not in payload:
            raise ValueError(f"Pipeline event missing required field: {field}")
    status = payload.get("status")
    if status not in PIPELINE_STATUS_VALUES:
        raise ValueError("Pipeline event status must be a valid status value.")
