"""Tests for config validation helpers."""

from __future__ import annotations

import pytest

from automated_software_developer.agent.config_validation import (
    validate_execution_mode,
    validate_provider_mode,
)


def test_validate_provider_mode_accepts_resilient() -> None:
    """Provider validator should allow resilient mode."""
    assert validate_provider_mode("resilient") == "resilient"


def test_validate_provider_mode_rejects_unknown() -> None:
    """Provider validator should reject unsupported providers."""
    with pytest.raises(ValueError):
        validate_provider_mode("other")


def test_validate_execution_mode_accepts_auto() -> None:
    """Execution mode validator should allow auto mode."""
    assert validate_execution_mode("auto") == "auto"


def test_validate_execution_mode_accepts_direct() -> None:
    """Execution mode validator should allow direct mode."""
    assert validate_execution_mode("direct") == "direct"


def test_validate_execution_mode_accepts_planning() -> None:
    """Execution mode validator should allow planning mode."""
    assert validate_execution_mode("planning") == "planning"


def test_validate_execution_mode_rejects_unknown() -> None:
    """Execution mode validator should reject unsupported modes."""
    with pytest.raises(ValueError):
        validate_execution_mode("other")
