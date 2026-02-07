"""Progress tracking and ETA estimation for autonomous runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from automated_software_developer.agent.pipeline.schema import generator_progress_definition


@dataclass(frozen=True)
class PhaseStep:
    """A sub-step within a progress phase."""

    name: str
    weight: float = 1.0


@dataclass(frozen=True)
class PhaseDefinition:
    """Definition of a progress phase."""

    name: str
    steps: tuple[PhaseStep, ...]
    weight: float = 1.0


@dataclass(frozen=True)
class EtaRange:
    """ETA range for remaining work expressed in days."""

    low_days: float
    most_likely_days: float
    high_days: float
    confidence: str

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable payload."""
        return {
            "low_days": self.low_days,
            "most_likely_days": self.most_likely_days,
            "high_days": self.high_days,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class ProgressSnapshot:
    """Snapshot of progress for serialization."""

    project_id: str
    timestamp: datetime
    phase: str
    percent_complete: float
    completed_steps: tuple[str, ...]
    story_points_completed: int
    story_points_total: int
    gates_passed: int
    eta_range: EtaRange | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable snapshot."""
        return {
            "project_id": self.project_id,
            "timestamp": self.timestamp.isoformat(),
            "phase": self.phase,
            "percent_complete": self.percent_complete,
            "completed_steps": list(self.completed_steps),
            "story_points_completed": self.story_points_completed,
            "story_points_total": self.story_points_total,
            "gates_passed": self.gates_passed,
            "eta_range": self.eta_range.to_dict() if self.eta_range else None,
        }


def default_phases() -> tuple[PhaseDefinition, ...]:
    """Return canonical phases and steps."""
    return tuple(
        PhaseDefinition(
            name=definition["name"],
            steps=tuple(PhaseStep(step) for step in definition["steps"]),
            weight=float(definition["weight"]),
        )
        for definition in generator_progress_definition()
    )


class ProgressTracker:
    """Tracks phase progress and persists snapshots."""

    def __init__(
        self,
        *,
        project_id: str,
        base_dir: Path,
        phases: tuple[PhaseDefinition, ...] | None = None,
    ) -> None:
        if not project_id.strip():
            raise ValueError("project_id must be non-empty.")
        self._project_id = project_id
        self._base_dir = base_dir
        self._phases = phases or default_phases()
        self._completed_steps: set[str] = set()
        self._current_phase = self._phases[0].name
        self._story_points_completed = 0
        self._story_points_total = 0
        self._gates_passed = 0
        self._last_snapshot: ProgressSnapshot | None = None

    @property
    def project_id(self) -> str:
        """Return project id."""
        return self._project_id

    def start_phase(self, phase_name: str) -> None:
        """Mark a phase as started."""
        self._ensure_phase_exists(phase_name)
        self._current_phase = phase_name

    def complete_step(self, phase_name: str, step_name: str) -> None:
        """Mark a phase step as completed."""
        self._ensure_phase_step_exists(phase_name, step_name)
        self._completed_steps.add(f"{phase_name}:{step_name}")

    def record_story_points(self, *, completed: int, total: int) -> None:
        """Record story point completion."""
        if completed < 0 or total < 0:
            raise ValueError("story points must be non-negative.")
        if completed > total:
            raise ValueError("completed story points cannot exceed total.")
        self._story_points_completed = completed
        self._story_points_total = total

    def record_gate_passed(self) -> None:
        """Increment the count of passed gates."""
        self._gates_passed += 1

    def snapshot(self) -> ProgressSnapshot:
        """Compute and return the latest progress snapshot."""
        percent = self._compute_percent_complete()
        eta_range = self._estimate_eta()
        snapshot = ProgressSnapshot(
            project_id=self._project_id,
            timestamp=datetime.now(UTC),
            phase=self._current_phase,
            percent_complete=percent,
            completed_steps=tuple(sorted(self._completed_steps)),
            story_points_completed=self._story_points_completed,
            story_points_total=self._story_points_total,
            gates_passed=self._gates_passed,
            eta_range=eta_range,
        )
        self._last_snapshot = snapshot
        return snapshot

    def save(self) -> ProgressSnapshot:
        """Persist progress snapshot to disk."""
        snapshot = self.snapshot()
        progress_dir = self._base_dir / ".autosd"
        progress_dir.mkdir(parents=True, exist_ok=True)
        progress_path = progress_dir / "progress.json"
        history_path = progress_dir / "progress_history.jsonl"
        progress_path.write_text(_to_json(snapshot.to_dict()), encoding="utf-8")
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(_to_json(snapshot.to_dict()))
            handle.write("\n")
        return snapshot

    def load_latest(self) -> ProgressSnapshot | None:
        """Load the latest snapshot from disk if available."""
        progress_path = self._base_dir / ".autosd" / "progress.json"
        if not progress_path.exists():
            return None
        payload = _from_json(progress_path.read_text(encoding="utf-8"))
        snapshot = ProgressSnapshot(
            project_id=payload["project_id"],
            timestamp=datetime.fromisoformat(payload["timestamp"]),
            phase=payload["phase"],
            percent_complete=float(payload["percent_complete"]),
            completed_steps=tuple(payload.get("completed_steps", [])),
            story_points_completed=int(payload.get("story_points_completed", 0)),
            story_points_total=int(payload.get("story_points_total", 0)),
            gates_passed=int(payload.get("gates_passed", 0)),
            eta_range=_eta_from_payload(payload.get("eta_range")),
        )
        self._last_snapshot = snapshot
        return snapshot

    def _estimate_eta(self) -> EtaRange | None:
        remaining = max(self._story_points_total - self._story_points_completed, 0)
        if remaining == 0 or self._story_points_total == 0:
            return None
        velocity = max(self._story_points_completed, 1) / max(len(self._completed_steps), 1)
        days = remaining / max(velocity, 0.25)
        low = max(days * 0.5, 0.5)
        high = max(days * 2.0, low + 0.5)
        confidence = "medium"
        if self._story_points_completed == 0:
            confidence = "low"
        elif self._story_points_completed > self._story_points_total * 0.6:
            confidence = "high"
        return EtaRange(
            low_days=round(low, 2),
            most_likely_days=round(days, 2),
            high_days=round(high, 2),
            confidence=confidence,
        )

    def _compute_percent_complete(self) -> float:
        total_weight = sum(phase.weight for phase in self._phases)
        completed_weight = 0.0
        for phase in self._phases:
            phase_steps = phase.steps
            if not phase_steps:
                continue
            phase_total = sum(step.weight for step in phase_steps)
            phase_completed = 0.0
            for step in phase_steps:
                if f"{phase.name}:{step.name}" in self._completed_steps:
                    phase_completed += step.weight
            phase_ratio = phase_completed / phase_total if phase_total else 0.0
            completed_weight += phase.weight * phase_ratio
        percent = (completed_weight / total_weight) * 100 if total_weight else 0.0
        return round(percent, 2)

    def _ensure_phase_exists(self, phase_name: str) -> None:
        if phase_name not in {phase.name for phase in self._phases}:
            raise ValueError(f"Unknown phase: {phase_name}")

    def _ensure_phase_step_exists(self, phase_name: str, step_name: str) -> None:
        self._ensure_phase_exists(phase_name)
        phase = next(phase for phase in self._phases if phase.name == phase_name)
        if step_name not in {step.name for step in phase.steps}:
            raise ValueError(f"Unknown step: {step_name} for phase {phase_name}")


def _eta_from_payload(payload: dict[str, Any] | None) -> EtaRange | None:
    if not payload:
        return None
    return EtaRange(
        low_days=float(payload["low_days"]),
        most_likely_days=float(payload["most_likely_days"]),
        high_days=float(payload["high_days"]),
        confidence=str(payload["confidence"]),
    )


def _to_json(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, sort_keys=True)


def _from_json(text: str) -> dict[str, Any]:
    import json

    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("progress payload must be a JSON object.")
    return data
