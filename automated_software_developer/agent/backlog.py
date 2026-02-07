"""Backlog and sprint orchestration data helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from typing import Any

from automated_software_developer.agent.models import BacklogStory, RefinedRequirements

STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


@dataclass
class StoryBacklog:
    """Story backlog state for sprint-based execution."""

    project_name: str
    product_brief: str
    stack_rationale: str
    personas: list[str]
    nfrs: dict[str, list[str]]
    assumptions: list[dict[str, str]]
    stories: list[BacklogStory]
    global_verification_commands: list[str]

    @classmethod
    def from_refined_requirements(cls, refined: RefinedRequirements) -> StoryBacklog:
        """Build executable backlog from refined requirements."""
        stories: list[BacklogStory] = []
        for story in refined.stories:
            item = BacklogStory.from_refined_story(story)
            commands = item.verification_commands or derive_verification_commands_from_criteria(
                item.acceptance_criteria
            )
            stories.append(replace(item, verification_commands=commands))
        return cls(
            project_name=refined.project_name,
            product_brief=refined.product_brief,
            stack_rationale=refined.stack_rationale,
            personas=refined.personas,
            nfrs=refined.nfrs,
            assumptions=[
                {
                    "assumption": item.assumption,
                    "testable_criterion": item.testable_criterion,
                }
                for item in refined.assumptions
            ],
            stories=stories,
            global_verification_commands=refined.global_verification_commands,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize backlog state for JSON persistence."""
        return {
            "project_name": self.project_name,
            "product_brief": self.product_brief,
            "stack_rationale": self.stack_rationale,
            "personas": self.personas,
            "nfrs": self.nfrs,
            "assumptions": self.assumptions,
            "global_verification_commands": self.global_verification_commands,
            "stories": [story.to_dict() for story in self.stories],
            "completed_stories": self.completed_count(),
            "total_stories": len(self.stories),
        }

    def completed_count(self) -> int:
        """Return count of completed stories."""
        return sum(1 for story in self.stories if story.status == STATUS_COMPLETED)

    def pending_count(self) -> int:
        """Return count of pending stories."""
        return sum(1 for story in self.stories if story.status == STATUS_PENDING)

    def story_by_id(self, story_id: str) -> BacklogStory:
        """Lookup story by identifier."""
        for story in self.stories:
            if story.story_id == story_id:
                return story
        raise KeyError(f"Unknown story id '{story_id}'.")

    def update_story(
        self,
        story_id: str,
        *,
        status: str,
        attempts: int,
        last_error: str | None,
    ) -> None:
        """Replace a story state in-place."""
        updated: list[BacklogStory] = []
        found = False
        for story in self.stories:
            if story.story_id == story_id:
                updated.append(
                    replace(
                        story,
                        status=status,
                        attempts=attempts,
                        last_error=last_error,
                    )
                )
                found = True
            else:
                updated.append(story)
        if not found:
            raise KeyError(f"Unknown story id '{story_id}'.")
        self.stories = updated

    def select_sprint(self, max_stories: int) -> list[BacklogStory]:
        """Pick the next dependency-satisfied story batch."""
        if max_stories <= 0:
            raise ValueError("max_stories must be greater than zero.")
        completed_ids = {item.story_id for item in self.stories if item.status == STATUS_COMPLETED}
        selection: list[BacklogStory] = []
        for story in self.stories:
            if story.status != STATUS_PENDING:
                continue
            if any(dep not in completed_ids for dep in story.dependencies):
                continue
            selection.append(story)
            if len(selection) >= max_stories:
                break
        return selection

    def has_active_work(self) -> bool:
        """Return whether stories are still pending or in-progress."""
        return any(story.status in {STATUS_PENDING, STATUS_IN_PROGRESS} for story in self.stories)

    def unresolved_dependencies(self) -> dict[str, list[str]]:
        """Return pending stories blocked by unmet dependencies."""
        completed_ids = {item.story_id for item in self.stories if item.status == STATUS_COMPLETED}
        blocked: dict[str, list[str]] = {}
        for story in self.stories:
            if story.status != STATUS_PENDING:
                continue
            missing = [dep for dep in story.dependencies if dep not in completed_ids]
            if missing:
                blocked[story.story_id] = missing
        return blocked


def derive_verification_commands_from_criteria(criteria: list[str]) -> list[str]:
    """Generate lightweight executable checks from textual acceptance criteria."""
    commands: list[str] = []
    exists_paths, contains_checks = parse_acceptance_criteria_assertions(criteria)
    for path in exists_paths:
        commands.append(
            "python -c "
            f"\"from pathlib import Path; assert Path({json.dumps(path)}).exists()\""
        )
    for path, expected in contains_checks:
        expected_literal = json.dumps(expected)
        path_literal = json.dumps(path)
        commands.append(
            "python -c "
            "\"from pathlib import Path; "
            f"assert {expected_literal} in "
            f"Path({path_literal}).read_text(encoding='utf-8')\""
        )
    return _dedupe(commands)


def resolve_story_commands(story: BacklogStory, fallback_commands: list[str]) -> list[str]:
    """Resolve verification commands for a story with deterministic fallback behavior."""
    if story.verification_commands:
        return story.verification_commands
    derived = derive_verification_commands_from_criteria(story.acceptance_criteria)
    if derived:
        return derived
    return fallback_commands


def parse_acceptance_criteria_assertions(
    criteria: list[str],
) -> tuple[list[str], list[tuple[str, str]]]:
    """Extract file-exists and file-contains assertions from acceptance criteria."""
    exists_paths: list[str] = []
    contains_checks: list[tuple[str, str]] = []
    for criterion in criteria:
        exists_paths.extend(_extract_exists_paths(criterion))
        contains_checks.extend(_extract_contains_assertions(criterion))
    return _dedupe(exists_paths), _dedupe_pairs(contains_checks)


def _extract_exists_paths(text: str) -> list[str]:
    """Extract paths referenced by '<path> exists' patterns."""
    return _dedupe(re.findall(r"(?i)\b([A-Za-z0-9_./-]+)\s+exists\b", text))


def _extract_contains_assertions(text: str) -> list[tuple[str, str]]:
    """Extract pairs from '<path> contains <expected>' patterns."""
    matches = re.findall(
        r"(?i)\b([A-Za-z0-9_./-]+)\s+contains\s+['\"]?([^'\".]+)['\"]?",
        text,
    )
    normalized: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for path, expected in matches:
        pair = (path.strip(), expected.strip())
        if not all(pair) or pair in seen:
            continue
        seen.add(pair)
        normalized.append(pair)
    return normalized


def _dedupe(items: list[str]) -> list[str]:
    """Return list preserving order while removing duplicates and blanks."""
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ordered


def _dedupe_pairs(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Return unique tuple pairs preserving order."""
    seen: set[tuple[str, str]] = set()
    ordered: list[tuple[str, str]] = []
    for pair in items:
        if pair in seen:
            continue
        seen.add(pair)
        ordered.append(pair)
    return ordered
