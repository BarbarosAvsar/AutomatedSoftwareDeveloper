"""Tests for planning mode selector behavior."""

from __future__ import annotations

from automated_software_developer.agent.planning_mode_agent import PlanningModeSelectorAgent


def test_auto_mode_resolves_to_planning() -> None:
    """Auto mode should resolve deterministically to planning."""
    agent = PlanningModeSelectorAgent()
    decision = agent.select(requested_mode="auto", requirements="Build a CLI tool.")
    assert decision.requested_mode == "auto"
    assert decision.selected_mode == "planning"
    assert "planning-first" in decision.reason


def test_direct_mode_is_preserved() -> None:
    """Direct mode should remain direct."""
    agent = PlanningModeSelectorAgent()
    decision = agent.select(requested_mode="direct", requirements="Build a CLI tool.")
    assert decision.selected_mode == "direct"


def test_planning_mode_is_preserved() -> None:
    """Planning mode should remain planning."""
    agent = PlanningModeSelectorAgent()
    decision = agent.select(requested_mode="planning", requirements="Build a CLI tool.")
    assert decision.selected_mode == "planning"
