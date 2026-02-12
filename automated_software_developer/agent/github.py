"""GitHub and repository scaffolding helpers."""

from __future__ import annotations

from automated_software_developer.agent.filesystem import FileWorkspace

DEFAULT_GITIGNORE = (
    """
# Python cache/artifacts
__pycache__/
*.py[cod]
*.so
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
coverage.xml

# Environments
.venv/
venv/
env/

# OS/editor
.DS_Store
Thumbs.db
.idea/
.vscode/
""".strip()
    + "\n"
)

DEFAULT_CI_ENTRYPOINT = (
    """#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip

if [ -f pyproject.toml ]; then
  python -m pip install -e .[dev] || python -m pip install -e .
fi

if [ -f requirements.txt ]; then
  python -m pip install -r requirements.txt
fi

python -m compileall -q .

if python - <<'PY'
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("ruff") else 1)
PY
then
  python -m ruff format --check .
  python -m ruff check .
else
  echo "ruff not installed; skipping format/lint"
fi

if python - <<'PY'
import importlib.util
from pathlib import Path

if not importlib.util.find_spec("mypy"):
    raise SystemExit(1)

paths = [Path("mypy.ini"), Path("setup.cfg"), Path("pyproject.toml")]
if paths[0].exists():
    raise SystemExit(0)
if paths[1].exists() and "[mypy" in paths[1].read_text(encoding="utf-8", errors="ignore").lower():
    raise SystemExit(0)
if paths[2].exists() and "[tool.mypy]" in paths[2].read_text(
    encoding="utf-8",
    errors="ignore",
).lower():
    raise SystemExit(0)
raise SystemExit(1)
PY
then
  python -m mypy .
else
  echo "mypy not configured; skipping type check"
fi

if [ -d tests ] || [ -f pytest.ini ] || [ -f pyproject.toml ]; then
  if python - <<'PY'
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("pytest") else 1)
PY
  then
    python -m pytest -q
  else
    echo "pytest not installed; skipping tests"
  fi
else
  echo "No tests found"
fi

if python - <<'PY'
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("build") else 1)
PY
then
  python -m build
else
  echo "build module not available; skipping package build"
fi
""".strip()
    + "\n"
)

DEFAULT_PYTHON_CI_WORKFLOW = (
    """
name: CI

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

permissions:
  contents: read

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5
      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065
        with:
          python-version: "3.12"
          cache: "pip"
          cache-dependency-path: "pyproject.toml"
      - name: Tool versions
        run: |
          python -V
          python -m pip -V
      - name: Run CI entrypoint
        run: ./ci/run_ci.sh
""".strip()
    + "\n"
)


def ensure_repository_scaffold(workspace: FileWorkspace) -> None:
    """Create baseline GitHub-friendly files if absent."""
    if workspace.read_optional(".gitignore") is None:
        workspace.write_file(".gitignore", DEFAULT_GITIGNORE)
    if workspace.read_optional(".github/workflows/ci.yml") is None:
        workspace.write_file(".github/workflows/ci.yml", DEFAULT_PYTHON_CI_WORKFLOW)
    if workspace.read_optional("ci/run_ci.sh") is None:
        workspace.write_file("ci/run_ci.sh", DEFAULT_CI_ENTRYPOINT)
        workspace.set_executable("ci/run_ci.sh")


def compose_commit_message(milestone: str, changed_files: list[str]) -> str:
    """Generate a concise conventional-style commit message."""
    scope = milestone.lower().replace(" ", "-")
    count = len(changed_files)
    return f"feat({scope}): apply {count} file updates"
