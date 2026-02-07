"""Tests for reproducibility helpers."""

from __future__ import annotations

import json
from pathlib import Path

from automated_software_developer.agent.reproducibility import (
    build_artifact_checksums,
    enforce_lockfiles,
    write_build_hash,
)


def _read_build_hash(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload["build_hash"])


def test_build_hash_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("requests==1.0.0\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")

    lockfiles = enforce_lockfiles(tmp_path, reproducible=True)
    first_checksums = build_artifact_checksums(tmp_path)
    first_path = write_build_hash(
        tmp_path,
        checksums=first_checksums,
        seed=4242,
        lockfiles=lockfiles,
    )
    second_checksums = build_artifact_checksums(tmp_path)
    second_path = write_build_hash(
        tmp_path,
        checksums=second_checksums,
        seed=4242,
        lockfiles=lockfiles,
    )

    assert _read_build_hash(first_path) == _read_build_hash(second_path)
