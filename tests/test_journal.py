"""Tests for prompt journal redaction behavior."""

from __future__ import annotations

import json
from pathlib import Path

from automated_software_developer.agent.journal import PromptJournal


def test_prompt_journal_redacts_secrets(tmp_path: Path) -> None:
    journal = PromptJournal(tmp_path / "prompt_journal.jsonl")
    journal.append(
        {
            "template_id": "story-implementation",
            "prompt": "token='ghp_abcdefghijklmnopqrstuvwxyz1234'",
            "api_key": "sk-123456789012345678901234",
            "metadata": {
                "OPENAI_API_KEY": "sk-aaaaaaaaaaaaaaaaaaaaaaaaa",
                "note": "safe note",
            },
        }
    )

    record = json.loads((tmp_path / "prompt_journal.jsonl").read_text(encoding="utf-8").strip())
    serialized = json.dumps(record)
    assert "ghp_abcdefghijklmnopqrstuvwxyz1234" not in serialized
    assert "sk-123456789012345678901234" not in serialized
    assert record["api_key"] == "[REDACTED:key]"
    assert record["metadata"]["OPENAI_API_KEY"] == "[REDACTED:key]"
