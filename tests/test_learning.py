"""Tests for bounded prompt-pattern learning updates."""

from __future__ import annotations

from pathlib import Path

from automated_software_developer.agent.journal import PromptJournal
from automated_software_developer.agent.learning import PromptPatternStore, learn_from_journals


def test_learning_updates_templates_in_bounded_way(tmp_path: Path) -> None:
    journal_path = tmp_path / "prompt_journal.jsonl"
    journal = PromptJournal(journal_path)
    journal.append(
        {
            "template_id": "story-implementation",
            "outcome": "fail",
            "failing_checks": "pytest failed and mypy type error",
        }
    )
    journal.append(
        {
            "template_id": "story-implementation",
            "outcome": "pass",
            "failing_checks": "",
        }
    )

    pattern_store = PromptPatternStore(base_dir=tmp_path / "patterns")
    pattern_store.ensure_defaults()
    summary = learn_from_journals(
        journal_paths=[journal_path],
        pattern_store=pattern_store,
        update_templates=True,
        playbook_path=tmp_path / "PROMPT_PLAYBOOK.md",
        changelog_path=tmp_path / "PROMPT_TEMPLATE_CHANGES.md",
    )
    assert summary.entries_processed == 2
    assert summary.templates_considered == 1
    assert len(summary.proposals) == 1
    assert len(summary.updates) == 1
    updated = pattern_store.load_latest("story-implementation")
    assert updated.version == 3
    assert any("focused tests" in item.lower() for item in updated.directives)
    assert summary.changelog_path == tmp_path / "PROMPT_TEMPLATE_CHANGES.md"

    second_summary = learn_from_journals(
        journal_paths=[journal_path],
        pattern_store=pattern_store,
        update_templates=True,
        playbook_path=tmp_path / "PROMPT_PLAYBOOK.md",
        changelog_path=tmp_path / "PROMPT_TEMPLATE_CHANGES.md",
    )
    assert len(second_summary.updates) == 0
    assert pattern_store.load_latest("story-implementation").version == 3
    assert (tmp_path / "PROMPT_PLAYBOOK.md").exists()
    assert (tmp_path / "PROMPT_TEMPLATE_CHANGES.md").exists()


def test_learning_proposes_without_applying_when_updates_disabled(tmp_path: Path) -> None:
    journal_path = tmp_path / "prompt_journal.jsonl"
    journal = PromptJournal(journal_path)
    journal.append(
        {
            "template_id": "requirements-refinement",
            "outcome": "fail",
            "failing_checks": "test failed due missing acceptance edge case",
        }
    )
    journal.append(
        {
            "template_id": "requirements-refinement",
            "outcome": "pass",
            "failing_checks": "",
        }
    )
    pattern_store = PromptPatternStore(base_dir=tmp_path / "patterns")
    pattern_store.ensure_defaults()
    summary = learn_from_journals(
        journal_paths=[journal_path],
        pattern_store=pattern_store,
        update_templates=False,
        playbook_path=tmp_path / "PROMPT_PLAYBOOK.md",
        changelog_path=tmp_path / "PROMPT_TEMPLATE_CHANGES.md",
    )
    assert len(summary.proposals) == 1
    assert len(summary.updates) == 0
    assert pattern_store.load_latest("requirements-refinement").version == 2
