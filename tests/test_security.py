"""Security-focused unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from automated_software_developer.agent.security import (
    SecurityError,
    ensure_safe_relative_path,
    find_potential_secrets,
    is_command_safe,
    redact_sensitive_text,
    scan_workspace_for_secrets,
)


def test_ensure_safe_relative_path_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(SecurityError):
        ensure_safe_relative_path(tmp_path, "../outside.txt")


def test_ensure_safe_relative_path_accepts_child(tmp_path: Path) -> None:
    resolved = ensure_safe_relative_path(tmp_path, "src/main.py")
    assert resolved.parent == tmp_path / "src"


def test_command_safety_blocks_destructive_sequences() -> None:
    assert not is_command_safe("rm -rf /")
    assert not is_command_safe("Remove-Item C:\\ -Recurse -Force")
    assert is_command_safe("python -m pytest -q")


def test_secret_pattern_detection() -> None:
    findings = find_potential_secrets("token = 'sk-ABCDEF123456789012345678'")
    assert "openai_api_key" in findings


def test_workspace_secret_scan(tmp_path: Path) -> None:
    secrets_file = tmp_path / "src" / "config.py"
    secrets_file.parent.mkdir(parents=True)
    secrets_file.write_text("API_KEY='ghp_abcdefghijklmnopqrstuvwxyz1234'", encoding="utf-8")
    findings = scan_workspace_for_secrets(tmp_path)
    assert any("github_token" in item for item in findings)


def test_redact_sensitive_text_covers_bearer_jwt_and_basic_auth_url() -> None:
    sample = (
        "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456\n"
        "token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature\n"
        "https://user:supersecret@example.com/path"
    )
    redacted = redact_sensitive_text(sample)
    assert "supersecret" not in redacted
    assert "abcdefghijklmnopqrstuvwxyz123456" not in redacted
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature" not in redacted
