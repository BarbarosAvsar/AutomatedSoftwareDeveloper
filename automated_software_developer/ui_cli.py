"""Utilities for serving the UI and managing Windows launch shortcuts."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess  # nosec B404
import sys
import threading
import time
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO


class UICommandError(RuntimeError):
    """Raised when UI serve/shortcut command preconditions fail."""


@dataclass(frozen=True)
class UIServeConfig:
    """Runtime configuration for ``autosd ui serve``."""

    host: str = "127.0.0.1"
    backend_port: int = 8080
    frontend_port: int = 5173
    open_browser: bool = True
    reload: bool = True
    install_frontend_deps: bool = False


@dataclass(frozen=True)
class UIServePlan:
    """Computed launch plan used by tests and runtime."""

    backend_command: list[str]
    frontend_command: list[str]
    frontend_url: str
    backend_url: str


def ensure_python_version() -> None:
    """Fail fast unless Python 3.11+ is active."""
    minimum = (3, 11)
    current = tuple(sys.version_info[:2])
    if current < minimum:
        raise UICommandError("autosd ui serve requires Python 3.11+.")


def ensure_tooling_available() -> tuple[str, str]:
    """Resolve required Node.js/npm executables, failing with actionable errors when missing."""
    resolved = {name: shutil.which(name) for name in ("node", "npm")}
    missing = [name for name, path in resolved.items() if path is None]
    if missing:
        joined = ", ".join(missing)
        raise UICommandError(
            f"Missing required tooling on PATH: {joined}. Install Node.js LTS and npm, then retry."
        )

    node_path = resolved["node"]
    npm_path = resolved["npm"]
    if node_path is None or npm_path is None:
        raise UICommandError("Unable to resolve Node.js/npm tooling paths from PATH.")
    return node_path, npm_path


def ensure_port_available(host: str, port: int) -> None:
    """Validate that ``host:port`` can be bound before launching subprocesses."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_socket:
            test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            test_socket.bind((host, port))
    except OSError as exc:
        raise UICommandError(f"Port {port} on {host} is unavailable: {exc}.") from exc


def ensure_frontend_dependencies(frontend_dir: Path, *, install: bool, npm_path: str) -> None:
    """Ensure frontend dependencies exist or install them when requested."""
    node_modules = frontend_dir / "node_modules"
    if node_modules.exists():
        return
    if not install:
        raise UICommandError(
            "Frontend dependencies are missing. Run `npm install` in ui/frontend or rerun "
            "with --install-frontend-deps."
        )

    result = subprocess.run(  # nosec B603
        [npm_path, "install"],
        cwd=frontend_dir,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "npm install failed"
        raise UICommandError(f"Unable to install frontend dependencies: {stderr}")


def build_ui_serve_plan(config: UIServeConfig, *, npm_path: str) -> UIServePlan:
    """Build the backend/frontend command plan from validated configuration."""
    backend_command = [
        sys.executable,
        "-m",
        "uvicorn",
        "ui.backend.app:app",
        "--host",
        config.host,
        "--port",
        str(config.backend_port),
    ]
    if config.reload:
        backend_command.append("--reload")

    frontend_command = [
        npm_path,
        "run",
        "dev",
        "--",
        "--host",
        config.host,
        "--port",
        str(config.frontend_port),
    ]
    frontend_url = f"http://{config.host}:{config.frontend_port}"
    backend_url = f"http://{config.host}:{config.backend_port}"
    return UIServePlan(
        backend_command=backend_command,
        frontend_command=frontend_command,
        frontend_url=frontend_url,
        backend_url=backend_url,
    )


def stream_subprocess_output(stream: IO[str] | None, *, label: str) -> None:
    """Forward subprocess logs with a concise label prefix."""
    if stream is None:
        return
    for raw_line in stream:
        line = raw_line.rstrip()
        if line:
            print(f"[{label}] {line}")


def serve_ui(config: UIServeConfig, *, repo_root: Path) -> None:
    """Run backend and frontend development servers with coordinated lifecycle management."""
    ensure_python_version()
    _, npm_path = ensure_tooling_available()
    ensure_port_available(config.host, config.backend_port)
    ensure_port_available(config.host, config.frontend_port)

    frontend_dir = repo_root / "ui" / "frontend"
    if not frontend_dir.exists():
        raise UICommandError(f"Frontend directory not found at {frontend_dir}.")
    ensure_frontend_dependencies(
        frontend_dir,
        install=config.install_frontend_deps,
        npm_path=npm_path,
    )

    plan = build_ui_serve_plan(config, npm_path=npm_path)
    print("Starting AutoSD UI services...")
    print(f"Frontend: {plan.frontend_url}")
    print(f"Backend : {plan.backend_url}")

    backend_proc = subprocess.Popen(  # nosec B603
        plan.backend_command,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    frontend_proc = subprocess.Popen(  # nosec B603
        plan.frontend_command,
        cwd=frontend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    backend_thread = threading.Thread(
        target=stream_subprocess_output,
        args=(backend_proc.stdout,),
        kwargs={"label": "backend"},
        daemon=True,
    )
    frontend_thread = threading.Thread(
        target=stream_subprocess_output,
        args=(frontend_proc.stdout,),
        kwargs={"label": "frontend"},
        daemon=True,
    )
    backend_thread.start()
    frontend_thread.start()

    if config.open_browser:
        webbrowser.open(plan.frontend_url)

    try:
        while True:
            backend_code = backend_proc.poll()
            frontend_code = frontend_proc.poll()
            if backend_code is not None or frontend_code is not None:
                if backend_code not in (None, 0):
                    raise UICommandError(f"Backend exited unexpectedly with code {backend_code}.")
                if frontend_code not in (None, 0):
                    raise UICommandError(f"Frontend exited unexpectedly with code {frontend_code}.")
                if backend_code == 0 or frontend_code == 0:
                    return
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("Stopping UI services...")
    finally:
        _terminate_process(frontend_proc)
        _terminate_process(backend_proc)


def _terminate_process(process: subprocess.Popen[str]) -> None:
    """Terminate a child process gracefully, then kill if required."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _windows_desktop_candidates() -> list[Path]:
    """Collect candidate per-user desktop paths in priority order."""
    candidates: list[Path] = []
    userprofile = os.environ.get("USERPROFILE")
    onedrive = os.environ.get("ONEDRIVE")
    if userprofile:
        candidates.append(Path(userprofile) / "Desktop")
    if onedrive:
        candidates.append(Path(onedrive) / "Desktop")
    candidates.append(Path.home() / "Desktop")
    return candidates


def resolve_windows_desktop_path() -> Path:
    """Resolve a usable desktop path for the current user."""
    for candidate in _windows_desktop_candidates():
        if candidate.exists() and candidate.is_dir():
            return candidate
    fallback = Path.home() / "Desktop"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def write_windows_launchers(repo_root: Path) -> tuple[Path, Path]:
    """Write repository-local PowerShell and batch launcher scripts."""
    scripts_dir = repo_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    ps1_path = scripts_dir / "start_ui.ps1"
    bat_path = scripts_dir / "start_ui.bat"

    ps1_path.write_text(
        """$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = 'AutoSD UI Launcher'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir '..')).Path
Set-Location $RepoRoot

Write-Host 'Launching AutoSD UI...' -ForegroundColor Cyan
if (-not (Get-Command autosd -ErrorAction SilentlyContinue)) {
  Write-Host 'autosd command not found.' -ForegroundColor Red
  Write-Host 'Install with: py -3.11 -m pip install -e .[dev]' -ForegroundColor Yellow
  exit 1
}

autosd ui serve @args
exit $LASTEXITCODE
""",
        encoding="utf-8",
    )

    bat_path.write_text(
        """@echo off
setlocal
set SCRIPT_DIR=%~dp0
for %%I in ("%SCRIPT_DIR%..") do set REPO_ROOT=%%~fI
cd /d "%REPO_ROOT%"
title AutoSD UI Launcher
where autosd >nul 2>&1
if errorlevel 1 (
  echo autosd command not found.
  echo Install with: py -3.11 -m pip install -e .[dev]
  exit /b 1
)
autosd ui serve %*
exit /b %errorlevel%
""",
        encoding="utf-8",
    )
    return ps1_path, bat_path


def install_windows_shortcuts(
    *,
    repo_root: Path,
    run_command: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
) -> list[Path]:
    """Install or update per-user desktop launcher shortcuts for Windows."""
    if sys.platform != "win32":
        raise UICommandError("Shortcut installation is only supported on Windows.")

    ps1_path, bat_path = write_windows_launchers(repo_root)
    desktop = resolve_windows_desktop_path()
    lnk_path = desktop / "AutoSD UI.lnk"
    fallback_bat = desktop / "AutoSD UI.bat"
    icon_path = repo_root / "ui" / "frontend" / "public" / "favicon.ico"

    runner = run_command or _run_powershell
    quoted_lnk = _powershell_single_quote(str(lnk_path))
    quoted_ps1 = _powershell_single_quote(str(ps1_path))
    quoted_repo = _powershell_single_quote(str(repo_root))
    script_lines = [
        "$shell = New-Object -ComObject WScript.Shell",
        f"$shortcut = $shell.CreateShortcut('{quoted_lnk}')",
        "$shortcut.TargetPath = 'powershell.exe'",
        f"$shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -File \"{quoted_ps1}\"'",
        f"$shortcut.WorkingDirectory = '{quoted_repo}'",
        "$shortcut.Description = 'Launch AutoSD UI'",
    ]
    if icon_path.exists():
        quoted_icon = _powershell_single_quote(str(icon_path))
        script_lines.append(f"$shortcut.IconLocation = '{quoted_icon}'")
    script_lines.extend(["$shortcut.Save()"])

    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        "\n".join(script_lines),
    ]

    result = runner(command)
    installed: list[Path] = []
    if result.returncode == 0:
        installed.append(lnk_path)
    else:
        shutil.copy2(bat_path, fallback_bat)
        installed.append(fallback_bat)
    return installed


def remove_windows_shortcuts() -> list[Path]:
    """Remove installed desktop shortcut artifacts when present."""
    if sys.platform != "win32":
        raise UICommandError("Shortcut removal is only supported on Windows.")
    desktop = resolve_windows_desktop_path()
    targets = [desktop / "AutoSD UI.lnk", desktop / "AutoSD UI.bat"]
    removed: list[Path] = []
    for path in targets:
        if path.exists():
            path.unlink()
            removed.append(path)
    return removed


def _run_powershell(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Execute PowerShell command helper for link creation."""
    return subprocess.run(command, check=False, capture_output=True, text=True)  # nosec B603


def _powershell_single_quote(value: str) -> str:
    """Escape single quotes for PowerShell single-quoted string literals."""
    return value.replace("'", "''")
