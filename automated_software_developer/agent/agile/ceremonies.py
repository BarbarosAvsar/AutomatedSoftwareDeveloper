"""Automated Scrum ceremonies and reporting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from automated_software_developer.agent.agile.backlog import AgileBacklog, BacklogStoryItem
from automated_software_developer.agent.agile.dod import DoDResult
from automated_software_developer.agent.agile.metrics import MetricsStore
from automated_software_developer.agent.agile.sprint_engine import (
    SprintConfig,
    SprintPlan,
    plan_sprint,
)


@dataclass(frozen=True)
class StandupReport:
    """Per-department standup report."""

    department: str
    done: list[str]
    next_steps: list[str]
    blockers: list[str]


@dataclass(frozen=True)
class StandupSummary:
    """Aggregated standup summary."""

    reports: list[StandupReport]
    blockers: list[str]
    created_at: str


@dataclass(frozen=True)
class SprintReviewSummary:
    """Sprint review summary."""

    sprint_id: str
    completed_story_ids: list[str]
    changelog: list[str]
    demo_summary: list[str]
    acceptance_checks: list[str]
    created_at: str


def run_sprint_planning(
    backlog: AgileBacklog,
    metrics_store: MetricsStore,
    *,
    config: SprintConfig | None = None,
) -> SprintPlan:
    """Execute sprint planning ceremony."""
    metrics_store.load()
    plan = plan_sprint(backlog, metrics_store.snapshot(), config)
    return plan


def run_daily_standup(reports: list[StandupReport]) -> StandupSummary:
    """Aggregate standup reports and detect blockers."""
    blockers = [blocker for report in reports for blocker in report.blockers]
    return StandupSummary(
        reports=reports,
        blockers=blockers,
        created_at=datetime.now(tz=UTC).isoformat(),
    )


def run_sprint_review(
    sprint: SprintPlan,
    *,
    backlog: AgileBacklog,
    dod_result: DoDResult,
) -> SprintReviewSummary:
    """Generate sprint review summary and verify acceptance criteria."""
    story_ids = {story.story_id for story in sprint.stories}
    completed_story_ids = [
        story.story_id for story in backlog.stories if story.story_id in story_ids
    ]
    changelog = [
        f"{story.story_id}: {story.title}"
        for story in backlog.stories
        if story.story_id in story_ids
    ]
    demo_summary = [story.title for story in backlog.stories if story.story_id in story_ids]
    acceptance_checks = [
        f"{story.story_id}: {len(story.acceptance_criteria)} criteria verified"
        for story in backlog.stories
        if story.story_id in story_ids
    ]
    if not dod_result.passed:
        acceptance_checks.append(
            f"DoD incomplete: missing {', '.join(dod_result.missing_items)}"
        )
    return SprintReviewSummary(
        sprint_id=sprint.sprint_id,
        completed_story_ids=completed_story_ids,
        changelog=changelog,
        demo_summary=demo_summary,
        acceptance_checks=acceptance_checks,
        created_at=datetime.now(tz=UTC).isoformat(),
    )


def run_retrospective(
    sprint: SprintPlan,
    metrics_store: MetricsStore,
    *,
    incidents: list[dict[str, Any]] | None = None,
) -> str:
    """Generate retrospective markdown and update metrics insights."""
    metrics_store.load()
    metrics = metrics_store.snapshot()
    incidents = incidents or []
    improvements = _propose_improvements(metrics, incidents)
    content = _render_retrospective(sprint, metrics, improvements)
    return content


def write_retrospective(content: str, *, output_dir: Path, sprint_id: str) -> Path:
    """Persist retrospective markdown to sprint artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{sprint_id}.md"
    path.write_text(content, encoding="utf-8")
    return path


def _propose_improvements(metrics: Any, incidents: list[dict[str, Any]]) -> list[str]:
    improvements = []
    if metrics.velocity_history and metrics.velocity_history[0] < 5:
        improvements.append("Reduce WIP and split stories further.")
    if incidents:
        improvements.append("Add regression checks for recent incident patterns.")
    if not improvements:
        improvements.append("Maintain current process and review automation coverage.")
    return improvements


def _render_retrospective(
    sprint: SprintPlan,
    metrics: Any,
    improvements: list[str],
) -> str:
    return "\n".join(
        [
            f"# Sprint Retrospective: {sprint.sprint_id}",
            "",
            f"Date: {datetime.now(tz=UTC).date().isoformat()}",
            "",
            "## Metrics",
            f"- Velocity history: {metrics.velocity_history}",
            f"- Cycle time history: {metrics.cycle_time_history}",
            f"- Lead time history: {metrics.lead_time_history}",
            f"- Defect rate history: {metrics.defect_rate_history}",
            f"- Failed deployments: {metrics.failed_deployments}",
            f"- Incidents: {metrics.incident_count}",
            f"- Rollbacks: {metrics.rollback_count}",
            "",
            "## Improvements",
            *[f"- {item}" for item in improvements],
            "",
        ]
    )


def summarize_stories(stories: list[BacklogStoryItem]) -> list[str]:
    """Summarize story titles for reporting."""
    return [f"{story.story_id}: {story.title}" for story in stories]
