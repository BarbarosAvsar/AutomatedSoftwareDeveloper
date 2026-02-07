---
name: story-implementer-with-tests
description: Story-by-story implementation workflow that applies safe file operations, creates or updates tests, runs verification commands, and retries with focused fixes until acceptance criteria pass. Use during sprint execution for autonomous coding with regression safeguards.
---

# Story Implementer With Tests

## Inputs
- Active backlog story with acceptance criteria and dependencies.
- Refined requirements context.
- Current project snapshot.
- Verification command set.

## Outputs
- Safe file operations for the active story.
- Updated tests and code.
- Story result (`completed` or `failed`) with attempt history.
- Journal and sprint-log records.

## Procedure
1. Select dependency-satisfied pending stories only.
2. Build story-specific prompts with template id/version and prior failure feedback.
3. Generate strict JSON file operations and apply them with workspace path safeguards.
4. Run story verification commands (and generated lightweight checks when needed).
5. If checks fail, capture failing signals and retry with bounded attempts.
6. Mark story completed only when checks pass and acceptance criteria are satisfied.
7. Persist backlog, progress, sprint log, and prompt journal artifacts.

## Success Criteria
- Each completed story passes verification commands and acceptance checks.
- Failures produce bounded retries with focused fixes.
- Journaling is append-only and redacted.
- No dependency violations in sprint selection.

## Safety Notes
- Never execute unsafe commands.
- Never store secrets in logs, journals, or generated artifacts.
- Never perform unrelated refactors during a fix loop.