from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.pool import NullPool

from app.bayesian.artifact_repository import _artifact_ref
from app.bayesian.cleanup import cleanup_fit_attempt, run_preflight_janitor
from app.bayesian.compiledir_reaper import create_compiledir_lease
from app.bayesian.db_engine import create_bayesian_worker_engine
from app.bayesian.db_topology import resolve_bayesian_worker_db_topology_policy
from app.bayesian.fit_execution import _sampler_failure_stream_metadata
from app.bayesian.sampler_supervisor import (
    CapturedChildStream,
    SupervisedSamplerResult,
    build_child_env_for_lease,
    run_supervised_sampler,
    synthetic_blocking_child_command,
)
from app.bayesian.temp_workspace import (
    _is_owned_child_path as _workspace_child_path_is_owned,
    cleanup_workspace,
    create_workspace_lease,
    reap_expired_workspaces,
)


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts/ci/validate_b24_p9_worker_tenant_hygiene.py"
FIT_EXECUTION = ROOT / "backend/app/bayesian/fit_execution.py"
DB_ENGINE = ROOT / "backend/app/bayesian/db_engine.py"
DB_TOPOLOGY = ROOT / "backend/app/bayesian/db_topology.py"
DB_BOOT_PROBE = ROOT / "backend/app/bayesian/db_boot_probe.py"
WORKER_BOOT_PROBE = ROOT / "backend/app/bayesian/worker_boot_probe.py"
TASKS_BAYESIAN = ROOT / "backend/app/tasks/bayesian.py"
BEAT_SCHEDULE = ROOT / "backend/app/tasks/beat_schedule.py"
TENANT_CONTEXT = ROOT / "backend/app/bayesian/tenant_context.py"
DISPATCH_AUTHORITY = ROOT / "backend/app/bayesian/dispatch_authority.py"
DISPATCH_OUTBOX = ROOT / "backend/app/bayesian/dispatch_outbox.py"
PROCFILE = ROOT / "Procfile"
TEMP_WORKSPACE = ROOT / "backend/app/bayesian/temp_workspace.py"
CHILD_ENVIRONMENT = ROOT / "backend/app/bayesian/child_environment.py"
COMPILEDIR_REAPER = ROOT / "backend/app/bayesian/compiledir_reaper.py"
DIRECTIVE_IX_MIGRATION = ROOT / (
    "alembic/versions/007_skeldir_foundation/"
    "202606181200_b24_p9_directive_x_broker_independent_authority.py"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_b24_p9_worker_tenant_hygiene", VALIDATOR
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _clear_topology_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "CI",
        "ENVIRONMENT",
        "SKELDIR_BAYESIAN_DB_TOPOLOGY",
        "SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION",
        "SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE",
        "SKELDIR_BAYESIAN_DB_BACKEND_AFFINITY",
        "SKELDIR_BAYESIAN_DB_TOPOLOGY_REQUIRE_ATTESTATION",
    ):
        monkeypatch.delenv(name, raising=False)


def _representative_parent_worker_attempt(
    *,
    tenant_id,
    fit_id,
    source_hash: str,
    attempt_id: str,
    sentinel: str,
) -> dict[str, object]:
    parent_pid = os.getpid()
    workspace = create_workspace_lease(
        tenant_id=tenant_id,
        fit_id=fit_id,
        source_snapshot_hash=source_hash,
        execution_attempt_id=attempt_id,
    )
    compiledir = create_compiledir_lease(
        execution_id=attempt_id,
        worker_id="p9-reused-worker-proof",
        tenant_id=tenant_id,
        fit_id=fit_id,
        source_snapshot_hash=source_hash,
    )
    ipc_dir = workspace.path / "ipc"
    ipc_dir.mkdir(parents=True, exist_ok=False)
    (ipc_dir / "private_source_payload.txt").write_text(sentinel, encoding="utf-8")
    env = build_child_env_for_lease(
        compiledir,
        source_env={
            "PATH": os.environ.get("PATH", ""),
            "DATABASE_URL": f"postgresql://{sentinel}@must-not-leak/db",
            "PYTENSOR_FLAGS": "mode=FAST_RUN,base_compiledir=/tmp/global",
        },
    )
    artifact_ref = _artifact_ref(
        tenant_id=tenant_id,
        fit_id=fit_id,
        artifact_type="diagnostics",
        artifact_hash="d" * 64,
    )
    state = {
        "parent_pid": parent_pid,
        "tenant_id": str(tenant_id),
        "fit_id": str(fit_id),
        "workspace": str(workspace.path),
        "compiledir": str(compiledir.path),
        "artifact_ref": artifact_ref,
        "child_env_keys": sorted(env),
        "child_compiledir": env["B24_PYTENSOR_COMPILEDIR"],
        "pytensor_flags": env["PYTENSOR_FLAGS"],
    }
    cleanup_report = cleanup_fit_attempt(workspace=workspace, compiledir=compiledir)
    state["cleanup"] = cleanup_report.__dict__
    state["workspace_exists_after_cleanup"] = workspace.path.exists()
    state["compiledir_exists_after_cleanup"] = compiledir.path.exists()
    return state


def test_b24_p9_transaction_context_uses_set_local_only() -> None:
    text = _read(TENANT_CONTEXT)
    assert "bind_transaction_local_tenant" in text
    assert "set_config('app.current_tenant_id', :tenant_id, true)" in text
    assert "SELECT pg_backend_pid()" in text
    assert "bayesian_tenant_transaction_required" in text
    assert "bayesian_tenant_transaction_preexisting_tenant_guc" in text
    assert "bayesian_tenant_transaction_backend_continuity_lost" in text
    assert "tenant_transaction" in text
    assert "assert_fresh_checkout_is_clean" in text
    assert "set_config('app.current_tenant_id', :tenant_id, false)" not in text
    assert "lru_cache" not in text


def test_b24_p9_bayesian_worker_engine_factory_is_nonpooled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TESTING", "1")
    text = _read(DB_ENGINE)
    for token in (
        "create_bayesian_worker_engine",
        "poolclass=NullPool",
        "assert_bayesian_worker_engine_nonpooled",
        "bayesian_worker_engine_must_use_nullpool",
        "runtime_sync_database_url",
        "resolve_bayesian_worker_db_topology_policy",
    ):
        assert token in text
    engine = create_bayesian_worker_engine("sqlite://")
    try:
        assert isinstance(engine.pool, NullPool)
    finally:
        engine.dispose()


def test_b24_p9_runtime_sync_dsn_preserves_security_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.bayesian import db_engine

    monkeypatch.setattr(
        db_engine,
        "get_database_url",
        lambda: (
            "postgresql+asyncpg://app_user:app_user@db-main.skeldir.internal:5432"
            "/skeldir?sslmode=verify-full&sslrootcert=/etc/skeldir/ca.pem"
            "&channel_binding=require&application_name=bayesian-worker"
        ),
    )

    sync_url = db_engine.runtime_sync_database_url()

    assert sync_url.startswith("postgresql://")
    assert "sslmode=verify-full" in sync_url
    assert "sslrootcert=/etc/skeldir/ca.pem" in sync_url
    assert "channel_binding=require" in sync_url
    assert "application_name=bayesian-worker" in sync_url


def test_b24_p9_db_topology_policy_is_code_authority_not_dsn_proof() -> None:
    text = _read(DB_TOPOLOGY)
    for token in (
        "SKELDIR_BAYESIAN_DB_TOPOLOGY",
        "SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION",
        "SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE",
        "SKELDIR_BAYESIAN_DB_BACKEND_AFFINITY",
        "DIRECT_POSTGRES_ATTESTATIONS",
        "BayesianWorkerDBBackendAffinity",
        "CONNECTION_LIFETIME",
        "POOLER_NEGATIVE_CONTROL_TOKENS",
        "UNSUPPORTED_POOLER_TOPOLOGIES",
        "DSN contents are intentionally insufficient proof",
        "bayesian_worker_db_topology_missing",
        "bayesian_worker_db_topology_affinity_missing",
        "bayesian_worker_db_topology_proxy_dsn_rejected",
        "bayesian_worker_db_topology_pooler_unsupported",
    ):
        assert token in text


def test_b24_p9_unknown_topology_fails_closed_in_protected_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_topology_env(monkeypatch)
    monkeypatch.setenv("CI", "true")
    with pytest.raises(RuntimeError, match="bayesian_worker_db_topology_missing"):
        resolve_bayesian_worker_db_topology_policy(
            "postgresql://app_user:app_user@db-main.skeldir.internal:5432/skeldir"
        )

    monkeypatch.setenv("SKELDIR_BAYESIAN_DB_TOPOLOGY", "mystery_mesh")
    with pytest.raises(RuntimeError, match="bayesian_worker_db_topology_unknown"):
        resolve_bayesian_worker_db_topology_policy(
            "postgresql://app_user:app_user@db-main.skeldir.internal:5432/skeldir"
        )


def test_b24_p9_opaque_hostname_requires_attestation_not_string_inference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_topology_env(monkeypatch)
    opaque_dsn = "postgresql://app_user:app_user@db-main.skeldir.internal:5432/skeldir"
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SKELDIR_BAYESIAN_DB_TOPOLOGY", "direct_postgres")

    with pytest.raises(
        RuntimeError, match="bayesian_worker_db_topology_attestation_missing"
    ):
        resolve_bayesian_worker_db_topology_policy(opaque_dsn)

    monkeypatch.setenv(
        "SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION",
        "direct_postgres_deployment_attested",
    )
    monkeypatch.setenv(
        "SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE",
        "deployment_control_plane",
    )
    with pytest.raises(
        RuntimeError, match="bayesian_worker_db_topology_affinity_missing"
    ):
        resolve_bayesian_worker_db_topology_policy(opaque_dsn)
    monkeypatch.setenv("SKELDIR_BAYESIAN_DB_BACKEND_AFFINITY", "connection_lifetime")
    policy = resolve_bayesian_worker_db_topology_policy(opaque_dsn)
    assert policy.topology.value == "direct_postgres"
    assert policy.backend_affinity.value == "connection_lifetime"
    assert policy.protected_runtime is True
    assert policy.source == "deployment_control_plane"


def test_b24_p9_pooler_and_proxy_topologies_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_topology_env(monkeypatch)
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("SKELDIR_BAYESIAN_DB_TOPOLOGY", "pgbouncer_transaction")
    with pytest.raises(
        RuntimeError, match="bayesian_worker_db_topology_pooler_unsupported"
    ):
        resolve_bayesian_worker_db_topology_policy(
            "postgresql://app_user:app_user@db-main.skeldir.internal:5432/skeldir"
        )

    monkeypatch.setenv("SKELDIR_BAYESIAN_DB_TOPOLOGY", "direct_postgres")
    monkeypatch.setenv(
        "SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION",
        "direct_postgres_ci_postgres15",
    )
    monkeypatch.setenv("SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE", "github_actions")
    monkeypatch.setenv("SKELDIR_BAYESIAN_DB_BACKEND_AFFINITY", "connection_lifetime")
    with pytest.raises(
        RuntimeError, match="bayesian_worker_db_topology_proxy_dsn_rejected"
    ):
        resolve_bayesian_worker_db_topology_policy(
            "postgresql://app_user:app_user@pgbouncer.internal:6432/skeldir"
        )

    for affinity, error in (
        (
            "transaction_lifetime",
            "bayesian_worker_db_topology_transaction_pooling_unsupported",
        ),
        (
            "statement_lifetime",
            "bayesian_worker_db_topology_statement_pooling_unsupported",
        ),
    ):
        monkeypatch.setenv("SKELDIR_BAYESIAN_DB_BACKEND_AFFINITY", affinity)
        with pytest.raises(RuntimeError, match=error):
            resolve_bayesian_worker_db_topology_policy(
                "postgresql://app_user:app_user@db-main.skeldir.internal:5432/skeldir"
            )


def test_b24_p9_boot_probe_is_physical_not_connectivity_only() -> None:
    text = _read(DB_BOOT_PROBE)
    for token in (
        "run_bayesian_worker_boot_topology_probe",
        "create_bayesian_worker_engine",
        "set_config('app.current_tenant_id', :tenant_id, false)",
        "SET search_path TO pg_catalog",
        "pg_advisory_lock",
        "CREATE TEMP TABLE",
        "pg_stat_activity",
        "old_pid",
        "new_pid",
        "bayesian_worker_boot_topology_backend_not_replaced",
        "bayesian_worker_boot_topology_guc_poison_survived",
        "bayesian_worker_boot_topology_advisory_lock_survived",
        "bayesian_worker_boot_topology_temp_object_survived",
        "_wait_for_backend_absence",
    ):
        assert token in text
    assert "pymc" not in text
    assert "pytensor" not in text
    assert "arviz" not in text


def test_b24_p9_celery_worker_init_runs_boot_probe_before_ready_and_prerun() -> None:
    boot_probe = _read(WORKER_BOOT_PROBE)
    tasks = _read(TASKS_BAYESIAN)
    worker_init_idx = boot_probe.index("signals.worker_init.connect(")
    worker_process_init_idx = boot_probe.index("signals.worker_process_init.connect(")
    probe_call_idx = boot_probe.index(
        "_run_bayesian_worker_boot_topology_probe_if_needed()"
    )
    assert worker_init_idx > probe_call_idx
    assert worker_process_init_idx > probe_call_idx
    assert 'SystemExit("bayesian_worker_boot_topology_probe_failed")' in boot_probe
    assert "run_bayesian_worker_boot_topology_probe()" in boot_probe
    child_handler = boot_probe[
        boot_probe.index("def _on_bayesian_worker_process_init") : boot_probe.index(
            "def ensure_bayesian_worker_boot_probe_signal_registered"
        )
    ]
    assert "_derive_bayesian_child_authority_if_needed()" in child_handler
    assert "run_bayesian_worker_boot_topology_probe()" not in child_handler
    assert "bayesian_worker_boot_topology_probe_has_passed" in boot_probe
    assert "assert_bayesian_worker_boot_topology_proven" in boot_probe
    assert "BayesianWorkerGenerationProof" in boot_probe
    assert "BayesianWorkerExecutionAuthority" in boot_probe
    assert "BayesianWorkerGenerationClaims" in boot_probe
    assert "hmac.compare_digest" in boot_probe
    assert "BAYESIAN_CHILD_AUTHORITY_BUDGET_S" in boot_probe
    assert "SKELDIR_BAYESIAN_WORKER_GENERATION_AUTHORITY_FILE" in boot_probe
    assert "_persist_generation_authority_file" in boot_probe
    assert "_load_generation_authority_file" in boot_probe
    assert "bayesian_worker_generation_authority_payload_contains_secret" in boot_probe
    assert "bayesian_worker_generation_anchor_unavailable" in boot_probe
    assert "os.getppid() != proof.parent_pid" in boot_probe
    assert "QUEUE_BAYESIAN in explicit_queues" not in boot_probe
    assert "_parse_celery_queue_arguments" not in boot_probe
    assert "_worker_may_consume_bayesian_tasks" not in boot_probe
    assert "SKELDIR_BAYESIAN_BOOT_PROBE_REQUIRED" not in boot_probe
    assert "_BAYESIAN_TOPOLOGY_AUTHORITY_ENV" not in boot_probe
    assert "worker_ready" not in boot_probe
    assert "task_prerun" not in boot_probe
    assert "if _BAYESIAN_TASKS_REGISTERED:" in tasks
    assert "ensure_bayesian_worker_boot_probe_signal_registered()" in tasks
    assert tasks.count("assert_bayesian_worker_boot_topology_proven()") >= 6


def test_b24_p9_non_bayesian_worker_registry_excludes_bayesian_tasks() -> None:
    script = r"""
import json
from celery import signals
from app.celery_app import celery_app
from app.tasks import bayesian
celery_app.loader.import_default_modules()
tasks = sorted(celery_app.tasks.keys())
print(json.dumps({
    "include": list(celery_app.conf.include),
    "bayesian_module_imported": bayesian.__name__ == "app.tasks.bayesian",
    "bayesian_tasks_registered_for_process": bayesian._BAYESIAN_TASKS_REGISTERED,
    "bayesian_tasks": [task for task in tasks if task.startswith("app.tasks.bayesian.")],
    "worker_init_receiver_count": len(signals.worker_init.receivers),
    "worker_process_init_receiver_count": len(signals.worker_process_init.receivers),
}, sort_keys=True))
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "backend")
    env["SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS"] = "0"
    env["SKELDIR_CELERY_WORKER_ROLE"] = "non_bayesian"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
        timeout=20,
    )
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["bayesian_module_imported"] is True
    assert payload["bayesian_tasks_registered_for_process"] is False
    assert payload["bayesian_tasks"] == []


def test_b24_p9_bayesian_registration_wires_tasks_and_boot_probe() -> None:
    script = r"""
import json
from celery import signals
from app.celery_app import celery_app
from app.tasks import bayesian
celery_app.loader.import_default_modules()
tasks = sorted(celery_app.tasks.keys())
print(json.dumps({
    "bayesian_tasks_registered_for_process": bayesian._BAYESIAN_TASKS_REGISTERED,
    "bayesian_tasks": [task for task in tasks if task.startswith("app.tasks.bayesian.")],
    "worker_init_receiver_count": len(signals.worker_init.receivers),
    "worker_process_init_receiver_count": len(signals.worker_process_init.receivers),
}, sort_keys=True))
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "backend")
    env["SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS"] = "1"
    env["SKELDIR_CELERY_WORKER_ROLE"] = "bayesian"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
        timeout=20,
    )
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["bayesian_tasks_registered_for_process"] is True
    assert "app.tasks.bayesian.health_probe" in payload["bayesian_tasks"]
    assert payload["worker_init_receiver_count"] > 0
    assert payload["worker_process_init_receiver_count"] > 0


def test_b24_p9_topology_env_alone_does_not_register_bayesian_tasks() -> None:
    script = r"""
import json
from app.celery_app import celery_app
from app.tasks import bayesian
celery_app.loader.import_default_modules()
tasks = sorted(celery_app.tasks.keys())
print(json.dumps({
    "bayesian_tasks_registered_for_process": bayesian._BAYESIAN_TASKS_REGISTERED,
    "bayesian_tasks": [task for task in tasks if task.startswith("app.tasks.bayesian.")],
}, sort_keys=True))
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "backend")
    env.pop("SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS", None)
    env.pop("SKELDIR_CELERY_WORKER_ROLE", None)
    env["SKELDIR_BAYESIAN_DB_TOPOLOGY"] = "direct_postgres"
    env["SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION"] = "direct_postgres_ci_postgres15"
    env["SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE"] = "github_actions"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
        timeout=20,
    )
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["bayesian_tasks_registered_for_process"] is False
    assert payload["bayesian_tasks"] == []


def test_b24_p9_worker_role_registration_contradiction_fails_closed() -> None:
    script = (
        "from app.tasks import bayesian\nprint(bayesian._BAYESIAN_TASKS_REGISTERED)\n"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "backend")
    env["SKELDIR_CELERY_WORKER_ROLE"] = "bayesian"
    env["SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS"] = "0"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode != 0
    assert "bayesian_worker_role_registration_contradiction" in (
        result.stderr + result.stdout
    )


def test_b24_p9_bayesian_task_entry_requires_process_local_boot_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.bayesian import worker_boot_probe
    from app.tasks import bayesian

    class _Request:
        id = "p9-direct-entry-proof"

    class _Task:
        request = _Request()

    def _run_health_probe_entry() -> None:
        if hasattr(bayesian.health_probe, "run"):
            bayesian.health_probe.run(
                tenant_id="not-a-uuid",
                correlation_id="not-a-uuid",
            )
            return
        bayesian.health_probe(
            _Task(),
            tenant_id="not-a-uuid",
            correlation_id="not-a-uuid",
        )

    monkeypatch.setattr(worker_boot_probe, "_bayesian_worker_generation_proof", None)
    monkeypatch.setattr(worker_boot_probe, "_bayesian_execution_authority", None)
    with pytest.raises(
        worker_boot_probe.BayesianWorkerBootTopologyProofMissing,
        match="bayesian_worker_boot_topology_probe_required",
    ):
        _run_health_probe_entry()

    topology_fingerprint = worker_boot_probe._topology_authority_fingerprint()
    proof = worker_boot_probe.BayesianWorkerGenerationProof(
        generation_id="unit-generation",
        parent_pid=os.getpid(),
        topology_fingerprint=topology_fingerprint,
        authority_secret="unit-secret",
        proof_elapsed_seconds=0.01,
        worker_connection_count=2,
        observer_connection_count=2,
        created_monotonic=0.0,
    )
    stale_pid = os.getpid() + 1
    stale_authority = worker_boot_probe.BayesianWorkerExecutionAuthority(
        generation_id=proof.generation_id,
        pid=stale_pid,
        parent_pid=proof.parent_pid,
        topology_fingerprint=topology_fingerprint,
        token=worker_boot_probe._authority_token(
            proof,
            pid=stale_pid,
            topology_fingerprint=topology_fingerprint,
        ),
        issued_monotonic=0.0,
        derivation_elapsed_seconds=0.0,
    )
    monkeypatch.setattr(
        worker_boot_probe,
        "_bayesian_worker_generation_proof",
        proof,
    )
    monkeypatch.setattr(
        worker_boot_probe,
        "_bayesian_execution_authority",
        stale_authority,
    )
    with pytest.raises(
        worker_boot_probe.BayesianWorkerBootTopologyProofMissing,
        match="bayesian_worker_boot_topology_probe_required",
    ):
        _run_health_probe_entry()


def test_b24_p9_child_authority_payload_cannot_mint_execution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.bayesian import worker_boot_probe

    topology_fingerprint = worker_boot_probe._topology_authority_fingerprint()
    proof = worker_boot_probe.BayesianWorkerGenerationProof(
        generation_id="unit-generation-file",
        parent_pid=os.getpid(),
        topology_fingerprint=topology_fingerprint,
        authority_secret="unit-root-secret",
        proof_elapsed_seconds=0.01,
        worker_connection_count=2,
        observer_connection_count=2,
        created_monotonic=0.0,
    )
    monkeypatch.setenv(
        "SKELDIR_BAYESIAN_WORKER_GENERATION_AUTHORITY_DIR",
        str(tmp_path / "authority"),
    )
    worker_boot_probe._persist_generation_authority_file(proof)
    authority_path = Path(
        os.environ["SKELDIR_BAYESIAN_WORKER_GENERATION_AUTHORITY_FILE"]
    )
    payload = json.loads(authority_path.read_text(encoding="utf-8"))
    assert "authority_secret" not in payload

    monkeypatch.setattr(worker_boot_probe, "_bayesian_worker_generation_proof", None)
    monkeypatch.setattr(worker_boot_probe, "_bayesian_execution_authority", None)
    with pytest.raises(
        worker_boot_probe.BayesianWorkerBootTopologyProofMissing,
        match="bayesian_worker_generation_anchor_unavailable",
    ):
        worker_boot_probe._derive_process_authority_from_generation()

    payload["authority_secret"] = "attacker-controlled-secret"
    authority_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    with pytest.raises(
        worker_boot_probe.BayesianWorkerBootTopologyProofMissing,
        match="bayesian_worker_generation_authority_payload_contains_secret",
    ):
        worker_boot_probe._load_generation_authority_file()


def test_b24_p9_parent_death_invalidates_child_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.bayesian import worker_boot_probe

    topology_fingerprint = worker_boot_probe._topology_authority_fingerprint()
    proof = worker_boot_probe.BayesianWorkerGenerationProof(
        generation_id="unit-generation-parent-death",
        parent_pid=os.getpid() + 1000,
        topology_fingerprint=topology_fingerprint,
        authority_secret="unit-root-secret",
        proof_elapsed_seconds=0.01,
        worker_connection_count=2,
        observer_connection_count=2,
        created_monotonic=0.0,
    )
    authority = worker_boot_probe.BayesianWorkerExecutionAuthority(
        generation_id=proof.generation_id,
        pid=os.getpid(),
        parent_pid=proof.parent_pid,
        topology_fingerprint=topology_fingerprint,
        token=worker_boot_probe._authority_token(
            proof,
            pid=os.getpid(),
            topology_fingerprint=topology_fingerprint,
        ),
        issued_monotonic=0.0,
        derivation_elapsed_seconds=0.0,
    )
    monkeypatch.setattr(worker_boot_probe, "_bayesian_worker_generation_proof", proof)
    monkeypatch.setattr(worker_boot_probe, "_bayesian_execution_authority", authority)
    monkeypatch.setattr(worker_boot_probe.os, "getppid", lambda: 1)

    assert worker_boot_probe.bayesian_worker_boot_topology_probe_has_passed() is False


def test_b24_p9_bayesian_task_module_registry_gate_is_structural() -> None:
    tasks = _read(TASKS_BAYESIAN)
    assert "SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS" in tasks
    assert "SKELDIR_CELERY_WORKER_ROLE" in tasks
    assert "REQUIRED_BAYESIAN_TASK_NAMES" in tasks
    assert "_bayesian_tasks_registered_for_process" in tasks
    assert "_BAYESIAN_TASK_REGISTRATION_TOPOLOGY_ENV" not in tasks
    assert "SKELDIR_BAYESIAN_DB_TOPOLOGY" not in tasks
    assert "if _BAYESIAN_TASKS_REGISTERED:" in tasks
    assert "return celery_app.task(*task_args, **task_kwargs)" in tasks
    assert "@_bayesian_task(" in tasks
    assert "@celery_app.task(" not in tasks


def test_b24_p9_bayesian_tasks_use_nonpooled_worker_engine() -> None:
    text = _read(TASKS_BAYESIAN)
    assert "create_bayesian_worker_engine(" in text
    assert "runtime_sync_database_url()" in text
    assert "from sqlalchemy import create_engine" not in text
    assert "pool_size=1" not in text
    assert "max_overflow=0" not in text


def test_b24_p9_workspace_scopes_and_cleans_tenant_fit_hash_attempt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tenant_id = uuid4()
    fit_id = uuid4()
    source_hash = "a" * 64
    monkeypatch.setenv("B24_BAYESIAN_WORKSPACE_ROOT", str(tmp_path / "workspaces"))

    lease_a = create_workspace_lease(
        tenant_id=tenant_id,
        fit_id=fit_id,
        source_snapshot_hash=source_hash,
        execution_attempt_id="attempt-a",
    )
    lease_b = create_workspace_lease(
        tenant_id=tenant_id,
        fit_id=fit_id,
        source_snapshot_hash=source_hash,
        execution_attempt_id="attempt-b",
    )

    assert lease_a.path != lease_b.path
    assert str(tenant_id) in lease_a.path.parts
    assert str(fit_id) in lease_a.path.parts
    assert source_hash in lease_a.path.parts
    assert "attempt-a" in lease_a.path.parts
    assert json.loads(
        (lease_a.path / "skeldir_workspace_owner.json").read_text(encoding="utf-8")
    )["tenant_id"] == str(tenant_id)
    assert cleanup_workspace(lease_a) is True
    assert not lease_a.path.exists()

    with pytest.raises(ValueError, match="unsafe"):
        create_workspace_lease(
            tenant_id=tenant_id,
            fit_id=fit_id,
            source_snapshot_hash=source_hash,
            execution_attempt_id="../escape",
        )

    metadata_path = lease_b.path / "skeldir_workspace_owner.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["created_at"] = 1
    metadata["parent_pid"] = 99999999
    metadata_path.write_text(json.dumps(metadata, sort_keys=True), encoding="utf-8")
    report = reap_expired_workspaces(ttl_seconds=60, max_deletions=10)
    assert report["deleted"] >= 1
    assert not lease_b.path.exists()


def test_b24_p9_compiledir_scopes_tenant_fit_hash_attempt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tenant_id = uuid4()
    fit_id = uuid4()
    source_hash = "b" * 64
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "compiledirs"))

    lease_a = create_compiledir_lease(
        execution_id="attempt-a",
        worker_id="unit-worker",
        tenant_id=tenant_id,
        fit_id=fit_id,
        source_snapshot_hash=source_hash,
    )
    lease_b = create_compiledir_lease(
        execution_id="attempt-b",
        worker_id="unit-worker",
        tenant_id=tenant_id,
        fit_id=fit_id,
        source_snapshot_hash=source_hash,
    )

    assert lease_a.path != lease_b.path
    assert str(tenant_id) in lease_a.path.parts
    assert str(fit_id) in lease_a.path.parts
    assert source_hash in lease_a.path.parts
    assert "attempt-a" in lease_a.path.parts
    metadata = json.loads(
        (lease_a.path / "skeldir_compiledir_owner.json").read_text(encoding="utf-8")
    )
    assert metadata["tenant_id"] == str(tenant_id)
    assert metadata["fit_id"] == str(fit_id)
    assert metadata["source_snapshot_hash"] == source_hash


def test_b24_p9_child_env_is_allowlisted_without_parent_mutation(
    tmp_path: Path,
) -> None:
    from app.bayesian.child_environment import build_sampler_child_env

    parent_before = dict(os.environ)
    env = build_sampler_child_env(
        compiledir=tmp_path / "compiledir",
        execution_id="attempt-env",
        source_env={
            "PATH": os.environ.get("PATH", ""),
            "DATABASE_URL": "postgresql://must:not@leak/db",
            "B24_STAGE_MARKER_PATH": str(tmp_path / "marker.jsonl"),
            "PYTENSOR_FLAGS": "mode=FAST_RUN,base_compiledir=/tmp/global",
        },
    )

    assert os.environ == parent_before
    assert "DATABASE_URL" not in env
    assert env["B24_STAGE_MARKER_PATH"].endswith("marker.jsonl")
    assert env["B24_PYTENSOR_COMPILEDIR"] == str(tmp_path / "compiledir")
    assert env["PYTENSOR_FLAGS"].startswith(
        f"base_compiledir={(tmp_path / 'compiledir').as_posix()}"
    )
    assert "/tmp/global" not in env["PYTENSOR_FLAGS"]


def test_b24_p9_artifact_ref_contains_tenant_authority() -> None:
    tenant_id = uuid4()
    fit_id = uuid4()
    ref = _artifact_ref(
        tenant_id=tenant_id,
        fit_id=fit_id,
        artifact_type="diagnostics",
        artifact_hash="c" * 64,
    )
    assert ref == f"b24://artifact/{tenant_id}/{fit_id}/diagnostics/{'c' * 12}"


def test_b24_p9_fit_execution_wires_cleanup_and_payload_airgap() -> None:
    text = _read(FIT_EXECUTION)
    for token in (
        "run_preflight_janitor(",
        "assert_fresh_checkout_is_clean(engine)",
        "create_workspace_lease(",
        "create_compiledir_lease(",
        "tenant_id=tenant_id",
        "fit_id=fit_id",
        "source_snapshot_hash=source_snapshot_hash",
        "cleanup_fit_attempt(workspace=workspace, compiledir=lease)",
        "_sampler_failure_stream_metadata(result)",
        "stderr_retained_bytes",
        "stderr_truncated",
    ):
        assert token in text
    assert 'stderr_retained": result.stderr.retained_text' not in text
    assert "payload_json" not in _read(CHILD_ENVIRONMENT)


def test_b24_p9_directive_x_dispatch_authority_is_broker_independent() -> None:
    authority = _read(DISPATCH_AUTHORITY)
    outbox = _read(DISPATCH_OUTBOX)
    migration = _read(DIRECTIVE_IX_MIGRATION)
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
        "claim_fit_dispatch_sync",
        "bind_dispatch_write_context_sync",
        "register_worker_process_authority_sync",
    ):
        assert token in authority
    for token in (
        "publish_capability_bound_dispatch",
        "publish_secret_free_dispatch",
        "publish_due_recovery_rows",
        '"dispatch_id": str(self.id)',
        '"attempt_id": str(self.attempt_id)',
        '"payload_hash": self.payload_hash',
        '"recovery_generation": str(self.recovery_generation)',
        "b24_create_fit_recovery_wakeups",
    ):
        assert token in outbox
    assert '"claim_capability": self.claim_capability' not in outbox
    for token in (
        "b24_worker_process_authority",
        "b24_register_worker_process_authority",
        "b24_next_active_worker_generation",
        "b24_claim_fit_dispatch",
        "p_fit_id uuid",
        "p_worker_process_token text",
        "b24_current_dispatch_fence_valid",
        "b24_enforce_dispatch_fence",
        "b24_dispatch_fence_rejected",
        "b24_fit_recovery_outbox",
        "ENABLE ROW LEVEL SECURITY",
        "FORCE ROW LEVEL SECURITY",
    ):
        assert token in migration
    assert "app.b24_dispatch_fence_required" not in migration


def test_b24_p9_directive_x_celery_task_rejects_broker_authority() -> None:
    tasks = _read(TASKS_BAYESIAN)
    assert "BayesianDispatchClaim" in tasks
    assert "dispatch_claim=claim" in tasks
    assert "worker_authority=worker_authority" in tasks
    assert "recovery_generation: str" in tasks
    assert "claim_capability: str" not in tasks
    assert "payload_hash: str" in tasks
    assert "attempt_id: str" in tasks
    assert "dispatch_id: str" in tasks
    assert "def execute_fit_intent(self, *, fit_id: str)" not in tasks


def test_b24_p9_directive_xi_recovery_scheduler_is_production_wired() -> None:
    tasks = _read(TASKS_BAYESIAN)
    beat = _read(BEAT_SCHEDULE)
    outbox = _read(DISPATCH_OUTBOX)
    procfile = _read(PROCFILE)

    assert (
        'RECOVERY_RECONCILER_TASK_NAME = "app.tasks.bayesian.reconcile_fit_recovery_wakeups"'
        in tasks
    )
    assert "RECOVERY_RECONCILER_TASK_NAME" in tasks
    assert "create_recovery_wakeups_sync(conn, batch_size=batch_size)" in tasks
    assert "publish_due_recovery_rows_sync(" in tasks
    assert "assert_bayesian_worker_boot_topology_proven()" in tasks
    assert '"event_type": "bayesian.recovery"' in tasks

    assert '"b24-p9-bayesian-recovery-reconciler"' in beat
    assert '"task": "app.tasks.bayesian.reconcile_fit_recovery_wakeups"' in beat
    assert '"queue": QUEUE_BAYESIAN' in beat
    assert '"routing_key": f"{QUEUE_BAYESIAN}.task"' in beat
    assert "B24_P9_RECOVERY_RECONCILE_INTERVAL_SECONDS" in beat
    assert "B24_P9_RECOVERY_STALE_PUBLISHING_SECONDS" in beat
    assert "SKELDIR_B24_P9_DISABLE_RECOVERY_RECONCILER_JOB" in beat

    assert "DEFAULT_STALE_RECOVERY_PUBLISHING_SECONDS = 300" in outbox
    assert "publish_due_recovery_rows_sync" in outbox
    assert "lease_due_recovery_rows_sync" in outbox
    assert "mark_recovery_published_sync" in outbox
    assert "mark_recovery_publish_failed_sync" in outbox
    assert "status = 'publishing'" in outbox
    assert (
        "updated_at <= now() - (:stale_publishing_seconds * interval '1 second')"
        in outbox
    )
    assert '"claim_capability":' not in outbox
    assert '"lease_capability":' not in outbox
    assert "worker_process_token" not in outbox

    assert "beat: cd backend && celery -A app.celery_app.celery_app beat" in procfile
    assert (
        "worker_bayesian: cd backend && SKELDIR_CELERY_WORKER_ROLE=bayesian" in procfile
    )
    assert "SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS=1" in procfile


def test_b24_p9_same_process_sequential_reused_worker_runtime_lane(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("B24_BAYESIAN_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "compiledirs"))
    monkeypatch.setenv("B24_BAYESIAN_MAX_TASKS_PER_CHILD", "10")
    assert os.getenv("B24_BAYESIAN_MAX_TASKS_PER_CHILD") != "1"

    tenant_a = uuid4()
    tenant_b = uuid4()
    fit_a = uuid4()
    fit_b = uuid4()
    sentinel_a = "P9_TENANT_A_SENTINEL_SHOULD_NOT_REACH_B"
    sentinel_b = "P9_TENANT_B_SENTINEL"

    state_a = _representative_parent_worker_attempt(
        tenant_id=tenant_a,
        fit_id=fit_a,
        source_hash="a" * 64,
        attempt_id="attempt-a",
        sentinel=sentinel_a,
    )
    state_b = _representative_parent_worker_attempt(
        tenant_id=tenant_b,
        fit_id=fit_b,
        source_hash="b" * 64,
        attempt_id="attempt-b",
        sentinel=sentinel_b,
    )
    baseline_b = _representative_parent_worker_attempt(
        tenant_id=tenant_b,
        fit_id=fit_b,
        source_hash="b" * 64,
        attempt_id="attempt-b-baseline",
        sentinel=sentinel_b,
    )

    assert state_a["parent_pid"] == state_b["parent_pid"] == os.getpid()
    assert state_b["artifact_ref"] == baseline_b["artifact_ref"]
    assert state_a["workspace"] != state_b["workspace"]
    assert state_a["compiledir"] != state_b["compiledir"]
    assert state_b["child_compiledir"] == state_b["compiledir"]
    assert "/tmp/global" not in str(state_b["pytensor_flags"])
    assert state_b["cleanup"] == {
        "workspace_removed": True,
        "compiledir_removed": True,
    }
    assert state_b["workspace_exists_after_cleanup"] is False
    assert state_b["compiledir_exists_after_cleanup"] is False
    assert sentinel_a not in json.dumps(state_b, sort_keys=True)


def test_b24_p9_concurrent_tenant_isolation_runtime_surfaces(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("B24_BAYESIAN_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "compiledirs"))
    barrier = Barrier(2)
    tenant_a = uuid4()
    tenant_b = uuid4()
    fit_a = uuid4()
    fit_b = uuid4()

    def run_lane(label: str, tenant_id, fit_id, source_hash: str) -> dict[str, object]:
        workspace = create_workspace_lease(
            tenant_id=tenant_id,
            fit_id=fit_id,
            source_snapshot_hash=source_hash,
            execution_attempt_id=f"attempt-{label}",
        )
        compiledir = create_compiledir_lease(
            execution_id=f"attempt-{label}",
            worker_id="p9-concurrent-worker-proof",
            tenant_id=tenant_id,
            fit_id=fit_id,
            source_snapshot_hash=source_hash,
        )
        artifact_ref = _artifact_ref(
            tenant_id=tenant_id,
            fit_id=fit_id,
            artifact_type="diagnostics",
            artifact_hash=source_hash,
        )
        barrier.wait(timeout=5)
        workspace_cleanup = cleanup_fit_attempt(workspace=workspace, compiledir=None)
        compiledir_survived_workspace_cleanup = compiledir.path.exists()
        compiledir_cleanup = cleanup_fit_attempt(workspace=None, compiledir=compiledir)
        return {
            "label": label,
            "workspace": workspace.path,
            "compiledir": compiledir.path,
            "artifact_ref": artifact_ref,
            "workspace_removed": workspace_cleanup.workspace_removed,
            "compiledir_survived_workspace_cleanup": compiledir_survived_workspace_cleanup,
            "compiledir_removed": compiledir_cleanup.compiledir_removed,
        }

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(run_lane, "a", tenant_a, fit_a, "a" * 64)
        future_b = executor.submit(run_lane, "b", tenant_b, fit_b, "b" * 64)
        result_a = future_a.result(timeout=10)
        result_b = future_b.result(timeout=10)

    assert result_a["workspace"] != result_b["workspace"]
    assert result_a["compiledir"] != result_b["compiledir"]
    assert result_a["artifact_ref"] != result_b["artifact_ref"]
    assert result_a["workspace_removed"] is True
    assert result_b["workspace_removed"] is True
    assert result_a["compiledir_survived_workspace_cleanup"] is True
    assert result_b["compiledir_survived_workspace_cleanup"] is True
    assert result_a["compiledir_removed"] is True
    assert result_b["compiledir_removed"] is True


def test_b24_p9_concurrent_janitor_toctou_safe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("B24_BAYESIAN_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "compiledirs"))
    stale_workspace = create_workspace_lease(
        tenant_id=uuid4(),
        fit_id=uuid4(),
        source_snapshot_hash="e" * 64,
        execution_attempt_id="stale-workspace",
    )
    stale_compiledir = create_compiledir_lease(
        execution_id="stale-compiledir",
        worker_id="p9-janitor",
        tenant_id=uuid4(),
        fit_id=uuid4(),
        source_snapshot_hash="f" * 64,
    )
    for metadata_path in (
        stale_workspace.path / "skeldir_workspace_owner.json",
        stale_compiledir.path / "skeldir_compiledir_owner.json",
    ):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["created_at"] = 1
        metadata["parent_pid"] = 99999999
        metadata_path.write_text(json.dumps(metadata, sort_keys=True), encoding="utf-8")

    with ThreadPoolExecutor(max_workers=4) as executor:
        reports = list(
            executor.map(
                lambda _: run_preflight_janitor(
                    ttl_seconds=0,
                    max_deletions=10,
                    max_scan_entries=20,
                ),
                range(4),
            )
        )

    assert not stale_workspace.path.exists()
    assert not stale_compiledir.path.exists()
    assert sum(int(report["workspaces"]["deleted"]) for report in reports) >= 1
    assert sum(int(report["compiledirs"]["deleted"]) for report in reports) >= 1
    assert any(
        report["workspaces"]["lock_contended"]
        or report["compiledirs"]["lock_contended"]
        or report["workspaces"]["deleted"]
        or report["compiledirs"]["deleted"]
        for report in reports
    )

    outside = tmp_path / "outside"
    outside.mkdir()
    outside_metadata_dir = outside / "owned-looking"
    outside_metadata_dir.mkdir()
    (outside_metadata_dir / "skeldir_workspace_owner.json").write_text(
        json.dumps(
            {"owner": "skeldir-b24-p9", "created_at": 1, "parent_pid": 99999999}
        ),
        encoding="utf-8",
    )
    symlink = tmp_path / "workspaces" / "symlinked-outside"
    try:
        symlink.symlink_to(outside_metadata_dir, target_is_directory=True)
    except OSError:
        return
    assert _workspace_child_path_is_owned(tmp_path / "workspaces", symlink) is False
    report = run_preflight_janitor(ttl_seconds=0, max_deletions=10, max_scan_entries=20)
    assert outside_metadata_dir.exists()
    assert report["workspaces"]["deleted"] == 0


def test_b24_p9_logs_and_failure_payloads_do_not_emit_sentinels() -> None:
    sentinel_a = "P9_RAW_TENANT_A_STDERR_SENTINEL"
    sentinel_b = "P9_RAW_TENANT_B_STDOUT_SENTINEL"
    result = SupervisedSamplerResult(
        status="completed",
        child_pid=12345,
        elapsed_seconds=0.01,
        killed_by_supervisor=False,
        returncode=2,
        orphan_reaped=True,
        stdout=CapturedChildStream(
            retained_bytes=sentinel_b.encode("utf-8"),
            total_bytes=len(sentinel_b),
            truncated=False,
        ),
        stderr=CapturedChildStream(
            retained_bytes=sentinel_a.encode("utf-8"),
            total_bytes=len(sentinel_a),
            truncated=False,
        ),
    )
    payload = _sampler_failure_stream_metadata(result)
    encoded = json.dumps(payload, sort_keys=True)
    assert sentinel_a not in encoded
    assert sentinel_b not in encoded
    assert payload == {
        "stdout_total_bytes": len(sentinel_b),
        "stdout_retained_bytes": len(sentinel_b),
        "stdout_truncated": False,
        "stderr_total_bytes": len(sentinel_a),
        "stderr_retained_bytes": len(sentinel_a),
        "stderr_truncated": False,
    }


def test_b24_p9_native_memory_lifecycle_child_per_fit_parent_airgap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "compiledirs"))
    forbidden_native_modules = {"pymc", "pytensor", "arviz"}
    assert forbidden_native_modules.isdisjoint(sys.modules)
    lease = create_compiledir_lease(
        execution_id="native-child-per-fit",
        worker_id="p9-native-lifecycle",
        tenant_id=uuid4(),
        fit_id=uuid4(),
        source_snapshot_hash="9" * 64,
    )
    result = run_supervised_sampler(
        synthetic_blocking_child_command(seconds=5),
        deadline_seconds=0.2,
        env=build_child_env_for_lease(
            lease,
            source_env={
                "PATH": os.environ.get("PATH", ""),
                "PYTHONPATH": str(ROOT / "backend"),
            },
        ),
        compiledir_lease=lease,
    )
    assert result.child_pid != os.getpid()
    assert result.killed_by_supervisor is True
    assert result.orphan_reaped is True
    assert not lease.path.exists()
    assert forbidden_native_modules.isdisjoint(sys.modules)


def test_b24_p9_validator_negative_controls() -> None:
    validator = _load_validator()
    validator.validate_all()
    validator.run_negative_controls()
