"""Resolve a legacy workflow check by mirroring a Unified Actions job result."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Any

IGNORED_PREFIXES = ("docs/", "newsfragments/")
UNIFIED_WORKFLOW_FILE = "unified-actions.yml"
ALLOWED_CONCLUSIONS = {"success", "skipped"}


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
            "User-Agent": "autosd-workflow-shim",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _paginate(
    *,
    endpoint: str,
    token: str,
    key: str,
) -> list[dict[str, Any]]:
    page = 1
    items: list[dict[str, Any]] = []
    while True:
        separator = "&" if "?" in endpoint else "?"
        payload = _github_request(
            endpoint=f"{endpoint}{separator}per_page=100&page={page}",
            token=token,
        )
        if key == "" and isinstance(payload, list):
            page_items = payload
        else:
            if not isinstance(payload, dict):
                break
            page_items = payload.get(key, [])
        if not isinstance(page_items, list) or not page_items:
            break
        for item in page_items:
            if isinstance(item, dict):
                items.append(item)
        page += 1
    return items


def _path_is_ignored(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("/")
    return normalized.endswith(".md") or normalized.startswith(IGNORED_PREFIXES)


def _all_paths_ignored(paths: Iterable[str]) -> bool:
    materialized = [item for item in paths if item.strip()]
    if not materialized:
        return False
    return all(_path_is_ignored(path) for path in materialized)


def _changed_files_for_pull_request(
    *,
    repo: str,
    token: str,
    payload: dict[str, Any],
) -> list[str]:
    pr = payload.get("pull_request")
    if not isinstance(pr, dict):
        return []
    number = pr.get("number")
    if not isinstance(number, int):
        return []
    files = _paginate(
        endpoint=f"/repos/{repo}/pulls/{number}/files",
        token=token,
        key="",
    )
    return [
        str(item.get("filename", ""))
        for item in files
        if isinstance(item.get("filename"), str)
    ]


def _changed_files_for_push(
    *,
    repo: str,
    token: str,
    payload: dict[str, Any],
) -> list[str]:
    before = payload.get("before")
    after = payload.get("after")
    if isinstance(before, str) and isinstance(after, str) and before and after:
        try:
            compare = _github_request(
                endpoint=f"/repos/{repo}/compare/{before}...{after}",
                token=token,
            )
            files = compare.get("files", [])
            if isinstance(files, list):
                output = [
                    str(item.get("filename", ""))
                    for item in files
                    if isinstance(item, dict) and isinstance(item.get("filename"), str)
                ]
                if output:
                    return output
        except urllib.error.HTTPError:
            pass
    output: list[str] = []
    commits = payload.get("commits", [])
    if isinstance(commits, list):
        for commit in commits:
            if not isinstance(commit, dict):
                continue
            for field in ("added", "modified", "removed"):
                values = commit.get(field, [])
                if isinstance(values, list):
                    output.extend(str(item) for item in values if isinstance(item, str))
    deduped = list(dict.fromkeys(output))
    return deduped


def _docs_only_change(
    *,
    repo: str,
    token: str,
    event_name: str,
    payload: dict[str, Any],
) -> bool:
    if event_name not in {"pull_request", "push"}:
        return False
    paths: list[str]
    if event_name == "pull_request":
        paths = _changed_files_for_pull_request(repo=repo, token=token, payload=payload)
    else:
        paths = _changed_files_for_push(repo=repo, token=token, payload=payload)
    return _all_paths_ignored(paths)


def _list_unified_runs(
    *,
    repo: str,
    token: str,
    event_name: str,
    head_sha: str,
) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "event": event_name,
            "head_sha": head_sha,
            "per_page": "20",
        }
    )
    payload = _github_request(
        endpoint=f"/repos/{repo}/actions/workflows/{UNIFIED_WORKFLOW_FILE}/runs?{query}",
        token=token,
    )
    runs = payload.get("workflow_runs", [])
    if not isinstance(runs, list):
        return []
    return [item for item in runs if isinstance(item, dict)]


def _jobs_for_run(*, repo: str, token: str, run_id: int) -> list[dict[str, Any]]:
    return _paginate(
        endpoint=f"/repos/{repo}/actions/runs/{run_id}/jobs",
        token=token,
        key="jobs",
    )


def _job_conclusion(
    *,
    repo: str,
    token: str,
    run_id: int,
    unified_job_id: str,
) -> str:
    jobs = _jobs_for_run(repo=repo, token=token, run_id=run_id)
    for job in jobs:
        if str(job.get("name", "")) == unified_job_id:
            conclusion = job.get("conclusion")
            if isinstance(conclusion, str):
                return conclusion
            status = job.get("status")
            if isinstance(status, str) and status == "completed":
                return "unknown"
            break
    return "skipped"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True, help="Unified Actions job id to mirror.")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=900,
        help="Maximum wait time for the unified run to complete.",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=int,
        default=10,
        help="Polling interval while waiting for unified run completion.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    head_sha = os.environ.get("GITHUB_SHA", "")
    current_run_id_raw = os.environ.get("GITHUB_RUN_ID", "0")
    if token is None or not token.strip():
        print("GITHUB_TOKEN is required.", file=sys.stderr)
        return 2
    if repo is None or not repo.strip():
        print("GITHUB_REPOSITORY is required.", file=sys.stderr)
        return 2
    if event_path is None or not event_path.strip():
        print("GITHUB_EVENT_PATH is required.", file=sys.stderr)
        return 2
    if not head_sha.strip():
        print("GITHUB_SHA is required.", file=sys.stderr)
        return 2
    try:
        current_run_id = int(current_run_id_raw)
    except ValueError:
        current_run_id = 0
    event_payload = json.loads(Path(event_path).read_text(encoding="utf-8"))

    if _docs_only_change(
        repo=repo,
        token=token,
        event_name=event_name,
        payload=event_payload,
    ):
        print("Docs-only change detected for push/pull_request; passing compatibility shim.")
        return 0

    deadline = time.monotonic() + max(args.timeout_seconds, 1)
    while time.monotonic() < deadline:
        runs = _list_unified_runs(repo=repo, token=token, event_name=event_name, head_sha=head_sha)
        candidate = None
        for run in runs:
            run_id = run.get("id")
            if not isinstance(run_id, int):
                continue
            if run_id == current_run_id:
                continue
            candidate = run
            break
        if candidate is None:
            print("Waiting for matching Unified Actions run...")
            time.sleep(max(args.poll_interval_seconds, 1))
            continue

        run_id = int(candidate["id"])
        status = str(candidate.get("status", "unknown"))
        conclusion = str(candidate.get("conclusion", "unknown"))
        print(
            f"Found Unified Actions run {run_id} status={status} conclusion={conclusion}.",
        )
        if status != "completed":
            time.sleep(max(args.poll_interval_seconds, 1))
            continue

        job_conclusion = _job_conclusion(
            repo=repo,
            token=token,
            run_id=run_id,
            unified_job_id=args.job,
        )
        print(f"Unified Actions job '{args.job}' conclusion={job_conclusion}.")
        return 0 if job_conclusion in ALLOWED_CONCLUSIONS else 1

    print(
        f"Timed out waiting for Unified Actions job '{args.job}' result.",
        file=sys.stderr,
    )
    if event_name == "workflow_dispatch":
        print("No matching unified run found for workflow_dispatch; passing shim.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
