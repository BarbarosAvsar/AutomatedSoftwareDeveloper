"""Module entrypoint for python -m automated_software_developer."""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import UTC, datetime

from automated_software_developer.cli import app


class JsonLogFormatter(logging.Formatter):
    """Format log records as JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize a log record in JSON format."""
        payload = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload)


class DummyTelemetry:
    """Local in-process telemetry counter with no external exporter."""

    def __init__(self) -> None:
        """Initialize local metric storage."""
        self._counters: Counter[str] = Counter()

    def increment(self, metric_name: str, amount: int = 1) -> None:
        """Increment a named counter metric."""
        self._counters[metric_name] += amount


TELEMETRY = DummyTelemetry()


def _configure_json_logging() -> None:
    """Configure root logger to use JSON formatter when module is invoked directly."""
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonLogFormatter())
        root.addHandler(handler)
        root.setLevel(logging.INFO)


if __name__ == "__main__":
    _configure_json_logging()
    app()
