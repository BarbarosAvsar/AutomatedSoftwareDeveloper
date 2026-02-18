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

python ci/run_ci.py
""".strip()
    + "\n"
)

DEFAULT_CI_ENTRYPOINT_PY = (
    """
\"\"\"Cross-platform CI entrypoint for generated projects.\"\"\"

from __future__ import annotations

import importlib.util
import subprocess  # nosec B404
import sys
from collections.abc import Sequence
from pathlib import Path


def _run(args: Sequence[str]) -> int:
    \"\"\"Run one command and return its exit code.\"\"\"
    result = subprocess.run(args, check=False)  # nosec B603
    return int(result.returncode)


def _module_available(module: str) -> bool:
    \"\"\"Return whether a module is importable.\"\"\"
    return importlib.util.find_spec(module) is not None


def _has_mypy_config() -> bool:
    \"\"\"Return whether mypy config exists in the project.\"\"\"
    mypy_ini = Path(\"mypy.ini\")
    if mypy_ini.exists():
        return True
    setup_cfg = Path(\"setup.cfg\")
    if setup_cfg.exists():
        content = setup_cfg.read_text(encoding=\"utf-8\", errors=\"ignore\").lower()
        if \"[mypy\" in content:
            return True
    pyproject = Path(\"pyproject.toml\")
    if pyproject.exists():
        content = pyproject.read_text(encoding=\"utf-8\", errors=\"ignore\").lower()
        if \"[tool.mypy]\" in content:
            return True
    return False


def main() -> int:
    \"\"\"Execute generated-project CI checks.\"\"\"
    if _run([sys.executable, \"-m\", \"compileall\", \"-q\", \".\"]) != 0:
        return 1

    if _module_available(\"ruff\"):
        if _run([sys.executable, \"-m\", \"ruff\", \"format\", \"--check\", \".\"]) != 0:
            return 1
        if _run([sys.executable, \"-m\", \"ruff\", \"check\", \".\"]) != 0:
            return 1

    if _module_available(\"mypy\") and _has_mypy_config():
        if _run([sys.executable, \"-m\", \"mypy\", \".\"]) != 0:
            return 1

    has_tests = (
        Path(\"tests\").exists()
        or Path(\"pytest.ini\").exists()
        or Path(\"pyproject.toml\").exists()
    )
    if has_tests and _module_available(\"pytest\"):
        if _run([sys.executable, \"-m\", \"pytest\", \"-q\"]) != 0:
            return 1

    if _module_available(\"build\"):
        if _run([sys.executable, \"-m\", \"build\"]) != 0:
            return 1

    return 0


if __name__ == \"__main__\":
    raise SystemExit(main())
""".strip()
    + "\n"
)

DEFAULT_PYTHON_CI_WORKFLOW = (
    """
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

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
    if workspace.read_optional("ci/run_ci.py") is None:
        workspace.write_file("ci/run_ci.py", DEFAULT_CI_ENTRYPOINT_PY)
    if workspace.read_optional("ci/run_ci.sh") is None:
        workspace.write_file("ci/run_ci.sh", DEFAULT_CI_ENTRYPOINT)
        workspace.set_executable("ci/run_ci.sh")


def compose_commit_message(milestone: str, changed_files: list[str]) -> str:
    """Generate a concise conventional-style commit message."""
    scope = milestone.lower().replace(" ", "-")
    count = len(changed_files)
    return f"feat({scope}): apply {count} file updates"
