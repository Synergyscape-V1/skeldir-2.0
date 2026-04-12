#!/usr/bin/env python3
"""B2.1-P0 authority convergence checks for attribution runtime/contract truth."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_LEGACY_REFERENCE = "contracts/attribution/v1/attribution.yaml"
CANONICAL_SOURCE = "api-contracts/openapi/v1/attribution.yaml"
CANONICAL_BUNDLE = "api-contracts/dist/openapi/v1/attribution.bundled.yaml"
CI_WORKFLOW = ".github/workflows/ci.yml"
RUNTIME_PROOF = "backend/tests/integration/test_b21_p0_runtime_authority_closeout.py"
REQUIRED_CHECKS_CONTRACT = (
    "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
)
B21_CLOSEOUT_CONTEXT = "B2.1-P0 Runtime Authority Closeout"
B21_MIGRATION_AUTHORITY_BOOTSTRAP = "scripts/database/prepare_migration_authority_boundary.py"
B21_CANONICAL_DSN_HELPER = "backend/app/db/dsn.py"
B21_RUNTIME_CONFTST = "backend/tests/conftest.py"
SELF_ALLOWLIST_PATHS = {
    "scripts/ci/enforce_b21_p0_authority_convergence.py",
}


def _resolve(repo_root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(_read_text(path)) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML payload must be an object: {path}")
    return payload


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(_read_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _iter_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    patterns = (
        "*.yml",
        "*.yaml",
        "*.sh",
        "*.ps1",
        "*.py",
        "*.json",
        "*.js",
        "*.mjs",
        "*.ts",
    )
    for pattern in patterns:
        files.extend(root.rglob(pattern))
    return sorted(set(files))


def run_enforcement(
    *,
    repo_root: Path,
    workflow_file: Path,
    runtime_proof_file: Path,
    required_checks_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []

    canonical_source_path = repo_root / CANONICAL_SOURCE
    canonical_bundle_path = repo_root / CANONICAL_BUNDLE
    legacy_source_path = repo_root / FORBIDDEN_LEGACY_REFERENCE
    contract_scope_path = repo_root / "backend/app/config/contract_scope.yaml"
    entrypoints_path = repo_root / "scripts/contracts/entrypoints.json"
    typegen_script_path = repo_root / "scripts/contracts/generate_frontend_types.sh"
    package_json_path = repo_root / "package.json"
    required_checks_path = required_checks_file
    migration_authority_bootstrap_path = repo_root / B21_MIGRATION_AUTHORITY_BOOTSTRAP
    canonical_dsn_helper_path = repo_root / B21_CANONICAL_DSN_HELPER
    conftest_path = repo_root / B21_RUNTIME_CONFTST

    required = (
        canonical_source_path,
        canonical_bundle_path,
        legacy_source_path,
        contract_scope_path,
        entrypoints_path,
        typegen_script_path,
        package_json_path,
        required_checks_path,
        migration_authority_bootstrap_path,
        canonical_dsn_helper_path,
        conftest_path,
        workflow_file,
        runtime_proof_file,
    )
    for required_path in required:
        if not required_path.exists():
            violations.append(f"missing_required_file:{required_path}")

    if violations:
        return 1, violations

    legacy_doc = _read_yaml(legacy_source_path)
    authority_marker = legacy_doc.get("info", {}).get("x-skeldir-authority", {})
    if authority_marker.get("status") != "non_authoritative_legacy_reference":
        violations.append("legacy_root_missing_non_authoritative_marker")
    if authority_marker.get("canonical_source") != CANONICAL_SOURCE:
        violations.append("legacy_root_missing_canonical_source_pointer")
    if authority_marker.get("generation_and_ci_authority_forbidden") is not True:
        violations.append("legacy_root_missing_generation_forbidden_marker")

    scope_doc = _read_yaml(contract_scope_path)
    mappings = scope_doc.get("spec_mappings", {})
    if mappings.get("/api/attribution") != CANONICAL_BUNDLE:
        violations.append("contract_scope_attribution_mapping_not_canonical_bundle")

    entrypoints_doc = _read_json(entrypoints_path)
    attribution_entry = None
    for entry in entrypoints_doc.get("entrypoints", []):
        if isinstance(entry, dict) and entry.get("id") == "attribution":
            attribution_entry = entry
            break
    if attribution_entry is None:
        violations.append("entrypoints_missing_attribution_entry")
    else:
        if attribution_entry.get("source") != CANONICAL_SOURCE:
            violations.append("entrypoints_attribution_source_not_canonical")
        if attribution_entry.get("bundle") != CANONICAL_BUNDLE:
            violations.append("entrypoints_attribution_bundle_not_canonical")

    typegen_text = _read_text(typegen_script_path)
    if 'generate "attribution.bundled.yaml" "attribution.ts"' not in typegen_text:
        violations.append("typegen_missing_canonical_attribution_bundle_generate_line")

    package_doc = _read_json(package_json_path)
    scripts = package_doc.get("scripts", {})
    contracts_validate = str(scripts.get("contracts:validate", ""))
    if FORBIDDEN_LEGACY_REFERENCE in contracts_validate:
        violations.append("package_contracts_validate_references_legacy_root")

    required_checks_doc = _read_json(required_checks_path)
    if bool(required_checks_doc.get("exact_match", False)) is not True:
        violations.append("required_checks_contract_exact_match_must_be_true")
    required_contexts = required_checks_doc.get("required_contexts", [])
    if not isinstance(required_contexts, list):
        violations.append("required_checks_contract_required_contexts_invalid")
        required_contexts = []
    if B21_CLOSEOUT_CONTEXT not in required_contexts:
        violations.append("required_checks_contract_missing_b21_closeout_context")

    workflow_text = _read_text(workflow_file)
    required_workflow_tokens = (
        "Prepare B2.1-P0 runtime closeout authority boundary",
        "python scripts/database/prepare_migration_authority_boundary.py",
        "Run B2.1-P0 closeout runtime authority proofs",
        "pytest backend/tests/integration/test_b21_p0_runtime_authority_closeout.py -q",
        "DATABASE_URL: postgresql+asyncpg://app_user:app_user@127.0.0.1:5432/skeldir_b21_p0",
        "MIGRATION_DATABASE_URL: postgresql://migration_owner:migration_owner@127.0.0.1:5432/skeldir_b21_p0",
        "ENFORCE_RUNTIME_IDENTITY_PARITY: \"1\"",
        "EXPECTED_RUNTIME_DB_USER: app_user",
        "REVOKE ALL ON TABLE public.alembic_version FROM app_user",
    )
    for token in required_workflow_tokens:
        if token not in workflow_text:
            violations.append(f"workflow_missing_b21_closeout_token:{token}")

    runtime_proof_text = _read_text(runtime_proof_file)
    required_runtime_proof_tokens = (
        "test_b21_p0_migration_authority_is_privileged_and_runtime_fails_closed",
        "test_b21_p0_channels_route_is_tenant_safe_with_cross_tenant_negative_control",
        "test_b21_p0_worker_substrate_path_is_tenant_safe_with_cross_tenant_negative_control",
        "permission denied for table alembic_version",
        "/api/attribution/channels",
        "AUTHORITY_ENVELOPE_HEADER",
        "current_setting('app.current_tenant_id', true)",
        "session_authority",
        "SHOW row_security",
        "relrowsecurity",
        "assert int(tenant_a_event_count) >= 1",
        "assert int(cross_event_count) == 0",
        "assert int(tenant_a_session_authority) >= 1",
        "assert int(cross_session_authority) == 0",
        "session locality violation",
    )
    for token in required_runtime_proof_tokens:
        if token not in runtime_proof_text:
            violations.append(f"runtime_proof_missing_b21_closeout_token:{token}")

    conftest_text = _read_text(conftest_path)
    if "from app.db.dsn import to_sync_postgres_dsn" not in conftest_text:
        violations.append("runtime_conftest_missing_canonical_dsn_import")
    if "create_engine(to_sync_postgres_dsn(runtime_dsn))" not in conftest_text:
        violations.append("runtime_conftest_missing_canonical_dsn_runtime_usage")
    if "create_engine(to_sync_postgres_dsn(migration_dsn))" not in conftest_text:
        violations.append("runtime_conftest_missing_canonical_dsn_migration_usage")

    runtime_proof_text = _read_text(runtime_proof_file)
    if "from app.db.dsn import to_sync_postgres_dsn" not in runtime_proof_text:
        violations.append("runtime_proof_missing_canonical_dsn_import")
    if "return to_sync_postgres_dsn(_runtime_async_url())" not in runtime_proof_text:
        violations.append("runtime_proof_missing_canonical_dsn_runtime_usage")
    if "return to_sync_postgres_dsn(_require_env(\"MIGRATION_DATABASE_URL\"))" not in runtime_proof_text:
        violations.append("runtime_proof_missing_canonical_dsn_migration_usage")

    migration_bootstrap_text = _read_text(migration_authority_bootstrap_path)
    required_migration_bootstrap_tokens = (
        "runtime_user and migration_user must be distinct principals",
        "CREATE DATABASE",
        "ALTER DATABASE",
        "ALTER DEFAULT PRIVILEGES FOR ROLE",
        "GRANT ALL ON SCHEMA public TO",
        "migration_authority_boundary_prepared",
    )
    for token in required_migration_bootstrap_tokens:
        if token not in migration_bootstrap_text:
            violations.append(f"migration_bootstrap_missing_token:{token}")

    scan_roots = (
        repo_root / ".github" / "workflows",
        repo_root / "scripts",
        repo_root / "backend" / "app" / "config",
        repo_root / "package.json",
    )
    scanned_files: list[Path] = []
    for scan_root in scan_roots:
        if scan_root.is_file():
            scanned_files.append(scan_root)
            continue
        if scan_root.exists():
            scanned_files.extend(_iter_text_files(scan_root))

    for path in sorted(set(scanned_files)):
        rel_path = path.relative_to(repo_root).as_posix()
        if rel_path in SELF_ALLOWLIST_PATHS:
            continue
        text = _read_text(path)
        if FORBIDDEN_LEGACY_REFERENCE in text:
            violations.append(f"legacy_reference_in_authority_chain:{rel_path}")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce B2.1-P0 attribution authority convergence."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--workflow-file", default=CI_WORKFLOW)
    parser.add_argument("--runtime-proof-file", default=RUNTIME_PROOF)
    parser.add_argument("--required-checks-file", default=REQUIRED_CHECKS_CONTRACT)
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b21_p0_authority_convergence_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        repo_root=repo_root,
        workflow_file=_resolve(repo_root, args.workflow_file),
        runtime_proof_file=_resolve(repo_root, args.runtime_proof_file),
        required_checks_file=_resolve(repo_root, args.required_checks_file),
    )
    lines = ["b21_p0_authority_convergence_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=canonical_attribution_authority_chain_converged")
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
