#!/usr/bin/env python3
"""
Verify that all 4xx/5xx responses reference the shared error response components.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import platform
from datetime import datetime, timezone

import yaml

SCRIPT_VERSION = "1.0.0"


VALID_RESPONSE_REF_PREFIXES = (
    "_common/components.yaml#/components/responses/",
    "#/components/responses/",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate RFC 7807 error usage.")
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


def response_is_valid(response: Dict[str, Any]) -> bool:
    if "$ref" in response:
        ref = response["$ref"]
        return any(ref.startswith(prefix) for prefix in VALID_RESPONSE_REF_PREFIXES)

    content = response.get("content", {})
    for media in content.values():
        schema = media.get("schema", {})
        if schema_matches_problem(schema):
            return True
    return False


def schema_matches_problem(schema: Dict[str, Any]) -> bool:
    if "$ref" in schema:
        ref = schema["$ref"]
        return any(ref.startswith(prefix) for prefix in VALID_RESPONSE_REF_PREFIXES)

    required = schema.get("required", [])
    properties = schema.get("properties", {})
    for key in ("type", "title", "status", "detail"):
        if key not in required or key not in properties:
            return False
    return True


def check_file(path: Path) -> List[Dict[str, str]]:
    problems: List[Dict[str, str]] = []
    with open(path, "r", encoding="utf-8") as fh:
        spec = yaml.safe_load(fh)

    paths = spec.get("paths", {})
    for route, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, method_item in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue
            responses = method_item.get("responses", {})
            for status_code, response in responses.items():
                if not isinstance(status_code, str) or not status_code[:1] in {"4", "5"}:
                    continue
                if not isinstance(response, dict):
                    problems.append(
                        {
                            "route": route,
                            "method": method.upper(),
                            "status": status_code,
                            "reason": "Response definition is not a mapping",
                        }
                    )
                    continue
                if response_is_valid(response):
                    continue
                problems.append(
                    {
                        "route": route,
                        "method": method.upper(),
                        "status": status_code,
                        "reason": "Response does not reference shared error component",
                    }
                )
    return problems


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
        print(
            f"ERROR: Found {total_issues} error-model issues. See {output_path}",
        )
        return 1

    print(f"Error model validation passed: {len(records)} files checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
