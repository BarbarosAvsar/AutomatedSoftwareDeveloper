"""Sprint planning and execution helpers for Scrum cycles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from automated_software_developer.agent.agile.backlog import AgileBacklog, BacklogStoryItem
from automated_software_developer.agent.agile.metrics import MetricsSnapshot


@dataclass(frozen=True)
class SprintConfig:
    """Configuration for sprint planning."""

    length_days: int = 14
    velocity_lookback: int = 3
    default_capacity_points: int = 10

    def __post_init__(self) -> None:
        if self.length_days <= 0:
            raise ValueError("length_days must be greater than zero.")
        if self.velocity_lookback <= 0:
            raise ValueError("velocity_lookback must be greater than zero.")
        if self.default_capacity_points <= 0:
            raise ValueError("default_capacity_points must be greater than zero.")


@dataclass(frozen=True)
class SprintPlan:
    """Sprint plan containing selected stories and goal."""

    sprint_id: str
    goal: str
    start_date: str
    end_date: str
    capacity_points: int
    stories: list[BacklogStoryItem]
    status: str = "planned"
    frozen: bool = False
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize sprint plan to JSON-compatible dict."""
        return {
            "sprint_id": self.sprint_id,
            "goal": self.goal,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "capacity_points": self.capacity_points,
            "status": self.status,
            "frozen": self.frozen,
            "metadata": self.metadata or {},
            "stories": [story.to_dict() for story in self.stories],
        }


def plan_sprint(
    backlog: AgileBacklog,
    metrics: MetricsSnapshot,
    config: SprintConfig | None = None,
) -> SprintPlan:
    """Generate a sprint plan based on velocity and backlog priority."""
    config = config or SprintConfig()
    capacity = _calculate_capacity(metrics, config)
    selected = _select_stories(backlog, capacity)
    goal = _sprint_goal(selected)
    sprint_id = _generate_sprint_id()
    start = date.today()
    end = start + timedelta(days=config.length_days)
    return SprintPlan(
        sprint_id=sprint_id,
        goal=goal,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        capacity_points=capacity,
        stories=selected,
        metadata={
            "planned_at": datetime.now(tz=UTC).isoformat(),
            "velocity_basis": metrics.velocity_history[: config.velocity_lookback],
        },
    )


def freeze_sprint(plan: SprintPlan, *, allow_override: bool = False) -> SprintPlan:
    """Freeze sprint scope unless an explicit override is allowed."""
    if plan.frozen and not allow_override:
        raise ValueError("Sprint scope is already frozen.")
    return SprintPlan(
        sprint_id=plan.sprint_id,
        goal=plan.goal,
        start_date=plan.start_date,
        end_date=plan.end_date,
        capacity_points=plan.capacity_points,
        stories=plan.stories,
        status=plan.status,
        frozen=True,
        metadata=plan.metadata,
    )


def _calculate_capacity(metrics: MetricsSnapshot, config: SprintConfig) -> int:
    """Calculate sprint capacity using historical velocity."""
    history = metrics.velocity_history[: config.velocity_lookback]
    if not history:
        return config.default_capacity_points
    average = sum(history) / len(history)
    return max(1, round(average))


def _select_stories(backlog: AgileBacklog, capacity: int) -> list[BacklogStoryItem]:
    """Select stories until capacity is filled."""
    selection: list[BacklogStoryItem] = []
    used = 0
    for story in backlog.stories:
        if story.status not in {"backlog", "ready"}:
            continue
        if used + story.estimate_points > capacity:
            continue
        selection.append(story)
        used += story.estimate_points
        if used >= capacity:
            break
    return selection


def _sprint_goal(stories: list[BacklogStoryItem]) -> str:
    """Generate a sprint goal statement."""
    if not stories:
        return "Stabilize and prepare backlog for upcoming sprint."
    titles = ", ".join(story.title for story in stories[:3])
    return f"Deliver {titles}."


def _generate_sprint_id() -> str:
    """Generate a deterministic sprint identifier."""
    now = datetime.now(tz=UTC)
    return f"sprint-{now:%Y%m%d%H%M%S}"
