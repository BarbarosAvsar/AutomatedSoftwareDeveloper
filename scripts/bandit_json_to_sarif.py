"""Convert Bandit JSON output to SARIF 2.1.0 for GitHub code scanning upload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_bandit_json(path: Path) -> dict[str, Any]:
    """Load and validate Bandit JSON payload from disk."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Bandit JSON payload must be an object.")
    results = payload.get("results", [])
    if not isinstance(results, list):
        raise ValueError("Bandit JSON payload field 'results' must be a list.")
    return payload


def _rule_index(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build a stable SARIF rule index keyed by Bandit test id."""
    rules: dict[str, dict[str, Any]] = {}
    for result in results:
        if not isinstance(result, dict):
            continue
        test_id = str(result.get("test_id", "BANDIT"))
        test_name = str(result.get("test_name", "Bandit finding"))
        if test_id not in rules:
            rules[test_id] = {
                "id": test_id,
                "name": test_name,
                "shortDescription": {"text": test_name},
                "helpUri": "https://bandit.readthedocs.io/",
            }
    return rules


def _level_for_issue_severity(severity: str) -> str:
    """Map Bandit severity labels to SARIF result levels."""
    normalized = severity.upper()
    if normalized == "HIGH":
        return "error"
    if normalized == "MEDIUM":
        return "warning"
    return "note"


def _to_sarif(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert Bandit payload to a SARIF 2.1.0 object."""
    raw_results = payload.get("results", [])
    results = [item for item in raw_results if isinstance(item, dict)]
    rules = _rule_index(results)

    sarif_results: list[dict[str, Any]] = []
    for result in results:
        test_id = str(result.get("test_id", "BANDIT"))
        file_path = str(result.get("filename", ""))
        line_number = int(result.get("line_number", 1) or 1)
        severity = str(result.get("issue_severity", "LOW"))
        confidence = str(result.get("issue_confidence", "LOW"))
        message = str(result.get("issue_text", "Bandit finding"))

        sarif_results.append(
            {
                "ruleId": test_id,
                "level": _level_for_issue_severity(severity),
                "message": {"text": message},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": file_path},
                            "region": {"startLine": line_number},
                        }
                    }
                ],
                "properties": {
                    "banditSeverity": severity,
                    "banditConfidence": confidence,
                },
            }
        )

    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Bandit",
                        "informationUri": "https://bandit.readthedocs.io/",
                        "rules": list(rules.values()),
                    }
                },
                "results": sarif_results,
            }
        ],
    }


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Path to Bandit JSON report.")
    parser.add_argument("--output", type=Path, required=True, help="Path to write SARIF report.")
    return parser.parse_args()


def main() -> None:
    """Run the Bandit JSON to SARIF conversion."""
    args = _parse_args()
    payload = _load_bandit_json(args.input)
    sarif_payload = _to_sarif(payload)
    args.output.write_text(json.dumps(sarif_payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
