"""Tests for GitOps helpers and patch engine orchestration."""

from __future__ import annotations

from pathlib import Path

import pytest

from automated_software_developer.agent.gitops import GitOpsManager
from automated_software_developer.agent.patching import (
    PatchEngine,
    PatchFilters,
    bump_semver,
    classify_change_reason,
)
from automated_software_developer.agent.portfolio.registry import PortfolioRegistry


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    manager = GitOpsManager()
    manager.ensure_repository(path)
    (path / "README.md").write_text("# Repo\n", encoding="utf-8")
    manager.commit_push_tag(
        repo_dir=path,
        message="chore: init",
        branch=manager.current_branch(path),
        auto_push=False,
        tag=None,
    )


def test_gitops_commit_and_push_gating(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    manager = GitOpsManager()

    (repo / "notes.txt").write_text("hello\n", encoding="utf-8")
    result = manager.commit_push_tag(
        repo_dir=repo,
        message="feat: notes",
        branch=manager.current_branch(repo),
        auto_push=False,
        tag="v0.1.1",
    )
    assert result.committed is True
    assert result.pending_push is True
    assert result.commit_sha is not None

    with pytest.raises(RuntimeError):
        manager.commit_push_tag(
            repo_dir=repo,
            message="feat: force push",
            branch=manager.current_branch(repo),
            auto_push=True,
            tag=None,
        )


def test_patch_engine_batch_updates_registry_and_changelog(tmp_path: Path) -> None:
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    _init_repo(repo_a)
    _init_repo(repo_b)

    registry_path = tmp_path / "registry.jsonl"
    registry = PortfolioRegistry(write_path=registry_path, read_paths=[registry_path])
    registry.register_project(
        project_id="a",
        name="Project A",
        domain="commerce",
        platforms=["web_app"],
    )
    registry.register_project(
        project_id="b",
        name="Project B",
        domain="internal",
        platforms=["cli_tool"],
    )
    registry.update("a", metadata={"local_path": str(repo_a), "needs_upgrade": "true"})
    registry.update("b", metadata={"local_path": str(repo_b), "needs_upgrade": "false"})

    engine = PatchEngine(registry=registry)
    outcomes = engine.patch_all(
        reason="security fix",
        filters=PatchFilters(domain="commerce", needs_upgrade=True),
        auto_push=False,
        create_tag=True,
    )

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.project_id == "a"
    assert outcome.success is True
    assert outcome.new_version == "0.1.1"

    entry = registry.get("a")
    assert entry is not None
    assert entry.current_version == "0.1.1"
    changelog_dir = repo_a / ".autosd" / "changelogs"
    assert changelog_dir.exists()
    assert any(path.suffix == ".md" for path in changelog_dir.iterdir())


def test_patch_engine_marks_failure_on_push_without_remote(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    registry_path = tmp_path / "registry.jsonl"
    registry = PortfolioRegistry(write_path=registry_path, read_paths=[registry_path])
    registry.register_project(
        project_id="push-fail",
        name="Push Fail",
        domain="ops",
        platforms=["api_service"],
    )
    registry.update("push-fail", metadata={"local_path": str(repo)})

    engine = PatchEngine(registry=registry)
    outcome = engine.patch_project(
        "push-fail",
        reason="maintenance",
        auto_push=True,
        create_tag=False,
    )
    assert outcome.success is False
    assert outcome.error is not None


def test_semver_classifier_helpers() -> None:
    assert classify_change_reason("breaking migration") == "major"
    assert classify_change_reason("minor feature") == "minor"
    assert classify_change_reason("security patch") == "patch"
    assert bump_semver("1.2.3", "major") == "2.0.0"
    assert bump_semver("1.2.3", "minor") == "1.3.0"
    assert bump_semver("1.2.3", "patch") == "1.2.4"
