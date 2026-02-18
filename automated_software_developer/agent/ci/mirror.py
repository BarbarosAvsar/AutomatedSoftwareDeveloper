"""CI mirror runner for standardized entrypoint execution."""

from __future__ import annotations

import subprocess  # nosec B404
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from shutil import which


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
    python_entrypoint = resolved / "ci" / "run_ci.py"
    if not entrypoint.is_file() and not python_entrypoint.is_file():
        raise ValueError("Missing ci/run_ci.sh and ci/run_ci.py for CI mirror run.")
    if which("bash") is None:
        if not python_entrypoint.is_file():
            raise ValueError("bash is unavailable and ci/run_ci.py is missing for CI mirror run.")
        command = f"{sys.executable} ./ci/run_ci.py"
        args = [sys.executable, "./ci/run_ci.py"]
    else:
        if not entrypoint.is_file():
            raise ValueError("ci/run_ci.sh missing for CI mirror run.")
        command = "bash ./ci/run_ci.sh"
        args = ["bash", "./ci/run_ci.sh"]
    start = time.monotonic()
    result = subprocess.run(  # nosec B603
        args,
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
