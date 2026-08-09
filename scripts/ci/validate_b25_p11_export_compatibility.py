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
        'EXPORT_ARTIFACT_SIGNING_DOMAIN = b"skeldir:b25-p11:export-artifact:v1\\x00"'
        in artifact,
        "artifact_signing_domain_drift",
    )
    _require(
        'candidate["artifact_hash"] != expected_hash' in artifact,
        "artifact_hash_verify_removed",
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
    _require(
        legacy.count("await asyncio.to_thread(") >= 2,
        "track1_cpu_serialization_not_offloaded",
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
        "corrective_negative_controls_fired=11",
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


def _run_pytest() -> None:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "backend/tests/trust/test_b25_p11_export_projection.py",
        "backend/tests/trust/test_b25_p11_export_artifact.py",
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
        if args.negative_control:
            _require(negative_controls == 15, "negative_control_count_drift")
            _require(
                corrective_negative_controls == 11,
                "corrective_negative_control_count_drift",
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
    print("pytest_controls_passed=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
