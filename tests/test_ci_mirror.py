"""Tests for CI mirror runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from automated_software_developer.agent.ci.mirror import run_ci_mirror


def test_ci_mirror_runs_entrypoint(tmp_path: Path) -> None:
    ci_dir = tmp_path / "ci"
    ci_dir.mkdir()
    script = ci_dir / "run_ci.sh"
    script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)

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

    result = run_ci_mirror(tmp_path)
    assert result.passed is True
    assert result.exit_code == 0
