"""Schema-first artifact definitions and lightweight validators."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from automated_software_developer.agent.incidents.model import (
    INCIDENT_SCHEMA as INCIDENT_SCHEMA_REFERENCE,
)
from automated_software_developer.agent.policy.engine import (
    POLICY_SNAPSHOT_SCHEMA as POLICY_SNAPSHOT_SCHEMA_REFERENCE,
)
from automated_software_developer.agent.portfolio.schemas import (
    REGISTRY_ENTRY_SCHEMA as REGISTRY_ENTRY_SCHEMA_REFERENCE,
)
from automated_software_developer.agent.telemetry.events import (
    TELEMETRY_EVENT_SCHEMA as TELEMETRY_EVENT_SCHEMA_REFERENCE,
)

BACKLOG_SCHEMA: dict[str, Any] = {
    "title": "StoryBacklog",
    "type": "object",
    "required": ["project_name", "stories", "global_verification_commands"],
}

SPRINT_LOG_EVENT_SCHEMA: dict[str, Any] = {
    "title": "SprintLogEvent",
    "type": "object",
    "required": ["timestamp", "sprint_index", "story_id", "event"],
}

REGISTRY_ENTRY_SCHEMA: dict[str, Any] = dict(REGISTRY_ENTRY_SCHEMA_REFERENCE)
TELEMETRY_EVENT_SCHEMA: dict[str, Any] = dict(TELEMETRY_EVENT_SCHEMA_REFERENCE)
INCIDENT_SCHEMA: dict[str, Any] = dict(INCIDENT_SCHEMA_REFERENCE)
POLICY_SNAPSHOT_SCHEMA: dict[str, Any] = dict(POLICY_SNAPSHOT_SCHEMA_REFERENCE)


def validate_backlog_payload(payload: Mapping[str, Any]) -> None:
    """Validate required top-level fields for backlog artifact."""
    for field in BACKLOG_SCHEMA["required"]:
        if field not in payload:
            raise ValueError(f"Backlog payload missing required field: {field}")
    stories = payload.get("stories")
    if not isinstance(stories, list) or not stories:
        raise ValueError("Backlog payload requires a non-empty 'stories' list.")


def validate_sprint_log_event(payload: Mapping[str, Any]) -> None:
    """Validate required fields for sprint log jsonl event."""
    for field in SPRINT_LOG_EVENT_SCHEMA["required"]:
        if field not in payload:
            raise ValueError(f"Sprint log event missing required field: {field}")
