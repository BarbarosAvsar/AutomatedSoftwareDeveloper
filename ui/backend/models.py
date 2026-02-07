"""Pydantic models for the UI backend."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):
    """Lifecycle status for a project."""

    draft = "draft"
    planning = "planning"
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"


class ProjectCreateRequest(BaseModel):
    """Request payload for creating a project."""

    name: str = Field(..., min_length=1)
    idea: str | None = None


class ProjectUpdateRequirements(BaseModel):
    """Request payload for updating project requirements."""

    requirements: str = Field(..., min_length=1)


class ProjectResponse(BaseModel):
    """Serialized project response."""

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


class RequirementsSessionRequest(BaseModel):
    """Request payload for starting a requirements session."""

    idea: str = Field(..., min_length=1)


class RequirementsMessageRequest(BaseModel):
    """Request payload for adding a message to a requirements session."""

    message: str = Field(..., min_length=1)


class RequirementsResponse(BaseModel):
    """Response payload for requirements assistant."""

    session_id: str
    questions: tuple[str, ...]
    suggestions: tuple[str, ...]
    draft: dict[str, Any]


class PlanResponse(BaseModel):
    """Response payload for plan preview."""

    architecture: dict[str, Any]
    sprint_plan: list[dict[str, Any]]
    timeline: dict[str, Any]
    risks: list[str]
    cost_estimate: dict[str, Any]
    deployment_targets: list[str]


class LaunchResponse(BaseModel):
    """Response payload for launch request."""

    launch_id: str
    status: ProjectStatus
    message: str


class EventPayload(BaseModel):
    """Event payload for websocket and SSE updates."""

    event_id: str
    project_id: str
    event_type: str
    message: str
    timestamp: datetime
    reason: str | None = None
    artifact_url: str | None = None
