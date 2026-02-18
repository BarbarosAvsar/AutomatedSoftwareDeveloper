"""Tests for generated-project quality and static validation gates."""

from __future__ import annotations

from pathlib import Path

from automated_software_developer.agent.models import CommandResult
from automated_software_developer.agent.quality import (
    QualityGateCacheEntry,
    build_quality_gate_plan,
    compute_quality_gate_fingerprint,
    evaluate_python_quality,
    load_quality_gate_cache,
    save_quality_gate_cache,
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


def test_quality_plan_skips_coverage_without_pytest_targets(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    plan = build_quality_gate_plan(
        tmp_path,
        enforce_quality_gates=True,
        enable_security_scan=False,
        security_scan_mode="if-available",
    )
    commands = " | ".join(plan.verification_commands)
    assert "coverage run -m pytest" not in commands
    assert any("skipping coverage artifact generation" in item.lower() for item in plan.warnings)


def test_quality_plan_includes_coverage_with_pytest_targets(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_app.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    plan = build_quality_gate_plan(
        tmp_path,
        enforce_quality_gates=True,
        enable_security_scan=False,
        security_scan_mode="if-available",
    )
    commands = " | ".join(plan.verification_commands)
    if "coverage run -m pytest" in commands:
        assert "coverage xml -o .autosd/provenance/coverage.xml" in commands


def test_quality_static_detects_missing_docstrings_and_syntax_error(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("def missing():\n    return 1\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def broken(\n", encoding="utf-8")
    result = evaluate_python_quality(tmp_path, enforce_docstrings=True)
    assert result.syntax_errors
    assert any("missing" in item for item in result.docstring_violations)


def test_quality_static_passes_when_docstrings_present(tmp_path: Path) -> None:
    (tmp_path / "good.py").write_text(
        '"""Module docs."""\n\ndef main() -> int:\n    """Return status code."""\n    return 0\n',
        encoding="utf-8",
    )
    result = evaluate_python_quality(tmp_path, enforce_docstrings=True)
    assert result.passed


def test_quality_gate_cache_roundtrip(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    commands = ["python -m ruff check ."]
    config = {
        "enforce_quality_gates": True,
        "enable_security_scan": False,
        "security_scan_mode": "if-available",
        "enforce_docstrings": True,
    }
    fingerprint = compute_quality_gate_fingerprint(tmp_path, commands=commands, config=config)
    entry = QualityGateCacheEntry(
        fingerprint=fingerprint,
        commands=commands,
        results=[
            CommandResult(
                command=commands[0],
                exit_code=0,
                stdout="ok",
                stderr="",
                duration_seconds=0.1,
            )
        ],
    )
    save_quality_gate_cache(tmp_path, entry)
    loaded = load_quality_gate_cache(tmp_path)
    assert loaded is not None
    assert loaded.fingerprint == fingerprint
    assert loaded.commands == commands
    assert loaded.results[0].command == commands[0]


def test_quality_gate_fingerprint_changes_when_files_change(tmp_path: Path) -> None:
    file_path = tmp_path / "app.py"
    file_path.write_text("print('ok')\n", encoding="utf-8")
    commands = ["python -m ruff check ."]
    config = {
        "enforce_quality_gates": True,
        "enable_security_scan": False,
        "security_scan_mode": "if-available",
        "enforce_docstrings": True,
    }
    before = compute_quality_gate_fingerprint(tmp_path, commands=commands, config=config)
    file_path.write_text("print('changed')\n", encoding="utf-8")
    after = compute_quality_gate_fingerprint(tmp_path, commands=commands, config=config)
    assert before != after
