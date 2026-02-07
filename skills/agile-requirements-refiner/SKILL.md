---
name: agile-requirements-refiner
description: Autonomous refinement of raw software requirements into an Agile-ready canonical spec with product brief, personas, user stories, Given/When/Then acceptance criteria, NFRs, assumptions, and dependency/ambiguity analysis. Use when requirements are incomplete, ambiguous, contradictory, or need implementation-ready decomposition before coding.
---

# Agile Requirements Refiner

## Inputs
- Raw requirements text.
- Repository AGENTS.md rules (if available).
- Optional heuristic notes or domain constraints.

## Outputs
- Canonical refined requirements artifact (`.autosd/refined_requirements.md`).
- Structured stories and assumptions suitable for backlog creation.

## Procedure
1. Parse raw requirements and detect ambiguity, contradiction, missing constraints, edge cases, and likely dependencies.
2. Infer NFR categories from requirement signals: security, privacy, performance, reliability, observability, UX/accessibility, compliance.
3. Generate user stories in strict format: `As a ... I want ... so that ...`.
4. Generate acceptance criteria per story in Given/When/Then form.
5. Convert unresolved uncertainties into explicit assumptions and attach a testable criterion for each assumption.
6. Validate schema completeness and normalize missing fields with safe defaults.
7. Persist the canonical refined markdown artifact.

## Success Criteria
- Every story has valid story text and executable-oriented acceptance criteria.
- Assumptions are explicit and testable.
- NFRs and edge cases are documented.
- Artifact is deterministic and saved in `.autosd`.

## Safety Notes
- Never request or log secrets.
- Never weaken execution guardrails.
- Never claim perfect security; use risk-reduced and hardened language.