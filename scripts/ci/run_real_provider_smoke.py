"""Run non-mock conformance smoke checks with a real OpenAI provider."""

from __future__ import annotations

import argparse
import json
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
        "--strict-readiness",
        action="store_true",
        help="Enable strict readiness checks for generated projects.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    fixtures = [item for item in load_fixtures() if item.fixture_id in SMOKE_FIXTURE_IDS]
    if not fixtures:
        print("No smoke fixtures found.")
        return 1
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
    print(json.dumps(payload, indent=2))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
