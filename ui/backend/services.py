"""Service layer for the Autonomous Engineering Console backend."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from automated_software_developer.agent.policy.engine import resolve_effective_policy
from automated_software_developer.agent.progress import ProgressTracker
from automated_software_developer.agent.ui.requirements_assistant import (
    RequirementsAssistant,
    RequirementsDraft,
    RequirementsRefinement,
    RequirementsValidation,
)
from automated_software_developer.agent.ui.requirements_assistant import (
    RequirementsResponse as AssistantResponse,
)
from ui.backend.events import Event, EventBroker
from ui.backend.models import PlanResponse, ProjectStatus
from ui.backend.store import ProjectStore


@dataclass(frozen=True)
class RequirementsServiceResponse:
    """Response payload for requirements service."""

    session_id: str
    questions: tuple[str, ...]
    suggestions: tuple[str, ...]
    draft: dict[str, Any]


class RequirementsService:
    """Adapter between API payloads and requirements assistant."""

    def __init__(self) -> None:
        self._assistant = RequirementsAssistant()

    def start(self, idea: str) -> RequirementsServiceResponse:
        response = self._assistant.start_session(idea)
        return self._to_service_response(response)

    def message(self, session_id: str, message: str) -> RequirementsServiceResponse:
        response = self._assistant.add_message(session_id, message)
        return self._to_service_response(response)

    def finalize(self, session_id: str) -> RequirementsDraft:
        return self._assistant.finalize(session_id)

    def refine(self, markdown: str) -> RequirementsRefinement:
        draft = self._assistant.start_session(markdown).draft
        return self._assistant.refine_markdown(draft)

    def validate(self, markdown: str) -> RequirementsValidation:
        return self._assistant.validate_markdown(markdown)

    def _to_service_response(self, response: AssistantResponse) -> RequirementsServiceResponse:
        return RequirementsServiceResponse(
            session_id=response.session_id,
            questions=response.questions,
            suggestions=response.suggestions,
            draft=self._draft_to_payload(response.draft),
        )

    def _draft_to_payload(self, draft: RequirementsDraft) -> dict[str, Any]:
        return {
            "summary": draft.summary,
            "goals": list(draft.goals),
            "constraints": list(draft.constraints),
            "functional_requirements": list(draft.functional_requirements),
            "non_functional_requirements": list(draft.non_functional_requirements),
            "acceptance_criteria": list(draft.acceptance_criteria),
            "risks": list(draft.risks),
            "compliance_flags": list(draft.compliance_flags),
        }


class PlanBuilder:
    """Builds a lightweight plan preview from requirements."""

    def build(self, requirements: str) -> PlanResponse:
        if not requirements.strip():
            raise ValueError("requirements must be non-empty.")
        architecture = {
            "style": "event-driven",
            "components": [
                "UI (React + Tailwind)",
                "API (FastAPI)",
                "Orchestrator (autosd)",
                "Telemetry & Audit",
            ],
        }
        sprint_plan = [
            {"sprint": 1, "focus": "Backend APIs + requirements assistant"},
            {"sprint": 2, "focus": "UI flows + dashboard"},
            {"sprint": 3, "focus": "Live events + launch pipeline"},
        ]
        timeline = {"estimate_weeks": 3, "confidence": "medium"}
        risks = [
            "Requirements ambiguity may delay autonomy.",
            "Policy/preauth alignment needed before production deploys.",
        ]
        cost_estimate = {"monthly_usd": 1200, "drivers": ["LLM usage", "compute"]}
        deployment_targets = ["staging", "production"]
        return PlanResponse(
            architecture=architecture,
            sprint_plan=sprint_plan,
            timeline=timeline,
            risks=risks,
            cost_estimate=cost_estimate,
            deployment_targets=deployment_targets,
        )


class LaunchCoordinator:
    """Coordinates the launch of an autonomous build."""

    def __init__(self, *, store: ProjectStore, broker: EventBroker) -> None:
        self._store = store
        self._broker = broker

    def launch(self, project_id: str) -> tuple[str, ProjectStatus]:
        project = self._store.get_project(project_id)
        if not project.requirements:
            raise ValueError("Project requirements must be set before launch.")
        policy = resolve_effective_policy(project_policy=None, grant=None)
        self._persist_requirements(project_id, project.requirements, policy.payload)
        self._broker.publish(
            Event.create(
                project_id=project_id,
                event_type="policy_snapshot",
                message="Policy snapshot captured.",
                reason=f"telemetry_mode={policy.payload['telemetry']['mode']}",
            )
        )
        launch_id = uuid4().hex
        _ = self._store.update_status(project_id, ProjectStatus.running)
        self._store.add_run(
            project_id,
            {
                "run_id": launch_id,
                "status": ProjectStatus.running,
                "started_at": datetime.now(UTC),
            },
        )
        self._store.add_artifact(
            project_id,
            {"name": "Requirements Snapshot", "path": ".autosd/refined_requirements.md"},
        )
        tracker = ProgressTracker(project_id=project_id, base_dir=Path.cwd())
        tracker.start_phase("Requirements")
        tracker.complete_step("Requirements", "lock")
        tracker.record_story_points(completed=0, total=20)
        snapshot = tracker.save()
        self._store.update_progress(project_id, snapshot.to_dict())
        self._broker.publish(
            Event.create(
                project_id=project_id,
                event_type="autonomy_launch",
                message="Autonomous build launched.",
                reason="requirements_locked",
                artifact_url=".autosd/refined_requirements.md",
            )
        )
        self._broker.publish(
            Event.create(
                project_id=project_id,
                event_type="progress.updated",
                message="Progress snapshot updated.",
                reason=f"percent={snapshot.percent_complete}",
            )
        )
        self._broker.publish(
            Event.create(
                project_id=project_id,
                event_type="agent_activity",
                message="ENG implementing sprint backlog.",
                reason="autonomous_execution",
            )
        )
        return launch_id, ProjectStatus.running

    def pause(self, project_id: str) -> ProjectStatus:
        """Pause an autonomous build."""
        status = self._store.update_status(project_id, ProjectStatus.paused)
        self._broker.publish(
            Event.create(
                project_id=project_id,
                event_type="autonomy_pause",
                message="Autonomous build paused.",
                reason="manual_pause",
            )
        )
        return status

    def resume(self, project_id: str) -> ProjectStatus:
        """Resume a paused autonomous build."""
        status = self._store.update_status(project_id, ProjectStatus.running)
        self._broker.publish(
            Event.create(
                project_id=project_id,
                event_type="autonomy_resume",
                message="Autonomous build resumed.",
                reason="manual_resume",
            )
        )
        return status

    def cancel(self, project_id: str) -> ProjectStatus:
        """Cancel an autonomous build."""
        status = self._store.update_status(project_id, ProjectStatus.failed)
        self._broker.publish(
            Event.create(
                project_id=project_id,
                event_type="autonomy_cancel",
                message="Autonomous build cancelled.",
                reason="manual_cancel",
            )
        )
        return status

    def _persist_requirements(
        self, project_id: str, requirements: str, policy_payload: dict[str, Any]
    ) -> None:
        autosd_dir = Path.cwd() / ".autosd"
        autosd_dir.mkdir(parents=True, exist_ok=True)
        (autosd_dir / "refined_requirements.md").write_text(
            requirements, encoding="utf-8"
        )
        (autosd_dir / "requirements_snapshot.json").write_text(
            _to_json({"project_id": project_id, "requirements": requirements}),
            encoding="utf-8",
        )
        (autosd_dir / "policy_resolved.json").write_text(
            _to_json(policy_payload), encoding="utf-8"
        )


def create_default_paths(base_dir: Path) -> dict[str, Path]:
    """Return deterministic paths for daemon integration."""
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return {
        "requirements_dir": base_dir / "requirements",
        "projects_dir": base_dir / "projects",
        "registry_path": base_dir / f"registry_{timestamp}.json",
        "incidents_path": base_dir / "incidents.json",
    }


def _to_json(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, sort_keys=True)
