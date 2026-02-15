"""Tests for config validation helpers."""

from __future__ import annotations

import pytest

from automated_software_developer.agent.config_validation import validate_provider_mode


def test_validate_provider_mode_accepts_resilient() -> None:
    """Provider validator should allow resilient mode."""
    assert validate_provider_mode("resilient") == "resilient"


def test_validate_provider_mode_rejects_unknown() -> None:
    """Provider validator should reject unsupported providers."""
    with pytest.raises(ValueError):
        validate_provider_mode("other")
