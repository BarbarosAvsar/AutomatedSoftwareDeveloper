"""Audit logging for privileged autonomous actions."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from automated_software_developer.agent.security import redact_sensitive_text

AUTOSD_AUDIT_LOG_ENV = "AUTOSD_AUDIT_LOG"


class AuditLogger:
    """Append-only JSONL audit logger with redaction safeguards."""

    def __init__(self, path: Path | None = None) -> None:
        """Initialize audit log path and parent directories."""
        self.path = (path or _default_audit_path()).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        *,
        project_id: str,
        action: str,
        result: str,
        grant_id: str | None,
        gates_run: list[str],
        commit_ref: str | None,
        tag_ref: str | None,
        break_glass_used: bool,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Append one audit event record."""
        payload: dict[str, Any] = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "project_id": project_id,
            "action": action,
            "result": result,
            "grant_id": grant_id,
            "gates_run": gates_run,
            "commit_ref": commit_ref,
            "tag_ref": tag_ref,
            "break_glass_used": break_glass_used,
            "details": details or {},
        }
        sanitized = _sanitize(payload)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(sanitized, ensure_ascii=True))
            handle.write("\n")


def _default_audit_path() -> Path:
    """Resolve default audit log path from env or home directory."""
    env_value = os.environ.get(AUTOSD_AUDIT_LOG_ENV)
    if env_value:
        return Path(env_value)
    return Path.home() / ".autosd" / "audit.log.jsonl"


def _sanitize(value: Any) -> Any:
    """Recursively sanitize audit payload values."""
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _sanitize(item) for key, item in value.items()}
    return value
