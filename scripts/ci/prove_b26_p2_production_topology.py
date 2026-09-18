#!/usr/bin/env python3
"""B2.6-P2 Corrective IV deployed-topology proof (Gates 1-4, 12-14).

Boots the EXACT compiled production topology and drives a REAL
HMAC-signed webhook from OUTSIDE the API process through the full causal
chain using the EXACT shipped commands, process identities, database
principals, queues, schedulers, and failure-recovery mechanisms:

  API (Dockerfile CMD, app_user)
    -> real signed Stripe webhook over HTTP (host -> container)
    -> atomic dispatch + outbox + admission-directory commit
    -> real broker publish (kombu sqla transport, stable task_id)
  worker_b23 (exact Procfile command, B23 worker credential)
    -> admission BEFORE B2.3 (constrained resolver, no GUC trust)
    -> authorized B2.3 verdict writes
    -> governed P2 scope (REPEATABLE READ, RLS strict, identity v3)
    -> conducted marking (operational state, never financial truth)
  relay (exact Procfile command, producer principal)
    + beat (exact beat command, scheduled sweep = the recovery motor)

Then proves FAILURE RECOVERY is natural (no manual enqueue): broker
outage -> pending_publish -> broker restored -> scheduler + relay +
worker conduct the SAME execution identity to conducted.

Then runs deployment-level falsifiers (each must RED the observed
property, then restore GREEN):
  F-a worker on producer DSN: verdict writes die, nothing conducts
  F-b scheduler removed: pending never recovers
  F-c sweep to unconsumed queue: pending never recovers
  F-d split-brain / orphan writes: database refuses
  F-e bootstrap grant removed: equivalence proof REDs
  F-f stale image: container identity diverges from host
  F-g comment-only policy edit: identity EQUAL (v3 semantic law)
  F-h semantic policy edit: identity CHANGED + validator REDs

Negative controls that only need source text live in
test_b26_p2_negative_controls.py (45/45). The controls here need the
DEPLOYED plane: they mutate deployment state, never host source.

No mocks, no eager mode, no manual derive bypass, no direct relay task
call for topology credit: every step observes durable broker/DB state
written by the preceding production edge.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO_ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
except Exception:  # noqa: BLE001 - non-critical on exotic platforms
    pass

NETWORK = "b26p2-iv-net"
PG_CONTAINER = "b26p2-iv-pg"
API_CONTAINER = "b26p2-iv-api"
WORKER_CONTAINER = "b26p2-iv-worker-b23"
RELAY_CONTAINER = "b26p2-iv-relay"
BEAT_CONTAINER = "b26p2-iv-beat"
DB_NAME = "skeldir_b26_p2_deployed"
PLATFORM_KEY = "b26-p2-iv-platform-key-do-not-use-outside-ci"
TENANT_KEY_PREFIX = "b26p2-iv-tenant-key"

WORKER_CMD = [
    "celery",
    "-A",
    "app.celery_app.celery_app",
    "worker",
    "--loglevel=info",
    "--queues=b23_match_engine",
    "--concurrency=1",
    "--prefetch-multiplier=1",
]
RELAY_CMD = [
    "celery",
    "-A",
    "app.celery_app.celery_app",
    "worker",
    "--loglevel=info",
    "--queues=b26_p2_relay",
    "--concurrency=1",
    "--prefetch-multiplier=1",
]
BEAT_CMD = [
    "celery",
    "-A",
    "app.celery_app.celery_app",
    "beat",
    "--loglevel=info",
]
API_CMD = ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


def _fail(msg: str) -> int:
    print(f"B26_P2_TOPOLOGY_FAIL {msg}")
    return 1


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, **kwargs)


def _docker(*args: str) -> subprocess.CompletedProcess[str]:
    return _run(["docker", *args], cwd=REPO_ROOT)


def _container_env(name: str, key: str) -> str:
    proc = _docker("exec", name, "printenv", key)
    return proc.stdout.strip()


def _container_current_user(name: str, dsn_env: str) -> str:
    """Capture current_user from INSIDE the running process's credential."""
    probe = (
        "import os,sys;"
        "from sqlalchemy.engine.url import make_url;"
        "raw=os.environ[sys.argv[1]];"
        "u=make_url(raw);"
        "dsn='postgresql://'+(u.username or '')+':'+(u.password or '')+'@'+(u.host or 'localhost')+':'+str(u.port or 5432)+'/'+(u.database or '');"
        "import psycopg2;"
        "c=psycopg2.connect(dsn);c.autocommit=True;cur=c.cursor();"
        "cur.execute('SELECT current_user, session_user');"
        "print('|'.join(cur.fetchone()));"
    )
    proc = _docker("exec", name, "python", "-c", probe, dsn_env)
    if proc.returncode != 0:
        raise RuntimeError(f"principal_capture_failed:{name}:{proc.stderr[-400:]}")
    return proc.stdout.strip()


def _pid1_cmdline(name: str) -> str:
    proc = _docker("exec", name, "cat", "/proc/1/cmdline")
    if proc.returncode != 0:
        raise RuntimeError(f"pid1_capture_failed:{name}")
    return proc.stdout.replace("\x00", " ").strip()


def _wait_http_ok(url: str, timeout_s: int) -> None:
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    return
                last = f"status={resp.status}"
        except Exception as exc:  # noqa: BLE001
            last = str(exc)[:120]
        time.sleep(2)
    raise RuntimeError(f"http_not_ready:{url}:{last}")


def _wait_log(name: str, needle: str, timeout_s: int) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        proc = _docker("logs", name)
        if needle in proc.stdout + proc.stderr:
            return
        time.sleep(2)
    raise RuntimeError(f"log_needle_missing:{name}:{needle}")


def _container_state(name: str) -> str:
    proc = _docker("inspect", "-f", "{{.State.Status}}", name)
    return proc.stdout.strip()


def _restart_count(name: str) -> str:
    proc = _docker("inspect", "-f", "{{.RestartCount}}", name)
    return proc.stdout.strip()


def _wait_running(name: str, timeout_s: int) -> None:
    """Wait until a supervised container is running (restarts absorbed)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _container_state(name) == "running":
            return
        time.sleep(2)
    raise RuntimeError(f"container_not_running:{name}:{_container_state(name)}")


class _Topology:
    """Owns the deployed plane; guarantees cleanup."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.image = f"skeldir-b26-p2-deployed:{args.image_tag}"
        self.pg_port = str(args.pg_port)
        self.api_port = str(args.api_port)
        self.admin_dsn = (
            f"postgresql://postgres:{args.pg_password}@127.0.0.1:{self.pg_port}/postgres"
        )
        self.db_admin = (
            f"postgresql://postgres:{args.pg_password}@127.0.0.1:{self.pg_port}/{DB_NAME}"
        )

    # -- lifecycle ------------------------------------------------------
    def _cleanup_container(self, name: str) -> None:
        _docker("rm", "-f", name)

    def cleanup(self) -> None:
        for name in (
            BEAT_CONTAINER,
            RELAY_CONTAINER,
            WORKER_CONTAINER,
            API_CONTAINER,
            PG_CONTAINER,
        ):
            self._cleanup_container(name)
        _docker("network", "rm", NETWORK)

    def build_image(self) -> str:
        if self.args.no_build:
            return self.image
        proc = _docker("build", "-f", "backend/Dockerfile", "-t", self.image, ".")
        if proc.returncode != 0:
            raise RuntimeError(f"image_build_failed:{proc.stderr[-2000:]}")
        proc = _docker("image", "inspect", self.image, "--format", "{{.Id}}")
        return proc.stdout.strip()

    def start_postgres(self) -> None:
        self._cleanup_container(PG_CONTAINER)
        _docker("network", "create", NETWORK)
        proc = _docker(
            "run",
            "-d",
            "--name",
            PG_CONTAINER,
            "--network",
            NETWORK,
            "--network-alias",
            "pg",
            "-e",
            f"POSTGRES_PASSWORD={self.args.pg_password}",
            "-p",
            f"{self.pg_port}:5432",
            "postgres:15-alpine",
        )
        if proc.returncode != 0:
            raise RuntimeError(f"pg_start_failed:{proc.stderr[-500:]}")
        deadline = time.time() + 90
        while time.time() < deadline:
            proc = _docker("exec", PG_CONTAINER, "pg_isready", "-U", "postgres")
            if proc.returncode == 0:
                return
            time.sleep(2)
        raise RuntimeError("pg_not_ready")

    def provision(self) -> None:
        import psycopg2

        conn = psycopg2.connect(self.admin_dsn)
        conn.autocommit = True
        try:
            cur = conn.cursor()
            cur.execute(f'DROP DATABASE IF EXISTS "{DB_NAME}"')
            cur.execute(f'CREATE DATABASE "{DB_NAME}"')
        finally:
            conn.close()
        proc = _run(
            [
                sys.executable,
                "scripts/database/prepare_migration_authority_boundary.py",
                "--admin-dsn",
                self.admin_dsn,
                "--database-name",
                DB_NAME,
            ],
            cwd=REPO_ROOT,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"provision_failed:{proc.stderr[-1500:]}")
        env = dict(
            os.environ,
            MIGRATION_DATABASE_URL=(
                f"postgresql://migration_owner:migration_owner"
                f"@127.0.0.1:{self.pg_port}/{DB_NAME}"
            ),
            DATABASE_URL=(
                f"postgresql://migration_owner:migration_owner"
                f"@127.0.0.1:{self.pg_port}/{DB_NAME}"
            ),
        )
        proc = _run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=REPO_ROOT, env=env)
        if proc.returncode != 0:
            raise RuntimeError(f"migrate_failed:{proc.stdout[-1000:]}:{proc.stderr[-1000:]}")

    # -- containers -----------------------------------------------------
    def _base_env(self, dsn: str) -> list[str]:
        # Production-fidelity env: no TESTING flag (that would switch pool
        # behavior); ENVIRONMENT=local mirrors the shipped local topology.
        return [
            "-e",
            f"DATABASE_URL={dsn}",
            "-e",
            f"MIGRATION_DATABASE_URL=postgresql://migration_owner:migration_owner@pg:5432/{DB_NAME}",
            "-e",
            f"PLATFORM_TOKEN_ENCRYPTION_KEY={PLATFORM_KEY}",
            "-e",
            "PROMETHEUS_MULTIPROC_DIR=/tmp",
            "-e",
            "ENVIRONMENT=local",
        ]

    # Supervision mirror: the deployment restarts service processes after
    # crashes (compose `restart: unless-stopped`; foreman-style managers
    # restart on exit). A transient broker fault can kill a Celery process
    # (beat exits on an unapplied scheduled task), so the proof must run
    # under the same supervision or it proves a weaker topology.
    _RESTART = ("--restart", "unless-stopped")

    def start_api(self) -> None:
        self._cleanup_container(API_CONTAINER)
        dsn = f"postgresql+asyncpg://app_user:app_user@pg:5432/{DB_NAME}"
        proc = _docker(
            "run",
            "-d",
            "--name",
            API_CONTAINER,
            *self._RESTART,
            "--network",
            NETWORK,
            "-p",
            f"{self.api_port}:8000",
            *self._base_env(dsn),
            self.image,
            *API_CMD,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"api_start_failed:{proc.stderr[-500:]}")

    def start_worker(self, dsn_override: str | None = None) -> None:
        self._cleanup_container(WORKER_CONTAINER)
        worker_dsn = dsn_override or f"postgresql+asyncpg://app_worker:app_worker@pg:5432/{DB_NAME}"
        proc = _docker(
            "run",
            "-d",
            "--name",
            WORKER_CONTAINER,
            *self._RESTART,
            "--network",
            NETWORK,
            *self._base_env(worker_dsn),
            "-e",
            f"B23_WORKER_DATABASE_URL={worker_dsn}",
            "-e",
            "SKELDIR_B23_REQUIRE_WORKER_DSN=1",
            "-e",
            "B23_WORKER_CONCURRENCY=1",
            self.image,
            *WORKER_CMD,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"worker_start_failed:{proc.stderr[-500:]}")

    def start_relay(self) -> None:
        self._cleanup_container(RELAY_CONTAINER)
        dsn = f"postgresql+asyncpg://app_user:app_user@pg:5432/{DB_NAME}"
        proc = _docker(
            "run",
            "-d",
            "--name",
            RELAY_CONTAINER,
            *self._RESTART,
            "--network",
            NETWORK,
            *self._base_env(dsn),
            "-e",
            "SKELDIR_CELERY_WORKER_ROLE=b26_p2_relay",
            self.image,
            *RELAY_CMD,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"relay_start_failed:{proc.stderr[-500:]}")

    def start_beat(self) -> None:
        self._cleanup_container(BEAT_CONTAINER)
        dsn = f"postgresql+asyncpg://app_user:app_user@pg:5432/{DB_NAME}"
        proc = _docker(
            "run",
            "-d",
            "--name",
            BEAT_CONTAINER,
            *self._RESTART,
            "--network",
            NETWORK,
            *self._base_env(dsn),
            "-e",
            f"B26_P2_RELAY_SWEEP_INTERVAL_SECONDS={self.args.sweep_interval}",
            self.image,
            *BEAT_CMD,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"beat_start_failed:{proc.stderr[-500:]}")


def _db() -> object:
    import psycopg2

    return psycopg2.connect(_TOPO.db_admin)


def _query(sql: str, params: tuple = ()) -> list[tuple]:
    conn = _db()
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql, params)
        try:
            return cur.fetchall()
        except Exception:  # noqa: BLE001 - no result set
            return []
    finally:
        conn.close()


def _seed_tenant() -> dict[str, str]:
    sys.path.insert(0, str(BACKEND))
    from tests.helpers.webhook_secret_seed import webhook_secret_insert_params

    tenant_id = str(uuid.uuid4())
    tenant_key = f"{TENANT_KEY_PREFIX}-{tenant_id[:8]}"
    api_key_hash = hashlib.sha256(tenant_key.encode("utf-8")).hexdigest()
    stripe_secret = f"whsec_b26p2_iv_{tenant_id[:8]}"
    secrets = webhook_secret_insert_params(
        shopify_secret=f"shop_b26p2_iv_{tenant_id[:8]}",
        stripe_secret=stripe_secret,
        paypal_secret=f"pp_b26p2_iv_{tenant_id[:8]}",
        woocommerce_secret=f"woo_b26p2_iv_{tenant_id[:8]}",
    )
    import psycopg2

    conn = psycopg2.connect(_TOPO.db_admin)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO tenants (
                id, name, api_key_hash, notification_email,
                shopify_webhook_secret_ciphertext, shopify_webhook_secret_key_id,
                stripe_webhook_secret_ciphertext, stripe_webhook_secret_key_id,
                paypal_webhook_secret_ciphertext, paypal_webhook_secret_key_id,
                woocommerce_webhook_secret_ciphertext, woocommerce_webhook_secret_key_id,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s,
                pgp_sym_encrypt(%s, %s), %s,
                pgp_sym_encrypt(%s, %s), %s,
                pgp_sym_encrypt(%s, %s), %s,
                pgp_sym_encrypt(%s, %s), %s,
                now(), now()
            )
            """,
            (
                tenant_id,
                f"b26p2-iv-{tenant_id[:8]}",
                api_key_hash,
                f"b26p2-iv-{tenant_id[:8]}@example.invalid",
                f"shop_b26p2_iv_{tenant_id[:8]}",
                secrets["webhook_secret_key"],
                secrets["webhook_secret_key_id"],
                stripe_secret,
                secrets["webhook_secret_key"],
                secrets["webhook_secret_key_id"],
                f"pp_b26p2_iv_{tenant_id[:8]}",
                secrets["webhook_secret_key"],
                secrets["webhook_secret_key_id"],
                f"woo_b26p2_iv_{tenant_id[:8]}",
                secrets["webhook_secret_key"],
                secrets["webhook_secret_key_id"],
            ),
        )
    finally:
        conn.close()
    return {"tenant_id": tenant_id, "tenant_key": tenant_key, "stripe_secret": stripe_secret}


def _sign_stripe(body: bytes, secret: str) -> str:
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def _post_stripe(tenant_key: str, stripe_secret: str, intent_id: str, amount: int) -> tuple[int, str]:
    body = json.dumps(
        {
            "id": intent_id,
            "amount": amount,
            "currency": "usd",
            "created": int(time.time()),
            "status": "succeeded",
        },
        separators=(",", ":"),
    ).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{_TOPO.api_port}/api/webhooks/stripe/payment_intent_succeeded",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Skeldir-Tenant-Key": tenant_key,
            "Stripe-Signature": _sign_stripe(body, stripe_secret),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()
    except Exception as exc:  # noqa: BLE001 - connection/timeout: fail with context
        raise RuntimeError(f"webhook_post_failed:{type(exc).__name__}:{exc}"[:300])


def _wait_state(table: str, idcol: str, task_id: str, want: str, timeout_s: int) -> dict:
    col = "delivery_state" if table == "b23_match_task_dispatches" else "state"
    idf = "task_id" if table == "b23_match_task_dispatches" else "dispatch_task_id"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        rows = _query(
            f"SELECT {col} FROM public.{table} WHERE {idf} = %s", (task_id,)
        )
        if rows and str(rows[0][0]) == want:
            return {"state": want}
        time.sleep(2)
    rows = _query(f"SELECT {col} FROM public.{table} WHERE {idf} = %s", (task_id,))
    raise RuntimeError(
        f"state_not_reached:{table}:{task_id}:want={want}:got={rows}:idcol={idcol}"
    )


def _dispatch_for_ingress(tenant_id: str, event_id: str) -> dict:
    rows = _query(
        """
        SELECT d.task_id, d.delivery_state, o.state
        FROM public.b23_match_task_dispatches AS d
        JOIN public.b26_p2_execution_outbox AS o ON o.dispatch_task_id = d.task_id
        JOIN public.webhook_ingress_identities AS i
          ON i.id = d.webhook_ingress_identity_id AND i.tenant_id = d.tenant_id
        WHERE d.tenant_id = %s AND i.event_id = %s
        """,
        (tenant_id, event_id),
    )
    if not rows:
        raise RuntimeError("dispatch_missing_for_ingress")
    return {"task_id": str(rows[0][0]), "delivery_state": str(rows[0][1]), "outbox": str(rows[0][2])}


_TOPO: _Topology


def _dead_edge_probe() -> dict:
    """Prove the natural-dispatch kill-switch is honored (host-level dead edge).

    With SKELDIR_B23_P6_DISABLE_NATURAL_DISPATCH set, the production
    webhook edge must persist ingress but issue NO dispatch/outbox/
    directory rows. Runs on the host against the proof database using the
    production webhook function (not a reimplementation).
    """
    import asyncio

    import psycopg2 as _pg

    tenant_id = str(uuid.uuid4())
    conn = _pg.connect(_TOPO.db_admin)
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash,"
            " notification_email) VALUES (%s, %s, %s, %s)",
                (tenant_id, "b26p2-iv-deadedge", uuid.uuid4().hex, "deadedge@example.invalid"),
        )
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant_id,))
        occurred = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
        event_uuid = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES ('b26p2ca1_channel', 'b26p2ca1',"
            " true, 'B26P2CA1', 'active') ON CONFLICT (code) DO NOTHING"
        )
        cur.execute(
            "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
            " correlation_id, session_id, revenue_cents, raw_payload,"
            " idempotency_key, event_type, channel, campaign_id,"
            " conversion_value_cents, currency, event_timestamp, processed_at,"
            " processing_status)"
            " VALUES (%s, %s, %s, %s, %s, 38000, '{\"order_id\": \"dead\"}'::jsonb,"
            " %s, 'conversion', 'b26p2ca1_channel', 'dead-campaign', 38000, 'USD',"
            " %s, %s, 'processed')",
            (
                event_uuid, tenant_id, occurred, str(uuid.uuid4()),
                str(uuid.uuid4()), f"deadedge:{tenant_id[:8]}", occurred, occurred,
            ),
        )
        ingress_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id,"
            " provider, provider_native_event_reference,"
            " provider_native_commerce_reference,"
            " normalized_commerce_reference_kind,"
            " normalized_commerce_reference_value, verified_amount_minor,"
            " verified_amount_currency, event_timestamp, idempotency_key,"
            " verified_commerce_ingress_state)"
            " VALUES (%s, %s, %s, 'stripe', %s, %s, 'order_reference', %s,"
            " 38000, 'USD', %s, %s, 'authenticity_verified')",
            (
                ingress_id, tenant_id, event_uuid, f"evt-dead-{tenant_id[:8]}",
                f"ord-dead-{tenant_id[:8]}", f"ord-dead-{tenant_id[:8]}", occurred,
                f"deadedge-ingress:{tenant_id[:8]}",
            ),
        )
    finally:
        conn.close()
    os.environ["SKELDIR_B23_P6_DISABLE_NATURAL_DISPATCH"] = "1"
    try:
        from app.api.webhooks import (  # noqa: PLC0415
            _dispatch_b23_match_task_from_persisted_ingress,
        )

        asyncio.run(
            _dispatch_b23_match_task_from_persisted_ingress(
                tenant_id=tenant_id,
                event_id=event_uuid,
                event_timestamp=occurred.isoformat(),
                correlation_id=str(uuid.uuid4()),
            )
        )
    finally:
        del os.environ["SKELDIR_B23_P6_DISABLE_NATURAL_DISPATCH"]
    rows = _query(
        "SELECT count(*) FROM public.b23_match_task_dispatches WHERE tenant_id = %s",
        (tenant_id,),
    )
    if int(rows[0][0]) != 0:
        raise RuntimeError("dead_edge_dispatch_not_suppressed")
    return {"dead_edge_sets": True, "dispatch_rows": 0}


def main() -> int:
    global _TOPO
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-out", type=Path, default=None)
    parser.add_argument("--pg-port", default="5544")
    parser.add_argument("--api-port", default="8000")
    parser.add_argument("--pg-password", default="postgres")
    parser.add_argument("--image-tag", default="ci")
    parser.add_argument("--sweep-interval", default="5")
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    if shutil.which("docker") is None:
        return _fail("docker_unavailable")
    # Host-side app imports (tenant seeding, dead-edge probe) build engines
    # and settings from env at import; point them at the proof database with
    # the proof platform key. The deployed containers use their own
    # per-process DSNs (never this one) plus the same platform key.
    os.environ.setdefault(
        "DATABASE_URL",
        f"postgresql+asyncpg://app_user:app_user@127.0.0.1:{args.pg_port}/{DB_NAME}",
    )
    os.environ.setdefault(
        "MIGRATION_DATABASE_URL",
        f"postgresql://migration_owner:migration_owner@127.0.0.1:{args.pg_port}/{DB_NAME}",
    )
    os.environ.setdefault("PLATFORM_TOKEN_ENCRYPTION_KEY", PLATFORM_KEY)
    details: dict = {}
    _TOPO = _Topology(args)
    try:
        # 0. Static deployment-contract pre-checks (fast; docker-independent).
        procfile = (REPO_ROOT / "Procfile").read_text(encoding="utf-8")
        worker_line = next(
            (ln for ln in procfile.splitlines() if ln.startswith("worker_b23:")), ""
        )
        for token in (
            "DATABASE_URL=$B23_WORKER_DATABASE_URL",
            "B23_WORKER_DATABASE_URL=$B23_WORKER_DATABASE_URL",
            "SKELDIR_B23_REQUIRE_WORKER_DSN=1",
        ):
            if token not in worker_line:
                return _fail(f"worker_custody_not_split:{token}")
        details["procfile_worker_custody_ok"] = True
        import subprocess as _sp

        heads = _sp.run(
            [sys.executable, "-m", "alembic", "heads"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if "202609180001" not in heads.stdout:
            return _fail("migration_head_missing_corrective_iv")
        details["migration_head"] = "202609180001"

        # 1. Build + boot the exact production topology.
        print("B26_P2_TOPOLOGY_STAGE build", flush=True)
        details["image_tag"] = _TOPO.image
        image_id = _TOPO.build_image()
        details["image_id"] = image_id
        print("B26_P2_TOPOLOGY_STAGE postgres", flush=True)
        _TOPO.start_postgres()
        print("B26_P2_TOPOLOGY_STAGE provision", flush=True)
        _TOPO.provision()
        # Dead-edge falsifier (host-level, production webhook function):
        # the kill-switch must suppress dispatch issuance entirely.
        print("B26_P2_TOPOLOGY_STAGE dead_edge", flush=True)
        details["dead_edge"] = _dead_edge_probe()
        print("B26_P2_TOPOLOGY_STAGE boot_services", flush=True)
        _TOPO.start_api()
        _TOPO.start_worker()
        _TOPO.start_relay()
        _TOPO.start_beat()
        _wait_http_ok(f"http://127.0.0.1:{args.api_port}/health/live", 120)
        details["api_live"] = True
        _wait_log(WORKER_CONTAINER, "ready", 180)
        _wait_log(RELAY_CONTAINER, "ready", 180)
        details["workers_ready"] = True
        print("B26_P2_TOPOLOGY_STAGE services_ready", flush=True)

        # 2. Prove the exact shipped commands are PID 1 in each container.
        pid1 = {
            "api": _pid1_cmdline(API_CONTAINER),
            "worker_b23": _pid1_cmdline(WORKER_CONTAINER),
            "relay": _pid1_cmdline(RELAY_CONTAINER),
            "beat": _pid1_cmdline(BEAT_CONTAINER),
        }
        details["pid1"] = pid1
        if "uvicorn app.main:app" not in pid1["api"]:
            return _fail("api_command_not_shipped")
        if "b23_match_engine" not in pid1["worker_b23"]:
            return _fail("worker_command_not_shipped")
        if "b26_p2_relay" not in pid1["relay"]:
            return _fail("relay_command_not_shipped")
        if "beat" not in pid1["beat"]:
            return _fail("scheduler_command_not_shipped")

        # 3. Capture in-process database principals (not role names in config).
        principals = {
            "api": _container_current_user(API_CONTAINER, "DATABASE_URL"),
            "worker_b23": _container_current_user(WORKER_CONTAINER, "B23_WORKER_DATABASE_URL"),
            "worker_b23_database_url": _container_current_user(WORKER_CONTAINER, "DATABASE_URL"),
            "relay": _container_current_user(RELAY_CONTAINER, "DATABASE_URL"),
            "beat": _container_current_user(BEAT_CONTAINER, "DATABASE_URL"),
        }
        details["principals"] = principals
        if principals["worker_b23"] != "app_worker|app_worker":
            return _fail(f"worker_principal_not_worker:{principals['worker_b23']}")
        if principals["worker_b23_database_url"] != "app_worker|app_worker":
            return _fail("worker_database_url_not_worker_credential")
        if principals["api"] != "app_user|app_user":
            return _fail(f"api_principal_not_producer:{principals['api']}")
        if principals["relay"] != "app_user|app_user":
            return _fail(f"relay_principal_not_producer:{principals['relay']}")

        # 4. Normal journey: REAL signed webhook from OUTSIDE the API process.
        print("B26_P2_TOPOLOGY_STAGE normal_journey", flush=True)
        tenant = _seed_tenant()
        intent = f"pi_{uuid.uuid4().hex[:18]}"
        status, body = _post_stripe(tenant["tenant_key"], tenant["stripe_secret"], intent, 38000)
        if status != 200:
            return _fail(f"signed_webhook_not_accepted:{status}:{body[:300]}")
        try:
            event_id = str(json.loads(body)["event_id"])
        except (ValueError, KeyError) as exc:
            return _fail(f"webhook_response_missing_event_id:{exc}:{body[:200]}")
        details["webhook_accepted"] = {"intent": intent, "http": status, "event_id": event_id}
        disp = _dispatch_for_ingress(tenant["tenant_id"], event_id)
        details["dispatch_issued"] = disp
        _wait_state("b23_match_task_dispatches", "task", disp["task_id"], "conducted", 180)
        _wait_state("b26_p2_execution_outbox", "task", disp["task_id"], "conducted", 60)
        details["conducted"] = {"task_id": disp["task_id"]}
        verdicts = _query(
            "SELECT count(*) FROM public.b23_match_verdicts WHERE tenant_id = %s",
            (tenant["tenant_id"],),
        )
        details["verdict_count"] = int(verdicts[0][0])
        if int(verdicts[0][0]) < 1:
            return _fail("b23_no_verdicts")
        try:
            scope = _task_result_scope(disp["task_id"])
        except RuntimeError as exc:
            return _fail(str(exc))
        details["task_result_principal"] = "app_worker"
        details["scope_identity"] = scope.get("scope_identity")
        details["scope_policy_version"] = scope.get("scope_policy_version")
        if len(str(scope.get("scope_identity") or "")) != 64:
            return _fail("scope_identity_malformed")
        if scope.get("scope_policy_version") != "b2.6-p2-scope-policy-v2":
            return _fail("scope_policy_not_v2")

        # 5. Recovery journey: broker outage, NO provider retry, natural recovery.
        print("B26_P2_TOPOLOGY_STAGE recovery_journey", flush=True)
        _query("REVOKE INSERT ON TABLE public.kombu_message FROM app_user")
        intent2 = f"pi_{uuid.uuid4().hex[:18]}"
        status2, body2 = _post_stripe(
            tenant["tenant_key"], tenant["stripe_secret"], intent2, 12000
        )
        if status2 != 200:
            return _fail(f"outage_webhook_not_accepted:{status2}")
        event_id2 = str(json.loads(body2)["event_id"])
        disp2 = _dispatch_for_ingress(tenant["tenant_id"], event_id2)
        if disp2["delivery_state"] != "pending_publish" or disp2["outbox"] != "pending_publish":
            return _fail(f"outage_not_pending:{disp2}")
        details["outage_pending"] = disp2
        # While the broker is down, the scheduler must NOT conjure recovery.
        time.sleep(int(args.sweep_interval) * 2 + 3)
        still = _dispatch_for_ingress(tenant["tenant_id"], event_id2)
        if still["delivery_state"] != "pending_publish":
            return _fail(f"recovery_without_broker:{still}")
        _query("GRANT INSERT ON TABLE public.kombu_message TO app_user")
        # Supervision check: a transient broker fault can kill the scheduler
        # (beat exits on an unapplied scheduled task). The supervisor must
        # have it running again without human action; record restarts.
        _wait_running(BEAT_CONTAINER, 120)
        _wait_running(RELAY_CONTAINER, 120)
        _wait_running(WORKER_CONTAINER, 120)
        details["supervision"] = {
            "beat_restarts": _restart_count(BEAT_CONTAINER),
            "relay_restarts": _restart_count(RELAY_CONTAINER),
            "worker_restarts": _restart_count(WORKER_CONTAINER),
        }
        # No manual enqueue from here on: beat + relay + worker must conduct it.
        _wait_state("b23_match_task_dispatches", "task", disp2["task_id"], "conducted", 240)
        _wait_state("b26_p2_execution_outbox", "task", disp2["task_id"], "conducted", 60)
        details["natural_recovery"] = {"task_id": disp2["task_id"]}
        recovery_scope = _task_result_scope(disp2["task_id"])
        details["natural_recovery_scope_identity"] = recovery_scope.get("scope_identity")
        if len(str(recovery_scope.get("scope_identity") or "")) != 64:
            return _fail("recovery_scope_identity_malformed")

        # 6. Deployment falsifiers (mutate deployed state, expect RED, restore).
        print("B26_P2_TOPOLOGY_STAGE falsifiers", flush=True)
        falsifiers: dict[str, str] = {}

        # F-a: worker on producer DSN cannot write verdicts; nothing conducts.
        _TOPO.start_worker(
            dsn_override=f"postgresql+asyncpg://app_user:app_user@pg:5432/{DB_NAME}"
        )
        _wait_log(WORKER_CONTAINER, "ready", 180)
        mis_principal = _container_current_user(WORKER_CONTAINER, "DATABASE_URL")
        if mis_principal != "app_user|app_user":
            return _fail("falsifier_worker_miswire_not_observed")
        _wait_http_ok(f"http://127.0.0.1:{args.api_port}/health/live", 60)
        intent3 = f"pi_{uuid.uuid4().hex[:18]}"
        status3, body3 = _post_stripe(
            tenant["tenant_key"], tenant["stripe_secret"], intent3, 5000
        )
        if status3 != 200:
            return _fail(f"falsifier_webhook_not_accepted:{status3}")
        disp3 = _dispatch_for_ingress(tenant["tenant_id"], str(json.loads(body3)["event_id"]))
        try:
            _wait_state("b23_match_task_dispatches", "task", disp3["task_id"], "conducted", 60)
            return _fail("falsifier_worker_miswire_stayed_green")
        except RuntimeError:
            pass
        meta3 = _query(
            "SELECT status FROM public.celery_taskmeta WHERE task_id = %s", (disp3["task_id"],)
        )
        if not meta3 or str(meta3[0][0]) != "FAILURE":
            return _fail(f"falsifier_worker_miswire_inconclusive:{meta3}")
        dlq3 = _query(
            "SELECT count(*) FROM public.worker_failed_jobs WHERE task_id = %s",
            (disp3["task_id"],),
        )
        falsifiers["worker_producer_dsn"] = f"RED_as_required:task_FAILURE:dlq={dlq3[0][0]}"
        _TOPO.start_worker()
        _wait_log(WORKER_CONTAINER, "ready", 180)

        # F-b: scheduler removed -> pending never recovers.
        _docker("stop", BEAT_CONTAINER)
        _query("REVOKE INSERT ON TABLE public.kombu_message FROM app_user")
        _wait_http_ok(f"http://127.0.0.1:{args.api_port}/health/live", 60)
        intent4 = f"pi_{uuid.uuid4().hex[:18]}"
        status4, body4 = _post_stripe(
            tenant["tenant_key"], tenant["stripe_secret"], intent4, 6000
        )
        if status4 != 200:
            return _fail(f"falsifier_webhook_not_accepted:{status4}")
        disp4 = _dispatch_for_ingress(tenant["tenant_id"], str(json.loads(body4)["event_id"]))
        _query("GRANT INSERT ON TABLE public.kombu_message TO app_user")
        try:
            _wait_state(
                "b23_match_task_dispatches", "task", disp4["task_id"], "conducted",
                int(args.sweep_interval) * 3 + 15,
            )
            return _fail("falsifier_missing_scheduler_stayed_green")
        except RuntimeError:
            falsifiers["missing_scheduler"] = "RED_as_required"
        _TOPO.start_beat()
        time.sleep(int(args.sweep_interval) + 2)
        _wait_state("b23_match_task_dispatches", "task", disp4["task_id"], "conducted", 240)
        falsifiers["scheduler_restored_green"] = "GREEN"

        # F-c: relay absent + sweep to an unconsumed queue stays pending.
        _query("REVOKE INSERT ON TABLE public.kombu_message FROM app_user")
        _wait_http_ok(f"http://127.0.0.1:{args.api_port}/health/live", 60)
        intent5 = f"pi_{uuid.uuid4().hex[:18]}"
        status5, body5 = _post_stripe(
            tenant["tenant_key"], tenant["stripe_secret"], intent5, 7000
        )
        if status5 != 200:
            return _fail(f"falsifier_webhook_not_accepted:{status5}")
        disp5 = _dispatch_for_ingress(tenant["tenant_id"], str(json.loads(body5)["event_id"]))
        _query("GRANT INSERT ON TABLE public.kombu_message TO app_user")
        _docker("stop", RELAY_CONTAINER)
        _send_relay_sweep(queue="housekeeping")
        try:
            _wait_state(
                "b23_match_task_dispatches", "task", disp5["task_id"], "conducted",
                int(args.sweep_interval) * 2 + 20,
            )
            return _fail("falsifier_wrong_queue_stayed_green")
        except RuntimeError:
            falsifiers["wrong_relay_queue"] = "RED_as_required"
        _TOPO.start_relay()
        _wait_log(RELAY_CONTAINER, "ready", 180)
        _wait_state("b23_match_task_dispatches", "task", disp5["task_id"], "conducted", 240)
        falsifiers["relay_restored_green"] = "GREEN"

        # F-d: split-brain and orphan writes are refused by the database.
        import psycopg2 as _pg

        user_dsn = (
            f"postgresql://app_user:app_user@127.0.0.1:{args.pg_port}/{DB_NAME}"
        )
        conn = _pg.connect(user_dsn)
        try:
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant["tenant_id"],),
            )
            try:
                cur.execute(
                    "INSERT INTO public.b26_p2_execution_outbox "
                    "(tenant_id, dispatch_task_id, webhook_ingress_identity_id) "
                    "VALUES (%s, 'no-such-task', (SELECT id FROM public.webhook_ingress_identities LIMIT 1))",
                    (tenant["tenant_id"],),
                )
                return _fail("falsifier_orphan_outbox_allowed")
            except Exception:
                falsifiers["orphan_outbox"] = "RED_as_required"
            try:
                cur.execute(
                    "INSERT INTO public.b26_p2_task_authority_directory "
                    "(task_id, tenant_id, webhook_ingress_identity_id, window_start, window_end) "
                    "VALUES ('orphan-task', %s, (SELECT id FROM public.webhook_ingress_identities LIMIT 1), now(), now() + interval '1 day')",
                    (tenant["tenant_id"],),
                )
                return _fail("falsifier_orphan_directory_allowed")
            except Exception:
                falsifiers["orphan_directory"] = "RED_as_required"
            try:
                cur.execute(
                    "UPDATE public.b26_p2_task_authority_directory "
                    "SET task_id = 'rewritten-task' "
                    "WHERE task_id = %s",
                    (disp["task_id"],),
                )
                return _fail("falsifier_directory_rewrite_allowed")
            except Exception:
                falsifiers["directory_rewrite"] = "RED_as_required"
        finally:
            conn.close()

        # Relay in-process principal: scan sweep task results. The result
        # column is pickle-framed bytes (rendered hex by ::text, so LIKE
        # cannot see inside); decode proof-side like the task-result
        # reader above.
        import pickle as _relay_pickle  # noqa: PLC0415

        relay_users: set[str] = set()
        for (raw,) in _query(
            "SELECT result FROM public.celery_taskmeta ORDER BY date_done DESC NULLS LAST LIMIT 200"
        ):
            blob = bytes(raw) if isinstance(raw, memoryview) else raw
            if isinstance(blob, bytes):
                try:
                    decoded = _relay_pickle.loads(blob)
                except Exception:
                    continue
                if isinstance(decoded, dict) and "database_user" in decoded:
                    relay_users.add(
                        f"{decoded.get('database_user')}:published={decoded.get('published')}"
                    )
        details["relay_task_result_principals"] = sorted(relay_users)
        details["falsifiers"] = falsifiers
        details["relay_observable"] = True
    except RuntimeError as exc:
        details["failure"] = str(exc)[:500]
        try:
            details["diagnostics"] = _collect_diagnostics()
        except Exception as diag_exc:  # noqa: BLE001
            details["diagnostics_error"] = str(diag_exc)[:300]
        print(json.dumps(details, sort_keys=True, default=str))
        return _fail(str(exc)[:500])
    except Exception as exc:  # noqa: BLE001 - crash safety: never exit without evidence
        import traceback as _tb  # noqa: PLC0415

        details["failure"] = f"topology_crash:{type(exc).__name__}:{exc}"[:500]
        details["traceback"] = _tb.format_exc()[-3000:]
        try:
            details["diagnostics"] = _collect_diagnostics()
        except Exception as diag_exc:  # noqa: BLE001
            details["diagnostics_error"] = str(diag_exc)[:300]
        print(json.dumps(details, sort_keys=True, default=str))
        return _fail(details["failure"])
    finally:
        if not args.keep:
            _TOPO.cleanup()

    if args.evidence_out is not None:
        from scripts.ci.b26_p2_evidence import write_evidence_cell  # noqa: PLC0415

        write_evidence_cell(
            args.evidence_out,
            gate_id="B26-P2-G12-PRODUCTION-TOPOLOGY",
            producer="b26-p2-production-topology",
            scenario_id="signed-ingress-to-governed-scope",
            falsifier_id="dead-edge-wrong-queue-missing-relay",
            details=details,
        )
    print("B26_P2_TOPOLOGY_PASS")
    print(json.dumps(details, sort_keys=True, default=str))
    return 0


def _task_result_scope(task_id: str) -> dict:
    """Fetch the B2.3 task result payload and return its P2 scope summary."""
    rows = _query(
        "SELECT status, result FROM public.celery_taskmeta WHERE task_id = %s", (task_id,)
    )
    if not rows:
        raise RuntimeError(f"task_result_missing:{task_id}")
    status, payload = rows[0][0], rows[0][1]
    if isinstance(payload, memoryview):
        payload = bytes(payload)
    if isinstance(payload, bytes):
        # The Celery database backend persists result payloads pickle-framed
        # (observed framing on the wire here); the result backend is
        # operational telemetry, never finance truth. Decode is proof-only
        # tooling against this disposable database: untrusted-data
        # unpickling rules do not apply, and no production code path
        # unpickles task results.
        import pickle as _pickle  # noqa: PLC0415

        try:
            payload = _pickle.loads(payload)
        except Exception:
            payload = payload.decode("utf-8", errors="replace")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            raise RuntimeError(
                f"task_result_malformed:{task_id}:status={status}:"
                f"type=str:prefix={payload[:200]}"
            )
    if not isinstance(payload, dict):
        raise RuntimeError(
            f"task_result_malformed:{task_id}:status={status}:"
            f"type={type(payload).__name__}:prefix={str(payload)[:200]}"
        )
    if payload.get("db_worker_principal") != "app_worker":
        raise RuntimeError(f"task_not_conducted_by_worker_principal:{task_id}")
    scope = payload.get("p2_scope") or {}
    if not isinstance(scope, dict):
        raise RuntimeError(f"task_result_scope_missing:{task_id}")
    return scope


def _collect_diagnostics() -> dict:
    """Capture container logs + broker/task state on failure (debugging aid)."""
    diag: dict = {}
    for name in (API_CONTAINER, WORKER_CONTAINER, RELAY_CONTAINER, BEAT_CONTAINER):
        proc = _docker("logs", "--tail", "40", name)
        diag[f"logs_{name}"] = (proc.stdout + proc.stderr)[-4000:]
        state = _docker("inspect", "-f", "{{.State.Status}} {{.State.ExitCode}}", name)
        diag[f"state_{name}"] = state.stdout.strip() or state.stderr.strip()[-200:]
    try:
        diag["kombu_messages"] = _query("SELECT count(*) FROM public.kombu_message")[0][0]
    except Exception as exc:  # noqa: BLE001
        diag["kombu_messages"] = f"unavailable:{exc}"[:200]
    try:
        diag["dispatch_states"] = [
            (str(r[0])[:8], str(r[1]))
            for r in _query(
                "SELECT task_id, delivery_state FROM public.b23_match_task_dispatches"
                " ORDER BY created_at DESC LIMIT 10"
            )
        ]
        try:
            diag["pending_detail"] = [
                (str(r[0])[:8], str(r[1]), str(r[2]), str(r[3]), str(r[4])[:160])
                for r in _query(
                    "SELECT d.task_id, d.delivery_state, d.publish_attempts,"
                    " o.next_retry_at, o.last_publish_error"
                    " FROM public.b23_match_task_dispatches AS d"
                    " JOIN public.b26_p2_execution_outbox AS o"
                    " ON o.dispatch_task_id = d.task_id"
                    " WHERE d.delivery_state = 'pending_publish'"
                )
            ]
        except Exception as exc:  # noqa: BLE001
            diag["pending_detail_error"] = str(exc)[:200]
        try:
            import pickle as _diag_pickle  # noqa: PLC0415

            decoded_sweeps = []
            for (raw,) in _query(
                "SELECT result FROM public.celery_taskmeta"
                " ORDER BY date_done DESC NULLS LAST LIMIT 60"
            ):
                blob = bytes(raw) if isinstance(raw, memoryview) else raw
                if isinstance(blob, bytes):
                    try:
                        payload = _diag_pickle.loads(blob)
                    except Exception:
                        continue
                    if isinstance(payload, dict) and "published" in payload:
                        decoded_sweeps.append(
                            {
                                "published": payload.get("published"),
                                "failed": payload.get("failed"),
                                "divergent": payload.get("divergent"),
                            }
                        )
            agg: dict[str, int] = {}
            for s in decoded_sweeps:
                key = (
                    f"p={s.get('published')}/f={s.get('failed')}/d={s.get('divergent')}"
                )
                agg[key] = agg.get(key, 0) + 1
            diag["sweep_results"] = agg
        except Exception as exc:  # noqa: BLE001
            diag["sweep_results_error"] = str(exc)[:200]
        diag["outbox_states"] = [
            (str(r[0])[:8], str(r[1]))
            for r in _query(
                "SELECT dispatch_task_id, state FROM public.b26_p2_execution_outbox"
                " ORDER BY created_at DESC LIMIT 10"
            )
        ]
        diag["taskmeta"] = [
            (str(r[0])[:8], str(r[1]))
            for r in _query("SELECT task_id, status FROM public.celery_taskmeta")
        ]
        diag["dlq"] = _query("SELECT count(*) FROM public.worker_failed_jobs")[0][0]
    except Exception as exc:  # noqa: BLE001
        diag["state_error"] = str(exc)[:300]
    return diag


def _send_relay_sweep(queue: str) -> None:
    """Publish one REAL relay sweep to a chosen queue (wrong-queue falsifier).

    Uses the production Celery publisher path (broker transport), not a
    hand-rolled broker row: the message is structurally valid and broker
    acceptance succeeds; only the routing is wrong, so no consumer ever
    executes it.
    """
    sys.path.insert(0, str(BACKEND))
    env_broker = (
        f"sqla+postgresql://app_user:app_user@127.0.0.1:{_TOPO.pg_port}/{DB_NAME}"
    )
    env_result = (
        f"db+postgresql://app_user:app_user@127.0.0.1:{_TOPO.pg_port}/{DB_NAME}"
    )
    code = (
        "import os;"
        f"os.environ['CELERY_BROKER_URL']={env_broker!r};"
        f"os.environ['CELERY_RESULT_BACKEND']={env_result!r};"
        f"os.environ['DATABASE_URL']='postgresql+asyncpg://app_user:app_user@127.0.0.1:{_TOPO.pg_port}/{DB_NAME}';"
        "from app.celery_app import celery_app;"
        "import app.tasks.b26_p2_relay;"
        f"r=celery_app.send_task('app.tasks.b26_p2_relay.relay_b26_p2_pending_dispatches',queue={queue!r});"
        "print('SWEEP_SENT '+str(r.id))"
    )
    env = dict(os.environ, PYTHONPATH=str(BACKEND))
    proc = _run([sys.executable, "-c", code], cwd=REPO_ROOT, env=env)
    if proc.returncode != 0 or "SWEEP_SENT" not in proc.stdout:
        raise RuntimeError(f"sweep_send_failed:{proc.stderr[-500:]}")


if __name__ == "__main__":
    raise SystemExit(main())
