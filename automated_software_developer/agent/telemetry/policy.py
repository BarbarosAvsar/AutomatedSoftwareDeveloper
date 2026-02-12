"""Telemetry policy definitions with privacy-preserving defaults."""

from __future__ import annotations

from dataclasses import dataclass

ALLOWED_MODES = {"off", "anonymous", "minimal", "custom"}

DEFAULT_EVENT_ALLOWLIST = {
    "performance_timing",
    "feature_usage",
    "error_count",
    "crash_count",
}


@dataclass(frozen=True)
class TelemetryPolicy:
    """Project telemetry policy resolved from mode and retention constraints."""

    mode: str
    retention_days: int
    event_allowlist: set[str]

    @classmethod
    def from_mode(
        cls,
        mode: str,
        *,
        retention_days: int = 30,
        custom_allowlist: set[str] | None = None,
    ) -> TelemetryPolicy:
        """Create telemetry policy from one of the supported modes."""
        normalized = mode.strip().lower()
        if normalized not in ALLOWED_MODES:
            allowed = ", ".join(sorted(ALLOWED_MODES))
            raise ValueError(f"Unsupported telemetry mode '{mode}'. Allowed: {allowed}")
        if retention_days <= 0:
            raise ValueError("retention_days must be greater than zero.")

        if normalized == "off":
            allowlist: set[str] = set()
        elif normalized == "anonymous":
            allowlist = set(DEFAULT_EVENT_ALLOWLIST)
        elif normalized == "minimal":
            allowlist = {"error_count", "crash_count"}
        else:
            allowlist = set(custom_allowlist or DEFAULT_EVENT_ALLOWLIST)
        return cls(mode=normalized, retention_days=retention_days, event_allowlist=allowlist)

    def to_dict(self) -> dict[str, object]:
        """Serialize telemetry policy for artifact output."""
        return {
            "mode": self.mode,
            "retention_days": self.retention_days,
            "event_allowlist": sorted(self.event_allowlist),
        }
