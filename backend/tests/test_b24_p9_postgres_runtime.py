from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.pool import NullPool

from app.bayesian.artifact_repository import _artifact_ref, persist_artifact_sync
from app.bayesian.cleanup import cleanup_fit_attempt
from app.bayesian.compiledir_reaper import create_compiledir_lease
from app.bayesian.db_boot_probe import (
    BayesianWorkerBootTopologyProbeError,
    run_bayesian_worker_boot_topology_probe,
)
from app.bayesian.db_engine import create_bayesian_worker_engine
from app.bayesian.db_topology import resolve_bayesian_worker_db_topology_policy
from app.bayesian.dispatch_authority import (
    BAYESIAN_FIT_EXECUTION_TASK,
    BayesianDispatchClaim,
    BayesianDispatchLease,
    BayesianWorkerClaimAuthority,
    DispatchClaimOutcome,
    claim_fit_dispatch_sync,
    dispatch_payload_hash,
    register_worker_process_authority_sync,
)
from app.bayesian.enums import FallbackReason, FitStatus
from app.bayesian.fit_execution import (
    _load_fit_for_execution,
    _mark_fit_failure,
    _persist_result_summary,
    _set_tenant_context,
)
from app.bayesian.model_spec import B24_P6_MODEL_TYPE, B24_P6_MODEL_VERSION
from app.bayesian.sampler_supervisor import (
    build_child_env_for_lease,
    run_supervised_sampler,
    synthetic_blocking_child_command,
)
from app.bayesian.temp_workspace import create_workspace_lease
from app.bayesian.tenant_context import (
    assert_bound_tenant,
    assert_fresh_checkout_is_clean,
    bind_transaction_local_tenant,
    current_tenant_guc,
)
from app.core.secrets import get_database_url
from app.db.dsn import to_sync_postgres_dsn
from app.db.session import engine, get_session


START = datetime(2026, 5, 1, tzinfo=timezone.utc)
END = datetime(2026, 6, 1, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[2]


def _require_db_proofs() -> bool:
    return os.getenv("SKELDIR_B24_P9_REQUIRE_DB_PROOFS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _is_ci() -> bool:
    return os.getenv("CI", "").strip().lower() == "true"


pytestmark = pytest.mark.skipif(
    not _require_db_proofs() and not _is_ci(),
    reason="B2.4-P9 PostgreSQL proof is opt-in for local runs",
)


def _require_protected_db_mode() -> None:
    if _require_db_proofs():
        return
    if _is_ci():
        pytest.fail("B2.4-P9 protected CI requires SKELDIR_B24_P9_REQUIRE_DB_PROOFS=1")
    pytest.skip("B2.4-P9 PostgreSQL proof is opt-in for local runs")


async def _assert_table_exists(table_name: str) -> None:
    _require_protected_db_mode()
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT to_regclass(:qualified_name)"),
                {"qualified_name": f"public.{table_name}"},
            )
    except OperationalError as exc:
        message = f"B2.4-P9 PostgreSQL runtime proof unavailable: {exc}"
        if _require_db_proofs() or _is_ci():
            pytest.fail(message)
        pytest.skip(message)
    if result.scalar() is None:
        message = f"B2.4-P9 PostgreSQL runtime proof table is missing: {table_name}"
        if _require_db_proofs() or _is_ci():
            pytest.fail(message)
        pytest.skip(message)


async def _insert_fit(tenant_id: UUID, *, fit_id: UUID, source_hash: str) -> None:
    async with get_session(tenant_id) as session:
        await session.execute(
            text(
                """
                INSERT INTO public.bayesian_model_fits (
                    tenant_id,
                    id,
                    model_type,
                    model_version,
                    source_window_start,
                    source_window_end,
                    source_snapshot_hash,
                    status,
                    eligibility_status,
                    data_completeness_status,
                    fallback_applied,
                    max_runtime_seconds,
                    max_samples,
                    max_cores
                )
                VALUES (
                    :tenant_id,
                    :fit_id,
                    :model_type,
                    :model_version,
                    :source_window_start,
                    :source_window_end,
                    :source_snapshot_hash,
                    'queued',
                    'eligible',
                    'complete',
                    false,
                    60,
                    160,
                    1
                )
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "fit_id": str(fit_id),
                "model_type": B24_P6_MODEL_TYPE,
                "model_version": B24_P6_MODEL_VERSION,
                "source_window_start": START,
                "source_window_end": END,
                "source_snapshot_hash": source_hash,
            },
        )


def _register_test_worker_authority(
    conn,
    *,
    generation_id: str = "directive-x-runtime-generation",
    pid: int = 4242,
    process_token: str = "directive-x-runtime-process-token-0001",
) -> BayesianWorkerClaimAuthority:
    register_worker_process_authority_sync(
        conn,
        generation_id=generation_id,
        pid=pid,
        parent_pid=1,
        topology_fingerprint="b" * 64,
        process_token=process_token,
        ttl_seconds=3600,
    )
    return BayesianWorkerClaimAuthority(
        generation_id=generation_id,
        pid=pid,
        process_token=process_token,
    )


def _sync_database_url() -> str:
    return to_sync_postgres_dsn(get_database_url())


def _observer_engine():
    return create_engine(_sync_database_url(), isolation_level="AUTOCOMMIT")


def _worker_env(*, include_bayesian_tasks: bool, log_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["C_FORCE_ROOT"] = "true"
    multiproc_dir = log_path.parent / "prometheus_multiproc"
    multiproc_dir.mkdir(parents=True, exist_ok=True)
    env["PROMETHEUS_MULTIPROC_DIR"] = str(multiproc_dir)
    env["SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS"] = (
        "1" if include_bayesian_tasks else "0"
    )
    env["SKELDIR_CELERY_WORKER_ROLE"] = (
        "bayesian" if include_bayesian_tasks else "non_bayesian"
    )
    env["SKELDIR_B24_P9_REQUIRE_DB_PROOFS"] = "1"
    env["SKELDIR_BAYESIAN_DB_TOPOLOGY"] = "direct_postgres"
    env["SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION"] = "direct_postgres_ci_postgres15"
    env["SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE"] = "github_actions_postgres_15_alpine"
    env["SKELDIR_BAYESIAN_DB_BACKEND_AFFINITY"] = "connection_lifetime"
    env["BAYESIAN_PROBE_LOG_PATH"] = str(log_path)
    return env


def _terminate_worker(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _read_log(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _wait_for_log(path: Path, token: str, *, timeout_s: float = 20.0) -> str:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        text = _read_log(path)
        if token in text:
            return text
        time.sleep(0.25)
    return _read_log(path)


def _backend_state(observer, pid: int) -> dict[str, object] | None:
    row = (
        observer.execute(
            text(
                """
                SELECT state, xact_start, backend_xid, backend_xmin
                FROM pg_stat_activity
                WHERE pid = :pid
                """
            ),
            {"pid": int(pid)},
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row is not None else None


def _assert_backend_absent_or_not_idle_in_transaction(observer, pid: int) -> None:
    state = _backend_state(observer, pid)
    if state is None:
        return
    assert state["state"] != "idle in transaction"
    assert state["xact_start"] is None
    assert state["backend_xid"] is None
    assert state["backend_xmin"] is None


def _poison_one_worker_backend(worker_engine, *, tenant_id: UUID) -> int:
    lock_key = int(tenant_id.int % 2_147_483_647)
    with worker_engine.connect() as conn:
        pid = int(conn.execute(text("SELECT pg_backend_pid()")).scalar_one())
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)},
        )
        conn.execute(text("SET search_path TO pg_catalog"))
        conn.execute(text("SELECT pg_advisory_lock(:lock_key)"), {"lock_key": lock_key})
        conn.execute(text("CREATE TEMP TABLE p9_temp_poison(value integer)"))
        conn.execute(text("INSERT INTO p9_temp_poison(value) VALUES (1)"))
        conn.commit()
        assert current_tenant_guc(conn) == str(tenant_id)
    return pid


def _assert_fresh_worker_backend_is_clean(
    worker_engine, *, old_pid: int, lock_key: int
) -> int:
    with worker_engine.connect() as conn:
        new_pid = int(conn.execute(text("SELECT pg_backend_pid()")).scalar_one())
        assert new_pid != old_pid
        assert current_tenant_guc(conn) is None
        search_path = str(conn.execute(text("SHOW search_path")).scalar_one())
        assert search_path != "pg_catalog"
        temp_table = conn.execute(
            text("SELECT to_regclass('pg_temp.p9_temp_poison')")
        ).scalar_one_or_none()
        assert temp_table is None
        lock_acquired = bool(
            conn.execute(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": int(lock_key)},
            ).scalar_one()
        )
        assert lock_acquired is True
        conn.execute(
            text("SELECT pg_advisory_unlock(:lock_key)"),
            {"lock_key": int(lock_key)},
        )
    return new_pid


def _representative_worker_db_lifecycle_attempt(
    worker_engine,
    *,
    tenant_id: UUID,
    fit_id: UUID,
    source_hash: str,
    attempt_id: str,
    sentinel: str,
) -> dict[str, object]:
    parent_pid = os.getpid()
    workspace = None
    compiledir = None
    artifact_ref = None
    try:
        with worker_engine.begin() as conn:
            bind_transaction_local_tenant(conn, tenant_id=tenant_id)
            assert_bound_tenant(conn, tenant_id=tenant_id)
            updated = conn.execute(
                text(
                    """
                    UPDATE public.bayesian_model_fits
                    SET status = 'running',
                        sampling_started_at = COALESCE(sampling_started_at, now()),
                        updated_at = now()
                    WHERE tenant_id = :tenant_id
                      AND id = :fit_id
                      AND status = 'queued'
                    """
                ),
                {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
            )
            assert int(updated.rowcount or 0) == 1

        workspace = create_workspace_lease(
            tenant_id=tenant_id,
            fit_id=fit_id,
            source_snapshot_hash=source_hash,
            execution_attempt_id=attempt_id,
        )
        compiledir = create_compiledir_lease(
            execution_id=attempt_id,
            worker_id="p9-db-representative-worker",
            tenant_id=tenant_id,
            fit_id=fit_id,
            source_snapshot_hash=source_hash,
        )
        ipc_dir = workspace.path / "ipc"
        ipc_dir.mkdir(parents=True, exist_ok=False)
        (ipc_dir / "private_sentinel.txt").write_text(sentinel, encoding="utf-8")
        result = run_supervised_sampler(
            synthetic_blocking_child_command(seconds=5),
            deadline_seconds=0.2,
            env=build_child_env_for_lease(
                compiledir,
                source_env={
                    "PATH": os.environ.get("PATH", ""),
                    "PYTHONPATH": str(ROOT / "backend"),
                    "DATABASE_URL": f"postgresql://{sentinel}@must-not-leak/db",
                    "PYTENSOR_FLAGS": "mode=FAST_RUN,base_compiledir=/tmp/global",
                },
            ),
            compiledir_lease=compiledir,
            cleanup_compiledir_on_exit=False,
        )
        assert result.child_pid != parent_pid
        assert result.killed_by_supervisor is True
        assert result.orphan_reaped is True

        diagnostic_payload = {
            "diagnostic_status": "unavailable",
            "credible_interval_status": "not_available",
            "stderr_total_bytes": result.stderr.total_bytes,
            "stdout_total_bytes": result.stdout.total_bytes,
            "child_pid_recorded": result.child_pid,
        }
        with worker_engine.begin() as conn:
            bind_transaction_local_tenant(conn, tenant_id=tenant_id)
            artifact = persist_artifact_sync(
                conn,
                tenant_id=tenant_id,
                fit_id=fit_id,
                artifact_type="diagnostics",
                payload=diagnostic_payload,
                retention_class="standard",
            )
            artifact_ref = str(artifact["artifact_ref"])
            assert_bound_tenant(conn, tenant_id=tenant_id)

        with worker_engine.begin() as conn:
            _mark_fit_failure(
                conn,
                tenant_id=tenant_id,
                fit_id=fit_id,
                status=FitStatus.FAILED,
                fallback_reason=FallbackReason.WORKER_FAILURE,
                runtime_seconds=1,
            )
            assert_bound_tenant(conn, tenant_id=tenant_id)
    finally:
        cleanup = cleanup_fit_attempt(workspace=workspace, compiledir=compiledir)

    with worker_engine.begin() as conn:
        bind_transaction_local_tenant(conn, tenant_id=tenant_id)
        fit_row = (
            conn.execute(
                text(
                    """
                    SELECT status, fallback_applied, fallback_reason
                    FROM public.bayesian_model_fits
                    WHERE tenant_id = :tenant_id AND id = :fit_id
                    """
                ),
                {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
            )
            .mappings()
            .one()
        )
        artifact_count = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.bayesian_artifacts
                    WHERE tenant_id = :tenant_id
                      AND fit_id = :fit_id
                      AND artifact_ref = :artifact_ref
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "fit_id": str(fit_id),
                    "artifact_ref": artifact_ref,
                },
            ).scalar_one()
        )
    return {
        "parent_pid": parent_pid,
        "tenant_id": str(tenant_id),
        "fit_id": str(fit_id),
        "artifact_ref": artifact_ref,
        "fit": dict(fit_row),
        "artifact_count": artifact_count,
        "workspace": str(workspace.path) if workspace is not None else None,
        "compiledir": str(compiledir.path) if compiledir is not None else None,
        "workspace_removed": cleanup.workspace_removed,
        "compiledir_removed": cleanup.compiledir_removed,
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_bayesian_worker_engine_uses_nullpool_structural_sanitation() -> (
    None
):
    await _assert_table_exists("bayesian_model_fits")
    worker_engine = create_bayesian_worker_engine(_sync_database_url())
    try:
        assert isinstance(worker_engine.pool, NullPool)
        assert assert_fresh_checkout_is_clean(worker_engine).is_clean
    finally:
        worker_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_direct_topology_attestation_precedes_backend_pid_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    monkeypatch.setenv("SKELDIR_BAYESIAN_DB_TOPOLOGY", "direct_postgres")
    monkeypatch.setenv(
        "SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION",
        "direct_postgres_ci_postgres15",
    )
    monkeypatch.setenv(
        "SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE",
        "github_actions_postgres_15_alpine",
    )
    monkeypatch.setenv("SKELDIR_BAYESIAN_DB_BACKEND_AFFINITY", "connection_lifetime")
    worker_url = _sync_database_url()
    policy = resolve_bayesian_worker_db_topology_policy(
        worker_url, require_attestation=True
    )
    assert policy.topology.value == "direct_postgres"
    assert policy.attestation == "direct_postgres_ci_postgres15"
    worker_engine = create_bayesian_worker_engine(worker_url)
    try:
        with worker_engine.connect() as conn:
            first_pid = int(conn.execute(text("SELECT pg_backend_pid()")).scalar_one())
        with worker_engine.connect() as conn:
            second_pid = int(conn.execute(text("SELECT pg_backend_pid()")).scalar_one())
        assert second_pid != first_pid
        assert assert_fresh_checkout_is_clean(worker_engine).is_clean
    finally:
        worker_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_boot_probe_physically_proves_session_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    monkeypatch.setenv("SKELDIR_BAYESIAN_DB_TOPOLOGY", "direct_postgres")
    monkeypatch.setenv(
        "SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION",
        "direct_postgres_ci_postgres15",
    )
    monkeypatch.setenv(
        "SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE",
        "github_actions_postgres_15_alpine",
    )
    monkeypatch.setenv("SKELDIR_BAYESIAN_DB_BACKEND_AFFINITY", "connection_lifetime")

    result = run_bayesian_worker_boot_topology_probe(
        _sync_database_url(),
        timeout_seconds=5.0,
    )

    assert result.old_pid != result.new_pid
    assert result.lock_key > 0
    assert result.temp_table_name.startswith("p9_boot_probe_poison_")
    assert result.elapsed_seconds >= 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_boot_probe_failure_is_fatal_before_task_consumption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    from app.bayesian import worker_boot_probe

    events: list[str] = []

    def _failing_probe() -> None:
        events.append("boot_probe")
        raise BayesianWorkerBootTopologyProbeError("injected_boot_probe_failure")

    monkeypatch.setattr(worker_boot_probe, "_bayesian_worker_generation_proof", None)
    monkeypatch.setattr(worker_boot_probe, "_bayesian_execution_authority", None)
    monkeypatch.setattr(
        worker_boot_probe,
        "run_bayesian_worker_boot_topology_probe",
        _failing_probe,
    )

    with pytest.raises(SystemExit, match="bayesian_worker_boot_topology_probe_failed"):
        worker_boot_probe._run_bayesian_worker_boot_topology_probe_if_needed()

    assert events == ["boot_probe"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_registered_bayesian_process_always_runs_boot_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    from app.bayesian import worker_boot_probe

    events: list[str] = []

    class _ProbeResult:
        old_pid = 100
        new_pid = 101
        elapsed_seconds = 0.01
        worker_connection_count = 2
        observer_connection_count = 2

    def _proof_probe() -> _ProbeResult:
        events.append("boot_probe")
        return _ProbeResult()

    monkeypatch.setattr(worker_boot_probe, "_bayesian_worker_generation_proof", None)
    monkeypatch.setattr(worker_boot_probe, "_bayesian_execution_authority", None)
    monkeypatch.setattr(
        worker_boot_probe,
        "run_bayesian_worker_boot_topology_probe",
        _proof_probe,
    )
    monkeypatch.setattr(sys, "argv", ["celery", "worker", "-Q", "housekeeping"])
    worker_boot_probe._run_bayesian_worker_boot_topology_probe_if_needed()

    assert events == ["boot_probe"]
    assert worker_boot_probe.bayesian_worker_boot_topology_probe_has_passed()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_child_process_init_derives_authority_without_db_probe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    from app.bayesian import worker_boot_probe

    events: list[str] = []

    class _ProbeResult:
        old_pid = 100
        new_pid = 101
        elapsed_seconds = 0.01
        worker_connection_count = 2
        observer_connection_count = 2

    def _proof_probe() -> _ProbeResult:
        events.append("boot_probe")
        return _ProbeResult()

    def _forbidden_probe() -> _ProbeResult:
        events.append("forbidden_child_db_probe")
        raise AssertionError("child init must not run the physical DB probe")

    monkeypatch.setattr(worker_boot_probe, "_bayesian_worker_generation_proof", None)
    monkeypatch.setattr(worker_boot_probe, "_bayesian_execution_authority", None)
    monkeypatch.setenv(
        "SKELDIR_BAYESIAN_WORKER_GENERATION_AUTHORITY_DIR",
        str(tmp_path / "authority"),
    )
    monkeypatch.setattr(
        worker_boot_probe,
        "run_bayesian_worker_boot_topology_probe",
        _proof_probe,
    )
    worker_boot_probe._run_bayesian_worker_boot_topology_probe_if_needed()

    monkeypatch.setattr(
        worker_boot_probe,
        "run_bayesian_worker_boot_topology_probe",
        _forbidden_probe,
    )
    monkeypatch.setattr(worker_boot_probe, "_bayesian_execution_authority", None)
    worker_boot_probe._derive_bayesian_child_authority_if_needed()

    assert events == ["boot_probe"]
    assert worker_boot_probe.bayesian_worker_boot_topology_probe_has_passed()

    monkeypatch.setattr(worker_boot_probe, "_bayesian_worker_generation_proof", None)
    monkeypatch.setattr(worker_boot_probe, "_bayesian_execution_authority", None)
    with pytest.raises(SystemExit, match="bayesian_worker_child_authority_failed"):
        worker_boot_probe._derive_bayesian_child_authority_if_needed()

    assert events == ["boot_probe"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_non_bayesian_registry_rejects_broker_misrouted_bayesian_task(
    tmp_path: Path,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    from app.celery_app import celery_app

    queue_name = f"p9_non_bayesian_{uuid4().hex}"
    worker_log = tmp_path / "p9_non_bayesian_worker.log"
    probe_log = tmp_path / "p9_bayesian_probe.jsonl"
    worker_log_handle = worker_log.open("w", encoding="utf-8", buffering=1)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "app.celery_app.celery_app",
            "worker",
            "-P",
            "solo",
            "-c",
            "1",
            "-Q",
            queue_name,
            "--loglevel=INFO",
            "--without-gossip",
            "--without-mingle",
            "--without-heartbeat",
        ],
        cwd=ROOT / "backend",
        env=_worker_env(include_bayesian_tasks=False, log_path=probe_log),
        text=True,
        stdout=worker_log_handle,
        stderr=subprocess.STDOUT,
    )
    try:
        ready_log = _wait_for_log(worker_log, " ready", timeout_s=90)
        worker_log_handle.flush()
        assert process.poll() is None, ready_log
        assert " ready" in ready_log

        celery_app.send_task(
            "app.tasks.bayesian.health_probe",
            kwargs={"tenant_id": str(uuid4()), "correlation_id": str(uuid4())},
            queue=queue_name,
            routing_key=f"{queue_name}.task",
        )
        log_text = _wait_for_log(
            worker_log,
            "app.tasks.bayesian.health_probe",
            timeout_s=25,
        )
    finally:
        _terminate_worker(process)
        worker_log_handle.close()

    assert "app.tasks.bayesian.health_probe" in log_text
    assert "unregistered" in log_text.lower()
    assert "bayesian_health_probe_ok" not in log_text
    assert "bayesian_worker_boot_topology_probe_started" not in log_text
    assert "bayesian_health_probe_ok" not in _read_log(probe_log)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_pool_poison_is_closed_and_replaced_without_manual_reset(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    tenant_a, _tenant_b = test_tenant_pair
    lock_key = int(tenant_a.int % 2_147_483_647)
    worker_engine = create_bayesian_worker_engine(_sync_database_url())
    observer_engine = _observer_engine()
    try:
        old_pid = _poison_one_worker_backend(worker_engine, tenant_id=tenant_a)
        with observer_engine.connect() as observer:
            _assert_backend_absent_or_not_idle_in_transaction(observer, old_pid)
        new_pid = _assert_fresh_worker_backend_is_clean(
            worker_engine, old_pid=old_pid, lock_key=lock_key
        )
        with observer_engine.connect() as observer:
            _assert_backend_absent_or_not_idle_in_transaction(observer, new_pid)
        assert assert_fresh_checkout_is_clean(worker_engine).is_clean
    finally:
        worker_engine.dispose()
        observer_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_pg_stat_activity_backend_not_idle_in_transaction(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    tenant_a, _tenant_b = test_tenant_pair
    worker_engine = create_bayesian_worker_engine(_sync_database_url())
    observer_engine = _observer_engine()
    try:
        with pytest.raises(RuntimeError, match="injected_after_tenant_bind"):
            with worker_engine.begin() as conn:
                pid = int(conn.execute(text("SELECT pg_backend_pid()")).scalar_one())
                bind_transaction_local_tenant(conn, tenant_id=tenant_a)
                raise RuntimeError("injected_after_tenant_bind")
        with observer_engine.connect() as observer:
            _assert_backend_absent_or_not_idle_in_transaction(observer, pid)
    finally:
        worker_engine.dispose()
        observer_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_reset_failure_surface_replaced_by_invalidation_or_close(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    tenant_a, _tenant_b = test_tenant_pair
    worker_engine = create_bayesian_worker_engine(_sync_database_url())
    observer_engine = _observer_engine()
    try:
        with worker_engine.connect() as conn:
            dirty_pid = int(conn.execute(text("SELECT pg_backend_pid()")).scalar_one())
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_a)},
            )
            conn.commit()
            conn.invalidate()
        with observer_engine.connect() as observer:
            _assert_backend_absent_or_not_idle_in_transaction(observer, dirty_pid)
        with worker_engine.connect() as conn:
            replacement_pid = int(
                conn.execute(text("SELECT pg_backend_pid()")).scalar_one()
            )
            assert replacement_pid != dirty_pid
            assert current_tenant_guc(conn) is None
        assert assert_fresh_checkout_is_clean(worker_engine).is_clean
    finally:
        worker_engine.dispose()
        observer_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_representative_same_process_worker_path_exercises_db_lifecycle(
    test_tenant_pair, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    await _assert_table_exists("bayesian_artifacts")
    monkeypatch.setenv("B24_BAYESIAN_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "compiledirs"))
    tenant_a, tenant_b = test_tenant_pair
    fit_a = uuid4()
    fit_b = uuid4()
    await _insert_fit(tenant_a, fit_id=fit_a, source_hash="e" * 64)
    await _insert_fit(tenant_b, fit_id=fit_b, source_hash="f" * 64)

    worker_engine = create_bayesian_worker_engine(_sync_database_url())
    try:
        state_a = _representative_worker_db_lifecycle_attempt(
            worker_engine,
            tenant_id=tenant_a,
            fit_id=fit_a,
            source_hash="e" * 64,
            attempt_id="attempt-db-a",
            sentinel="P9_DB_TENANT_A_SENTINEL_SHOULD_NOT_REACH_B",
        )
        state_b = _representative_worker_db_lifecycle_attempt(
            worker_engine,
            tenant_id=tenant_b,
            fit_id=fit_b,
            source_hash="f" * 64,
            attempt_id="attempt-db-b",
            sentinel="P9_DB_TENANT_B_SENTINEL",
        )
        assert state_a["parent_pid"] == state_b["parent_pid"] == os.getpid()
        for state in (state_a, state_b):
            assert state["fit"]["status"] == "failed"
            assert state["fit"]["fallback_applied"] is True
            assert (
                state["fit"]["fallback_reason"] == FallbackReason.WORKER_FAILURE.value
            )
            assert state["artifact_count"] == 1
            assert state["workspace_removed"] is True
            assert state["compiledir_removed"] is True
        assert state_a["tenant_id"] != state_b["tenant_id"]
        assert state_a["artifact_ref"] != state_b["artifact_ref"]
        assert state_a["workspace"] != state_b["workspace"]
        assert state_a["compiledir"] != state_b["compiledir"]
        assert "P9_DB_TENANT_A_SENTINEL_SHOULD_NOT_REACH_B" not in json.dumps(
            state_b, sort_keys=True
        )
        assert "P9_DB_TENANT_A_SENTINEL_SHOULD_NOT_REACH_B" not in sys.modules
        assert assert_fresh_checkout_is_clean(worker_engine).is_clean
    finally:
        worker_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_transaction_local_guc_clean_return_and_sequential_isolation(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    tenant_a, tenant_b = test_tenant_pair
    fit_a = uuid4()
    fit_b = uuid4()
    await _insert_fit(tenant_a, fit_id=fit_a, source_hash="a" * 64)
    await _insert_fit(tenant_b, fit_id=fit_b, source_hash="b" * 64)

    sync_engine = create_engine(
        to_sync_postgres_dsn(get_database_url()),
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    try:
        with pytest.raises(RuntimeError, match="injected_after_set_local"):
            with sync_engine.begin() as conn:
                bind_transaction_local_tenant(conn, tenant_id=tenant_a)
                assert current_tenant_guc(conn) == str(tenant_a)
                raise RuntimeError("injected_after_set_local")

        clean = assert_fresh_checkout_is_clean(sync_engine)
        assert clean.is_clean

        with sync_engine.begin() as conn:
            bind_transaction_local_tenant(conn, tenant_id=tenant_b)
            visible_b = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.bayesian_model_fits
                    WHERE tenant_id = :tenant_id
                      AND id = :fit_id
                    """
                ),
                {"tenant_id": str(tenant_b), "fit_id": str(fit_b)},
            ).scalar_one()
            hidden_a = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.bayesian_model_fits
                    WHERE tenant_id = :tenant_id
                      AND id = :fit_id
                    """
                ),
                {"tenant_id": str(tenant_a), "fit_id": str(fit_a)},
            ).scalar_one()
            assert int(visible_b) == 1
            assert int(hidden_a) == 0
    finally:
        sync_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_db_proof_requires_explicit_flag_in_ci() -> None:
    if _is_ci():
        assert _require_db_proofs()
    else:
        _require_protected_db_mode()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_session_level_guc_poison_is_detected(test_tenant_pair) -> None:
    await _assert_table_exists("bayesian_model_fits")
    tenant_a, _tenant_b = test_tenant_pair
    sync_engine = create_engine(
        to_sync_postgres_dsn(get_database_url()),
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    try:
        with sync_engine.connect() as conn:
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_a)},
            )
            assert current_tenant_guc(conn) == str(tenant_a)
            conn.commit()

        with pytest.raises(RuntimeError, match="bayesian_connection_returned_dirty"):
            assert_fresh_checkout_is_clean(sync_engine)

        with sync_engine.connect() as conn:
            conn.execute(text("RESET app.current_tenant_id"))
            conn.commit()
        assert assert_fresh_checkout_is_clean(sync_engine).is_clean
    finally:
        sync_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_multi_transaction_task_flow_rebinds_each_transaction(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    tenant_a, _tenant_b = test_tenant_pair
    fit_id = uuid4()
    source_hash = "c" * 64
    await _insert_fit(tenant_a, fit_id=fit_id, source_hash=source_hash)

    sync_engine = create_engine(
        to_sync_postgres_dsn(get_database_url()),
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    result_summary = {
        "diagnostic_status": "passed",
        "credible_interval_status": "available",
        "diagnostic_policy_version": "b24-p7-diagnostic-policy-v1",
        "diagnostic_target_filter_version": "b24-p7-target-filter-v1",
        "interval_policy_version": "b24-p7-interval-policy-v1",
        "n_chains": 1,
        "n_samples_actual": 20,
        "r_hat_max": 1.0,
        "ess_min": 500,
        "divergence_count": 0,
        "hdi_lower": 0.1,
        "hdi_upper": 0.2,
        "interval_shape": [1],
        "interval_element_count": 1,
        "interval_summary_bytes": 32,
    }
    try:
        with sync_engine.begin() as conn:
            row = _load_fit_for_execution(conn, tenant_id=tenant_a, fit_id=fit_id)
            assert row is not None
            assert_bound_tenant(conn, tenant_id=tenant_a)
            conn.execute(
                text(
                    """
                    UPDATE public.bayesian_model_fits
                    SET status = 'running', updated_at = now()
                    WHERE tenant_id = :tenant_id AND id = :fit_id
                    """
                ),
                {"tenant_id": str(tenant_a), "fit_id": str(fit_id)},
            )

        with sync_engine.begin() as conn:
            _persist_result_summary(
                conn,
                tenant_id=tenant_a,
                fit_id=fit_id,
                source_snapshot_hash=source_hash,
                runtime_seconds=1,
                result_summary=result_summary,
                result_hash="d" * 64,
            )
            assert_bound_tenant(conn, tenant_id=tenant_a)

        with sync_engine.begin() as conn:
            _mark_fit_failure(
                conn,
                tenant_id=tenant_a,
                fit_id=fit_id,
                status=FitStatus.FAILED,
                fallback_reason=FallbackReason.WORKER_FAILURE,
                runtime_seconds=2,
            )
            assert_bound_tenant(conn, tenant_id=tenant_a)
    finally:
        sync_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_directive_ix_pre_tenant_claim_and_fence_runtime(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("b24_fit_dispatch_outbox")
    await _assert_table_exists("b24_fit_recovery_outbox")
    tenant_a, _tenant_b = test_tenant_pair
    fit_id = uuid4()
    dispatch_id = uuid4()
    attempt_id = uuid4()
    payload_hash = dispatch_payload_hash(fit_id=fit_id)
    generation_id = "directive-x-runtime-generation"
    await _insert_fit(tenant_a, fit_id=fit_id, source_hash="9" * 64)

    sync_engine = create_engine(
        to_sync_postgres_dsn(get_database_url()),
        poolclass=NullPool,
    )
    try:
        with sync_engine.begin() as conn:
            worker_authority = _register_test_worker_authority(
                conn,
                generation_id=generation_id,
                process_token="directive-x-runtime-process-token-0001",
            )
            _set_tenant_context(conn, tenant_a)
            conn.execute(
                text(
                    """
                    INSERT INTO public.b24_fit_dispatch_outbox (
                        tenant_id,
                        id,
                        fit_id,
                        dispatch_key,
                        task_name,
                        attempt_id,
                        payload_hash,
                        assigned_worker_generation,
                        assignment_generation,
                        assignment_expires_at,
                        assignment_reason,
                        status,
                        next_attempt_at,
                        next_recovery_at
                    )
                    VALUES (
                        :tenant_id,
                        :dispatch_id,
                        :fit_id,
                        :dispatch_key,
                        :task_name,
                        :attempt_id,
                        :payload_hash,
                        :assigned_worker_generation,
                        1,
                        now() + interval '10 minutes',
                        'runtime_test_dispatch',
                        'dispatched',
                        now(),
                        now() + interval '1 hour'
                    )
                    """
                ),
                {
                    "tenant_id": str(tenant_a),
                    "dispatch_id": str(dispatch_id),
                    "fit_id": str(fit_id),
                    "dispatch_key": f"b24-fit:{tenant_a}:{fit_id}",
                    "task_name": BAYESIAN_FIT_EXECUTION_TASK,
                    "attempt_id": str(attempt_id),
                    "payload_hash": payload_hash,
                    "assigned_worker_generation": generation_id,
                },
            )

        bad_claim = BayesianDispatchClaim(
            dispatch_id=dispatch_id,
            fit_id=fit_id,
            task_name=BAYESIAN_FIT_EXECUTION_TASK,
            attempt_id=attempt_id,
            payload_hash=payload_hash,
            recovery_generation=0,
        )
        with sync_engine.begin() as conn:
            assert (
                claim_fit_dispatch_sync(
                    conn,
                    claim=bad_claim,
                    worker_authority=BayesianWorkerClaimAuthority(
                        generation_id=generation_id,
                        pid=worker_authority.pid,
                        process_token="wrong-process-token",
                    ),
                )
                == DispatchClaimOutcome.UNAUTHORIZED
            )

        claim = BayesianDispatchClaim(
            dispatch_id=dispatch_id,
            fit_id=fit_id,
            task_name=BAYESIAN_FIT_EXECUTION_TASK,
            attempt_id=attempt_id,
            payload_hash=payload_hash,
            recovery_generation=0,
        )
        with sync_engine.begin() as conn:
            lease = claim_fit_dispatch_sync(
                conn,
                claim=claim,
                worker_authority=worker_authority,
                lease_seconds=120,
            )
            assert isinstance(lease, BayesianDispatchLease)
            assert lease.outcome is DispatchClaimOutcome.ACQUIRED
            conn.execute(text("SELECT public.b24_mark_fit_dispatch_running()"))
            conn.execute(
                text(
                    """
                    UPDATE public.bayesian_model_fits
                    SET status = 'running', updated_at = now()
                    WHERE id = :fit_id
                    """
                ),
                {"fit_id": str(fit_id)},
            )

        with sync_engine.begin() as conn:
            assert (
                claim_fit_dispatch_sync(
                    conn,
                    claim=claim,
                    worker_authority=worker_authority,
                )
                == DispatchClaimOutcome.ACTIVE_LEASE
            )

        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    SELECT
                        set_config('app.current_tenant_id', :tenant_id, true),
                        set_config('app.b24_dispatch_id', :dispatch_id, true),
                        set_config('app.b24_attempt_id', :attempt_id, true),
                        set_config('app.b24_claim_epoch', '0', true),
                        set_config('app.b24_lease_capability', :lease_capability, true)
                    """
                ),
                {
                    "tenant_id": str(tenant_a),
                    "dispatch_id": str(dispatch_id),
                    "attempt_id": str(attempt_id),
                    "lease_capability": "not-the-db-minted-lease",
                },
            )
            with pytest.raises(DBAPIError, match="b24_dispatch_fence_rejected"):
                conn.execute(
                    text(
                        """
                        UPDATE public.bayesian_model_fits
                        SET status = 'failed', updated_at = now()
                        WHERE id = :fit_id
                        """
                    ),
                    {"fit_id": str(fit_id)},
                )
    finally:
        sync_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_directive_ix_stale_lease_and_recovery_runtime(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("b24_fit_dispatch_outbox")
    await _assert_table_exists("b24_fit_recovery_outbox")
    tenant_a, _tenant_b = test_tenant_pair
    fit_id = uuid4()
    dispatch_id = uuid4()
    attempt_id = uuid4()
    payload_hash = dispatch_payload_hash(fit_id=fit_id)
    await _insert_fit(tenant_a, fit_id=fit_id, source_hash="8" * 64)

    sync_engine = create_engine(
        to_sync_postgres_dsn(get_database_url()),
        poolclass=NullPool,
    )
    try:
        with sync_engine.begin() as conn:
            worker_authority = _register_test_worker_authority(
                conn,
                generation_id="directive-x-recovery-generation",
                process_token="directive-x-runtime-process-token-0002",
            )
            _set_tenant_context(conn, tenant_a)
            conn.execute(
                text(
                    """
                    INSERT INTO public.b24_fit_dispatch_outbox (
                        tenant_id,
                        id,
                        fit_id,
                        dispatch_key,
                        task_name,
                        attempt_id,
                        payload_hash,
                        assigned_worker_generation,
                        assignment_generation,
                        assignment_expires_at,
                        assignment_reason,
                        status,
                        next_attempt_at,
                        next_recovery_at
                    )
                    VALUES (
                        :tenant_id,
                        :dispatch_id,
                        :fit_id,
                        :dispatch_key,
                        :task_name,
                        :attempt_id,
                        :payload_hash,
                        :assigned_worker_generation,
                        1,
                        now() + interval '10 minutes',
                        'runtime_recovery_test',
                        'dispatched',
                        now(),
                        now()
                    )
                    """
                ),
                {
                    "tenant_id": str(tenant_a),
                    "dispatch_id": str(dispatch_id),
                    "fit_id": str(fit_id),
                    "dispatch_key": f"b24-fit:{tenant_a}:{fit_id}",
                    "task_name": BAYESIAN_FIT_EXECUTION_TASK,
                    "attempt_id": str(attempt_id),
                    "payload_hash": payload_hash,
                    "assigned_worker_generation": worker_authority.generation_id,
                },
            )

        with sync_engine.begin() as conn:
            count = conn.execute(
                text("SELECT public.b24_create_fit_recovery_wakeups(10)")
            ).scalar_one()
            assert int(count) >= 1

        with sync_engine.begin() as conn:
            _set_tenant_context(conn, tenant_a)
            row = (
                conn.execute(
                    text(
                        """
                        SELECT recovery_generation, status, claim_capability, attempt_id
                        FROM public.b24_fit_recovery_outbox
                        WHERE tenant_id = :tenant_id
                          AND dispatch_id = :dispatch_id
                        """
                    ),
                    {
                        "tenant_id": str(tenant_a),
                        "dispatch_id": str(dispatch_id),
                    },
                )
                .mappings()
                .one()
            )
            assert row["status"] == "pending"
            assert int(row["recovery_generation"]) == 1
            assert row["claim_capability"] is None
            assert row["attempt_id"] != attempt_id

        stale_claim = BayesianDispatchClaim(
            dispatch_id=dispatch_id,
            fit_id=fit_id,
            task_name=BAYESIAN_FIT_EXECUTION_TASK,
            attempt_id=attempt_id,
            payload_hash=payload_hash,
            recovery_generation=0,
        )
        with sync_engine.begin() as conn:
            assert (
                claim_fit_dispatch_sync(
                    conn,
                    claim=stale_claim,
                    worker_authority=worker_authority,
                )
                == DispatchClaimOutcome.UNAUTHORIZED
            )
    finally:
        sync_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p9_concurrent_tenant_isolation_db_and_runtime_surfaces(
    test_tenant_pair, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    monkeypatch.setenv("B24_BAYESIAN_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "compiledirs"))
    tenant_a, tenant_b = test_tenant_pair
    fit_a = uuid4()
    fit_b = uuid4()
    await _insert_fit(tenant_a, fit_id=fit_a, source_hash="a" * 64)
    await _insert_fit(tenant_b, fit_id=fit_b, source_hash="b" * 64)

    sync_engine = create_engine(
        to_sync_postgres_dsn(get_database_url()),
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=0,
    )
    barrier = Barrier(2)

    def lane(
        label: str, tenant_id: UUID, own_fit: UUID, other_fit: UUID
    ) -> dict[str, object]:
        source_hash = ("a" if label == "a" else "b") * 64
        workspace = create_workspace_lease(
            tenant_id=tenant_id,
            fit_id=own_fit,
            source_snapshot_hash=source_hash,
            execution_attempt_id=f"concurrent-{label}",
        )
        compiledir = create_compiledir_lease(
            execution_id=f"concurrent-{label}",
            worker_id="p9-db-concurrent",
            tenant_id=tenant_id,
            fit_id=own_fit,
            source_snapshot_hash=source_hash,
        )
        artifact_ref = _artifact_ref(
            tenant_id=tenant_id,
            fit_id=own_fit,
            artifact_type="diagnostics",
            artifact_hash=source_hash,
        )
        with sync_engine.connect() as conn:
            with conn.begin():
                bind_transaction_local_tenant(conn, tenant_id=tenant_id)
                assert current_tenant_guc(conn) == str(tenant_id)
                barrier.wait(timeout=10)
                own_visible = conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM public.bayesian_model_fits
                        WHERE tenant_id = :tenant_id AND id = :fit_id
                        """
                    ),
                    {"tenant_id": str(tenant_id), "fit_id": str(own_fit)},
                ).scalar_one()
                other_visible = conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM public.bayesian_model_fits
                        WHERE id = :fit_id
                        """
                    ),
                    {"fit_id": str(other_fit)},
                ).scalar_one()
        workspace_cleanup = cleanup_fit_attempt(workspace=workspace, compiledir=None)
        compiledir_survived = compiledir.path.exists()
        compiledir_cleanup = cleanup_fit_attempt(workspace=None, compiledir=compiledir)
        return {
            "label": label,
            "guc_after_commit_clean": assert_fresh_checkout_is_clean(
                sync_engine
            ).is_clean,
            "own_visible": int(own_visible),
            "other_visible": int(other_visible),
            "workspace": str(workspace.path),
            "compiledir": str(compiledir.path),
            "artifact_ref": artifact_ref,
            "workspace_removed": workspace_cleanup.workspace_removed,
            "compiledir_survived_workspace_cleanup": compiledir_survived,
            "compiledir_removed": compiledir_cleanup.compiledir_removed,
        }

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            result_a = executor.submit(lane, "a", tenant_a, fit_a, fit_b)
            result_b = executor.submit(lane, "b", tenant_b, fit_b, fit_a)
            payload_a = result_a.result(timeout=20)
            payload_b = result_b.result(timeout=20)
        for payload in (payload_a, payload_b):
            assert payload["own_visible"] == 1
            assert payload["other_visible"] == 0
            assert payload["guc_after_commit_clean"] is True
            assert payload["workspace_removed"] is True
            assert payload["compiledir_survived_workspace_cleanup"] is True
            assert payload["compiledir_removed"] is True
        assert payload_a["workspace"] != payload_b["workspace"]
        assert payload_a["compiledir"] != payload_b["compiledir"]
        assert payload_a["artifact_ref"] != payload_b["artifact_ref"]
    finally:
        sync_engine.dispose()
