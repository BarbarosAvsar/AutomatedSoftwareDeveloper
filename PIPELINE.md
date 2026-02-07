# Pipeline Truth Map

This repository uses a single authoritative pipeline map defined in
`automated_software_developer/agent/pipeline/schema.py`. That module is referenced by
progress reporting to avoid drift between documentation and implementation. It also
publishes the JSON schema for pipeline events and statuses.

## Generator Pipeline

1. **Refine** → draft, refine, validate, lock
2. **Plan** → architecture, backlog, sprint_planning
3. **Sprint** → stories_in_progress, stories_completed
4. **Gates** → tests, quality_gates, security_scans
5. **Release** → version_tag, artifacts
6. **Deploy** → dev, staging, production
7. **Monitor** → health_checks
8. **Learn** → retrospective, template_proposals

## UI Pipeline

1. **Requirements Studio** → capture + refine requirements
2. **Approve** → lock requirements before autonomy
3. **Launch** → start autonomous build
4. **Progress / ETA** → monitor pipeline and ETA updates

## CI Pipeline

1. **Workflow Lint** → validate workflow syntax and policy compliance
2. **Lint** → ruff linting
3. **Typecheck** → mypy type checking
4. **Test** → unit + integration tests
5. **Conformance** → generator fixture conformance

## Pipeline Event Schema

Pipeline events must conform to `PIPELINE_EVENT_SCHEMA` in
`automated_software_developer/agent/pipeline/schema.py`, including:

- `event_id`, `timestamp`, `pipeline`, `step`, `status`
- status values: `not_started`, `in_progress`, `blocked`, `completed`, `failed`
