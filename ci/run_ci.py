"""Cross-platform CI entrypoint for repository quality gates."""

from __future__ import annotations

import os
import subprocess  # nosec B404
import sys
from collections.abc import Sequence


def _run(args: Sequence[str]) -> int:
    """Run one command and return its exit code."""
    command = " ".join(args)
    print(f"$ {command}")
    result = subprocess.run(args, check=False)  # nosec B603
    if result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}: {command}")
    return int(result.returncode)


def main() -> int:
    """Execute the canonical CI gate sequence."""
    commands: list[list[str]] = [
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "mypy", "automated_software_developer"],
        [
            sys.executable,
            "-m",
            "pytest",
            "--cov=automated_software_developer",
            "--cov-report=term-missing",
            "--cov-fail-under=79",
        ],
        [sys.executable, "-m", "pip_audit", "--progress-spinner", "off"],
    ]
    for args in commands[:-1]:
        exit_code = _run(args)
        if exit_code != 0:
            return exit_code
    pip_audit_required = os.environ.get("AUTOSD_CI_PIP_AUDIT_REQUIRED", "").lower() in {
        "1",
        "true",
        "yes",
    }
    pip_audit_exit = _run(commands[-1])
    if pip_audit_exit != 0 and pip_audit_required:
        return pip_audit_exit
    if pip_audit_exit != 0:
        print("pip_audit reported vulnerabilities; continuing because strict mode is disabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
