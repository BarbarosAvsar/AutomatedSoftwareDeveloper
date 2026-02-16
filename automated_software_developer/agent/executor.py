"""Command execution utilities for verification steps."""

from __future__ import annotations

import os
import re
import subprocess  # nosec B404
import time
from pathlib import Path

from automated_software_developer.agent.models import CommandResult
from automated_software_developer.agent.security import SecurityError, is_command_safe


class CommandExecutor:
    """Runs shell commands with timeout and safety checks."""

    def __init__(self, timeout_seconds: int = 180) -> None:
        """Initialize executor with per-command timeout in seconds."""
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero.")
        self.timeout_seconds = timeout_seconds

    def run(self, command: str, cwd: Path) -> CommandResult:
        """Execute a single command and capture outputs."""
        if not is_command_safe(command):
            raise SecurityError(f"Rejected unsafe command: {command}")

        start = time.perf_counter()
        if os.name == "nt":
            normalized = self._normalize_windows_command(command)
            shell_command = ["powershell", "-NoProfile", "-Command", normalized]
        else:
            shell_command = ["bash", "-lc", command]

        completed = subprocess.run(  # noqa: S603  # nosec B603
            shell_command,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        duration = time.perf_counter() - start
        return CommandResult(
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_seconds=duration,
        )

    def run_many(self, commands: list[str], cwd: Path) -> list[CommandResult]:
        """Execute commands sequentially and return all results."""
        results: list[CommandResult] = []
        for command in commands:
            result = self.run(command, cwd=cwd)
            results.append(result)
            if result.exit_code != 0:
                break
        return results

    def _normalize_windows_command(self, command: str) -> str:
        """Normalize common POSIX shell patterns into PowerShell-compatible commands."""
        parts = [part.strip() for part in command.split("&&")]
        normalized_parts = [self._normalize_windows_command_part(part) for part in parts]
        if len(normalized_parts) == 1:
            return normalized_parts[0]
        guard = "; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } ; "
        return guard.join(normalized_parts)

    def _normalize_windows_command_part(self, command: str) -> str:
        """Normalize a single command part for PowerShell execution."""
        match = re.fullmatch(r"mkdir\s+-p\s+(.+)", command.strip())
        if match is None:
            return command
        raw_path = match.group(1).strip().strip("'\"")
        escaped_path = raw_path.replace("'", "''")
        return f"New-Item -ItemType Directory -Force -Path '{escaped_path}' | Out-Null"
