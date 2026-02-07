"""Metrics tracking for autonomous Scrum cycles."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MetricsSnapshot:
    """Snapshot of metrics to support sprint planning decisions."""

    velocity_history: list[int]
    cycle_time_history: list[float]
    lead_time_history: list[float]
    defect_rate_history: list[float]
    failed_deployments: int
    incident_count: int
    rollback_count: int


@dataclass
class MetricsStore:
    """Persistence layer for Scrum metrics."""

    path: Path
    payload: dict[str, Any] = field(default_factory=dict)

    def load(self) -> None:
        """Load metrics file if present, else initialize defaults."""
        if self.path.exists():
            self.payload = _read_json(self.path)
            return
        self.payload = _default_payload()

    def snapshot(self) -> MetricsSnapshot:
        """Return a snapshot of current metrics."""
        data = self.payload or _default_payload()
        return MetricsSnapshot(
            velocity_history=list(data.get("velocity_history", [])),
            cycle_time_history=list(data.get("cycle_time_history", [])),
            lead_time_history=list(data.get("lead_time_history", [])),
            defect_rate_history=list(data.get("defect_rate_history", [])),
            failed_deployments=int(data.get("failed_deployments", 0)),
            incident_count=int(data.get("incident_count", 0)),
            rollback_count=int(data.get("rollback_count", 0)),
        )

    def record_sprint(self, *, velocity: int, cycle_time: float, lead_time: float) -> None:
        """Record sprint-level metrics."""
        if velocity < 0:
            raise ValueError("velocity must be non-negative.")
        if cycle_time < 0 or lead_time < 0:
            raise ValueError("cycle_time and lead_time must be non-negative.")
        self.payload.setdefault("velocity_history", []).insert(0, velocity)
        self.payload.setdefault("cycle_time_history", []).insert(0, cycle_time)
        self.payload.setdefault("lead_time_history", []).insert(0, lead_time)
        self.payload["updated_at"] = datetime.now(tz=UTC).isoformat()

    def record_quality_events(
        self,
        *,
        defect_rate: float | None = None,
        failed_deployments: int | None = None,
        incident_count: int | None = None,
        rollback_count: int | None = None,
    ) -> None:
        """Record quality and reliability events."""
        if defect_rate is not None:
            if defect_rate < 0:
                raise ValueError("defect_rate must be non-negative.")
            self.payload.setdefault("defect_rate_history", []).insert(0, defect_rate)
        if failed_deployments is not None:
            if failed_deployments < 0:
                raise ValueError("failed_deployments must be non-negative.")
            self.payload["failed_deployments"] = failed_deployments
        if incident_count is not None:
            if incident_count < 0:
                raise ValueError("incident_count must be non-negative.")
            self.payload["incident_count"] = incident_count
        if rollback_count is not None:
            if rollback_count < 0:
                raise ValueError("rollback_count must be non-negative.")
            self.payload["rollback_count"] = rollback_count

    def save(self) -> None:
        """Persist metrics to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(_to_json(self.payload), encoding="utf-8")


def _default_payload() -> dict[str, Any]:
    return {
        "velocity_history": [],
        "cycle_time_history": [],
        "lead_time_history": [],
        "defect_rate_history": [],
        "failed_deployments": 0,
        "incident_count": 0,
        "rollback_count": 0,
        "updated_at": datetime.now(tz=UTC).isoformat(),
    }


def _read_json(path: Path) -> dict[str, Any]:
    data = path.read_text(encoding="utf-8")
    return _safe_json_loads(data)


def _safe_json_loads(raw: str) -> dict[str, Any]:
    import json

    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Metrics payload must be a JSON object.")
    return parsed


def _to_json(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
