"""Autonomous refinement, backlog sprinting, and verification orchestration."""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from automated_software_developer.agent.agile.backlog import build_backlog
from automated_software_developer.agent.agile.ceremonies import (
    run_retrospective,
    run_sprint_planning,
    write_retrospective,
)
from automated_software_developer.agent.agile.metrics import MetricsStore
from automated_software_developer.agent.agile.sprint_engine import SprintConfig
from automated_software_developer.agent.architecture import (
    ArchitectureArtifacts,
    ArchitecturePlanner,
)
from automated_software_developer.agent.backlog import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_IN_PROGRESS,
    StoryBacklog,
    parse_acceptance_criteria_assertions,
    resolve_story_commands,
)
from automated_software_developer.agent.config_validation import (
    require_positive_int,
    validate_sbom_mode,
    validate_security_scan_mode,
)
from automated_software_developer.agent.design_doc import build_design_doc_markdown
from automated_software_developer.agent.executor import CommandExecutor
from automated_software_developer.agent.filesystem import FileWorkspace
from automated_software_developer.agent.github import ensure_repository_scaffold
from automated_software_developer.agent.journal import PromptJournal, hash_text
from automated_software_developer.agent.learning import PromptPatternStore, learn_from_journals
from automated_software_developer.agent.models import (
    BacklogStory,
    CommandResult,
    ExecutionBundle,
    PromptTemplate,
    RefinedRequirements,
    RunSummary,
    StoryExecutionState,
)
from automated_software_developer.agent.packaging import PackagingOrchestrator
from automated_software_developer.agent.planning import Planner
from automated_software_developer.agent.platforms.catalog import (
    build_capability_graph,
    select_platform_adapter,
)
from automated_software_developer.agent.prompts import (
    REFINEMENT_TEMPLATE_ID,
    STORY_IMPLEMENTATION_TEMPLATE_ID,
    build_story_implementation_system_prompt,
    build_story_implementation_user_prompt,
)
from automated_software_developer.agent.provenance import (
    BuildManifest,
    gather_tool_versions,
    maybe_write_sbom,
    write_build_manifest,
)
from automated_software_developer.agent.providers.base import LLMProvider
from automated_software_developer.agent.quality import (
    QualityGateCacheEntry,
    QualityGateResult,
    build_quality_gate_plan,
    compute_quality_gate_fingerprint,
    evaluate_python_quality,
    load_quality_gate_cache,
    save_quality_gate_cache,
)
from automated_software_developer.agent.reproducibility import (
    build_artifact_checksums,
    enforce_lockfiles,
    write_build_hash,
)
from automated_software_developer.agent.requirements_refiner import RequirementsRefiner
from automated_software_developer.agent.schemas import (
    validate_backlog_payload,
    validate_sprint_log_event,
)
from automated_software_developer.agent.security import (
    ensure_safe_relative_path,
    scan_workspace_for_secrets,
)

DEFAULT_AGENTS_MD = (
    """
# AGENTS.md

## Project Rules
- Never commit credentials, access tokens, or private keys.
- Run lint and tests before proposing completion.
- Keep code modular, typed/documented, and security-focused.
- Update README when functionality changes.
- Never store secrets in `.autosd` artifacts (progress, backlog, sprint log, journals).
""".strip()
    + "\n"
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentConfig:
    """Runtime configuration for autonomous backlog execution."""

    max_task_attempts: int = 4
    command_timeout_seconds: int = 240
    snapshot_max_files: int = 60
    snapshot_max_chars_per_file: int = 3_500
    max_stories_per_sprint: int = 2
    progress_file: str = ".autosd/progress.json"
    refined_spec_file: str = ".autosd/refined_requirements.md"
    backlog_file: str = ".autosd/backlog.json"
    sprint_log_file: str = ".autosd/sprint_log.jsonl"
    journal_file: str = ".autosd/prompt_journal.jsonl"
    design_doc_file: str = ".autosd/design_doc.md"
    platform_plan_file: str = ".autosd/platform_plan.json"
    capability_graph_file: str = ".autosd/capability_graph.json"
    architecture_doc_file: str = ".autosd/architecture/architecture.md"
    architecture_components_file: str = ".autosd/architecture/components.json"
    architecture_adrs_dir: str = ".autosd/architecture/adrs"
    enforce_quality_gates: bool = True
    enforce_docstrings: bool = True
    enable_security_scan: bool = False
    security_scan_mode: str = "if-available"
    enable_learning: bool = False
    update_templates: bool = False
    preferred_platform: str | None = None
    execute_packaging: bool = False
    reproducible: bool = False
    sbom_mode: str = "if-available"
    prompt_playbook_path: str = "PROMPT_PLAYBOOK.md"
    prompt_changelog_path: str = "PROMPT_TEMPLATE_CHANGES.md"
    prompt_seed_base: int = 4242
    build_hash_file: str = ".autosd/provenance/build_hash.json"
    parallel_prompt_workers: int = 1
    allow_stale_parallel_prompts: bool = False

    def __post_init__(self) -> None:
        """Validate configuration values eagerly."""
        require_positive_int(self.max_task_attempts, "max_task_attempts")
        require_positive_int(self.command_timeout_seconds, "command_timeout_seconds")
        require_positive_int(self.max_stories_per_sprint, "max_stories_per_sprint")
        validate_security_scan_mode(self.security_scan_mode)
        validate_sbom_mode(self.sbom_mode)
        require_positive_int(self.prompt_seed_base, "prompt_seed_base")
        if self.preferred_platform is not None and not self.preferred_platform.strip():
            raise ValueError("preferred_platform cannot be blank when provided.")
        require_positive_int(self.parallel_prompt_workers, "parallel_prompt_workers")


@dataclass(frozen=True)
class StoryPromptPrefetch:
    """Prefetched story prompt and response for parallel execution."""

    story_id: str
    system_prompt: str
    user_prompt: str
    prompt_fingerprint: str
    response: dict[str, Any]
    snapshot_hash: str


class SoftwareDevelopmentAgent:
    """Coordinates refinement, story-by-story implementation, and verification."""

    def __init__(
        self,
        provider: LLMProvider,
        config: AgentConfig | None = None,
        pattern_store: PromptPatternStore | None = None,
    ) -> None:
        """Create a software development agent with provider and runtime config."""
        self.provider = provider
        self.config = config or AgentConfig()
        self.planner = Planner(provider)
        self.refiner = RequirementsRefiner(provider)
        self.architecture_planner = ArchitecturePlanner(provider)
        self.executor = CommandExecutor(timeout_seconds=self.config.command_timeout_seconds)
        self.packaging = PackagingOrchestrator(self.executor)
        self.pattern_store = pattern_store or PromptPatternStore()
        self.pattern_store.ensure_defaults()

    def refine_requirements(self, requirements: str, output_dir: Path) -> RefinedRequirements:
        """Run only the requirements refinement stage and persist canonical artifact."""
        if not requirements.strip():
            raise ValueError("requirements must be non-empty.")
        prompt_seed = self.config.prompt_seed_base if self.config.reproducible else None
        workspace = FileWorkspace(output_dir)
        workspace.ensure_exists()
        self._ensure_agents_md(workspace)
        ensure_repository_scaffold(workspace)
        repo_guidelines = workspace.read_optional("AGENTS.md")
        refinement_template = self.pattern_store.load_latest(REFINEMENT_TEMPLATE_ID)
        refined = self.refiner.refine(
            requirements=requirements,
            repo_guidelines=repo_guidelines,
            template=refinement_template,
            seed=prompt_seed,
        )
        workspace.write_file(self.config.refined_spec_file, refined.to_markdown())
        return refined

    def run_scrum_cycle(self, requirements: str, output_dir: Path) -> dict[str, Path]:
        """Run requirements refinement, backlog generation, and sprint planning."""
        if not requirements.strip():
            raise ValueError("requirements must be non-empty.")
        prompt_seed = self.config.prompt_seed_base if self.config.reproducible else None
        workspace = FileWorkspace(output_dir)
        workspace.ensure_exists()
        self._ensure_agents_md(workspace)
        ensure_repository_scaffold(workspace)
        repo_guidelines = workspace.read_optional("AGENTS.md")

        refinement_template = self.pattern_store.load_latest(REFINEMENT_TEMPLATE_ID)
        refined = self.refiner.refine(
            requirements=requirements,
            repo_guidelines=repo_guidelines,
            template=refinement_template,
            seed=prompt_seed,
        )
        workspace.write_file(self.config.refined_spec_file, refined.to_markdown())

        backlog = build_backlog(refined)
        backlog_path = output_dir / self.config.backlog_file
        backlog_path.parent.mkdir(parents=True, exist_ok=True)
        backlog_path.write_text(json.dumps(backlog.to_dict(), indent=2), encoding="utf-8")

        metrics_store = MetricsStore(path=output_dir / ".autosd" / "metrics.json")
        sprint_plan = run_sprint_planning(backlog, metrics_store, config=SprintConfig())
        sprint_dir = output_dir / ".autosd" / "sprints" / sprint_plan.sprint_id
        sprint_dir.mkdir(parents=True, exist_ok=True)
        sprint_plan_path = sprint_dir / "sprint_plan.json"
        sprint_plan_path.write_text(json.dumps(sprint_plan.to_dict(), indent=2), encoding="utf-8")

        retrospective_md = run_retrospective(sprint_plan, metrics_store)
        retrospective_path = write_retrospective(
            retrospective_md,
            output_dir=output_dir / ".autosd" / "retrospectives",
            sprint_id=sprint_plan.sprint_id,
        )
        metrics_store.save()
        return {
            "refined_requirements": output_dir / self.config.refined_spec_file,
            "backlog": backlog_path,
            "sprint_plan": sprint_plan_path,
            "retrospective": retrospective_path,
            "metrics": metrics_store.path,
        }

    def run(self, requirements: str, output_dir: Path) -> RunSummary:
        """Execute the full refine -> backlog sprint -> verify workflow."""
        if not requirements.strip():
            raise ValueError("requirements must be non-empty.")

        prompt_seed = self.config.prompt_seed_base if self.config.reproducible else None
        workspace = FileWorkspace(output_dir)
        workspace.ensure_exists()
        self._ensure_agents_md(workspace)
        ensure_repository_scaffold(workspace)
        repo_guidelines = workspace.read_optional("AGENTS.md")

        refinement_template = self.pattern_store.load_latest(REFINEMENT_TEMPLATE_ID)
        story_template = self.pattern_store.load_latest(STORY_IMPLEMENTATION_TEMPLATE_ID)
        refined = self.refiner.refine(
            requirements=requirements,
            repo_guidelines=repo_guidelines,
            template=refinement_template,
            seed=prompt_seed,
        )
        refined_markdown = refined.to_markdown()
        workspace.write_file(self.config.refined_spec_file, refined_markdown)

        architecture_plan = self.architecture_planner.create_plan(
            refined=refined,
            repo_guidelines=repo_guidelines,
            seed=prompt_seed,
        )
        architecture_artifacts = self.architecture_planner.write_artifacts(
            architecture_plan,
            workspace.base_dir,
        )
        self._track_architecture_artifacts(workspace, architecture_artifacts)

        capability_graph = build_capability_graph()
        workspace.write_file(
            self.config.capability_graph_file,
            json.dumps(capability_graph.to_dict(), indent=2),
        )
        platform_plan = select_platform_adapter(
            refined,
            project_dir=workspace.base_dir,
            preferred_adapter=self.config.preferred_platform,
        )
        workspace.write_file(
            self.config.platform_plan_file,
            json.dumps(platform_plan.to_dict(), indent=2),
        )
        for relative_path, content in platform_plan.scaffold_files.items():
            if workspace.read_optional(relative_path) is None:
                workspace.write_file(relative_path, content)

        backlog = self.planner.create_backlog(refined)
        self._persist_backlog(workspace, backlog)
        self._persist_design_doc(workspace, refined, backlog, phase="refinement-complete")

        journal_path = ensure_safe_relative_path(workspace.base_dir, self.config.journal_file)
        journal = PromptJournal(journal_path)
        self._append_journal_refinement_event(
            journal=journal,
            template=refinement_template,
            refined=refined,
        )
        self._persist_progress(
            workspace,
            backlog,
            refined,
            platform_adapter_id=platform_plan.adapter_id,
        )

        sprint_index = 0
        while backlog.has_active_work():
            sprint = backlog.select_sprint(max_stories=self.config.max_stories_per_sprint)
            if not sprint:
                blocked = backlog.unresolved_dependencies()
                raise RuntimeError(
                    "No dependency-satisfied stories available in backlog.\n"
                    f"Blocked stories: {json.dumps(blocked, indent=2)}"
                )
            sprint_index += 1
            prefetched_prompts = self._prefetch_story_prompts(
                workspace=workspace,
                stories=[backlog.story_by_id(item.story_id) for item in sprint],
                backlog=backlog,
                refined_markdown=refined_markdown,
                repo_guidelines=repo_guidelines,
                template=story_template,
                prompt_seed=prompt_seed,
            )
            for story in sprint:
                backlog.update_story(
                    story.story_id,
                    status=STATUS_IN_PROGRESS,
                    attempts=story.attempts,
                    last_error=story.last_error,
                )
                self._append_sprint_log(
                    workspace=workspace,
                    payload={
                        "timestamp": self._now(),
                        "sprint_index": sprint_index,
                        "story_id": story.story_id,
                        "event": "story_started",
                    },
                )
                self._persist_backlog(workspace, backlog)
                self._persist_progress(
                    workspace,
                    backlog,
                    refined,
                    platform_adapter_id=platform_plan.adapter_id,
                )
                self._persist_design_doc(
                    workspace,
                    refined,
                    backlog,
                    phase=f"sprint-{sprint_index}-story-{story.story_id}-started",
                )

                state = self._execute_story(
                    workspace=workspace,
                    story=backlog.story_by_id(story.story_id),
                    backlog=backlog,
                    refined_markdown=refined_markdown,
                    repo_guidelines=repo_guidelines,
                    template=story_template,
                    journal=journal,
                    prompt_seed=prompt_seed,
                    prefetched=prefetched_prompts.get(story.story_id),
                )
                backlog.update_story(
                    story.story_id,
                    status=state.status,
                    attempts=state.attempt,
                    last_error=state.error,
                )
                self._append_sprint_log(
                    workspace=workspace,
                    payload={
                        "timestamp": self._now(),
                        "sprint_index": sprint_index,
                        "story_id": story.story_id,
                        "event": (
                            "story_completed"
                            if state.status == STATUS_COMPLETED
                            else "story_failed"
                        ),
                        "attempt": state.attempt,
                        "error": state.error,
                    },
                )
                self._persist_backlog(workspace, backlog)
                self._persist_progress(
                    workspace,
                    backlog,
                    refined,
                    platform_adapter_id=platform_plan.adapter_id,
                )
                self._persist_design_doc(
                    workspace,
                    refined,
                    backlog,
                    phase=f"sprint-{sprint_index}-story-{story.story_id}-{state.status}",
                )
                if state.status != STATUS_COMPLETED:
                    raise RuntimeError(
                        f"Story '{story.story_id}' failed after {state.attempt} attempts.\n"
                        f"{state.error or 'No error details available.'}"
                    )

        final_quality_plan = build_quality_gate_plan(
            workspace.base_dir,
            enforce_quality_gates=self.config.enforce_quality_gates,
            enable_security_scan=self.config.enable_security_scan,
            security_scan_mode=self.config.security_scan_mode,
        )
        quality_commands = _dedupe_commands(
            [*final_quality_plan.format_commands, *final_quality_plan.verification_commands]
        )
        quality_results, _ = self._run_quality_gate_commands(workspace, quality_commands)
        remaining_commands = _dedupe_commands(list(backlog.global_verification_commands))
        final_commands = [*quality_commands, *remaining_commands]
        if quality_results and not all(result.passed for result in quality_results):
            final_results = quality_results
        else:
            remaining_results = self.executor.run_many(remaining_commands, cwd=workspace.base_dir)
            final_results = [*quality_results, *remaining_results]
        if not final_results or final_results[-1].exit_code != 0:
            raise RuntimeError(
                "Final verification failed.\n" + self._format_command_results(final_results)
            )
        packaging_result = self.packaging.execute(
            plan=platform_plan,
            project_dir=workspace.base_dir,
            enabled=self.config.execute_packaging,
        )
        if packaging_result.results:
            final_results = [*final_results, *packaging_result.results]

        static_quality = evaluate_python_quality(
            workspace.base_dir,
            enforce_docstrings=self.config.enforce_docstrings,
        )
        if not static_quality.passed:
            raise RuntimeError(self._format_quality_findings(static_quality))

        secret_findings = scan_workspace_for_secrets(workspace.base_dir)
        if secret_findings:
            findings = "\n".join(f"- {item}" for item in secret_findings)
            raise RuntimeError(f"Potential secrets detected in output project:\n{findings}")

        manifest = BuildManifest(
            project_id=refined.project_name,
            version="0.1.0",
            commit_sha=None,
            tag=None,
            gates_run=[*final_commands, *packaging_result.commands],
            gate_results=self._serialize_gate_results(final_results),
            reproducible=self.config.reproducible,
            tool_versions=gather_tool_versions(),
        )
        write_build_manifest(workspace.base_dir, manifest)
        maybe_write_sbom(workspace.base_dir, mode=self.config.sbom_mode)
        lockfiles = enforce_lockfiles(
            workspace.base_dir,
            reproducible=self.config.reproducible,
        )
        checksums = build_artifact_checksums(workspace.base_dir)
        build_hash_path = write_build_hash(
            workspace.base_dir,
            checksums=checksums,
            seed=prompt_seed,
            lockfiles=lockfiles,
        )
        workspace.changed_files.add(
            str(build_hash_path.relative_to(workspace.base_dir)).replace("\\", "/")
        )

        if self.config.enable_learning:
            learn_from_journals(
                journal_paths=[journal_path],
                pattern_store=self.pattern_store,
                update_templates=self.config.update_templates,
                playbook_path=Path(self.config.prompt_playbook_path),
                changelog_path=Path(self.config.prompt_changelog_path),
            )

        return RunSummary(
            output_dir=workspace.base_dir,
            project_name=refined.project_name,
            stack_rationale=refined.stack_rationale,
            tasks_total=len(backlog.stories),
            tasks_completed=backlog.completed_count(),
            changed_files=sorted(workspace.changed_files),
            verification_results=final_results,
            refined_spec_path=ensure_safe_relative_path(
                workspace.base_dir,
                self.config.refined_spec_file,
            ),
            backlog_path=ensure_safe_relative_path(
                workspace.base_dir,
                self.config.backlog_file,
            ),
            design_doc_path=ensure_safe_relative_path(
                workspace.base_dir,
                self.config.design_doc_file,
            ),
            sprint_log_path=ensure_safe_relative_path(
                workspace.base_dir,
                self.config.sprint_log_file,
            ),
            journal_path=journal_path,
            platform_plan_path=ensure_safe_relative_path(
                workspace.base_dir,
                self.config.platform_plan_file,
            ),
            capability_graph_path=ensure_safe_relative_path(
                workspace.base_dir,
                self.config.capability_graph_file,
            ),
            architecture_doc_path=ensure_safe_relative_path(
                workspace.base_dir,
                self.config.architecture_doc_file,
            ),
            architecture_components_path=ensure_safe_relative_path(
                workspace.base_dir,
                self.config.architecture_components_file,
            ),
            architecture_adrs_path=ensure_safe_relative_path(
                workspace.base_dir,
                self.config.architecture_adrs_dir,
            ),
            build_hash_path=build_hash_path,
        )

    def _prefetch_story_prompts(
        self,
        workspace: FileWorkspace,
        stories: list[BacklogStory],
        backlog: StoryBacklog,
        refined_markdown: str,
        repo_guidelines: str | None,
        template: PromptTemplate,
        prompt_seed: int | None,
    ) -> dict[str, StoryPromptPrefetch]:
        """Prefetch story prompts in parallel for the next sprint."""
        if self.config.parallel_prompt_workers <= 1 or len(stories) < 2:
            return {}

        snapshot = workspace.build_context_snapshot(
            max_files=self.config.snapshot_max_files,
            max_chars_per_file=self.config.snapshot_max_chars_per_file,
        )
        snapshot_hash = hash_text(snapshot)
        system_prompt = build_story_implementation_system_prompt(template)

        def _prefetch(story: BacklogStory) -> StoryPromptPrefetch:
            user_prompt = build_story_implementation_user_prompt(
                refined_requirements_markdown=refined_markdown,
                story=story,
                project_snapshot=snapshot,
                fallback_verification_commands=backlog.global_verification_commands,
                previous_attempt_feedback=story.last_error,
                repo_guidelines=repo_guidelines,
            )
            prompt_fingerprint = hash_text(system_prompt + "\n" + user_prompt)
            response = self.provider.generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                seed=prompt_seed,
            )
            return StoryPromptPrefetch(
                story_id=story.story_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                prompt_fingerprint=prompt_fingerprint,
                response=response,
                snapshot_hash=snapshot_hash,
            )

        prefetched: dict[str, StoryPromptPrefetch] = {}
        with ThreadPoolExecutor(max_workers=self.config.parallel_prompt_workers) as executor:
            future_map = {executor.submit(_prefetch, story): story.story_id for story in stories}
            for future in as_completed(future_map):
                story_id = future_map[future]
                try:
                    prefetched[story_id] = future.result()
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Prefetch failed for story %s: %s",
                        story_id,
                        exc,
                    )
        return prefetched

    def _execute_story(
        self,
        workspace: FileWorkspace,
        story: BacklogStory,
        backlog: StoryBacklog,
        refined_markdown: str,
        repo_guidelines: str | None,
        template: PromptTemplate,
        journal: PromptJournal,
        prompt_seed: int | None,
        prefetched: StoryPromptPrefetch | None = None,
    ) -> StoryExecutionState:
        """Execute one story with bounded retries and journaling."""
        feedback: str | None = story.last_error
        last_results: list[CommandResult] = []
        max_attempts = self.config.max_task_attempts
        default_commands = resolve_story_commands(story, backlog.global_verification_commands)

        for attempt in range(1, max_attempts + 1):
            snapshot = workspace.build_context_snapshot(
                max_files=self.config.snapshot_max_files,
                max_chars_per_file=self.config.snapshot_max_chars_per_file,
            )
            snapshot_hash = hash_text(snapshot)
            prefetch_snapshot_match: bool | None = None
            use_prefetch = (
                prefetched is not None
                and attempt == 1
                and (
                    prefetched.snapshot_hash == snapshot_hash
                    or self.config.allow_stale_parallel_prompts
                )
            )
            prefetched_data = prefetched if use_prefetch and prefetched is not None else None
            if prefetched_data is not None:
                system_prompt = prefetched_data.system_prompt
                user_prompt = prefetched_data.user_prompt
                prompt_fingerprint = prefetched_data.prompt_fingerprint
                prefetch_snapshot_match = prefetched_data.snapshot_hash == snapshot_hash
            else:
                system_prompt = build_story_implementation_system_prompt(template)
                user_prompt = build_story_implementation_user_prompt(
                    refined_requirements_markdown=refined_markdown,
                    story=story,
                    project_snapshot=snapshot,
                    fallback_verification_commands=backlog.global_verification_commands,
                    previous_attempt_feedback=feedback,
                    repo_guidelines=repo_guidelines,
                )
                prompt_fingerprint = hash_text(system_prompt + "\n" + user_prompt)
            raw_response: dict[str, Any] | None = None
            bundle: ExecutionBundle | None = None
            commands = default_commands
            error_text: str | None = None
            quality_warnings: list[str] = []
            quality_result_text: str | None = None
            quality_cached = False

            try:
                if prefetched_data is not None:
                    raw_response = prefetched_data.response
                else:
                    raw_response = self.provider.generate_json(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        seed=prompt_seed,
                    )
                bundle = ExecutionBundle.from_dict(raw_response)
                self._apply_operations(bundle, workspace)
                quality_plan = build_quality_gate_plan(
                    workspace.base_dir,
                    enforce_quality_gates=self.config.enforce_quality_gates,
                    enable_security_scan=self.config.enable_security_scan,
                    security_scan_mode=self.config.security_scan_mode,
                )
                quality_warnings = quality_plan.warnings
                quality_commands = _dedupe_commands(
                    [*quality_plan.format_commands, *quality_plan.verification_commands]
                )
                quality_results, quality_cached = self._run_quality_gate_commands(
                    workspace,
                    quality_commands,
                )
                verification_commands = _dedupe_commands(
                    list(bundle.verification_commands or default_commands)
                )
                commands = [*quality_commands, *verification_commands]
                if quality_results and not all(result.passed for result in quality_results):
                    last_results = quality_results
                else:
                    verification_results = self.executor.run_many(
                        verification_commands,
                        cwd=workspace.base_dir,
                    )
                    last_results = [*quality_results, *verification_results]

                static_quality = evaluate_python_quality(
                    workspace.base_dir,
                    enforce_docstrings=self.config.enforce_docstrings,
                )
                if not static_quality.passed:
                    quality_result_text = self._format_quality_findings(static_quality)
            except Exception as exc:  # noqa: BLE001
                error_text = f"Story attempt failed before verification. Error: {exc}"
                last_results = []

            criteria_ok = self._acceptance_criteria_satisfied(story, workspace)
            commands_passed = bool(last_results) and all(result.passed for result in last_results)
            outcome = (
                "pass"
                if error_text is None
                and commands_passed
                and criteria_ok
                and quality_result_text is None
                else "fail"
            )
            failing_checks = None
            if outcome == "fail":
                failing_checks = error_text or self._format_command_results(last_results)
                if not criteria_ok:
                    failing_checks = (
                        failing_checks + "\n" if failing_checks else ""
                    ) + "Executable acceptance criteria checks failed."
                if quality_result_text is not None:
                    failing_checks = (
                        failing_checks + "\n" if failing_checks else ""
                    ) + quality_result_text
                feedback = failing_checks

            journal.append(
                {
                    "timestamp": self._now(),
                    "phase": "story_execution",
                    "template_id": template.template_id,
                    "template_version": template.version,
                    "story_id": story.story_id,
                    "story_title": story.title,
                    "attempt": attempt,
                    "model_settings": {
                        "provider": type(self.provider).__name__,
                        "seed": prompt_seed,
                    },
                    "prompt_fingerprint": prompt_fingerprint,
                    "response_fingerprint": hash_text(json.dumps(raw_response, sort_keys=True))
                    if raw_response is not None
                    else None,
                    "prefetch_used": use_prefetch,
                    "prefetch_snapshot_match": prefetch_snapshot_match,
                    "tool_actions_requested": [
                        {"op": item.op, "path": item.path}
                        for item in (bundle.operations if bundle is not None else [])
                    ],
                    "verification_commands": commands,
                    "outcome": outcome,
                    "failing_checks": failing_checks,
                    "error": error_text,
                    "quality_warnings": quality_warnings,
                    "quality_cache_hit": quality_cached,
                    "fix_iteration": attempt - 1,
                }
            )

            if outcome == "pass":
                return StoryExecutionState(
                    story_id=story.story_id,
                    attempt=attempt,
                    status=STATUS_COMPLETED,
                    verification_results=last_results,
                    error=None,
                )

        return StoryExecutionState(
            story_id=story.story_id,
            attempt=max_attempts,
            status=STATUS_FAILED,
            verification_results=last_results,
            error=feedback,
        )

    def _append_journal_refinement_event(
        self,
        journal: PromptJournal,
        template: PromptTemplate,
        refined: RefinedRequirements,
    ) -> None:
        """Write a refinement completion entry to prompt journal."""
        journal.append(
            {
                "timestamp": self._now(),
                "phase": "requirements_refinement",
                "template_id": template.template_id,
                "template_version": template.version,
                "outcome": "pass",
                "stories": [story.story_id for story in refined.stories],
                "nfr_categories": sorted(refined.nfrs.keys()),
            }
        )

    def _apply_operations(self, bundle: ExecutionBundle, workspace: FileWorkspace) -> None:
        """Apply model-proposed file operations after schema validation."""
        for operation in bundle.operations:
            if operation.op == "write_file":
                if operation.content is None:
                    msg = f"write_file operation missing content for '{operation.path}'."
                    raise ValueError(msg)
                workspace.write_file(operation.path, operation.content)
            elif operation.op == "delete_file":
                workspace.delete_file(operation.path)
            else:
                raise ValueError(f"Unsupported operation '{operation.op}'.")

    def _acceptance_criteria_satisfied(self, story: BacklogStory, workspace: FileWorkspace) -> bool:
        """Verify extracted executable acceptance checks from story criteria."""
        exists_checks, contains_checks = parse_acceptance_criteria_assertions(
            story.acceptance_criteria
        )
        for path in exists_checks:
            target = workspace.base_dir / path
            if not target.exists():
                return False
        for path, expected in contains_checks:
            target = workspace.base_dir / path
            if not target.exists():
                return False
            try:
                content = target.read_text(encoding="utf-8").lower()
            except OSError:
                return False
            if expected.lower() not in content:
                return False
        return True

    def _persist_progress(
        self,
        workspace: FileWorkspace,
        backlog: StoryBacklog,
        refined: RefinedRequirements,
        *,
        platform_adapter_id: str | None = None,
    ) -> None:
        """Persist progress snapshot for compatibility and observability."""
        output: dict[str, Any] = {
            "project_name": refined.project_name,
            "stack_rationale": refined.stack_rationale,
            "verification_commands": backlog.global_verification_commands,
            "refined_spec": self.config.refined_spec_file,
            "backlog": self.config.backlog_file,
            "design_doc": self.config.design_doc_file,
            "platform_plan": self.config.platform_plan_file,
            "capability_graph": self.config.capability_graph_file,
            "architecture_doc": self.config.architecture_doc_file,
            "architecture_components": self.config.architecture_components_file,
            "architecture_adrs": self.config.architecture_adrs_dir,
            "platform_adapter_id": platform_adapter_id,
            "stories": [
                {
                    "id": item.story_id,
                    "title": item.title,
                    "status": item.status,
                    "attempts": item.attempts,
                    "last_error": item.last_error,
                }
                for item in backlog.stories
            ],
            # Legacy compatibility with prior progress schema.
            "tasks": [
                {
                    "id": item.story_id,
                    "title": item.title,
                    "status": item.status,
                    "attempts": item.attempts,
                    "last_error": item.last_error,
                    "results": [],
                }
                for item in backlog.stories
            ],
        }
        workspace.write_file(self.config.progress_file, json.dumps(output, indent=2))

    def _persist_backlog(self, workspace: FileWorkspace, backlog: StoryBacklog) -> None:
        """Persist the latest backlog JSON artifact."""
        payload = backlog.to_dict()
        validate_backlog_payload(payload)
        workspace.write_file(self.config.backlog_file, json.dumps(payload, indent=2))

    def _persist_design_doc(
        self,
        workspace: FileWorkspace,
        refined: RefinedRequirements,
        backlog: StoryBacklog,
        *,
        phase: str,
    ) -> None:
        """Persist or update internal design doc artifact."""
        content = build_design_doc_markdown(refined=refined, backlog=backlog, phase=phase)
        workspace.write_file(self.config.design_doc_file, content)

    def _append_sprint_log(self, workspace: FileWorkspace, payload: dict[str, Any]) -> None:
        """Append a sprint event to jsonl log."""
        validate_sprint_log_event(payload)
        path = ensure_safe_relative_path(workspace.base_dir, self.config.sprint_log_file)
        root = workspace.base_dir.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True))
            handle.write("\n")
        workspace.changed_files.add(str(path.relative_to(root)).replace("\\", "/"))

    def _format_command_results(self, results: list[CommandResult]) -> str:
        """Render command outputs for debugging and retry feedback."""
        if not results:
            return "No verification commands executed."
        lines: list[str] = []
        any_failure = False
        for result in results:
            lines.append(f"$ {result.command}")
            lines.append(f"exit_code={result.exit_code}")
            lines.append(f"duration_seconds={result.duration_seconds:.2f}")
            if result.exit_code != 0:
                any_failure = True
                hints = self._command_failure_hints(result)
                if hints:
                    lines.append("hints:")
                    lines.extend(f"- {item}" for item in hints)
            if result.stdout.strip():
                lines.append("stdout:")
                lines.append(result.stdout.strip()[-2_000:])
            if result.stderr.strip():
                lines.append("stderr:")
                lines.append(result.stderr.strip()[-2_000:])
        if any_failure:
            lines.append("hint: rerun with --verbose and inspect autosd.log for details.")
        return "\n".join(lines)

    def _format_quality_findings(self, result: QualityGateResult) -> str:
        """Render static quality findings into a single failure message."""
        lines: list[str] = ["Static quality gates failed."]
        syntax_errors = result.syntax_errors
        doc_violations = result.docstring_violations
        if syntax_errors:
            lines.append("Syntax errors:")
            lines.extend(f"- {item}" for item in syntax_errors)
        if doc_violations:
            lines.append("Docstring violations:")
            lines.extend(f"- {item}" for item in doc_violations)
        return "\n".join(lines)

    def _command_failure_hints(self, result: CommandResult) -> list[str]:
        """Derive actionable hints from command failures."""
        if result.exit_code == 0:
            return []
        combined = f"{result.stdout}\n{result.stderr}".lower()
        hints: list[str] = []
        if "no module named" in combined or "command not found" in combined:
            if "ruff" in result.command:
                hints.append("Install ruff (python -m pip install ruff) or disable quality gates.")
            if "mypy" in result.command:
                hints.append("Install mypy (python -m pip install mypy) or adjust mypy config.")
            if "pytest" in result.command:
                hints.append("Install pytest (python -m pip install pytest) or update test scope.")
            if "bandit" in result.command:
                hints.append("Install bandit or set --security-scan-mode if-available.")
        if "permission denied" in combined:
            hints.append("Check filesystem permissions for generated project files.")
        return hints

    def _ensure_agents_md(self, workspace: FileWorkspace) -> None:
        """Create default AGENTS.md in generated workspace if absent."""
        if workspace.read_optional("AGENTS.md") is None:
            workspace.write_file("AGENTS.md", DEFAULT_AGENTS_MD)

    def _track_architecture_artifacts(
        self,
        workspace: FileWorkspace,
        artifacts: ArchitectureArtifacts,
    ) -> None:
        """Track architecture artifacts in workspace change list."""
        root = workspace.base_dir.resolve()
        for path in [artifacts.architecture_doc, artifacts.components_json, *artifacts.adr_files]:
            resolved = path.resolve()
            workspace.changed_files.add(str(resolved.relative_to(root)).replace("\\", "/"))

    def _now(self) -> str:
        """Return deterministic timestamp when reproducible mode is enabled."""
        if self.config.reproducible:
            return "1970-01-01T00:00:00+00:00"
        return datetime.now(tz=UTC).isoformat()

    def _run_quality_gate_commands(
        self,
        workspace: FileWorkspace,
        commands: list[str],
    ) -> tuple[list[CommandResult], bool]:
        """Run quality gate commands with cache support."""
        if not commands:
            return [], False
        config_payload = {
            "enforce_quality_gates": self.config.enforce_quality_gates,
            "enable_security_scan": self.config.enable_security_scan,
            "security_scan_mode": self.config.security_scan_mode,
            "enforce_docstrings": self.config.enforce_docstrings,
        }
        fingerprint = compute_quality_gate_fingerprint(
            workspace.base_dir,
            commands=commands,
            config=config_payload,
        )
        cache = load_quality_gate_cache(workspace.base_dir)
        if (
            cache is not None
            and cache.fingerprint == fingerprint
            and cache.commands == commands
            and cache.results
            and all(result.passed for result in cache.results)
        ):
            return self._mark_cached_results(cache.results), True

        results = self.executor.run_many(commands, cwd=workspace.base_dir)
        if results and all(result.passed for result in results):
            post_fingerprint = compute_quality_gate_fingerprint(
                workspace.base_dir,
                commands=commands,
                config=config_payload,
            )
            save_quality_gate_cache(
                workspace.base_dir,
                QualityGateCacheEntry(
                    fingerprint=post_fingerprint,
                    commands=commands,
                    results=results,
                ),
            )
        return results, False

    def _mark_cached_results(self, results: list[CommandResult]) -> list[CommandResult]:
        """Annotate cached command results for visibility."""
        cached_results: list[CommandResult] = []
        for item in results:
            note = "cached: previous success\n"
            stdout = item.stdout
            if note not in stdout:
                stdout = f"{note}{stdout}".strip()
            cached_results.append(
                CommandResult(
                    command=item.command,
                    exit_code=item.exit_code,
                    stdout=stdout,
                    stderr=item.stderr,
                    duration_seconds=item.duration_seconds,
                )
            )
        return cached_results

    def _serialize_gate_results(self, results: list[CommandResult]) -> list[dict[str, Any]]:
        """Serialize gate results for provenance reporting."""
        duration_override = 0.0 if self.config.reproducible else None
        output: list[dict[str, Any]] = []
        for item in results:
            duration = duration_override if duration_override is not None else item.duration_seconds
            output.append(
                {
                    "command": item.command,
                    "exit_code": item.exit_code,
                    "duration_seconds": duration,
                }
            )
        return output


def _dedupe_commands(commands: list[str]) -> list[str]:
    """Remove duplicate commands while preserving order."""
    seen: set[str] = set()
    output: list[str] = []
    for command in commands:
        cleaned = command.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        output.append(cleaned)
    return output
