from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import psycopg2
import pytest

from app.celery_app import celery_app
from app.tasks.authority import AUTHORITY_ENVELOPE_HEADER, SystemAuthorityEnvelope, authority_envelope_payload

# Import registers SKELDIR_TEST_TASKS probes in this pytest process. Worker subprocesses
# also load them through SKELDIR_TEST_TASKS=1.
from app.tasks import observability_test as _m2_observability_test  # noqa: F401


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "postgres", "pgbouncer"}
SAFE_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_WORKER_LINES_BY_PID: dict[int, list[str]] = {}


def _strip_driver_prefix(dsn: str) -> str:
    cleaned = dsn
    for prefix in ("sqla+", "db+"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
    return cleaned.replace("postgresql+asyncpg://", "postgresql://", 1)


def _require_local_dsn(env_name: str) -> str:
    dsn = os.getenv(env_name)
    if not dsn:
        pytest.fail(f"{env_name} is required for corrective M2 runtime proof")
    cleaned = _strip_driver_prefix(dsn)
    host = (urlparse(cleaned).hostname or "").lower()
    if host not in LOCAL_HOSTS:
        pytest.fail(f"{env_name} must point at local topology, got host={host}")
    return cleaned


def _qualified_public_table(table_name: str) -> str:
    if not SAFE_IDENTIFIER.fullmatch(table_name):
        raise AssertionError(f"unsafe table name: {table_name}")
    return f"public.{table_name}"


def _connect(env_name: str):
    return psycopg2.connect(_require_local_dsn(env_name))


def _wait_for_worker_ready(lines: list[str], proc: subprocess.Popen[str], timeout_s: float = 90.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if any("ready." in line for line in lines):
            return
        if proc.poll() is not None:
            raise RuntimeError("Celery worker exited before ready signal:\n" + "\n".join(lines[-80:]))
        time.sleep(0.2)
    raise RuntimeError("Timed out waiting for Celery worker readiness:\n" + "\n".join(lines[-80:]))


def _start_worker(
    *,
    queue: str,
    database_url: str,
    concurrency: int = 4,
    node_suffix: str = "0",
) -> tuple[subprocess.Popen[str], list[str]]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["TESTING"] = "1"
    env["SKELDIR_TEST_TASKS"] = "1"
    env["SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS"] = "0"
    env["DATABASE_FORCE_POOLING"] = "1"
    env["DATABASE_POOL_SIZE"] = "4"
    env["DATABASE_MAX_OVERFLOW"] = "0"
    env["CELERY_WORKER_PREFETCH_MULTIPLIER"] = "4"
    env["SKELDIR_ASYNCPG_DISABLE_STATEMENT_CACHE"] = env.get("SKELDIR_ASYNCPG_DISABLE_STATEMENT_CACHE", "0")
    env["PROMETHEUS_MULTIPROC_DIR"] = tempfile.mkdtemp(prefix="m2_prom_")
    env["DATABASE_URL"] = database_url
    env["CELERY_BROKER_URL"] = str(celery_app.conf.broker_url)
    env["CELERY_RESULT_BACKEND"] = str(celery_app.conf.result_backend)

    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "app.celery_app.celery_app",
        "worker",
        "-P",
        "threads",
        "-c",
        str(concurrency),
        "--prefetch-multiplier=4",
        "-Q",
        queue,
        "-n",
        f"m2-{re.sub(r'[^A-Za-z0-9_.-]', '-', queue)[:80]}-{node_suffix}@%h",
        "--without-gossip",
        "--without-mingle",
        "--without-heartbeat",
        "--loglevel=INFO",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines: list[str] = []

    def _reader() -> None:
        if proc.stdout is None:
            return
        for line in proc.stdout:
            lines.append(line.rstrip("\n"))

    threading.Thread(target=_reader, daemon=True).start()
    _wait_for_worker_ready(lines, proc)
    _WORKER_LINES_BY_PID[proc.pid or -1] = lines
    return proc, lines


def _start_worker_pair(*, queues: tuple[str, str], database_url: str) -> list[subprocess.Popen[str]]:
    queue_arg = ",".join(queues)
    return [
        _start_worker(queue=queue_arg, database_url=database_url, concurrency=2, node_suffix="a")[0],
        _start_worker(queue=queue_arg, database_url=database_url, concurrency=2, node_suffix="b")[0],
    ]


def _stop_worker(proc: subprocess.Popen[str]) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=20)


def _worker_log_tail(procs: list[subprocess.Popen[str]]) -> str:
    chunks: list[str] = []
    for proc in procs:
        lines = _WORKER_LINES_BY_PID.get(proc.pid or -1, [])
        chunks.append(f"pid={proc.pid}\n" + "\n".join(lines[-80:]))
    return "\n\n".join(chunks)


def _prepare_probe_table(table_name: str) -> None:
    qualified = _qualified_public_table(table_name)
    barrier = _qualified_public_table(f"{table_name}_barrier")
    with _connect("TEST_DIRECT_DATABASE_URL") as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {qualified}")
            cur.execute(f"DROP TABLE IF EXISTS {barrier}")
            cur.execute(
                """
                DO $$
                BEGIN
                    CREATE ROLE m2_runtime_rls;
                EXCEPTION
                    WHEN duplicate_object THEN NULL;
                END
                $$;
                """
            )
            cur.execute(
                f"""
                CREATE TABLE {barrier} (
                    run_id text NOT NULL,
                    marker text NOT NULL,
                    tenant_id uuid NOT NULL,
                    task_id text NOT NULL,
                    worker_pid integer NOT NULL,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    PRIMARY KEY (run_id, marker)
                )
                """
            )
            cur.execute(
                f"""
                CREATE TABLE {qualified} (
                    id uuid PRIMARY KEY,
                    run_id text NOT NULL,
                    tenant_id uuid NOT NULL,
                    marker text NOT NULL,
                    task_id text NOT NULL,
                    worker_pid integer NOT NULL,
                    backend_pid integer NOT NULL,
                    created_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute(f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY")
            cur.execute(f"ALTER TABLE {qualified} FORCE ROW LEVEL SECURITY")
            cur.execute(
                f"""
                CREATE POLICY m2_worker_probe_tenant_isolation
                  ON {qualified}
               USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
               WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
                """
            )
            cur.execute("GRANT USAGE ON SCHEMA public TO m2_runtime_rls")
            cur.execute(f"GRANT SELECT, INSERT ON {qualified} TO m2_runtime_rls")
            cur.execute(f"GRANT SELECT, INSERT ON {barrier} TO m2_runtime_rls")


def _drop_probe_table(table_name: str) -> None:
    qualified = _qualified_public_table(table_name)
    barrier = _qualified_public_table(f"{table_name}_barrier")
    with _connect("TEST_DIRECT_DATABASE_URL") as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {qualified}")
            cur.execute(f"DROP TABLE IF EXISTS {barrier}")


def _pooler_insert_and_cross_check(*, pooled_dsn: str, table_name: str, tenant_id, other_tenant_id, run_id: str) -> tuple[int, int, str | None]:
    qualified = _qualified_public_table(table_name)
    with psycopg2.connect(pooled_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("BEGIN")
            cur.execute("SELECT set_config('app.current_tenant_id', %s, true)", (str(tenant_id),))
            cur.execute("SET LOCAL ROLE m2_runtime_rls")
            cur.execute(
                f"""
                INSERT INTO {qualified} (
                    id,
                    run_id,
                    tenant_id,
                    marker,
                    task_id,
                    worker_pid,
                    backend_pid
                )
                VALUES (%s, %s, %s, %s, %s, %s, pg_backend_pid())
                """,
                (str(uuid4()), run_id, str(tenant_id), f"pooler-{tenant_id}", "pooler-query", os.getpid()),
            )
            cur.execute(
                f"SELECT count(*) FROM {qualified} WHERE run_id = %s AND tenant_id = %s",
                (run_id, str(tenant_id)),
            )
            own_count = int(cur.fetchone()[0])
            cur.execute(
                f"SELECT count(*) FROM {qualified} WHERE run_id = %s AND tenant_id = %s",
                (run_id, str(other_tenant_id)),
            )
            cross_count = int(cur.fetchone()[0])
            cur.execute("COMMIT")
            cur.execute("SELECT current_setting('app.current_tenant_id', true)")
            reset_value = cur.fetchone()[0]
    return own_count, cross_count, reset_value


def _enqueue_probe(
    *,
    queue: str,
    tenant_id,
    other_tenant_id,
    table_name: str,
    run_id: str,
    marker: str,
    barrier_timeout_seconds: float,
):
    envelope = SystemAuthorityEnvelope(tenant_id=tenant_id)
    return celery_app.send_task(
        "app.tasks.observability_test.m2_worker_concurrency_probe",
        queue=queue,
        kwargs={
            "table_name": table_name,
            "run_id": run_id,
            "marker": marker,
            "other_tenant_id": str(other_tenant_id),
            "barrier_timeout_seconds": barrier_timeout_seconds,
        },
        headers={AUTHORITY_ENVELOPE_HEADER: authority_envelope_payload(envelope)},
        correlation_id=str(uuid4()),
    )


def _assert_missing_tenant_task_fails_visibly(*, table_name: str, run_id: str, tenant_id) -> None:
    with pytest.raises(ValueError, match="authority_envelope header is required"):
        _m2_observability_test.m2_worker_concurrency_probe.apply(
            kwargs={
                "table_name": table_name,
                "run_id": run_id,
                "marker": "missing-tenant",
                "other_tenant_id": str(tenant_id),
                "hold_seconds": 0.0,
            },
            throw=True,
        )


def _assert_concurrent_tenant_isolation(*, queues: tuple[str, str], table_name: str, run_id: str, pooled: bool) -> None:
    tenant_a = uuid4()
    tenant_b = uuid4()
    barrier_timeout_seconds = 45.0
    result_a = _enqueue_probe(
        queue=queues[0],
        tenant_id=tenant_a,
        other_tenant_id=tenant_b,
        table_name=table_name,
        run_id=run_id,
        marker="tenant-a",
        barrier_timeout_seconds=barrier_timeout_seconds,
    )
    result_b = _enqueue_probe(
        queue=queues[1],
        tenant_id=tenant_b,
        other_tenant_id=tenant_a,
        table_name=table_name,
        run_id=run_id,
        marker="tenant-b",
        barrier_timeout_seconds=barrier_timeout_seconds,
    )
    payload_a = result_a.get(timeout=90, propagate=True)
    payload_b = result_b.get(timeout=90, propagate=True)

    assert payload_a["tenant"] == str(tenant_a)
    assert payload_b["tenant"] == str(tenant_b)
    assert payload_a["tenant_guc"] == str(tenant_a)
    assert payload_b["tenant_guc"] == str(tenant_b)
    assert payload_a["context_tenant"] == str(tenant_a)
    assert payload_b["context_tenant"] == str(tenant_b)
    assert payload_a["own_visible"] >= 1
    assert payload_b["own_visible"] >= 1
    assert payload_a["cross_visible"] == 0
    assert payload_b["cross_visible"] == 0
    if pooled:
        assert payload_a["database_url_hostport"] in {"127.0.0.1:6432", "localhost:6432", "pgbouncer:5432"}
        assert payload_b["database_url_hostport"] in {"127.0.0.1:6432", "localhost:6432", "pgbouncer:5432"}
    with _connect("TEST_DIRECT_DATABASE_URL") as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT count(DISTINCT marker)
                  FROM {_qualified_public_table(f"{table_name}_barrier")}
                 WHERE run_id = %s
                   AND marker IN ('tenant-a', 'tenant-b')
                """,
                (run_id,),
            )
            assert int(cur.fetchone()[0]) == 2
    _assert_missing_tenant_task_fails_visibly(table_name=table_name, run_id=run_id, tenant_id=tenant_a)


@pytest.mark.celery_worker
@pytest.mark.celery_worker_concurrent
@pytest.mark.integration_db_pooler
@pytest.mark.pooler_worker_concurrent
@pytest.mark.rls_guc_sensitive
@pytest.mark.fail_visible_tenant_context
def test_m2_pooler_worker_concurrent_tenant_isolation() -> None:
    table_name = f"m2_pooler_worker_probe_{uuid4().hex}"
    run_id = os.environ["SKELDIR_TEST_RUN_ID"]
    queue_prefix = f"m2.pooler.{run_id}.{uuid4().hex[:8]}"
    queues = (f"{queue_prefix}.a", f"{queue_prefix}.b")
    _prepare_probe_table(table_name)
    procs: list[subprocess.Popen[str]] = []
    try:
        pooled_dsn = _require_local_dsn("TEST_POOLED_DATABASE_URL")
        os.environ["SKELDIR_ASYNCPG_DISABLE_STATEMENT_CACHE"] = "1"
        procs = _start_worker_pair(queues=queues, database_url=pooled_dsn)
        try:
            _assert_concurrent_tenant_isolation(queues=queues, table_name=table_name, run_id=run_id, pooled=True)
        except Exception as exc:
            pytest.fail(f"{exc}\n\nworker logs:\n{_worker_log_tail(procs)}")
        with psycopg2.connect(pooled_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_setting('app.current_tenant_id', true)")
                assert cur.fetchone()[0] in (None, "")
    finally:
        for proc in procs:
            _stop_worker(proc)
        _drop_probe_table(table_name)


@pytest.mark.integration_db_pooler
@pytest.mark.rls_guc_sensitive
@pytest.mark.fail_visible_tenant_context
def test_m2_pooler_rls_guc_negative_controls_under_concurrency() -> None:
    table_name = f"m2_pooler_rls_probe_{uuid4().hex}"
    run_id = os.environ["SKELDIR_TEST_RUN_ID"]
    tenant_a = uuid4()
    tenant_b = uuid4()
    pooled_dsn = _require_local_dsn("TEST_POOLED_DATABASE_URL")
    _prepare_probe_table(table_name)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(
                _pooler_insert_and_cross_check,
                pooled_dsn=pooled_dsn,
                table_name=table_name,
                tenant_id=tenant_a,
                other_tenant_id=tenant_b,
                run_id=run_id,
            )
            future_b = executor.submit(
                _pooler_insert_and_cross_check,
                pooled_dsn=pooled_dsn,
                table_name=table_name,
                tenant_id=tenant_b,
                other_tenant_id=tenant_a,
                run_id=run_id,
            )
            own_a, cross_a, reset_a = future_a.result(timeout=30)
            own_b, cross_b, reset_b = future_b.result(timeout=30)

        assert own_a == 1
        assert own_b == 1
        assert cross_a == 0
        assert cross_b == 0
        assert reset_a in (None, "")
        assert reset_b in (None, "")
        with psycopg2.connect(pooled_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_setting('app.current_tenant_id', true)")
                assert cur.fetchone()[0] in (None, "")
                cur.execute("BEGIN")
                cur.execute("SET LOCAL ROLE m2_runtime_rls")
                try:
                    cur.execute(
                        f"SELECT count(*) FROM {_qualified_public_table(table_name)} WHERE run_id = %s",
                        (run_id,),
                    )
                except psycopg2.Error:
                    conn.rollback()
                else:
                    assert int(cur.fetchone()[0]) == 0
                    cur.execute("ROLLBACK")
    finally:
        _drop_probe_table(table_name)


@pytest.mark.celery_worker
def test_m2_broker_absent_negative_control_fails_visibly() -> None:
    from kombu import Connection

    bad_broker = "sqla+postgresql://skeldir:skeldir_local@127.0.0.1:1/skeldir_local"
    with pytest.raises(Exception):
        with Connection(bad_broker, connect_timeout=1) as conn:
            channel = conn.channel()
            channel.queue_declare(queue="m2_broker_absent_probe")


@pytest.mark.parallel_isolation
def test_m2_serial_parallel_isolation_and_namespace_authority() -> None:
    worker_id = os.getenv("PYTEST_XDIST_WORKER", "master")
    run_id = os.getenv("SKELDIR_TEST_RUN_ID")
    assert run_id and run_id.startswith("m2-")
    assert os.getenv("SKELDIR_TEST_PARALLEL_MODE", "serial-only") == "serial-only"
    assert worker_id == "master", "M2 CI is serial-only until per-worker DB/schema isolation is implemented"
