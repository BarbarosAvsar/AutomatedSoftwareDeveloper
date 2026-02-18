"""Tests for CI failure summary and dashboard helper scripts."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module(script_path: str):
    path = Path(script_path).resolve()
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load script module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_build_failure_summary_with_no_failures(tmp_path: Path) -> None:
    script = _load_module("scripts/ci/build_failure_summary.py")
    summary = script.build_summary(
        failed_jobs={},
        autosd_log_dir=tmp_path / "logs",
        diagnostics_dir=tmp_path / "diagnostics",
    )
    assert "No failed actions found." in summary


def test_build_failure_summary_extracts_failed_jobs() -> None:
    script = _load_module("scripts/ci/build_failure_summary.py")
    failed = script._failed_jobs(  # noqa: SLF001
        {
            "lint": "success",
            "test": "failure",
            "sbom": "skipped",
            "security": "cancelled",
        }
    )
    assert failed == {"security": "cancelled", "test": "failure"}


def test_failure_dashboard_data_block_roundtrip() -> None:
    script = _load_module("scripts/ci/update_failure_dashboard.py")
    entry = {
        "run_id": "123",
        "date_utc": "2026-02-16 20:00:00Z",
        "workflow": "Unified Actions",
        "branch": "main",
        "sha7": "abcdef1",
        "failed_jobs": ["test_shard"],
        "run_url": "https://example.invalid/run/123",
    }
    body = script._render_issue_body(entries=[entry])  # noqa: SLF001
    parsed = script._extract_data_block(body)  # noqa: SLF001
    entries = parsed.get("entries", [])
    assert isinstance(entries, list)
    assert entries and entries[0]["run_id"] == "123"


def test_append_failure_ledger_writes_jsonl(tmp_path: Path, monkeypatch) -> None:
    script = _load_module("scripts/ci/build_failure_summary.py")
    ledger = tmp_path / ".autosd" / "ci" / "failure_ledger.jsonl"
    monkeypatch.setenv("GITHUB_RUN_ID", "456")
    monkeypatch.setenv("GITHUB_WORKFLOW", "Unified Actions")
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    monkeypatch.setenv("GITHUB_SHA", "abcdef123456")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    script.append_failure_ledger(
        failed_jobs={"quality_gates": "failure"},
        ledger_path=ledger,
    )
    lines = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["run_id"] == "456"
    assert payload["failed_jobs"][0]["job"] == "quality_gates"
