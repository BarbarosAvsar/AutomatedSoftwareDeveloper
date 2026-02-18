"""Tests for CI mirror runner."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from automated_software_developer.agent.ci.mirror import run_ci_mirror


def test_ci_mirror_runs_entrypoint(tmp_path: Path) -> None:
    ci_dir = tmp_path / "ci"
    ci_dir.mkdir()
    script = ci_dir / "run_ci.sh"
    script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)
    (ci_dir / "run_ci.py").write_text("print('ok')\n", encoding="utf-8")

    result = run_ci_mirror(tmp_path)
    assert result.passed is True
    assert result.exit_code == 0


def test_ci_mirror_requires_entrypoint(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        run_ci_mirror(tmp_path)


def test_ci_mirror_runs_without_execute_bit(tmp_path: Path) -> None:
    ci_dir = tmp_path / "ci"
    ci_dir.mkdir()
    script = ci_dir / "run_ci.sh"
    script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (ci_dir / "run_ci.py").write_text("print('ok')\n", encoding="utf-8")

    result = run_ci_mirror(tmp_path)
    assert result.passed is True
    assert result.exit_code == 0


def test_ci_mirror_uses_python_fallback_when_bash_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ci_dir = tmp_path / "ci"
    ci_dir.mkdir()
    script = ci_dir / "run_ci.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setattr("automated_software_developer.agent.ci.mirror.which", lambda _: None)

    result = run_ci_mirror(tmp_path)
    assert result.command == f"{sys.executable} ./ci/run_ci.py"
    assert result.passed is True


def test_ci_mirror_requires_python_fallback_when_bash_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ci_dir = tmp_path / "ci"
    ci_dir.mkdir()
    script = ci_dir / "run_ci.sh"
    script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    monkeypatch.setattr("automated_software_developer.agent.ci.mirror.which", lambda _: None)
    with pytest.raises(ValueError):
        run_ci_mirror(tmp_path)
