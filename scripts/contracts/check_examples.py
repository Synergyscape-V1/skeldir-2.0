#!/usr/bin/env python3
"""
Ensure that success responses include request/response examples.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

import platform
from datetime import datetime, timezone

import yaml

SCRIPT_VERSION = "1.0.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate success response examples.")
    parser.add_argument(
        "--input-dir",
        default="api-contracts/dist/openapi/v1",
        help="Directory containing bundled OpenAPI files.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write the JSON report.",
    )
    return parser.parse_args()


def has_example(response: Dict[str, Any]) -> bool:
    content = response.get("content", {})
    json_content = content.get("application/json", {})
    if "example" in json_content:
        return True
    examples = json_content.get("examples")
    if isinstance(examples, dict) and len(examples) > 0:
        return True
    return False


def check_file(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        spec = yaml.safe_load(fh)

    issues: list[dict] = []
    paths = spec.get("paths", {})
    for route, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, method_item in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue
            responses = method_item.get("responses", {})
            for status_code, response in responses.items():
                if not isinstance(status_code, str) or not status_code.startswith("2"):
                    continue
                if not isinstance(response, dict):
                    issues.append(
                        {
                            "route": route,
                            "method": method.upper(),
                            "status": status_code,
                            "reason": "Response definition is not a mapping",
                        }
                    )
                    continue
                if has_example(response):
                    continue
                issues.append(
                    {
                        "route": route,
                        "method": method.upper(),
                        "status": status_code,
                        "reason": "Missing example for application/json success response",
                    }
                )
    return issues


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    records = []
    total_issues = 0
    for file_path in sorted(input_dir.glob("*.bundled.yaml")):
        issues = check_file(file_path)
        records.append(
            {
                "file": str(file_path),
                "issues": issues,
            }
        )
        total_issues += len(issues)

    report = {
        "status": "success" if total_issues == 0 else "failure",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "script_version": SCRIPT_VERSION,
        "python_version": platform.python_version(),
        "total_files": len(records),
        "total_issues": total_issues,
        "files": records,
    }

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    if total_issues > 0:
        print(f"ERROR: Found {total_issues} example issues. See {output_path}")
        return 1

    print(f"Example validation passed: {len(records)} files checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
