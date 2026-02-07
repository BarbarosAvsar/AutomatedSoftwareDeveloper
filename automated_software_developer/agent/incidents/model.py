"""Incident schema and persistence helpers for autonomous healing."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

INCIDENT_SCHEMA: dict[str, Any] = {
    "title": "IncidentRecord",
    "type": "object",
    "required": [
        "incident_id",
        "project_id",
        "created_at",
        "updated_at",
        "source",
        "severity",
        "status",
        "signal_summary",
    ],
    "properties": {
        "incident_id": {"type": "string", "minLength": 1},
        "project_id": {"type": "string", "minLength": 1},
        "created_at": {"type": "string", "format": "date-time"},
        "updated_at": {"type": "string", "format": "date-time"},
        "source": {"type": "string", "minLength": 1},
        "severity": {"type": "string", "minLength": 1},
        "status": {"type": "string", "minLength": 1},
        "signal_summary": {"type": "string", "minLength": 1},
        "proposed_fix": {"type": ["string", "null"]},
        "patch_success": {"type": ["boolean", "null"]},
        "deploy_success": {"type": ["boolean", "null"]},
        "postmortem_path": {"type": ["string", "null"]},
    },
}


@dataclass(frozen=True)
class IncidentRecord:
    """Canonical incident record used by healing pipeline."""

    incident_id: str
    project_id: str
    created_at: str
    updated_at: str
    source: str
    severity: str
    status: str
    signal_summary: str
    proposed_fix: str | None
    patch_success: bool | None
    deploy_success: bool | None
    postmortem_path: str | None

    @classmethod
    def create(
        cls,
        *,
        project_id: str,
        source: str,
        severity: str,
        signal_summary: str,
        proposed_fix: str | None,
    ) -> IncidentRecord:
        """Create a new incident record with generated id and timestamps."""
        timestamp = _utc_now()
        return cls(
            incident_id=str(uuid.uuid4()),
            project_id=project_id,
            created_at=timestamp,
            updated_at=timestamp,
            source=source,
            severity=severity,
            status="open",
            signal_summary=signal_summary,
            proposed_fix=proposed_fix,
            patch_success=None,
            deploy_success=None,
            postmortem_path=None,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> IncidentRecord:
        """Build incident record from untrusted payload."""
        return cls(
            incident_id=_require_string(payload.get("incident_id"), "incident_id"),
            project_id=_require_string(payload.get("project_id"), "project_id"),
            created_at=_require_string(payload.get("created_at"), "created_at"),
            updated_at=_require_string(payload.get("updated_at"), "updated_at"),
            source=_require_string(payload.get("source"), "source"),
            severity=_require_string(payload.get("severity"), "severity"),
            status=_require_string(payload.get("status"), "status"),
            signal_summary=_require_string(payload.get("signal_summary"), "signal_summary"),
            proposed_fix=_optional_string(payload.get("proposed_fix"), "proposed_fix"),
            patch_success=_optional_bool(payload.get("patch_success"), "patch_success"),
            deploy_success=_optional_bool(payload.get("deploy_success"), "deploy_success"),
            postmortem_path=_optional_string(payload.get("postmortem_path"), "postmortem_path"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize incident record as JSON dictionary."""
        return {
            "incident_id": self.incident_id,
            "project_id": self.project_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": self.source,
            "severity": self.severity,
            "status": self.status,
            "signal_summary": self.signal_summary,
            "proposed_fix": self.proposed_fix,
            "patch_success": self.patch_success,
            "deploy_success": self.deploy_success,
            "postmortem_path": self.postmortem_path,
        }


def append_incident(path: Path, record: IncidentRecord) -> None:
    """Append incident record to JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.to_dict(), ensure_ascii=True))
        handle.write("\n")


def load_incidents(path: Path) -> list[IncidentRecord]:
    """Load incident records from JSONL file in append order."""
    if not path.exists() or not path.is_file():
        return []
    records: list[IncidentRecord] = []
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
            records.append(IncidentRecord.from_dict(payload))
        except ValueError:
            continue
    return records


def _utc_now() -> str:
    """Return current UTC timestamp string."""
    return datetime.now(tz=UTC).isoformat()


def _require_string(value: object, field_name: str) -> str:
    """Validate non-empty string field."""
    if not isinstance(value, str):
        raise ValueError(f"Expected '{field_name}' to be a string.")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"Expected '{field_name}' to be non-empty.")
    return cleaned


def _optional_string(value: object, field_name: str) -> str | None:
    """Validate optional string field."""
    if value is None:
        return None
    return _require_string(value, field_name)


def _optional_bool(value: object, field_name: str) -> bool | None:
    """Validate optional boolean field."""
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f"Expected '{field_name}' to be a boolean when provided.")
    return value
