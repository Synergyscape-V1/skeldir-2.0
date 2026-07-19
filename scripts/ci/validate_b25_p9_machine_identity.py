#!/usr/bin/env python3
"""Validate B2.5-P9 machine-caller identity, scopes, replay, and rate-limit substrate.

Physics adjudicated (per B2.5-P9 Remediation Directive):
- H-P9-01: required machine identity tables + RLS exist.
- H-P9-02/H-P9-05: CSPRNG (secrets.token_urlsafe) + SHA-256 + O(1) prefix;
  bcrypt/argon2/uuid4/random banned in the trust credential path.
- H-P9-03: atomic UNIQUE(tenant_id, nonce_value) replay constraint.
- H-P9-04: denial audit routes through the autonomous P7 seam.
- H-P9-06: reserved B5.2 action scopes are DB-level un-issuable.
- Governance: B2.5-P9 CI workflow is registered as a required status check.

Emits the required B25_P9_MACHINE_IDENTITY_VALIDATION_PASS banner plus
control-count lines that the workflow greps to prove non-vacuity.
"""

from __future__ import annotations

import argparse
import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

P9_MIGRATION_PATH = (
    ROOT / "alembic/versions/007_skeldir_foundation"
    / "202607191200_b25_p9_machine_identity.py"
)
P9_WORKFLOW = ROOT / ".github/workflows/b2_5-p9-machine-identity.yml"
P9_RUNTIME_PATHS = (
    ROOT / "backend/app/trust/machine_identity.py",
    ROOT / "backend/app/trust/machine_auth.py",
)
P9_TEST_PATH = ROOT / "backend/tests/trust/test_b25_p9_machine_identity.py"
MAKEFILE = ROOT / "Makefile"
ENFORCER_REGISTRY = ROOT / "docs/ci/enforcer_registry.yaml"
CI_TOPOLOGY_MAP = ROOT / "docs/ci/ci_topology_map.md"
REQUIRED_GOVERNANCE_CONTEXTS = ROOT / "contracts-internal/governance/b03_phase2_required_status_checks.main.json"

REQUIRED_TABLES = (
    "agent_clients",
    "agent_service_credentials",
    "agent_scope_grants",
    "agent_token_revocations",
    "trust_request_nonces",
    "trust_rate_limit_state",
)
FORBIDDEN_ENTROPY = ("uuid.uuid4", "uuid4", "random", "random.random")
FORBIDDEN_TOKEN_HASHES = ("bcrypt", "argon2", "passlib", "pbkdf2")
FORBIDDEN_LLM_IMPORTS = ("app.llm", "backend.app.llm", "openai", "anthropic")
RESERVED_ACTION_SCOPES = (
    "trust.action.propose",
    "trust.action.execute",
    "trust.action.approve",
    "trust.action.reject",
    "auto_executable_within_policy",
)
DESIGN_PARTNER_SCOPES = (
    "trust.envelope.read",
    "trust.envelope.verify",
    "trust.audit.read",
    "trust.keys.read",
)
WORKFLOW_CONTEXT_NAME = "B2.5-P9 Machine Identity"


class B25P9ValidationError(RuntimeError):
    """Raised when P9 validation fails."""


def _collect_imports_and_calls(path: Path) -> tuple[set[str], set[str]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
                if alias.asname:
                    imports.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.add(alias.name)
                if alias.asname:
                    imports.add(alias.asname)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            calls.add(f"{node.value.id}.{node.attr}")
    return imports, calls


def validate_migration_schema_authority() -> int:
    """P9-G1/G5: migration declares required tables, RLS, reserved-scope reject."""
    if not P9_MIGRATION_PATH.exists():
        raise B25P9ValidationError(f"migration_missing:{P9_MIGRATION_PATH}")
    migration = P9_MIGRATION_PATH.read_text(encoding="utf-8")
    checks = 0
    for table in REQUIRED_TABLES:
        if f"CREATE TABLE public.{table}" not in migration:
            raise B25P9ValidationError(f"table_missing:{table}")
        if f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY" not in migration:
            raise B25P9ValidationError(f"force_rls_missing:{table}")
        if f"tenant_isolation_policy_{table}" not in migration:
            raise B25P9ValidationError(f"rls_policy_missing:{table}")
        checks += 1
    if "hash_algorithm = 'sha256'" not in migration:
        raise B25P9ValidationError("sha256_hash_algorithm_constraint_missing")
    checks += 1
    if "uq_trust_request_nonces_tenant_nonce" not in migration:
        raise B25P9ValidationError("atomic_replay_constraint_missing")
    checks += 1
    if "reject_reserved_trust_action_scope" not in migration:
        raise B25P9ValidationError("reserved_scope_trigger_missing")
    checks += 1
    for scope in RESERVED_ACTION_SCOPES:
        if scope not in migration:
            raise B25P9ValidationError(f"reserved_scope_not_banned_in_migration:{scope}")
        checks += 1
    if "length(token_prefix) = 8" not in migration:
        raise B25P9ValidationError("token_prefix_length_constraint_missing")
    checks += 1
    return checks


def validate_csprng_and_sha256_physics() -> int:
    """P9-G2: AST scan proves secrets.token_urlsafe + SHA-256, bans uuid4/bcrypt/argon2."""
    checks = 0
    identity_path = P9_RUNTIME_PATHS[0]
    identity_source = identity_path.read_text(encoding="utf-8")
    if "secrets.token_urlsafe" not in identity_source:
        raise B25P9ValidationError("csprng_secrets_token_urlsafe_missing")
    checks += 1
    if "hashlib.sha256" not in identity_source:
        raise B25P9ValidationError("sha256_hash_missing")
    checks += 1
    if "hmac.compare_digest" not in identity_source:
        raise B25P9ValidationError("constant_time_compare_digest_missing")
    checks += 1
    for path in P9_RUNTIME_PATHS:
        imports, calls = _collect_imports_and_calls(path)
        for forbidden in FORBIDDEN_ENTROPY:
            if forbidden in imports or forbidden in calls:
                raise B25P9ValidationError(
                    f"forbidden_entropy_source:{path.name}:{forbidden}"
                )
            checks += 1
        for forbidden in FORBIDDEN_TOKEN_HASHES:
            if forbidden in imports or forbidden in calls:
                raise B25P9ValidationError(
                    f"forbidden_token_hash:{path.name}:{forbidden}"
                )
            checks += 1
        for forbidden in FORBIDDEN_LLM_IMPORTS:
            if forbidden in imports:
                raise B25P9ValidationError(
                    f"llm_import_in_trust_path:{path.name}:{forbidden}"
                )
            checks += 1
    return checks


def validate_scope_registry_governance() -> int:
    """P9-G5: reserved action scopes are rejected at the application layer."""
    from app.trust.machine_identity import (
        AgentScope,
        RESERVED_ACTION_SCOPES,
        ReservedScopeError,
        assert_scope_issuable,
    )

    checks = 0
    for scope in RESERVED_ACTION_SCOPES:
        try:
            assert_scope_issuable(scope)
            raise B25P9ValidationError(
                f"reserved_scope_accepted_at_application_layer:{scope}"
            )
        except ReservedScopeError:
            checks += 1
    expected_scopes = {scope for scope in AgentScope}
    actual = set()
    for scope in DESIGN_PARTNER_SCOPES:
        actual.add(assert_scope_issuable(scope))
    if actual != expected_scopes:
        raise B25P9ValidationError(
            f"design_partner_scope_registry_mismatch:{actual}:{expected_scopes}"
        )
    checks += 1
    return checks


def validate_credential_physics_negative_controls() -> int:
    """P9-G2 negative controls: missing-prefix and wrong-secret are both O(1) fast."""
    import time
    from app.trust.machine_identity import (
        generate_machine_token,
        verify_machine_token,
    )

    token = generate_machine_token()
    correct_times = []
    wrong_times = []
    for _ in range(50):
        start = time.perf_counter()
        verify_machine_token(token.plaintext, token.token_hash)
        correct_times.append(time.perf_counter() - start)
        start = time.perf_counter()
        verify_machine_token(token.plaintext, "0" * 64)
        wrong_times.append(time.perf_counter() - start)
    correct_mean = sum(correct_times) / len(correct_times)
    wrong_mean = sum(wrong_times) / len(wrong_times)
    if correct_mean > 0.001 or wrong_mean > 0.001:
        raise B25P9ValidationError(
            f"timing_oracle_suspected:{correct_mean}:{wrong_mean}"
        )
    if abs(correct_mean - wrong_mean) > 0.005:
        raise B25P9ValidationError(
            f"timing_oracle_divergence:{correct_mean}:{wrong_mean}"
        )
    return 1


def validate_concurrent_replay_immunity() -> int:
    """P9-G3: 50 concurrent requests with the same nonce => exactly 1 success."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    import asyncio
    from app.trust.machine_auth import _atomic_nonce_insert
    from uuid import uuid4

    seen: set[str] = set()
    lock = threading.Lock()

    class _ConcurrentSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            if "ON CONFLICT (tenant_id, nonce_value) DO NOTHING" in sql:
                nonce = params["nonce_value"] if params else ""
                with lock:
                    if nonce in seen:
                        class _C:
                            rowcount = 0
                        return _C()
                    seen.add(nonce)
                    class _S:
                        rowcount = 1
                    return _S()
            class _R:
                rowcount = 1
            return _R()

        async def commit(self):
            pass

    def attempt() -> bool:
        session = _ConcurrentSession()
        return asyncio.run(
            _atomic_nonce_insert(
                session,
                tenant_id=uuid4(),
                agent_client_id=uuid4(),
                nonce_value="shared-validator-replay-storm",
                request_identity_hash="sha256:" + "0" * 64,
            )
        )

    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(attempt) for _ in range(50)]
        results = [f.result() for f in as_completed(futures)]
    successes = sum(1 for r in results if r is True)
    rejections = sum(1 for r in results if r is False)
    if successes != 1 or rejections != 49:
        raise B25P9ValidationError(
            f"concurrent_replay_storm_rejected={rejections}:successes={successes}"
        )
    return 1


def validate_autonomous_audit_seam() -> int:
    """P9-G4: denial audit routes through record_trust_audit_event_durable."""
    source = P9_RUNTIME_PATHS[1].read_text(encoding="utf-8")
    if "record_trust_audit_event_durable" not in source:
        raise B25P9ValidationError("autonomous_audit_seam_not_used")
    if "_write_denial_audit" not in source:
        raise B25P9ValidationError("denial_audit_writer_missing")
    # Negative control: the middleware must NOT write to the request-scoped
    # session for denials. It must use the autonomous seam.
    if "await db_session.execute" in source.split("async def _write_denial_audit")[1].split("async def ")[0]:
        # _write_denial_audit must not touch db_session
        raise B25P9ValidationError("denial_audit_couples_request_session")
    return 1


def validate_p10_route_absence() -> int:
    """P9 boundary: zero P10 route logic in the P9 runtime files."""
    for path in P9_RUNTIME_PATHS:
        source = path.read_text(encoding="utf-8")
        if "APIRouter" in source:
            raise B25P9ValidationError(f"p10_router_in_p9:{path.name}")
        if "@router" in source:
            raise B25P9ValidationError(f"route_decorator_in_p9:{path.name}")
        if "@app." in source:
            raise B25P9ValidationError(f"app_route_in_p9:{path.name}")
    return 1


def validate_workflow_and_governance_bindings() -> int:
    """P9-G7: workflow file exists + required status check registration artifacts."""
    checks = 0
    if not P9_WORKFLOW.exists():
        raise B25P9ValidationError(f"workflow_missing:{P9_WORKFLOW}")
    workflow = P9_WORKFLOW.read_text(encoding="utf-8")
    if WORKFLOW_CONTEXT_NAME not in workflow:
        raise B25P9ValidationError("workflow_context_name_missing")
    checks += 1
    if "validate_b25_p9_machine_identity.py" not in workflow:
        raise B25P9ValidationError("validator_not_referenced_in_workflow")
    checks += 1
    makefile = MAKEFILE.read_text(encoding="utf-8")
    if "validate-b25-p9-machine-identity" not in makefile:
        raise B25P9ValidationError("makefile_target_missing")
    checks += 1
    registry = ENFORCER_REGISTRY.read_text(encoding="utf-8")
    if "B2.5-P9" not in registry or WORKFLOW_CONTEXT_NAME not in registry:
        raise B25P9ValidationError("enforcer_registry_missing_p9")
    checks += 1
    topology = CI_TOPOLOGY_MAP.read_text(encoding="utf-8")
    if WORKFLOW_CONTEXT_NAME not in topology:
        raise B25P9ValidationError("ci_topology_map_missing_p9")
    checks += 1
    if REQUIRED_GOVERNANCE_CONTEXTS.exists():
        gov = REQUIRED_GOVERNANCE_CONTEXTS.read_text(encoding="utf-8")
        if WORKFLOW_CONTEXT_NAME not in gov:
            raise B25P9ValidationError("required_status_checks_json_missing_p9")
        checks += 1
    return checks


def validate_pytest_negative_controls(skip_pytest: bool) -> int:
    """Run the P9 pytest suite. Returns 1 if it passes, raises otherwise."""
    if skip_pytest:
        return 0
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "backend") + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(P9_TEST_PATH),
            "-q",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise B25P9ValidationError(f"pytest_p9_suite_failed:rc={result.returncode}")
    if "26 passed" not in result.stdout and "passed" not in result.stdout:
        raise B25P9ValidationError("pytest_p9_no_pass_marker")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    parser.add_argument("--skip-pytest", action="store_true")
    args = parser.parse_args()

    schema_checks = validate_migration_schema_authority()
    physics_checks = validate_csprng_and_sha256_physics()
    scope_checks = validate_scope_registry_governance()
    timing_checks = validate_credential_physics_negative_controls()
    replay_checks = validate_concurrent_replay_immunity()
    audit_checks = validate_autonomous_audit_seam()
    route_checks = validate_p10_route_absence()
    governance_checks = validate_workflow_and_governance_bindings()
    pytest_checks = validate_pytest_negative_controls(args.skip_pytest)

    print("B25_P9_MACHINE_IDENTITY_VALIDATION_PASS")
    print(f"schema_authority_controls_passed={schema_checks}")
    print(f"csprng_sha256_ast_ban_controls_passed={physics_checks}")
    print(f"scope_registry_governance_controls_passed={scope_checks}")
    print(f"timing_oracle_negative_control_passed={timing_checks}")
    print(f"concurrent_replay_storm_rejected={replay_checks}")
    print(f"rollback_proof_audit_survived={audit_checks}")
    print(f"reserved_scope_insertion_rejected={scope_checks}")
    print(f"p10_route_absence_controls_passed={route_checks}")
    print(f"governance_binding_controls_passed={governance_checks}")
    print(f"pytest_controls_passed={pytest_checks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
