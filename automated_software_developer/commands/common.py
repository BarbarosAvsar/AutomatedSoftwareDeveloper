"""Command-line interface for the autonomous software development agent."""

from __future__ import annotations

# ruff: noqa: F401
import json
import subprocess  # nosec B404
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from automated_software_developer import __version__
from automated_software_developer.agent.agile.backlog import (
    AgileBacklog,
    BacklogStoryItem,
    build_backlog,
)
from automated_software_developer.agent.agile.ceremonies import (
    run_retrospective,
    run_sprint_planning,
    run_sprint_review,
    write_retrospective,
)
from automated_software_developer.agent.agile.dod import DoDChecklist, evaluate_definition_of_done
from automated_software_developer.agent.agile.github_sync import (
    GitHubProjectConfig,
    GitHubProjectSync,
)
from automated_software_developer.agent.agile.metrics import MetricsStore
from automated_software_developer.agent.agile.sprint_engine import (
    SprintConfig,
    SprintPlan,
    freeze_sprint,
)
from automated_software_developer.agent.audit import AuditLogger
from automated_software_developer.agent.ci.mirror import run_ci_mirror
from automated_software_developer.agent.ci.workflow_lint import lint_workflows
from automated_software_developer.agent.config_validation import (
    require_positive_int,
    validate_provider_mode,
    validate_sbom_mode,
    validate_security_scan_mode,
)
from automated_software_developer.agent.conformance.runner import (
    ConformanceConfig,
    run_conformance_suite,
)
from automated_software_developer.agent.daemon import CompanyDaemon, DaemonConfig
from automated_software_developer.agent.departments.operations import ReleaseManager
from automated_software_developer.agent.deploy import (
    DeploymentOrchestrator,
    default_deployment_targets,
)
from automated_software_developer.agent.gitops import GitOpsManager
from automated_software_developer.agent.incidents.engine import IncidentEngine
from automated_software_developer.agent.learning import PromptPatternStore, learn_from_journals
from automated_software_developer.agent.orchestrator import AgentConfig, SoftwareDevelopmentAgent
from automated_software_developer.agent.patching import PatchEngine, PatchFilters
from automated_software_developer.agent.plugins.registry import PluginRegistry
from automated_software_developer.agent.policy.engine import (
    evaluate_action,
    resolve_effective_policy,
)
from automated_software_developer.agent.portfolio.dashboard import serve_dashboard
from automated_software_developer.agent.portfolio.registry import PortfolioRegistry
from automated_software_developer.agent.preauth.grants import (
    PreauthGrant,
    create_grant,
    ensure_project_grant_reference,
    list_grants,
    load_grant,
    load_revoked_ids,
    revoke_grant,
    save_grant,
)
from automated_software_developer.agent.preauth.keys import (
    init_keys,
    load_private_key,
    rotate_keys,
)
from automated_software_developer.agent.preauth.verify import grant_break_glass, verify_grant
from automated_software_developer.agent.providers.base import LLMProvider
from automated_software_developer.agent.providers.mock_provider import MockProvider
from automated_software_developer.agent.providers.openai_provider import OpenAIProvider
from automated_software_developer.agent.providers.resilient_llm import ResilientLLM
from automated_software_developer.agent.telemetry.policy import TelemetryPolicy
from automated_software_developer.agent.telemetry.store import TelemetryStore
from automated_software_developer.logging_utils import configure_logging
from automated_software_developer.ui_cli import (
    UICommandError,
    UIServeConfig,
    install_windows_shortcuts,
    remove_windows_shortcuts,
    serve_ui,
)

app = typer.Typer(add_completion=False, no_args_is_help=True)
projects_app = typer.Typer(no_args_is_help=True)
dashboard_app = typer.Typer(no_args_is_help=True)
telemetry_app = typer.Typer(no_args_is_help=True)
incidents_app = typer.Typer(no_args_is_help=True)
preauth_app = typer.Typer(no_args_is_help=True)
backlog_app = typer.Typer(no_args_is_help=True)
sprint_app = typer.Typer(no_args_is_help=True)
plugins_app = typer.Typer(no_args_is_help=True)
ci_app = typer.Typer(no_args_is_help=True)
policy_app = typer.Typer(no_args_is_help=True)
ui_app = typer.Typer(no_args_is_help=True)
console = Console()

app.add_typer(projects_app, name="projects")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(telemetry_app, name="telemetry")
app.add_typer(incidents_app, name="incidents")
app.add_typer(preauth_app, name="preauth")
app.add_typer(backlog_app, name="backlog")
app.add_typer(sprint_app, name="sprint")
app.add_typer(plugins_app, name="plugins")
app.add_typer(ci_app, name="ci")
app.add_typer(policy_app, name="policy")
app.add_typer(ui_app, name="ui")


def _version_callback(value: bool) -> None:
    """Print package version and exit when requested."""
    if value:
        console.print(__version__)
        raise typer.Exit()


def _confirm_destructive_action(message: str, *, force: bool) -> None:
    """Confirm destructive actions unless forced."""
    if force:
        return
    if not typer.confirm(message, default=False):
        raise typer.Exit(code=1)


def _load_requirements(requirements_file: Path | None, requirements_text: str | None) -> str:
    """Load requirements text from file or inline input with mutual exclusivity validation."""
    if requirements_file is None and requirements_text is None:
        raise typer.BadParameter("Provide --requirements-file or --requirements-text.")
    if requirements_file is not None and requirements_text is not None:
        raise typer.BadParameter("Use either --requirements-file or --requirements-text, not both.")
    if requirements_file is not None:
        return requirements_file.read_text(encoding="utf-8")
    if requirements_text is None:
        raise typer.BadParameter(
            "requirements_text cannot be empty when requirements_file is omitted."
        )
    return requirements_text


def _load_mock_responses(mock_responses_file: Path) -> list[dict[str, object]]:
    """Load and validate deterministic mock provider responses."""
    content = mock_responses_file.read_text(encoding="utf-8")
    raw = json.loads(content)
    if not isinstance(raw, list):
        raise typer.BadParameter("--mock-responses-file must contain a JSON list.")
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise typer.BadParameter(f"Mock response index {index} is not an object.")
    return raw


def _create_provider(
    provider: str,
    model: str,
    mock_responses_file: Path | None,
) -> LLMProvider:
    """Create a model provider instance from CLI options."""
    try:
        resolved_provider = validate_provider_mode(provider)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if resolved_provider == "openai":
        return OpenAIProvider(model=model)
    if resolved_provider == "resilient":
        primary = OpenAIProvider(model=model)
        fallback = MockProvider([{}])
        return ResilientLLM(primary=primary, fallback=fallback)
    if mock_responses_file is None:
        raise typer.BadParameter("--mock-responses-file is required when provider=mock.")
    return MockProvider(_load_mock_responses(mock_responses_file))


def _ensure_positive(value: int, field_name: str) -> int:
    """Validate positive integer CLI values."""
    try:
        return require_positive_int(value, field_name)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _validate_security_scan_mode(value: str) -> str:
    """Validate security scan mode option."""
    try:
        return validate_security_scan_mode(value)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _validate_sbom_mode(value: str) -> str:
    """Validate SBOM mode option."""
    try:
        return validate_sbom_mode(value)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _run_gate_command(args: list[str]) -> tuple[bool, float]:
    """Run a shell command for gate enforcement and return success/duration."""
    start = time.monotonic()
    result = subprocess.run(args, check=False)  # nosec B603
    duration = time.monotonic() - start
    return result.returncode == 0, duration


def _write_verify_report(path: Path, payload: dict[str, Any]) -> None:
    """Write verify-factory report payload to disk."""
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _create_registry(registry_path: Path | None) -> PortfolioRegistry:
    """Create a portfolio registry instance from optional CLI path override."""
    if registry_path is None:
        return PortfolioRegistry()
    return PortfolioRegistry(write_path=registry_path, read_paths=[registry_path])


def _create_deployment_orchestrator(registry_path: Path | None) -> DeploymentOrchestrator:
    """Create deployment orchestrator backed by portfolio registry."""
    registry = _create_registry(registry_path)
    return DeploymentOrchestrator(
        registry=registry,
        targets=default_deployment_targets(),
    )


def _create_incident_engine(
    *,
    registry_path: Path | None,
    incidents_path: Path | None,
) -> IncidentEngine:
    """Create incident engine with patch/deploy capabilities wired in."""
    registry = _create_registry(registry_path)
    patch_engine = PatchEngine(registry=registry)
    deployment_orchestrator = DeploymentOrchestrator(
        registry=registry,
        targets=default_deployment_targets(),
    )
    return IncidentEngine(
        registry=registry,
        patch_engine=patch_engine,
        deployment_orchestrator=deployment_orchestrator,
        incidents_path=incidents_path,
    )


def _resolve_project_path(entry_metadata: dict[str, str]) -> Path | None:
    """Resolve local project path from known metadata keys."""
    for key in ("local_path", "workspace_path", "project_path"):
        value = entry_metadata.get(key)
        if value is None:
            continue
        candidate = Path(value).expanduser().resolve()
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def _telemetry_events_path(project_dir: Path) -> Path:
    """Return project-local telemetry events file path."""
    return project_dir / ".autosd" / "telemetry" / "events.jsonl"


def _write_privacy_note(project_dir: Path, policy: TelemetryPolicy) -> None:
    """Write/update privacy note describing telemetry collection constraints."""
    privacy_path = project_dir / "PRIVACY.md"
    lines = [
        "# Privacy",
        "",
        "Telemetry is privacy-preserving and policy-governed.",
        "",
        f"- Mode: `{policy.mode}`",
        f"- Retention: `{policy.retention_days}` days",
        (
            "- No PII, IP addresses, device fingerprints, "
            "request payloads, or user content are collected."
        ),
        "- Event allowlist:",
    ]
    lines.extend(f"  - `{item}`" for item in sorted(policy.event_allowlist) or ["off"])
    privacy_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _cli_error(code: str, message: str, hint: str | None = None) -> typer.BadParameter:
    """Create a standardized CLI error with error code and optional remediation hint."""
    if hint is None:
        return typer.BadParameter(f"[{code}] {message}")
    return typer.BadParameter(f"[{code}] {message} Hint: {hint}")


def _parse_retention_days(raw_value: str) -> int:
    """Parse retention policy strings like '30d' into integer days."""
    cleaned = raw_value.strip().lower()
    if cleaned.endswith("d"):
        cleaned = cleaned[:-1]
    try:
        days = int(cleaned)
    except ValueError as exc:
        raise typer.BadParameter(f"Invalid retention policy value: '{raw_value}'") from exc
    if days <= 0:
        raise typer.BadParameter("Retention days must be greater than zero.")
    return days


def _write_policy_snapshot(project_dir: Path, payload: dict[str, object]) -> None:
    """Persist resolved policy snapshot in project artifacts directory."""
    policy_path = project_dir / ".autosd" / "policy_resolved.json"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _resolve_verified_grant(
    *,
    grant_id: str | None,
    require_preauth: bool,
    required_capability: str | None,
    project_id: str | None,
    environment: str | None,
) -> PreauthGrant | None:
    """Verify optional grant and enforce requirement when requested."""
    if grant_id is None:
        if require_preauth:
            hint = (
                "Create a grant with `autosd preauth create-grant` and pass --preauth-grant <id>."
            )
            if required_capability == "auto_deploy_prod":
                hint = (
                    "Production deploys require a signed grant. "
                    "Create one with `autosd preauth create-grant --auto-deploy-prod` "
                    "and pass --preauth-grant <id>."
                )
            raise _cli_error("AUTOSD-PREAUTH-REQUIRED", "Preauthorization is required.", hint)
        return None
    verification = verify_grant(
        grant_id=grant_id,
        required_capability=required_capability,
        project_id=project_id,
        environment=environment,
    )
    if not verification.valid:
        raise _cli_error(
            "AUTOSD-PREAUTH-INVALID",
            f"Preauthorization verification failed: {verification.reason}",
            "Use `autosd preauth list --active-only` to find a valid grant or create a new one.",
        )
    return verification.grant


__all__ = [name for name in globals() if not name.startswith("__")]
