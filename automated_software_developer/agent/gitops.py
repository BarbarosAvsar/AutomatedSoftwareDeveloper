"""Deterministic GitOps helpers for local commit/push/tag automation."""

from __future__ import annotations

import shutil
import subprocess  # nosec B404
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitOperationResult:
    """Result summary for a commit/push/tag GitOps operation."""

    committed: bool
    commit_sha: str | None
    pushed: bool
    tag: str | None
    pending_push: bool
    branch: str | None


class GitOpsManager:
    """Runs non-interactive Git operations with safe defaults."""

    def ensure_repository(self, repo_dir: Path) -> None:
        """Initialize a git repository if one is not already present."""
        if (repo_dir / ".git").exists():
            return
        self._run_git(repo_dir, ["init"])

    def current_branch(self, repo_dir: Path) -> str | None:
        """Return current git branch or None when unavailable."""
        result = self._run_git(repo_dir, ["branch", "--show-current"], check=False)
        branch = result.stdout.strip()
        return branch or None

    def current_commit(self, repo_dir: Path) -> str | None:
        """Return current commit SHA if repository has commits."""
        result = self._run_git(repo_dir, ["rev-parse", "HEAD"], check=False)
        commit_sha = result.stdout.strip()
        return commit_sha or None

    def checkout_new_branch(self, repo_dir: Path, branch_name: str) -> None:
        """Create and check out a new branch."""
        self._run_git(repo_dir, ["checkout", "-b", branch_name])

    def has_changes(self, repo_dir: Path) -> bool:
        """Return whether repository has staged or unstaged changes."""
        result = self._run_git(repo_dir, ["status", "--porcelain"], check=False)
        return bool(result.stdout.strip())

    def has_remote(self, repo_dir: Path) -> bool:
        """Return whether repository has an origin remote configured."""
        result = self._run_git(repo_dir, ["remote", "get-url", "origin"], check=False)
        return result.returncode == 0 and bool(result.stdout.strip())

    def commit_push_tag(
        self,
        *,
        repo_dir: Path,
        message: str,
        branch: str | None,
        auto_push: bool,
        tag: str | None,
    ) -> GitOperationResult:
        """Commit all changes and optionally push/tag based on configuration."""
        self.ensure_repository(repo_dir)
        self._ensure_local_identity(repo_dir)
        self._run_git(repo_dir, ["add", "-A"])
        committed = False
        commit_sha: str | None = None
        if self.has_changes(repo_dir):
            self._run_git(repo_dir, ["commit", "-m", message])
            committed = True
            commit_sha = self._run_git(repo_dir, ["rev-parse", "HEAD"]).stdout.strip() or None

        pushed = False
        pending_push = False
        effective_branch = branch or self.current_branch(repo_dir)
        if auto_push:
            if not self.has_remote(repo_dir):
                raise RuntimeError(
                    "Push requested but no 'origin' remote is configured for repository."
                )
            if effective_branch is None:
                raise RuntimeError("Push requested but current branch could not be resolved.")
            self._run_git(repo_dir, ["push", "-u", "origin", effective_branch])
            pushed = True
        elif committed:
            pending_push = True

        if tag is not None:
            self._run_git(repo_dir, ["tag", "-f", tag])
            if auto_push:
                self._run_git(repo_dir, ["push", "origin", tag])

        return GitOperationResult(
            committed=committed,
            commit_sha=commit_sha,
            pushed=pushed,
            tag=tag,
            pending_push=pending_push,
            branch=effective_branch,
        )

    def _ensure_local_identity(self, repo_dir: Path) -> None:
        """Ensure repository has local git user identity configured for commits."""
        email = self._run_git(repo_dir, ["config", "user.email"], check=False).stdout.strip()
        if not email:
            self._run_git(repo_dir, ["config", "user.email", "autosd@local.invalid"])
        name = self._run_git(repo_dir, ["config", "user.name"], check=False).stdout.strip()
        if not name:
            self._run_git(repo_dir, ["config", "user.name", "AutoSD Bot"])

    def _run_git(
        self,
        repo_dir: Path,
        args: list[str],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command in repository directory."""
        git_path = shutil.which("git")
        if git_path is None:
            raise RuntimeError("git executable not found on PATH.")
        completed = subprocess.run(  # nosec B603
            [git_path, *args],
            cwd=str(repo_dir),
            check=False,
            text=True,
            capture_output=True,
        )
        if check and completed.returncode != 0:
            command_text = "git " + " ".join(args)
            raise RuntimeError(
                f"Git command failed ({command_text}):\n"
                f"stdout: {completed.stdout.strip()}\n"
                f"stderr: {completed.stderr.strip()}"
            )
        return completed
