"""Build provenance and reproducibility artifact helpers."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BuildManifest:
    """Build manifest captured for reproducibility and auditability."""

    project_id: str
    version: str
    commit_sha: str | None
    tag: str | None
    gates_run: list[str]
    reproducible: bool
    tool_versions: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize build manifest object."""
        return {
            "project_id": self.project_id,
            "version": self.version,
            "commit_sha": self.commit_sha,
            "tag": self.tag,
            "gates_run": self.gates_run,
            "reproducible": self.reproducible,
            "tool_versions": self.tool_versions,
        }


def write_build_manifest(project_dir: Path, manifest: BuildManifest) -> Path:
    """Write build manifest to project provenance artifact path."""
    output_path = project_dir / ".autosd" / "provenance" / "build_manifest.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
    return output_path


def maybe_write_sbom(project_dir: Path, *, mode: str) -> Path | None:
    """Write lightweight SBOM when dependencies are discoverable."""
    if mode == "off":
        return None
    dependencies = _collect_dependencies(project_dir)
    if not dependencies:
        if mode == "required":
            raise RuntimeError("SBOM mode is required but no dependencies could be discovered.")
        return None
    payload = {
        "format": "lightweight-json",
        "dependencies": dependencies,
    }
    output_path = project_dir / ".autosd" / "provenance" / "sbom.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def gather_tool_versions() -> dict[str, str]:
    """Collect core tool versions for provenance manifest."""
    versions = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "implementation": platform.python_implementation(),
        "executable": sys.executable,
    }
    for package in ("ruff", "mypy", "pytest", "bandit"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def _collect_dependencies(project_dir: Path) -> list[str]:
    """Collect dependencies from requirements and pyproject when present."""
    dependencies: list[str] = []
    requirements = project_dir / "requirements.txt"
    if requirements.exists():
        for line in requirements.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            dependencies.append(stripped)

    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        import tomllib

        payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        project = payload.get("project")
        if isinstance(project, dict):
            deps = project.get("dependencies")
            if isinstance(deps, list):
                for item in deps:
                    if isinstance(item, str) and item.strip():
                        dependencies.append(item.strip())
    seen: set[str] = set()
    output: list[str] = []
    for dep in dependencies:
        if dep in seen:
            continue
        seen.add(dep)
        output.append(dep)
    return output
