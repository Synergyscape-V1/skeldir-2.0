"""B1.5-P2 contract addendum semantic enforcement tests.

These tests are static contract semantics checks against bundled OpenAPI specs.
They intentionally fail under meaningful regressions (negative controls included).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = REPO_ROOT / "api-contracts" / "dist" / "openapi" / "v1"

CANONICAL_LIFECYCLE_STATES = [
    "submitted",
    "validating",
    "investigating",
    "ready_for_review",
    "approved",
    "rejected",
    "refine_requested",
    "rerun_requested",
    "completed",
    "failed",
    "timeout",
    "cancelled",
]

REQUIRED_MUTATIONS = ("approve", "reject", "refine", "rerun", "retry", "cancel")


def _load_bundle(bundle_name: str) -> dict[str, Any]:
    bundle_path = DIST_DIR / bundle_name
    assert bundle_path.exists(), f"missing bundle: {bundle_path}"
    return yaml.safe_load(bundle_path.read_text(encoding="utf-8"))


def _resolve_local_ref(doc: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    resolved = schema
    while isinstance(resolved, dict) and "$ref" in resolved:
        ref = resolved["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            raise AssertionError(f"unsupported ref: {ref}")
        target: Any = doc
        for part in ref.lstrip("#/").split("/"):
            target = target[part]
        resolved = target
    if not isinstance(resolved, dict):
        raise AssertionError("resolved schema is not an object")
    return resolved


def _flatten_object_schema(doc: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    schema = _resolve_local_ref(doc, schema)
    merged: dict[str, Any] = {"properties": {}, "required": []}

    def _merge(src: dict[str, Any]) -> None:
        resolved = _resolve_local_ref(doc, src)
        for key, value in resolved.get("properties", {}).items():
            merged["properties"][key] = value
        for req in resolved.get("required", []):
            if req not in merged["required"]:
                merged["required"].append(req)

    if "allOf" in schema:
        for part in schema["allOf"]:
            _merge(part)
    else:
        _merge(schema)

    return merged


def _collect_status_urls(payload: Any) -> list[str]:
    urls: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "status_url" and isinstance(value, str):
                urls.append(value)
            else:
                urls.extend(_collect_status_urls(value))
    elif isinstance(payload, list):
        for item in payload:
            urls.extend(_collect_status_urls(item))
    return urls


def _find_broken_status_urls(doc: dict[str, Any]) -> list[str]:
    found_urls = _collect_status_urls(doc)
    paths = doc.get("paths", {})
    broken: list[str] = []

    def _matches_template(actual_path: str, template_path: str) -> bool:
        actual_parts = [part for part in actual_path.split("/") if part]
        template_parts = [part for part in template_path.split("/") if part]
        if len(actual_parts) != len(template_parts):
            return False
        for actual_part, template_part in zip(actual_parts, template_parts):
            if template_part.startswith("{") and template_part.endswith("}"):
                if not actual_part:
                    return False
                continue
            if actual_part != template_part:
                return False
        return True

    for raw_url in found_urls:
        parsed = urlparse(raw_url)
        route_path = parsed.path if parsed.scheme else raw_url
        matched = False
        for template_path, operations in paths.items():
            if not isinstance(operations, dict):
                continue
            if "get" not in operations:
                continue
            if _matches_template(route_path, template_path):
                matched = True
                break
        if not matched:
            broken.append(route_path)
    return broken


def _validate_lifecycle_vocab(enum_values: list[str]) -> list[str]:
    violations: list[str] = []
    if enum_values != CANONICAL_LIFECYCLE_STATES:
        violations.append("lifecycle_enum_mismatch")
    return violations


def _assert_mutations_and_idempotency(doc: dict[str, Any], *, domain_base_path: str, id_field: str) -> None:
    paths = doc.get("paths", {})
    for action in REQUIRED_MUTATIONS:
        route = f"{domain_base_path}/{action}"
        assert route in paths, f"missing mutation route: {route}"
        operation = paths[route].get("post")
        assert operation, f"missing POST operation: {route}"

        description = str(operation.get("description", "")).lower()
        assert "idempotency" in description, f"idempotency contract text missing in {route}"
        assert "replay" in description, f"duplicate replay semantics missing in {route}"

        params = operation.get("parameters", [])
        idempotency_params = [
            p
            for p in params
            if isinstance(p, dict)
            and p.get("in") == "header"
            and p.get("name") == "X-Idempotency-Key"
            and p.get("required") is True
        ]
        assert idempotency_params, f"{route} missing required X-Idempotency-Key header"

        response_200 = operation.get("responses", {}).get("200", {})
        headers = response_200.get("headers", {})
        replay_header = headers.get("X-Idempotency-Replayed")
        assert replay_header, f"{route} missing X-Idempotency-Replayed response header"

        response_schema = (
            response_200
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )
        flattened = _flatten_object_schema(doc, response_schema)
        required = set(flattened.get("required", []))
        assert id_field in required, f"{route} response missing {id_field}"
        assert "idempotency_key" in required, f"{route} response missing idempotency_key"
        assert "idempotency_replayed" in required, f"{route} response missing idempotency_replayed"
        assert "mutation_accepted" in required, f"{route} response missing mutation_accepted"


@pytest.mark.parametrize(
    "bundle_name",
    ["llm-investigations.bundled.yaml", "llm-budget.bundled.yaml"],
)
def test_b15_p2_state_vocabulary_contains_review_and_terminal_failure_truth(bundle_name: str) -> None:
    doc = _load_bundle(bundle_name)
    enum_values = (
        doc.get("components", {})
        .get("schemas", {})
        .get("CentaurLifecycleStatus", {})
        .get("enum", [])
    )
    violations = _validate_lifecycle_vocab(enum_values)
    assert not violations, f"{bundle_name} lifecycle violations: {violations}"


def test_b15_p2_investigation_mutations_have_idempotency_contract_semantics() -> None:
    doc = _load_bundle("llm-investigations.bundled.yaml")
    _assert_mutations_and_idempotency(
        doc,
        domain_base_path="/api/investigations/{investigation_id}",
        id_field="investigation_id",
    )


def test_b15_p2_budget_mutations_have_idempotency_contract_semantics() -> None:
    doc = _load_bundle("llm-budget.bundled.yaml")
    _assert_mutations_and_idempotency(
        doc,
        domain_base_path="/api/budget/recommendations/{job_id}",
        id_field="job_id",
    )


@pytest.mark.parametrize(
    "bundle_name",
    ["llm-investigations.bundled.yaml", "llm-budget.bundled.yaml"],
)
def test_b15_p2_status_url_examples_resolve_to_contracted_status_routes(bundle_name: str) -> None:
    doc = _load_bundle(bundle_name)
    broken = _find_broken_status_urls(doc)
    assert not broken, f"{bundle_name} has broken status_url paths: {sorted(set(broken))}"


def test_b15_p2_result_shapes_separate_deterministic_authority_from_llm_synthesis() -> None:
    investigations = _load_bundle("llm-investigations.bundled.yaml")
    budget = _load_bundle("llm-budget.bundled.yaml")

    inv_schema = investigations["components"]["schemas"]["InvestigationResultResponse"]
    inv_flat = _flatten_object_schema(investigations, inv_schema)
    inv_props = inv_flat["properties"]
    inv_required = set(inv_flat["required"])
    assert "deterministic_findings" in inv_props
    assert "deterministic_findings" in inv_required
    assert "llm_synthesis" in inv_props
    assert "synthesis" not in inv_props

    inv_synthesis = _resolve_local_ref(investigations, inv_props["llm_synthesis"])
    inv_description = str(inv_synthesis.get("description", "")).lower()
    assert "non-authoritative" in inv_description

    budget_schema = budget["components"]["schemas"]["BudgetRecommendationResponse"]
    budget_flat = _flatten_object_schema(budget, budget_schema)
    budget_props = budget_flat["properties"]
    budget_required = set(budget_flat["required"])
    assert "deterministic_recommendation" in budget_props
    assert "deterministic_recommendation" in budget_required
    assert "llm_synthesis" in budget_props
    assert "synthesis" not in budget_props

    budget_synthesis = _resolve_local_ref(budget, budget_props["llm_synthesis"])
    budget_description = str(budget_synthesis.get("description", "")).lower()
    assert "non-authoritative" in budget_description


def test_b15_p2_negative_control_detects_missing_ready_for_review_state() -> None:
    doc = _load_bundle("llm-investigations.bundled.yaml")
    mutated = copy.deepcopy(doc)
    enum_values = mutated["components"]["schemas"]["CentaurLifecycleStatus"]["enum"]
    mutated["components"]["schemas"]["CentaurLifecycleStatus"]["enum"] = [
        value for value in enum_values if value != "ready_for_review"
    ]

    violations = _validate_lifecycle_vocab(
        mutated["components"]["schemas"]["CentaurLifecycleStatus"]["enum"]
    )
    assert violations == ["lifecycle_enum_mismatch"]


def test_b15_p2_negative_control_detects_broken_budget_status_url() -> None:
    doc = _load_bundle("llm-budget.bundled.yaml")
    mutated = copy.deepcopy(doc)

    mutated["paths"]["/api/budget/optimize"]["post"]["responses"]["202"]["content"][
        "application/json"
    ]["example"]["status_url"] = "http://localhost:4025/api/budget/jobs/does-not-exist/status"

    broken = _find_broken_status_urls(mutated)
    assert "/api/budget/jobs/does-not-exist/status" in broken
