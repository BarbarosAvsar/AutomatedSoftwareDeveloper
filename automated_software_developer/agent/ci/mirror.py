"""CI mirror runner for standardized entrypoint execution."""

from __future__ import annotations

import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MirrorResult:
    """Result payload for CI mirror runs."""

    repo_path: Path
    command: str
    passed: bool
    exit_code: int
    duration_seconds: float
    stdout: str
    stderr: str


def run_ci_mirror(repo_path: Path) -> MirrorResult:
    """Run the standardized CI entrypoint for the provided repo."""
    resolved = repo_path.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError("repo_path must be an existing directory.")
    entrypoint = resolved / "ci" / "run_ci.sh"
    if not entrypoint.exists():
        raise ValueError("ci/run_ci.sh missing for CI mirror run.")
    command = "./ci/run_ci.sh"
    start = time.monotonic()
    result = subprocess.run(
        shlex.split(command),
        cwd=resolved,
        check=False,
        text=True,
        capture_output=True,
    )
    duration = time.monotonic() - start
    return MirrorResult(
        repo_path=resolved,
        command=command,
        passed=result.returncode == 0,
        exit_code=result.returncode,
        duration_seconds=duration,
        stdout=result.stdout,
        stderr=result.stderr,
    )
