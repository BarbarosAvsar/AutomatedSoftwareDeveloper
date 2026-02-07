"""Property-style tests for requirement refinement stability."""

from __future__ import annotations

from automated_software_developer.agent.providers.mock_provider import MockProvider
from automated_software_developer.agent.requirements_refiner import RequirementsRefiner


def test_requirements_heuristics_handle_weird_inputs() -> None:
    refiner = RequirementsRefiner(provider=MockProvider([]))
    samples = [
        "",
        " ",
        "\n\n\t",
        "🚀✨💾",
        "DROP TABLE users; --",
        "As a user, I want 🧪 so that ✅",
        "requirement: \x00\x01\x02",
        "newline\nseparated\nrequirements",
        "Mixed CASE and symbols !@#$%^&*()",
        "JSON-like {\"key\": \"value\"}",
    ]
    for sample in samples:
        analysis = refiner._analyze(sample)
        notes = analysis.to_prompt_notes()
        assert isinstance(notes, str)
