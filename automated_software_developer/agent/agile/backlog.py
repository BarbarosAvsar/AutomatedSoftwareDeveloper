"""Backlog generation for autonomous Scrum execution."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from automated_software_developer.agent.models import RefinedRequirements, RefinedStory


@dataclass(frozen=True)
class BacklogTask:
    """Task-level unit of work within a story."""

    task_id: str
    title: str
    description: str
    estimate_hours: int


@dataclass(frozen=True)
class BacklogStoryItem:
    """Story representation for Scrum backlog management."""

    story_id: str
    title: str
    story: str
    acceptance_criteria: list[str]
    nfr_tags: list[str]
    dependencies: list[str]
    tasks: list[BacklogTask]
    estimate_points: int
    priority_score: float
    status: str = "backlog"

    def to_dict(self) -> dict[str, Any]:
        """Serialize story to JSON-compatible dict."""
        return {
            "story_id": self.story_id,
            "title": self.title,
            "story": self.story,
            "acceptance_criteria": self.acceptance_criteria,
            "nfr_tags": self.nfr_tags,
            "dependencies": self.dependencies,
            "tasks": [task.__dict__ for task in self.tasks],
            "estimate_points": self.estimate_points,
            "priority_score": self.priority_score,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BacklogStoryItem:
        """Restore story from serialized data."""
        return _story_from_payload(payload)


@dataclass(frozen=True)
class BacklogEpic:
    """Epic grouping stories for the backlog."""

    epic_id: str
    title: str
    description: str
    story_ids: list[str]


@dataclass(frozen=True)
class AgileBacklog:
    """Scrum backlog data set with epics, stories, and priority ordering."""

    project_name: str
    created_at: str
    epics: list[BacklogEpic]
    stories: list[BacklogStoryItem]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize backlog to a JSON-compatible dict."""
        return {
            "project_name": self.project_name,
            "created_at": self.created_at,
            "metadata": self.metadata,
            "epics": [epic.__dict__ for epic in self.epics],
            "stories": [story.to_dict() for story in self.stories],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AgileBacklog:
        """Create backlog from serialized data."""
        return cls(
            project_name=str(payload["project_name"]),
            created_at=str(payload["created_at"]),
            metadata=dict(payload.get("metadata", {})),
            epics=[BacklogEpic(**epic) for epic in payload.get("epics", [])],
            stories=[_story_from_payload(item) for item in payload.get("stories", [])],
        )


def build_backlog(
    refined: RefinedRequirements,
    *,
    incidents: Iterable[dict[str, Any]] | None = None,
    telemetry_insights: Iterable[dict[str, Any]] | None = None,
) -> AgileBacklog:
    """Convert refined requirements into a structured Scrum backlog."""
    incidents_list = list(incidents or [])
    telemetry_list = list(telemetry_insights or [])
    created_at = datetime.now(tz=UTC).isoformat()
    stories: list[BacklogStoryItem] = []
    epics_map: dict[str, BacklogEpic] = {}

    for story in refined.stories:
        split_stories = _split_story(story)
        for split in split_stories:
            acceptance = split.acceptance_criteria or _generate_acceptance(split)
            tasks = _derive_tasks(split.story_id, acceptance)
            estimate_points = _estimate_story_points(split, tasks)
            priority_score = _priority_score(
                split,
                incidents=incidents_list,
                telemetry=telemetry_list,
            )
            story_item = BacklogStoryItem(
                story_id=split.story_id,
                title=split.title,
                story=split.story,
                acceptance_criteria=acceptance,
                nfr_tags=split.nfr_tags,
                dependencies=split.dependencies,
                tasks=tasks,
                estimate_points=estimate_points,
                priority_score=priority_score,
            )
            stories.append(story_item)
            epic_key = _epic_key(split)
            if epic_key not in epics_map:
                epics_map[epic_key] = BacklogEpic(
                    epic_id=epic_key,
                    title=epic_key.replace("_", " ").title(),
                    description=f"Epic for {epic_key}.",
                    story_ids=[],
                )
            epics_map[epic_key].story_ids.append(story_item.story_id)

    stories_sorted = sorted(stories, key=lambda item: item.priority_score, reverse=True)
    return AgileBacklog(
        project_name=refined.project_name,
        created_at=created_at,
        epics=list(epics_map.values()),
        stories=stories_sorted,
        metadata={
            "total_stories": len(stories_sorted),
            "total_epics": len(epics_map),
        },
    )


def _split_story(story: RefinedStory) -> list[RefinedStory]:
    """Split oversized stories into smaller slices deterministically."""
    acceptance = story.acceptance_criteria
    if len(acceptance) <= 4 and len(story.story) <= 160:
        return [story]
    midpoint = max(1, len(acceptance) // 2)
    parts = [acceptance[:midpoint], acceptance[midpoint:]]
    if not parts[1]:
        return [story]
    return [
        RefinedStory(
            story_id=f"{story.story_id}-a",
            title=f"{story.title} (Part A)",
            story=story.story,
            acceptance_criteria=parts[0],
            nfr_tags=story.nfr_tags,
            dependencies=story.dependencies,
            verification_commands=story.verification_commands,
        ),
        RefinedStory(
            story_id=f"{story.story_id}-b",
            title=f"{story.title} (Part B)",
            story=story.story,
            acceptance_criteria=parts[1],
            nfr_tags=story.nfr_tags,
            dependencies=[f"{story.story_id}-a", *story.dependencies],
            verification_commands=story.verification_commands,
        ),
    ]


def _generate_acceptance(story: RefinedStory) -> list[str]:
    """Generate default acceptance criteria for missing entries."""
    return [
        f"Given {story.title} is implemented, when core flow is executed, then it succeeds.",
        "Given standard usage, when inputs are valid, then results are deterministic.",
    ]


def _derive_tasks(story_id: str, acceptance: list[str]) -> list[BacklogTask]:
    """Derive tasks from acceptance criteria."""
    tasks = []
    for index, criterion in enumerate(acceptance, start=1):
        tasks.append(
            BacklogTask(
                task_id=f"{story_id}-t{index}",
                title=f"Task {index}",
                description=criterion,
                estimate_hours=min(8, max(1, len(criterion) // 40)),
            )
        )
    return tasks


def _estimate_story_points(story: RefinedStory, tasks: list[BacklogTask]) -> int:
    """Estimate story points based on size and complexity heuristics."""
    points = 1 + len(tasks) // 2
    points += len(story.nfr_tags) // 2
    points += len(story.dependencies) // 2
    if len(story.story) > 200:
        points += 1
    return max(1, min(13, points))


def _priority_score(
    story: RefinedStory,
    *,
    incidents: Iterable[dict[str, Any]],
    telemetry: Iterable[dict[str, Any]],
) -> float:
    """Compute priority score from value, risk, dependencies, and feedback signals."""
    value_score = 1 + len(story.acceptance_criteria) / 2
    risk_score = 1 + len(story.dependencies) / 2
    incident_boost = sum(
        1 for incident in incidents if story.story_id in incident.get("related_story_ids", [])
    )
    telemetry_boost = sum(
        1 for item in telemetry if story.story_id in item.get("related_story_ids", [])
    )
    dependency_penalty = len(story.dependencies) * 0.5
    return (
        (value_score * 3)
        + (risk_score * 2)
        + incident_boost
        + telemetry_boost
        - dependency_penalty
    )


def _epic_key(story: RefinedStory) -> str:
    """Derive an epic key from story metadata."""
    if story.nfr_tags:
        return story.nfr_tags[0].lower().replace(" ", "_")
    return "core_product"


def _story_from_payload(data: dict[str, Any]) -> BacklogStoryItem:
    tasks = [BacklogTask(**task) for task in data.get("tasks", [])]
    return BacklogStoryItem(
        story_id=str(data["story_id"]),
        title=str(data["title"]),
        story=str(data["story"]),
        acceptance_criteria=list(data.get("acceptance_criteria", [])),
        nfr_tags=list(data.get("nfr_tags", [])),
        dependencies=list(data.get("dependencies", [])),
        tasks=tasks,
        estimate_points=int(data.get("estimate_points", 1)),
        priority_score=float(data.get("priority_score", 0.0)),
        status=str(data.get("status", "backlog")),
    )
