"""Command-line interface for the autonomous software development agent."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from automated_software_developer.agent.audit import AuditLogger
from automated_software_developer.agent.deploy import (
    DeploymentOrchestrator,
    default_deployment_targets,
)
from automated_software_developer.agent.gitops import GitOpsManager
from automated_software_developer.agent.incidents.engine import IncidentEngine
from automated_software_developer.agent.learning import PromptPatternStore, learn_from_journals
from automated_software_developer.agent.orchestrator import AgentConfig, SoftwareDevelopmentAgent
from automated_software_developer.agent.patching import PatchEngine, PatchFilters
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
from automated_software_developer.agent.telemetry.policy import TelemetryPolicy
from automated_software_developer.agent.telemetry.store import TelemetryStore

app = typer.Typer(add_completion=False, no_args_is_help=True)
projects_app = typer.Typer(no_args_is_help=True)
dashboard_app = typer.Typer(no_args_is_help=True)
telemetry_app = typer.Typer(no_args_is_help=True)
incidents_app = typer.Typer(no_args_is_help=True)
preauth_app = typer.Typer(no_args_is_help=True)
console = Console()

app.add_typer(projects_app, name="projects")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(telemetry_app, name="telemetry")
app.add_typer(incidents_app, name="incidents")
app.add_typer(preauth_app, name="preauth")


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
    if provider == "openai":
        return OpenAIProvider(model=model)
    if provider == "mock":
        if mock_responses_file is None:
            raise typer.BadParameter("--mock-responses-file is required when provider=mock.")
        return MockProvider(_load_mock_responses(mock_responses_file))
    raise typer.BadParameter("provider must be one of: openai, mock")


def _ensure_positive(value: int, field_name: str) -> int:
    """Validate positive integer CLI values."""
    if value <= 0:
        raise typer.BadParameter(f"{field_name} must be greater than zero.")
    return value


def _validate_security_scan_mode(value: str) -> str:
    """Validate security scan mode option."""
    allowed = {"off", "if-available", "required"}
    if value not in allowed:
        raise typer.BadParameter("security-scan-mode must be one of: off, if-available, required.")
    return value


def _validate_sbom_mode(value: str) -> str:
    """Validate SBOM mode option."""
    allowed = {"off", "if-available", "required"}
    if value not in allowed:
        raise typer.BadParameter("sbom-mode must be one of: off, if-available, required.")
    return value


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
            raise typer.BadParameter(
                "Preauthorization is required but --preauth-grant was omitted."
            )
        return None
    verification = verify_grant(
        grant_id=grant_id,
        required_capability=required_capability,
        project_id=project_id,
        environment=environment,
    )
    if not verification.valid:
        raise typer.BadParameter(f"Preauthorization verification failed: {verification.reason}")
    return verification.grant


@app.callback()
def main() -> None:
    """Autonomous software-development agent CLI."""


@app.command()
def run(
    requirements_file: Annotated[
        Path | None,
        typer.Option(help="Path to markdown/text requirements specification."),
    ] = None,
    requirements_text: Annotated[
        str | None,
        typer.Option(help="Inline requirements specification string."),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option(help="Output directory for the generated software project."),
    ] = Path("generated_project"),
    provider: Annotated[
        str,
        typer.Option(help="Model provider to use: openai or mock."),
    ] = "openai",
    model: Annotated[
        str,
        typer.Option(help="Model name when using OpenAI provider."),
    ] = "gpt-5.3-codex",
    mock_responses_file: Annotated[
        Path | None,
        typer.Option(help="JSON file of queued responses when provider=mock."),
    ] = None,
    max_task_attempts: Annotated[
        int,
        typer.Option(help="Maximum retries per story when verification fails."),
    ] = 4,
    timeout_seconds: Annotated[
        int,
        typer.Option(help="Timeout for each verification command."),
    ] = 240,
    max_stories_per_sprint: Annotated[
        int,
        typer.Option(help="Maximum stories selected per sprint iteration."),
    ] = 2,
    enable_learning: Annotated[
        bool,
        typer.Option(
            "--enable-learning/--disable-learning",
            help="Opt-in local learning pass from current run journal.",
        ),
    ] = False,
    update_templates: Annotated[
        bool,
        typer.Option(
            "--update-templates/--no-update-templates",
            help="When learning is enabled, allow versioned prompt template updates.",
        ),
    ] = False,
    preferred_platform: Annotated[
        str | None,
        typer.Option(
            help=(
                "Optional platform adapter override "
                "(web_app, api_service, cli_tool, desktop_app, mobile_app)."
            ),
        ),
    ] = None,
    execute_packaging: Annotated[
        bool,
        typer.Option(
            "--execute-packaging/--plan-packaging",
            help="Execute platform build/package commands (default: plan only).",
        ),
    ] = False,
    quality_gates: Annotated[
        bool,
        typer.Option(
            "--quality-gates/--no-quality-gates",
            help="Enable style/lint/type quality gates in story verification.",
        ),
    ] = True,
    enforce_docstrings: Annotated[
        bool,
        typer.Option(
            "--enforce-docstrings/--no-enforce-docstrings",
            help="Require docstrings for generated public Python functions/classes.",
        ),
    ] = True,
    security_scan: Annotated[
        bool,
        typer.Option(
            "--security-scan/--no-security-scan",
            help="Enable optional security scanning (Bandit when available).",
        ),
    ] = False,
    security_scan_mode: Annotated[
        str,
        typer.Option(
            help="Security scan behavior: off, if-available, required.",
        ),
    ] = "if-available",
    reproducible: Annotated[
        bool,
        typer.Option(
            "--reproducible/--non-reproducible",
            help="Enable reproducible mode metadata and deterministic build intent.",
        ),
    ] = False,
    sbom_mode: Annotated[
        str,
        typer.Option(help="SBOM behavior: off, if-available, required."),
    ] = "if-available",
    gitops_enable: Annotated[
        bool,
        typer.Option(
            "--gitops-enable/--gitops-disable",
            help="Enable local Git commit/tag after successful run.",
        ),
    ] = False,
    gitops_auto_push: Annotated[
        bool,
        typer.Option(
            "--gitops-auto-push/--gitops-no-auto-push",
            help="Push generated project branch when gitops is enabled.",
        ),
    ] = False,
    gitops_tag_release: Annotated[
        bool,
        typer.Option(
            "--gitops-tag-release/--gitops-no-tag-release",
            help="Create a version tag after successful run when gitops is enabled.",
        ),
    ] = True,
) -> None:
    """Run the full autonomous refine -> implement -> verify workflow."""
    requirements = _load_requirements(requirements_file, requirements_text)
    resolved_provider = _create_provider(provider, model, mock_responses_file)
    max_task_attempts = _ensure_positive(max_task_attempts, "max-task-attempts")
    timeout_seconds = _ensure_positive(timeout_seconds, "timeout-seconds")
    max_stories_per_sprint = _ensure_positive(max_stories_per_sprint, "max-stories-per-sprint")
    security_scan_mode = _validate_security_scan_mode(security_scan_mode)
    sbom_mode = _validate_sbom_mode(sbom_mode)
    config = AgentConfig(
        max_task_attempts=max_task_attempts,
        command_timeout_seconds=timeout_seconds,
        max_stories_per_sprint=max_stories_per_sprint,
        enforce_quality_gates=quality_gates,
        enforce_docstrings=enforce_docstrings,
        enable_security_scan=security_scan,
        security_scan_mode=security_scan_mode,
        enable_learning=enable_learning,
        update_templates=update_templates,
        preferred_platform=preferred_platform,
        execute_packaging=execute_packaging,
        reproducible=reproducible,
        sbom_mode=sbom_mode,
    )
    agent = SoftwareDevelopmentAgent(provider=resolved_provider, config=config)

    summary = agent.run(requirements=requirements, output_dir=output_dir)
    table = Table(title="Autonomous Development Summary")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Output Directory", str(summary.output_dir))
    table.add_row("Project Name", summary.project_name)
    table.add_row("Stories Completed", f"{summary.tasks_completed}/{summary.tasks_total}")
    table.add_row("Stack Rationale", summary.stack_rationale)
    table.add_row("Files Changed", str(len(summary.changed_files)))
    if summary.refined_spec_path is not None:
        table.add_row("Refined Spec", str(summary.refined_spec_path))
    if summary.backlog_path is not None:
        table.add_row("Backlog", str(summary.backlog_path))
    if summary.design_doc_path is not None:
        table.add_row("Design Doc", str(summary.design_doc_path))
    if summary.sprint_log_path is not None:
        table.add_row("Sprint Log", str(summary.sprint_log_path))
    if summary.journal_path is not None:
        table.add_row("Prompt Journal", str(summary.journal_path))
    if summary.platform_plan_path is not None:
        table.add_row("Platform Plan", str(summary.platform_plan_path))
    if summary.capability_graph_path is not None:
        table.add_row("Capability Graph", str(summary.capability_graph_path))
    console.print(table)

    console.print("\nVerification commands:")
    for result in summary.verification_results:
        status = "PASS" if result.passed else "FAIL"
        console.print(f"[{status}] {result.command} ({result.duration_seconds:.2f}s)")

    if gitops_enable:
        manager = GitOpsManager()
        tag = "v0.1.0" if gitops_tag_release else None
        git_result = manager.commit_push_tag(
            repo_dir=summary.output_dir,
            message=f"chore(run): autosd generated {summary.project_name}",
            branch=None,
            auto_push=gitops_auto_push,
            tag=tag,
        )
        console.print("\nGitOps:")
        console.print(f"- committed: {git_result.committed}")
        console.print(f"- pushed: {git_result.pushed}")
        console.print(f"- pending_push: {git_result.pending_push}")
        console.print(f"- commit_sha: {git_result.commit_sha or '-'}")


@app.command()
def refine(
    requirements_file: Annotated[
        Path | None,
        typer.Option(help="Path to markdown/text requirements specification."),
    ] = None,
    requirements_text: Annotated[
        str | None,
        typer.Option(help="Inline requirements specification string."),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option(help="Output directory where refined artifact is written."),
    ] = Path("generated_project"),
    provider: Annotated[
        str,
        typer.Option(help="Model provider to use: openai or mock."),
    ] = "openai",
    model: Annotated[
        str,
        typer.Option(help="Model name when using OpenAI provider."),
    ] = "gpt-5.3-codex",
    mock_responses_file: Annotated[
        Path | None,
        typer.Option(help="JSON file of queued responses when provider=mock."),
    ] = None,
) -> None:
    """Run only autonomous requirements refinement."""
    requirements = _load_requirements(requirements_file, requirements_text)
    resolved_provider = _create_provider(provider, model, mock_responses_file)
    agent = SoftwareDevelopmentAgent(provider=resolved_provider)
    refined = agent.refine_requirements(requirements=requirements, output_dir=output_dir)
    artifact_path = output_dir / ".autosd" / "refined_requirements.md"
    console.print(f"Refined specification written to: {artifact_path}")
    console.print(f"Stories identified: {len(refined.stories)}")


@app.command()
def learn(
    journals: Annotated[
        list[Path],
        typer.Option(
            "--journals",
            help="One or more prompt_journal.jsonl paths.",
        ),
    ],
    update_templates: Annotated[
        bool,
        typer.Option(
            "--update-templates/--no-update-templates",
            help="Persist incremented prompt template versions from journal signals.",
        ),
    ] = False,
    changelog_path: Annotated[
        Path,
        typer.Option(help="Path for human-readable prompt template change log."),
    ] = Path("PROMPT_TEMPLATE_CHANGES.md"),
) -> None:
    """Summarize journal history and optionally update versioned prompt templates."""
    if not journals:
        raise typer.BadParameter("Provide at least one --journals path.")
    store = PromptPatternStore()
    summary = learn_from_journals(
        journal_paths=journals,
        pattern_store=store,
        update_templates=update_templates,
        playbook_path=Path("PROMPT_PLAYBOOK.md"),
        changelog_path=changelog_path,
    )
    table = Table(title="Learning Summary")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Entries Processed", str(summary.entries_processed))
    table.add_row("Templates Considered", str(summary.templates_considered))
    table.add_row("Template Proposals", str(len(summary.proposals)))
    table.add_row("Template Updates", str(len(summary.updates)))
    table.add_row("Failure Signals", json.dumps(summary.failure_signals))
    table.add_row("Change Log", str(summary.changelog_path))
    console.print(table)
    if summary.proposals:
        console.print("\nTemplate proposals:")
        for proposal in summary.proposals:
            console.print(
                f"- {proposal.template_id} (base v{proposal.base_version}): {proposal.reason}"
            )
    if summary.updates:
        console.print("\nTemplate updates:")
        for update in summary.updates:
            console.print(
                f"- {update.template_id}: v{update.old_version} -> v{update.new_version} "
                f"({update.path})"
            )


@projects_app.command("list")
def projects_list(
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    include_archived: Annotated[
        bool,
        typer.Option("--include-archived/--exclude-archived"),
    ] = False,
) -> None:
    """List registered generated projects."""
    registry = _create_registry(registry_path)
    entries = registry.list_entries(include_archived=include_archived)
    table = Table(title="Project Portfolio")
    table.add_column("Project ID")
    table.add_column("Name")
    table.add_column("Platforms")
    table.add_column("Version")
    table.add_column("Health")
    table.add_column("Archived")
    if not entries:
        console.print("No projects registered.")
        return
    for entry in entries:
        table.add_row(
            entry.project_id,
            entry.name,
            ", ".join(entry.platforms),
            entry.current_version,
            entry.health_status,
            "yes" if entry.archived else "no",
        )
    console.print(table)


@projects_app.command("show")
def projects_show(
    project_id: Annotated[str, typer.Argument(help="Project ID or exact name.")],
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
) -> None:
    """Show detailed metadata for one project."""
    registry = _create_registry(registry_path)
    entry = registry.get(project_id)
    if entry is None:
        raise typer.BadParameter(f"Project '{project_id}' not found.")
    console.print_json(json.dumps(entry.to_dict(), indent=2))


@projects_app.command("status")
def projects_status(
    all_projects: Annotated[
        bool,
        typer.Option("--all", help="Include archived projects."),
    ] = False,
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
) -> None:
    """Show compact project health and CI status table."""
    registry = _create_registry(registry_path)
    rows = registry.status_rows(include_archived=all_projects)
    table = Table(title="Project Status")
    table.add_column("Project ID")
    table.add_column("Name")
    table.add_column("Version")
    table.add_column("Health")
    table.add_column("CI")
    table.add_column("Security")
    table.add_column("Halted")
    if not rows:
        console.print("No project statuses available.")
        return
    for row in rows:
        table.add_row(
            row["project_id"],
            row["name"],
            row["version"],
            row["health"],
            row["ci"],
            row["security"],
            row["halted"],
        )
    console.print(table)


@projects_app.command("open")
def projects_open(
    project_id: Annotated[str, typer.Argument(help="Project ID or exact name.")],
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
) -> None:
    """Print repository URL and key metadata for one project."""
    registry = _create_registry(registry_path)
    entry = registry.get(project_id)
    if entry is None:
        raise typer.BadParameter(f"Project '{project_id}' not found.")
    payload = {
        "project_id": entry.project_id,
        "name": entry.name,
        "repo_url": entry.repo_url or "<none>",
        "default_branch": entry.default_branch,
        "current_version": entry.current_version,
    }
    console.print_json(json.dumps(payload, indent=2))


@projects_app.command("retire")
def projects_retire(
    project_id: Annotated[str, typer.Argument(help="Project ID or exact name.")],
    reason: Annotated[
        str,
        typer.Option(help="Retirement reason stored in project metadata."),
    ] = "retired by operator",
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
) -> None:
    """Retire one project and disable automation by default."""
    registry = _create_registry(registry_path)
    updated = registry.retire(project_id, reason=reason)
    console.print(
        f"Project '{updated.project_id}' retired. automation_halted={updated.automation_halted}"
    )


@app.command("halt")
def halt_project(
    project: Annotated[str, typer.Option(help="Project ID or exact name.")],
    reason: Annotated[
        str,
        typer.Option(help="Reason recorded in project metadata."),
    ] = "manual halt",
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
) -> None:
    """Halt autonomous actions for a project (kill switch)."""
    registry = _create_registry(registry_path)
    entry = registry.get(project)
    if entry is None:
        raise typer.BadParameter(f"Project '{project}' not found.")
    metadata = dict(entry.metadata)
    metadata["halt_reason"] = reason
    metadata["halted_at"] = datetime.now(tz=UTC).isoformat()
    registry.update(entry.project_id, automation_halted=True, metadata=metadata)
    console.print(f"Automation halted for '{entry.project_id}'.")


@app.command("resume")
def resume_project(
    project: Annotated[str, typer.Option(help="Project ID or exact name.")],
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
) -> None:
    """Resume autonomous actions for a halted project."""
    registry = _create_registry(registry_path)
    entry = registry.get(project)
    if entry is None:
        raise typer.BadParameter(f"Project '{project}' not found.")
    metadata = dict(entry.metadata)
    metadata["resumed_at"] = datetime.now(tz=UTC).isoformat()
    registry.update(entry.project_id, automation_halted=False, metadata=metadata)
    console.print(f"Automation resumed for '{entry.project_id}'.")


@dashboard_app.command("serve")
def dashboard_serve(
    host: Annotated[
        str,
        typer.Option(help="Host interface for local dashboard API."),
    ] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="TCP port for local dashboard API.")] = 8765,
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
) -> None:
    """Serve read-only local portfolio dashboard API."""
    if port <= 0 or port > 65535:
        raise typer.BadParameter("port must be between 1 and 65535.")
    registry = _create_registry(registry_path)
    console.print(f"Serving dashboard on http://{host}:{port}")
    serve_dashboard(registry=registry, host=host, port=port)


@telemetry_app.command("enable")
def telemetry_enable(
    project: Annotated[str, typer.Option(help="Project ID or exact name.")],
    mode: Annotated[
        str,
        typer.Option(help="Telemetry mode: off, anonymous, minimal, custom."),
    ] = "anonymous",
    retention_days: Annotated[
        int,
        typer.Option(help="Telemetry retention period in days."),
    ] = 30,
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
) -> None:
    """Enable or disable privacy-safe telemetry policy for a project."""
    policy = TelemetryPolicy.from_mode(mode, retention_days=retention_days)
    registry = _create_registry(registry_path)
    entry = registry.get(project)
    if entry is None:
        raise typer.BadParameter(f"Project '{project}' not found.")
    updated = registry.update(
        entry.project_id,
        telemetry_policy=policy.mode,
        data_retention_policy=f"{policy.retention_days}d",
    )
    project_dir = _resolve_project_path(updated.metadata)
    if project_dir is not None:
        _write_privacy_note(project_dir, policy)
    console.print(
        f"Telemetry policy for '{updated.project_id}' set to {policy.mode} "
        f"with {policy.retention_days}d retention."
    )


@telemetry_app.command("report")
def telemetry_report(
    project: Annotated[str, typer.Option(help="Project ID or exact name.")],
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
) -> None:
    """Ingest local telemetry events and print aggregate report for one project."""
    registry = _create_registry(registry_path)
    entry = registry.get(project)
    if entry is None:
        raise typer.BadParameter(f"Project '{project}' not found.")
    retention_days = _parse_retention_days(entry.data_retention_policy)
    policy = TelemetryPolicy.from_mode(entry.telemetry_policy, retention_days=retention_days)
    if policy.mode == "off":
        console.print(f"Telemetry is disabled for '{entry.project_id}'.")
        return
    project_dir = _resolve_project_path(entry.metadata)
    if project_dir is None:
        raise typer.BadParameter(
            f"Project '{entry.project_id}' has no local path metadata for telemetry ingestion."
        )
    events_path = _telemetry_events_path(project_dir)
    store = TelemetryStore()
    ingested = store.ingest_events_file(
        project_id=entry.project_id,
        events_path=events_path,
        policy=policy,
    )
    deleted = store.enforce_retention(policy.retention_days)
    report = store.report_project(entry.project_id)
    table = Table(title=f"Telemetry Report: {entry.project_id}")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Events Ingested", str(ingested))
    table.add_row("Events Pruned", str(deleted))
    table.add_row("Total Events", str(report.event_count))
    table.add_row("Error Events", str(report.error_events))
    table.add_row("Crash Events", str(report.crash_events))
    table.add_row("Average Value", f"{report.avg_value:.4f}")
    console.print(table)


@telemetry_app.command("report-all")
def telemetry_report_all(
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    domain: Annotated[
        str | None,
        typer.Option(help="Optional exact domain filter."),
    ] = None,
    platform: Annotated[
        str | None,
        typer.Option(help="Optional platform filter."),
    ] = None,
) -> None:
    """Ingest and report telemetry for all registered projects with telemetry enabled."""
    registry = _create_registry(registry_path)
    entries = registry.list_entries(include_archived=False)
    store = TelemetryStore()
    reports: list[tuple[str, int, int, int, float]] = []
    for entry in entries:
        if domain is not None and entry.domain != domain:
            continue
        if platform is not None and platform not in entry.platforms:
            continue
        retention_days = _parse_retention_days(entry.data_retention_policy)
        policy = TelemetryPolicy.from_mode(entry.telemetry_policy, retention_days=retention_days)
        if policy.mode == "off":
            continue
        project_dir = _resolve_project_path(entry.metadata)
        if project_dir is None:
            continue
        events_path = _telemetry_events_path(project_dir)
        store.ingest_events_file(
            project_id=entry.project_id,
            events_path=events_path,
            policy=policy,
        )
        store.enforce_retention(policy.retention_days)
        report = store.report_project(entry.project_id)
        reports.append(
            (
                report.project_id,
                report.event_count,
                report.error_events,
                report.crash_events,
                report.avg_value,
            )
        )
    if not reports:
        console.print("No telemetry reports available for selected projects.")
        return
    table = Table(title="Telemetry Reports")
    table.add_column("Project")
    table.add_column("Events")
    table.add_column("Errors")
    table.add_column("Crashes")
    table.add_column("Avg Value")
    for project_id, events, errors, crashes, avg_value in reports:
        table.add_row(project_id, str(events), str(errors), str(crashes), f"{avg_value:.4f}")
    console.print(table)


@incidents_app.command("list")
def incidents_list(
    project: Annotated[
        str | None,
        typer.Option(help="Optional project ID filter."),
    ] = None,
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    incidents_path: Annotated[
        Path | None,
        typer.Option(help="Optional incidents JSONL path override."),
    ] = None,
) -> None:
    """List incidents from append-only incident ledger."""
    engine = _create_incident_engine(registry_path=registry_path, incidents_path=incidents_path)
    records = engine.list_incidents(project_id=project)
    if not records:
        console.print("No incidents found.")
        return
    table = Table(title="Incidents")
    table.add_column("Incident")
    table.add_column("Project")
    table.add_column("Status")
    table.add_column("Severity")
    table.add_column("Source")
    for record in records:
        table.add_row(
            record.incident_id,
            record.project_id,
            record.status,
            record.severity,
            record.source,
        )
    console.print(table)


@incidents_app.command("show")
def incidents_show(
    incident_id: Annotated[str, typer.Argument(help="Incident identifier.")],
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    incidents_path: Annotated[
        Path | None,
        typer.Option(help="Optional incidents JSONL path override."),
    ] = None,
) -> None:
    """Show one incident record."""
    engine = _create_incident_engine(registry_path=registry_path, incidents_path=incidents_path)
    incident = engine.get_incident(incident_id)
    if incident is None:
        raise typer.BadParameter(f"Incident '{incident_id}' not found.")
    console.print_json(json.dumps(incident.to_dict(), indent=2))


@app.command("heal")
def heal_project(
    project: Annotated[str, typer.Option(help="Project ID or exact name.")],
    incident: Annotated[
        str | None,
        typer.Option(help="Optional existing incident ID."),
    ] = None,
    target: Annotated[
        str | None,
        typer.Option(
            "--target",
            help="Optional deployment target after patch (docker/github_pages/generic_container).",
        ),
    ] = None,
    env: Annotated[
        str,
        typer.Option("--env", help="Deployment environment when target is provided."),
    ] = "staging",
    auto_push: Annotated[
        bool,
        typer.Option("--auto-push/--no-auto-push", help="Push healing patch branch."),
    ] = False,
    execute_deploy: Annotated[
        bool,
        typer.Option(
            "--execute-deploy/--scaffold-deploy",
            help="Execute deploy target commands when possible.",
        ),
    ] = False,
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    incidents_path: Annotated[
        Path | None,
        typer.Option(help="Optional incidents JSONL path override."),
    ] = None,
    require_preauth: Annotated[
        bool,
        typer.Option("--require-preauth", help="Require valid preauthorization grant."),
    ] = False,
    preauth_grant: Annotated[
        str | None,
        typer.Option("--preauth-grant", help="Grant ID used for healing authorization."),
    ] = None,
) -> None:
    """Run incident-driven self-healing (patch -> optional deploy -> postmortem)."""
    registry = _create_registry(registry_path)
    entry = registry.get(project)
    if entry is None:
        raise typer.BadParameter(f"Project '{project}' not found.")
    required_capability = "auto_heal" if (require_preauth or preauth_grant is not None) else None
    grant = _resolve_verified_grant(
        grant_id=preauth_grant,
        require_preauth=require_preauth,
        required_capability=required_capability,
        project_id=entry.project_id,
        environment=env if target is not None else None,
    )
    project_dir = _resolve_project_path(entry.metadata)
    if grant is not None and project_dir is not None:
        ensure_project_grant_reference(project_dir, grant.grant_id)
    policy = resolve_effective_policy(project_policy=None, grant=grant)
    if project_dir is not None:
        _write_policy_snapshot(project_dir, policy.to_dict())
    if auto_push:
        push_decision = evaluate_action(policy=policy, action="auto_push")
        if not push_decision.allowed:
            raise typer.BadParameter(f"Policy blocked heal auto-push: {push_decision.reason}")
    if target is not None:
        deploy_decision = evaluate_action(policy=policy, action="deploy", environment=env)
        if not deploy_decision.allowed:
            raise typer.BadParameter(f"Policy blocked heal deploy: {deploy_decision.reason}")
    engine = _create_incident_engine(registry_path=registry_path, incidents_path=incidents_path)
    result = engine.heal_project(
        project_ref=entry.project_id,
        incident_id=incident,
        auto_push=auto_push,
        deploy_target=target,
        environment=env,
        execute_deploy=execute_deploy,
    )
    table = Table(title="Heal Result")
    table.add_column("Incident")
    table.add_column("Project")
    table.add_column("Status")
    table.add_column("Patch")
    table.add_column("Deploy")
    table.add_row(
        result.incident.incident_id,
        result.incident.project_id,
        result.incident.status,
        "ok" if result.patch_outcome.success else "failed",
        "n/a"
        if result.deploy_outcome is None
        else ("ok" if result.deploy_outcome.success else "failed"),
    )
    console.print(table)
    if result.incident.postmortem_path is not None:
        console.print(f"Postmortem: {result.incident.postmortem_path}")
    AuditLogger().log(
        project_id=entry.project_id,
        action="heal",
        result="success" if result.incident.status == "resolved" else "failed",
        grant_id=grant.grant_id if grant is not None else None,
        gates_run=["patch", "deploy" if target else "patch_only"],
        commit_ref=result.patch_outcome.commit_sha,
        tag_ref=None,
        break_glass_used=grant_break_glass(grant),
        details={
            "incident_id": result.incident.incident_id,
            "deploy_target": target,
            "environment": env,
        },
    )
    if result.incident.status != "resolved":
        raise typer.Exit(code=1)


@preauth_app.command("init-keys")
def preauth_init_keys() -> None:
    """Initialize local Ed25519 keypair for preauthorization grants."""
    paths = init_keys()
    console.print(f"Private key: {paths.private_key_path}")
    console.print(f"Public key: {paths.public_key_path}")


@preauth_app.command("rotate-keys")
def preauth_rotate_keys() -> None:
    """Rotate preauthorization keypair while retaining archived public keys."""
    paths = rotate_keys()
    console.print(f"Rotated private key: {paths.private_key_path}")
    console.print(f"Rotated public key: {paths.public_key_path}")


@preauth_app.command("create-grant")
def preauth_create_grant(
    issuer: Annotated[str, typer.Option(help="Issuer label for audit trail.")] = "owner",
    project_ids: Annotated[
        list[str] | None,
        typer.Option("--project-ids", help="Allowed project IDs; repeat flag for multiple."),
    ] = None,
    expires_in_hours: Annotated[
        int,
        typer.Option(help="Grant expiry in hours."),
    ] = 1,
    auto_push: Annotated[
        bool,
        typer.Option("--auto-push/--no-auto-push"),
    ] = False,
    auto_merge_pr: Annotated[
        bool,
        typer.Option("--auto-merge-pr/--no-auto-merge-pr"),
    ] = False,
    auto_deploy_dev: Annotated[
        bool,
        typer.Option("--auto-deploy-dev/--no-auto-deploy-dev"),
    ] = True,
    auto_deploy_staging: Annotated[
        bool,
        typer.Option("--auto-deploy-staging/--no-auto-deploy-staging"),
    ] = True,
    auto_deploy_prod: Annotated[
        bool,
        typer.Option("--auto-deploy-prod/--no-auto-deploy-prod"),
    ] = False,
    auto_rollback: Annotated[
        bool,
        typer.Option("--auto-rollback/--no-auto-rollback"),
    ] = True,
    auto_heal: Annotated[
        bool,
        typer.Option("--auto-heal/--no-auto-heal"),
    ] = True,
    create_repos: Annotated[
        bool,
        typer.Option("--create-repos/--no-create-repos"),
    ] = False,
    rotate_deployments: Annotated[
        bool,
        typer.Option("--rotate-deployments/--no-rotate-deployments"),
    ] = False,
    publish_app_store: Annotated[
        bool,
        typer.Option("--publish-app-store/--no-publish-app-store"),
    ] = False,
    break_glass: Annotated[
        bool,
        typer.Option("--break-glass/--no-break-glass"),
    ] = False,
) -> None:
    """Create and sign a preauthorization grant."""
    init_keys()
    private_key = load_private_key()
    scope = {
        "project_ids": project_ids or "*",
        "domains": [],
        "platforms": [],
    }
    capabilities = {
        "auto_push": auto_push,
        "auto_merge_pr": auto_merge_pr,
        "auto_deploy_dev": auto_deploy_dev,
        "auto_deploy_staging": auto_deploy_staging,
        "auto_deploy_prod": auto_deploy_prod,
        "auto_rollback": auto_rollback,
        "auto_heal": auto_heal,
        "create_repos": create_repos,
        "rotate_deployments": rotate_deployments,
        "publish_app_store": publish_app_store,
    }
    required_gates = {
        "quality_gates": True,
        "security_scan_mode": "if-available",
        "sbom": "if-available",
        "dependency_audit": "if-available",
        "canary_required_for_prod": True,
        "min_test_scope": "suite",
    }
    budgets = {
        "max_deploys_per_day": 20,
        "max_patches_per_incident": 3,
        "max_auto_merges_per_day": 10,
        "max_failures_before_halt": 5,
    }
    telemetry = {
        "allowed_modes": ["off", "anonymous", "minimal", "custom"],
        "retention_max_days": 30,
        "event_allowlist_ref": "default",
    }
    grant = create_grant(
        issuer=issuer,
        scope=scope,
        capabilities=capabilities,
        required_gates=required_gates,
        budgets=budgets,
        telemetry=telemetry,
        expires_in_hours=expires_in_hours,
        break_glass=break_glass,
        private_key=private_key,
    )
    output_path = save_grant(grant)
    console.print(f"Grant created: {grant.grant_id}")
    console.print(f"Path: {output_path}")


@preauth_app.command("list")
def preauth_list() -> None:
    """List available signed grants."""
    grants = list_grants()
    if not grants:
        console.print("No grants found.")
        return
    table = Table(title="Preauth Grants")
    table.add_column("Grant ID")
    table.add_column("Issuer")
    table.add_column("Expires")
    table.add_column("Break Glass")
    for grant in grants:
        payload = grant.to_dict()
        table.add_row(
            grant.grant_id,
            str(payload.get("issuer", "")),
            str(payload.get("expires_at", "")),
            "yes" if bool(payload.get("break_glass", False)) else "no",
        )
    console.print(table)


@preauth_app.command("show")
def preauth_show(
    grant_id: Annotated[str, typer.Argument(help="Grant identifier.")],
) -> None:
    """Show one grant payload."""
    grant = load_grant(grant_id)
    if grant is None:
        raise typer.BadParameter(f"Grant '{grant_id}' not found.")
    console.print_json(json.dumps(grant.to_dict(), indent=2))


@preauth_app.command("revoke")
def preauth_revoke(
    grant_id: Annotated[str, typer.Argument(help="Grant identifier.")],
    reason: Annotated[str, typer.Option(help="Revocation reason.")] = "revoked",
) -> None:
    """Revoke a grant immediately."""
    revoke_grant(grant_id, reason=reason)
    console.print(f"Grant revoked: {grant_id}")


@app.command("patch")
def patch_project(
    project: Annotated[str, typer.Option(help="Project ID or exact name.")],
    reason: Annotated[str, typer.Option(help="Patch reason for changelog/commit.")] = "maintenance",
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    auto_push: Annotated[
        bool,
        typer.Option("--auto-push/--no-auto-push", help="Push patch branch to origin."),
    ] = False,
    create_tag: Annotated[
        bool,
        typer.Option("--create-tag/--no-create-tag", help="Create version tag for patch."),
    ] = True,
    require_preauth: Annotated[
        bool,
        typer.Option("--require-preauth", help="Require valid preauthorization grant."),
    ] = False,
    preauth_grant: Annotated[
        str | None,
        typer.Option("--preauth-grant", help="Grant ID used for privileged patch actions."),
    ] = None,
) -> None:
    """Run patch workflow for a single project."""
    if not project.strip():
        raise typer.BadParameter("project must be non-empty.")
    registry = _create_registry(registry_path)
    entry = registry.get(project)
    if entry is None:
        raise typer.BadParameter(f"Project '{project}' not found.")
    required_capability = "auto_push" if auto_push else None
    grant = _resolve_verified_grant(
        grant_id=preauth_grant,
        require_preauth=require_preauth or (auto_push and preauth_grant is None),
        required_capability=required_capability,
        project_id=entry.project_id,
        environment=None,
    )
    project_dir = _resolve_project_path(entry.metadata)
    if grant is not None and project_dir is not None:
        ensure_project_grant_reference(project_dir, grant.grant_id)
    policy = resolve_effective_policy(project_policy=None, grant=grant)
    if project_dir is not None:
        _write_policy_snapshot(project_dir, policy.to_dict())
    if auto_push:
        decision = evaluate_action(policy=policy, action="auto_push")
        if not decision.allowed:
            raise typer.BadParameter(f"Policy blocked action: {decision.reason}")
    engine = PatchEngine(registry=registry)
    outcome = engine.patch_project(
        entry.project_id,
        reason=reason,
        auto_push=auto_push,
        create_tag=create_tag,
    )
    table = Table(title="Patch Result")
    table.add_column("Project")
    table.add_column("Status")
    table.add_column("Branch")
    table.add_column("Version")
    table.add_column("Commit")
    table.add_row(
        outcome.project_id,
        "ok" if outcome.success else "failed",
        outcome.branch or "-",
        f"{outcome.old_version} -> {outcome.new_version or '-'}",
        outcome.commit_sha or "-",
    )
    console.print(table)
    AuditLogger().log(
        project_id=entry.project_id,
        action="patch",
        result="success" if outcome.success else "failed",
        grant_id=grant.grant_id if grant is not None else None,
        gates_run=["quality_gates", "version_bump"],
        commit_ref=outcome.commit_sha,
        tag_ref=(
            f"v{outcome.new_version}"
            if outcome.new_version is not None and create_tag
            else None
        ),
        break_glass_used=grant_break_glass(grant),
        details={"reason": reason, "branch": outcome.branch},
    )
    if outcome.error is not None:
        raise typer.Exit(code=1)


@app.command("patch-all")
def patch_all_projects(
    reason: Annotated[str, typer.Option(help="Patch reason for changelog/commit.")] = "maintenance",
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    domain: Annotated[
        str | None,
        typer.Option(help="Filter by exact project domain."),
    ] = None,
    platform: Annotated[
        str | None,
        typer.Option(help="Filter by platform identifier."),
    ] = None,
    needs_security: Annotated[
        bool,
        typer.Option(help="Only projects with non-green security status."),
    ] = False,
    needs_upgrade: Annotated[
        bool,
        typer.Option(help="Only projects with metadata.needs_upgrade=true."),
    ] = False,
    telemetry_enabled: Annotated[
        bool,
        typer.Option(help="Only projects with telemetry enabled."),
    ] = False,
    deployed: Annotated[
        bool,
        typer.Option(help="Only projects with at least one deploy record."),
    ] = False,
    auto_push: Annotated[
        bool,
        typer.Option("--auto-push/--no-auto-push", help="Push patch branches to origin."),
    ] = False,
    create_tag: Annotated[
        bool,
        typer.Option("--create-tag/--no-create-tag", help="Create version tags for patches."),
    ] = True,
    require_preauth: Annotated[
        bool,
        typer.Option("--require-preauth", help="Require valid preauthorization grant."),
    ] = False,
    preauth_grant: Annotated[
        str | None,
        typer.Option("--preauth-grant", help="Grant ID used for privileged patch actions."),
    ] = None,
) -> None:
    """Run patch workflow for all projects matching filters."""
    registry = _create_registry(registry_path)
    required_capability = "auto_push" if auto_push else None
    grant = _resolve_verified_grant(
        grant_id=preauth_grant,
        require_preauth=require_preauth or (auto_push and preauth_grant is None),
        required_capability=required_capability,
        project_id=None,
        environment=None,
    )
    policy = resolve_effective_policy(project_policy=None, grant=grant)
    if auto_push:
        decision = evaluate_action(policy=policy, action="auto_push")
        if not decision.allowed:
            raise typer.BadParameter(f"Policy blocked action: {decision.reason}")
    engine = PatchEngine(registry=registry)
    filters = PatchFilters(
        domain=domain,
        platform=platform,
        needs_security=needs_security,
        needs_upgrade=needs_upgrade,
        telemetry_enabled=telemetry_enabled,
        deployed=deployed,
    )
    outcomes = engine.patch_all(
        reason=reason,
        filters=filters,
        auto_push=auto_push,
        create_tag=create_tag,
    )
    table = Table(title="Patch-All Results")
    table.add_column("Project")
    table.add_column("Status")
    table.add_column("Version")
    table.add_column("Pending Push")
    if not outcomes:
        console.print("No projects matched the selected filters.")
        return
    failures = 0
    for outcome in outcomes:
        if not outcome.success:
            failures += 1
        AuditLogger().log(
            project_id=outcome.project_id,
            action="patch_all_item",
            result="success" if outcome.success else "failed",
            grant_id=grant.grant_id if grant is not None else None,
            gates_run=["quality_gates", "version_bump"],
            commit_ref=outcome.commit_sha,
            tag_ref=(
                f"v{outcome.new_version}"
                if outcome.new_version is not None and create_tag
                else None
            ),
            break_glass_used=grant_break_glass(grant),
            details={"reason": reason, "branch": outcome.branch},
        )
        table.add_row(
            outcome.project_id,
            "ok" if outcome.success else "failed",
            f"{outcome.old_version} -> {outcome.new_version or '-'}",
            "yes" if outcome.pending_push else "no",
        )
    console.print(table)
    if failures > 0:
        raise typer.Exit(code=1)


@app.command("deploy")
def deploy_project(
    project: Annotated[str, typer.Option(help="Project ID or exact name.")],
    env: Annotated[
        str,
        typer.Option("--env", help="Target environment: dev, staging, or prod."),
    ] = "dev",
    target: Annotated[
        str,
        typer.Option(
            "--target",
            help="Deployment target (docker, github_pages, generic_container).",
        ),
    ] = "generic_container",
    strategy: Annotated[
        str,
        typer.Option(help="Deployment strategy: standard, canary, blue-green."),
    ] = "standard",
    execute: Annotated[
        bool,
        typer.Option(
            "--execute/--scaffold-only",
            help="Run target commands when possible; default is scaffold-only.",
        ),
    ] = False,
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    require_preauth: Annotated[
        bool,
        typer.Option("--require-preauth", help="Require valid preauthorization grant."),
    ] = False,
    preauth_grant: Annotated[
        str | None,
        typer.Option("--preauth-grant", help="Grant ID used for privileged deploy actions."),
    ] = None,
) -> None:
    """Deploy one project to selected target/environment."""
    registry = _create_registry(registry_path)
    entry = registry.get(project)
    if entry is None:
        raise typer.BadParameter(f"Project '{project}' not found.")
    env_normalized = env.strip().lower()
    capability_by_env = {
        "dev": "auto_deploy_dev",
        "staging": "auto_deploy_staging",
        "prod": "auto_deploy_prod",
    }
    required_capability = capability_by_env.get(env_normalized)
    if required_capability is None:
        raise typer.BadParameter("env must be one of: dev, staging, prod")
    grant = _resolve_verified_grant(
        grant_id=preauth_grant,
        require_preauth=require_preauth or (env_normalized == "prod"),
        required_capability=required_capability,
        project_id=entry.project_id,
        environment=env_normalized,
    )
    project_dir = _resolve_project_path(entry.metadata)
    if grant is not None and project_dir is not None:
        ensure_project_grant_reference(project_dir, grant.grant_id)
    policy = resolve_effective_policy(project_policy=None, grant=grant)
    if project_dir is not None:
        _write_policy_snapshot(project_dir, policy.to_dict())
    decision = evaluate_action(policy=policy, action="deploy", environment=env_normalized)
    if not decision.allowed:
        raise typer.BadParameter(f"Policy blocked deploy action: {decision.reason}")
    orchestrator = _create_deployment_orchestrator(registry_path)
    result = orchestrator.deploy(
        project_ref=entry.project_id,
        environment=env_normalized,
        target=target,
        strategy=strategy,
        execute=execute,
    )
    table = Table(title="Deploy Result")
    table.add_column("Project")
    table.add_column("Target")
    table.add_column("Env")
    table.add_column("Version")
    table.add_column("Status")
    table.add_row(
        result.project_id,
        result.target,
        result.environment,
        result.version,
        "ok" if result.success else "failed",
    )
    console.print(table)
    console.print(result.message)
    AuditLogger().log(
        project_id=entry.project_id,
        action="deploy",
        result="success" if result.success else "failed",
        grant_id=grant.grant_id if grant is not None else None,
        gates_run=["deployment_policy", "target_scaffold"],
        commit_ref=None,
        tag_ref=None,
        break_glass_used=grant_break_glass(grant),
        details={
            "environment": env_normalized,
            "target": target,
            "strategy": strategy,
            "scaffold_only": result.scaffold_only,
        },
    )
    if not result.success:
        raise typer.Exit(code=1)


@app.command("rollback")
def rollback_project(
    project: Annotated[str, typer.Option(help="Project ID or exact name.")],
    env: Annotated[str, typer.Option("--env", help="Target environment.")] = "dev",
    target: Annotated[
        str,
        typer.Option(
            "--target",
            help="Deployment target (docker, github_pages, generic_container).",
        ),
    ] = "generic_container",
    execute: Annotated[
        bool,
        typer.Option(
            "--execute/--scaffold-only",
            help="Run rollback commands when possible; default is scaffold-only.",
        ),
    ] = False,
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    require_preauth: Annotated[
        bool,
        typer.Option("--require-preauth", help="Require valid preauthorization grant."),
    ] = False,
    preauth_grant: Annotated[
        str | None,
        typer.Option("--preauth-grant", help="Grant ID used for rollback authorization."),
    ] = None,
) -> None:
    """Rollback one project deployment."""
    registry = _create_registry(registry_path)
    entry = registry.get(project)
    if entry is None:
        raise typer.BadParameter(f"Project '{project}' not found.")
    grant = _resolve_verified_grant(
        grant_id=preauth_grant,
        require_preauth=require_preauth,
        required_capability="auto_rollback" if preauth_grant is not None else None,
        project_id=entry.project_id,
        environment=env,
    )
    project_dir = _resolve_project_path(entry.metadata)
    if grant is not None and project_dir is not None:
        ensure_project_grant_reference(project_dir, grant.grant_id)
    orchestrator = _create_deployment_orchestrator(registry_path)
    result = orchestrator.rollback(
        project_ref=entry.project_id,
        environment=env,
        target=target,
        execute=execute,
    )
    console.print(
        f"Rollback {result.target}/{result.environment}: {'ok' if result.success else 'failed'}"
    )
    console.print(result.message)
    AuditLogger().log(
        project_id=entry.project_id,
        action="rollback",
        result="success" if result.success else "failed",
        grant_id=grant.grant_id if grant is not None else None,
        gates_run=["rollback_marker"],
        commit_ref=None,
        tag_ref=None,
        break_glass_used=grant_break_glass(grant),
        details={"environment": env, "target": target},
    )
    if not result.success:
        raise typer.Exit(code=1)


@app.command("promote")
def promote_project(
    project: Annotated[str, typer.Option(help="Project ID or exact name.")],
    from_env: Annotated[
        str,
        typer.Option("--from", help="Source environment."),
    ] = "staging",
    to_env: Annotated[
        str,
        typer.Option("--to", help="Target environment."),
    ] = "prod",
    target: Annotated[
        str,
        typer.Option(
            "--target",
            help="Deployment target (docker, github_pages, generic_container).",
        ),
    ] = "generic_container",
    execute: Annotated[
        bool,
        typer.Option(
            "--execute/--scaffold-only",
            help="Run promotion commands when possible; default is scaffold-only.",
        ),
    ] = False,
    registry_path: Annotated[
        Path | None,
        typer.Option(help="Optional registry JSONL path override."),
    ] = None,
    require_preauth: Annotated[
        bool,
        typer.Option("--require-preauth", help="Require valid preauthorization grant."),
    ] = False,
    preauth_grant: Annotated[
        str | None,
        typer.Option("--preauth-grant", help="Grant ID used for promotion authorization."),
    ] = None,
) -> None:
    """Promote one project from staging to production-like environment."""
    registry = _create_registry(registry_path)
    entry = registry.get(project)
    if entry is None:
        raise typer.BadParameter(f"Project '{project}' not found.")
    target_env = to_env.strip().lower()
    capability_by_env = {
        "dev": "auto_deploy_dev",
        "staging": "auto_deploy_staging",
        "prod": "auto_deploy_prod",
    }
    required_capability = capability_by_env.get(target_env)
    if required_capability is None:
        raise typer.BadParameter("--to must be one of: dev, staging, prod")
    grant = _resolve_verified_grant(
        grant_id=preauth_grant,
        require_preauth=require_preauth or (target_env == "prod"),
        required_capability=required_capability,
        project_id=entry.project_id,
        environment=target_env,
    )
    project_dir = _resolve_project_path(entry.metadata)
    if grant is not None and project_dir is not None:
        ensure_project_grant_reference(project_dir, grant.grant_id)
    policy = resolve_effective_policy(project_policy=None, grant=grant)
    if project_dir is not None:
        _write_policy_snapshot(project_dir, policy.to_dict())
    decision = evaluate_action(policy=policy, action="deploy", environment=target_env)
    if not decision.allowed:
        raise typer.BadParameter(f"Policy blocked promotion action: {decision.reason}")
    orchestrator = _create_deployment_orchestrator(registry_path)
    result = orchestrator.promote(
        project_ref=entry.project_id,
        source_environment=from_env,
        target_environment=target_env,
        target=target,
        execute=execute,
    )
    console.print(
        f"Promote {from_env}->{target_env} on {target}: {'ok' if result.success else 'failed'}"
    )
    console.print(result.message)
    AuditLogger().log(
        project_id=entry.project_id,
        action="promote",
        result="success" if result.success else "failed",
        grant_id=grant.grant_id if grant is not None else None,
        gates_run=["deployment_policy", "promotion"],
        commit_ref=None,
        tag_ref=None,
        break_glass_used=grant_break_glass(grant),
        details={"from": from_env, "to": target_env, "target": target},
    )
    if not result.success:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
