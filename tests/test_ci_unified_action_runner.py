"""Tests for sequential CI unified action runner."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module(script_path: str):
    path = Path(script_path).resolve()
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load script module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_classify_log_level() -> None:
    script = _load_module("scripts/ci/run_unified_action.py")
    assert script.classify_log_level("INFO startup") == "info"
    assert script.classify_log_level("WARNING potential issue") == "warning"
    assert script.classify_log_level("ERROR command failed") == "error"
    assert script.classify_log_level("CRITICAL outage") == "critical"


def test_runner_continues_then_fails_and_writes_artifacts(tmp_path: Path) -> None:
    script = _load_module("scripts/ci/run_unified_action.py")
    events_path = tmp_path / "ci-unified-events.jsonl"
    summary_path = tmp_path / "ci-unified-summary.md"
    failed_jobs_path = tmp_path / "failed-jobs.json"
    ledger_path = tmp_path / ".autosd" / "ci" / "failure_ledger.jsonl"
    verify_report_path = tmp_path / "verify_factory_report.json"
    conformance_report_path = tmp_path / "conformance" / "report.json"
    stages = [
        script.StageConfig(
            name="stage_info",
            command=(sys.executable, "-c", "print('INFO warmup')"),
            blocking=True,
        ),
        script.StageConfig(
            name="stage_fail",
            command=(
                sys.executable,
                "-c",
                "import sys; print('WARNING pre-fail'); "
                "sys.stderr.write('ERROR fail now\\n'); raise SystemExit(2)",
            ),
            blocking=True,
        ),
        script.StageConfig(
            name="stage_after_fail",
            command=(sys.executable, "-c", "print('CRITICAL follow-up detail')"),
            blocking=True,
        ),
    ]
    exit_code = script.run_unified_action(
        events_path=events_path,
        summary_path=summary_path,
        failed_jobs_path=failed_jobs_path,
        ledger_path=ledger_path,
        verify_report_path=verify_report_path,
        conformance_report_path=conformance_report_path,
        stages=stages,
        update_dashboard=False,
    )
    assert exit_code == 1
    assert events_path.exists()
    assert summary_path.exists()
    assert failed_jobs_path.exists()
    assert ledger_path.exists()

    failed_jobs = json.loads(failed_jobs_path.read_text(encoding="utf-8"))
    assert failed_jobs == [{"job": "stage_fail", "result": "failure"}]
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    assert events
    for event in events:
        assert {"timestamp_utc", "level", "stage", "event_type", "message"}.issubset(event)
    assert any(item["event_type"] == "stage_start" for item in events)
    assert any(
        item["event_type"] == "stage_end" and item["stage"] == "stage_after_fail"
        for item in events
    )
    levels = {item["level"] for item in events if item["event_type"] == "log_line"}
    assert {"info", "warning", "error", "critical"}.issubset(levels)


def test_runner_success_produces_empty_failed_jobs(tmp_path: Path) -> None:
    script = _load_module("scripts/ci/run_unified_action.py")
    events_path = tmp_path / "ci-unified-events.jsonl"
    summary_path = tmp_path / "ci-unified-summary.md"
    failed_jobs_path = tmp_path / "failed-jobs.json"
    ledger_path = tmp_path / ".autosd" / "ci" / "failure_ledger.jsonl"
    verify_report_path = tmp_path / "verify_factory_report.json"
    conformance_report_path = tmp_path / "conformance" / "report.json"
    stages = [
        script.StageConfig(
            name="stage_ok",
            command=(sys.executable, "-c", "print('INFO all good')"),
            blocking=True,
        )
    ]
    exit_code = script.run_unified_action(
        events_path=events_path,
        summary_path=summary_path,
        failed_jobs_path=failed_jobs_path,
        ledger_path=ledger_path,
        verify_report_path=verify_report_path,
        conformance_report_path=conformance_report_path,
        stages=stages,
        update_dashboard=False,
    )
    assert exit_code == 0
    assert json.loads(failed_jobs_path.read_text(encoding="utf-8")) == []
    assert not ledger_path.exists()


def test_stage_env_overrides_take_precedence(tmp_path: Path, monkeypatch) -> None:
    script = _load_module("scripts/ci/run_unified_action.py")
    monkeypatch.setenv("AUTOSD_CI_PIP_AUDIT_REQUIRED", "1")
    events_path = tmp_path / "ci-unified-events.jsonl"
    summary_path = tmp_path / "ci-unified-summary.md"
    failed_jobs_path = tmp_path / "failed-jobs.json"
    ledger_path = tmp_path / ".autosd" / "ci" / "failure_ledger.jsonl"
    verify_report_path = tmp_path / "verify_factory_report.json"
    conformance_report_path = tmp_path / "conformance" / "report.json"
    stages = [
        script.StageConfig(
            name="env_override_check",
            command=(
                sys.executable,
                "-c",
                "import os,sys;"
                "sys.exit(0 if os.environ.get('AUTOSD_CI_PIP_AUDIT_REQUIRED') == '0' else 3)",
            ),
            env_overrides={"AUTOSD_CI_PIP_AUDIT_REQUIRED": "0"},
        )
    ]
    exit_code = script.run_unified_action(
        events_path=events_path,
        summary_path=summary_path,
        failed_jobs_path=failed_jobs_path,
        ledger_path=ledger_path,
        verify_report_path=verify_report_path,
        conformance_report_path=conformance_report_path,
        stages=stages,
        update_dashboard=False,
    )
    assert exit_code == 0
    assert json.loads(failed_jobs_path.read_text(encoding="utf-8")) == []


def test_unified_workflow_single_job_and_runner_invocation() -> None:
    workflow = Path(".github/workflows/unified-actions.yml").read_text(encoding="utf-8")
    assert "jobs:\n  unified_action:" in workflow
    assert "quality_gates:" not in workflow
    assert "factory_conformance:" not in workflow
    assert "failure_summary:" not in workflow
    assert "python scripts/ci/run_unified_action.py" in workflow
