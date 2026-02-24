"""CLI tests for verify-factory provider/readiness options."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from automated_software_developer.agent.conformance.reporting import (
    ConformanceReport,
    FixtureResult,
    GateResult,
)
from automated_software_developer.cli import app
from automated_software_developer.commands import run_and_verify


def _stub_prereq_checks(monkeypatch) -> None:
    monkeypatch.setattr(run_and_verify, "lint_workflows", lambda _: [])
    monkeypatch.setattr(
        run_and_verify,
        "run_ci_mirror",
        lambda _: SimpleNamespace(passed=True, exit_code=0, duration_seconds=0.01),
    )


def test_verify_factory_openai_required_fails_without_key(tmp_path: Path, monkeypatch) -> None:
    _stub_prereq_checks(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    runner = CliRunner()
    report_path = tmp_path / "verify_factory_report.json"
    conformance_path = tmp_path / "conformance" / "report.json"
    result = runner.invoke(
        app,
        [
            "verify-factory",
            "--skip-generator-gates",
            "--conformance-provider",
            "openai",
            "--real-provider-required",
            "--verify-report-path",
            str(report_path),
            "--report-path",
            str(conformance_path),
        ],
    )
    assert result.exit_code == 1
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["real_provider"]["enabled"] is True
    assert any("OPENAI_API_KEY" in item for item in payload["real_provider"]["blocking_failures"])


def test_verify_factory_openai_advisory_skips_without_key(tmp_path: Path, monkeypatch) -> None:
    _stub_prereq_checks(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    runner = CliRunner()
    report_path = tmp_path / "verify_factory_report.json"
    conformance_path = tmp_path / "conformance" / "report.json"
    result = runner.invoke(
        app,
        [
            "verify-factory",
            "--skip-generator-gates",
            "--conformance-provider",
            "openai",
            "--real-provider-advisory",
            "--verify-report-path",
            str(report_path),
            "--report-path",
            str(conformance_path),
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["conformance"]["skipped"] is True
    assert payload["real_provider"]["required"] is False


def test_verify_factory_unknown_smoke_fixture_fails(tmp_path: Path, monkeypatch) -> None:
    _stub_prereq_checks(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        run_and_verify,
        "run_conformance_suite",
        lambda **_: ConformanceReport(
            started_at=datetime.now(tz=UTC).isoformat(),
            finished_at=datetime.now(tz=UTC).isoformat(),
            duration_seconds=0.01,
            fixtures=[
                FixtureResult(
                    fixture_id="cli_tool",
                    adapter_id="cli_tool",
                    output_dir="output",
                    gates=[GateResult(name="gate", passed=True)],
                )
            ],
        ),
    )
    runner = CliRunner()
    report_path = tmp_path / "verify_factory_report.json"
    conformance_path = tmp_path / "conformance" / "report.json"
    result = runner.invoke(
        app,
        [
            "verify-factory",
            "--skip-generator-gates",
            "--conformance-provider",
            "openai",
            "--smoke-fixtures",
            "unknown_fixture",
            "--verify-report-path",
            str(report_path),
            "--report-path",
            str(conformance_path),
        ],
    )
    assert result.exit_code == 2
    stderr_text = getattr(result, "stderr", "")
    assert "unknown_fixture" in f"{result.stdout}\n{stderr_text}"
