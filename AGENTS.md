# AGENTS.md

## Scope
This repository contains the generator for an autonomous software-factory agent.

## Coding Rules
- Use Python 3.11+.
- Keep code modular (SRP), avoid duplication (DRY), and prefer simple designs (KISS).
- Validate inputs early and fail fast with explicit errors.
- Follow idiomatic style and naming; Python code should be PEP8-compatible.
- Add docstrings for public functions/classes.
- Do not hardcode credentials, tokens, API keys, private keys, or secrets.

## Execution Rules
- Default `autosd run` flow remains backward-compatible.
- Keep retries and autonomous loops bounded by config/policy budgets.
- Never loosen executor guardrails or path safety checks.

## Artifact Rules
Generated project `.autosd/` artifacts may include:

- `refined_requirements.md`
- `backlog.json`
- `progress.json`
- `sprint_log.jsonl`
- `prompt_journal.jsonl`
- `design_doc.md`
- `platform_plan.json`
- `capability_graph.json`
- `policy_resolved.json`
- `provenance/build_manifest.json` (optional `provenance/sbom.json`)
- `telemetry/events.jsonl` (only when telemetry enabled)
- `postmortems/*.md` (incident healing)

Rules:
- Keep JSONL logs append-only (`sprint_log.jsonl`, `prompt_journal.jsonl`, incidents/audit logs).
- Redact secrets before writing logs/journals/audit/telemetry.
- Never write raw environment variable values to artifacts.

## Privacy Rules
- Telemetry is OFF by default.
- Never collect/store PII, IP addresses, device fingerprints, raw payloads, or user content.
- Enforce retention policies for local telemetry warehouse.

## Policy / Preauth Rules
- High-risk actions require policy checks and (when configured/required) valid preauth grants.
- Production deploy and auto-merge must not proceed without explicit grant allowance.
- Preauth private keys must remain local and never be committed.
- Revocation and expiry must be enforced on every privileged action.

## Prompt Pattern and Learning Rules
- Prompt templates are versioned in `automated_software_developer/agent/prompt_patterns/`.
- Learning outputs human-reviewable proposals/changelog.
- Template changes are applied only when explicitly requested.
- Keep prior versions for rollback.

## Quality/Security Gate Rules
- Treat lint/type/test/style violations as blocking errors.
- Keep quality gates safe-by-default.
- Optional security scanning may run (Bandit when configured).
- Use risk-reduced/hardened wording; never claim perfect security.

## Verification Rules
Run before completion:

```bash
python -m ruff check .
python -m mypy automated_software_developer
python -m pytest
```

## Review Guidelines
- Prioritize regressions, security gaps, missing edge-case tests, and interface breakage.
- Keep README/CLI docs aligned with implementation.
- Ensure new features include deterministic tests.

## Release Documentation Notes
- Ensure docs cover telemetry defaults, incident/self-healing workflows, and preauth grant management.
- Keep operational examples current (deploy, rollback, promote, preauth list/revoke, telemetry enable/disable).
- Mention the local debug log (`autosd.log`) and `--verbose` flag when relevant.
