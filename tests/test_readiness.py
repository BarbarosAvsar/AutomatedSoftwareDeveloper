"""Tests for readiness helpers and strict preflight checks."""

from __future__ import annotations

from automated_software_developer.agent.readiness import (
    generator_gate_commands,
    strict_readiness_issues,
)


def test_strict_readiness_reports_missing_openai_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "automated_software_developer.agent.readiness.module_available",
        lambda module_name: True,
    )
    issues = strict_readiness_issues(
        provider="openai",
        quality_gates=False,
        enable_security_scan=False,
        security_scan_mode="off",
    )
    assert any("OPENAI_API_KEY" in issue for issue in issues)


def test_strict_readiness_reports_missing_quality_tools(monkeypatch) -> None:
    monkeypatch.setattr(
        "automated_software_developer.agent.readiness.module_available",
        lambda module_name: module_name != "ruff",
    )
    issues = strict_readiness_issues(
        provider="mock",
        quality_gates=True,
        enable_security_scan=False,
        security_scan_mode="off",
    )
    assert any("ruff" in issue for issue in issues)


def test_generator_gate_commands_use_custom_python() -> None:
    commands = generator_gate_commands(python_executable="python-custom")
    assert commands[0][0] == "python-custom"
    assert commands[1][2] == "mypy"
    assert commands[2][2] == "pytest"
