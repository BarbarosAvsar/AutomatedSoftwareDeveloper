"""Fixture definitions for software factory conformance runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConformanceFixture:
    """Metadata for a single conformance fixture run."""

    fixture_id: str
    requirements_path: Path
    mock_responses_path: Path
    expected_adapter_id: str
    required_paths: list[str]
    requires_strict_typing: bool = False
    security_scan_mode: str = "if-available"


def load_fixtures() -> list[ConformanceFixture]:
    """Load the canonical set of conformance fixtures."""
    root = _repo_root()
    requirements_dir = root / "conformance" / "requirements"
    return [
        ConformanceFixture(
            fixture_id="api_service",
            requirements_path=requirements_dir / "api_service.md",
            mock_responses_path=requirements_dir / "api_service.mock.json",
            expected_adapter_id="api_service",
            required_paths=[
                "README.md",
                "api/README.md",
                "ci/run_ci.sh",
                ".github/workflows/ci.yml",
            ],
        ),
        ConformanceFixture(
            fixture_id="cli_tool",
            requirements_path=requirements_dir / "cli_tool.md",
            mock_responses_path=requirements_dir / "cli_tool.mock.json",
            expected_adapter_id="cli_tool",
            required_paths=[
                "README.md",
                "cli/README.md",
                "ci/run_ci.sh",
                ".github/workflows/ci.yml",
            ],
        ),
        ConformanceFixture(
            fixture_id="web_app",
            requirements_path=requirements_dir / "web_app.md",
            mock_responses_path=requirements_dir / "web_app.mock.json",
            expected_adapter_id="web_app",
            required_paths=[
                "README.md",
                "frontend/README.md",
                "ci/run_ci.sh",
                ".github/workflows/ci.yml",
                "frontend/index.html",
            ],
        ),
        ConformanceFixture(
            fixture_id="edge_case",
            requirements_path=requirements_dir / "edge_case.md",
            mock_responses_path=requirements_dir / "edge_case.mock.json",
            expected_adapter_id="cli_tool",
            required_paths=[
                "README.md",
                "ci/run_ci.sh",
                ".github/workflows/ci.yml",
                "mypy.ini",
            ],
            requires_strict_typing=True,
            security_scan_mode="required",
        ),
    ]


def _repo_root() -> Path:
    """Resolve the repository root based on this file location."""
    return Path(__file__).resolve().parents[3]
