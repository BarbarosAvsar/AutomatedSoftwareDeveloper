"""SQLite-backed session store for the AEC UI."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from automated_software_developer.agent.security import redact_sensitive_text


@dataclass(frozen=True)
class SessionRecord:
    """Session metadata."""

    session_id: str
    idea: str
    created_at: datetime


@dataclass(frozen=True)
class MessageRecord:
    """Session message record."""

    session_id: str
    role: str
    content: str
    created_at: datetime


class AECSessionStore:
    """Stores sessions and progress snapshots in a local SQLite database."""

    def __init__(self, *, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or Path.cwd() / ".autosd"
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._base_dir / "aec_sessions.sqlite"
        self._connection = sqlite3.connect(self._db_path, check_same_thread=False)
        self._init_schema()

    def create_session(self, idea: str, *, session_id: str | None = None) -> SessionRecord:
        """Create a new session for requirements ideation."""
        if not idea.strip():
            raise ValueError("idea must be non-empty.")
        session_id = session_id or uuid4().hex
        created_at = datetime.now(UTC)
        self._connection.execute(
            "INSERT INTO sessions (session_id, idea, created_at) VALUES (?, ?, ?)",
            (session_id, redact_sensitive_text(idea.strip()), created_at.isoformat()),
        )
        self._connection.commit()
        return SessionRecord(session_id=session_id, idea=idea.strip(), created_at=created_at)

    def add_message(self, session_id: str, role: str, content: str) -> MessageRecord:
        """Add a message to a session."""
        if not session_id.strip():
            raise ValueError("session_id must be non-empty.")
        if not role.strip():
            raise ValueError("role must be non-empty.")
        if not content.strip():
            raise ValueError("content must be non-empty.")
        created_at = datetime.now(UTC)
        redacted = redact_sensitive_text(content.strip())
        self._connection.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role.strip(), redacted, created_at.isoformat()),
        )
        self._connection.commit()
        return MessageRecord(
            session_id=session_id,
            role=role.strip(),
            content=redacted,
            created_at=created_at,
        )

    def list_messages(self, session_id: str) -> list[MessageRecord]:
        """Return all messages for a session."""
        cursor = self._connection.execute(
            "SELECT session_id, role, content, created_at FROM messages WHERE session_id = ?",
            (session_id,),
        )
        records = []
        for row in cursor.fetchall():
            records.append(
                MessageRecord(
                    session_id=row[0],
                    role=row[1],
                    content=row[2],
                    created_at=datetime.fromisoformat(row[3]),
                )
            )
        return records

    def save_progress_snapshot(self, project_id: str, snapshot: dict[str, object]) -> None:
        """Persist a progress snapshot for a project."""
        if not project_id.strip():
            raise ValueError("project_id must be non-empty.")
        payload = json.dumps(snapshot, sort_keys=True)
        created_at = datetime.now(UTC).isoformat()
        self._connection.execute(
            "INSERT INTO progress_snapshots (project_id, payload, created_at) VALUES (?, ?, ?)",
            (project_id, payload, created_at),
        )
        self._connection.commit()

    def latest_progress_snapshot(self, project_id: str) -> dict[str, object] | None:
        """Return the latest progress snapshot payload for a project."""
        cursor = self._connection.execute(
            "SELECT payload FROM progress_snapshots WHERE project_id = ? ORDER BY id DESC LIMIT 1",
            (project_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        payload = json.loads(row[0])
        if not isinstance(payload, dict):
            raise ValueError("progress snapshot payload is invalid.")
        return payload

    def _init_schema(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                idea TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS progress_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._connection.commit()
