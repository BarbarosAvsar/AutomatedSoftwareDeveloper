"""Definition of Done enforcement."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DoDChecklist:
    """Checklist for Definition of Done gates."""

    compile_passed: bool
    tests_passed: bool
    lint_passed: bool
    type_check_passed: bool
    security_scan_passed: bool
    docs_updated: bool
    deployment_successful: bool


@dataclass(frozen=True)
class DoDResult:
    """Result of Definition of Done evaluation."""

    passed: bool
    missing_items: list[str]


def evaluate_definition_of_done(checklist: DoDChecklist) -> DoDResult:
    """Evaluate Definition of Done and return missing items."""
    missing = []
    if not checklist.compile_passed:
        missing.append("compile")
    if not checklist.tests_passed:
        missing.append("tests")
    if not checklist.lint_passed:
        missing.append("lint")
    if not checklist.type_check_passed:
        missing.append("type_checks")
    if not checklist.security_scan_passed:
        missing.append("security_scan")
    if not checklist.docs_updated:
        missing.append("docs")
    if not checklist.deployment_successful:
        missing.append("deployment")
    return DoDResult(passed=not missing, missing_items=missing)
