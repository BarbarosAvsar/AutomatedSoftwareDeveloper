"""Tests for schema-first validators and schema exports."""

from __future__ import annotations

import pytest

from automated_software_developer.agent.schemas import (
    BACKLOG_SCHEMA,
    INCIDENT_SCHEMA,
    POLICY_SNAPSHOT_SCHEMA,
    REGISTRY_ENTRY_SCHEMA,
    SPRINT_LOG_EVENT_SCHEMA,
    TELEMETRY_EVENT_SCHEMA,
    validate_backlog_payload,
    validate_sprint_log_event,
)


def test_schema_constants_exist() -> None:
    assert BACKLOG_SCHEMA["title"] == "StoryBacklog"
    assert SPRINT_LOG_EVENT_SCHEMA["title"] == "SprintLogEvent"
    assert REGISTRY_ENTRY_SCHEMA["title"] == "PortfolioRegistryEntry"
    assert TELEMETRY_EVENT_SCHEMA["title"] == "TelemetryEvent"
    assert INCIDENT_SCHEMA["title"] == "IncidentRecord"
    assert POLICY_SNAPSHOT_SCHEMA["title"] == "PolicySnapshot"


def test_backlog_validator_and_sprint_log_validator() -> None:
    valid_backlog = {
        "project_name": "demo",
        "stories": [{"id": "story-1"}],
        "global_verification_commands": ["python -m pytest"],
    }
    validate_backlog_payload(valid_backlog)

    with pytest.raises(ValueError):
        validate_backlog_payload({"project_name": "missing fields"})

    valid_event = {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "sprint_index": 1,
        "story_id": "story-1",
        "event": "story_started",
    }
    validate_sprint_log_event(valid_event)

    with pytest.raises(ValueError):
        validate_sprint_log_event({"event": "missing required"})
