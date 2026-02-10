"""Deterministic build helpers for reproducible runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

LOCKFILE_CANDIDATES = (
    "poetry.lock",
    "pdm.lock",
    "uv.lock",
    "Pipfile.lock",
    "requirements.lock",
    "requirements.txt",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Cargo.lock",
    "go.sum",
    "composer.lock",
)

IGNORED_REPRODUCIBILITY_PATHS = {
    ".autosd/sprint_log.jsonl",
    ".autosd/prompt_journal.jsonl",
    ".autosd/provenance/quality_gate_cache.json",
}

IGNORED_ARTIFACT_DIRS = {
    ".git",
    ".ruff_cache",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "dist",
    "build",
    ".venv",
    "venv",
}


def derive_prompt_seed(prompt_fingerprint: str, base_seed: int) -> int:
    """Derive a stable seed for a prompt from its fingerprint."""
    digest = hashlib.sha256(f"{base_seed}:{prompt_fingerprint}".encode()).hexdigest()
    return int(digest[:8], 16)


def enforce_lockfiles(project_dir: Path, *, reproducible: bool) -> list[str]:
    """Ensure lockfiles are present and pinned when reproducible mode is enabled."""
    if not reproducible:
        return []
    lockfiles: list[Path] = []
    for candidate in LOCKFILE_CANDIDATES:
        path = project_dir / candidate
        if path.exists():
            lockfiles.append(path)
    if not lockfiles:
        raise RuntimeError("Reproducible mode requires a lockfile in the project root.")

    requirements_path = project_dir / "requirements.txt"
    if requirements_path.exists():
        requirements_text = requirements_path.read_text(encoding="utf-8")
        if not _requirements_are_pinned(requirements_text):
            raise RuntimeError(
                "requirements.txt must pin versions (== or @) when reproducible mode is enabled."
            )
    return [str(path.relative_to(project_dir)).replace("\\", "/") for path in lockfiles]


def build_artifact_checksums(project_dir: Path) -> dict[str, str]:
    """Compute SHA-256 checksums for all project files."""
    checksums: dict[str, str] = {}
    for path in sorted(project_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(project_dir)
        if _should_ignore_artifact(relative):
            continue
        if relative.as_posix() == ".autosd/provenance/build_hash.json":
            continue
        checksum = _hash_file(path)
        checksums[relative.as_posix()] = checksum
    return checksums


def compute_build_hash(checksums: dict[str, str]) -> str:
    """Compute a deterministic build hash from file checksums."""
    digest = hashlib.sha256()
    for path in sorted(checksums):
        digest.update(f"{path}:{checksums[path]}".encode())
    return digest.hexdigest()


def write_build_hash(
    project_dir: Path,
    *,
    checksums: dict[str, str],
    seed: int | None,
    lockfiles: list[str],
) -> Path:
    """Write deterministic build hash artifact."""
    build_hash = compute_build_hash(checksums)
    payload = {
        "build_hash": build_hash,
        "seed": seed,
        "lockfiles": lockfiles,
        "artifact_checksums": checksums,
    }
    output_path = project_dir / ".autosd" / "provenance" / "build_hash.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def _requirements_are_pinned(text: str) -> bool:
    """Return True when all dependency lines are pinned."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "==" not in stripped and "@" not in stripped:
            return False
    return True


def _hash_file(path: Path) -> str:
    """Hash file contents using SHA-256."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _should_ignore_artifact(relative: Path) -> bool:
    """Return True when a file should be excluded from reproducibility checks."""
    relative_posix = relative.as_posix()
    if relative_posix in IGNORED_REPRODUCIBILITY_PATHS:
        return True
    if any(part in IGNORED_ARTIFACT_DIRS for part in relative.parts):
        return True
    return any(part.endswith(".egg-info") for part in relative.parts)
