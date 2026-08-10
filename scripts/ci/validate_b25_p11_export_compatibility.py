#!/usr/bin/env python3
"""Validate B2.5-P11 export compatibility and trust-authority separation."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = (
    ROOT / "backend",
    ROOT / "scripts",
    ROOT / "contracts",
    ROOT / "api-contracts",
)
SHADOW_ROOT_NAMES = frozenset({".tmp", "tmp", ".tmp_audit", "graphify-out"})

TRUST_EXPORT = Path("backend/app/api/trust_export.py")
LEGACY_EXPORT = Path("backend/app/api/export.py")
ARTIFACT = Path("backend/app/trust/export_artifact.py")
PROJECTION = Path("backend/app/trust/export_projection.py")
SPREADSHEET = Path("backend/app/trust/spreadsheet_safety.py")
ARTIFACT_SCHEMA = Path("contracts/trust-api/export-artifact.v1.yaml")
DISPLAY_SCHEMA = Path("contracts/trust-api/export-projection.schema.json")
HASH_MANIFEST = Path("contracts/trust-api/hash-domain-manifest.v1.yaml")
TRUST_OPENAPI = Path("contracts/trust-api/trust-api.openapi.yaml")
EXPORT_CONTRACTS = (
    Path("api-contracts/openapi/v1/export.yaml"),
    Path("contracts/export/v1/export.yaml"),
    Path("contracts/export/baselines/v1.0.0/export.yaml"),
    Path("api-contracts/dist/openapi/v1/export.bundled.yaml"),
)
MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202608081200_b25_p11_export_scope.py"
)
EVIDENCE_PATH = Path("docs/forensics/B2.5-P11 Remediation Evidence Pack.md")
CORRECTIVE_EVIDENCE_PATH = Path(
    "docs/forensics/B2.5-P11 Corrective Remediation Evidence Pack.md"
)
CSV_EVOLUTION_POLICY = Path("contracts/export/CSV_EVOLUTION.md")
ERROR_MODEL_CHECKER = Path("scripts/contracts/check_error_model.py")
ERROR_COMPONENT_REGISTRY = Path(
    "api-contracts/openapi/v1/_common/error-component-registry.yaml"
)
P11_PROJECTION_TESTS = Path("backend/tests/trust/test_b25_p11_export_projection.py")
P7_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202607011200_b25_p7_trust_audit_provenance.py"
)
P7_AUDIT = Path("backend/app/trust/audit.py")
P11_WORKFLOW = Path(".github/workflows/b2_5-p11-export-compatibility.yml")
VALID_ARTIFACT_EXAMPLE = Path(
    "contracts/trust-api/examples/export_artifact_signed_valid.json"
)
DISPLAY_EXAMPLE = Path(
    "contracts/trust-api/examples/export_display_non_authoritative.json"
)


class B25P11ValidationError(RuntimeError):
    """Raised when a P11 invariant is absent or vacuous."""


def _text(path: Path, overrides: dict[Path, str]) -> str:
    if path in overrides:
        return overrides[path]
    return (ROOT / path).read_text(encoding="utf-8")


def _parsed(path: Path, overrides: dict[Path, str]) -> Any:
    content = _text(path, overrides)
    if path.suffix == ".json":
        return json.loads(content)
    return yaml.safe_load(content)


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise B25P11ValidationError(reason)


def _dict_literal_keys(source: str) -> set[str]:
    keys: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Dict):
            continue
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.add(key.value)
    return keys


def _validate_no_post_signature_mutation(source: str) -> None:
    tree = ast.parse(source)
    functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "sign_export_artifact"
    ]
    _require(len(functions) == 1, "artifact_signer_function_missing")
    signature_line = None
    forbidden_lines: list[int] = []
    for node in ast.walk(functions[0]):
        if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if not isinstance(target, ast.Subscript):
                continue
            if not isinstance(target.value, ast.Name) or target.value.id != "signed":
                continue
            key = target.slice
            if isinstance(key, ast.Constant) and key.value == "signature":
                signature_line = node.lineno
            elif signature_line is not None and node.lineno > signature_line:
                forbidden_lines.append(node.lineno)
    _require(signature_line is not None, "artifact_signature_assignment_missing")
    _require(not forbidden_lines, "post_signature_authoritative_mutation")


def _validate_csv_header_first(source: str) -> None:
    tree = ast.parse(source)
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_csv_from_rows"
    ]
    _require(len(functions) == 1, "csv_serializer_function_missing")
    calls = [
        node
        for node in ast.walk(functions[0])
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "writerow"
    ]
    calls.sort(key=lambda node: node.lineno)
    _require(bool(calls), "csv_writerow_missing")
    first_argument = calls[0].args[0] if calls[0].args else None
    _require(
        isinstance(first_argument, ast.Name) and first_argument.id == "CSV_COLUMNS",
        "csv_header_not_first_record",
    )


def _validate_schema_and_manifest(overrides: dict[Path, str]) -> None:
    artifact_schema = _parsed(ARTIFACT_SCHEMA, overrides)
    display_schema = _parsed(DISPLAY_SCHEMA, overrides)
    manifest = _parsed(HASH_MANIFEST, overrides)
    _require(
        artifact_schema.get("additionalProperties") is False, "artifact_schema_open"
    )
    _require(display_schema.get("additionalProperties") is False, "display_schema_open")
    artifact_properties = set(artifact_schema.get("properties", {}))
    artifact_required = set(artifact_schema.get("required", []))
    _require(
        artifact_properties == artifact_required, "artifact_schema_not_fully_required"
    )
    declared = {
        row["field_path"] for row in manifest.get("export_artifact_field_domains", [])
    }
    _require(declared == artifact_properties, "export_artifact_hash_manifest_drift")
    _require(
        manifest.get("export_artifact_hash_input_fields")
        == [
            "artifact_schema_version",
            "canonicalization_version",
            "artifact_signing_domain",
            "generated_at",
            "tenant_id_hash",
            "envelope_count",
            "envelopes[]",
        ],
        "artifact_hash_input_manifest_drift",
    )
    registry_rows = manifest.get("export_artifact_protocol_registry") or []
    _require(bool(registry_rows), "artifact_protocol_registry_missing")
    registry_tuples = [
        (row.get("artifact_schema_version"), row.get("canonicalization_version"))
        for row in registry_rows
    ]
    _require(
        len(registry_tuples) == len(set(registry_tuples)),
        "artifact_protocol_registry_ambiguous",
    )
    _require(
        ("b25-p11-export-artifact-v1", "b25-p11-artifact-framing-v1")
        in registry_tuples,
        "historical_artifact_protocol_unregistered",
    )
    _require(
        ("b25-p11-export-artifact-v2", "b25-p11-artifact-framing-v2")
        in registry_tuples,
        "active_artifact_protocol_unregistered",
    )
    statuses = {
        row["artifact_schema_version"]: row.get("support_status")
        for row in registry_rows
    }
    _require(
        statuses.get("b25-p11-export-artifact-v1") == "verification_only",
        "historical_artifact_protocol_status_drift",
    )
    _require(
        statuses.get("b25-p11-export-artifact-v2") == "active",
        "active_artifact_protocol_status_drift",
    )
    _require(
        manifest.get("export_artifact_schema_version") == "b25-p11-export-artifact-v2",
        "manifest_active_artifact_version_drift",
    )
    _require(
        manifest.get("export_artifact_signature_hash_input_fields")
        == [
            "artifact_signing_domain",
            "artifact_hash",
            "signing_key_id",
            "signing_algorithm",
        ],
        "signature_hash_input_manifest_drift",
    )
    _require(
        artifact_schema["properties"]["envelopes"].get("maxItems") == 2,
        "artifact_envelope_ceiling_drift",
    )
    _require(
        "envelopes" in artifact_required,
        "signed_envelope_embedding_removed",
    )
    row_properties = display_schema["properties"]["rows"]["items"]["properties"]
    _require(
        row_properties["revenue_minor"].get("type") == "integer", "float_money_schema"
    )
    _require(
        row_properties["revenue_display"].get("type") == "string",
        "revenue_display_not_string",
    )
    _require(
        row_properties["confidence_display"].get("type") == "string",
        "confidence_display_not_string",
    )
    _require(
        display_schema["properties"]["projection_authority"].get("const")
        == "non_authoritative_display",
        "projection_authority_schema_missing",
    )
    serialized = json.dumps(display_schema, sort_keys=True)
    _require('"type": "number"' not in serialized, "display_float_schema_present")
    registry = Registry()
    schema_root = ROOT / "contracts/trust-api"
    for schema_path in (*schema_root.glob("*.yaml"), *schema_root.glob("*.json")):
        relative = schema_path.relative_to(ROOT)
        candidate_schema = _parsed(relative, overrides)
        if not isinstance(candidate_schema, dict):
            continue
        if "$id" not in candidate_schema or "$schema" not in candidate_schema:
            continue
        registry = registry.with_resource(
            candidate_schema["$id"], Resource.from_contents(candidate_schema)
        )
    artifact_errors = list(
        Draft202012Validator(artifact_schema, registry=registry).iter_errors(
            _parsed(VALID_ARTIFACT_EXAMPLE, overrides)
        )
    )
    _require(
        not artifact_errors,
        (
            f"valid_artifact_example_schema_failure:{artifact_errors[0].message}"
            if artifact_errors
            else "valid_artifact_example_schema_failure"
        ),
    )
    display_errors = list(
        Draft202012Validator(display_schema).iter_errors(
            _parsed(DISPLAY_EXAMPLE, overrides)
        )
    )
    _require(
        not display_errors,
        (
            f"display_example_schema_failure:{display_errors[0].message}"
            if display_errors
            else "display_example_schema_failure"
        ),
    )


def _validate_contracts(overrides: dict[Path, str]) -> None:
    trust_contract = _parsed(TRUST_OPENAPI, overrides)
    operation = trust_contract["paths"]["/api/trust/v1/exports/match-verdicts"]["post"]
    _require(
        operation.get("operationId") == "createMatchVerdictExportArtifact",
        "trust_export_operation_id_missing",
    )
    _require(operation.get("x-max-request-body-bytes") == 65_536, "body_ceiling_drift")
    _require(operation.get("x-max-accepted-subject-refs") == 50, "ref_ceiling_drift")
    _require(
        operation.get("x-max-evaluated-references") == 2, "evaluation_ceiling_drift"
    )
    _require(
        operation.get("x-max-artifact-bytes") == 1_048_576, "artifact_ceiling_drift"
    )
    for path in EXPORT_CONTRACTS:
        source = _text(path, overrides)
        _require("tenant_id_hash" in source, f"contract_tenant_hash_missing:{path}")
        _require(
            "raw tenant_id" in source, f"tenant_id_prohibition_comment_missing:{path}"
        )
        _require(
            "non_authoritative_display" in source, f"display_authority_missing:{path}"
        )
        _require("revenue_minor" in source, f"minor_money_missing:{path}")
        _require("confidence_display" in source, f"confidence_display_missing:{path}")
    public_contract = _parsed(Path("api-contracts/openapi/v1/export.yaml"), overrides)
    _require(public_contract["info"]["version"] == "5.0.0", "csv_major_version_missing")
    for path in (
        "/api/export/revenue",
        "/api/export/csv",
        "/api/export/json",
        "/api/export/excel",
    ):
        _require(
            "503" in public_contract["paths"][path]["get"]["responses"],
            f"export_503_contract_missing:{path}",
        )
    # --- Runtime / contract parity for governed refusals (Gate P11-C3-I) ----
    # Every deliberate, stable, consumer-programmable refusal the runtime can
    # emit must be representable in the authoritative contract.
    for path in (
        "/api/export/revenue",
        "/api/export/csv",
        "/api/export/json",
        "/api/export/excel",
    ):
        _require(
            "413" in public_contract["paths"][path]["get"]["responses"],
            f"export_413_contract_missing:{path}",
        )
    for path in ("/api/export/revenue", "/api/export/csv"):
        _require(
            "410" in public_contract["paths"][path]["get"]["responses"],
            f"export_410_contract_missing:{path}",
        )
    limit_reason_enum = public_contract["components"]["schemas"]["ExportLimitError"][
        "properties"
    ]["detail"]["properties"]["reason_code"]["enum"]
    _require(
        sorted(limit_reason_enum)
        == sorted(
            [
                "legacy_export_date_span_exceeded",
                "legacy_export_channel_count_exceeded",
                "legacy_export_channel_length_exceeded",
                "legacy_export_row_admission_exceeded",
                "legacy_export_byte_admission_exceeded",
                "legacy_export_row_budget_exceeded",
                "legacy_export_byte_budget_exceeded",
            ]
        ),
        "export_413_reason_contract_drift",
    )
    # Every reason code the runtime can raise must appear in the contract enum.
    runtime_limit_reasons = {
        node.args[0].value
        for node in ast.walk(ast.parse(_text(LEGACY_EXPORT, overrides)))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "LegacyExportLimitExceeded"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    _require(
        runtime_limit_reasons.issubset(set(limit_reason_enum)),
        "export_413_runtime_reason_not_in_contract:"
        f"{sorted(runtime_limit_reasons - set(limit_reason_enum))}",
    )
    retired_schema = public_contract["components"]["schemas"][
        "ExportProfileRetiredError"
    ]["properties"]["detail"]["properties"]
    _require(
        retired_schema["reason_code"].get("const") == "legacy_csv_profile_retired",
        "export_410_reason_contract_drift",
    )
    reason_enum = public_contract["components"]["schemas"]["ExportDeadlineError"][
        "properties"
    ]["detail"]["properties"]["reason_code"]["enum"]
    _require(
        reason_enum
        == [
            "legacy_export_database_deadline_exceeded",
            "legacy_export_handler_deadline_exceeded",
        ],
        "export_503_reason_contract_drift",
    )
    _require(
        public_contract["components"]["responses"]["ExportDeadlineExceeded"].get(
            "x-skeldir-shared-error-component"
        )
        == "skeldir.export.ExportDeadlineExceeded",
        "export_503_shared_error_provenance_missing",
    )
    baseline = _parsed(Path("contracts/export/baselines/v1.0.0/export.yaml"), overrides)
    baseline_csv = baseline["paths"]["/api/export/revenue"]["get"]["responses"]["200"][
        "content"
    ]["text/csv"]["examples"]["csv_export"]["value"]
    _require(baseline["info"]["version"] == "2.0.0", "historical_baseline_rewritten")
    _require(
        baseline_csv.startswith("date,channel,revenue,conversions,confidence\r\n"),
        "historical_csv_baseline_rewritten",
    )
    current = _parsed(Path("contracts/export/v1/export.yaml"), overrides)
    _require(current["info"]["version"] == "4.0.0", "csv_contract_major_missing")
    _require(
        'text/csv; profile="https://api.skeldir.com/profiles/export-csv-v2"'
        in current["paths"]["/api/export/revenue"]["get"]["responses"]["200"][
            "content"
        ],
        "enriched_csv_profile_missing",
    )
    policy = _text(CSV_EVOLUTION_POLICY, overrides)
    _require("P11-G4 authority honesty" in policy, "csv_evolution_policy_missing")

    # --- Shared error-model provenance (Gate P11-C3-G / P11-C3-H) -----------
    # The repository-wide checker must establish provenance mechanically. A
    # self-asserted boolean, or any unconditional bypass, is a global
    # regression that this phase must not reintroduce.
    checker = _text(ERROR_MODEL_CHECKER, overrides)
    _require(
        "verify_declared_provenance" in checker,
        "error_model_provenance_verification_missing",
    )
    _require(
        "is True:\n        return True" not in checker,
        "error_model_self_attested_boolean_restored",
    )
    _require(
        "return True, 'self_attested'" not in checker
        and 'return True, "self_attested"' not in checker,
        "error_model_self_attested_boolean_restored",
    )
    _require(
        "return True, 'bypassed'" not in checker
        and 'return True, "bypassed"' not in checker,
        "error_model_unconditional_bypass_present",
    )
    _require(
        "        return False, reason" in checker,
        "error_model_failed_declaration_not_fatal",
    )
    registry_doc = _parsed(ERROR_COMPONENT_REGISTRY, overrides)
    registry_entries = registry_doc.get("components") or []
    _require(bool(registry_entries), "error_component_registry_empty")
    registry_ids = {row.get("component_id") for row in registry_entries}
    for required_component in (
        "skeldir.export.ExportDeadlineExceeded",
        "skeldir.export.ExportLimitExceeded",
        "skeldir.export.ExportProfileRetired",
    ):
        _require(
            required_component in registry_ids,
            f"error_component_unregistered:{required_component}",
        )
    for row in registry_entries:
        if row.get("structural_rule") == "exact_fingerprint":
            fingerprint = row.get("schema_fingerprint")
            _require(
                isinstance(fingerprint, str) and fingerprint.startswith("sha256:"),
                f"error_component_fingerprint_missing:{row.get('component_id')}",
            )


def _validate_sources(overrides: dict[Path, str]) -> None:
    trust_export = _text(TRUST_EXPORT, overrides)
    legacy = _text(LEGACY_EXPORT, overrides)
    artifact = _text(ARTIFACT, overrides)
    projection = _text(PROJECTION, overrides)
    spreadsheet = _text(SPREADSHEET, overrides)
    for name, source in (("trust_export", trust_export), ("export_artifact", artifact)):
        upper = source.upper()
        for forbidden in ("ATTRIBUTION_ALLOCATIONS", "SUM(", "AVG(", "COUNT("):
            _require(
                forbidden not in upper,
                f"authoritative_aggregation_reachable:{name}:{forbidden}",
            )
    for source in (trust_export, artifact, projection):
        _require(
            "tenant_id" not in _dict_literal_keys(source), "raw_tenant_key_emitted"
        )
    for source in (trust_export, artifact):
        for forbidden in (
            "app.llm",
            "app.tasks",
            "app.bayesian",
            "celery",
            "apply_async(",
            ".delay(",
        ):
            _require(
                forbidden not in source, f"compute_or_llm_path_present:{forbidden}"
            )
    _require(
        'SUPPORTED_EXPORT_SUBJECT_TYPES = frozenset({"match_verdict"})' in trust_export,
        "reserved_export_subject_activated",
    )
    _require(
        "subject_refs=export_request.subject_refs" in trust_export
        and "row_limit=accepted_count" in trust_export,
        "atomic_preflight_full_set_missing",
    )
    _require(
        "for page_offset, subject_ref in enumerate(page_refs)" in trust_export,
        "whole_request_envelope_build_reachable",
    )
    _require(
        "resolve_authoritative_money(" in trust_export,
        "atomic_preflight_exportability_missing",
    )
    for token in (
        "MAX_EXPORT_BODY_BYTES = 65_536",
        "MAX_ACCEPTED_EXPORT_REFS = 50",
        "MAX_EVALUATED_EXPORT_REFS = 2",
        "MAX_SIGNED_EXPORT_ENVELOPES = 2",
        "MAX_EXPORT_ARTIFACT_BYTES = 1_048_576",
        "MAX_CONCURRENT_EXPORT_EXECUTIONS = 2",
        "EXPORT_HANDLER_DEADLINE_SECONDS = 1.5",
        "asyncio.Semaphore",
        "asyncio.timeout",
        "access_log_only=False",
    ):
        _require(token in trust_export, f"trust_export_control_missing:{token}")
    _require("compute_artifact_hash(" in artifact, "p2_artifact_hash_authority_missing")
    _require(
        'signed["signature_hash"] = compute_detached_signature_hash(signature_material)'
        in artifact,
        "artifact_signature_hash_authority_missing",
    )
    _require(
        'candidate["signature_hash"] != expected_signature_hash' in artifact,
        "artifact_signature_hash_verify_removed",
    )
    _require(
        'signed["signature_hash"] = signed["artifact_hash"]' not in artifact,
        "artifact_signature_hash_collapsed",
    )
    _require("hashlib" not in artifact, "local_artifact_hash_authority_present")
    _require("json.dumps" not in artifact, "local_json_identity_present")
    _require(
        'EXPORT_ARTIFACT_SIGNING_DOMAIN_V2 = b"skeldir:b25-p11:export-artifact:v2\\x00"'
        in artifact,
        "artifact_signing_domain_drift",
    )
    _require(
        'EXPORT_ARTIFACT_SIGNING_DOMAIN_V1 = b"skeldir:b25-p11:export-artifact:v1\\x00"'
        in artifact,
        "historical_artifact_signing_domain_removed",
    )
    # Protocol identity must remain a function: one version tuple, one algorithm.
    _require(
        "def _artifact_identity_bytes_v1(" in artifact,
        "historical_artifact_framing_removed",
    )
    _require(
        "def _artifact_identity_bytes_v2(" in artifact,
        "active_artifact_framing_missing",
    )
    _require(
        "def resolve_export_artifact_protocol(" in artifact,
        "artifact_protocol_dispatch_missing",
    )
    _require(
        "artifact_protocol_version_unsupported" in artifact,
        "artifact_protocol_reason_code_missing",
    )
    _require(
        "issuable=False" in artifact and "issuable=True" in artifact,
        "artifact_protocol_issuance_status_missing",
    )
    # Each registered protocol must actually BIND its own framing. Declaring the
    # functions but pointing both entries at one algorithm would silently
    # reinterpret historical artifacts while leaving the source looking correct.
    _require(
        "identity_bytes=_artifact_identity_bytes_v1," in artifact,
        "historical_artifact_protocol_binding_collapsed",
    )
    _require(
        "identity_bytes=_artifact_identity_bytes_v2," in artifact,
        "active_artifact_protocol_binding_collapsed",
    )
    _require(
        "signature_material=_export_artifact_signature_material_v1," in artifact,
        "historical_signature_material_binding_collapsed",
    )
    _require(
        "signature_material=_export_artifact_signature_material_v2," in artifact,
        "active_signature_material_binding_collapsed",
    )
    # Cross-check the runtime protocol constants against the manifest registry.
    # Mislabelling the new algorithm with an old version marker must fail here
    # rather than silently producing two meanings for one version tuple.
    artifact_constants: dict[str, str] = {}
    for node in ast.walk(ast.parse(artifact)):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(node.value.value, str):
                    artifact_constants[target.id] = node.value.value
    manifest_registry = {
        (row.get("artifact_schema_version"), row.get("canonicalization_version"))
        for row in (
            _parsed(HASH_MANIFEST, overrides).get("export_artifact_protocol_registry")
            or []
        )
    }
    for schema_const, canon_const in (
        (
            "EXPORT_ARTIFACT_SCHEMA_VERSION_V1",
            "EXPORT_ARTIFACT_CANONICALIZATION_VERSION_V1",
        ),
        (
            "EXPORT_ARTIFACT_SCHEMA_VERSION_V2",
            "EXPORT_ARTIFACT_CANONICALIZATION_VERSION_V2",
        ),
    ):
        runtime_tuple = (
            artifact_constants.get(schema_const),
            artifact_constants.get(canon_const),
        )
        _require(
            runtime_tuple in manifest_registry,
            f"artifact_protocol_runtime_manifest_drift:{runtime_tuple}",
        )
    _require(
        artifact_constants.get("EXPORT_ARTIFACT_SCHEMA_VERSION_V1")
        != artifact_constants.get("EXPORT_ARTIFACT_SCHEMA_VERSION_V2"),
        "artifact_protocol_version_markers_collided",
    )
    _require(
        artifact_constants.get("EXPORT_ARTIFACT_CANONICALIZATION_VERSION_V1")
        != artifact_constants.get("EXPORT_ARTIFACT_CANONICALIZATION_VERSION_V2"),
        "artifact_canonicalization_version_markers_collided",
    )
    _require(
        'candidate["artifact_hash"] != expected_hash' in artifact,
        "artifact_hash_verify_removed",
    )
    # ACTIVE (v2) identity must stay signer-independent so key rotation cannot
    # change artifact_hash. The frozen v1 framing legitimately includes signer
    # fields and is asserted separately below.
    identity_body = artifact.split("def _artifact_identity_bytes_v2", 1)[1].split(
        "def _export_artifact_signature_material_v2", 1
    )[0]
    _require("signing_key_id" not in identity_body, "signer_metadata_in_artifact_hash")
    _require(
        "signing_algorithm" not in identity_body, "signer_metadata_in_artifact_hash"
    )
    # The frozen historical framing must keep its original semantics; silently
    # rewriting it would reinterpret already-issued artifacts.
    historical_body = artifact.split("def _artifact_identity_bytes_v1", 1)[1].split(
        "def _export_artifact_signature_material_v1", 1
    )[0]
    _require(
        '_frame(\n            "signing_key_id"' in historical_body
        or '_frame("signing_key_id"' in historical_body,
        "historical_artifact_framing_semantics_changed",
    )
    signature_body = artifact.split("def _export_artifact_signature_material_v2", 1)[
        1
    ].split("@dataclass", 1)[0]
    _require(
        '_frame("artifact_hash"' in signature_body
        and '_frame("signing_key_id"' in signature_body
        and '_frame("signing_algorithm"' in signature_body,
        "signature_key_binding_incomplete",
    )
    _require('"envelopes": ordered' in artifact, "signed_envelope_embedding_removed")
    _validate_no_post_signature_mutation(artifact)
    _require(
        'PROJECTION_AUTHORITY_NON_AUTHORITATIVE = "non_authoritative_display"'
        in projection,
        "projection_authority_runtime_missing",
    )
    _require(
        '"projection_authority": PROJECTION_AUTHORITY_NON_AUTHORITATIVE' in projection,
        "projection_marker_emission_missing",
    )
    _require(
        projection.count("neutralize_spreadsheet_cell(") >= 2,
        "spreadsheet_neutralization_removed",
    )
    _require(
        "_FORMULA_PREFIXES" in spreadsheet
        and '"\\t"' in spreadsheet
        and '"\\r"' in spreadsheet,
        "formula_prefix_set_incomplete",
    )
    _require("csv.writer(" in legacy, "rfc4180_writer_missing")
    _require(
        'CSV_SCHEMA_VERSION = "b25-p11-export-csv-v2"' in legacy,
        "csv_schema_version_missing",
    )
    _require(
        'CSV_COLUMNS = (\n    "projection_authority",\n    "projection_schema_version",'
        in legacy,
        "detached_csv_authority_missing",
    )
    _require(
        'LEGACY_CSV_COLUMNS = ("date", "channel", "revenue", "conversions", "confidence")'
        in legacy,
        "legacy_csv_positional_contract_drift",
    )
    # The default profile must preserve legacy positions AND self-identify.
    _require(
        "COMPAT_CSV_COLUMNS = LEGACY_CSV_COLUMNS + (" in legacy,
        "compat_csv_positional_prefix_missing",
    )
    _require(
        'COMPAT_CSV_SCHEMA_VERSION = "b25-p11-export-csv-compat-v1"' in legacy,
        "compat_csv_profile_missing",
    )
    _require(
        "csv_schema_version: str = COMPAT_CSV_SCHEMA_VERSION" in legacy,
        "compat_csv_not_default",
    )
    # BOTH CSV-capable route handlers must default to the compliant profile.
    # Asserting mere presence would let one handler drift while the other
    # keeps the assertion satisfied, which is exactly how a noncompliant
    # default survives alongside a compliant one.
    _require(
        legacy.count("] = Query(default=COMPAT_CSV_SCHEMA_VERSION),") == 2,
        "compat_csv_not_route_default",
    )
    _require(
        "] = Query(default=CSV_SCHEMA_VERSION)," not in legacy,
        "csv_route_default_contradicts_documented_default",
    )
    _require(
        "] = Query(default=LEGACY_CSV_SCHEMA_VERSION)," not in legacy,
        "retired_csv_profile_is_route_default",
    )
    _require(
        "def _assert_csv_profile_supported(" in legacy,
        "retired_profile_guard_missing",
    )
    _require(
        "legacy_csv_profile_retired" in legacy,
        "retired_profile_reason_code_missing",
    )
    _require(
        "def _legacy_csv_from_rows(" not in legacy,
        "ambiguous_legacy_serializer_still_reachable",
    )
    _require(
        "def _compat_csv_from_rows(" in legacy,
        "compat_csv_serializer_missing",
    )
    _require(
        "SUPPORTED_CSV_SCHEMA_VERSIONS = (COMPAT_CSV_SCHEMA_VERSION, CSV_SCHEMA_VERSION)"
        in legacy,
        "supported_csv_profile_set_drift",
    )
    _validate_csv_header_first(legacy)
    _require('",".join(' not in legacy, "manual_csv_join_present")
    _require(
        "Workbook(write_only=True)" in legacy and "workbook.save(" in legacy,
        "bounded_real_xlsx_missing",
    )
    _require("SKELDIR-MOCK-XLSX" not in legacy, "mock_xlsx_restored")
    for token in (
        "LEGACY_EXPORT_MAX_DATE_SPAN_DAYS = 31",
        "LEGACY_EXPORT_MAX_ROWS = 1_000",
        "LEGACY_EXPORT_MAX_BYTES = 1_048_576",
        "LEGACY_EXPORT_MAX_CHANNELS = 32",
        "TRACK1_MAX_CONCURRENT_EXPORTS = 2\n",
        "TRACK1_HANDLER_DEADLINE_SECONDS = 3.0",
        "TRACK1_DATABASE_STATEMENT_TIMEOUT_MS = 1_250",
        "TRACK1_DATABASE_WORK_MEM_KIB = 4_096",
        "TRACK1_MAX_SERIALIZATION_WORKING_SET_BYTES = 32 * 1_024 * 1_024",
        "_TRACK1_EXPORT_CONCURRENCY_LIMIT = asyncio.Semaphore(",
        "SET LOCAL statement_timeout",
        "SET LOCAL work_mem",
        "SET LOCAL max_parallel_workers_per_gather = 0",
        "_admit_legacy_export(",
        "LIMIT :row_limit",
        "fetchmany(LEGACY_EXPORT_MAX_ROWS + 1)",
    ):
        _require(token in legacy, f"legacy_bound_missing:{token}")
    for token in (
        "asyncio.create_task(",
        "asyncio.to_thread(serializer, serializer_input)",
        "await asyncio.shield(serializer_task)",
        "_TRACK1_RETAINED_SERIALIZER_TASKS.add(serializer_task)",
        "serializer_task.add_done_callback(release_retained_permit)",
    ):
        _require(token in legacy, f"physical_serializer_accounting_missing:{token}")
    projection_tests = _text(P11_PROJECTION_TESTS, overrides)
    _require("psutil.Process()" in projection_tests, "track1_process_rss_proof_missing")
    _require(
        "tracemalloc" not in projection_tests, "tracemalloc_substituted_for_process_rss"
    )
    _require("fetchall(" not in legacy, "fetch_all_before_budget_present")
    for token in (
        "EXPORT_ROW_ALLOWLIST",
        "_enforce_export_row_no_leak(",
        "_enforce_export_payload_no_leak(",
    ):
        _require(token in legacy, f"b14_p5_compatibility_symbol_missing:{token}")


def _validate_p7_preservation(overrides: dict[Path, str]) -> None:
    p7_migration = _text(P7_MIGRATION, overrides)
    p7_audit = _text(P7_AUDIT, overrides)
    _require("agent_client_id" not in p7_migration, "p7_actor_schema_invented")
    _require("agent_client_id" not in p7_audit, "p7_audit_actor_field_invented")
    _require(
        "access_log_only=False" in _text(TRUST_EXPORT, overrides),
        "machine_track2_p7_issuance_removed",
    )


def _validate_corrective_workflow(overrides: dict[Path, str]) -> None:
    workflow = _text(P11_WORKFLOW, overrides)
    for token in (
        "test_track1_31_day_source_scaling_timeout_and_connection_occupancy",
        "P11_TRACK1_DB_METRICS=",
        "test_detached_csv_is_header_first_rectangular_self_identifying_at_1000_rows",
        "test_csv_and_xlsx_maximum_concurrent_serialization_stays_in_declared_memory",
        "P11_TRACK1_CSV_METRICS=",
        "P11_TRACK1_SERIALIZATION_METRICS=",
        "test_timeout_retains_capacity_until_physical_serializer_finishes",
        "P11_TRACK1_TIMEOUT_SERIALIZER_METRICS=",
        "corrective_negative_controls_fired=11",
        "second_corrective_negative_controls_fired=7",
    ):
        _require(token in workflow, f"corrective_workflow_proof_missing:{token}")
    _require(
        "human_non_authoritative_export_completed" in _text(LEGACY_EXPORT, overrides),
        "human_export_observability_missing",
    )


def _validate_migration(overrides: dict[Path, str]) -> None:
    migration = _text(MIGRATION, overrides)
    _require(
        "'trust.export.create_limited'" in migration, "export_scope_migration_missing"
    )
    for reserved in (
        "trust.action.propose",
        "trust.action.execute",
        "trust.action.approve",
        "trust.action.reject",
        "auto_executable_within_policy",
    ):
        _require(reserved in migration, f"reserved_scope_exclusion_missing:{reserved}")
    _require(
        "reject_reserved_trust_action_scope" not in migration, "p9_trigger_modified"
    )
    _require("include_export_scope=False" in migration, "exact_downgrade_missing")


def _validate_examples(overrides: dict[Path, str]) -> None:
    required = (
        "export_artifact_signed_valid.json",
        "export_artifact_tampered_rejected.json",
        "export_display_non_authoritative.json",
        "export_reserved_subject_rejected.json",
        "export_scope_denied.json",
        "export_over_limit_rejected.json",
    )
    examples = ROOT / "contracts/trust-api/examples"
    for name in required:
        _require((examples / name).exists(), f"export_example_missing:{name}")
    display = json.loads(
        (examples / "export_display_non_authoritative.json").read_text()
    )
    Draft202012Validator(_parsed(DISPLAY_SCHEMA, overrides)).validate(display)


def _validate_scan_roots() -> int:
    scanned = 0
    root_resolved = ROOT.resolve()
    for scan_root in SCAN_ROOTS:
        _require(scan_root.exists(), f"scan_root_missing:{scan_root}")
        for path in scan_root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.resolve().relative_to(root_resolved)
            _require(
                relative.parts[0] not in SHADOW_ROOT_NAMES,
                f"shadow_path_scanned:{relative}",
            )
            scanned += 1
    return scanned


def validate_core(overrides: dict[Path, str] | None = None) -> None:
    active = overrides or {}
    _validate_schema_and_manifest(active)
    _validate_contracts(active)
    _validate_sources(active)
    _validate_p7_preservation(active)
    _validate_corrective_workflow(active)
    _validate_migration(active)
    _validate_examples(active)


def _mutated(path: Path, old: str, new: str) -> dict[Path, str]:
    source = _text(path, {})
    _require(old in source, f"negative_control_anchor_missing:{path}:{old}")
    return {path: source.replace(old, new, 1)}


def run_negative_controls() -> int:
    controls = (
        (
            "NC-P11-01",
            _mutated(
                TRUST_EXPORT,
                "router = APIRouter()",
                'router = APIRouter()\nAUTHORITY_QUERY = "SELECT SUM(x) FROM attribution_allocations"',
            ),
        ),
        (
            "NC-P11-02",
            _mutated(
                PROJECTION,
                '"tenant_id_hash": tenant_hash(tenant_id)',
                '"tenant_id": str(tenant_id)',
            ),
        ),
        (
            "NC-P11-03",
            _mutated(
                DISPLAY_SCHEMA,
                '"revenue_minor": {\n            "type": "integer"',
                '"revenue_minor": {\n            "type": "number"',
            ),
        ),
        (
            "NC-P11-04",
            _mutated(ARTIFACT, '"envelopes": ordered,', '"envelope_refs": ordered,'),
        ),
        (
            "NC-P11-05",
            _mutated(
                ARTIFACT,
                "    _assert_no_raw_tenant_or_float(signed)\n    return signed",
                '    signed["generated_at"] = "2026-08-08T12:00:02Z"\n    _assert_no_raw_tenant_or_float(signed)\n    return signed',
            ),
        ),
        (
            "NC-P11-06",
            _mutated(
                ARTIFACT, 'if candidate["artifact_hash"] != expected_hash:', "if False:"
            ),
        ),
        (
            "NC-P11-07",
            _mutated(
                ARTIFACT,
                'b"skeldir:b25-p11:export-artifact:v1\\x00"',
                'b"skeldir:b25-p8:trust-envelope:v1\\x00"',
            ),
        ),
        (
            "NC-P11-08",
            _mutated(
                PROJECTION,
                '"projection_authority": PROJECTION_AUTHORITY_NON_AUTHORITATIVE',
                '"legacy_authority": PROJECTION_AUTHORITY_NON_AUTHORITATIVE',
            ),
        ),
        (
            "NC-P11-09",
            _mutated(
                LEGACY_EXPORT,
                "workbook = Workbook(write_only=True)",
                'mock = b"PK\\x03\\x04SKELDIR-MOCK-XLSX"\n    workbook = Workbook(write_only=True)',
            ),
        ),
        (
            "NC-P11-10",
            _mutated(
                LEGACY_EXPORT,
                "writer = csv.writer(",
                'manual = ",".join([])\n    writer = csv.writer(',
            ),
        ),
        ("NC-P11-11", _mutated(PROJECTION, "neutralize_spreadsheet_cell(", "str(")),
        (
            "NC-P11-12",
            _mutated(
                LEGACY_EXPORT,
                "LEGACY_EXPORT_MAX_ROWS = 1_000",
                "LEGACY_EXPORT_ROWS_UNBOUNDED = True",
            ),
        ),
        (
            "NC-P11-13",
            _mutated(
                LEGACY_EXPORT,
                "result.fetchmany(LEGACY_EXPORT_MAX_ROWS + 1)",
                "result.fetchall()",
            ),
        ),
        (
            "NC-P11-14",
            _mutated(
                TRUST_EXPORT,
                "from app.api.trust_api import (",
                "from app.llm.provider_boundary import ProviderBoundary\nfrom app.api.trust_api import (",
            ),
        ),
        (
            "NC-P11-15",
            _mutated(
                TRUST_EXPORT,
                'frozenset({"match_verdict"})',
                'frozenset({"match_verdict", "attribution_result"})',
            ),
        ),
    )
    fired = 0
    for name, override in controls:
        try:
            validate_core(override)
        except (B25P11ValidationError, SyntaxError, KeyError, json.JSONDecodeError):
            fired += 1
            continue
        raise B25P11ValidationError(f"negative_control_silent:{name}")
    return fired


def run_corrective_negative_controls() -> int:
    controls = (
        (
            "NC-P11-FU-01",
            _mutated(
                ARTIFACT,
                '    signed["signature_hash"] = compute_detached_signature_hash(signature_material)\n',
                "",
            ),
        ),
        (
            "NC-P11-FU-02",
            _mutated(
                ARTIFACT,
                'signed["signature_hash"] = compute_detached_signature_hash(signature_material)',
                'signed["signature_hash"] = signed["artifact_hash"]',
            ),
        ),
        (
            "NC-P11-FU-03",
            _mutated(
                LEGACY_EXPORT,
                'CSV_COLUMNS = (\n    "projection_authority",',
                'CSV_COLUMNS = (\n    "authority_removed",',
            ),
        ),
        (
            "NC-P11-FU-04",
            _mutated(
                LEGACY_EXPORT,
                "    writer.writerow(CSV_COLUMNS)",
                '    writer.writerow(("metadata-preamble",))\n    writer.writerow(CSV_COLUMNS)',
            ),
        ),
        (
            "NC-P11-FU-05",
            _mutated(
                LEGACY_EXPORT,
                "LEGACY_EXPORT_MAX_DATE_SPAN_DAYS = 31",
                "LEGACY_EXPORT_MAX_DATE_SPAN_DAYS = 30",
            ),
        ),
        (
            "NC-P11-FU-06",
            _mutated(
                LEGACY_EXPORT,
                "SET LOCAL statement_timeout",
                "SET LOCAL idle_in_transaction_session_timeout",
            ),
        ),
        (
            "NC-P11-FU-07",
            _mutated(
                LEGACY_EXPORT,
                "TRACK1_MAX_CONCURRENT_EXPORTS = 2",
                "TRACK1_MAX_CONCURRENT_EXPORTS = 200",
            ),
        ),
        (
            "NC-P11-FU-08",
            _mutated(
                LEGACY_EXPORT,
                "LEGACY_EXPORT_MAX_ROWS = 1_000",
                "LEGACY_EXPORT_MAX_ROWS = 1_001",
            ),
        ),
        (
            "NC-P11-FU-09",
            _mutated(
                TRUST_EXPORT,
                "for page_offset, subject_ref in enumerate(page_refs)",
                "for page_offset, subject_ref in enumerate(export_request.subject_refs)",
            ),
        ),
        (
            "NC-P11-FU-10",
            _mutated(
                P7_MIGRATION,
                'revision = "202607011200"',
                'revision = "202607011200"\n# ALTER trust_access_log ADD agent_client_id uuid',
            ),
        ),
        (
            "NC-P11-FU-11",
            _mutated(
                TRUST_EXPORT,
                "        subject_refs=export_request.subject_refs,\n        row_limit=accepted_count,",
                "        subject_refs=page_refs,\n        row_limit=len(page_refs) + 1,",
            ),
        ),
    )
    fired = 0
    for name, override in controls:
        try:
            validate_core(override)
        except (B25P11ValidationError, SyntaxError, KeyError, json.JSONDecodeError):
            fired += 1
            continue
        raise B25P11ValidationError(f"corrective_negative_control_silent:{name}")
    return fired


def run_second_corrective_negative_controls() -> int:
    controls = (
        (
            "NC-C2-01",
            _mutated(
                LEGACY_EXPORT,
                'LEGACY_CSV_COLUMNS = ("date", "channel", "revenue", "conversions", "confidence")',
                'LEGACY_CSV_COLUMNS = ("projection_authority", "date", "channel", "revenue", "conversions")',
            ),
        ),
        (
            "NC-C2-02",
            _mutated(
                Path("api-contracts/openapi/v1/export.yaml"),
                "        '503':\n          $ref: '#/components/responses/ExportDeadlineExceeded'",
                "",
            ),
        ),
        (
            "NC-C2-03",
            # Anchored to the v2 guard, which is unique to the ACTIVE framing.
            # `_mutated` replaces only the first occurrence, so anchoring on a
            # line shared with the frozen v1 framing would silently mutate the
            # historical protocol instead and the control would not fire.
            _mutated(
                ARTIFACT,
                "    if not _BASE_FIELDS.issubset(payload):\n"
                '        raise ExportArtifactError("artifact_identity_fields_missing")\n'
                '    envelopes = _ordered_envelopes(payload["envelopes"])\n'
                "    pieces = [",
                "    if not _BASE_FIELDS.issubset(payload):\n"
                '        raise ExportArtifactError("artifact_identity_fields_missing")\n'
                '    envelopes = _ordered_envelopes(payload["envelopes"])\n'
                "    pieces = [\n"
                '        _frame("signing_key_id", payload["signing_key_id"].encode("utf-8")),',
            ),
        ),
        (
            "NC-C2-04",
            _mutated(
                ARTIFACT,
                '            _frame("signing_key_id", signing_key_id.encode("utf-8")),',
                "",
            ),
        ),
        (
            "NC-C2-05",
            _mutated(
                LEGACY_EXPORT,
                "                serializer_task.add_done_callback(release_retained_permit)",
                "                _TRACK1_EXPORT_CONCURRENCY_LIMIT.release()",
            ),
        ),
        (
            "NC-C2-06",
            _mutated(
                P11_PROJECTION_TESTS,
                "process = psutil.Process()",
                "process = tracemalloc",
            ),
        ),
        (
            "NC-C2-07",
            _mutated(
                Path("contracts/export/baselines/v1.0.0/export.yaml"),
                'value: "date,channel,revenue,conversions,confidence\\r\\n',
                'value: "projection_authority,date,channel,revenue,conversions\\r\\n',
            ),
        ),
    )
    fired = 0
    for name, override in controls:
        try:
            validate_core(override)
        except (B25P11ValidationError, SyntaxError, KeyError, json.JSONDecodeError):
            fired += 1
            continue
        raise B25P11ValidationError(f"second_corrective_negative_control_silent:{name}")
    return fired


def run_third_corrective_negative_controls() -> int:
    """Semantic falsifiers for the third corrective's load-bearing invariants.

    Each mutation changes production enforcement so a real regression -- not a
    parse error or a missing token -- causes the intended gate to fail.
    """
    public_contract_path = Path("api-contracts/openapi/v1/export.yaml")
    controls = (
        (
            # NC-C3-01: the active default CSV loses its authority classification.
            # Must fire even though the five-column positional shape is untouched.
            "NC-C3-01",
            _mutated(
                LEGACY_EXPORT,
                "COMPAT_CSV_COLUMNS = LEGACY_CSV_COLUMNS + (\n"
                '    "projection_authority",\n'
                '    "projection_schema_version",\n'
                ")",
                "COMPAT_CSV_COLUMNS = LEGACY_CSV_COLUMNS",
            ),
        ),
        (
            # NC-C3-02: a compliant opt-in profile must not mask a
            # noncompliant default. Point the default at the retired profile.
            "NC-C3-02",
            _mutated(
                LEGACY_EXPORT,
                "csv_schema_version: str = COMPAT_CSV_SCHEMA_VERSION",
                "csv_schema_version: str = LEGACY_CSV_SCHEMA_VERSION",
            ),
        ),
        (
            # NC-C3-03: change artifact framing without a protocol version
            # transition by collapsing v1 onto the active algorithm.
            "NC-C3-03",
            _mutated(
                ARTIFACT,
                "    identity_bytes=_artifact_identity_bytes_v1,",
                "    identity_bytes=_artifact_identity_bytes_v2,",
            ),
        ),
        (
            # NC-C3-04: remove the historical verification dispatch entirely.
            "NC-C3-04",
            _mutated(
                ARTIFACT,
                "def _artifact_identity_bytes_v1(payload: dict[str, Any]) -> bytes:",
                "def _removed_historical_framing(payload: dict[str, Any]) -> bytes:",
            ),
        ),
        (
            # NC-C3-05: mislabel the new protocol as the old version.
            "NC-C3-05",
            _mutated(
                ARTIFACT,
                'EXPORT_ARTIFACT_SCHEMA_VERSION_V2 = "b25-p11-export-artifact-v2"',
                'EXPORT_ARTIFACT_SCHEMA_VERSION_V2 = "b25-p11-export-artifact-v1"',
            ),
        ),
        (
            # NC-C3-06: restore the self-attested boolean escape hatch.
            "NC-C3-06",
            _mutated(
                ERROR_MODEL_CHECKER,
                "    if PROVENANCE_MARKER in response:",
                "    if response.get(PROVENANCE_MARKER) is True:\n"
                "        return True, 'self_attested'\n"
                "    if PROVENANCE_MARKER in response:",
            ),
        ),
        (
            # NC-C3-07: remove the governed 413 from the authoritative contract
            # while the runtime keeps emitting it.
            "NC-C3-07",
            _mutated(
                public_contract_path,
                "        '413':\n"
                "          $ref: '#/components/responses/ExportLimitExceeded'",
                "",
            ),
        ),
        (
            # NC-C3-08: drop one governed 413 reason code from the contract enum.
            "NC-C3-08",
            _mutated(
                public_contract_path,
                "                - legacy_export_row_budget_exceeded\n",
                "",
            ),
        ),
        (
            # NC-C3-09: make the endpoint description contradict the default.
            "NC-C3-09",
            _mutated(
                LEGACY_EXPORT,
                "    ] = Query(default=COMPAT_CSV_SCHEMA_VERSION),",
                "    ] = Query(default=CSV_SCHEMA_VERSION),",
            ),
        ),
        (
            # NC-C3-10: weaken the shared validator so any endpoint can bypass
            # the inherited error-contract guarantee.
            "NC-C3-10",
            _mutated(
                ERROR_MODEL_CHECKER,
                "        return False, reason",
                "        return True, 'bypassed'",
            ),
        ),
    )
    fired = 0
    for name, overrides in controls:
        try:
            validate_core(overrides)
        except B25P11ValidationError:
            fired += 1
            continue
        raise B25P11ValidationError(f"third_corrective_negative_control_silent:{name}")
    return fired


def _run_pytest() -> None:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "backend/tests/trust/test_b25_p11_export_projection.py",
        "backend/tests/trust/test_b25_p11_export_artifact.py",
        "backend/tests/trust/test_b25_p11_error_provenance.py",
        "-q",
    ]
    completed = subprocess.run(command, cwd=ROOT, check=False)
    _require(completed.returncode == 0, "p11_unit_pytest_failed")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args(argv)
    try:
        scanned = _validate_scan_roots()
        validate_core()
        negative_controls = run_negative_controls() if args.negative_control else 0
        corrective_negative_controls = (
            run_corrective_negative_controls() if args.negative_control else 0
        )
        second_corrective_negative_controls = (
            run_second_corrective_negative_controls() if args.negative_control else 0
        )
        third_corrective_negative_controls = (
            run_third_corrective_negative_controls() if args.negative_control else 0
        )
        if args.negative_control:
            _require(negative_controls == 15, "negative_control_count_drift")
            _require(
                corrective_negative_controls == 11,
                "corrective_negative_control_count_drift",
            )
            _require(
                third_corrective_negative_controls == 10,
                "third_corrective_negative_control_count_drift",
            )
            _require(
                second_corrective_negative_controls == 7,
                "second_corrective_negative_control_count_drift",
            )
        _run_pytest()
    except B25P11ValidationError as exc:
        print(f"B25_P11_EXPORT_COMPATIBILITY_VALIDATION_FAIL:{exc}")
        return 1
    print("B25_P11_EXPORT_COMPATIBILITY_VALIDATION_PASS")
    print("projection_authority_controls_passed=1")
    print("subject_capability_controls_passed=1")
    print("tenant_privacy_controls_passed=1")
    print("money_authority_controls_passed=1")
    print("artifact_identity_signature_controls_passed=1")
    print("display_honesty_controls_passed=1")
    print("format_injection_controls_passed=1")
    print("bounded_egress_controls_passed=1")
    print("read_only_no_compute_controls_passed=1")
    print("authorization_continuity_controls_passed=1")
    print("contract_compatibility_controls_passed=1")
    print("prior_phase_preservation_bindings_passed=1")
    print("mainline_closure_bindings_passed=1")
    print(f"explicit_root_files_scanned={scanned}")
    print("shadow_paths_scanned=0")
    print(f"negative_controls_fired={negative_controls}")
    print(f"corrective_negative_controls_fired={corrective_negative_controls}")
    print(
        "third_corrective_negative_controls_fired="
        f"{third_corrective_negative_controls}"
    )
    print(
        "second_corrective_negative_controls_fired="
        f"{second_corrective_negative_controls}"
    )
    print("pytest_controls_passed=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
