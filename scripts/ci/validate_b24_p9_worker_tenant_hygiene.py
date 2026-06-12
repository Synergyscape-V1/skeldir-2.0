#!/usr/bin/env python3
"""Validate B2.4-P9 worker tenant hygiene and process isolation."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BAYESIAN_PACKAGE = Path("backend/app/bayesian")
TENANT_CONTEXT = BAYESIAN_PACKAGE / "tenant_context.py"
DB_ENGINE = BAYESIAN_PACKAGE / "db_engine.py"
DB_TOPOLOGY = BAYESIAN_PACKAGE / "db_topology.py"
DB_BOOT_PROBE = BAYESIAN_PACKAGE / "db_boot_probe.py"
WORKER_BOOT_PROBE = BAYESIAN_PACKAGE / "worker_boot_probe.py"
TEMP_WORKSPACE = BAYESIAN_PACKAGE / "temp_workspace.py"
CLEANUP = BAYESIAN_PACKAGE / "cleanup.py"
COMPILEDIR_REAPER = BAYESIAN_PACKAGE / "compiledir_reaper.py"
CHILD_ENVIRONMENT = BAYESIAN_PACKAGE / "child_environment.py"
FIT_EXECUTION = BAYESIAN_PACKAGE / "fit_execution.py"
ARTIFACT_REPOSITORY = BAYESIAN_PACKAGE / "artifact_repository.py"
MODELS = BAYESIAN_PACKAGE / "models.py"
TASKS_BAYESIAN = Path("backend/app/tasks/bayesian.py")
P9_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202606081200_b24_p9_worker_tenant_hygiene.py"
)
P9_TESTS = Path("backend/tests/test_b24_p9_worker_tenant_hygiene.py")
P9_DB_TESTS = Path("backend/tests/test_b24_p9_postgres_runtime.py")
WORKFLOW = Path(".github/workflows/b2_4-gate-dry-run.yml")
CI_WORKFLOW = Path(".github/workflows/ci.yml")
B07_P5_TIMEOUT_RUNTIME_TEST = Path(
    "backend/tests/integration/test_b07_p5_bayesian_timeout_runtime.py"
)
MAKEFILE = Path("Makefile")
REQUIRED_STATUS_CONTRACT = Path(
    "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
)

REQUIRED_FILES = {
    TENANT_CONTEXT,
    DB_ENGINE,
    DB_TOPOLOGY,
    DB_BOOT_PROBE,
    WORKER_BOOT_PROBE,
    TEMP_WORKSPACE,
    CLEANUP,
    COMPILEDIR_REAPER,
    CHILD_ENVIRONMENT,
    FIT_EXECUTION,
    ARTIFACT_REPOSITORY,
    MODELS,
    TASKS_BAYESIAN,
    P9_MIGRATION,
    P9_TESTS,
    P9_DB_TESTS,
    WORKFLOW,
    CI_WORKFLOW,
    B07_P5_TIMEOUT_RUNTIME_TEST,
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


def _ci_job_block(workflow_text: str, job_id: str) -> str:
    pattern = rf"^  {re.escape(job_id)}:\n(?P<body>.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)"
    match = re.search(pattern, workflow_text, re.MULTILINE | re.DOTALL)
    _require(match is not None, f"CI workflow job missing: {job_id}")
    return match.group("body")


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


def validate_bayesian_worker_engine(text: str | None = None) -> None:
    db_engine = text if text is not None else _read(DB_ENGINE)
    for token in (
        "create_bayesian_worker_engine",
        "runtime_sync_database_url",
        "resolve_bayesian_worker_db_topology_policy",
        "poolclass=NullPool",
        "assert_bayesian_worker_engine_nonpooled",
        "bayesian_worker_engine_must_use_nullpool",
    ):
        _require(token in db_engine, f"P9 worker engine missing: {token}")
    for forbidden in (
        "pool_size=1",
        "max_overflow=0",
        "QueuePool",
        "SingletonThreadPool",
    ):
        _require(
            forbidden not in db_engine,
            f"P9 worker engine has forbidden pooled token: {forbidden}",
        )


def validate_bayesian_worker_db_topology(text: str | None = None) -> None:
    topology = text if text is not None else _read(DB_TOPOLOGY)
    for token in (
        "SKELDIR_BAYESIAN_DB_TOPOLOGY",
        "SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION",
        "SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE",
        "DIRECT_POSTGRES_ATTESTATIONS",
        "UNSUPPORTED_POOLER_TOPOLOGIES",
        "POOLER_NEGATIVE_CONTROL_TOKENS",
        "protected_topology_runtime",
        "DSN contents are intentionally insufficient proof",
        "bayesian_worker_db_topology_missing",
        "bayesian_worker_db_topology_unknown",
        "bayesian_worker_db_topology_pooler_unsupported",
        "bayesian_worker_db_topology_proxy_dsn_rejected",
        "bayesian_worker_db_topology_attestation_missing",
        "bayesian_worker_db_topology_source_missing",
    ):
        _require(token in topology, f"P9 topology policy missing: {token}")
    for forbidden in (
        "if 'internal' in",
        "if 'localhost' in",
        "if '127.0.0.1' in",
    ):
        _require(
            forbidden not in topology,
            f"P9 topology policy has string-proof shortcut: {forbidden}",
        )


def validate_bayesian_worker_boot_probe(
    probe_text: str | None = None,
    worker_boot_text: str | None = None,
    tasks_text: str | None = None,
) -> None:
    boot_probe = probe_text if probe_text is not None else _read(DB_BOOT_PROBE)
    worker_boot = (
        worker_boot_text if worker_boot_text is not None else _read(WORKER_BOOT_PROBE)
    )
    tasks = tasks_text if tasks_text is not None else _read(TASKS_BAYESIAN)
    for token in (
        "run_bayesian_worker_boot_topology_probe",
        "BayesianWorkerBootTopologyProbeError",
        "create_bayesian_worker_engine",
        "set_config('app.current_tenant_id', :tenant_id, false)",
        "SET search_path TO pg_catalog",
        "pg_advisory_lock",
        "CREATE TEMP TABLE",
        "pg_stat_activity",
        "old_pid",
        "new_pid",
        "_wait_for_backend_absence",
        "bayesian_worker_boot_topology_backend_not_replaced",
        "bayesian_worker_boot_topology_guc_poison_survived",
        "bayesian_worker_boot_topology_advisory_lock_survived",
        "bayesian_worker_boot_topology_temp_object_survived",
    ):
        _require(token in boot_probe, f"P9 worker boot probe missing: {token}")
    for forbidden in ("pymc", "pytensor", "arviz", "INSERT INTO public."):
        _require(
            forbidden not in boot_probe,
            f"P9 worker boot probe has forbidden token: {forbidden}",
        )
    for token in (
        "signals.worker_init.connect(",
        "signals.worker_process_init.connect(",
        "_run_bayesian_worker_boot_topology_probe_if_needed()",
        "run_bayesian_worker_boot_topology_probe()",
        'SystemExit("bayesian_worker_boot_topology_probe_failed")',
        "bayesian_worker_boot_topology_probe_has_passed",
        "assert_bayesian_worker_boot_topology_proven",
        "_bayesian_boot_topology_probe_pid == os.getpid()",
    ):
        _require(
            token in worker_boot,
            f"P9 Celery boot probe wiring missing: {token}",
        )
    for forbidden in (
        "_parse_celery_queue_arguments",
        "_worker_may_consume_bayesian_tasks",
        "QUEUE_BAYESIAN in explicit_queues",
        "SKELDIR_BAYESIAN_BOOT_PROBE_REQUIRED",
        "_BAYESIAN_TOPOLOGY_AUTHORITY_ENV",
    ):
        _require(
            forbidden not in worker_boot,
            f"P9 boot probe still has forbidden queue/env skip authority: {forbidden}",
        )
    _require(
        "if _BAYESIAN_TASKS_REGISTERED:" in tasks
        and "ensure_bayesian_worker_boot_probe_signal_registered()" in tasks,
        "P9 Bayesian task module must register boot probe signal only when tasks are registered",
    )
    _require(
        tasks.count("assert_bayesian_worker_boot_topology_proven()") >= 6,
        "P9 Bayesian task entries must fail closed on missing boot proof",
    )
    for token in (
        "SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS",
        "_bayesian_tasks_registered_for_process",
        "_BAYESIAN_TASK_REGISTRATION_TOPOLOGY_ENV",
        "_BAYESIAN_TASKS_REGISTERED",
        "return celery_app.task(*task_args, **task_kwargs)",
        "return _return_plain_function",
    ):
        _require(token in tasks, f"P9 Bayesian task registry gate missing: {token}")
    _require(
        tasks.count("@_bayesian_task(") >= 6,
        "P9 Bayesian task entries must use the structural task-registration gate",
    )
    _require(
        "@celery_app.task(" not in tasks,
        "P9 Bayesian task entries must not bypass the structural registration gate",
    )
    try:
        worker_init_idx = worker_boot.index("signals.worker_init.connect(")
        worker_process_init_idx = worker_boot.index(
            "signals.worker_process_init.connect("
        )
        probe_call_idx = worker_boot.index(
            "_run_bayesian_worker_boot_topology_probe_if_needed()"
        )
    except ValueError as exc:
        raise ValidationError(
            f"P9 Celery boot probe order token missing: {exc}"
        ) from exc
    _require(
        probe_call_idx < worker_init_idx,
        "P9 Celery boot probe receiver must be defined before worker_init registration",
    )
    _require(
        probe_call_idx < worker_process_init_idx,
        "P9 Celery boot probe receiver must be defined before worker_process_init registration",
    )
    for forbidden in ("worker_ready", "task_prerun"):
        _require(
            forbidden not in worker_boot,
            f"P9 boot probe must not defer to {forbidden}",
        )


def validate_bayesian_tasks(text: str | None = None) -> None:
    tasks = text if text is not None else _read(TASKS_BAYESIAN)
    for token in (
        "create_bayesian_worker_engine(",
        "runtime_sync_database_url()",
        "engine.dispose()",
    ):
        _require(token in tasks, f"P9 Bayesian task wiring missing: {token}")
    for forbidden in (
        "from sqlalchemy import create_engine",
        "create_engine(",
        "pool_size=1",
        "max_overflow=0",
    ):
        _require(
            forbidden not in tasks,
            f"P9 Bayesian task wiring has forbidden pooled token: {forbidden}",
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
        "lock_contended",
        "except FileExistsError",
        "except FileNotFoundError",
        "_is_owned_child_path",
    ):
        _require(token in workspace, f"P9 workspace missing: {token}")
    for forbidden in (
        "while True",
        "ignore_errors=True",
        "tempfile.TemporaryDirectory",
    ):
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
        "lock_contended",
        "except FileExistsError",
        "except FileNotFoundError",
        "_is_owned_child_path",
    ):
        _require(token in compiledir, f"P9 compiledir missing: {token}")


def validate_child_env(text: str | None = None) -> None:
    child_env = text if text is not None else _read(CHILD_ENVIRONMENT)
    for token in (
        "source = source_env if source_env is not None else os.environ",
        "env = {name: source[name] for name in ALLOWLISTED_CHILD_ENV if name in source}",
        'env["B24_PYTENSOR_COMPILEDIR"]',
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
        "assert_bound_tenant(conn, tenant_id=tenant_id)",
        "create_workspace_lease(",
        "create_compiledir_lease(",
        "tenant_id=tenant_id",
        "fit_id=fit_id",
        "source_snapshot_hash=source_snapshot_hash",
        'ipc_dir = workspace.path / "ipc"',
        "cleanup_fit_attempt(workspace=workspace, compiledir=lease)",
        "_sampler_failure_stream_metadata(result)",
        "stderr_retained_bytes",
        "stderr_truncated",
    ):
        _require(token in fit_execution, f"P9 fit execution missing: {token}")
    for forbidden in (
        'stderr_retained": result.stderr.retained_text',
        'ipc_dir = lease.path / "ipc"',
        "cleanup_compiledir(lease)",
        "os.environ[",
    ):
        _require(
            forbidden not in fit_execution, f"P9 fit execution forbidden: {forbidden}"
        )


def validate_artifact_authority(
    repository_text: str | None = None,
    models_text: str | None = None,
    migration_text: str | None = None,
) -> None:
    repository = (
        repository_text if repository_text is not None else _read(ARTIFACT_REPOSITORY)
    )
    models = models_text if models_text is not None else _read(MODELS)
    migration = migration_text if migration_text is not None else _read(P9_MIGRATION)
    for token in (
        "tenant_id: UUID",
        "b24://artifact/{tenant_id}/{fit_id}/{artifact_type}/{artifact_hash[:12]}",
        "assert_bound_tenant(conn, tenant_id=tenant_id)",
    ):
        _require(token in repository, f"P9 artifact repository missing: {token}")
    tenant_bound_regex = (
        "^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$"
    )
    _require(
        tenant_bound_regex in models, "P9 models missing tenant-bound artifact regex"
    )
    _require(
        tenant_bound_regex in migration,
        "P9 migration missing tenant-bound artifact regex",
    )


def validate_tests_and_ci(
    workflow_text: str | None = None,
    ci_workflow_text: str | None = None,
    b07_p5_timeout_test_text: str | None = None,
    required_status_text: str | None = None,
) -> None:
    tests = _read(P9_TESTS)
    db_tests = _read(P9_DB_TESTS)
    workflow = workflow_text if workflow_text is not None else _read(WORKFLOW)
    ci_workflow = (
        ci_workflow_text if ci_workflow_text is not None else _read(CI_WORKFLOW)
    )
    b07_p5_timeout_test = (
        b07_p5_timeout_test_text
        if b07_p5_timeout_test_text is not None
        else _read(B07_P5_TIMEOUT_RUNTIME_TEST)
    )
    required_status = (
        required_status_text
        if required_status_text is not None
        else _read(REQUIRED_STATUS_CONTRACT)
    )
    makefile = _read(MAKEFILE)
    for token in (
        "test_b24_p9_transaction_context_uses_set_local_only",
        "test_b24_p9_bayesian_worker_engine_factory_is_nonpooled",
        "test_b24_p9_db_topology_policy_is_code_authority_not_dsn_proof",
        "test_b24_p9_unknown_topology_fails_closed_in_protected_mode",
        "test_b24_p9_opaque_hostname_requires_attestation_not_string_inference",
        "test_b24_p9_pooler_and_proxy_topologies_fail_closed",
        "test_b24_p9_boot_probe_is_physical_not_connectivity_only",
        "test_b24_p9_celery_worker_init_runs_boot_probe_before_ready_and_prerun",
        "test_b24_p9_non_bayesian_worker_registry_excludes_bayesian_tasks",
        "test_b24_p9_bayesian_registration_wires_tasks_and_boot_probe",
        "test_b24_p9_bayesian_task_entry_requires_process_local_boot_proof",
        "test_b24_p9_bayesian_task_module_registry_gate_is_structural",
        "test_b24_p9_bayesian_tasks_use_nonpooled_worker_engine",
        "test_b24_p9_workspace_scopes_and_cleans_tenant_fit_hash_attempt",
        "test_b24_p9_compiledir_scopes_tenant_fit_hash_attempt",
        "test_b24_p9_child_env_is_allowlisted_without_parent_mutation",
        "test_b24_p9_artifact_ref_contains_tenant_authority",
        "test_b24_p9_fit_execution_wires_cleanup_and_payload_airgap",
        "test_b24_p9_same_process_sequential_reused_worker_runtime_lane",
        "test_b24_p9_concurrent_tenant_isolation_runtime_surfaces",
        "test_b24_p9_concurrent_janitor_toctou_safe",
        "test_b24_p9_logs_and_failure_payloads_do_not_emit_sentinels",
        "test_b24_p9_native_memory_lifecycle_child_per_fit_parent_airgap",
        "test_b24_p9_validator_negative_controls",
    ):
        _require(token in tests, f"P9 unit proof missing: {token}")
    for token in (
        "test_b24_p9_bayesian_worker_engine_uses_nullpool_structural_sanitation",
        "test_b24_p9_direct_topology_attestation_precedes_backend_pid_proof",
        "test_b24_p9_boot_probe_physically_proves_session_boundary",
        "test_b24_p9_boot_probe_failure_is_fatal_before_task_consumption",
        "test_b24_p9_registered_bayesian_process_always_runs_boot_probe",
        "test_b24_p9_non_bayesian_registry_rejects_broker_misrouted_bayesian_task",
        "test_b24_p9_pool_poison_is_closed_and_replaced_without_manual_reset",
        "test_b24_p9_pg_stat_activity_backend_not_idle_in_transaction",
        "test_b24_p9_reset_failure_surface_replaced_by_invalidation_or_close",
        "test_b24_p9_representative_same_process_worker_path_exercises_db_lifecycle",
        "test_b24_p9_transaction_local_guc_clean_return_and_sequential_isolation",
        "test_b24_p9_db_proof_requires_explicit_flag_in_ci",
        "test_b24_p9_session_level_guc_poison_is_detected",
        "test_b24_p9_multi_transaction_task_flow_rebinds_each_transaction",
        "test_b24_p9_concurrent_tenant_isolation_db_and_runtime_surfaces",
        "bind_transaction_local_tenant",
        "assert_fresh_checkout_is_clean",
        "pg_stat_activity",
        "pg_advisory_lock",
        "CREATE TEMP TABLE p9_temp_poison",
        "B2.4-P9 protected CI requires SKELDIR_B24_P9_REQUIRE_DB_PROOFS=1",
        "SKELDIR_B24_P9_REQUIRE_DB_PROOFS",
        "SKELDIR_BAYESIAN_DB_TOPOLOGY",
        "direct_postgres_ci_postgres15",
    ):
        _require(token in db_tests, f"P9 DB proof missing: {token}")
    for token in (
        "validate-b24-p9-worker-tenant-hygiene",
        "B2.4-P9 Worker Tenant Hygiene Proof",
        "B2.4-P5 PostgreSQL Runtime Proof",
        "test_b24_p9_worker_tenant_hygiene.py",
        "test_b24_p9_postgres_runtime.py",
        "SKELDIR_B24_P9_REQUIRE_DB_PROOFS",
        "SKELDIR_BAYESIAN_DB_TOPOLOGY",
        "SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION",
        "SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE",
        "direct_postgres_ci_postgres15",
        "scripts/ci/validate_b24_p9_worker_tenant_hygiene.py --negative-control",
    ):
        _require(token in workflow, f"P9 workflow wiring missing: {token}")
    for token in (
        "B2.1-P4 Queue Isolation + Performance Semantics Lock",
        "B2.1-P6 Full End-to-End Closure + Downstream Readiness",
    ):
        _require(
            token in ci_workflow, f"P9 CI workflow topology wiring missing: {token}"
        )
    for job_id in (
        "b21-p4-queue-isolation-performance-lock",
        "b21-p6-full-chain-closure-readiness",
        "b07-p2-runtime-proof",
        "celery-foundation",
    ):
        block = _ci_job_block(ci_workflow, job_id)
        for token in (
            "SKELDIR_BAYESIAN_DB_TOPOLOGY",
            "SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION",
            "SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE",
            "direct_postgres_ci_postgres15",
        ):
            _require(
                token in block,
                f"P9 CI workflow topology wiring missing in {job_id}: {token}",
            )
    for job_id in (
        "b21-p4-queue-isolation-performance-lock",
        "b21-p6-full-chain-closure-readiness",
        "celery-foundation",
    ):
        _require(
            "github_actions_postgres_15_alpine" in _ci_job_block(ci_workflow, job_id),
            f"P9 CI workflow topology source missing in {job_id}",
        )
    _require(
        "github_actions_postgres_16"
        in _ci_job_block(ci_workflow, "b07-p2-runtime-proof"),
        "P9 CI workflow topology source missing in b07-p2-runtime-proof",
    )
    for token in (
        '"SKELDIR_BAYESIAN_DB_TOPOLOGY"',
        '"SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION"',
        '"SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE"',
        '"direct_postgres_ci_postgres15"',
        '"b07_p5_bayesian_timeout_runtime"',
    ):
        _require(
            token in b07_p5_timeout_test,
            f"P9 B0.7 P5 runtime worker topology wiring missing: {token}",
        )
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
    validate_bayesian_worker_engine()
    validate_bayesian_worker_db_topology()
    validate_bayesian_worker_boot_probe()
    validate_bayesian_tasks()
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
            "nullpool_removed",
            lambda: validate_bayesian_worker_engine(
                _read(DB_ENGINE).replace("poolclass=NullPool", "pool_size=1")
            ),
            "worker engine",
        ),
        (
            "topology_attestation_removed",
            lambda: validate_bayesian_worker_db_topology(
                _read(DB_TOPOLOGY).replace(
                    "SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION",
                    "SKELDIR_BAYESIAN_DB_ATTESTATION_REMOVED",
                )
            ),
            "topology",
        ),
        (
            "topology_proxy_negative_control_removed",
            lambda: validate_bayesian_worker_db_topology(
                _read(DB_TOPOLOGY).replace(
                    "bayesian_worker_db_topology_proxy_dsn_rejected",
                    "bayesian_worker_db_topology_proxy_allowed",
                )
            ),
            "proxy",
        ),
        (
            "boot_probe_poison_removed",
            lambda: validate_bayesian_worker_boot_probe(
                probe_text=_read(DB_BOOT_PROBE).replace(
                    "pg_advisory_lock",
                    "advisory_lock_removed",
                )
            ),
            "pg_advisory_lock",
        ),
        (
            "boot_probe_worker_init_removed",
            lambda: validate_bayesian_worker_boot_probe(
                worker_boot_text=_read(WORKER_BOOT_PROBE).replace(
                    "_run_bayesian_worker_boot_topology_probe_if_needed()",
                    "_run_bayesian_worker_boot_topology_probe_removed()",
                )
            ),
            "boot probe",
        ),
        (
            "boot_probe_child_process_hook_removed",
            lambda: validate_bayesian_worker_boot_probe(
                worker_boot_text=_read(WORKER_BOOT_PROBE).replace(
                    "signals.worker_process_init.connect(",
                    "signals.worker_process_init_removed(",
                )
            ),
            "worker_process_init",
        ),
        (
            "bayesian_task_entry_guard_removed",
            lambda: validate_bayesian_worker_boot_probe(
                tasks_text=_read(TASKS_BAYESIAN).replace(
                    "assert_bayesian_worker_boot_topology_proven()",
                    "bayesian_task_entry_guard_removed()",
                    1,
                )
            ),
            "task entries",
        ),
        (
            "bayesian_task_registration_gate_removed",
            lambda: validate_bayesian_worker_boot_probe(
                tasks_text=_read(TASKS_BAYESIAN).replace(
                    "SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS",
                    "SKELDIR_CELERY_INCLUDE_BAYESIAN_REMOVED",
                )
            ),
            "registry",
        ),
        (
            "task_factory_removed",
            lambda: validate_bayesian_tasks(
                _read(TASKS_BAYESIAN).replace(
                    "create_bayesian_worker_engine", "create_engine"
                )
            ),
            "Bayesian task",
        ),
        (
            "workspace_cleanup_removed",
            lambda: validate_workspace(
                _read(TEMP_WORKSPACE).replace("cleanup_workspace", "cleanup_removed")
            ),
            "cleanup_workspace",
        ),
        (
            "workspace_lock_contention_removed",
            lambda: validate_workspace(
                _read(TEMP_WORKSPACE).replace(
                    "except FileExistsError", "except RuntimeError"
                )
            ),
            "FileExistsError",
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
            "compiledir_lock_contention_removed",
            lambda: validate_compiledir(
                _read(COMPILEDIR_REAPER).replace(
                    "except FileExistsError", "except RuntimeError"
                )
            ),
            "FileExistsError",
        ),
        (
            "parent_env_mutation",
            lambda: validate_child_env(
                _read(CHILD_ENVIRONMENT) + "\nos.environ['X']='Y'\n"
            ),
            "os.environ",
        ),
        (
            "stderr_payload_returned",
            lambda: validate_fit_execution(
                _read(FIT_EXECUTION)
                + '\nstderr_retained": result.stderr.retained_text\n'
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
            "artifact_bound_tenant_assert_removed",
            lambda: validate_artifact_authority(
                repository_text=_read(ARTIFACT_REPOSITORY).replace(
                    "assert_bound_tenant(conn, tenant_id=tenant_id)",
                    "pass",
                )
            ),
            "assert_bound_tenant",
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
        (
            "ci_topology_attestation_removed",
            lambda: validate_tests_and_ci(
                ci_workflow_text=_read(CI_WORKFLOW).replace(
                    "SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION",
                    "SKELDIR_BAYESIAN_DB_ATTESTATION_REMOVED",
                )
            ),
            "topology",
        ),
        (
            "b07_p5_runtime_topology_attestation_removed",
            lambda: validate_tests_and_ci(
                b07_p5_timeout_test_text=_read(B07_P5_TIMEOUT_RUNTIME_TEST).replace(
                    '"b07_p5_bayesian_timeout_runtime"',
                    '"b07_p5_bayesian_timeout_removed"',
                )
            ),
            "B0.7 P5 runtime worker topology",
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
