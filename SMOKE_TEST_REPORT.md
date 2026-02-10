# Smoke Test Report: end-to-end generation and functional validation

Date: 2026-02-10

## Goal
Validate that `autosd` can generate a small software project and that the generated product works end-to-end.

## Scenario
Used the bundled conformance CLI fixture (mocked provider) to create a small CLI application without requiring external API credentials.

## Commands executed
1. `autosd run --provider mock --mock-responses-file conformance/requirements/cli_tool.mock.json --requirements-file conformance/requirements/cli_tool.md --output-dir /tmp/autosd_cli_fixture`
2. `python -m pytest -q` (run inside `/tmp/autosd_cli_fixture`)
3. `python -m pip install -e .[dev]` (run inside `/tmp/autosd_cli_fixture`)
4. `python -m cli_tool_fixture.cli` (run inside `/tmp/autosd_cli_fixture`)

## Results
- Project generation completed successfully with the autonomous development summary and internal verification checks marked PASS.
- Generated project unit tests passed (`1 passed`).
- Generated CLI executed successfully and printed `hello world`.

## Cleanup performed
Deleted temporary smoke-test artifacts from `/tmp`:
- `/tmp/autosd_cli_fixture`
- `/tmp/autosd_smoke_project` (empty failed-attempt path if present)
- `/tmp/autosd_smoke_requirements.md`

No generated artifacts were kept in this repository.
