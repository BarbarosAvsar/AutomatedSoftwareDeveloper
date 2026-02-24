"""CLI tests for readiness doctor command."""

from __future__ import annotations

from typer.testing import CliRunner

from automated_software_developer.cli import app


def test_doctor_allows_missing_openai_key_when_optional(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["doctor", "--skip-security", "--allow-missing-openai-key"],
    )
    assert result.exit_code == 0
    assert "Doctor status: PASS" in result.stdout


def test_doctor_requires_openai_key_when_requested(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["doctor", "--skip-security", "--require-openai-key"],
    )
    assert result.exit_code == 1
    assert "OPENAI_API_KEY" in result.stdout
