"""Run all CI stages sequentially and emit one unified JSONL event stream."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess  # nosec B404
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from queue import Queue
from typing import Any, TextIO, cast

LOG_LEVELS = {"info", "warning", "error", "critical"}
SECRET_NAME_MARKERS = (
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PRIVATE_KEY",
    "API_KEY",
    "AUTH",
    "PASS",
)
TOKEN_PATTERNS = (
    re.compile(r"gh[psu]_[A-Za-z0-9]{30,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{30,}"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9\-._~+/]+=*"),
)


@dataclass(frozen=True)
class StageConfig:
    """One sequential CI stage definition."""

    name: str
    command: tuple[str, ...]
    blocking: bool = True


@dataclass(frozen=True)
class StageResult:
    """Execution result for one CI stage."""

    name: str
    command: str
    exit_code: int
    blocking: bool
    duration_seconds: float

    @property
    def status(self) -> str:
        """Return stage status string."""
        if self.exit_code == 0:
            return "success"
        if self.blocking:
            return "failure"
        return "warning"


def classify_log_level(line: str) -> str:
    """Classify one log line into info/warning/error/critical."""
    upper = line.upper()
    if "CRITICAL" in upper:
        return "critical"
    if "ERROR" in upper or "TRACEBACK" in upper or "FATAL" in upper:
        return "error"
    if "WARNING" in upper or "WARN" in upper:
        return "warning"
    return "info"


def _utc_timestamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _github_metadata() -> dict[str, str]:
    sha = os.environ.get("GITHUB_SHA", "")
    return {
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
        "branch": os.environ.get("GITHUB_REF_NAME", ""),
        "sha7": sha[:7],
    }


def _collect_secret_values() -> list[str]:
    values: list[str] = []
    for name, value in os.environ.items():
        if len(value) < 8:
            continue
        upper_name = name.upper()
        if any(marker in upper_name for marker in SECRET_NAME_MARKERS):
            values.append(value)
    values.sort(key=len, reverse=True)
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _redact(text: str, secret_values: list[str]) -> str:
    """Redact token-like strings and secret env values."""
    output = text
    for pattern in TOKEN_PATTERNS:
        output = pattern.sub(lambda match: f"{match.group(0)[:8]}***REDACTED***", output)
    for secret in secret_values:
        output = output.replace(secret, "***REDACTED***")
    return output


class EventStream:
    """Append-only writer for unified CI JSONL events."""

    def __init__(self, path: Path, secret_values: list[str]) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("w", encoding="utf-8")
        self._secret_values = secret_values
        self._meta = _github_metadata()

    def emit(
        self,
        *,
        level: str,
        stage: str,
        event_type: str,
        message: str,
        command: str | None = None,
        exit_code: int | None = None,
        status: str | None = None,
        source: str | None = None,
    ) -> None:
        """Emit one JSONL event row."""
        safe_level = level if level in LOG_LEVELS else "info"
        payload: dict[str, Any] = {
            "timestamp_utc": _utc_timestamp(),
            "level": safe_level,
            "stage": stage,
            "event_type": event_type,
            "message": _redact(message, self._secret_values),
        }
        for key, value in self._meta.items():
            if value:
                payload[key] = value
        if command is not None:
            payload["command"] = command
        if exit_code is not None:
            payload["exit_code"] = exit_code
        if status is not None:
            payload["status"] = status
        if source is not None:
            payload["source"] = source
        self._handle.write(json.dumps(payload, sort_keys=True))
        self._handle.write("\n")
        self._handle.flush()

    def close(self) -> None:
        """Close JSONL stream."""
        self._handle.close()


def _pump_stream(
    stream: TextIO,
    source: str,
    queue: Queue[tuple[str, str | None]],
) -> None:
    for line in iter(stream.readline, ""):
        queue.put((source, line.rstrip("\n")))
    queue.put((source, None))


def _run_stage(stage: StageConfig, events: EventStream, secret_values: list[str]) -> StageResult:
    command = " ".join(stage.command)
    events.emit(
        level="info",
        stage=stage.name,
        event_type="stage_start",
        message=f"Starting stage '{stage.name}'.",
        command=command,
        status="in_progress",
    )
    start = time.monotonic()
    try:
        process = subprocess.Popen(  # nosec B603
            list(stage.command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except OSError as exc:
        duration = time.monotonic() - start
        message = _redact(f"Failed to start command: {exc}", secret_values)
        print(f"[{stage.name}] {message}")
        events.emit(
            level="critical" if stage.blocking else "warning",
            stage=stage.name,
            event_type="stage_end",
            message=message,
            command=command,
            exit_code=1,
            status="failure" if stage.blocking else "warning",
        )
        return StageResult(
            name=stage.name,
            command=command,
            exit_code=1,
            blocking=stage.blocking,
            duration_seconds=duration,
        )

    stdout = process.stdout
    stderr = process.stderr
    if stdout is None or stderr is None:
        duration = time.monotonic() - start
        events.emit(
            level="critical" if stage.blocking else "warning",
            stage=stage.name,
            event_type="stage_end",
            message="Process streams were unavailable.",
            command=command,
            exit_code=1,
            status="failure" if stage.blocking else "warning",
        )
        return StageResult(
            name=stage.name,
            command=command,
            exit_code=1,
            blocking=stage.blocking,
            duration_seconds=duration,
        )

    queue: Queue[tuple[str, str | None]] = Queue()
    threads = [
        threading.Thread(target=_pump_stream, args=(stdout, "stdout", queue), daemon=True),
        threading.Thread(target=_pump_stream, args=(stderr, "stderr", queue), daemon=True),
    ]
    for thread in threads:
        thread.start()

    completed_streams = 0
    while completed_streams < 2:
        source, line = queue.get()
        if line is None:
            completed_streams += 1
            continue
        safe_line = _redact(line, secret_values)
        level = classify_log_level(safe_line)
        print(f"[{stage.name}][{source}] {safe_line}")
        events.emit(
            level=level,
            stage=stage.name,
            event_type="log_line",
            message=safe_line,
            command=command,
            source=source,
        )

    for thread in threads:
        thread.join(timeout=1)
    exit_code = int(process.wait())
    duration = time.monotonic() - start
    result = StageResult(
        name=stage.name,
        command=command,
        exit_code=exit_code,
        blocking=stage.blocking,
        duration_seconds=duration,
    )
    end_level = "info" if result.exit_code == 0 else ("error" if result.blocking else "warning")
    events.emit(
        level=end_level,
        stage=stage.name,
        event_type="stage_end",
        message=(
            f"Stage '{stage.name}' completed successfully."
            if result.exit_code == 0
            else f"Stage '{stage.name}' failed with exit code {result.exit_code}."
        ),
        command=command,
        exit_code=result.exit_code,
        status=result.status,
    )
    return result


def _failed_jobs(results: list[StageResult]) -> list[dict[str, str]]:
    payload: list[dict[str, str]] = []
    for result in results:
        if result.exit_code == 0:
            continue
        payload.append(
            {
                "job": result.name,
                "result": "failure" if result.blocking else "warning",
            }
        )
    return payload


def _write_failed_jobs(path: Path, jobs: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jobs, indent=2), encoding="utf-8")


def _write_summary(path: Path, results: list[StageResult]) -> None:
    lines = [
        "# Unified CI Summary",
        "",
        "| Stage | Blocking | Exit Code | Status | Duration (s) |",
        "|---|---:|---:|---|---:|",
    ]
    for result in results:
        lines.append(
            f"| `{result.name}` | {'yes' if result.blocking else 'no'} | "
            f"{result.exit_code} | `{result.status}` | {result.duration_seconds:.2f} |"
        )
    blocking_failures = [result for result in results if result.blocking and result.exit_code != 0]
    lines.extend(
        [
            "",
            f"- Total stages: {len(results)}",
            f"- Blocking failures: {len(blocking_failures)}",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _fallback_append_failure_ledger(*, failed_jobs: dict[str, str], ledger_path: Path) -> None:
    if not failed_jobs:
        return
    sha = os.environ.get("GITHUB_SHA", "")
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run_url = f"{server_url}/{repository}/actions/runs/{run_id}" if repository and run_id else ""
    payload = {
        "timestamp_utc": _utc_timestamp(),
        "run_id": run_id,
        "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
        "branch": os.environ.get("GITHUB_REF_NAME", ""),
        "sha7": sha[:7],
        "failed_jobs": [{"job": job, "result": result} for job, result in failed_jobs.items()],
        "run_url": run_url,
    }
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True))
        handle.write("\n")


def _load_append_failure_ledger() -> Callable[..., None] | None:
    script_path = Path(__file__).with_name("build_failure_summary.py")
    if not script_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("build_failure_summary", script_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    candidate = getattr(module, "append_failure_ledger", None)
    if not callable(candidate):
        return None
    return cast(Callable[..., None], candidate)


def _append_failure_ledger(*, failed_jobs: dict[str, str], ledger_path: Path) -> None:
    append_function = _load_append_failure_ledger()
    if append_function is not None:
        append_function(failed_jobs=failed_jobs, ledger_path=ledger_path)
        return
    _fallback_append_failure_ledger(failed_jobs=failed_jobs, ledger_path=ledger_path)


def run_unified_action(
    *,
    events_path: Path,
    summary_path: Path,
    failed_jobs_path: Path,
    ledger_path: Path,
    verify_report_path: Path,
    conformance_report_path: Path,
    stages: list[StageConfig] | None = None,
    update_dashboard: bool = True,
) -> int:
    """Execute sequential CI stages and emit unified observability artifacts."""
    secret_values = _collect_secret_values()
    events = EventStream(events_path, secret_values=secret_values)
    results: list[StageResult] = []
    configured_stages = stages or [
        StageConfig(
            name="install_pip",
            command=(sys.executable, "-m", "pip", "install", "--upgrade", "pip"),
        ),
        StageConfig(
            name="install_deps",
            command=(sys.executable, "-m", "pip", "install", "-e", ".[dev,security]"),
        ),
        StageConfig(
            name="verify_factory",
            command=(
                sys.executable,
                "-m",
                "automated_software_developer.cli",
                "verify-factory",
                "--verify-report-path",
                str(verify_report_path),
                "--report-path",
                str(conformance_report_path),
            ),
        ),
    ]

    try:
        for stage in configured_stages:
            results.append(_run_stage(stage, events, secret_values))

        if update_dashboard and any(result.exit_code != 0 for result in results):
            dashboard_stage = StageConfig(
                name="dashboard_update",
                command=(
                    sys.executable,
                    "scripts/ci/update_failure_dashboard.py",
                    "--failed-jobs-json",
                    str(failed_jobs_path),
                    "--max-entries",
                    "30",
                ),
                blocking=False,
            )
            # Write initial failed jobs so dashboard updater can consume it.
            _write_failed_jobs(failed_jobs_path, _failed_jobs(results))
            results.append(_run_stage(dashboard_stage, events, secret_values))

        failed_job_list = _failed_jobs(results)
        _write_failed_jobs(failed_jobs_path, failed_job_list)
        failed_job_map = {item["job"]: item["result"] for item in failed_job_list}
        _append_failure_ledger(failed_jobs=failed_job_map, ledger_path=ledger_path)
        _write_summary(summary_path, results)

        blocking_failed = any(result.blocking and result.exit_code != 0 for result in results)
        events.emit(
            level="error" if blocking_failed else "info",
            stage="unified_action",
            event_type="run_summary",
            message=(
                "Unified sequential action completed with blocking failures."
                if blocking_failed
                else "Unified sequential action completed successfully."
            ),
            status="failed" if blocking_failed else "passed",
        )
        return 1 if blocking_failed else 0
    except Exception as exc:  # noqa: BLE001
        events.emit(
            level="critical",
            stage="unified_action",
            event_type="run_summary",
            message=f"Unhandled exception in unified action runner: {exc}",
            status="failed",
        )
        _write_failed_jobs(
            failed_jobs_path,
            [{"job": "unified_action_runner", "result": "failure"}],
        )
        _write_summary(summary_path, results)
        return 1
    finally:
        events.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--events-path",
        type=Path,
        default=Path("ci-unified-events.jsonl"),
        help="Path for unified CI event JSONL output.",
    )
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=Path("ci-unified-summary.md"),
        help="Path for human-readable CI summary markdown.",
    )
    parser.add_argument(
        "--failed-jobs-path",
        type=Path,
        default=Path("failed-jobs.json"),
        help="Path for failed stage payload consumed by dashboard integration.",
    )
    parser.add_argument(
        "--ledger-path",
        type=Path,
        default=Path(".autosd/ci/failure_ledger.jsonl"),
        help="Path for append-only local failure ledger.",
    )
    parser.add_argument(
        "--verify-report-path",
        type=Path,
        default=Path("verify_factory_report.json"),
        help="Path for autosd verify-factory summary report.",
    )
    parser.add_argument(
        "--conformance-report-path",
        type=Path,
        default=Path("conformance/report.json"),
        help="Path for conformance suite report output.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    return run_unified_action(
        events_path=args.events_path,
        summary_path=args.summary_path,
        failed_jobs_path=args.failed_jobs_path,
        ledger_path=args.ledger_path,
        verify_report_path=args.verify_report_path,
        conformance_report_path=args.conformance_report_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
