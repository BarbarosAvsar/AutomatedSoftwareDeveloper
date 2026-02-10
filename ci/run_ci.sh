#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -e .[dev,security]

python -m ruff check .
python -m mypy automated_software_developer
python -m pytest --cov=automated_software_developer --cov-report=term-missing --cov-fail-under=79
python -m pip_audit --progress-spinner off
