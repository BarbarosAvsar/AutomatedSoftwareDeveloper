"""Local learning utilities for prompt-pattern updates from journal history."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from automated_software_developer.agent.journal import PromptJournal
from automated_software_developer.agent.models import PromptTemplate
from automated_software_developer.agent.security import find_potential_secrets

DEFAULT_PATTERN_DEFINITIONS: dict[str, dict[str, Any]] = {
    "requirements-refinement": {
        "version": 2,
        "directives": [
            "Convert raw requirements into implementation-ready Agile artifacts.",
            "Use deterministic structure and explicit assumptions when uncertainty exists.",
            "Translate assumptions into testable Given/When/Then criteria.",
            "Require secure-by-default and maintainable implementation intent.",
        ],
        "retry_directives": [
            "If output validation fails, tighten schema conformance and story formatting.",
            "Preserve executable verification focus and remove ambiguous phrasing.",
        ],
        "constraints": [
            "Return strict JSON only.",
            "Never include secrets or environment variables.",
            "Each story must use 'As a ... I want ... so that ...' format.",
            "Each story must include acceptance criteria and verification commands when possible.",
        ],
    },
    "story-implementation": {
        "version": 2,
        "directives": [
            "Implement one story at a time with tests and verification steps.",
            "Prefer small, reviewable file operations and secure coding practices.",
            "Use acceptance criteria to drive test creation and runtime checks.",
            "Enforce idiomatic style, naming conventions, SRP, DRY, and KISS principles.",
        ],
        "retry_directives": [
            "On failures, apply minimal focused fixes guided by failing checks.",
            "Avoid unrelated refactors when fixing verification errors.",
            "Prioritize fixing quality gate violations before adding new behavior.",
        ],
        "constraints": [
            "Return strict JSON only.",
            "Never emit secrets or tokens.",
            "Include or update tests before declaring story complete.",
            "Add docstrings to public functions and classes in generated code.",
        ],
    },
}

MAX_PATTERN_ITEMS = 10
CHANGELOG_FILENAME = "PROMPT_TEMPLATE_CHANGES.md"


@dataclass(frozen=True)
class TemplateLearningProposal:
    """A proposed template mutation derived from journal signals."""

    template_id: str
    base_version: int
    reason: str
    directives: list[str]
    retry_directives: list[str]
    constraints: list[str]


@dataclass(frozen=True)
class TemplateLearningUpdate:
    """A template version update produced by learning."""

    template_id: str
    old_version: int
    new_version: int
    reason: str
    path: Path


@dataclass(frozen=True)
class LearningSummary:
    """Result summary from a learning pass."""

    entries_processed: int
    templates_considered: int
    proposals: list[TemplateLearningProposal]
    updates: list[TemplateLearningUpdate]
    failure_signals: dict[str, int]
    changelog_path: Path


class PromptPatternStore:
    """Versioned prompt template storage and retrieval."""

    def __init__(self, base_dir: Path | None = None) -> None:
        """Initialize template store rooted at prompt pattern directory."""
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent / "prompt_patterns"
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._defaults_ensured = False
        self._latest_template_cache: dict[str, PromptTemplate] = {}

    def ensure_defaults(self) -> None:
        """Create or upgrade baseline template files when needed."""
        if self._defaults_ensured:
            return
        wrote_defaults = False
        for template_id, payload in DEFAULT_PATTERN_DEFINITIONS.items():
            latest = self._find_latest_path(template_id)
            default_version = int(payload["version"])
            if latest is None:
                self._write_template(
                    template_id=template_id,
                    version=default_version,
                    payload={
                        "template_id": template_id,
                        "version": default_version,
                        "directives": payload["directives"],
                        "retry_directives": payload["retry_directives"],
                        "constraints": payload["constraints"],
                    },
                )
                wrote_defaults = True
                continue
            current_version = self._parse_filename(latest.name)[1]
            if current_version >= default_version:
                continue
            self._write_template(
                template_id=template_id,
                version=default_version,
                payload={
                    "template_id": template_id,
                    "version": default_version,
                    "directives": payload["directives"],
                    "retry_directives": payload["retry_directives"],
                    "constraints": payload["constraints"],
                },
            )
            wrote_defaults = True
        self._defaults_ensured = True
        if wrote_defaults:
            self._latest_template_cache.clear()

    def list_template_ids(self) -> list[str]:
        """Return discovered template ids sorted by name."""
        ids: set[str] = set()
        for path in self.base_dir.glob("*.v*.json"):
            template_id, _ = self._parse_filename(path.name)
            ids.add(template_id)
        return sorted(ids)

    def load_latest(self, template_id: str) -> PromptTemplate:
        """Load the latest version of a template."""
        self.ensure_defaults()
        cached = self._latest_template_cache.get(template_id)
        if cached is not None:
            return cached
        latest_path = self._find_latest_path(template_id)
        if latest_path is None:
            raise ValueError(f"Template '{template_id}' not found.")
        payload = json.loads(latest_path.read_text(encoding="utf-8"))
        template = PromptTemplate(
            template_id=str(payload["template_id"]),
            version=int(payload["version"]),
            directives=[str(item) for item in payload["directives"]],
            retry_directives=[str(item) for item in payload["retry_directives"]],
            constraints=[str(item) for item in payload["constraints"]],
        )
        self._latest_template_cache[template_id] = template
        return template

    def load_all_latest(self) -> dict[str, PromptTemplate]:
        """Load latest templates for all template ids."""
        self.ensure_defaults()
        return {
            template_id: self.load_latest(template_id) for template_id in self.list_template_ids()
        }

    def save_new_version(
        self,
        template: PromptTemplate,
        directives: list[str],
        retry_directives: list[str],
        constraints: list[str],
    ) -> Path:
        """Persist a new incremented template version."""
        self.ensure_defaults()
        next_version = template.version + 1
        payload = {
            "template_id": template.template_id,
            "version": next_version,
            "directives": directives[:MAX_PATTERN_ITEMS],
            "retry_directives": retry_directives[:MAX_PATTERN_ITEMS],
            "constraints": constraints[:MAX_PATTERN_ITEMS],
        }
        return self._write_template(template.template_id, next_version, payload)

    def summarize_versions(self) -> dict[str, int]:
        """Return template -> latest version mapping."""
        return {
            template_id: self.load_latest(template_id).version
            for template_id in self.list_template_ids()
        }

    def _find_latest_path(self, template_id: str) -> Path | None:
        """Find latest version path for a template id."""
        candidates = [
            (self._parse_filename(path.name)[1], path)
            for path in self.base_dir.glob(f"{template_id}.v*.json")
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        return candidates[-1][1]

    def _write_template(self, template_id: str, version: int, payload: dict[str, Any]) -> Path:
        """Write a template payload to disk as JSON."""
        output_path = self.base_dir / f"{template_id}.v{version}.json"
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._latest_template_cache.pop(template_id, None)
        return output_path

    def _parse_filename(self, filename: str) -> tuple[str, int]:
        """Parse template filename pattern `<id>.v<version>.json`."""
        match = re.match(r"^([a-z0-9-]+)\.v([0-9]+)\.json$", filename)
        if match is None:
            raise ValueError(f"Invalid prompt pattern filename: {filename}")
        return match.group(1), int(match.group(2))


def learn_from_journals(
    journal_paths: list[Path],
    pattern_store: PromptPatternStore,
    update_templates: bool,
    playbook_path: Path,
    changelog_path: Path | None = None,
) -> LearningSummary:
    """Analyze journals and optionally create incremented prompt template versions."""
    entries = PromptJournal.load_entries(journal_paths)
    grouped: dict[str, list[dict[str, Any]]] = {}
    signal_counts: dict[str, int] = {"test": 0, "typing": 0, "security": 0, "runtime": 0}
    for entry in entries:
        template_id = str(entry.get("template_id", "unknown"))
        grouped.setdefault(template_id, []).append(entry)
        text = str(entry.get("failing_checks", "")) + "\n" + str(entry.get("error", ""))
        lowered = text.lower()
        if any(token in lowered for token in ("pytest", "assert", "test failed")):
            signal_counts["test"] += 1
        if any(token in lowered for token in ("mypy", "type error", "typing")):
            signal_counts["typing"] += 1
        if any(token in lowered for token in ("secret", "token", "credential", "bandit")):
            signal_counts["security"] += 1
        if any(token in lowered for token in ("traceback", "runtimeerror", "exception")):
            signal_counts["runtime"] += 1

    proposals = _build_proposals(grouped, pattern_store, signal_counts)

    updates: list[TemplateLearningUpdate] = []
    if update_templates:
        for proposal in proposals:
            _validate_proposal(proposal)
            current = pattern_store.load_latest(proposal.template_id)
            if _proposal_is_noop(current, proposal):
                continue
            output_path = pattern_store.save_new_version(
                template=current,
                directives=proposal.directives,
                retry_directives=proposal.retry_directives,
                constraints=proposal.constraints,
            )
            updates.append(
                TemplateLearningUpdate(
                    template_id=proposal.template_id,
                    old_version=current.version,
                    new_version=current.version + 1,
                    reason=proposal.reason,
                    path=output_path,
                )
            )

    _write_playbook(playbook_path, pattern_store, grouped, proposals, updates)
    resolved_changelog = changelog_path or playbook_path.with_name(CHANGELOG_FILENAME)
    _write_template_changelog(resolved_changelog, proposals, updates, update_templates)
    return LearningSummary(
        entries_processed=len(entries),
        templates_considered=len(grouped),
        proposals=proposals,
        updates=updates,
        failure_signals=signal_counts,
        changelog_path=resolved_changelog,
    )


def _build_proposals(
    grouped: dict[str, list[dict[str, Any]]],
    pattern_store: PromptPatternStore,
    signal_counts: dict[str, int],
) -> list[TemplateLearningProposal]:
    """Create bounded template proposals from grouped journal entries."""
    proposals: list[TemplateLearningProposal] = []
    available = set(pattern_store.list_template_ids())
    for template_id in sorted(grouped):
        if template_id not in available:
            continue
        entries_for_template = grouped[template_id]
        total = len(entries_for_template)
        failures = sum(1 for entry in entries_for_template if str(entry.get("outcome")) != "pass")
        if total < 2:
            continue
        failure_ratio = failures / max(total, 1)
        current = pattern_store.load_latest(template_id)
        directives = list(current.directives)
        retry_directives = list(current.retry_directives)
        constraints = list(current.constraints)
        changed = False

        if failure_ratio >= 0.25 and _append_unique(
            directives,
            "Prefer writing or updating focused tests before feature completion.",
        ):
            changed = True
        if signal_counts["typing"] > 0 and _append_unique(
            directives,
            "Use explicit type annotations in new or modified public functions.",
        ):
            changed = True
        if signal_counts["runtime"] > 0 and _append_unique(
            retry_directives,
            "When runtime failures occur, inspect stderr first and patch minimally.",
        ):
            changed = True
        if signal_counts["security"] > 0 and _append_unique(
            constraints,
            "Do not write logs, artifacts, or tests that expose secrets.",
        ):
            changed = True
        if signal_counts["security"] > 0 and _append_unique(
            constraints,
            "Apply input validation and sanitization aligned to OWASP guidance.",
        ):
            changed = True
        if signal_counts["test"] > 0 and _append_unique(
            directives,
            "Add edge-case tests, not only happy-path tests, for each story.",
        ):
            changed = True

        if not changed:
            continue
        proposals.append(
            TemplateLearningProposal(
                template_id=template_id,
                base_version=current.version,
                reason=f"failure_ratio={failure_ratio:.2f}, signals={signal_counts}",
                directives=directives[:MAX_PATTERN_ITEMS],
                retry_directives=retry_directives[:MAX_PATTERN_ITEMS],
                constraints=constraints[:MAX_PATTERN_ITEMS],
            )
        )
    return proposals


def _proposal_is_noop(current: PromptTemplate, proposal: TemplateLearningProposal) -> bool:
    """Return whether a proposal is identical to the current template state."""
    return (
        current.directives == proposal.directives
        and current.retry_directives == proposal.retry_directives
        and current.constraints == proposal.constraints
    )


def _validate_proposal(proposal: TemplateLearningProposal) -> None:
    """Validate proposal structure and block secret-bearing prompt content."""
    for name, items in (
        ("directives", proposal.directives),
        ("retry_directives", proposal.retry_directives),
        ("constraints", proposal.constraints),
    ):
        if not items:
            raise ValueError(f"Proposal '{proposal.template_id}' has empty {name}.")
        if len(items) > MAX_PATTERN_ITEMS:
            raise ValueError(f"Proposal '{proposal.template_id}' exceeds max {name} items.")
        for item in items:
            if find_potential_secrets(item):
                raise ValueError(
                    f"Proposal '{proposal.template_id}' contains sensitive pattern in {name}."
                )


def _append_unique(items: list[str], text: str) -> bool:
    """Append text to list when not already present."""
    if text in items:
        return False
    items.append(text)
    return True


def _write_playbook(
    playbook_path: Path,
    pattern_store: PromptPatternStore,
    grouped_entries: dict[str, list[dict[str, Any]]],
    proposals: list[TemplateLearningProposal],
    updates: list[TemplateLearningUpdate],
) -> None:
    """Write a human-readable prompt playbook snapshot."""
    playbook_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "# Prompt Playbook",
        "",
        "Versioned prompt patterns derived from bounded local learning.",
        "",
        "## Current Templates",
    ]
    for template_id in pattern_store.list_template_ids():
        template = pattern_store.load_latest(template_id)
        lines.append(f"- `{template_id}`: v{template.version}")

    lines.extend(["", "## Journal Coverage"])
    if not grouped_entries:
        lines.append("- No journal entries analyzed.")
    else:
        for template_id in sorted(grouped_entries):
            lines.append(f"- `{template_id}`: {len(grouped_entries[template_id])} entries")

    lines.extend(["", "## Proposals"])
    if not proposals:
        lines.append("- No template update proposals.")
    else:
        for proposal in proposals:
            lines.append(
                f"- `{proposal.template_id}` from v{proposal.base_version}: {proposal.reason}"
            )

    lines.extend(["", "## Applied Updates"])
    if not updates:
        lines.append("- No template updates applied.")
    else:
        for update in updates:
            lines.append(
                f"- `{update.template_id}`: v{update.old_version} -> v{update.new_version} "
                f"({update.reason})"
            )
    lines.append("")
    playbook_path.write_text("\n".join(lines), encoding="utf-8")


def _write_template_changelog(
    changelog_path: Path,
    proposals: list[TemplateLearningProposal],
    updates: list[TemplateLearningUpdate],
    updates_requested: bool,
) -> None:
    """Write review-oriented changelog for proposal and applied template updates."""
    changelog_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "# Prompt Template Changes",
        "",
        f"Updates requested: {'yes' if updates_requested else 'no'}",
        "",
        "## Proposed Changes",
    ]
    if not proposals:
        lines.append("- None")
    else:
        for proposal in proposals:
            lines.extend(
                [
                    f"### {proposal.template_id} (base v{proposal.base_version})",
                    f"Reason: {proposal.reason}",
                    "Directives:",
                    *[f"- {item}" for item in proposal.directives],
                    "Retry directives:",
                    *[f"- {item}" for item in proposal.retry_directives],
                    "Constraints:",
                    *[f"- {item}" for item in proposal.constraints],
                    "",
                ]
            )
    lines.extend(["## Applied Changes"])
    if not updates:
        lines.append("- None")
    else:
        for update in updates:
            lines.append(
                f"- {update.template_id}: v{update.old_version} -> v{update.new_version} "
                f"({update.path})"
            )
    lines.append("")
    changelog_path.write_text("\n".join(lines), encoding="utf-8")
