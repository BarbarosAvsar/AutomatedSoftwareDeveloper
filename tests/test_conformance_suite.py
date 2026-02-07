"""Tests for the conformance suite runner and reporting."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from automated_software_developer.agent.conformance.fixtures import load_fixtures
from automated_software_developer.agent.conformance.reporting import (
    ConformanceReport,
    DiffResult,
    FixtureResult,
    GateResult,
    validate_report_payload,
)
from automated_software_developer.agent.conformance.runner import (
    ConformanceConfig,
    run_conformance_suite,
    validate_workflow,
)


def test_conformance_report_schema() -> None:
    report = ConformanceReport(
        started_at=datetime.now(tz=UTC).isoformat(),
        finished_at=datetime.now(tz=UTC).isoformat(),
        duration_seconds=0.01,
        fixtures=[
            FixtureResult(
                fixture_id="fixture",
                adapter_id="cli_tool",
                output_dir="output",
                gates=[GateResult(name="gate", passed=True)],
                diff=DiffResult(matched=True),
            )
        ],
    )
    payload = report.to_dict()
    validate_report_payload(payload)


def test_workflow_validation_invalid_yaml(tmp_path: Path) -> None:
    workflow = tmp_path / "ci.yml"
    workflow.write_text("name: CI\njobs: [", encoding="utf-8")
    errors = validate_workflow(workflow)
    assert errors


def test_conformance_integration_runs_fixture(tmp_path: Path) -> None:
    fixtures = [fixture for fixture in load_fixtures() if fixture.fixture_id == "cli_tool"]
    assert fixtures
    report = run_conformance_suite(
        fixtures=fixtures,
        config=ConformanceConfig(
            output_dir=tmp_path / "output",
            report_path=tmp_path / "report.json",
            max_workers=1,
            diff_check=False,
        ),
    )
    assert report.passed is True
    assert (tmp_path / "report.json").exists()
