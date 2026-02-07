"""Voice input ingestion for requirements sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from automated_software_developer.agent.security import redact_sensitive_text


@dataclass(frozen=True)
class VoiceTranscript:
    """A normalized voice transcript payload."""

    session_id: str
    transcript: str
    captured_at: datetime


class VoiceInputHandler:
    """Normalizes and redacts voice transcripts before ingestion."""

    def __init__(self, *, allow_server_side: bool = False) -> None:
        self._allow_server_side = allow_server_side

    def ingest_transcript(self, *, session_id: str, transcript: str) -> VoiceTranscript:
        """Normalize a transcript and enforce opt-in for server-side processing."""
        if not session_id.strip():
            raise ValueError("session_id must be non-empty.")
        if not transcript.strip():
            raise ValueError("transcript must be non-empty.")
        if not self._allow_server_side:
            raise ValueError("Server-side transcription is disabled by default.")
        redacted = redact_sensitive_text(transcript.strip())
        return VoiceTranscript(
            session_id=session_id,
            transcript=redacted,
            captured_at=datetime.now(UTC),
        )
