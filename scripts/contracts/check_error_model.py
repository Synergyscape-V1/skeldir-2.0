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

from error_component_registry import (
    ErrorComponentRegistryError,
    PROVENANCE_MARKER,
    load_registry,
    verify_declared_provenance,
)

SCRIPT_VERSION = "2.0.0"


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


def response_is_valid(
    response: Dict[str, Any],
    registry: Dict[str, Dict[str, Any]] | None = None,
) -> tuple[bool, str]:
    """Return ``(is_valid, reason)`` for one 4xx/5xx response object.

    Bundling dereferences response components, destroying `$ref` lineage. A
    response whose runtime wire intentionally is not RFC 7807 (for example
    FastAPI HTTPException's nested ``detail`` object) may therefore declare
    shared provenance explicitly -- but that declaration is only honoured when
    it NAMES a registered component id AND the response's canonical schema
    fingerprint matches that component exactly.

    A bare ``x-skeldir-shared-error-component: true`` is rejected: a response
    cannot prove its own provenance by asserting a boolean.
    """
    if PROVENANCE_MARKER in response:
        verified, reason = verify_declared_provenance(response, registry or {})
        if verified:
            return True, reason
        # A response that declares provenance and fails verification is a hard
        # failure. It must not silently fall through to the structural checks,
        # otherwise a false declaration costs the attacker nothing.
        return False, reason

    if "$ref" in response:
        ref = response["$ref"]
        if any(ref.startswith(prefix) for prefix in VALID_RESPONSE_REF_PREFIXES):
            return True, "shared_component_ref"
        return False, "response_ref_is_not_a_shared_error_component"

    content = response.get("content", {})
    for media in content.values():
        schema = media.get("schema", {})
        if schema_matches_problem(schema):
            return True, "rfc7807_structural_match"
    return False, "response_does_not_reference_shared_error_component"


def schema_matches_problem(schema: Dict[str, Any]) -> bool:
    if "$ref" in schema:
        ref = schema["$ref"]
        if any(ref.startswith(prefix) for prefix in VALID_RESPONSE_REF_PREFIXES):
            return True
        if str(ref).endswith("/ProblemDetails") or str(ref).endswith("ProblemDetails"):
            return True
        return False

    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        for item in all_of:
            if isinstance(item, dict) and schema_matches_problem(item):
                return True

    required = schema.get("required", [])
    properties = schema.get("properties", {})
    for key in ("type", "title", "status", "detail"):
        if key not in required or key not in properties:
            return False
    return True


def check_file(
    path: Path, registry: Dict[str, Dict[str, Any]] | None = None
) -> List[Dict[str, str]]:
    problems: List[Dict[str, str]] = []
    with open(path, "r", encoding="utf-8") as fh:
        spec = yaml.safe_load(fh)

    paths = spec.get("paths", {})
    for route, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, method_item in path_item.items():
            if method.lower() not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "options",
                "head",
            }:
                continue
            responses = method_item.get("responses", {})
            for status_code, response in responses.items():
                if not isinstance(status_code, str) or not status_code[:1] in {
                    "4",
                    "5",
                }:
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
                is_valid, reason = response_is_valid(response, registry)
                if is_valid:
                    continue
                problems.append(
                    {
                        "route": route,
                        "method": method.upper(),
                        "status": status_code,
                        "reason": reason,
                    }
                )
    return problems


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        registry = load_registry()
    except ErrorComponentRegistryError as exc:
        print(f"ERROR: governed error-component registry is invalid: {exc}")
        return 1

    records = []
    total_issues = 0
    for file_path in sorted(input_dir.glob("*.bundled.yaml")):
        issues = check_file(file_path, registry)
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
