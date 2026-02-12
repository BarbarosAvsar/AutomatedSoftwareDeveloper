"""Ensure coverage does not regress compared with base branch."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

COVERAGE_CMD = [
    sys.executable,
    "-m",
    "pytest",
    "--cov=automated_software_developer",
    "--cov-report=json:coverage.json",
    "-q",
]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def coverage_percent(path: Path) -> float:
    data = json.loads(path.read_text(encoding="utf-8"))
    return float(data["totals"]["percent_covered"])


def main() -> None:
    base = sys.argv[1] if len(sys.argv) > 1 else "main"

    run(COVERAGE_CMD)
    head_cov = coverage_percent(Path("coverage.json"))

    run(["git", "fetch", "origin", base])
    run(["git", "checkout", f"origin/{base}"])
    run([sys.executable, "-m", "pip", "install", "-e", ".[dev,security]"])
    run(COVERAGE_CMD)
    base_cov = coverage_percent(Path("coverage.json"))

    print(f"base={base_cov:.2f} head={head_cov:.2f}")
    if head_cov < 85.0:
        raise SystemExit("Coverage threshold 85% not met")
    if head_cov < base_cov:
        raise SystemExit("Coverage regression detected")


if __name__ == "__main__":
    main()
