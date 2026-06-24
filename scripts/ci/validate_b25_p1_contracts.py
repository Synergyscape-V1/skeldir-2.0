#!/usr/bin/env python3
"""Validate B2.5-P1 TrustEnvelope contract authority and negative controls."""

from __future__ import annotations

import argparse
import copy
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaError


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = ROOT / "contracts/trust-api"
EXAMPLES_DIR = CONTRACT_DIR / "examples"
TRUST_SCHEMA_PATH = CONTRACT_DIR / "trust-envelope.v1.yaml"
ERROR_SCHEMA_PATH = CONTRACT_DIR / "error-envelope.schema.json"
OPENAPI_PATH = CONTRACT_DIR / "trust-api.openapi.yaml"
SCHEMA_REGISTRY_PATH = CONTRACT_DIR / "schema-version-registry.yaml"
SUBJECT_REGISTRY_PATH = CONTRACT_DIR / "subject-authority-registry.yaml"

REQUIRED_FILES = (
    "trust-envelope.v1.yaml",
    "trust-api.openapi.yaml",
    "confidence-metadata.schema.json",
    "provenance-chain.schema.json",
    "policy-authority.schema.json",
    "benchmark-metadata.schema.json",
    "signature.schema.json",
    "audience-binding.schema.json",
    "subject-authority.schema.json",
    "subject-authority-registry.yaml",
    "evidence-temporal-boundary.schema.json",
    "text-disposition.schema.json",
    "error-envelope.schema.json",
    "schema-version-registry.yaml",
)

REQUIRED_TRUST_FIELDS = (
    "envelope_version",
    "schema_version",
    "canonicalization_version",
    "envelope_id",
    "tenant_id_hash",
    "audience_binding",
    "subject_authority",
    "subject_type",
    "subject_ref",
    "subject_ref_hash",
    "truth_type",
    "truth_authority",
    "deterministic_verification_status",
    "match_verdict_status",
    "verified_revenue_minor",
    "currency",
    "discrepancy_class",
    "attribution_model",
    "model_assumption",
    "causal_status",
    "confidence_metadata",
    "provenance_chain",
    "data_completeness_status",
    "benchmark_metadata",
    "policy_action_authority",
    "fallback_applied",
    "fallback_reason",
    "evidence_temporal_boundary",
    "audit_ref",
    "audit_hash",
    "semantic_truth_hash",
    "artifact_ref",
    "artifact_hash",
    "signature_hash",
    "signature",
    "signing_algorithm",
    "signing_key_id",
    "created_at",
    "valid_until",
    "untrusted_display_data",
)

REQUIRED_EXAMPLES = (
    "deterministic_only_verified.json",
    "deterministic_with_bayesian_available.json",
    "deterministic_with_bayesian_unavailable.json",
    "diagnostics_failed_degraded.json",
    "benchmark_unavailable_explicit.json",
    "source_snapshot_stale_degraded.json",
    "artifact_pruned_degraded.json",
    "scope_denied.json",
    "replay_rejected.json",
    "schema_version_unsupported.json",
    "schema_downgrade_rejected.json",
    "prompt_control_string_quarantined.json",
    "money_source_not_authoritative.json",
    "money_amount_exceeds_json_safe_integer.json",
    "audience_bound_agent_client.json",
    "public_verification_only.json",
    "evidence_snapshot_stale_degraded.json",
    "canonical_timestamp_rejected.json",
    "human_workflow_state_rejected.json",
    "subject_authority_rejected.json",
    "mutable_workflow_subject_rejected.json",
)

ERROR_EXAMPLES = {
    "scope_denied.json",
    "replay_rejected.json",
    "schema_version_unsupported.json",
    "schema_downgrade_rejected.json",
    "money_source_not_authoritative.json",
    "money_amount_exceeds_json_safe_integer.json",
    "canonical_timestamp_rejected.json",
    "human_workflow_state_rejected.json",
    "subject_authority_rejected.json",
    "mutable_workflow_subject_rejected.json",
}

FORBIDDEN_EXTERNAL_FIELDS = {
    "tenant_id",
    "client_id",
    "agent_client_id",
    "user_id",
    "service_token_id",
    "raw_account_id",
}

HUMAN_WORKFLOW_STATES = {
    "open",
    "acknowledged",
    "resolved",
    "dismissed",
    "assigned",
    "in_review",
    "escalated",
    "closed",
    "pending_human_review",
    "approved",
    "rejected",
    "commented",
    "snoozed",
}

REQUIRED_OPENAPI_PATHS = {
    "/api/trust/v1/envelopes/{subject_type}/{subject_ref}",
    "/api/trust/v1/envelopes/query",
    "/api/trust/v1/keys/jwks",
    "/api/trust/v1/verify",
}


class ContractValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class NegativeControl:
    name: str
    schema_name: str
    mutate: Callable[[dict[str, Any]], None]
    expected_keyword: str
    expected_path: str


def _read_yaml(path: Path) -> Any:
    if not path.exists():
        raise ContractValidationError(f"missing required file: {path.as_posix()}")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise ContractValidationError(f"missing required file: {path.as_posix()}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractValidationError(message)


def _load_schema(path: Path) -> Any:
    if path.suffix in {".yaml", ".yml"}:
        schema = _read_yaml(path)
    else:
        schema = _read_json(path)
    if path != TRUST_SCHEMA_PATH:
        schema = _inline_trust_defs(schema)
    return schema


def _inline_trust_defs(value: Any) -> Any:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str) and "trust-envelope.v1.yaml#/$defs/" in ref:
            name = ref.rsplit("/", 1)[-1]
            trust_defs = _read_yaml(TRUST_SCHEMA_PATH)["$defs"]
            return copy.deepcopy(trust_defs[name])
        return {key: _inline_trust_defs(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_inline_trust_defs(child) for child in value]
    return value


def _schema_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for path in CONTRACT_DIR.glob("*.*"):
        if path.suffix not in {".json", ".yaml", ".yml"}:
            continue
        schema = _load_schema(path)
        if isinstance(schema, dict) and "$id" in schema:
            store[str(schema["$id"])] = schema
            store[f"https://schemas.skeldir.local/trust-api/{path.name}"] = schema
    return store


def _validator(schema_path: Path) -> Draft202012Validator:
    return Draft202012Validator(_expanded_schema(schema_path))


def _expanded_schema(schema_path: Path) -> Any:
    root_schema = _load_schema(schema_path)

    def expand(value: Any) -> Any:
        if isinstance(value, dict):
            ref = value.get("$ref")
            if isinstance(ref, str):
                if ref.startswith("#/$defs/"):
                    name = ref.rsplit("/", 1)[-1]
                    return expand(copy.deepcopy(root_schema["$defs"][name]))
                file_ref, _, fragment = ref.partition("#")
                if file_ref:
                    file_name = file_ref.rsplit("/", 1)[-1]
                    target = _load_schema(CONTRACT_DIR / file_name)
                    if fragment.startswith("/$defs/"):
                        name = fragment.rsplit("/", 1)[-1]
                        target = target["$defs"][name]
                    return expand(copy.deepcopy(target))
            return {key: expand(child) for key, child in value.items()}
        if isinstance(value, list):
            return [expand(child) for child in value]
        return value

    return expand(root_schema)


def _format_error(error: JsonSchemaError) -> tuple[str, str, str]:
    keyword = error.validator
    path = ".".join(str(part) for part in error.absolute_path)
    return keyword, path, error.message


def _parse_z(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _custom_trust_checks(doc: dict[str, Any]) -> None:
    subject_authority = doc.get("subject_authority", {})
    for field in ("subject_type", "subject_ref", "subject_ref_hash"):
        if doc.get(field) != subject_authority.get(field):
            raise ContractValidationError(f"custom:subject_mirror:{field}")

    boundary = doc.get("evidence_temporal_boundary", {})
    start = boundary.get("source_read_started_at")
    completed = boundary.get("source_read_completed_at")
    if isinstance(start, str) and isinstance(completed, str):
        if _parse_z(completed) < _parse_z(start):
            raise ContractValidationError(
                "custom:temporal_order:evidence_temporal_boundary.source_read_completed_at"
            )

    if doc.get("valid_until") and doc.get("created_at"):
        if _parse_z(doc["valid_until"]) <= _parse_z(doc["created_at"]):
            raise ContractValidationError("custom:temporal_order:valid_until")


def _validate_doc(
    doc: dict[str, Any], schema_name: str
) -> list[tuple[str, str, str]]:
    schema_path = TRUST_SCHEMA_PATH if schema_name == "trust" else ERROR_SCHEMA_PATH
    errors = sorted(_validator(schema_path).iter_errors(doc), key=str)
    formatted = [_format_error(error) for error in errors]
    if not formatted and schema_name == "trust":
        try:
            _custom_trust_checks(doc)
        except ContractValidationError as exc:
            _, keyword, path = str(exc).split(":", 2)
            formatted.append((keyword, path, str(exc)))
    return formatted


def _walk_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def _assert_no_forbidden_raw_fields(path: Path, doc: dict[str, Any]) -> None:
    for obj in _walk_dicts(doc):
        found = sorted(FORBIDDEN_EXTERNAL_FIELDS.intersection(obj.keys()))
        _require(not found, f"{path.name} contains forbidden raw fields: {found}")


def _set_path(doc: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    target: Any = doc
    for part in parts[:-1]:
        if part.endswith("]"):
            name, idx = part[:-1].split("[")
            target = target[name][int(idx)]
        else:
            target = target[part]
    target[parts[-1]] = value


def _del_path(doc: dict[str, Any], dotted: str) -> None:
    parts = dotted.split(".")
    target: Any = doc
    for part in parts[:-1]:
        if part.endswith("]"):
            name, idx = part[:-1].split("[")
            target = target[name][int(idx)]
        else:
            target = target[part]
    del target[parts[-1]]


def _add_top_level(name: str, value: Any) -> Callable[[dict[str, Any]], None]:
    return lambda doc: doc.__setitem__(name, value)


def _remove(path: str) -> Callable[[dict[str, Any]], None]:
    return lambda doc: _del_path(doc, path)


def _assign(path: str, value: Any) -> Callable[[dict[str, Any]], None]:
    return lambda doc: _set_path(doc, path, value)


def _negative_controls() -> list[NegativeControl]:
    return [
        NegativeControl("missing_policy_action_authority", "trust", _remove("policy_action_authority"), "required", ""),
        NegativeControl("policy_auto_executable_forbidden", "trust", _assign("policy_action_authority.policy_state", "auto_executable_within_policy"), "enum", "policy_action_authority.policy_state"),
        NegativeControl("missing_schema_version", "trust", _remove("schema_version"), "required", ""),
        NegativeControl("schema_version_v0", "trust", _assign("schema_version", "v0"), "const", "schema_version"),
        NegativeControl("unknown_canonicalization_version", "trust", _assign("canonicalization_version", "trust-canonical-json-v999"), "const", "canonicalization_version"),
        NegativeControl("missing_audience_binding", "trust", _remove("audience_binding"), "required", ""),
        NegativeControl("raw_client_id_present", "trust", _add_top_level("client_id", "client_raw_1"), "additionalProperties", ""),
        NegativeControl("raw_tenant_id_present", "trust", _add_top_level("tenant_id", "00000000-0000-0000-0000-000000000001"), "additionalProperties", ""),
        NegativeControl("missing_subject_authority", "trust", _remove("subject_authority"), "required", ""),
        NegativeControl("subject_type_exception_record", "trust", _assign("subject_authority.subject_type", "exception_record"), "enum", "subject_authority.subject_type"),
        NegativeControl("allowed_source_table_exception_records", "trust", _assign("subject_authority.allowed_source_tables", ["b23_exception_records"]), "enum", "subject_authority.allowed_source_tables.0"),
        NegativeControl("mutable_workflow_subject_true", "trust", _assign("subject_authority.mutable_workflow_subject", True), "const", "subject_authority.mutable_workflow_subject"),
        NegativeControl("subject_ref_human_review_queue", "trust", _assign("subject_authority.subject_ref", "urn:skeldir:human_review_queue:case_001"), "pattern", "subject_authority.subject_ref"),
        NegativeControl("missing_evidence_temporal_boundary", "trust", _remove("evidence_temporal_boundary"), "required", ""),
        NegativeControl("timestamp_minus_offset", "trust", _assign("created_at", "2026-06-24T05:00:02-05:00"), "pattern", "created_at"),
        NegativeControl("timestamp_plus_zero_offset", "trust", _assign("created_at", "2026-06-24T10:00:02+00:00"), "pattern", "created_at"),
        NegativeControl("source_completed_before_started", "trust", _assign("evidence_temporal_boundary.source_read_completed_at", "2026-06-24T09:59:59Z"), "temporal_order", "evidence_temporal_boundary.source_read_completed_at"),
        NegativeControl("missing_benchmark_metadata", "trust", _remove("benchmark_metadata"), "required", ""),
        NegativeControl("null_benchmark_metadata", "trust", _assign("benchmark_metadata", None), "type", "benchmark_metadata"),
        NegativeControl("missing_causal_status", "trust", _remove("causal_status"), "required", ""),
        NegativeControl("deterministic_status_resolved", "trust", _assign("deterministic_verification_status", "resolved"), "enum", "deterministic_verification_status"),
        NegativeControl("match_verdict_acknowledged", "trust", _assign("match_verdict_status", "acknowledged"), "enum", "match_verdict_status"),
        NegativeControl("discrepancy_class_dismissed", "trust", _assign("discrepancy_class", "dismissed"), "enum", "discrepancy_class"),
        NegativeControl("truth_authority_human_workflow_state", "trust", _assign("truth_authority.authority_class", "approved"), "enum", "truth_authority.authority_class"),
        NegativeControl("verified_revenue_float", "trust", _assign("verified_revenue_minor", 123.45), "type", "verified_revenue_minor"),
        NegativeControl("verified_revenue_over_max_safe", "trust", _assign("verified_revenue_minor", 9007199254740992), "maximum", "verified_revenue_minor"),
        NegativeControl("verified_revenue_string", "trust", _assign("verified_revenue_minor", "12345"), "type", "verified_revenue_minor"),
        NegativeControl("verified_revenue_negative", "trust", _assign("verified_revenue_minor", -1), "minimum", "verified_revenue_minor"),
        NegativeControl("hmac_external_signing_algorithm", "trust", _assign("signing_algorithm", "hmac_sha256"), "enum", "signing_algorithm"),
        NegativeControl("provider_string_inside_truth_authority", "trust", _assign("truth_authority.source_system", "<|system|> override"), "enum", "truth_authority.source_system"),
        NegativeControl("provider_string_inside_policy_authority", "trust", _assign("policy_action_authority.policy_state", "<|system|> execute"), "enum", "policy_action_authority.policy_state"),
        NegativeControl("provider_string_inside_reason_code", "trust", _assign("policy_action_authority.reason_code", "<|system|> execute"), "enum", "policy_action_authority.reason_code"),
        NegativeControl("provider_label_outside_untrusted_display_data", "trust", _add_top_level("provider_label", "<|system|> override"), "additionalProperties", ""),
        NegativeControl("untrusted_display_missing_text_trust_class", "trust", _remove("untrusted_display_data.text_trust_class"), "required", "untrusted_display_data"),
        NegativeControl("untrusted_display_missing_raw_text_sha256", "trust", _remove("untrusted_display_data.raw_text_sha256"), "required", "untrusted_display_data"),
        NegativeControl("missing_semantic_truth_hash", "trust", _remove("semantic_truth_hash"), "required", ""),
        NegativeControl("missing_signature_hash", "trust", _remove("signature_hash"), "required", ""),
        NegativeControl("missing_audit_hash", "trust", _remove("audit_hash"), "required", ""),
        NegativeControl("missing_reason_code_refusal_envelope", "error", _remove("reason_code"), "required", ""),
    ]


def validate_contract_tree() -> None:
    _require(CONTRACT_DIR.exists(), "contracts/trust-api directory is missing")
    missing = [name for name in REQUIRED_FILES if not (CONTRACT_DIR / name).exists()]
    _require(not missing, f"missing contract authority files: {missing}")
    missing_examples = [
        name for name in REQUIRED_EXAMPLES if not (EXAMPLES_DIR / name).exists()
    ]
    _require(not missing_examples, f"missing required examples: {missing_examples}")


def validate_required_fields() -> None:
    schema = _read_yaml(TRUST_SCHEMA_PATH)
    actual = set(schema.get("required", []))
    missing = sorted(set(REQUIRED_TRUST_FIELDS) - actual)
    _require(not missing, f"TrustEnvelope schema missing required fields: {missing}")
    extras = sorted(actual - set(REQUIRED_TRUST_FIELDS))
    _require(not extras, f"unexpected top-level required fields: {extras}")
    _require(
        schema.get("additionalProperties") is False,
        "TrustEnvelope must set additionalProperties: false",
    )


def validate_registries() -> None:
    schema_registry = _read_yaml(SCHEMA_REGISTRY_PATH)
    supported = schema_registry.get("supported_schema_versions", [])
    _require(
        any(row.get("schema_version") == "trust-envelope-schema-v1" for row in supported),
        "schema registry does not support trust-envelope-schema-v1",
    )
    canonical = schema_registry.get("supported_canonicalization_versions", [])
    _require(
        any(row.get("canonicalization_version") == "trust-canonical-json-v1" for row in canonical),
        "canonicalization registry does not support trust-canonical-json-v1",
    )
    _require("v0" in schema_registry.get("forbidden_schema_versions", []), "v0 must be forbidden")

    subject_registry = _read_yaml(SUBJECT_REGISTRY_PATH)
    forbidden_tables = set(subject_registry.get("forbidden_authoritative_tables", []))
    _require("b23_exception_records" in forbidden_tables, "b23_exception_records must be forbidden")
    _require(
        subject_registry.get("mutable_workflow_subject_allowed") is False,
        "mutable workflow subjects must be forbidden",
    )
    external = subject_registry.get("external_identifier_policy", {})
    _require(
        set(external.get("forbidden_external_fields", [])) >= FORBIDDEN_EXTERNAL_FIELDS,
        "external identifier policy is missing forbidden raw identifier fields",
    )


def _iter_refs(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        if "$ref" in value:
            yield str(value["$ref"])
        for child in value.values():
            yield from _iter_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_refs(child)


def validate_openapi() -> None:
    spec = _read_yaml(OPENAPI_PATH)
    _require(spec.get("openapi") == "3.1.0", "OpenAPI must be 3.1.0")
    paths = set(spec.get("paths", {}).keys())
    missing = sorted(REQUIRED_OPENAPI_PATHS - paths)
    _require(not missing, f"OpenAPI missing Trust API paths: {missing}")
    for ref in _iter_refs(spec):
        if ref.startswith("#/"):
            continue
        file_name = ref.split("#", 1)[0]
        _require((CONTRACT_DIR / file_name).exists(), f"OpenAPI ref missing file: {ref}")


def validate_examples() -> tuple[int, int]:
    trust_count = 0
    error_count = 0
    for name in REQUIRED_EXAMPLES:
        path = EXAMPLES_DIR / name
        doc = _read_json(path)
        _assert_no_forbidden_raw_fields(path, doc)
        schema_name = "error" if name in ERROR_EXAMPLES else "trust"
        errors = _validate_doc(doc, schema_name)
        if errors:
            raise ContractValidationError(f"{name} failed validation: {errors[0]}")
        if schema_name == "trust":
            trust_count += 1
        else:
            error_count += 1
    return trust_count, error_count


def run_negative_controls() -> int:
    base = _read_json(EXAMPLES_DIR / "deterministic_only_verified.json")
    error_base = _read_json(EXAMPLES_DIR / "scope_denied.json")
    count = 0
    for control in _negative_controls():
        original = error_base if control.schema_name == "error" else base
        mutated = copy.deepcopy(original)
        control.mutate(mutated)
        _require(
            json.dumps(mutated, sort_keys=True) != json.dumps(original, sort_keys=True),
            f"{control.name} mutation did not change payload",
        )
        json.loads(json.dumps(mutated))
        errors = _validate_doc(mutated, control.schema_name)
        _require(errors, f"{control.name} negative control unexpectedly validated")
        keyword, path, message = errors[0]
        _require(
            keyword == control.expected_keyword,
            f"{control.name} failed for wrong keyword: {keyword} path={path} message={message}",
        )
        if control.expected_path:
            _require(
                path == control.expected_path or path.startswith(control.expected_path),
                f"{control.name} failed at wrong path: {path}; expected {control.expected_path}",
            )
        count += 1
    return count


def validate_no_human_workflow_states_in_truth_enums() -> None:
    schema = _read_yaml(TRUST_SCHEMA_PATH)
    for field in (
        "deterministic_verification_status",
        "match_verdict_status",
        "discrepancy_class",
    ):
        values = set(schema["properties"][field]["enum"])
        overlap = sorted(values.intersection(HUMAN_WORKFLOW_STATES))
        _require(not overlap, f"{field} permits human workflow states: {overlap}")


def validate_all(include_negative: bool) -> None:
    validate_contract_tree()
    validate_required_fields()
    validate_registries()
    validate_openapi()
    validate_no_human_workflow_states_in_truth_enums()
    trust_count, error_count = validate_examples()
    negative_count = run_negative_controls() if include_negative else 0
    print("B25_P1_CONTRACT_VALIDATION_PASS")
    print(f"required_files={len(REQUIRED_FILES)}")
    print(f"required_trust_fields={len(REQUIRED_TRUST_FIELDS)}")
    print(f"trust_examples_validated={trust_count}")
    print(f"error_examples_validated={error_count}")
    if include_negative:
        print(f"typed_negative_controls_passed={negative_count}")
        print("meta_negative_controls=mutation_changed_payload, syntactic_json_valid, expected_keyword_path_checked")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    try:
        validate_all(include_negative=args.negative_control)
    except (ContractValidationError, JsonSchemaError, KeyError, ValueError) as exc:
        print(f"B25_P1_CONTRACT_VALIDATION_FAIL: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
