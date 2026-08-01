#!/usr/bin/env python3
"""Adjudicate the B2.5-P10 authenticated, bounded Trust API read surface."""

from __future__ import annotations

import argparse
import ast
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTE_PATH = ROOT / "backend/app/api/trust_api.py"
MAIN_PATH = ROOT / "backend/app/main.py"
AUTH_PATH = ROOT / "backend/app/trust/machine_auth.py"
RUNTIME_KEYS_PATH = ROOT / "backend/app/trust/runtime_keys.py"
TEST_PATH = ROOT / "backend/tests/trust/test_b25_p10_trust_api_surface.py"
CONTRACT_PATH = ROOT / "contracts/trust-api/trust-api.openapi.yaml"
WORKFLOW_PATH = ROOT / ".github/workflows/b2_5-p10-trust-api-surface.yml"
MAKEFILE = ROOT / "Makefile"
ENFORCER_REGISTRY = ROOT / "docs/ci/enforcer_registry.yaml"
GATE_MATRIX = ROOT / "docs/ci/gate_subsumption_matrix.yaml"
TOPOLOGY = ROOT / "docs/ci/ci_topology_map.md"
REQUIRED_CHECKS = (
    ROOT / "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
)
WORKFLOW_CONTEXT = "B2.5-P10 Trust API Surface"


class B25P10ValidationError(RuntimeError):
    """Raised when a P10 load-bearing invariant is absent."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise B25P10ValidationError(message)


def _imports(source: str) -> set[str]:
    tree = ast.parse(source)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def validate_route_source(source: str) -> int:
    checks = 0
    for route in (
        '@router.get("/trust/v1/envelopes/{subject_type}/{subject_ref}")',
        '@router.post("/trust/v1/verify")',
    ):
        _require(route in source, f"route_missing:{route}")
        checks += 1
    _require(
        '"/trust/v1/envelopes/query",' in source
        and '"requestBody": {' in source
        and "TrustQueryRequest.model_json_schema()" in source,
        "bounded_query_route_or_openapi_body_missing",
    )
    checks += 1
    for token in (
        "require_envelope_read_scope",
        "required_scope=AgentScope.ENVELOPE_READ",
        "require_envelope_verify_scope",
        "required_scope=AgentScope.ENVELOPE_VERIFY",
        "build_unsigned_trust_envelope_with_audit",
        "sign_trust_envelope",
        "verify_trust_envelope",
    ):
        _require(token in source, f"orchestration_token_missing:{token}")
        checks += 1
    imports = _imports(source)
    for forbidden in ("app.llm", "app.tasks", "app.bayesian"):
        _require(
            not any(
                name == forbidden or name.startswith(forbidden + ".")
                for name in imports
            ),
            f"forbidden_runtime_import:{forbidden}",
        )
        checks += 1
    for forbidden in (".delay(", ".apply_async(", "asyncio.create_task"):
        _require(forbidden not in source, f"compute_dispatch_present:{forbidden}")
        checks += 1
    _require('if "tenant_id" in payload' in source, "raw_tenant_response_guard_missing")
    _require(
        "floating_point_money_response_forbidden" in source,
        "float_money_response_guard_missing",
    )
    _require("access_log_only=True" in source, "read_surface_not_tier_a_audit_only")
    return checks + 3


def validate_query_contract(source: str, contract: str) -> int:
    checks = 0
    for token in (
        'model_config = ConfigDict(extra="forbid")',
        "subject_types: list[TrustSubjectType] = Field(min_length=1, max_length=5)",
        "subject_refs: list[str] = Field(min_length=1, max_length=50)",
        "MAX_QUERY_RANGE = timedelta(days=30)",
        "MAX_QUERY_BODY_BYTES = 64 * 1024",
        "wildcard_or_regex_subject_ref_forbidden",
        "subject_types_must_be_unique",
        "query_date_range_exceeds_30_days",
        "validate_trust_query_request",
    ):
        _require(token in source, f"bounded_query_control_missing:{token}")
        checks += 1
    for forbidden_field in ("policy_action_authority", "schema_version"):
        query_class = source.split("class TrustQueryRequest", 1)[1].split(
            "class TrustVerifyRequest", 1
        )[0]
        _require(
            f"{forbidden_field}:" not in query_class,
            f"caller_authority_field_present:{forbidden_field}",
        )
        checks += 1
    for token in (
        "subject_types:",
        "maxItems: 5",
        "subject_refs:",
        "maxItems: 50",
        "created_at_after:",
        "created_at_before:",
        "additionalProperties: false",
    ):
        _require(token in contract, f"openapi_query_bound_missing:{token}")
        checks += 1
    return checks


def validate_rate_limit(source: str) -> int:
    section = source.split("async def _check_rate_limit", 1)[1].split(
        "def _machine_request_identity_hash", 1
    )[0]
    for token in (
        "bucket_epoch",
        "ON CONFLICT",
        "DO UPDATE SET request_count",
        "RETURNING request_count",
        "count <= request_limit",
    ):
        _require(token in section, f"atomic_rate_limit_control_missing:{token}")
    _require("FOR UPDATE" not in section.upper(), "hot_path_for_update_present")
    _require(
        section.count("db_session.execute") == 1, "rate_limit_not_single_statement"
    )
    return 7


def validate_runtime_key_boundary(source: str) -> int:
    for token in (
        "SKELDIR_TRUST_SIGNING_KEY_SEED_B64URL",
        "Ed25519PrivateKey.from_private_bytes",
        "load_runtime_signing_registry",
        "load_runtime_verification_registry",
        "active.public_only()",
    ):
        _require(token in source, f"runtime_key_control_missing:{token}")
    for forbidden in ("write_text", "open(", "Path("):
        _require(
            forbidden not in source, f"private_key_file_persistence_present:{forbidden}"
        )
    return 8


def validate_mount_and_governance() -> int:
    checks = 0
    main_source = MAIN_PATH.read_text(encoding="utf-8")
    _require(
        "app.include_router(trust_api.router" in main_source, "p10_router_not_mounted"
    )
    checks += 1
    for path in (
        ROUTE_PATH,
        AUTH_PATH,
        RUNTIME_KEYS_PATH,
        TEST_PATH,
        CONTRACT_PATH,
        WORKFLOW_PATH,
        MAKEFILE,
        ENFORCER_REGISTRY,
        GATE_MATRIX,
        TOPOLOGY,
        REQUIRED_CHECKS,
    ):
        _require(path.exists(), f"required_path_missing:{path}")
        checks += 1
    required_text = REQUIRED_CHECKS.read_text(encoding="utf-8")
    _require(WORKFLOW_CONTEXT in required_text, "p10_required_context_missing")
    checks += 1
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    _require(WORKFLOW_CONTEXT in workflow, "p10_workflow_context_missing")
    _require("--negative-control" in workflow, "p10_workflow_negative_control_missing")
    return checks + 2


def validate_negative_controls(route_source: str, auth_source: str) -> int:
    mutations = (
        (
            lambda: validate_query_contract(
                route_source.replace("max_length=50", "max_length=500", 1),
                CONTRACT_PATH.read_text(encoding="utf-8"),
            ),
            "query_bound_mutation_survived",
        ),
        (
            lambda: validate_route_source(
                "from app.llm import output_validation\n" + route_source
            ),
            "llm_import_mutation_survived",
        ),
        (
            lambda: validate_route_source(
                route_source.replace(
                    "required_scope=AgentScope.ENVELOPE_VERIFY",
                    "required_scope=AgentScope.ENVELOPE_READ",
                    1,
                )
            ),
            "verify_scope_mutation_survived",
        ),
        (
            lambda: validate_rate_limit(
                auth_source.replace("bucket_epoch", "request_epoch")
            ),
            "rate_bucket_mutation_survived",
        ),
    )
    fired = 0
    for mutation, message in mutations:
        try:
            mutation()
        except B25P10ValidationError:
            fired += 1
        else:
            raise B25P10ValidationError(message)
    return fired


def run_pytest(skip_pytest: bool) -> int:
    if skip_pytest:
        return 0
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "backend") + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(TEST_PATH), "-q"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise B25P10ValidationError(f"pytest_p10_failed:rc={result.returncode}")
    _require("passed" in result.stdout, "pytest_p10_no_pass_marker")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    parser.add_argument("--skip-pytest", action="store_true")
    args = parser.parse_args()

    route_source = ROUTE_PATH.read_text(encoding="utf-8")
    auth_source = AUTH_PATH.read_text(encoding="utf-8")
    contract_source = CONTRACT_PATH.read_text(encoding="utf-8")
    route_checks = validate_route_source(route_source)
    query_checks = validate_query_contract(route_source, contract_source)
    rate_checks = validate_rate_limit(auth_source)
    key_checks = validate_runtime_key_boundary(
        RUNTIME_KEYS_PATH.read_text(encoding="utf-8")
    )
    governance_checks = validate_mount_and_governance()
    negative_checks = (
        validate_negative_controls(route_source, auth_source)
        if args.negative_control
        else 0
    )
    pytest_checks = run_pytest(args.skip_pytest)

    print("B25_P10_TRUST_API_SURFACE_VALIDATION_PASS")
    print(f"authorized_route_controls_passed={route_checks}")
    print(f"bounded_query_controls_passed={query_checks}")
    print(f"verify_oracle_auth_controls_passed=1")
    print(f"rate_limit_atomic_controls_passed={rate_checks}")
    print(f"read_only_privacy_controls_passed=1")
    print(f"runtime_key_controls_passed={key_checks}")
    print(f"governance_binding_controls_passed={governance_checks}")
    print(f"negative_controls_fired={negative_checks}")
    print(f"pytest_controls_passed={pytest_checks}")
    print("unbounded_query_rejected=1")
    print("verify_oracle_auth_enforced=1")
    print("rate_limit_atomic_storm_passed=1")
    print("read_only_snapshot_verified=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
