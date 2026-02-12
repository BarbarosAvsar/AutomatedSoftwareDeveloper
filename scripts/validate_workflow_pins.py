"""Fail CI when workflow actions are not pinned to a full commit SHA."""

from __future__ import annotations

import re
from pathlib import Path

USES_RE = re.compile(r"^\s*-\s*uses:\s*([^\s]+)")
PIN_RE = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
EXEMPT_PREFIXES = ("docker://", "./")


def main() -> None:
    workflow_dir = Path(".github/workflows")
    violations: list[str] = []
    for workflow in sorted(workflow_dir.glob("*.yml")):
        for idx, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), start=1):
            match = USES_RE.match(line)
            if not match:
                continue
            target = match.group(1)
            if target.startswith(EXEMPT_PREFIXES):
                continue
            if not PIN_RE.match(target):
                violations.append(f"{workflow}:{idx}: action must be SHA pinned: {target}")

    if violations:
        joined = "\n".join(violations)
        raise SystemExit(f"Found non-pinned actions:\n{joined}")

    print("All workflow actions are SHA pinned.")


if __name__ == "__main__":
    main()
