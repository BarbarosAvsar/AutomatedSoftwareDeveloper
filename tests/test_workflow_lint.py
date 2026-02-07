"""Tests for workflow linting rules."""

from __future__ import annotations

from pathlib import Path

from automated_software_developer.agent.ci.workflow_lint import validate_workflow


def _write(workflow_path: Path, content: str) -> Path:
    workflow_path.write_text(content, encoding="utf-8")
    return workflow_path


def test_duplicate_keys_detected(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / "ci.yml",
        "name: CI\nname: CI2\non: [push]\njobs: {}\npermissions: {contents: read}\n",
    )
    errors = validate_workflow(workflow)
    assert any(error.startswith("duplicate_key:") for error in errors)


def test_missing_required_fields(tmp_path: Path) -> None:
    workflow = _write(tmp_path / "ci.yml", "name: CI\njobs: {}\npermissions: {contents: read}\n")
    errors = validate_workflow(workflow)
    assert "missing_on" in errors


def test_unpinned_action_and_permissions(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / "ci.yml",
        """
name: CI
on: [push]
permissions: {contents: read}
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
""",
    )
    errors = validate_workflow(workflow)
    assert any(error.startswith("unpin_action") for error in errors)


def test_banned_secret_echo_and_env_dump(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / "ci.yml",
        """
name: CI
on: [push]
permissions: {contents: read}
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Unsafe
        run: |
          set -x
          echo ${{ secrets.TOKEN }}
""",
    )
    errors = validate_workflow(workflow)
    assert "unsafe_set_x" in errors
    assert "unsafe_echo_secrets" in errors


def test_valid_workflow_passes(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / "ci.yml",
        """
name: CI
on: [push]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5
      - name: Run
        run: echo "ok"
""",
    )
    errors = validate_workflow(workflow)
    assert errors == []
