"""Tests for AutoSD UI serve and Windows shortcut helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from automated_software_developer.cli import app
from automated_software_developer.ui_cli import (
    UICommandError,
    UIServeConfig,
    build_ui_serve_plan,
    ensure_frontend_dependencies,
    ensure_port_available,
    install_windows_shortcuts,
    resolve_windows_desktop_path,
    write_windows_launchers,
)


def test_ui_serve_cli_defaults() -> None:
    """The UI serve command should expose expected defaults."""
    runner = CliRunner()
    result = runner.invoke(app, ["ui", "serve", "--help"])
    assert result.exit_code == 0
    assert "127.0.0.1" in result.stdout
    assert "8080" in result.stdout
    assert "5173" in result.stdout


def test_build_ui_serve_plan_defaults() -> None:
    """UI serve plan should include backend/frontend defaults and reload mode."""
    plan = build_ui_serve_plan(UIServeConfig(), npm_path="/usr/bin/npm")
    command_head = plan.backend_command[:3]
    assert command_head == ["python", "-m", "uvicorn"] or command_head[1:3] == ["-m", "uvicorn"]
    assert "--reload" in plan.backend_command
    assert plan.frontend_command[0] == "/usr/bin/npm"
    assert plan.frontend_command[-1] == "5173"
    assert plan.frontend_url == "http://127.0.0.1:5173"


def test_ensure_frontend_dependencies_missing_without_install(tmp_path: Path) -> None:
    """Missing frontend dependencies should fail fast when install flag is false."""
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    with pytest.raises(UICommandError):
        ensure_frontend_dependencies(frontend_dir, install=False, npm_path="/usr/bin/npm")


def test_ensure_frontend_dependencies_installs_with_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Frontend dependencies should invoke npm install when requested."""
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()

    calls: list[list[str]] = []

    def fake_run(
        args: list[str],
        cwd: Path,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert check is False
        assert capture_output is True
        assert text is True
        calls.append(args)
        (cwd / "node_modules").mkdir()
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("automated_software_developer.ui_cli.subprocess.run", fake_run)

    ensure_frontend_dependencies(frontend_dir, install=True, npm_path="/usr/bin/npm")
    assert calls == [["/usr/bin/npm", "install"]]


def test_ensure_port_available_rejects_bound_port() -> None:
    """Port validation should reject ports already in use."""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    try:
        with pytest.raises(UICommandError):
            ensure_port_available("127.0.0.1", port)
    finally:
        sock.close()


def test_resolve_windows_desktop_path_prefers_userprofile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Desktop path resolver should prioritize USERPROFILE desktop when present."""
    user_desktop = tmp_path / "user" / "Desktop"
    user_desktop.mkdir(parents=True)
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "user"))
    monkeypatch.delenv("OneDrive", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

    resolved = resolve_windows_desktop_path()
    assert resolved == user_desktop


def test_write_windows_launchers(tmp_path: Path) -> None:
    """Launcher script generation should create .ps1 and .bat files."""
    ps1_path, bat_path = write_windows_launchers(tmp_path)
    assert ps1_path.exists()
    assert bat_path.exists()
    assert "autosd ui serve" in ps1_path.read_text(encoding="utf-8")
    assert "autosd ui serve" in bat_path.read_text(encoding="utf-8")


def test_install_windows_shortcuts_fallback_to_bat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shortcut install should fallback to desktop .bat when COM creation fails."""
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr("automated_software_developer.ui_cli.sys.platform", "win32")

    def fake_runner(_: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["powershell"], returncode=1, stdout="", stderr="")

    installed = install_windows_shortcuts(repo_root=tmp_path, run_command=fake_runner)
    assert installed == [desktop / "AutoSD UI.bat"]
    assert installed[0].exists()


def test_install_windows_shortcuts_lnk_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shortcut installer should return .lnk path on successful COM script execution."""
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr("automated_software_developer.ui_cli.sys.platform", "win32")

    def fake_runner(_: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["powershell"], returncode=0, stdout="", stderr="")

    installed = install_windows_shortcuts(repo_root=tmp_path, run_command=fake_runner)
    assert installed == [desktop / "AutoSD UI.lnk"]


def test_ensure_python_version_with_supported_runtime() -> None:
    """Python version guard should accept current supported interpreter."""
    from automated_software_developer.ui_cli import ensure_python_version

    ensure_python_version()


def test_ensure_tooling_available_missing_node(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tooling validation should fail with actionable error when npm/node are absent."""
    monkeypatch.setattr("automated_software_developer.ui_cli.shutil.which", lambda _: None)

    from automated_software_developer.ui_cli import ensure_tooling_available

    with pytest.raises(UICommandError):
        ensure_tooling_available()


def test_install_windows_shortcuts_non_windows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Shortcut installation should reject non-Windows platforms."""
    monkeypatch.setattr("automated_software_developer.ui_cli.sys.platform", "linux")
    with pytest.raises(UICommandError):
        install_windows_shortcuts(repo_root=tmp_path)
