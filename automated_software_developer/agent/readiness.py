"""Environment readiness helpers for local and CI execution."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import shutil
import sys
from dataclasses import dataclass

_MODULE_TO_DISTRIBUTION: dict[str, str] = {
    "yaml": "PyYAML",
    "pip_audit": "pip-audit",
}

CORE_RUNTIME_MODULES: tuple[str, ...] = (
    "typer",
    "rich",
    "openai",
    "yaml",
    "cryptography",
)
CORE_DEV_MODULES: tuple[str, ...] = (
    "ruff",
    "mypy",
    "pytest",
)
CORE_SECURITY_MODULES: tuple[str, ...] = (
    "bandit",
    "pip_audit",
)


@dataclass(frozen=True)
class DoctorCheck:
    """One doctor readiness check row."""

    category: str
    name: str
    passed: bool
    required: bool
    detail: str
    remediation: str | None = None


@dataclass(frozen=True)
class DoctorReport:
    """Doctor report payload with pass/fail semantics."""

    checks: list[DoctorCheck]

    @property
    def passed(self) -> bool:
        """Return whether all required checks passed."""
        return all(item.passed or not item.required for item in self.checks)

    def blocking_reasons(self) -> list[str]:
        """Return actionable blocking reasons for failed required checks."""
        reasons: list[str] = []
        for item in self.checks:
            if item.passed or not item.required:
                continue
            remediation = item.remediation or "No remediation provided."
            reasons.append(f"{item.category}/{item.name}: {item.detail}. {remediation}")
        return reasons


def module_available(module_name: str) -> bool:
    """Return whether a Python module can be imported."""
    return importlib.util.find_spec(module_name) is not None


def missing_modules(module_names: tuple[str, ...]) -> list[str]:
    """Return missing modules in deterministic order."""
    return [name for name in module_names if not module_available(name)]


def strict_readiness_issues(
    *,
    provider: str,
    quality_gates: bool,
    enable_security_scan: bool,
    security_scan_mode: str,
) -> list[str]:
    """Return strict readiness issues for run/verify preflight."""
    issues: list[str] = []
    if quality_gates:
        missing_dev = missing_modules(CORE_DEV_MODULES)
        if missing_dev:
            issues.append(
                "Missing required quality modules: "
                f"{', '.join(sorted(missing_dev))}. "
                "Install with `python -m pip install -e .[dev]`."
            )

    security_required = security_scan_mode == "required" or (
        enable_security_scan and security_scan_mode != "off"
    )
    if security_required and not module_available("bandit"):
        issues.append(
            "Security scan requires `bandit`, but it is not installed. "
            "Install with `python -m pip install -e .[security]`."
        )

    if provider in {"openai", "resilient"}:
        if not module_available("openai"):
            issues.append(
                "Provider mode requires `openai`, but it is not installed. "
                "Install with `python -m pip install -e .`."
            )
        if not os.environ.get("OPENAI_API_KEY"):
            issues.append(
                "`OPENAI_API_KEY` is required for provider modes `openai` and `resilient`."
            )
    return issues


def generator_gate_commands(*, python_executable: str | None = None) -> list[list[str]]:
    """Return canonical generator gate commands."""
    python_bin = python_executable or sys.executable
    return [
        [python_bin, "-m", "ruff", "check", "."],
        [python_bin, "-m", "mypy", "automated_software_developer"],
        [python_bin, "-m", "pytest"],
    ]


def build_doctor_report(
    *,
    include_security: bool = True,
    require_openai_key: bool = False,
) -> DoctorReport:
    """Build a readiness report for runtime/dev/security/tool dependencies."""
    checks: list[DoctorCheck] = []
    checks.append(
        DoctorCheck(
            category="runtime",
            name="python_version",
            passed=sys.version_info >= (3, 11),
            required=True,
            detail=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            remediation="Use Python 3.11 or newer.",
        )
    )

    for module_name in CORE_RUNTIME_MODULES:
        checks.append(_module_check("runtime", module_name, required=True))
    for module_name in CORE_DEV_MODULES:
        checks.append(_module_check("dev", module_name, required=True))
    if include_security:
        for module_name in CORE_SECURITY_MODULES:
            checks.append(_module_check("security", module_name, required=True))
    else:
        for module_name in CORE_SECURITY_MODULES:
            checks.append(_module_check("security", module_name, required=False))

    checks.append(_binary_check("tooling", "git", required=True))
    checks.append(_binary_check("tooling", "docker", required=False))
    checks.append(_binary_check("tooling", "gh", required=False))
    checks.append(
        DoctorCheck(
            category="env",
            name="OPENAI_API_KEY",
            passed=bool(os.environ.get("OPENAI_API_KEY")),
            required=require_openai_key,
            detail="configured" if os.environ.get("OPENAI_API_KEY") else "missing",
            remediation=(
                "Set `OPENAI_API_KEY` in the environment for real-provider runs."
            ),
        )
    )
    return DoctorReport(checks=checks)


def _module_check(category: str, module_name: str, *, required: bool) -> DoctorCheck:
    """Create doctor check row for a Python module."""
    available = module_available(module_name)
    if available:
        distribution = _MODULE_TO_DISTRIBUTION.get(module_name, module_name)
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            version = "installed"
        detail = f"installed ({version})"
    else:
        detail = "missing"
    extras = "[dev,security]" if category in {"dev", "security"} else ""
    remediation = (
        "Install with "
        f"`python -m pip install -e .{extras}`."
        if not available
        else None
    )
    return DoctorCheck(
        category=category,
        name=module_name,
        passed=available,
        required=required,
        detail=detail,
        remediation=remediation,
    )


def _binary_check(category: str, binary_name: str, *, required: bool) -> DoctorCheck:
    """Create doctor check row for required/optional binaries."""
    present = shutil.which(binary_name) is not None
    return DoctorCheck(
        category=category,
        name=binary_name,
        passed=present,
        required=required,
        detail="available" if present else "missing",
        remediation=(
            f"Install `{binary_name}` and ensure it is on PATH." if not present else None
        ),
    )
