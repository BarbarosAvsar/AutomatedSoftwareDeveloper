"""Run software factory conformance suite across fixture projects."""

from __future__ import annotations

import importlib.util
import json
import shlex
import subprocess
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from automated_software_developer.agent.ci.workflow_lint import validate_workflow
from automated_software_developer.agent.conformance.fixtures import (
    ConformanceFixture,
    load_fixtures,
)
from automated_software_developer.agent.conformance.reporting import (
    ConformanceReport,
    DiffResult,
    FixtureResult,
    GateResult,
)
from automated_software_developer.agent.orchestrator import AgentConfig, SoftwareDevelopmentAgent
from automated_software_developer.agent.platforms.catalog import adapter_catalog
from automated_software_developer.agent.providers.mock_provider import MockProvider
from automated_software_developer.agent.reproducibility import build_artifact_checksums


@dataclass(frozen=True)
class ConformanceConfig:
    """Configuration for conformance suite execution."""

    output_dir: Path
    report_path: Path
    provider: str = "mock"
    conformance_seed: int = 4242
    reproducible: bool = True
    diff_check: bool = True
    max_workers: int = 3


def run_conformance_suite(
    *,
    fixtures: Iterable[ConformanceFixture] | None = None,
    config: ConformanceConfig | None = None,
) -> ConformanceReport:
    """Run conformance suite and write a report to disk."""
    resolved_fixtures = list(fixtures) if fixtures is not None else load_fixtures()
    if not resolved_fixtures:
        raise ValueError("No conformance fixtures available.")

    cfg = config or ConformanceConfig(
        output_dir=_repo_root() / "conformance" / "output",
        report_path=_repo_root() / "conformance" / "report.json",
    )
    if cfg.max_workers <= 0:
        raise ValueError("max_workers must be greater than zero.")
    cfg.output_dir.mkdir(parents=True, exist_ok=True)

    builder, _ = ConformanceReport.start()
    with ThreadPoolExecutor(max_workers=cfg.max_workers) as executor:
        futures = [
            executor.submit(_run_fixture, fixture, cfg)
            for fixture in resolved_fixtures
        ]
        for future in as_completed(futures):
            builder.fixtures.append(future.result())

    report = builder.finish()
    report.write(cfg.report_path)
    return report


def _run_fixture(fixture: ConformanceFixture, cfg: ConformanceConfig) -> FixtureResult:
    """Execute a single fixture run and gather results."""
    output_dir = cfg.output_dir / fixture.fixture_id
    run1_dir = output_dir / "run-1"
    run2_dir = output_dir / "run-2"
    for target in (run1_dir, run2_dir):
        target.mkdir(parents=True, exist_ok=True)

    gates: list[GateResult] = []
    adapter_id = fixture.expected_adapter_id

    generation_gate = _generate_project(
        fixture=fixture,
        output_dir=run1_dir,
        cfg=cfg,
    )
    gates.append(generation_gate)
    if not generation_gate.passed:
        return FixtureResult(
            fixture_id=fixture.fixture_id,
            adapter_id=adapter_id,
            output_dir=str(run1_dir),
            gates=gates,
            diff=None,
        )

    adapter_id = _resolve_adapter_id(run1_dir, fixture.expected_adapter_id)
    gates.extend(_validate_project_files(run1_dir, fixture, adapter_id))
    gates.append(_validate_workflow_gate(run1_dir))
    gates.extend(_run_ci_entrypoint(run1_dir))
    gates.append(_run_security_scan(run1_dir, fixture))

    diff_result: DiffResult | None = None
    if cfg.diff_check:
        diff_result = _run_diff_check(
            fixture=fixture,
            run1_dir=run1_dir,
            run2_dir=run2_dir,
            cfg=cfg,
        )

    return FixtureResult(
        fixture_id=fixture.fixture_id,
        adapter_id=adapter_id,
        output_dir=str(run1_dir),
        gates=gates,
        diff=diff_result,
    )


def _generate_project(
    *,
    fixture: ConformanceFixture,
    output_dir: Path,
    cfg: ConformanceConfig,
) -> GateResult:
    """Generate a project for the fixture using the selected provider."""
    requirements_text = fixture.requirements_path.read_text(encoding="utf-8")
    responses = json.loads(fixture.mock_responses_path.read_text(encoding="utf-8"))

    if cfg.provider != "mock":
        raise ValueError("Only mock provider is supported in conformance suite.")
    provider = MockProvider(responses)
    config = AgentConfig(
        reproducible=cfg.reproducible,
        prompt_seed_base=cfg.conformance_seed,
        security_scan_mode=fixture.security_scan_mode,
    )
    agent = SoftwareDevelopmentAgent(provider=provider, config=config)

    start = time.monotonic()
    try:
        agent.run(requirements=requirements_text, output_dir=output_dir)
    except Exception as exc:  # noqa: BLE001
        duration = time.monotonic() - start
        return GateResult(
            name="generate_project",
            passed=False,
            command="autosd run (mock)",
            exit_code=1,
            duration_seconds=duration,
            stderr=str(exc),
        )

    duration = time.monotonic() - start
    return GateResult(
        name="generate_project",
        passed=True,
        command="autosd run (mock)",
        exit_code=0,
        duration_seconds=duration,
    )


def _resolve_adapter_id(project_dir: Path, fallback: str) -> str:
    """Resolve adapter id from platform plan if available."""
    platform_plan = project_dir / ".autosd" / "platform_plan.json"
    if not platform_plan.exists():
        return fallback
    try:
        payload = json.loads(platform_plan.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback
    adapter_id = payload.get("adapter_id")
    return adapter_id if isinstance(adapter_id, str) else fallback


def _validate_project_files(
    project_dir: Path,
    fixture: ConformanceFixture,
    adapter_id: str,
) -> list[GateResult]:
    """Validate required files and adapter expectations exist."""
    missing: list[str] = []
    for path in fixture.required_paths:
        if not (project_dir / path).exists():
            missing.append(path)

    if not (project_dir / ".gitignore").exists():
        missing.append(".gitignore")

    required_autosd = [
        ".autosd/refined_requirements.md",
        ".autosd/backlog.json",
        ".autosd/design_doc.md",
        ".autosd/platform_plan.json",
        ".autosd/capability_graph.json",
        ".autosd/provenance/build_manifest.json",
        ".autosd/provenance/build_hash.json",
    ]
    for path in required_autosd:
        if not (project_dir / path).exists():
            missing.append(path)

    readme_gate = _readme_instructions_gate(project_dir)
    adapter_gate = _adapter_gate(project_dir, adapter_id)
    missing_gate = GateResult(
        name="required_files",
        passed=not missing,
        notes=missing,
    )
    return [missing_gate, readme_gate, adapter_gate]


def _readme_instructions_gate(project_dir: Path) -> GateResult:
    """Ensure README exists and contains install/run hints."""
    readme = project_dir / "README.md"
    if not readme.exists():
        return GateResult(name="readme_instructions", passed=False, notes=["README missing"])
    content = readme.read_text(encoding="utf-8").lower()
    markers = ["install", "run"]
    missing = [marker for marker in markers if marker not in content]
    return GateResult(
        name="readme_instructions",
        passed=not missing,
        notes=missing,
    )


def _adapter_gate(project_dir: Path, adapter_id: str) -> GateResult:
    """Validate adapter-specific scaffolding markers."""
    catalog = adapter_catalog()
    adapter = catalog.get(adapter_id)
    if adapter is None:
        return GateResult(
            name="adapter_scaffold",
            passed=False,
            notes=[f"unknown_adapter:{adapter_id}"],
        )
    scaffold_files = adapter.scaffold_files(project_dir.name)
    missing = [
        path for path in scaffold_files if not (project_dir / path).exists()
    ]
    return GateResult(
        name="adapter_scaffold",
        passed=not missing,
        notes=missing,
    )


def _validate_workflow_gate(project_dir: Path) -> GateResult:
    """Validate workflow syntax and action pinning."""
    workflow_path = project_dir / ".github" / "workflows" / "ci.yml"
    if not workflow_path.exists():
        return GateResult(
            name="workflow_lint",
            passed=False,
            notes=["ci.yml missing"],
        )
    errors = validate_workflow(workflow_path)
    return GateResult(
        name="workflow_lint",
        passed=not errors,
        notes=errors,
    )


def _run_ci_entrypoint(project_dir: Path) -> list[GateResult]:
    """Run the standardized CI entrypoint script."""
    script = project_dir / "ci" / "run_ci.sh"
    if not script.exists():
        return [
            GateResult(
                name="ci_entrypoint",
                passed=False,
                notes=["ci/run_ci.sh missing"],
            )
        ]
    return [_run_command("ci_entrypoint", "./ci/run_ci.sh", project_dir)]


def _run_security_scan(project_dir: Path, fixture: ConformanceFixture) -> GateResult:
    """Run optional security scan when available."""
    if not _module_available("bandit"):
        required = fixture.security_scan_mode == "required"
        return GateResult(
            name="security_scan",
            passed=not required,
            notes=[
                "bandit not available; skipping"
                if not required
                else "bandit not available but required",
            ],
        )
    if fixture.security_scan_mode == "off":
        return GateResult(name="security_scan", passed=True, notes=["disabled"])
    result = _run_command(
        "security_scan",
        "python -m bandit -q -r . -x tests,.venv,venv,.git,.autosd",
        project_dir,
    )
    if fixture.security_scan_mode == "required":
        return result
    if result.passed:
        return result
    return GateResult(
        name="security_scan",
        passed=True,
        command=result.command,
        exit_code=result.exit_code,
        duration_seconds=result.duration_seconds,
        stdout=result.stdout,
        stderr=result.stderr,
        notes=["bandit findings (non-blocking)"],
    )


def _run_diff_check(
    *,
    fixture: ConformanceFixture,
    run1_dir: Path,
    run2_dir: Path,
    cfg: ConformanceConfig,
) -> DiffResult:
    """Generate a second run and compare outputs for determinism."""
    generation_gate = _generate_project(
        fixture=fixture,
        output_dir=run2_dir,
        cfg=cfg,
    )
    if not generation_gate.passed:
        return DiffResult(
            matched=False,
            differences=[{"path": "run-2", "reason": "generation failed"}],
        )
    checksums_a = build_artifact_checksums(run1_dir)
    checksums_b = build_artifact_checksums(run2_dir)
    differences = _diff_checksums(checksums_a, checksums_b)
    return DiffResult(matched=not differences, differences=differences)


def _diff_checksums(
    checksums_a: dict[str, str],
    checksums_b: dict[str, str],
) -> list[dict[str, str]]:
    """Compute checksum differences between two project snapshots."""
    differences: list[dict[str, str]] = []
    all_paths = set(checksums_a) | set(checksums_b)
    for path in sorted(all_paths):
        if path not in checksums_a:
            differences.append({"path": path, "reason": "missing_in_run1"})
            continue
        if path not in checksums_b:
            differences.append({"path": path, "reason": "missing_in_run2"})
            continue
        if checksums_a[path] != checksums_b[path]:
            differences.append({"path": path, "reason": "checksum_mismatch"})
    return differences


def _run_command(name: str, command: str, cwd: Path) -> GateResult:
    """Run a shell command and capture output."""
    start = time.monotonic()
    try:
        args = shlex.split(command)
        result = subprocess.run(
            args,
            cwd=cwd,
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError as exc:
        duration = time.monotonic() - start
        return GateResult(
            name=name,
            passed=False,
            command=command,
            exit_code=1,
            duration_seconds=duration,
            stderr=str(exc),
        )
    duration = time.monotonic() - start
    stdout = _trim_output(result.stdout)
    stderr = _trim_output(result.stderr)
    return GateResult(
        name=name,
        passed=result.returncode == 0,
        command=command,
        exit_code=result.returncode,
        duration_seconds=duration,
        stdout=stdout,
        stderr=stderr,
    )


def _trim_output(text: str, limit: int = 4000) -> str:
    """Trim output to a safe length."""
    if len(text) <= limit:
        return text
    return text[:limit] + "...<truncated>..."


def _module_available(module_name: str) -> bool:
    """Check module availability without importing it."""
    return importlib.util.find_spec(module_name) is not None


def _repo_root() -> Path:
    """Resolve repository root based on this file location."""
    return Path(__file__).resolve().parents[3]
