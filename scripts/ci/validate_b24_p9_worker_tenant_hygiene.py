#!/usr/bin/env python3
"""Validate B2.4-P9 worker tenant hygiene and process isolation."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BAYESIAN_PACKAGE = Path("backend/app/bayesian")
TENANT_CONTEXT = BAYESIAN_PACKAGE / "tenant_context.py"
TEMP_WORKSPACE = BAYESIAN_PACKAGE / "temp_workspace.py"
CLEANUP = BAYESIAN_PACKAGE / "cleanup.py"
COMPILEDIR_REAPER = BAYESIAN_PACKAGE / "compiledir_reaper.py"
CHILD_ENVIRONMENT = BAYESIAN_PACKAGE / "child_environment.py"
FIT_EXECUTION = BAYESIAN_PACKAGE / "fit_execution.py"
ARTIFACT_REPOSITORY = BAYESIAN_PACKAGE / "artifact_repository.py"
MODELS = BAYESIAN_PACKAGE / "models.py"
P9_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202606081200_b24_p9_worker_tenant_hygiene.py"
)
P9_TESTS = Path("backend/tests/test_b24_p9_worker_tenant_hygiene.py")
P9_DB_TESTS = Path("backend/tests/test_b24_p9_postgres_runtime.py")
WORKFLOW = Path(".github/workflows/b2_4-gate-dry-run.yml")
MAKEFILE = Path("Makefile")
REQUIRED_STATUS_CONTRACT = Path(
    "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
)

REQUIRED_FILES = {
    TENANT_CONTEXT,
    TEMP_WORKSPACE,
    CLEANUP,
    COMPILEDIR_REAPER,
    CHILD_ENVIRONMENT,
    FIT_EXECUTION,
    ARTIFACT_REPOSITORY,
    MODELS,
    P9_MIGRATION,
    P9_TESTS,
    P9_DB_TESTS,
    WORKFLOW,
    MAKEFILE,
    REQUIRED_STATUS_CONTRACT,
}


class ValidationError(RuntimeError):
    pass


def _read(path: Path) -> str:
    full = ROOT / path
    if not full.exists():
        raise ValidationError(f"missing required file: {path.as_posix()}")
    return full.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate_tenant_context(text: str | None = None) -> None:
    tenant_context = text if text is not None else _read(TENANT_CONTEXT)
    for token in (
        "bind_transaction_local_tenant",
        "set_config('app.current_tenant_id', :tenant_id, true)",
        "tenant_transaction",
        "assert_fresh_checkout_is_clean",
        "checked_out_connection_state",
        "bayesian_connection_returned_dirty",
    ):
        _require(token in tenant_context, f"P9 tenant context missing: {token}")
    for forbidden in (
        "set_config('app.current_tenant_id', :tenant_id, false)",
        "SET app.current_tenant_id",
        "lru_cache",
        "global ",
    ):
        _require(
            forbidden not in tenant_context,
            f"P9 tenant context has forbidden token: {forbidden}",
        )


def validate_workspace(text: str | None = None) -> None:
    workspace = text if text is not None else _read(TEMP_WORKSPACE)
    for token in (
        "WORKSPACE_OWNER",
        "create_workspace_lease",
        "tenant_id",
        "fit_id",
        "source_snapshot_hash",
        "execution_attempt_id",
        "cleanup_workspace",
        "reap_expired_workspaces",
        "max_deletions",
        "max_scan_entries",
        "_workspace_reaper_lock",
    ):
        _require(token in workspace, f"P9 workspace missing: {token}")
    for forbidden in ("while True", "ignore_errors=True", "tempfile.TemporaryDirectory"):
        _require(forbidden not in workspace, f"P9 workspace forbidden: {forbidden}")


def validate_compiledir(text: str | None = None) -> None:
    compiledir = text if text is not None else _read(COMPILEDIR_REAPER)
    for token in (
        "tenant_id: UUID | None",
        "fit_id: UUID | None",
        "source_snapshot_hash: str | None",
        "compiledir tenant, fit, and source hash must travel together",
        "_safe_segment(source_snapshot_hash",
        "root.rglob(METADATA_FILE)",
    ):
        _require(token in compiledir, f"P9 compiledir missing: {token}")


def validate_child_env(text: str | None = None) -> None:
    child_env = text if text is not None else _read(CHILD_ENVIRONMENT)
    for token in (
        "source = source_env if source_env is not None else os.environ",
        "env = {name: source[name] for name in ALLOWLISTED_CHILD_ENV if name in source}",
        "env[\"B24_PYTENSOR_COMPILEDIR\"]",
        "base_compiledir=",
        "PYTENSORRC",
    ):
        _require(token in child_env, f"P9 child env missing: {token}")
    for forbidden in ("os.environ[", "os.putenv", "DATABASE_URL"):
        _require(forbidden not in child_env, f"P9 child env forbidden: {forbidden}")


def validate_fit_execution(text: str | None = None) -> None:
    fit_execution = text if text is not None else _read(FIT_EXECUTION)
    for token in (
        "run_preflight_janitor(",
        "assert_fresh_checkout_is_clean(engine)",
        "create_workspace_lease(",
        "create_compiledir_lease(",
        "tenant_id=tenant_id",
        "fit_id=fit_id",
        "source_snapshot_hash=source_snapshot_hash",
        "ipc_dir = workspace.path / \"ipc\"",
        "cleanup_fit_attempt(workspace=workspace, compiledir=lease)",
        "stderr_retained_bytes",
        "stderr_truncated",
    ):
        _require(token in fit_execution, f"P9 fit execution missing: {token}")
    for forbidden in (
        "stderr_retained\": result.stderr.retained_text",
        "ipc_dir = lease.path / \"ipc\"",
        "cleanup_compiledir(lease)",
        "os.environ[",
    ):
        _require(forbidden not in fit_execution, f"P9 fit execution forbidden: {forbidden}")


def validate_artifact_authority(
    repository_text: str | None = None,
    models_text: str | None = None,
    migration_text: str | None = None,
) -> None:
    repository = repository_text if repository_text is not None else _read(ARTIFACT_REPOSITORY)
    models = models_text if models_text is not None else _read(MODELS)
    migration = migration_text if migration_text is not None else _read(P9_MIGRATION)
    for token in (
        "tenant_id: UUID",
        "b24://artifact/{tenant_id}/{fit_id}/{artifact_type}/{artifact_hash[:12]}",
    ):
        _require(token in repository, f"P9 artifact repository missing: {token}")
    tenant_bound_regex = (
        "^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$"
    )
    _require(tenant_bound_regex in models, "P9 models missing tenant-bound artifact regex")
    _require(
        tenant_bound_regex in migration,
        "P9 migration missing tenant-bound artifact regex",
    )


def validate_tests_and_ci(
    workflow_text: str | None = None,
    required_status_text: str | None = None,
) -> None:
    tests = _read(P9_TESTS)
    db_tests = _read(P9_DB_TESTS)
    workflow = workflow_text if workflow_text is not None else _read(WORKFLOW)
    required_status = (
        required_status_text
        if required_status_text is not None
        else _read(REQUIRED_STATUS_CONTRACT)
    )
    makefile = _read(MAKEFILE)
    for token in (
        "test_b24_p9_transaction_context_uses_set_local_only",
        "test_b24_p9_workspace_scopes_and_cleans_tenant_fit_hash_attempt",
        "test_b24_p9_compiledir_scopes_tenant_fit_hash_attempt",
        "test_b24_p9_child_env_is_allowlisted_without_parent_mutation",
        "test_b24_p9_artifact_ref_contains_tenant_authority",
        "test_b24_p9_fit_execution_wires_cleanup_and_payload_airgap",
        "test_b24_p9_validator_negative_controls",
    ):
        _require(token in tests, f"P9 unit proof missing: {token}")
    for token in (
        "test_b24_p9_transaction_local_guc_clean_return_and_sequential_isolation",
        "bind_transaction_local_tenant",
        "assert_fresh_checkout_is_clean",
        "SKELDIR_B24_P9_REQUIRE_DB_PROOFS",
    ):
        _require(token in db_tests, f"P9 DB proof missing: {token}")
    for token in (
        "validate-b24-p9-worker-tenant-hygiene",
        "B2.4-P9 Worker Tenant Hygiene Proof",
        "test_b24_p9_worker_tenant_hygiene.py",
        "test_b24_p9_postgres_runtime.py",
        "SKELDIR_B24_P9_REQUIRE_DB_PROOFS",
        "scripts/ci/validate_b24_p9_worker_tenant_hygiene.py --negative-control",
    ):
        _require(token in workflow, f"P9 workflow wiring missing: {token}")
    _require(
        "validate-b24-p9-worker-tenant-hygiene" in makefile,
        "Makefile missing P9 validator target",
    )
    _require(
        '"B2.4-P9 Worker Tenant Hygiene Proof"' in required_status,
        "required-status contract missing P9 proof context",
    )


def validate_all() -> None:
    for path in REQUIRED_FILES:
        _read(path)
    validate_tenant_context()
    validate_workspace()
    validate_compiledir()
    validate_child_env()
    validate_fit_execution()
    validate_artifact_authority()
    validate_tests_and_ci()


def run_negative_controls() -> None:
    controls = (
        (
            "set_local_removed",
            lambda: validate_tenant_context(
                _read(TENANT_CONTEXT).replace(
                    "set_config('app.current_tenant_id', :tenant_id, true)",
                    "set_config('app.current_tenant_id', :tenant_id, false)",
                )
            ),
            "tenant context",
        ),
        (
            "workspace_cleanup_removed",
            lambda: validate_workspace(
                _read(TEMP_WORKSPACE).replace("cleanup_workspace", "cleanup_removed")
            ),
            "cleanup_workspace",
        ),
        (
            "compiledir_hash_removed",
            lambda: validate_compiledir(
                _read(COMPILEDIR_REAPER).replace(
                    "_safe_segment(source_snapshot_hash",
                    "str(source_snapshot_hash",
                )
            ),
            "source_snapshot_hash",
        ),
        (
            "parent_env_mutation",
            lambda: validate_child_env(_read(CHILD_ENVIRONMENT) + "\nos.environ['X']='Y'\n"),
            "os.environ",
        ),
        (
            "stderr_payload_returned",
            lambda: validate_fit_execution(
                _read(FIT_EXECUTION) + "\nstderr_retained\": result.stderr.retained_text\n"
            ),
            "stderr",
        ),
        (
            "artifact_tenant_omitted",
            lambda: validate_artifact_authority(
                repository_text=_read(ARTIFACT_REPOSITORY).replace(
                    "{tenant_id}/{fit_id}",
                    "{fit_id}",
                )
            ),
            "artifact",
        ),
        (
            "required_status_removed",
            lambda: validate_tests_and_ci(
                required_status_text=_read(REQUIRED_STATUS_CONTRACT).replace(
                    '"B2.4-P9 Worker Tenant Hygiene Proof"',
                    '"B2.4-P9 Missing Proof"',
                )
            ),
            "required-status",
        ),
    )
    for name, runner, expected in controls:
        try:
            runner()
        except ValidationError as exc:
            _require(
                expected.lower() in str(exc).lower(),
                f"{name} failed for wrong reason: {exc}",
            )
        else:
            raise ValidationError(f"negative control did not fail: {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    try:
        validate_all()
        if args.negative_control:
            run_negative_controls()
    except ValidationError as exc:
        print(f"B24_P9_WORKER_TENANT_HYGIENE_VALIDATION_FAIL: {exc}")
        return 1
    print("B24_P9_WORKER_TENANT_HYGIENE_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
