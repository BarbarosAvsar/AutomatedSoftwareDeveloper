"""Structured reporting helpers for conformance suite execution."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GateResult:
    """Outcome of a single conformance gate."""

    name: str
    passed: bool
    command: str | None = None
    exit_code: int | None = None
    duration_seconds: float = 0.0
    stdout: str = ""
    stderr: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the gate result as JSON-ready dict."""
        return {
            "name": self.name,
            "passed": self.passed,
            "command": self.command,
            "exit_code": self.exit_code,
            "duration_seconds": round(self.duration_seconds, 4),
            "stdout": self.stdout,
            "stderr": self.stderr,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class DiffResult:
    """Diff check outcome for reproducibility validation."""

    matched: bool
    differences: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the diff result as JSON-ready dict."""
        return {
            "matched": self.matched,
            "differences": self.differences,
        }


@dataclass(frozen=True)
class FixtureResult:
    """Aggregate outcome for a single fixture."""

    fixture_id: str
    adapter_id: str
    output_dir: str
    gates: list[GateResult]
    diff: DiffResult | None = None

    @property
    def passed(self) -> bool:
        """Return whether every gate passed."""
        return all(gate.passed for gate in self.gates) and (self.diff is None or self.diff.matched)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the fixture result as JSON-ready dict."""
        payload = {
            "fixture_id": self.fixture_id,
            "adapter_id": self.adapter_id,
            "output_dir": self.output_dir,
            "passed": self.passed,
            "gates": [gate.to_dict() for gate in self.gates],
        }
        if self.diff is not None:
            payload["diff"] = self.diff.to_dict()
        return payload


@dataclass(frozen=True)
class ConformanceReport:
    """Top-level conformance suite report structure."""

    started_at: str
    finished_at: str
    duration_seconds: float
    fixtures: list[FixtureResult]

    @property
    def passed(self) -> bool:
        """Return whether every fixture passed."""
        return all(fixture.passed for fixture in self.fixtures)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report as JSON-ready dict."""
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": round(self.duration_seconds, 4),
            "passed": self.passed,
            "fixtures": [fixture.to_dict() for fixture in self.fixtures],
        }

    def write(self, path: Path) -> None:
        """Write report JSON to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def start(cls) -> tuple[ConformanceReportBuilder, str]:
        """Create a report builder and timestamp."""
        started_at = datetime.now(tz=UTC).isoformat()
        return ConformanceReportBuilder(started_at=started_at), started_at


@dataclass
class ConformanceReportBuilder:
    """Mutable builder for assembling conformance reports."""

    started_at: str
    fixtures: list[FixtureResult] = field(default_factory=list)

    def finish(self) -> ConformanceReport:
        """Finalize report with a completion timestamp."""
        finished_at = datetime.now(tz=UTC).isoformat()
        duration = _duration_seconds(self.started_at, finished_at)
        return ConformanceReport(
            started_at=self.started_at,
            finished_at=finished_at,
            duration_seconds=duration,
            fixtures=self.fixtures,
        )


def validate_report_payload(payload: dict[str, Any]) -> None:
    """Validate minimal report schema for tests."""
    required_top = {"started_at", "finished_at", "duration_seconds", "passed", "fixtures"}
    missing = required_top - set(payload)
    if missing:
        raise ValueError(f"Conformance report missing keys: {sorted(missing)}")
    if not isinstance(payload["fixtures"], list):
        raise ValueError("fixtures must be a list.")
    for fixture in payload["fixtures"]:
        for key in ("fixture_id", "adapter_id", "output_dir", "passed", "gates"):
            if key not in fixture:
                raise ValueError(f"fixture missing key: {key}")


def _duration_seconds(started_at: str, finished_at: str) -> float:
    """Compute duration in seconds between two ISO timestamps."""
    start_dt = datetime.fromisoformat(started_at)
    end_dt = datetime.fromisoformat(finished_at)
    return (end_dt - start_dt).total_seconds()
