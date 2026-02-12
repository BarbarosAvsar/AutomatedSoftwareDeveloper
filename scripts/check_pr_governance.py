"""Validate PR governance requirements."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

TITLE_RE = re.compile(r"^(feat|fix|chore|docs|refactor|test|ci)(\(.+\))?!?: .+")
REQUIRED_LABELS = {"core", "ci", "security", "docs"}


def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def main() -> None:
    title = os.environ.get("PR_TITLE", "")
    raw_labels = os.environ.get("PR_LABELS", "").split(",")
    labels = {label.strip() for label in raw_labels if label.strip()}

    if not TITLE_RE.match(title):
        raise SystemExit(f"PR title must follow conventional format. Got: {title!r}")

    if labels.isdisjoint(REQUIRED_LABELS):
        required = ", ".join(sorted(REQUIRED_LABELS))
        raise SystemExit(f"PR must include at least one required label from: {required}")

    news = list(Path("newsfragments").glob("*.md")) if Path("newsfragments").exists() else []
    if not news:
        raise SystemExit("Missing changelog fragment in newsfragments/*.md")

    base_ref = os.environ.get("BASE_REF", "origin/main")
    merge_base = _run(["git", "merge-base", "HEAD", base_ref])
    commits = _run(["git", "log", "--format=%B", f"{merge_base}..HEAD"])
    if "Signed-off-by:" not in commits:
        raise SystemExit("DCO check failed: commits are missing Signed-off-by trailers")

    print("Governance checks passed.")


if __name__ == "__main__":
    main()
