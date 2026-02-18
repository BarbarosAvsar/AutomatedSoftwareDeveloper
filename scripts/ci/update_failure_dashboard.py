"""Update a persistent CI failure dashboard issue with failed workflow runs."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DASHBOARD_TITLE = "CI Failure Dashboard"
DASHBOARD_LABEL = "ci-failures"
DATA_BEGIN = "<!-- AUTOSD_CI_FAILURE_DASHBOARD_DATA_BEGIN -->"
DATA_END = "<!-- AUTOSD_CI_FAILURE_DASHBOARD_DATA_END -->"


def _github_request(
    *,
    endpoint: str,
    token: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> Any:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=f"https://api.github.com{endpoint}",
        method=method,
        data=data,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "autosd-failure-dashboard",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _github_safe_request(
    *,
    endpoint: str,
    token: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> Any | None:
    try:
        return _github_request(endpoint=endpoint, token=token, method=method, payload=payload)
    except urllib.error.HTTPError:
        return None


def _list_open_issues(*, repo: str, token: str) -> list[dict[str, Any]]:
    page = 1
    issues: list[dict[str, Any]] = []
    while True:
        endpoint = f"/repos/{repo}/issues?state=open&per_page=100&page={page}"
        payload = _github_request(endpoint=endpoint, token=token)
        if not isinstance(payload, list) or not payload:
            break
        for item in payload:
            if isinstance(item, dict) and "pull_request" not in item:
                issues.append(item)
        page += 1
    return issues


def _ensure_label(*, repo: str, token: str, label: str) -> None:
    _github_safe_request(
        endpoint=f"/repos/{repo}/labels/{label}",
        token=token,
    )
    _github_safe_request(
        endpoint=f"/repos/{repo}/labels",
        token=token,
        method="POST",
        payload={
            "name": label,
            "color": "b60205",
            "description": "Aggregated CI failure dashboard.",
        },
    )


def _find_or_create_dashboard_issue(*, repo: str, token: str) -> int:
    for issue in _list_open_issues(repo=repo, token=token):
        if str(issue.get("title", "")).strip() == DASHBOARD_TITLE:
            number = issue.get("number")
            if isinstance(number, int):
                return number
    _ensure_label(repo=repo, token=token, label=DASHBOARD_LABEL)
    payload = _github_request(
        endpoint=f"/repos/{repo}/issues",
        token=token,
        method="POST",
        payload={
            "title": DASHBOARD_TITLE,
            "body": "Initializing CI failure dashboard...",
            "labels": [DASHBOARD_LABEL],
        },
    )
    number = payload.get("number")
    if not isinstance(number, int):
        raise RuntimeError("Unable to create dashboard issue.")
    return number


def _load_failed_jobs_from_file(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    output: list[dict[str, str]] = []
    if isinstance(payload, dict):
        for job, result in payload.items():
            if isinstance(job, str) and isinstance(result, str):
                output.append({"job": job, "result": result})
        return output
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, str):
                output.append({"job": item, "result": "failure"})
                continue
            if not isinstance(item, dict):
                continue
            job = item.get("job")
            result = item.get("result", "failure")
            if isinstance(job, str) and isinstance(result, str):
                output.append({"job": job, "result": result})
    return output


def _load_failed_jobs_from_flags(items: list[str]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for item in items:
        cleaned = item.strip()
        if not cleaned:
            continue
        if "=" in cleaned:
            job, result = cleaned.split("=", 1)
            output.append({"job": job.strip(), "result": result.strip() or "failure"})
        else:
            output.append({"job": cleaned, "result": "failure"})
    return output


def _extract_data_block(body: str) -> dict[str, Any]:
    pattern = re.compile(
        re.escape(DATA_BEGIN) + r"\s*```json\s*(.*?)\s*```\s*" + re.escape(DATA_END),
        flags=re.DOTALL,
    )
    match = pattern.search(body)
    if match is None:
        return {"version": 1, "entries": []}
    raw = match.group(1)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"version": 1, "entries": []}
    if not isinstance(parsed, dict):
        return {"version": 1, "entries": []}
    entries = parsed.get("entries")
    if not isinstance(entries, list):
        return {"version": 1, "entries": []}
    return {"version": 1, "entries": entries}


def _render_issue_body(*, entries: list[dict[str, Any]]) -> str:
    now_utc = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%SZ")
    lines = [
        "# CI Failure Dashboard",
        "",
        "Single-click view of recent failed workflow runs.",
        "",
        f"Last updated (UTC): `{now_utc}`",
        "",
    ]
    if not entries:
        lines.extend(["No failed runs recorded.", ""])
    else:
        lines.extend(
            [
                "| Date UTC | Workflow | Branch | SHA7 | Failed Jobs | Run |",
                "|---|---|---|---|---|---|",
            ]
        )
        for entry in entries:
            date_utc = str(entry.get("date_utc", ""))
            workflow = str(entry.get("workflow", ""))
            branch = str(entry.get("branch", ""))
            sha7 = str(entry.get("sha7", ""))
            failed_jobs = entry.get("failed_jobs", [])
            if isinstance(failed_jobs, list):
                failed_jobs_display = ", ".join(str(item) for item in failed_jobs)
            else:
                failed_jobs_display = str(failed_jobs)
            run_url = str(entry.get("run_url", ""))
            run_link = f"[open]({run_url})" if run_url else "-"
            lines.append(
                f"| {date_utc} | `{workflow}` | `{branch}` | `{sha7}` | "
                f"`{failed_jobs_display}` | {run_link} |"
            )
        lines.append("")
    data_payload = {"version": 1, "entries": entries}
    lines.extend(
        [
            DATA_BEGIN,
            "```json",
            json.dumps(data_payload, indent=2),
            "```",
            DATA_END,
            "",
        ]
    )
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--failed-jobs-json",
        type=Path,
        default=None,
        help="Path to failed jobs payload written by CI summary/runner scripts.",
    )
    parser.add_argument(
        "--failed-job",
        action="append",
        default=[],
        help="Inline failed job item (job or job=result). Repeat as needed.",
    )
    parser.add_argument(
        "--max-entries",
        type=int,
        default=30,
        help="Maximum number of failure entries retained in the dashboard.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    workflow = os.environ.get("GITHUB_WORKFLOW", "")
    branch = os.environ.get("GITHUB_REF_NAME", "")
    sha = os.environ.get("GITHUB_SHA", "")
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    if token is None or not token.strip():
        raise SystemExit("GITHUB_TOKEN is required.")
    if repo is None or not repo.strip():
        raise SystemExit("GITHUB_REPOSITORY is required.")
    if not run_id.strip():
        raise SystemExit("GITHUB_RUN_ID is required.")

    failed_items: list[dict[str, str]] = []
    if args.failed_jobs_json is not None and args.failed_jobs_json.exists():
        failed_items.extend(_load_failed_jobs_from_file(args.failed_jobs_json))
    failed_items.extend(_load_failed_jobs_from_flags(args.failed_job))
    deduped_failed: list[dict[str, str]] = []
    seen_jobs: set[str] = set()
    for item in failed_items:
        job = item.get("job", "").strip()
        result = item.get("result", "").strip() or "failure"
        if not job or job in seen_jobs:
            continue
        seen_jobs.add(job)
        if result in {"success", "skipped"}:
            continue
        deduped_failed.append({"job": job, "result": result})
    if not deduped_failed:
        print("No failed jobs detected; dashboard update skipped.")
        return 0

    issue_number = _find_or_create_dashboard_issue(repo=repo, token=token)
    issue = _github_request(
        endpoint=f"/repos/{repo}/issues/{issue_number}",
        token=token,
    )
    current_body = str(issue.get("body", ""))
    data = _extract_data_block(current_body)
    existing_entries = data.get("entries", [])
    if not isinstance(existing_entries, list):
        existing_entries = []

    run_url = f"{server_url}/{repo}/actions/runs/{run_id}"
    new_entry = {
        "run_id": run_id,
        "date_utc": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%SZ"),
        "workflow": workflow,
        "branch": branch,
        "sha7": sha[:7],
        "failed_jobs": [item["job"] for item in deduped_failed],
        "run_url": run_url,
    }
    filtered = [
        entry
        for entry in existing_entries
        if isinstance(entry, dict) and str(entry.get("run_id", "")) != run_id
    ]
    entries = [new_entry, *filtered]
    max_entries = max(args.max_entries, 1)
    entries = entries[:max_entries]
    updated_body = _render_issue_body(entries=entries)
    _github_request(
        endpoint=f"/repos/{repo}/issues/{issue_number}",
        token=token,
        method="PATCH",
        payload={"body": updated_body},
    )
    print(f"Updated dashboard issue #{issue_number} with failed run {run_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
