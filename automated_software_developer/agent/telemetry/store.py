"""Local telemetry warehouse backed by SQLite."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from automated_software_developer.agent.telemetry.events import TelemetryEvent, load_events
from automated_software_developer.agent.telemetry.policy import TelemetryPolicy

AUTOSD_TELEMETRY_DB_ENV = "AUTOSD_TELEMETRY_DB"


@dataclass(frozen=True)
class TelemetryReport:
    """Aggregated telemetry report for one project."""

    project_id: str
    event_count: int
    error_events: int
    crash_events: int
    avg_value: float

    def to_dict(self) -> dict[str, object]:
        """Serialize report to JSON dictionary."""
        return {
            "project_id": self.project_id,
            "event_count": self.event_count,
            "error_events": self.error_events,
            "crash_events": self.crash_events,
            "avg_value": self.avg_value,
        }


class TelemetryStore:
    """SQLite-backed telemetry store for local analytics and retention."""

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize telemetry DB path and ensure schema is present."""
        self.db_path = (db_path or _default_db_path()).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def ingest_events_file(
        self,
        *,
        project_id: str,
        events_path: Path,
        policy: TelemetryPolicy,
    ) -> int:
        """Ingest validated telemetry events from project JSONL file."""
        events = load_events(events_path, policy)
        if not events:
            return 0
        inserted = 0
        with sqlite3.connect(self.db_path) as connection:
            for event in events:
                inserted += self._insert_event(connection, project_id=project_id, event=event)
            connection.commit()
        return inserted

    def report_project(self, project_id: str) -> TelemetryReport:
        """Build aggregate report for one project."""
        with sqlite3.connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                SELECT
                    COUNT(*) AS event_count,
                    SUM(CASE WHEN event_type = 'error_count' THEN 1 ELSE 0 END) AS error_events,
                    SUM(CASE WHEN event_type = 'crash_count' THEN 1 ELSE 0 END) AS crash_events,
                    COALESCE(AVG(value), 0.0) AS avg_value
                FROM telemetry_events
                WHERE project_id = ?
                """,
                (project_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return TelemetryReport(
                project_id=project_id,
                event_count=0,
                error_events=0,
                crash_events=0,
                avg_value=0.0,
            )
        return TelemetryReport(
            project_id=project_id,
            event_count=int(row[0] or 0),
            error_events=int(row[1] or 0),
            crash_events=int(row[2] or 0),
            avg_value=float(row[3] or 0.0),
        )

    def report_all(self) -> list[TelemetryReport]:
        """Build aggregate report for all projects in store."""
        reports: list[TelemetryReport] = []
        with sqlite3.connect(self.db_path) as connection:
            cursor = connection.execute(
                "SELECT DISTINCT project_id FROM telemetry_events ORDER BY project_id"
            )
            project_ids = [str(row[0]) for row in cursor.fetchall()]
        for project_id in project_ids:
            reports.append(self.report_project(project_id))
        return reports

    def enforce_retention(self, retention_days: int) -> int:
        """Delete events older than retention period and return deleted row count."""
        if retention_days <= 0:
            raise ValueError("retention_days must be greater than zero.")
        threshold = datetime.now(tz=UTC) - timedelta(days=retention_days)
        threshold_iso = threshold.isoformat()
        with sqlite3.connect(self.db_path) as connection:
            cursor = connection.execute(
                "DELETE FROM telemetry_events WHERE timestamp < ?",
                (threshold_iso,),
            )
            connection.commit()
            return int(cursor.rowcount)

    def _ensure_schema(self) -> None:
        """Ensure telemetry table schema exists."""
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS telemetry_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    value REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    platform TEXT,
                    metadata_json TEXT NOT NULL,
                    UNIQUE(project_id, event_type, metric_name, timestamp, metadata_json)
                )
                """
            )
            connection.commit()

    def _insert_event(
        self,
        connection: sqlite3.Connection,
        *,
        project_id: str,
        event: TelemetryEvent,
    ) -> int:
        """Insert one event idempotently; return 1 if inserted else 0."""
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO telemetry_events (
                project_id,
                event_type,
                metric_name,
                value,
                timestamp,
                platform,
                metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                event.event_type,
                event.metric_name,
                event.value,
                event.timestamp,
                event.platform,
                str(sorted(event.metadata.items())),
            ),
        )
        return int(cursor.rowcount)


def _default_db_path() -> Path:
    """Resolve default telemetry DB path."""
    env_value = os.environ.get(AUTOSD_TELEMETRY_DB_ENV)
    if env_value:
        return Path(env_value)
    return Path.home() / ".autosd" / "telemetry.db"
