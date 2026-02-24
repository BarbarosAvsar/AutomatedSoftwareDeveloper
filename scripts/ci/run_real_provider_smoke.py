"""Run non-mock conformance smoke checks with a real OpenAI provider."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from automated_software_developer.agent.conformance.fixtures import load_fixtures
from automated_software_developer.agent.conformance.runner import (
    ConformanceConfig,
    run_conformance_suite,
)

SMOKE_FIXTURE_IDS: tuple[str, ...] = ("cli_tool", "api_service", "web_app")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("conformance/output-real-provider"),
        help="Directory for generated smoke projects.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path("conformance/report-real-provider.json"),
        help="Output report path.",
    )
    parser.add_argument(
        "--model",
        default="gpt-5.3-codex",
        help="OpenAI model id for smoke checks.",
    )
    parser.add_argument(
        "--smoke-fixtures",
        default="cli_tool,api_service,web_app",
        help="Comma-separated fixture ids for smoke checks.",
    )
    parser.add_argument(
        "--required",
        action="store_true",
        help="Treat missing provider prerequisites and failed checks as blocking.",
    )
    parser.add_argument(
        "--advisory",
        action="store_true",
        help="Treat failed checks as advisory (non-blocking).",
    )
    parser.add_argument(
        "--strict-readiness",
        action="store_true",
        help="Enable strict readiness checks for generated projects.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    required = args.required or not args.advisory
    fixture_ids = _parse_fixture_ids(args.smoke_fixtures)
    fixtures = [item for item in load_fixtures() if item.fixture_id in fixture_ids]
    if not fixtures:
        print("No smoke fixtures found.")
        return 1
    if required and not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is required for real-provider smoke checks.")
        return 1
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY missing; skipping real-provider smoke checks (advisory mode).")
        return 0
    report = run_conformance_suite(
        fixtures=fixtures,
        config=ConformanceConfig(
            output_dir=args.output_dir,
            report_path=args.report_path,
            provider="openai",
            model=args.model,
            reproducible=False,
            diff_check=False,
            max_workers=1,
            strict_readiness=args.strict_readiness,
        ),
    )
    payload = report.to_dict()
    payload["fixtures_requested"] = fixture_ids
    payload["required"] = required
    print(json.dumps(payload, indent=2))
    if report.passed or not required:
        return 0
    return 1


def _parse_fixture_ids(raw_value: str) -> tuple[str, ...]:
    """Parse and normalize smoke fixture ids from comma-separated input."""
    items = [item.strip() for item in raw_value.split(",")]
    normalized = tuple(item for item in items if item)
    return normalized or SMOKE_FIXTURE_IDS


if __name__ == "__main__":
    raise SystemExit(main())
