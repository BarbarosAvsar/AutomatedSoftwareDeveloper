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


def test_build_artifact_checksums_ignores_ephemeral_artifacts(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / ".ruff_cache").mkdir()
    (tmp_path / ".ruff_cache" / "cache").write_text("ruff\n", encoding="utf-8")
    (tmp_path / ".mypy_cache").mkdir()
    (tmp_path / ".mypy_cache" / "cache").write_text("mypy\n", encoding="utf-8")
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "artifact.whl").write_text("dist\n", encoding="utf-8")
    egg_info = tmp_path / "sample.egg-info"
    egg_info.mkdir()
    (egg_info / "PKG-INFO").write_text("metadata\n", encoding="utf-8")

    checksums = build_artifact_checksums(tmp_path)

    assert "main.py" in checksums
    assert ".ruff_cache/cache" not in checksums
    assert ".mypy_cache/cache" not in checksums
    assert "dist/artifact.whl" not in checksums
    assert "sample.egg-info/PKG-INFO" not in checksums


def test_build_artifact_checksums_ignores_autosd_runtime_logs(tmp_path: Path) -> None:
    (tmp_path / ".autosd" / "provenance").mkdir(parents=True)
    (tmp_path / ".autosd" / "sprint_log.jsonl").write_text('{"event":"a"}\n', encoding="utf-8")
    (tmp_path / ".autosd" / "prompt_journal.jsonl").write_text('{"event":"b"}\n', encoding="utf-8")
    (tmp_path / ".autosd" / "provenance" / "quality_gate_cache.json").write_text(
        "{}",
        encoding="utf-8",
    )
    (tmp_path / ".autosd" / "provenance" / "build_manifest.json").write_text(
        "{}",
        encoding="utf-8",
    )

    checksums = build_artifact_checksums(tmp_path)

    assert ".autosd/sprint_log.jsonl" not in checksums
    assert ".autosd/prompt_journal.jsonl" not in checksums
    assert ".autosd/provenance/quality_gate_cache.json" not in checksums
    assert ".autosd/provenance/build_manifest.json" in checksums
