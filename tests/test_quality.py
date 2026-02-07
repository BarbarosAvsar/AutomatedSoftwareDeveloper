"""Tests for generated-project quality and static validation gates."""

from __future__ import annotations

from pathlib import Path

from automated_software_developer.agent.quality import (
    build_quality_gate_plan,
    evaluate_python_quality,
)


def test_quality_plan_includes_readme_check_even_without_python(tmp_path: Path) -> None:
    plan = build_quality_gate_plan(
        tmp_path,
        enforce_quality_gates=True,
        enable_security_scan=False,
        security_scan_mode="off",
    )
    assert "README.md" in " ".join(plan.verification_commands)


def test_quality_plan_includes_python_commands_for_python_project(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    plan = build_quality_gate_plan(
        tmp_path,
        enforce_quality_gates=True,
        enable_security_scan=False,
        security_scan_mode="if-available",
    )
    commands = " | ".join(plan.verification_commands + plan.format_commands)
    assert "compileall" in commands


def test_quality_static_detects_missing_docstrings_and_syntax_error(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("def missing():\n    return 1\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def broken(\n", encoding="utf-8")
    result = evaluate_python_quality(tmp_path, enforce_docstrings=True)
    assert result.syntax_errors
    assert any("missing" in item for item in result.docstring_violations)


def test_quality_static_passes_when_docstrings_present(tmp_path: Path) -> None:
    (tmp_path / "good.py").write_text(
        '"""Module docs."""\n\n'
        "def main() -> int:\n"
        '    """Return status code."""\n'
        "    return 0\n",
        encoding="utf-8",
    )
    result = evaluate_python_quality(tmp_path, enforce_docstrings=True)
    assert result.passed
