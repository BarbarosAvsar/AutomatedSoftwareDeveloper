"""In-memory project store for UI backend."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from ui.backend.models import ProjectResponse, ProjectStatus


@dataclass
class ProjectRecord:
    """Internal representation of a project."""

    id: str
    name: str
    idea: str | None
    status: ProjectStatus
    environment: str
    created_at: datetime
    updated_at: datetime
    last_deploy: datetime | None
    health: str
    incidents: int
    sprint_progress: float
    requirements: str | None
    plan: dict[str, Any] | None
    progress: dict[str, Any] | None
    artifacts: list[dict[str, Any]]
    runs: list[dict[str, Any]]


class ProjectStore:
    """In-memory store with basic validation."""

    def __init__(self) -> None:
        self._projects: dict[str, ProjectRecord] = {}

    def list_projects(self) -> list[ProjectResponse]:
        return [self._to_response(project) for project in self._projects.values()]

    def create_project(self, *, name: str, idea: str | None) -> ProjectResponse:
        if not name.strip():
            raise ValueError("name must be non-empty.")
        project_id = uuid4().hex
        now = datetime.now(UTC)
        record = ProjectRecord(
            id=project_id,
            name=name.strip(),
            idea=idea.strip() if idea else None,
            status=ProjectStatus.draft,
            environment="staging",
            created_at=now,
            updated_at=now,
            last_deploy=None,
            health="unknown",
            incidents=0,
            sprint_progress=0.0,
            requirements=None,
            plan=None,
            progress=None,
            artifacts=[],
            runs=[],
        )
        self._projects[project_id] = record
        return self._to_response(record)

    def get_project(self, project_id: str) -> ProjectResponse:
        record = self._get_record(project_id)
        return self._to_response(record)

    def update_requirements(self, project_id: str, requirements: str) -> ProjectResponse:
        if not requirements.strip():
            raise ValueError("requirements must be non-empty.")
        record = self._get_record(project_id)
        record.requirements = requirements.strip()
        record.updated_at = datetime.now(UTC)
        return self._to_response(record)

    def update_plan(self, project_id: str, plan: dict[str, Any]) -> ProjectResponse:
        record = self._get_record(project_id)
        record.plan = plan
        record.updated_at = datetime.now(UTC)
        return self._to_response(record)

    def update_status(self, project_id: str, status: ProjectStatus) -> ProjectResponse:
        record = self._get_record(project_id)
        record.status = status
        record.updated_at = datetime.now(UTC)
        return self._to_response(record)

    def update_progress(self, project_id: str, progress: dict[str, Any]) -> None:
        record = self._get_record(project_id)
        record.progress = progress
        record.updated_at = datetime.now(UTC)

    def get_progress(self, project_id: str) -> dict[str, Any] | None:
        record = self._get_record(project_id)
        return record.progress

    def add_artifact(self, project_id: str, artifact: dict[str, Any]) -> None:
        record = self._get_record(project_id)
        record.artifacts.append(artifact)
        record.updated_at = datetime.now(UTC)

    def list_artifacts(self, project_id: str) -> list[dict[str, Any]]:
        record = self._get_record(project_id)
        return list(record.artifacts)

    def add_run(self, project_id: str, run: dict[str, Any]) -> None:
        record = self._get_record(project_id)
        record.runs.append(run)
        record.updated_at = datetime.now(UTC)

    def list_runs(self, project_id: str) -> list[dict[str, Any]]:
        record = self._get_record(project_id)
        return list(record.runs)

    def _get_record(self, project_id: str) -> ProjectRecord:
        if project_id not in self._projects:
            raise KeyError("project not found")
        return self._projects[project_id]

    def _to_response(self, record: ProjectRecord) -> ProjectResponse:
        return ProjectResponse(
            id=record.id,
            name=record.name,
            idea=record.idea,
            status=record.status,
            environment=record.environment,
            created_at=record.created_at,
            updated_at=record.updated_at,
            last_deploy=record.last_deploy,
            health=record.health,
            incidents=record.incidents,
            sprint_progress=record.sprint_progress,
            requirements=record.requirements,
            plan=record.plan,
            progress=record.progress,
        )
