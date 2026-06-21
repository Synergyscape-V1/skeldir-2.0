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
DISPATCH_AUTHORITY = BAYESIAN_PACKAGE / "dispatch_authority.py"
DISPATCH_OUTBOX = BAYESIAN_PACKAGE / "dispatch_outbox.py"
ARTIFACT_REPOSITORY = BAYESIAN_PACKAGE / "artifact_repository.py"
MODELS = BAYESIAN_PACKAGE / "models.py"
TASKS_BAYESIAN = Path("backend/app/tasks/bayesian.py")
BEAT_SCHEDULE = Path("backend/app/tasks/beat_schedule.py")
PROCFILE = Path("Procfile")
P9_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202606081200_b24_p9_worker_tenant_hygiene.py"
)
P9_DIRECTIVE_IX_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202606141200_b24_p9_directive_ix_dispatch_authority.py"
)
P9_DIRECTIVE_X_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202606181200_b24_p9_directive_x_broker_independent_authority.py"
)
P9_DIRECTIVE_XIII_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202606201300_b24_p9_directive_xiii_shared_recovery.py"
)
P9_DIRECTIVE_XIV_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202606201430_b24_p9_directive_xiv_failure_ack_recovery.py"
)
P9_TESTS = Path("backend/tests/test_b24_p9_worker_tenant_hygiene.py")
P9_DB_TESTS = Path("backend/tests/test_b24_p9_postgres_runtime.py")
P9_RAW_DB_TESTS = Path("backend/tests/test_b24_p9_raw_driver_postgres_runtime.py")
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
    DISPATCH_AUTHORITY,
    DISPATCH_OUTBOX,
    ARTIFACT_REPOSITORY,
    MODELS,
    TASKS_BAYESIAN,
    BEAT_SCHEDULE,
    P9_MIGRATION,
    P9_DIRECTIVE_IX_MIGRATION,
    P9_DIRECTIVE_X_MIGRATION,
    P9_DIRECTIVE_XIII_MIGRATION,
    P9_DIRECTIVE_XIV_MIGRATION,
    P9_TESTS,
    P9_DB_TESTS,
    P9_RAW_DB_TESTS,
    WORKFLOW,
    CI_WORKFLOW,
    B07_P5_TIMEOUT_RUNTIME_TEST,
    MAKEFILE,
    PROCFILE,
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
        "SELECT pg_backend_pid()",
        "bayesian_tenant_transaction_required",
        "bayesian_tenant_transaction_preexisting_tenant_guc",
        "bayesian_tenant_transaction_backend_continuity_lost",
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
        "to_sync_postgres_dsn(get_database_url())",
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
        "SKELDIR_BAYESIAN_DB_BACKEND_AFFINITY",
        "BayesianWorkerDBBackendAffinity",
        "CONNECTION_LIFETIME",
        "TRANSACTION_LIFETIME",
        "STATEMENT_LIFETIME",
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
        "bayesian_worker_db_topology_affinity_missing",
        "bayesian_worker_db_topology_transaction_pooling_unsupported",
        "bayesian_worker_db_topology_statement_pooling_unsupported",
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
        "_derive_bayesian_child_authority_if_needed()",
        "run_bayesian_worker_boot_topology_probe()",
        'SystemExit("bayesian_worker_boot_topology_probe_failed")',
        "bayesian_worker_boot_topology_probe_has_passed",
        "assert_bayesian_worker_boot_topology_proven",
        "BayesianWorkerGenerationProof",
        "BayesianWorkerExecutionAuthority",
        "BayesianWorkerGenerationClaims",
        "SKELDIR_BAYESIAN_DB_BACKEND_AFFINITY",
        "hmac.compare_digest",
        "BAYESIAN_CHILD_AUTHORITY_BUDGET_S",
        "SKELDIR_BAYESIAN_WORKER_GENERATION_AUTHORITY_FILE",
        "_persist_generation_authority_file",
        "_load_generation_authority_file",
        "bayesian_worker_generation_authority_payload_contains_secret",
        "bayesian_worker_generation_anchor_unavailable",
        "os.getppid() != proof.parent_pid",
    ):
        _require(
            token in worker_boot,
            f"P9 Celery boot probe wiring missing: {token}",
        )
    public_payload = worker_boot[
        worker_boot.index("def _generation_proof_to_json") : worker_boot.index(
            "def _generation_proof_from_json"
        )
    ]
    _require(
        "authority_secret" not in public_payload,
        "P9 child-readable generation payload must not contain root secret",
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
        tasks.count("assert_bayesian_worker_boot_topology_proven()") >= 8,
        "P9 Bayesian task entries must fail closed on missing boot proof",
    )
    for token in (
        "SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS",
        "SKELDIR_CELERY_WORKER_ROLE",
        "REQUIRED_BAYESIAN_TASK_NAMES",
        "_bayesian_tasks_registered_for_process",
        "_BAYESIAN_TASKS_REGISTERED",
        "return celery_app.task(*task_args, **task_kwargs)",
        "return _return_plain_function",
    ):
        _require(token in tasks, f"P9 Bayesian task registry gate missing: {token}")
    for forbidden in (
        "_BAYESIAN_TASK_REGISTRATION_TOPOLOGY_ENV",
        "SKELDIR_BAYESIAN_DB_TOPOLOGY",
    ):
        _require(
            forbidden not in tasks,
            f"P9 Bayesian task registration still depends on topology env: {forbidden}",
        )
    _require(
        tasks.count("@_bayesian_task(") >= 8,
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
    child_handler = worker_boot[
        worker_boot.index("def _on_bayesian_worker_process_init") : worker_boot.index(
            "def ensure_bayesian_worker_boot_probe_signal_registered"
        )
    ]
    _require(
        "_derive_bayesian_child_authority_if_needed()" in child_handler,
        "P9 worker_process_init must derive local child authority",
    )
    _require(
        "run_bayesian_worker_boot_topology_probe()" not in child_handler,
        "P9 worker_process_init must not run the physical DB probe",
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
        "dispatch_claim: BayesianDispatchClaim",
        "worker_authority: BayesianWorkerClaimAuthority",
        "bayesian_dispatch_claim_required",
        "claim_fit_dispatch_sync",
        "bind_dispatch_write_context_sync",
        "mark_dispatch_running_sync",
        "complete_dispatch_sync",
        "fail_dispatch_terminal_sync",
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


def validate_directive_ix_dispatch_authority(
    authority_text: str | None = None,
    outbox_text: str | None = None,
    tasks_text: str | None = None,
    beat_text: str | None = None,
    procfile_text: str | None = None,
    migration_text: str | None = None,
    models_text: str | None = None,
) -> None:
    authority = (
        authority_text if authority_text is not None else _read(DISPATCH_AUTHORITY)
    )
    outbox = outbox_text if outbox_text is not None else _read(DISPATCH_OUTBOX)
    tasks = tasks_text if tasks_text is not None else _read(TASKS_BAYESIAN)
    beat = beat_text if beat_text is not None else _read(BEAT_SCHEDULE)
    procfile = procfile_text if procfile_text is not None else _read(PROCFILE)
    migration = (
        migration_text
        if migration_text is not None
        else _read(P9_DIRECTIVE_IX_MIGRATION)
        + "\n"
        + _read(P9_DIRECTIVE_X_MIGRATION)
        + "\n"
        + _read(P9_DIRECTIVE_XIII_MIGRATION)
        + "\n"
        + _read(P9_DIRECTIVE_XIV_MIGRATION)
    )
    current_migration = (
        migration_text
        if migration_text is not None
        else _read(P9_DIRECTIVE_XIV_MIGRATION)
    )
    models = models_text if models_text is not None else _read(MODELS)
    for token in (
        "DispatchClaimOutcome",
        "ACQUIRED",
        "RECLAIMED",
        "ACTIVE_LEASE",
        "ALREADY_COMPLETED",
        "CANCELLED",
        "EXPIRED",
        "SUPERSEDED",
        "TERMINAL_FAILURE",
        "UNAUTHORIZED",
        "RETRYABLE_INFRASTRUCTURE_FAILURE",
        "BayesianDispatchClaim",
        "BayesianDispatchLease",
        "BayesianWorkerClaimAuthority",
        "dispatch_payload_hash",
        "claim_fit_dispatch_sync",
        "bind_dispatch_write_context_sync",
        "create_recovery_wakeups_sync",
        "fail_dispatch_recoverable_sync",
        "register_worker_process_authority_sync",
    ):
        _require(token in authority, f"Directive IX authority missing: {token}")
    for token in (
        "publish_capability_bound_dispatch",
        "publish_secret_free_dispatch",
        "publish_due_recovery_rows",
        "publish_due_recovery_rows_sync",
        "lease_due_recovery_rows_sync",
        "mark_recovery_published_sync",
        "mark_recovery_publish_failed_sync",
        "published_task_id",
        "DEFAULT_STALE_RECOVERY_PUBLISHING_SECONDS = 300",
        "app.b24_recovery_reconciler",
        "app.b24_dispatch_claim_access",
        "updated_at <= now() - (:stale_publishing_seconds * interval '1 second')",
        "assigned_worker_generation = NULL",
        "assignment_reason = 'recovery_shared_eligible'",
        '"dispatch_id": str(self.id)',
        '"attempt_id": str(self.attempt_id)',
        '"payload_hash": self.payload_hash',
        '"recovery_generation": str(self.recovery_generation)',
        "b24_create_fit_recovery_wakeups",
    ):
        _require(token in outbox, f"Directive IX outbox missing: {token}")
    _require(
        '"claim_capability": self.claim_capability' not in outbox,
        "Directive X broker payload must not carry claim capability",
    )
    for token in (
        "dispatch_id: str",
        "attempt_id: str",
        "payload_hash: str",
        "recovery_generation: str",
        "BayesianDispatchClaim",
        "dispatch_claim=claim",
        "worker_authority=worker_authority",
        "RECOVERY_RECONCILER_TASK_NAME",
        "RECOVERABLE_FAILURE_ACK_PROBE_TASK_NAME",
        "create_recovery_wakeups_sync(conn, batch_size=batch_size)",
        "publish_due_recovery_rows_sync(",
        "probe_recoverable_failure_ack",
        "fail_dispatch_recoverable_sync(",
        "bayesian_recoverable_failure_ack_probe",
        "bayesian_recovery_reconciler_completed",
        "recovery_published_task_ids",
        "fit_id: str",
    ):
        _require(token in tasks, f"Directive IX Celery task missing: {token}")
    _require(
        "claim_capability: str" not in tasks,
        "Directive X Celery task must not accept broker capability",
    )
    for token in (
        '"b24-p9-bayesian-recovery-reconciler"',
        '"task": "app.tasks.bayesian.reconcile_fit_recovery_wakeups"',
        '"queue": QUEUE_BAYESIAN',
        '"routing_key": f"{QUEUE_BAYESIAN}.task"',
        "B24_P9_RECOVERY_RECONCILE_INTERVAL_SECONDS",
        "B24_P9_RECOVERY_STALE_PUBLISHING_SECONDS",
        "SKELDIR_B24_P9_DISABLE_RECOVERY_RECONCILER_JOB",
    ):
        _require(token in beat, f"Directive XI beat schedule missing: {token}")
    for token in (
        "beat: cd backend && celery -A app.celery_app.celery_app beat",
        "worker_bayesian: cd backend && SKELDIR_CELERY_WORKER_ROLE=bayesian",
        "SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS=1",
        "--queues=bayesian",
    ):
        _require(token in procfile, f"Directive XI launch profile missing: {token}")
    for token in (
        "b24_worker_process_authority",
        "b24_register_worker_process_authority",
        "b24_next_active_worker_generation",
        "ORDER BY auth.registered_at DESC, auth.generation_id DESC",
        "b24_claim_fit_dispatch",
        "p_fit_id uuid",
        "p_worker_process_token text",
        "v_shared_recovery_eligible",
        "assignment_reason = 'recovery_shared_eligible'",
        "NOT COALESCE(",
        "v_row.assigned_worker_generation = p_worker_generation",
        "b24_current_dispatch_fence_valid",
        "b24_enforce_dispatch_fence",
        "trg_b24_dispatch_fence_fits",
        "trg_b24_dispatch_fence_artifacts",
        "b24_mark_fit_dispatch_running",
        "b24_complete_fit_dispatch",
        "b24_fail_fit_dispatch_terminal",
        "b24_fail_fit_dispatch_recoverable",
        "failure_ack_recovery_required",
        "recoverable_ack:",
        "b24_create_fit_recovery_wakeups",
        "b24_fit_recovery_outbox",
        "ENABLE ROW LEVEL SECURITY",
        "FORCE ROW LEVEL SECURITY",
        "b24_dispatch_fence_rejected",
    ):
        _require(token in migration, f"Directive IX migration missing: {token}")
    _require(
        "app.b24_dispatch_fence_required" not in current_migration,
        "Directive X fence enforcement must not depend on a caller-controlled GUC",
    )
    for token in (
        "claim_capability",
        "claim_capability_digest",
        "lease_capability_digest",
        "claim_epoch",
        "B24FitRecoveryOutbox",
        "B24WorkerProcessAuthority",
    ):
        _require(token in models, f"Directive IX models missing: {token}")
    for forbidden in (
        "def publish_fit_id_only",
        "def execute_fit_intent(self, *, fit_id: str)",
    ):
        _require(
            forbidden not in outbox + tasks,
            f"Directive IX stale authority remained: {forbidden}",
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
    p9_tests_text: str | None = None,
    p9_db_tests_text: str | None = None,
    p9_raw_db_tests_text: str | None = None,
    workflow_text: str | None = None,
    ci_workflow_text: str | None = None,
    b07_p5_timeout_test_text: str | None = None,
    required_status_text: str | None = None,
) -> None:
    tests = p9_tests_text if p9_tests_text is not None else _read(P9_TESTS)
    db_tests = p9_db_tests_text if p9_db_tests_text is not None else _read(P9_DB_TESTS)
    raw_db_tests = (
        p9_raw_db_tests_text
        if p9_raw_db_tests_text is not None
        else _read(P9_RAW_DB_TESTS)
    )
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
        "test_b24_p9_runtime_sync_dsn_preserves_security_query",
        "test_b24_p9_db_topology_policy_is_code_authority_not_dsn_proof",
        "test_b24_p9_unknown_topology_fails_closed_in_protected_mode",
        "test_b24_p9_opaque_hostname_requires_attestation_not_string_inference",
        "test_b24_p9_pooler_and_proxy_topologies_fail_closed",
        "test_b24_p9_boot_probe_is_physical_not_connectivity_only",
        "test_b24_p9_celery_worker_init_runs_boot_probe_before_ready_and_prerun",
        "test_b24_p9_non_bayesian_worker_registry_excludes_bayesian_tasks",
        "test_b24_p9_bayesian_registration_wires_tasks_and_boot_probe",
        "test_b24_p9_topology_env_alone_does_not_register_bayesian_tasks",
        "test_b24_p9_worker_role_registration_contradiction_fails_closed",
        "test_b24_p9_bayesian_task_entry_requires_process_local_boot_proof",
        "test_b24_p9_child_authority_payload_cannot_mint_execution",
        "test_b24_p9_parent_death_invalidates_child_authority",
        "test_b24_p9_bayesian_task_module_registry_gate_is_structural",
        "test_b24_p9_bayesian_tasks_use_nonpooled_worker_engine",
        "test_b24_p9_workspace_scopes_and_cleans_tenant_fit_hash_attempt",
        "test_b24_p9_compiledir_scopes_tenant_fit_hash_attempt",
        "test_b24_p9_child_env_is_allowlisted_without_parent_mutation",
        "test_b24_p9_artifact_ref_contains_tenant_authority",
        "test_b24_p9_fit_execution_wires_cleanup_and_payload_airgap",
        "test_b24_p9_directive_x_dispatch_authority_is_broker_independent",
        "test_b24_p9_directive_x_celery_task_rejects_broker_authority",
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
        "test_b24_p9_child_process_init_derives_authority_without_db_probe",
        "test_b24_p9_non_bayesian_registry_rejects_broker_misrouted_bayesian_task",
        "test_b24_p9_pool_poison_is_closed_and_replaced_without_manual_reset",
        "test_b24_p9_pg_stat_activity_backend_not_idle_in_transaction",
        "test_b24_p9_reset_failure_surface_replaced_by_invalidation_or_close",
        "test_b24_p9_representative_same_process_worker_path_exercises_db_lifecycle",
        "test_b24_p9_transaction_local_guc_clean_return_and_sequential_isolation",
        "test_b24_p9_db_proof_requires_explicit_flag_in_ci",
        "test_b24_p9_session_level_guc_poison_is_detected",
        "test_b24_p9_multi_transaction_task_flow_rebinds_each_transaction",
        "test_b24_p9_directive_ix_pre_tenant_claim_and_fence_runtime",
        "test_b24_p9_directive_xi_recovery_publication_assignment_runtime",
        "test_b24_p9_directive_xi_stale_publishing_recovery_quarantines",
        "test_b24_p9_directive_xiii_shared_recovery_claim_liveness",
        "test_b24_p9_directive_xiii_broker_backed_recovery_liveness",
        "test_b24_p9_directive_xiv_failure_ack_revokes_stale_authority",
        "test_b24_p9_directive_xiv_broker_backed_failure_ack_recovery",
        "test_b24_p9_directive_xv_live_beat_drives_failure_ack_recovery",
        "test_b24_p9_directive_xv_disabled_beat_schedule_blocks_recovery",
        "_beat_env",
        "_wait_for_broker_task_messages",
        "_max_broker_message_id",
        "pre_worker_beat_task_ids",
        "correlated_beat_messages",
        "task_id=recovery_task_id",
        "B24_P9_RECOVERY_RECONCILE_INTERVAL_SECONDS",
        "SKELDIR_B24_P9_DISABLE_RECOVERY_RECONCILER_JOB",
        "b24-p9-bayesian-recovery-reconciler",
        "beat",
        "--schedule",
        "celery_app.conf.task_always_eager = False",
        "assert celery_app.conf.task_always_eager is False",
        "bayesian_recoverable_failure_ack_probe",
        "bayesian_recovery_reconciler_completed",
        "bayesian_fit_intent_executed",
        "_assert_dispatch_state_remains",
        "failure_ack_recovery_required",
        "recovery_published_task_ids",
        "recovery_shared_eligible",
        "postgresql://",
        "memory://",
        "test_b24_p9_concurrent_tenant_isolation_db_and_runtime_surfaces",
        "bind_transaction_local_tenant",
        "assert_fresh_checkout_is_clean",
        "pg_stat_activity",
        "pg_advisory_lock",
        "CREATE TEMP TABLE p9_temp_poison",
        "B2.4-P9 protected CI requires SKELDIR_B24_P9_REQUIRE_DB_PROOFS=1",
        "SKELDIR_B24_P9_REQUIRE_DB_PROOFS",
        "SKELDIR_BAYESIAN_DB_TOPOLOGY",
        "SKELDIR_BAYESIAN_DB_BACKEND_AFFINITY",
        "connection_lifetime",
        "direct_postgres_ci_postgres15",
    ):
        _require(token in db_tests, f"P9 DB proof missing: {token}")
    for token in (
        "validate-b24-p9-worker-tenant-hygiene",
        "B2.4-P9 Worker Tenant Hygiene Proof",
        "B2.4-P5 PostgreSQL Runtime Proof",
        "test_b24_p9_worker_tenant_hygiene.py",
        "test_b24_p9_postgres_runtime.py",
        "test_b24_p9_raw_driver_postgres_runtime.py",
        "SKELDIR_B24_P9_REQUIRE_DB_PROOFS",
        "EXPECTED_RUNTIME_DB_USER: app_user",
        "SKELDIR_CELERY_WORKER_ROLE",
        "SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS",
        "SKELDIR_BAYESIAN_DB_TOPOLOGY",
        "SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION",
        "SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE",
        "SKELDIR_BAYESIAN_DB_BACKEND_AFFINITY",
        "connection_lifetime",
        "direct_postgres_ci_postgres15",
        "scripts/ci/validate_b24_p9_worker_tenant_hygiene.py --negative-control",
    ):
        _require(token in workflow, f"P9 workflow wiring missing: {token}")
    for token in (
        "DIRECTIVE_XVI_RAW_PSYCOPG_RUNTIME_ROLE_PROOF",
        "DIRECTIVE_XVI_RAW_ASYNCPG_REPRESENTATIVE_PROOF",
        "DIRECTIVE_XVI_SECURITY_DEFINER_DIRECT_ABUSE_PROOF",
        "DIRECTIVE_XVIII_CLASSIFIED_RAW_REJECTION_PROOF",
        "DIRECTIVE_XVIII_TARGET_PRESENT_ZERO_ROW_PROOF",
        "DIRECTIVE_XVIII_ASYNCPG_CLASSIFIED_POST_STATE_PROOF",
        "DIRECTIVE_XVIII_SECURITY_DEFINER_SIGNATURE_PROOF",
        "DIRECTIVE_XVIII_EXPLICIT_RUNTIME_ROLE_BINDING_PROOF",
        "FORBIDDEN_MALFORMED_SQLSTATES",
        '"42601"',
        '"42703"',
        '"42P01"',
        '"42883"',
        '"42804"',
        '"22P02"',
        '"25P02"',
        "exc.pgcode",
        "exc.diag",
        "exc.sqlstate",
        "_assert_psycopg_security_rejection",
        "_assert_asyncpg_security_rejection",
        "pytest.raises(asyncpg.PostgresError)",
        "get_migration_database_url",
        "psycopg2.connect(_migration_dsn())",
        "_target_present_fit_state",
        "target_present_reader",
        "post_state_verifier",
        "_assert_post_state_unchanged",
        "to_regprocedure",
        "_expected_runtime_db_user",
        'assert expected, "EXPECTED_RUNTIME_DB_USER must be explicitly bound in P9 CI"',
        "import psycopg2",
        "import asyncpg",
        "psycopg2.connect(_runtime_dsn())",
        "asyncpg.connect(async_dsn)",
        "cur.execute(sql, params)",
        "test_b24_p9_directive_xvi_raw_psycopg_runtime_role_rejects_hostile_sql",
        "test_b24_p9_directive_xvi_raw_asyncpg_representative_hostile_writes",
        "current_user",
        "rolsuper",
        "rolbypassrls",
        "pg_has_role(current_user, 'migration_owner', 'member')",
        "owns_protected_tables",
        "inherits_bypassrls",
        "INSERT INTO public.bayesian_model_fits",
        "UPDATE public.bayesian_model_fits",
        "INSERT INTO public.bayesian_artifacts",
        "INSERT INTO public.b24_fit_dispatch_outbox",
        "INSERT INTO public.b24_fit_recovery_outbox",
        "DELETE FROM public.bayesian_model_fits",
        "public.b24_claim_fit_dispatch",
        "public.b24_mark_fit_dispatch_running()",
        "public.b24_complete_fit_dispatch()",
        "public.b24_fail_fit_dispatch_terminal",
        "public.b24_fail_fit_dispatch_recoverable",
        "forged-process-token",
        "stale_recovery_claim",
        "wrong_pid_claim",
        "wrong_task_claim",
        "UPDATE 0",
    ):
        _require(token in raw_db_tests, f"P9 raw DB proof missing: {token}")
    for forbidden in (
        "pytest.raises(Exception)",
        '(os.getenv("EXPECTED_RUNTIME_DB_USER") or "app_user")',
        "except psycopg2.Error:\n            conn.rollback()\n            return",
    ):
        _require(
            forbidden not in raw_db_tests,
            f"P9 raw DB proof regressed to generic or implicit proof: {forbidden}",
        )
    for forbidden in (
        "from sqlalchemy",
        "import sqlalchemy",
        "create_engine",
        "Session",
        "text(",
        "claim_fit_dispatch_sync",
        "bind_dispatch_write_context_sync",
        "mark_dispatch_running_sync",
        "fail_dispatch_recoverable_sync",
    ):
        _require(
            forbidden not in raw_db_tests,
            f"P9 raw DB proof regressed to helper-mediated proof: {forbidden}",
        )
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
            "SKELDIR_CELERY_WORKER_ROLE",
            "SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS",
            "SKELDIR_BAYESIAN_DB_TOPOLOGY",
            "SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION",
            "SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE",
            "SKELDIR_BAYESIAN_DB_BACKEND_AFFINITY",
            "connection_lifetime",
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
        '"SKELDIR_BAYESIAN_DB_BACKEND_AFFINITY"',
        '"SKELDIR_CELERY_WORKER_ROLE"',
        '"SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS"',
        '"connection_lifetime"',
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
    validate_directive_ix_dispatch_authority()
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
            "topology_affinity_removed",
            lambda: validate_bayesian_worker_db_topology(
                _read(DB_TOPOLOGY).replace(
                    "SKELDIR_BAYESIAN_DB_BACKEND_AFFINITY",
                    "SKELDIR_BAYESIAN_DB_AFFINITY_REMOVED",
                )
            ),
            "affinity",
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
            "authority_payload_root_secret_reintroduced",
            lambda: validate_bayesian_worker_boot_probe(
                worker_boot_text=_read(WORKER_BOOT_PROBE).replace(
                    '"proof_elapsed_seconds": proof.proof_elapsed_seconds,',
                    '"authority_secret": proof.authority_secret,\n'
                    '        "proof_elapsed_seconds": proof.proof_elapsed_seconds,',
                )
            ),
            "root secret",
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
            "topology_env_task_registration_reintroduced",
            lambda: validate_bayesian_worker_boot_probe(
                tasks_text=_read(TASKS_BAYESIAN).replace(
                    "return bool(explicit)",
                    "return bool(explicit) or bool(os.getenv('SKELDIR_BAYESIAN_DB_TOPOLOGY'))",
                )
            ),
            "topology",
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
            "directive_ix_claim_outcome_removed",
            lambda: validate_directive_ix_dispatch_authority(
                authority_text=_read(DISPATCH_AUTHORITY).replace(
                    "ACTIVE_LEASE", "LEASE_ACTIVE_REMOVED"
                )
            ),
            "ACTIVE_LEASE",
        ),
        (
            "directive_ix_broker_capability_removed",
            lambda: validate_directive_ix_dispatch_authority(
                outbox_text=_read(DISPATCH_OUTBOX).replace(
                    '"recovery_generation": str(self.recovery_generation)',
                    '"recovery_generation": str(self.recovery_generation),\n'
                    '            "claim_capability": self.claim_capability',
                )
            ),
            "broker payload",
        ),
        (
            "directive_ix_db_fence_removed",
            lambda: validate_directive_ix_dispatch_authority(
                migration_text=_read(P9_DIRECTIVE_IX_MIGRATION)
                + "\n"
                + _read(P9_DIRECTIVE_X_MIGRATION)
                + "\n"
                + _read(P9_DIRECTIVE_XIII_MIGRATION)
                + "\n"
                + _read(P9_DIRECTIVE_XIV_MIGRATION)
                + "\nPERFORM set_config('app.b24_dispatch_fence_required', 'on', true);\n"
            ),
            "caller-controlled GUC",
        ),
        (
            "directive_x_worker_token_removed",
            lambda: validate_directive_ix_dispatch_authority(
                migration_text=(
                    _read(P9_DIRECTIVE_IX_MIGRATION)
                    + "\n"
                    + _read(P9_DIRECTIVE_X_MIGRATION)
                    + "\n"
                    + _read(P9_DIRECTIVE_XIII_MIGRATION)
                    + "\n"
                    + _read(P9_DIRECTIVE_XIV_MIGRATION)
                ).replace(
                    "p_worker_process_token text",
                    "p_worker_process_token_removed text",
                )
            ),
            "p_worker_process_token",
        ),
        (
            "directive_xiii_shared_recovery_removed",
            lambda: validate_directive_ix_dispatch_authority(
                outbox_text=_read(DISPATCH_OUTBOX).replace(
                    "recovery_shared_eligible",
                    "recovery_republish",
                ),
                migration_text=(
                    _read(P9_DIRECTIVE_IX_MIGRATION)
                    + "\n"
                    + _read(P9_DIRECTIVE_X_MIGRATION)
                    + "\n"
                    + _read(P9_DIRECTIVE_XIII_MIGRATION).replace(
                        "v_shared_recovery_eligible",
                        "v_specific_replacement_only",
                    )
                    + "\n"
                    + _read(P9_DIRECTIVE_XIV_MIGRATION)
                ),
            ),
            "recovery_shared_eligible",
        ),
        (
            "directive_xiv_recoverable_failure_api_removed",
            lambda: validate_directive_ix_dispatch_authority(
                authority_text=_read(DISPATCH_AUTHORITY).replace(
                    "fail_dispatch_recoverable_sync",
                    "fail_dispatch_recoverable_removed",
                ),
                migration_text=(
                    _read(P9_DIRECTIVE_IX_MIGRATION)
                    + "\n"
                    + _read(P9_DIRECTIVE_X_MIGRATION)
                    + "\n"
                    + _read(P9_DIRECTIVE_XIII_MIGRATION)
                    + "\n"
                    + _read(P9_DIRECTIVE_XIV_MIGRATION).replace(
                        "b24_fail_fit_dispatch_recoverable",
                        "b24_fail_fit_dispatch_recoverable_removed",
                    )
                ),
            ),
            "recoverable",
        ),
        (
            "directive_xiv_failure_ack_assignment_revocation_removed",
            lambda: validate_directive_ix_dispatch_authority(
                migration_text=(
                    _read(P9_DIRECTIVE_IX_MIGRATION)
                    + "\n"
                    + _read(P9_DIRECTIVE_X_MIGRATION)
                    + "\n"
                    + _read(P9_DIRECTIVE_XIII_MIGRATION)
                    + "\n"
                    + _read(P9_DIRECTIVE_XIV_MIGRATION).replace(
                        "failure_ack_recovery_required",
                        "initial_dispatch",
                    )
                ),
            ),
            "failure_ack",
        ),
        (
            "directive_xiv_recovery_task_correlation_removed",
            lambda: validate_directive_ix_dispatch_authority(
                outbox_text=_read(DISPATCH_OUTBOX).replace(
                    "published_task_id", "published_task_removed"
                ),
                tasks_text=_read(TASKS_BAYESIAN).replace(
                    "recovery_published_task_ids", "recovery_task_ids_removed"
                ),
            ),
            "published_task",
        ),
        (
            "directive_xiv_broker_failure_ack_proof_removed",
            lambda: validate_tests_and_ci(
                p9_db_tests_text=_read(P9_DB_TESTS).replace(
                    "test_b24_p9_directive_xiv_broker_backed_failure_ack_recovery",
                    "test_b24_p9_directive_xiv_broker_backed_failure_ack_removed",
                ),
                b07_p5_timeout_test_text=_read(B07_P5_TIMEOUT_RUNTIME_TEST),
                required_status_text=_read(REQUIRED_STATUS_CONTRACT),
                workflow_text=_read(WORKFLOW),
                ci_workflow_text=_read(CI_WORKFLOW),
            ),
            "failure_ack",
        ),
        (
            "directive_xv_live_beat_proof_removed",
            lambda: validate_tests_and_ci(
                p9_db_tests_text=_read(P9_DB_TESTS).replace(
                    "test_b24_p9_directive_xv_live_beat_drives_failure_ack_recovery",
                    "test_b24_p9_directive_xv_live_beat_removed",
                ),
                b07_p5_timeout_test_text=_read(B07_P5_TIMEOUT_RUNTIME_TEST),
                required_status_text=_read(REQUIRED_STATUS_CONTRACT),
                workflow_text=_read(WORKFLOW),
                ci_workflow_text=_read(CI_WORKFLOW),
            ),
            "live_beat",
        ),
        (
            "directive_xv_schedule_disabled_negative_control_removed",
            lambda: validate_tests_and_ci(
                p9_db_tests_text=_read(P9_DB_TESTS).replace(
                    "test_b24_p9_directive_xv_disabled_beat_schedule_blocks_recovery",
                    "test_b24_p9_directive_xv_disabled_beat_removed",
                ),
                b07_p5_timeout_test_text=_read(B07_P5_TIMEOUT_RUNTIME_TEST),
                required_status_text=_read(REQUIRED_STATUS_CONTRACT),
                workflow_text=_read(WORKFLOW),
                ci_workflow_text=_read(CI_WORKFLOW),
            ),
            "disabled_beat",
        ),
        (
            "directive_xv_broker_correlation_removed",
            lambda: validate_tests_and_ci(
                p9_db_tests_text=_read(P9_DB_TESTS).replace(
                    "_wait_for_broker_task_messages",
                    "broker_task_message_wait_removed",
                ),
                b07_p5_timeout_test_text=_read(B07_P5_TIMEOUT_RUNTIME_TEST),
                required_status_text=_read(REQUIRED_STATUS_CONTRACT),
                workflow_text=_read(WORKFLOW),
                ci_workflow_text=_read(CI_WORKFLOW),
            ),
            "broker",
        ),
        (
            "directive_xvi_raw_file_removed",
            lambda: validate_tests_and_ci(
                p9_raw_db_tests_text=_read(P9_RAW_DB_TESTS).replace(
                    "test_b24_p9_directive_xvi_raw_psycopg_runtime_role_rejects_hostile_sql",
                    "test_b24_p9_directive_xvi_raw_psycopg_removed",
                ),
                b07_p5_timeout_test_text=_read(B07_P5_TIMEOUT_RUNTIME_TEST),
                required_status_text=_read(REQUIRED_STATUS_CONTRACT),
                workflow_text=_read(WORKFLOW),
                ci_workflow_text=_read(CI_WORKFLOW),
            ),
            "raw_psycopg",
        ),
        (
            "directive_xvi_sqlalchemy_substitution",
            lambda: validate_tests_and_ci(
                p9_raw_db_tests_text=_read(P9_RAW_DB_TESTS).replace(
                    "import pytest",
                    "import pytest\nfrom sqlalchemy import create_engine",
                ),
                b07_p5_timeout_test_text=_read(B07_P5_TIMEOUT_RUNTIME_TEST),
                required_status_text=_read(REQUIRED_STATUS_CONTRACT),
                workflow_text=_read(WORKFLOW),
                ci_workflow_text=_read(CI_WORKFLOW),
            ),
            "helper-mediated",
        ),
        (
            "directive_xvi_role_hygiene_removed",
            lambda: validate_tests_and_ci(
                p9_raw_db_tests_text=_read(P9_RAW_DB_TESTS).replace(
                    "rolbypassrls",
                    "role_bypass_check_removed",
                ),
                b07_p5_timeout_test_text=_read(B07_P5_TIMEOUT_RUNTIME_TEST),
                required_status_text=_read(REQUIRED_STATUS_CONTRACT),
                workflow_text=_read(WORKFLOW),
                ci_workflow_text=_read(CI_WORKFLOW),
            ),
            "rolbypassrls",
        ),
        (
            "directive_xvi_asyncpg_removed",
            lambda: validate_tests_and_ci(
                p9_raw_db_tests_text=_read(P9_RAW_DB_TESTS).replace(
                    "asyncpg.connect(async_dsn)",
                    "asyncpg_connect_removed(async_dsn)",
                ),
                b07_p5_timeout_test_text=_read(B07_P5_TIMEOUT_RUNTIME_TEST),
                required_status_text=_read(REQUIRED_STATUS_CONTRACT),
                workflow_text=_read(WORKFLOW),
                ci_workflow_text=_read(CI_WORKFLOW),
            ),
            "asyncpg.connect",
        ),
        (
            "directive_xvi_workflow_omits_raw_file",
            lambda: validate_tests_and_ci(
                b07_p5_timeout_test_text=_read(B07_P5_TIMEOUT_RUNTIME_TEST),
                required_status_text=_read(REQUIRED_STATUS_CONTRACT),
                workflow_text=_read(WORKFLOW).replace(
                    " backend/tests/test_b24_p9_raw_driver_postgres_runtime.py",
                    "",
                ),
                ci_workflow_text=_read(CI_WORKFLOW),
            ),
            "raw_driver",
        ),
        (
            "directive_xviii_forbidden_sqlstate_guard_removed",
            lambda: validate_tests_and_ci(
                p9_raw_db_tests_text=_read(P9_RAW_DB_TESTS).replace(
                    "FORBIDDEN_MALFORMED_SQLSTATES",
                    "FORBIDDEN_SQLSTATE_GUARD_REMOVED",
                ),
                b07_p5_timeout_test_text=_read(B07_P5_TIMEOUT_RUNTIME_TEST),
                required_status_text=_read(REQUIRED_STATUS_CONTRACT),
                workflow_text=_read(WORKFLOW),
                ci_workflow_text=_read(CI_WORKFLOW),
            ),
            "FORBIDDEN_MALFORMED_SQLSTATES",
        ),
        (
            "directive_xviii_generic_asyncpg_exception_restored",
            lambda: validate_tests_and_ci(
                p9_raw_db_tests_text=_read(P9_RAW_DB_TESTS).replace(
                    "pytest.raises(asyncpg.PostgresError)",
                    "pytest.raises(Exception)",
                ),
                b07_p5_timeout_test_text=_read(B07_P5_TIMEOUT_RUNTIME_TEST),
                required_status_text=_read(REQUIRED_STATUS_CONTRACT),
                workflow_text=_read(WORKFLOW),
                ci_workflow_text=_read(CI_WORKFLOW),
            ),
            "pytest.raises(asyncpg.PostgresError)",
        ),
        (
            "directive_xviii_target_present_removed",
            lambda: validate_tests_and_ci(
                p9_raw_db_tests_text=_read(P9_RAW_DB_TESTS).replace(
                    "_target_present_fit_state",
                    "_fit_target_probe_removed",
                ),
                b07_p5_timeout_test_text=_read(B07_P5_TIMEOUT_RUNTIME_TEST),
                required_status_text=_read(REQUIRED_STATUS_CONTRACT),
                workflow_text=_read(WORKFLOW),
                ci_workflow_text=_read(CI_WORKFLOW),
            ),
            "_target_present_fit_state",
        ),
        (
            "directive_xviii_post_state_verifier_removed",
            lambda: validate_tests_and_ci(
                p9_raw_db_tests_text=_read(P9_RAW_DB_TESTS).replace(
                    "post_state_verifier",
                    "state_after_attack_check_removed",
                ),
                b07_p5_timeout_test_text=_read(B07_P5_TIMEOUT_RUNTIME_TEST),
                required_status_text=_read(REQUIRED_STATUS_CONTRACT),
                workflow_text=_read(WORKFLOW),
                ci_workflow_text=_read(CI_WORKFLOW),
            ),
            "post_state_verifier",
        ),
        (
            "directive_xviii_runtime_user_binding_removed",
            lambda: validate_tests_and_ci(
                workflow_text=_read(WORKFLOW).replace(
                    "      EXPECTED_RUNTIME_DB_USER: app_user\n",
                    "",
                ),
                b07_p5_timeout_test_text=_read(B07_P5_TIMEOUT_RUNTIME_TEST),
                required_status_text=_read(REQUIRED_STATUS_CONTRACT),
                ci_workflow_text=_read(CI_WORKFLOW),
            ),
            "EXPECTED_RUNTIME_DB_USER",
        ),
        (
            "directive_xviii_security_definer_signature_removed",
            lambda: validate_tests_and_ci(
                p9_raw_db_tests_text=_read(P9_RAW_DB_TESTS).replace(
                    "to_regprocedure",
                    "regproc_signature_probe_removed",
                ),
                b07_p5_timeout_test_text=_read(B07_P5_TIMEOUT_RUNTIME_TEST),
                required_status_text=_read(REQUIRED_STATUS_CONTRACT),
                workflow_text=_read(WORKFLOW),
                ci_workflow_text=_read(CI_WORKFLOW),
            ),
            "to_regprocedure",
        ),
        (
            "directive_ix_db_fence_rejection_removed",
            lambda: validate_directive_ix_dispatch_authority(
                migration_text=(
                    _read(P9_DIRECTIVE_IX_MIGRATION)
                    + "\n"
                    + _read(P9_DIRECTIVE_X_MIGRATION)
                    + "\n"
                    + _read(P9_DIRECTIVE_XIII_MIGRATION)
                    + "\n"
                    + _read(P9_DIRECTIVE_XIV_MIGRATION)
                ).replace(
                    "b24_dispatch_fence_rejected",
                    "b24_dispatch_fence_allowed",
                )
            ),
            "fence",
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
            "ci_backend_affinity_removed",
            lambda: validate_tests_and_ci(
                ci_workflow_text=_read(CI_WORKFLOW).replace(
                    "SKELDIR_BAYESIAN_DB_BACKEND_AFFINITY",
                    "SKELDIR_BAYESIAN_DB_AFFINITY_REMOVED",
                )
            ),
            "affinity",
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
