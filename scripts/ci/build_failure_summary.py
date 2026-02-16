"""Build a unified markdown summary of failed CI jobs for a workflow run."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

ERROR_PATTERN = re.compile(r"\bERROR\b")
WARNING_PATTERN = re.compile(r"\bWARNING\b")
CRITICAL_PATTERN = re.compile(r"\bCRITICAL\b")


def _parse_needs_payload(raw: str) -> dict[str, str]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("NEEDS must deserialize to a mapping.")
    output: dict[str, str] = {}
    for job_name, value in payload.items():
        if not isinstance(job_name, str) or not isinstance(value, dict):
            continue
        result = value.get("result")
        if isinstance(result, str):
            output[job_name] = result
    return output


def _failed_jobs(needs: dict[str, str]) -> dict[str, str]:
    return {
        name: result
        for name, result in sorted(needs.items())
        if result not in {"success", "skipped"}
    }


def _log_excerpts(log_dir: Path) -> tuple[list[str], list[str]]:
    summary_rows: list[str] = []
    excerpts: list[str] = []
    for log_path in sorted(log_dir.rglob("autosd.log")):
        content_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        joined = "\n".join(content_lines)
        errors = len(ERROR_PATTERN.findall(joined))
        warnings = len(WARNING_PATTERN.findall(joined))
        critical = len(CRITICAL_PATTERN.findall(joined))
        if errors == 0 and warnings == 0 and critical == 0:
            continue
        artifact_name = log_path.parent.name
        summary_rows.append(f"| `{artifact_name}` | {errors} | {warnings} | {critical} |")
        matching = [
            line
            for line in content_lines
            if (" ERROR " in line or " WARNING " in line or " CRITICAL " in line)
        ]
        if matching:
            excerpts.append(f"### `{artifact_name}` notable entries")
            excerpts.append("```text")
            excerpts.extend(matching[:20])
            excerpts.append("```")
            excerpts.append("")
    return summary_rows, excerpts


def _diagnostic_blocks(diagnostics_dir: Path) -> list[str]:
    lines: list[str] = []
    files = sorted(item for item in diagnostics_dir.rglob("*") if item.is_file())
    if not files:
        return lines
    lines.extend(["", "### Action diagnostics", ""])
    for diagnostic_path in files:
        rel = diagnostic_path.relative_to(diagnostics_dir)
        content = diagnostic_path.read_text(encoding="utf-8", errors="replace")
        non_empty = [line for line in content.splitlines() if line.strip()]
        lines.append(f"#### `{rel.as_posix()}`")
        lines.append("```text")
        lines.extend(non_empty[:40] if non_empty else ["(empty diagnostic file)"])
        lines.append("```")
        lines.append("")
    return lines


def build_summary(
    *,
    failed_jobs: dict[str, str],
    autosd_log_dir: Path,
    diagnostics_dir: Path,
) -> str:
    lines = [
        "## Unified failure summary",
        "",
        "Only failing actions are included below. Successful or skipped actions are omitted.",
    ]
    if not failed_jobs:
        lines.extend(["", "No failed actions found."])
        return "\n".join(lines) + "\n"

    lines.extend(["", "| Action | Result |", "|---|---|"])
    for job_name, result in failed_jobs.items():
        lines.append(f"| `{job_name}` | `{result}` |")

    summary_rows, excerpts = _log_excerpts(autosd_log_dir)
    if summary_rows:
        lines.extend(
            [
                "",
                "| AutoSD Artifact | Errors | Warnings | Critical |",
                "|---|---:|---:|---:|",
            ]
        )
        lines.extend(summary_rows)

    lines.extend(_diagnostic_blocks(diagnostics_dir))

    if excerpts:
        lines.extend(["", "### AutoSD log excerpts", ""])
        lines.extend(excerpts)

    return "\n".join(lines) + "\n"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=Path("autosd-log-summary.md"),
        help="Path to write markdown summary.",
    )
    parser.add_argument(
        "--failed-jobs-path",
        type=Path,
        default=Path("failed-jobs.json"),
        help="Path to write machine-readable failed jobs list.",
    )
    parser.add_argument(
        "--autosd-log-dir",
        type=Path,
        default=Path("autosd-log-artifacts"),
        help="Directory containing downloaded autosd log artifacts.",
    )
    parser.add_argument(
        "--diagnostics-dir",
        type=Path,
        default=Path("unified-error-artifacts"),
        help="Directory containing downloaded diagnostics artifacts.",
    )
    parser.add_argument(
        "--needs-json",
        type=str,
        default=None,
        help="Optional explicit NEEDS json payload. Defaults to NEEDS env var.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    raw_needs = args.needs_json
    if raw_needs is None:
        raw_needs = os.environ.get("NEEDS")
    if raw_needs is None:
        raise SystemExit("Missing NEEDS payload. Provide --needs-json or NEEDS env variable.")
    needs = _parse_needs_payload(raw_needs)
    failed_jobs = _failed_jobs(needs)
    summary = build_summary(
        failed_jobs=failed_jobs,
        autosd_log_dir=args.autosd_log_dir,
        diagnostics_dir=args.diagnostics_dir,
    )
    args.summary_path.write_text(summary, encoding="utf-8")
    failed_payload = [{"job": name, "result": result} for name, result in failed_jobs.items()]
    args.failed_jobs_path.write_text(json.dumps(failed_payload, indent=2), encoding="utf-8")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
