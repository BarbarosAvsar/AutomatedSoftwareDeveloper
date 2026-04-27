"""Tests for AutoSD Control Center request handling."""

from __future__ import annotations

from pathlib import Path

from automated_software_developer.agent.control_center import (
    ControlCenterState,
    OperationRecord,
    RunRecord,
    resolve_control_center_request,
)


def _provider_factory(*_args: object) -> object:
    raise AssertionError("provider factory should not run in request-resolution unit tests")


def test_onboarding_endpoint_returns_expected_defaults(tmp_path: Path) -> None:
    state = ControlCenterState(provider_factory=_provider_factory)
    status, payload = resolve_control_center_request(
        state=state,
        method="GET",
        raw_path="/api/onboarding",
        body=None,
        log_file=tmp_path / "autosd.log",
    )
    assert status == 200
    assert payload["telemetry_default"] == "off"


def test_runs_listing_filters_by_status(tmp_path: Path) -> None:
    state = ControlCenterState(provider_factory=_provider_factory)
    state.runs["a"] = RunRecord(
        run_id="a",
        created_at="2026-01-01T00:00:00+00:00",
        output_dir="one",
        execution_mode="direct",
        provider="mock",
        status="completed",
    )
    state.runs["b"] = RunRecord(
        run_id="b",
        created_at="2026-01-02T00:00:00+00:00",
        output_dir="two",
        execution_mode="planning",
        provider="mock",
        status="failed",
    )
    status, payload = resolve_control_center_request(
        state=state,
        method="GET",
        raw_path="/api/runs?status=failed",
        body=None,
        log_file=tmp_path / "autosd.log",
    )
    assert status == 200
    assert len(payload["runs"]) == 1
    assert payload["runs"][0]["run_id"] == "b"


def test_operations_listing_returns_recent_records(tmp_path: Path) -> None:
    state = ControlCenterState(provider_factory=_provider_factory)
    state.add_operation(
        OperationRecord(
            operation_id="op1",
            command=["python", "-m", "automated_software_developer", "doctor"],
            created_at="2026-01-01T00:00:00+00:00",
            status="passed",
            exit_code=0,
            output_snippet="Doctor status: PASS",
        )
    )
    status, payload = resolve_control_center_request(
        state=state,
        method="GET",
        raw_path="/api/operations",
        body=None,
        log_file=tmp_path / "autosd.log",
    )
    assert status == 200
    assert payload["operations"][0]["operation_id"] == "op1"
