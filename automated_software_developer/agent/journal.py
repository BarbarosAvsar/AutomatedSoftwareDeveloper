"""Prompt/result journaling with strict redaction safeguards."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from automated_software_developer.agent.security import (
    is_probably_sensitive_key,
    redact_sensitive_text,
)

MAX_STRING_LENGTH = 8_000
MAX_LIST_ITEMS = 200


def hash_text(text: str) -> str:
    """Create a stable SHA-256 hash for prompt/response fingerprints."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PromptJournal:
    """Append-only JSONL journal with recursive secret redaction."""

    def __init__(self, path: Path) -> None:
        """Initialize prompt journal at path and ensure parent directory exists."""
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry: Mapping[str, Any]) -> None:
        """Append a redacted JSONL journal record."""
        sanitized = self._sanitize_mapping(entry)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(sanitized, ensure_ascii=True))
            handle.write("\n")

    @staticmethod
    def load_entries(paths: list[Path]) -> list[dict[str, Any]]:
        """Load JSONL journal entries from one or more files."""
        entries: list[dict[str, Any]] = []
        for path in paths:
            if not path.exists() or not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    entries.append(parsed)
        return entries

    def _sanitize_mapping(self, value: Mapping[str, Any]) -> dict[str, Any]:
        """Recursively sanitize dictionary values and redact sensitive keys."""
        output: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if is_probably_sensitive_key(key_text):
                output[key_text] = "[REDACTED:key]"
                continue
            output[key_text] = self._sanitize_value(item)
        return output

    def _sanitize_value(self, value: Any) -> Any:
        """Recursively sanitize scalars, lists, and mappings."""
        if isinstance(value, Mapping):
            return self._sanitize_mapping(value)
        if isinstance(value, list):
            return [self._sanitize_value(item) for item in value[:MAX_LIST_ITEMS]]
        if isinstance(value, str):
            cleaned = redact_sensitive_text(value)
            if len(cleaned) > MAX_STRING_LENGTH:
                cleaned = cleaned[:MAX_STRING_LENGTH] + "...<truncated>..."
            return cleaned
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        return redact_sensitive_text(str(value))
