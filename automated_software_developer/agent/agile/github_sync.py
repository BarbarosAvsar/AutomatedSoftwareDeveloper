"""GitHub Projects sync for Scrum backlog and sprints."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from automated_software_developer.agent.agile.backlog import AgileBacklog
from automated_software_developer.agent.agile.sprint_engine import SprintPlan


class HttpClient(Protocol):
    """Minimal HTTP client protocol for GitHub API interactions."""

    def post(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> Any: ...


@dataclass(frozen=True)
class GitHubProjectConfig:
    """GitHub Project sync configuration."""

    repo: str
    project_number: int
    token: str | None = None
    api_url: str = "https://api.github.com"
    dry_run: bool = True

    def __post_init__(self) -> None:
        if not self.repo:
            raise ValueError("repo must be provided.")
        if self.project_number <= 0:
            raise ValueError("project_number must be greater than zero.")


class GitHubProjectSync:
    """Synchronize backlog and sprint to GitHub Projects."""

    def __init__(
        self,
        config: GitHubProjectConfig,
        *,
        client: HttpClient | None = None,
        log_path: Path | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self.log_path = log_path or Path(".autosd/github_sync.json")

    def sync_backlog(self, backlog: AgileBacklog) -> dict[str, Any]:
        """Sync backlog items to GitHub Projects."""
        payload = {
            "repo": self.config.repo,
            "project_number": self.config.project_number,
            "stories": [story.story_id for story in backlog.stories],
        }
        return self._dispatch("backlog", payload)

    def sync_sprint(self, sprint: SprintPlan) -> dict[str, Any]:
        """Sync sprint plan to GitHub Projects."""
        payload = {
            "repo": self.config.repo,
            "project_number": self.config.project_number,
            "sprint_id": sprint.sprint_id,
            "stories": [story.story_id for story in sprint.stories],
            "status": sprint.status,
        }
        return self._dispatch("sprint", payload)

    def _dispatch(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.config.dry_run or self.config.token is None or self.client is None:
            self._log_action(action, payload)
            return {"status": "dry_run", "action": action, "payload": payload}
        url = (
            f"{self.config.api_url}/repos/{self.config.repo}/projects/"
            f"{self.config.project_number}"
        )
        headers = {"Authorization": f"Bearer {self.config.token}"}
        response = self.client.post(url, headers=headers, json={"action": action, **payload})
        return {"status": "submitted", "response": response}

    def _log_action(self, action: str, payload: dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {"action": action, "payload": payload}
        self.log_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
