# Deep Research Implementation Roadmap

## Prioritized ToDo

| Priority | Area | Tasks | Effort |
|---|---|---|---|
| P0 | Orchestrator modularization | Split orchestration concerns into dedicated agent modules and wire interfaces. | 1-2 days |
| P0 | Resilience | Add retry/backoff wrapper provider and fallback behavior. | 0.5-1 day |
| P1 | Task queue | Introduce queue abstraction and provide Celery deployment stub. | 0.5 day |
| P1 | Quality gates | Add coverage artifact output and cached gate results. | 0.5 day |
| P1 | Observability | Add JSON logging and local OTEL-like counters. | 0.5 day |
| P2 | Memory layer | Add vector DB adapter interface and journal embedding utility. | 0.5 day |
| P2 | CI/CD hardening | Add dedicated build, SBOM, policy, and verify-factory workflows. | 1 day |

## Migration Notes

- Existing `autosd run` behavior remains backward-compatible by preserving serial execution defaults.
- Task queue integration is additive and currently uses in-process serial behavior.
- Provider selection now supports resilient mode while preserving openai/mock choices.
- New workflows are additive and do not auto-deploy.

## Success Metrics

- `autosd verify-factory` exits successfully in CI.
- Lint/type/test gates are green.
- Coverage artifacts are persisted under `.autosd/provenance/`.
- SBOM and policy checks are generated via CI stubs for future hardening.
