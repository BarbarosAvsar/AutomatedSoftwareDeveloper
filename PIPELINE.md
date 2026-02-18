# Pipeline Truth Map

This repository uses a single authoritative pipeline map defined in
`automated_software_developer/agent/pipeline/schema.py`. That module is referenced by
progress reporting to avoid drift between documentation and implementation. It also
publishes the JSON schema for pipeline events and statuses.

## Generator Pipeline

1. **Refine** -> draft, refine, validate, lock
2. **Plan** -> architecture, backlog, sprint_planning
3. **Sprint** -> stories_in_progress, stories_completed
4. **Gates** -> tests, quality_gates, security_scans
5. **Release** -> version_tag, artifacts
6. **Deploy** -> dev, staging, production
7. **Monitor** -> health_checks
8. **Learn** -> retrospective, template_proposals

## CI Pipeline

1. **Quality Gates** -> ruff, mypy, pytest
2. **Factory Conformance** -> `autosd verify-factory --skip-generator-gates`
3. **Failure Summary** -> unified summary, append-only ledger, dashboard update

Execution notes:

- `.github/workflows/unified-actions.yml` is the authoritative CI executor.
- `.github/workflows/unified-actions.yml` is the only workflow file used for CI execution.
- Failed workflow runs are documented in:
  - local append-only ledger: `.autosd/ci/failure_ledger.jsonl`
  - persistent issue: `CI Failure Dashboard` (`ci-failures` label, latest 30 failures)

## Pipeline Event Schema

Pipeline events must conform to `PIPELINE_EVENT_SCHEMA` in
`automated_software_developer/agent/pipeline/schema.py`, including:

- `event_id`, `timestamp`, `pipeline`, `step`, `status`
- status values: `not_started`, `in_progress`, `blocked`, `completed`, `failed`
