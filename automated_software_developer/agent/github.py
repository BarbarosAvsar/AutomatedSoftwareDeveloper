"""GitHub and repository scaffolding helpers."""

from __future__ import annotations

from automated_software_developer.agent.filesystem import FileWorkspace

DEFAULT_GITIGNORE = """
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
""".strip() + "\n"


DEFAULT_PYTHON_CI_WORKFLOW = """
name: CI

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install
        run: |
          python -m pip install --upgrade pip
          if [ -f pyproject.toml ]; then pip install -e .[dev] || pip install -e .; fi
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
      - name: Lint
        run: |
          if command -v ruff >/dev/null 2>&1; then
            ruff check .
          else
            echo "ruff not installed, skipping"
          fi
      - name: Test
        run: |
          if [ -f pytest.ini ] || [ -d tests ]; then
            python -m pytest -q
          else
            echo "No tests found"
          fi
""".strip() + "\n"


def ensure_repository_scaffold(workspace: FileWorkspace) -> None:
    """Create baseline GitHub-friendly files if absent."""
    if workspace.read_optional(".gitignore") is None:
        workspace.write_file(".gitignore", DEFAULT_GITIGNORE)
    if workspace.read_optional(".github/workflows/ci.yml") is None:
        workspace.write_file(".github/workflows/ci.yml", DEFAULT_PYTHON_CI_WORKFLOW)


def compose_commit_message(milestone: str, changed_files: list[str]) -> str:
    """Generate a concise conventional-style commit message."""
    scope = milestone.lower().replace(" ", "-")
    count = len(changed_files)
    return f"feat({scope}): apply {count} file updates"
