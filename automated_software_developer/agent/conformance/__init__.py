"""Conformance suite package for generator validation."""

from __future__ import annotations

from automated_software_developer.agent.conformance.fixtures import (
    ConformanceFixture,
    load_fixtures,
)
from automated_software_developer.agent.conformance.reporting import (
    ConformanceReport,
    FixtureResult,
    GateResult,
)
from automated_software_developer.agent.conformance.runner import run_conformance_suite

__all__ = [
    "ConformanceFixture",
    "ConformanceReport",
    "FixtureResult",
    "GateResult",
    "load_fixtures",
    "run_conformance_suite",
]
