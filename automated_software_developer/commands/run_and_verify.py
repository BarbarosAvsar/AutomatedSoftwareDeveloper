"""CLI command registrations."""

from __future__ import annotations

import os

# mypy: ignore-errors
# ruff: noqa: B008,F403,F405,I001
from automated_software_developer.commands.common import *


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show AutoSD version and exit.",
            is_eager=True,
            callback=_version_callback,
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose debug logging."),
    ] = False,
    log_file: Annotated[
        Path,
        typer.Option("--log-file", help="Write logs to autosd.log (default: ./autosd.log)."),
    ] = Path("autosd.log"),
) -> None:
    """Autonomous software-development agent CLI with policy-gated operations."""
    configure_logging(log_file=log_file, verbose=verbose)


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
        typer.Option(help="Model provider to use: openai, resilient, or mock."),
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
    parallel_prompt_workers: Annotated[
        int,
        typer.Option(help="Parallel worker count for prompt prefetching."),
    ] = 1,
    allow_stale_parallel_prompts: Annotated[
        bool,
        typer.Option(
            "--allow-stale-parallel-prompts/--disallow-stale-parallel-prompts",
            help="Allow parallel prompt prefetch responses even if workspace changed.",
        ),
    ] = False,
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
    strict_readiness: Annotated[
        bool,
        typer.Option(
            "--strict-readiness/--allow-readiness-gaps",
            help=(
                "Fail fast when required quality/security/provider dependencies are missing "
                "instead of skipping checks."
            ),
        ),
    ] = False,
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
    conformance_seed: Annotated[
        int | None,
        typer.Option(
            "--conformance-seed",
            help="Optional seed override for reproducible runs and conformance checks.",
        ),
    ] = None,
    sbom_mode: Annotated[
        str,
        typer.Option(help="SBOM behavior: off, if-available, required."),
    ] = "if-available",
    execution_mode: Annotated[
        str,
        typer.Option(
            help="Execution mode: direct, planning, auto (auto resolves to planning-first).",
        ),
    ] = "direct",
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
    """Run the full autonomous refine -> implement -> verify workflow.

    Examples:
        autosd run --requirements-file requirements.md --output-dir output/project
        autosd run --requirements-text "Build a CLI" --provider mock \\
          --mock-responses-file mocks.json
    """
    requirements = _load_requirements(requirements_file, requirements_text)
    resolved_provider = _create_provider(provider, model, mock_responses_file)
    max_task_attempts = _ensure_positive(max_task_attempts, "max-task-attempts")
    timeout_seconds = _ensure_positive(timeout_seconds, "timeout-seconds")
    max_stories_per_sprint = _ensure_positive(max_stories_per_sprint, "max-stories-per-sprint")
    parallel_prompt_workers = _ensure_positive(
        parallel_prompt_workers,
        "parallel-prompt-workers",
    )
    security_scan_mode = _validate_security_scan_mode(security_scan_mode)
    sbom_mode = _validate_sbom_mode(sbom_mode)
    execution_mode = _validate_execution_mode(execution_mode)
    if strict_readiness:
        _enforce_strict_readiness(
            provider=provider,
            quality_gates=quality_gates,
            enable_security_scan=security_scan,
            security_scan_mode=security_scan_mode,
        )
    if conformance_seed is not None:
        conformance_seed = _ensure_positive(conformance_seed, "conformance-seed")
    config = AgentConfig(
        max_task_attempts=max_task_attempts,
        command_timeout_seconds=timeout_seconds,
        max_stories_per_sprint=max_stories_per_sprint,
        enforce_quality_gates=quality_gates,
        strict_readiness=strict_readiness,
        enforce_docstrings=enforce_docstrings,
        enable_security_scan=security_scan,
        security_scan_mode=security_scan_mode,
        enable_learning=enable_learning,
        update_templates=update_templates,
        preferred_platform=preferred_platform,
        execute_packaging=execute_packaging,
        reproducible=reproducible,
        sbom_mode=sbom_mode,
        prompt_seed_base=conformance_seed
        if conformance_seed is not None
        else AgentConfig().prompt_seed_base,
        parallel_prompt_workers=parallel_prompt_workers,
        allow_stale_parallel_prompts=allow_stale_parallel_prompts,
        execution_mode=execution_mode,
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
    table.add_row("Readiness Level", summary.readiness_level)
    if summary.blocking_reasons:
        table.add_row("Blocking Reasons", "; ".join(summary.blocking_reasons))
    table.add_row("Validation Provider", summary.validation_provider)
    if summary.validation_scope:
        table.add_row("Validation Scope", ", ".join(summary.validation_scope))
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
    if summary.architecture_doc_path is not None:
        table.add_row("Architecture Doc", str(summary.architecture_doc_path))
    if summary.architecture_components_path is not None:
        table.add_row("Architecture Components", str(summary.architecture_components_path))
    if summary.architecture_adrs_path is not None:
        table.add_row("Architecture ADRs", str(summary.architecture_adrs_path))
    if summary.build_hash_path is not None:
        table.add_row("Build Hash", str(summary.build_hash_path))
    if summary.requested_execution_mode is not None:
        table.add_row("Execution Mode (Requested)", summary.requested_execution_mode)
    if summary.selected_execution_mode is not None:
        table.add_row("Execution Mode (Selected)", summary.selected_execution_mode)
    if summary.execution_mode_reason is not None:
        table.add_row("Execution Mode Rationale", summary.execution_mode_reason)
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


@app.command("verify-factory")
def verify_factory(
    conformance_seed: Annotated[
        int,
        typer.Option(
            "--conformance-seed",
            help="Seed for reproducible conformance generation runs.",
        ),
    ] = 4242,
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            help="Directory to write generated conformance projects.",
        ),
    ] = Path("conformance/output"),
    report_path: Annotated[
        Path,
        typer.Option(
            "--report-path",
            help="Path to write the conformance report JSON.",
        ),
    ] = Path("conformance/report.json"),
    diff_check: Annotated[
        bool,
        typer.Option(
            "--diff-check/--no-diff-check",
            help="Generate fixtures twice and compare outputs for determinism.",
        ),
    ] = True,
    skip_generator_gates: Annotated[
        bool,
        typer.Option(
            "--skip-generator-gates/--run-generator-gates",
            help="Skip repo-level ruff/mypy/pytest gates before conformance.",
        ),
    ] = False,
    max_workers: Annotated[
        int,
        typer.Option(help="Parallel worker count for conformance fixtures."),
    ] = 3,
    verify_report_path: Annotated[
        Path,
        typer.Option(
            "--verify-report-path",
            help="Path to write the verify-factory report JSON.",
        ),
    ] = Path("verify_factory_report.json"),
    strict_readiness: Annotated[
        bool,
        typer.Option(
            "--strict-readiness/--allow-readiness-gaps",
            help=(
                "Fail fast when required quality/security dependencies are missing "
                "instead of skipping checks."
            ),
        ),
    ] = False,
    conformance_provider: Annotated[
        str,
        typer.Option(
            "--conformance-provider",
            help="Conformance provider: mock or openai.",
        ),
    ] = "mock",
    real_provider_required: Annotated[
        bool,
        typer.Option(
            "--real-provider-required/--real-provider-advisory",
            help=(
                "When using --conformance-provider openai, treat failures as blocking "
                "(required) or non-blocking (advisory)."
            ),
        ),
    ] = False,
    real_provider_model: Annotated[
        str,
        typer.Option(
            "--real-provider-model",
            help="OpenAI model used when --conformance-provider openai.",
        ),
    ] = "gpt-5.3-codex",
    smoke_fixtures: Annotated[
        str | None,
        typer.Option(
            "--smoke-fixtures",
            help=(
                "Optional comma-separated fixture IDs. "
                "Defaults to cli_tool,api_service,web_app when provider=openai."
            ),
        ),
    ] = None,
) -> None:
    """Run generator and generated-project quality gates for release readiness."""
    provider_mode = conformance_provider.strip().lower()
    if provider_mode not in {"mock", "openai"}:
        raise typer.BadParameter("--conformance-provider must be one of: mock, openai")
    conformance_seed = _ensure_positive(conformance_seed, "conformance-seed")
    max_workers = _ensure_positive(max_workers, "max-workers")
    if strict_readiness:
        _enforce_strict_readiness(
            provider=provider_mode,
            quality_gates=True,
            enable_security_scan=True,
            security_scan_mode="required",
        )
    default_smoke_fixture_ids = ("cli_tool", "api_service", "web_app")
    fixture_filter_raw = smoke_fixtures
    if fixture_filter_raw is None and provider_mode == "openai":
        fixture_filter_raw = ",".join(default_smoke_fixture_ids)
    selected_fixture_ids = _parse_fixture_ids_csv(fixture_filter_raw)

    verify_report: dict[str, Any] = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "generator_gates": [],
        "workflow_lint": {},
        "ci_mirror": {},
        "conformance": {},
        "real_provider": {
            "enabled": provider_mode == "openai",
            "required": provider_mode == "openai" and real_provider_required,
            "provider": provider_mode if provider_mode == "openai" else None,
            "model": real_provider_model if provider_mode == "openai" else None,
            "fixtures_run": [],
            "pass_rate": 0.0,
            "blocking_failures": [],
        },
    }
    if not skip_generator_gates:
        gates = generator_gate_commands()
        for args in gates:
            command = " ".join(args)
            passed, duration = _run_gate_command(args)
            status = "PASS" if passed else "FAIL"
            console.print(f"[{status}] {command} ({duration:.2f}s)")
            verify_report["generator_gates"].append(
                {"command": command, "passed": passed, "duration_seconds": duration}
            )
            if not passed:
                _write_verify_report(verify_report_path, verify_report)
                raise typer.Exit(code=1)

    workflow_results = lint_workflows(Path("."))
    workflow_errors = [
        {"path": str(result.path), "errors": list(result.errors)}
        for result in workflow_results
        if not result.passed
    ]
    verify_report["workflow_lint"] = {
        "passed": not workflow_errors,
        "errors": workflow_errors,
    }
    if workflow_errors:
        console.print("[FAIL] Workflow lint failed.")
        _write_verify_report(verify_report_path, verify_report)
        raise typer.Exit(code=1)
    console.print("[PASS] Workflow lint passed.")

    mirror_result = run_ci_mirror(Path("."))
    verify_report["ci_mirror"] = {
        "passed": mirror_result.passed,
        "exit_code": mirror_result.exit_code,
        "duration_seconds": mirror_result.duration_seconds,
    }
    if not mirror_result.passed:
        console.print("[FAIL] CI mirror failed.")
        _write_verify_report(verify_report_path, verify_report)
        raise typer.Exit(code=1)
    console.print("[PASS] CI mirror passed.")

    fixtures = _resolve_conformance_fixtures(selected_fixture_ids)
    if provider_mode == "openai" and not os.environ.get("OPENAI_API_KEY"):
        key_message = (
            "OPENAI_API_KEY is missing; real-provider conformance cannot run."
        )
        verify_report["real_provider"]["blocking_failures"] = [key_message]
        verify_report["conformance"] = {
            "passed": False,
            "skipped": True,
            "report_path": str(report_path),
            "output_dir": str(output_dir),
            "provider": provider_mode,
            "model": real_provider_model,
            "fixtures_run": [fixture.fixture_id for fixture in fixtures],
            "pass_rate": 0.0,
            "blocking_failures": [key_message],
        }
        if real_provider_required:
            console.print(f"[FAIL] {key_message}")
            _write_verify_report(verify_report_path, verify_report)
            raise typer.Exit(code=1)
        console.print(f"[WARN] {key_message} Advisory mode allows continuation.")
        _write_verify_report(verify_report_path, verify_report)
        return

    report = run_conformance_suite(
        fixtures=fixtures,
        config=ConformanceConfig(
            output_dir=output_dir,
            report_path=report_path,
            provider=provider_mode,
            model=real_provider_model,
            conformance_seed=conformance_seed,
            diff_check=diff_check,
            max_workers=max_workers,
            strict_readiness=strict_readiness,
        )
    )
    fixture_ids_run = [item.fixture_id for item in report.fixtures]
    blocking_failures = _conformance_blocking_failures(report)
    status = "PASS" if report.passed else "FAIL"
    console.print(f"[{status}] Conformance suite complete. Report: {report_path}")
    verify_report["conformance"] = {
        "passed": report.passed,
        "report_path": str(report_path),
        "output_dir": str(output_dir),
        "provider": provider_mode,
        "model": real_provider_model if provider_mode == "openai" else None,
        "fixtures_run": fixture_ids_run,
        "pass_rate": round(report.pass_rate, 4),
        "blocking_failures": blocking_failures,
    }
    if provider_mode == "openai":
        verify_report["real_provider"] = {
            "enabled": True,
            "required": real_provider_required,
            "provider": provider_mode,
            "model": real_provider_model,
            "fixtures_run": fixture_ids_run,
            "pass_rate": round(report.pass_rate, 4),
            "blocking_failures": blocking_failures,
        }
    _write_verify_report(verify_report_path, verify_report)
    if not report.passed and (provider_mode != "openai" or real_provider_required):
        raise typer.Exit(code=1)
    if not report.passed and provider_mode == "openai":
        console.print("[WARN] Real-provider conformance failed in advisory mode.")


def _parse_fixture_ids_csv(raw_value: str | None) -> list[str]:
    """Parse optional comma-separated fixture ids into normalized list."""
    if raw_value is None:
        return []
    items = [item.strip() for item in raw_value.split(",")]
    return [item for item in items if item]


def _resolve_conformance_fixtures(fixture_ids: list[str]) -> list[Any]:
    """Load fixtures and optionally filter by fixture id."""
    from automated_software_developer.agent.conformance.fixtures import load_fixtures

    fixtures = load_fixtures()
    if not fixture_ids:
        return fixtures
    fixture_index = {item.fixture_id: item for item in fixtures}
    unknown = [item for item in fixture_ids if item not in fixture_index]
    if unknown:
        allowed = ", ".join(sorted(fixture_index))
        raise typer.BadParameter(
            f"Unknown smoke fixture(s): {', '.join(sorted(set(unknown)))}. Allowed: {allowed}"
        )
    return [fixture_index[item] for item in fixture_ids]


def _conformance_blocking_failures(report: Any) -> list[str]:
    """Build deterministic fixture/gate failure summaries."""
    failures: list[str] = []
    for fixture in report.fixtures:
        if fixture.passed:
            continue
        failing_gates = [gate.name for gate in fixture.gates if not gate.passed]
        if fixture.diff is not None and not fixture.diff.matched:
            failing_gates.append("diff_check")
        if failing_gates:
            failures.append(f"{fixture.fixture_id}: {', '.join(sorted(set(failing_gates)))}")
        else:
            failures.append(f"{fixture.fixture_id}: unknown_failure")
    return failures


@app.command("doctor")
def doctor(
    include_security: Annotated[
        bool,
        typer.Option(
            "--include-security/--skip-security",
            help="Include security dependency checks (bandit/pip-audit).",
        ),
    ] = True,
    require_openai_key: Annotated[
        bool,
        typer.Option(
            "--require-openai-key/--allow-missing-openai-key",
            help="Treat missing OPENAI_API_KEY as a blocking failure.",
        ),
    ] = False,
) -> None:
    """Run local environment readiness checks with actionable remediation."""
    report = build_doctor_report(
        include_security=include_security,
        require_openai_key=require_openai_key,
    )
    table = Table(title="AutoSD Doctor")
    table.add_column("Category")
    table.add_column("Check")
    table.add_column("Required")
    table.add_column("Status")
    table.add_column("Detail")
    for item in report.checks:
        status = "[green]PASS[/green]" if item.passed else "[red]FAIL[/red]"
        table.add_row(
            item.category,
            item.name,
            "yes" if item.required else "no",
            status,
            item.detail,
        )
    console.print(table)
    if report.passed:
        console.print("\nDoctor status: PASS")
        return

    console.print("\nDoctor status: FAIL")
    for reason in report.blocking_reasons():
        console.print(f"- {reason}")
    raise typer.Exit(code=1)


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
        typer.Option(help="Model provider to use: openai, resilient, or mock."),
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
    """Run only autonomous requirements refinement.

    Examples:
        autosd refine --requirements-file requirements.md --output-dir output/refined
        autosd refine --requirements-text "API for inventory tracking"
    """
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
    """Summarize journal history and optionally update versioned prompt templates.

    Examples:
        autosd learn --journals output/.autosd/prompt_journal.jsonl
        autosd learn --journals output/.autosd/prompt_journal.jsonl --update-templates
    """
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


@app.command("daemon")
def daemon(
    requirements_dir: Annotated[
        Path,
        typer.Option(help="Directory to watch for new requirements files."),
    ] = Path("requirements"),
    projects_dir: Annotated[
        Path,
        typer.Option(help="Directory to write generated projects."),
    ] = Path("projects"),
    registry_path: Annotated[
        Path,
        typer.Option(help="Registry JSONL path for portfolio updates."),
    ] = Path(".autosd_portfolio/registry.jsonl"),
    incidents_path: Annotated[
        Path,
        typer.Option(help="Incident log JSONL path."),
    ] = Path(".autosd/incidents.jsonl"),
    incident_signals_path: Annotated[
        Path | None,
        typer.Option(help="Optional JSON list of incident signals to process."),
    ] = None,
    provider: Annotated[
        str,
        typer.Option(help="Model provider to use: openai, resilient, or mock."),
    ] = "openai",
    model: Annotated[
        str,
        typer.Option(help="Model name when using OpenAI provider."),
    ] = "gpt-5.3-codex",
    mock_responses_file: Annotated[
        Path | None,
        typer.Option(help="JSON file of queued responses when provider=mock."),
    ] = None,
    environment: Annotated[
        str,
        typer.Option(help="Deployment environment to target."),
    ] = "staging",
    deploy_target: Annotated[
        str,
        typer.Option(help="Deployment target ID."),
    ] = "generic_container",
    execute_deploy: Annotated[
        bool,
        typer.Option(
            "--execute-deploy/--scaffold-deploy",
            help="Execute deploy steps when possible.",
        ),
    ] = False,
    execution_mode: Annotated[
        str,
        typer.Option(
            help="Execution mode: direct, planning, auto (auto resolves to planning-first).",
        ),
    ] = "direct",
    max_cycles: Annotated[
        int,
        typer.Option(help="Maximum daemon cycles (0 for infinite)."),
    ] = 1,
    interval_seconds: Annotated[
        int,
        typer.Option(help="Sleep interval between cycles."),
    ] = 5,
) -> None:
    """Run the non-interactive autonomous company workflow daemon."""
    resolved_provider = _create_provider(provider, model, mock_responses_file)
    execution_mode = _validate_execution_mode(execution_mode)
    config = DaemonConfig(
        requirements_dir=requirements_dir,
        projects_dir=projects_dir,
        registry_path=registry_path,
        incidents_path=incidents_path,
        incident_signals_path=incident_signals_path,
        environment=environment,
        deploy_target=deploy_target,
        execute_deploy=execute_deploy,
        execution_mode=execution_mode,
    )
    daemon_runner = CompanyDaemon(provider=resolved_provider, config=config)
    cycles_run = 0
    while True:
        processed = daemon_runner.run_once()
        console.print(f"Daemon cycle complete. Projects processed: {len(processed)}")
        cycles_run += 1
        if max_cycles and cycles_run >= max_cycles:
            break
        if interval_seconds > 0:
            import time

            time.sleep(interval_seconds)
