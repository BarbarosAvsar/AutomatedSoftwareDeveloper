"""Telemetry event schema validation and JSONL persistence."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from automated_software_developer.agent.security import redact_sensitive_text
from automated_software_developer.agent.telemetry.policy import TelemetryPolicy

TELEMETRY_EVENT_SCHEMA: dict[str, Any] = {
    "title": "TelemetryEvent",
    "type": "object",
    "required": ["event_type", "timestamp", "metric_name", "value", "project_id"],
    "properties": {
        "event_type": {"type": "string", "minLength": 1},
        "timestamp": {"type": "string", "format": "date-time"},
        "metric_name": {"type": "string", "minLength": 1},
        "value": {"type": "number"},
        "project_id": {"type": "string", "minLength": 1},
        "platform": {"type": "string"},
        "metadata": {
            "type": "object",
            "additionalProperties": {"type": "string"},
        },
    },
}

PII_PATTERNS = (
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    re.compile(r"\b[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b", re.I),
)

ALLOWED_METADATA_KEYS = {
    "status",
    "bucket",
    "environment",
    "platform",
}


@dataclass(frozen=True)
class TelemetryEvent:
    """Validated, privacy-safe telemetry event."""

    event_type: str
    timestamp: str
    metric_name: str
    value: float
    project_id: str
    platform: str | None
    metadata: dict[str, str]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any], policy: TelemetryPolicy) -> TelemetryEvent:
        """Validate and build telemetry event according to policy and privacy rules."""
        if policy.mode == "off":
            raise ValueError("Telemetry policy mode is off; event ingestion is disabled.")

        event_type = _require_string(payload.get("event_type"), "event_type")
        if event_type not in policy.event_allowlist:
            raise ValueError(f"Event '{event_type}' is not allowed by telemetry policy.")

        timestamp = _require_string(payload.get("timestamp"), "timestamp")
        metric_name = _require_string(payload.get("metric_name"), "metric_name")
        value_raw = payload.get("value")
        if not isinstance(value_raw, (int, float)):
            raise ValueError("Expected 'value' to be numeric.")
        project_id = _require_string(payload.get("project_id"), "project_id")

        platform_raw = payload.get("platform")
        platform = _require_string(platform_raw, "platform") if platform_raw is not None else None

        metadata_raw = payload.get("metadata")
        metadata: dict[str, str] = {}
        if metadata_raw is not None:
            if not isinstance(metadata_raw, Mapping):
                raise ValueError("Expected 'metadata' to be an object when provided.")
            for key, raw_value in metadata_raw.items():
                normalized_key = _require_string(key, "metadata key")
                if normalized_key not in ALLOWED_METADATA_KEYS:
                    raise ValueError(f"Metadata key '{normalized_key}' is not allowed.")
                metadata[normalized_key] = _require_string(raw_value, f"metadata[{normalized_key}]")

        _reject_pii(
            [event_type, timestamp, metric_name, project_id, platform or "", *metadata.values()]
        )

        return cls(
            event_type=event_type,
            timestamp=timestamp,
            metric_name=metric_name,
            value=float(value_raw),
            project_id=project_id,
            platform=platform,
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize telemetry event to JSON-safe dictionary."""
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "metric_name": self.metric_name,
            "value": self.value,
            "project_id": self.project_id,
            "platform": self.platform,
            "metadata": self.metadata,
        }


def append_event(path: Path, event: TelemetryEvent) -> None:
    """Append one validated telemetry event to JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sanitized = _sanitize(event.to_dict())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(sanitized, ensure_ascii=True))
        handle.write("\n")


def load_events(path: Path, policy: TelemetryPolicy) -> list[TelemetryEvent]:
    """Load and validate telemetry events from JSONL file."""
    events: list[TelemetryEvent] = []
    if not path.exists() or not path.is_file():
        return events
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        try:
            events.append(TelemetryEvent.from_dict(payload, policy))
        except ValueError:
            continue
    return events


def _require_string(value: Any, field_name: str) -> str:
    """Validate non-empty string value."""
    if not isinstance(value, str):
        raise ValueError(f"Expected '{field_name}' to be a string.")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"Expected '{field_name}' to be non-empty.")
    return cleaned


def _reject_pii(values: list[str]) -> None:
    """Reject telemetry values containing likely PII."""
    for value in values:
        for pattern in PII_PATTERNS:
            if pattern.search(value):
                raise ValueError("Telemetry payload contains prohibited PII-like content.")


def _sanitize(payload: dict[str, object]) -> dict[str, object]:
    """Recursively redact sensitive text in telemetry payload."""
    output: dict[str, object] = {}
    for key, value in payload.items():
        if isinstance(value, str):
            output[key] = redact_sensitive_text(value)
        elif isinstance(value, dict):
            output[key] = {
                str(child_key): redact_sensitive_text(str(child_value))
                for child_key, child_value in value.items()
            }
        else:
            output[key] = value
    return output
