#!/usr/bin/env python3
"""B2.6-P2 Corrective VI deployed-topology proof (Gates 1-33).

Boots the EXACT compiled production topology and drives a REAL
HMAC-signed webhook from OUTSIDE the API process through the full causal
chain using the EXACT shipped commands, process identities, database
principals, queues, schedulers, and failure-recovery mechanisms:

  API (Dockerfile CMD, app_user: issuance only)
    -> real signed Stripe webhook over HTTP (host -> container)
    -> atomic dispatch + outbox + admission-directory commit (one tuple)
    -> real broker publish (kombu sqla transport, stable task_id)
  worker_b23 (exact Procfile command, B23 worker credential)
    -> admission BEFORE B2.3 (constrained resolver, no GUC trust)
    -> authorized B2.3 verdict writes
    -> governed P2 scope (REPEATABLE READ, RLS strict, identity v3)
    -> conduction receipt + server-side conducted gate (no direct mark)
  relay (exact Procfile command, relay credential: recover/publish only)
    + beat (exact beat command, scheduler credential: schedule only)

Then proves FAILURE RECOVERY is natural (no manual enqueue): broker
outage -> pending_publish -> broker restored -> scheduler + relay +
worker conduct the SAME execution identity to conducted.

Then runs deployment-level falsifiers (each must RED the observed
property, then restore GREEN):
  F-a worker on producer DSN: verdict writes die, nothing conducts
  F-b scheduler removed: pending never recovers
  F-c sweep to unconsumed queue: pending never recovers
  F-d split-brain / orphan writes: database refuses (tuple law)
  F-e bootstrap grant removed: equivalence proof REDs
  F-f stale image: container identity diverges from host
  F-g comment-only policy edit: identity EQUAL (v3 semantic law)
  F-h semantic policy edit: identity CHANGED + validator REDs
  F-v1 false conducted: direct mark refused; gate path conducts
  F-v2 published-unconsumed: staleness signal fires, then drains
  F-v3 recovery mint: relay/beat cannot issue execution authority
  F-vi1 forged canonical dispatch: issuer persistence refuses (sovereign)
  F-vi2 worker synthesis: direct INSERT denied, junk scope refused
  F-vi3 evaluator wiring: beat-scheduled consumer executes in topology,
    sweep/evaluator results record the signal, quarantine fields served,
    metadata bumps cannot reset the anchor, absurd thresholds refuse

Negative controls that only need source text live in
test_b26_p2_negative_controls.py (60/60). The controls here need the
DEPLOYED plane: they mutate deployment state, never host source.
Database-plane defect injection lives in b26_p2_vi_negatives.py
(M-VI-01..16); the capability-derived class gate at the end of this
proof fails coverage while any mechanically reachable load-bearing
surface is untested (b26_p2_capability_surface.py +
b26_p2_vi_coverage.py).

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
import re
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
AUTH_CONTAINER = "b26p2-iv-auth"
WORKER_CONTAINER = "b26p2-iv-worker-b23"
RELAY_CONTAINER = "b26p2-iv-relay"
BEAT_CONTAINER = "b26p2-iv-beat"
DB_NAME = "skeldir_b26_p2_deployed"
PLATFORM_KEY = "b26-p2-iv-platform-key-do-not-use-outside-ci"
TENANT_KEY_PREFIX = "b26p2-iv-tenant-key"
# XVI provider parity: PayPal test cert URL (paypal-suffixed host so the
# provider URL law holds; the cryptography below is test-only via the
# SKELDIR_PAYPAL_TEST_CERT_* override + TESTING=1 in the API container).
_PAYPAL_CERT_URL = "https://cert.test.paypal.com/xvi-paypal-test.pem"

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
AUTH_CMD = [
    "uvicorn",
    "app.auth_service.server:app",
    "--host",
    "0.0.0.0",
    "--port",
    "8001",
]


def _fail(msg: str) -> int:
    print(f"B26_P2_TOPOLOGY_FAIL {msg}")
    return 1


def _write_failure_evidence(args: argparse.Namespace, details: dict) -> None:
    """Persist failure details to a sibling file (stdout may be truncated)."""
    evidence_out = getattr(args, "evidence_out", None)
    if evidence_out is None:
        return
    try:
        failed_path = Path(str(evidence_out) + ".failed.json")
        failed_path.write_text(
            json.dumps(details, sort_keys=True, default=str),
            encoding="utf-8",
        )
    except Exception:  # noqa: BLE001 - evidence is best-effort on failure
        pass


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


def _assert_stopped(name: str) -> None:
    """Fail loud if a falsifier's container did not actually stop.

    `_docker("stop")` never checks its exit status; a silently
    unstopped consumer/scheduler keeps sweeping and conducting, which
    the falsifiers below would misread as a wrong GREEN. Stopped state
    is asserted explicitly so a stop failure cannot masquerade as a
    routing or recovery defect.
    """
    proc = _docker("stop", name)
    if proc.returncode != 0:
        raise RuntimeError(f"falsifier_stop_failed:{name}:{proc.stderr[-200:]}")
    deadline = time.time() + 60
    while time.time() < deadline:
        if _container_state(name) != "running":
            return
        time.sleep(2)
    raise RuntimeError(f"falsifier_stop_failed:{name}:still_running")


def _drain_broker_quiescent(timeout_s: int = 90) -> None:
    """Wait until no deliverable P2 broker messages remain, then settle.

    Stopping a scheduler/consumer does not retract messages it already
    published: a relay-task row queued just before the stop is consumed
    after the falsifier's fresh webhook exists and sweeps it. Prior
    stages all ended terminal, so a drained P2 queue set plus a short
    settle means no queued sweep can publish for the fresh dispatch;
    without this, stop-phase alignment decides the verdict.

    Only deliverable (visible) rows in the P2 queues count: rows a dead
    consumer prefetched stay invisible until the transport visibility
    timeout (far outside any window) and nobody can consume them, while
    counting them would deadlock the drain. Foreign queues (b24/b25 and
    friends, whose consumers do not exist in this topology) are excluded
    the same way: they pile forever. DB errors fail loud.
    """
    deadline = time.time() + timeout_s
    quiet_polls = 0
    while time.time() < deadline:
        rows = _query(
            "SELECT count(*) FROM public.kombu_message AS m"
            " JOIN public.kombu_queue AS q ON q.id = m.queue_id"
            " WHERE m.visible IS TRUE"
            " AND q.name IN ('b26_p2_relay', 'b23_match_engine')"
        )
        pending = int(rows[0][0]) if rows else 0
        if pending == 0:
            quiet_polls += 1
            if quiet_polls >= 2:
                time.sleep(15)
                return
        else:
            quiet_polls = 0
        time.sleep(2)
    raise RuntimeError("falsifier_broker_not_quiescent")


def _purge_p2_queues() -> None:
    """Delete visible P2-queue broker rows (falsifier setup hygiene).

    Pre-stop in-flight sweeps/evaluations are inert once their consumer
    is stopped; they predate the fresh webhook and cannot publish for
    it. Purging them makes stop-phase alignment deterministic instead
    of phase-luck. P2 queues only; foreign queues are never touched.
    """
    _query(
        "DELETE FROM public.kombu_message AS m"
        " USING public.kombu_queue AS q"
        " WHERE m.queue_id = q.id AND m.visible IS TRUE"
        " AND q.name IN ('b26_p2_relay', 'b23_match_engine')"
    )


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
        self.admin_dsn = f"postgresql://postgres:{args.pg_password}@127.0.0.1:{self.pg_port}/postgres"
        self.db_admin = f"postgresql://postgres:{args.pg_password}@127.0.0.1:{self.pg_port}/{DB_NAME}"

    # -- lifecycle ------------------------------------------------------
    def _cleanup_container(self, name: str) -> None:
        _docker("rm", "-f", name)

    def cleanup(self) -> None:
        for name in (
            BEAT_CONTAINER,
            RELAY_CONTAINER,
            WORKER_CONTAINER,
            API_CONTAINER,
            AUTH_CONTAINER,
            PG_CONTAINER,
        ):
            self._cleanup_container(name)
        _docker("network", "rm", NETWORK)
        dsn_path = getattr(self, "_auth_dsn_path", None)
        if dsn_path:
            try:
                os.unlink(dsn_path)
            except OSError:
                pass

    def build_image(self) -> str:
        if self.args.no_build:
            return self.image
        proc = _docker("build", "-f", "backend/Dockerfile", "-t", self.image, ".")
        if proc.returncode != 0:
            raise RuntimeError(f"image_build_failed:{proc.stderr[-2000:]}")
        proc = _docker("image", "inspect", self.image, "--format", "{{.Id}}")
        return proc.stdout.strip()

    def image_artifact_identity(self) -> dict:
        """Record artifact identity: image + tree + base digest (XVI-R18).

        The proof must execute the exact bytes under proof. Local content
        Id alone does not bind the base layer; record the base image
        digest and the exact source tree alongside it.
        """
        identity: dict[str, str] = {}
        proc = _docker("image", "inspect", self.image, "--format", "{{.Id}}")
        identity["image_id"] = proc.stdout.strip()
        proc = _docker(
            "image", "inspect", self.image, "--format", "{{json .RepoDigests}}"
        )
        identity["repo_digests"] = proc.stdout.strip()
        proc = _run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT)
        identity["git_sha"] = proc.stdout.strip()
        proc = _run(["git", "rev-parse", "HEAD^{tree}"], cwd=REPO_ROOT)
        identity["git_tree"] = proc.stdout.strip()
        # XVI-N9: HEAD^{tree} describes the COMMIT, not the working tree.
        # An image built from dirty bytes would otherwise carry a clean
        # identity. Tracked modifications always void the proof; untracked
        # files void it only under image-copied paths (backend/, alembic/,
        # contracts/, db/, contracts-internal/) since only those enter
        # the image (Dockerfile COPY).
        proc = _run(["git", "diff", "HEAD", "--name-only"], cwd=REPO_ROOT)
        tracked_dirty = proc.stdout.strip()
        proc = _run(["git", "status", "--porcelain"], cwd=REPO_ROOT)
        image_paths = ("backend/", "alembic/", "contracts/", "db/", "contracts-internal/")
        untracked_dirty = sorted(
            line[3:].strip().strip('"')
            for line in proc.stdout.splitlines()
            if line.startswith("??")
            and line[3:].strip().strip('"').replace("\\", "/").startswith(image_paths)
        )
        dirty = tracked_dirty + "\n" + "\n".join(untracked_dirty)
        identity["worktree_dirty"] = "false" if not dirty.strip() else "true"
        identity["worktree_dirty_paths"] = dirty.strip()[:2000]
        if dirty.strip():
            raise RuntimeError(f"dirty_tree_unprovable:{dirty.strip()[:500]}")
        dockerfile_from = next(
            (
                ln.split(None, 1)[1].strip()
                for ln in (REPO_ROOT / "backend" / "Dockerfile")
                .read_text(encoding="utf-8")
                .splitlines()
                if ln.strip().upper().startswith("FROM ")
            ),
            "",
        )
        identity["base_ref"] = dockerfile_from
        base = _docker("image", "inspect", dockerfile_from, "--format", "{{.Id}}")
        identity["base_image_id"] = (
            base.stdout.strip() if base.returncode == 0 else "unresolved"
        )
        return identity

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
        # XVI (H-XVI-R18): the migration path under proof executes inside
        # the compiled production image (no host alembic, no host
        # workspace on the database's behalf). The image carries
        # alembic.ini + the versions tree (Dockerfile COPY).
        migrate_dsn = (
            f"postgresql://migration_owner:migration_owner@pg:5432/{DB_NAME}"
        )
        proc = _docker(
            "run",
            "--rm",
            "--network",
            NETWORK,
            # The ini's version_locations are relative: run from /app so
            # the image resolves the exact shipped versions tree.
            "--workdir",
            "/app",
            "-e",
            f"MIGRATION_DATABASE_URL={migrate_dsn}",
            "-e",
            f"DATABASE_URL={migrate_dsn}",
            self.image,
            "alembic",
            "-c",
            "/app/alembic.ini",
            "upgrade",
            "head",
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"migrate_failed:{proc.stdout[-1000:]}:{proc.stderr[-1000:]}"
            )

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

    def start_api(self, extra_env: list[str] | None = None) -> None:
        self._cleanup_container(API_CONTAINER)
        dsn = f"postgresql+asyncpg://app_user:app_user@pg:5432/{DB_NAME}"
        env_extras: list[str] = []
        for item in extra_env or []:
            env_extras.extend(["-e", item])
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
            "-e",
            f"B26_P2_STALENESS_SECONDS={self.args.staleness_seconds}",
            # XIV Architecture B (production topology): the general API
            # is a non-authoritative byte relay only -- non-auth role,
            # no authenticated-ingress DB capability in any form -- and
            # relays verified arrivals to the dedicated authentication
            # trust root below (same topology as production/c19/e2e).
            "-e",
            "SKELDIR_PROCESS_ROLE=api",
            "-e",
            "B26_P2_INGRESS_DATABASE_URL=",
            "-e",
            "B26_P2_INGRESS_DATABASE_URL_FILE=",
            "-e",
            f"B26_P2_AUTH_ROOT_URL=http://{AUTH_CONTAINER}:8001",
            *env_extras,
            self.image,
            *API_CMD,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"api_start_failed:{proc.stderr[-500:]}")

    def start_auth_root(self, extra_env: list[str] | None = None) -> None:
        """Boot the dedicated authentication trust root (XIV).

        Sole holder of the file-mounted ingress credential (XIV single
        secret-delivery law). Verifies provider signatures and persists
        the full-commerce ingress row + atomic authority transition.
        Needs the application credential for tenant/secret resolution
        alongside the ingress file credential.
        """
        import tempfile  # noqa: PLC0415

        self._cleanup_container(AUTH_CONTAINER)
        dsn = f"postgresql+asyncpg://app_user:app_user@pg:5432/{DB_NAME}"
        ingress_dsn = f"postgresql+asyncpg://app_ingress:app_ingress@pg:5432/{DB_NAME}"
        fd, dsn_path = tempfile.mkstemp(prefix="b26_p2_ingress_dsn_iv_")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(ingress_dsn)
        self._auth_dsn_path = dsn_path
        env_extras: list[str] = []
        for item in extra_env or []:
            env_extras.extend(["-e", item])
        proc = _docker(
            "run",
            "-d",
            "--name",
            AUTH_CONTAINER,
            *self._RESTART,
            "--network",
            NETWORK,
            # XVI: host-mapped so hostile root-direct journeys can reach
            # the real root process (binding-refusal negatives).
            "-p",
            f"{self.args.auth_port}:8001",
            *self._base_env(dsn),
            "-e",
            "SKELDIR_PROCESS_ROLE=auth_ingress",
            "-e",
            "B26_P2_INGRESS_DATABASE_URL=",
            "-e",
            "B26_P2_INGRESS_DATABASE_URL_FILE=/run/secrets/b26_p2_ingress_dsn",
            "-v",
            f"{dsn_path}:/run/secrets/b26_p2_ingress_dsn:ro",
            *env_extras,
            self.image,
            *AUTH_CMD,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"auth_start_failed:{proc.stderr[-500:]}")

    def start_worker(self, dsn_override: str | None = None) -> None:
        self._cleanup_container(WORKER_CONTAINER)
        worker_dsn = (
            dsn_override
            or f"postgresql+asyncpg://app_worker:app_worker@pg:5432/{DB_NAME}"
        )
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
        dsn = f"postgresql+asyncpg://app_relay:app_relay@pg:5432/{DB_NAME}"
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
            "-e",
            f"B26_P2_STALENESS_SECONDS={self.args.staleness_seconds}",
            self.image,
            *RELAY_CMD,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"relay_start_failed:{proc.stderr[-500:]}")

    def start_beat(self) -> None:
        self._cleanup_container(BEAT_CONTAINER)
        dsn = f"postgresql+asyncpg://app_beat:app_beat@pg:5432/{DB_NAME}"
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
    shopify_secret = f"shop_b26p2_iv_{tenant_id[:8]}"
    paypal_secret = f"pp_b26p2_iv_{tenant_id[:8]}"
    woo_secret = f"woo_b26p2_iv_{tenant_id[:8]}"
    secrets = webhook_secret_insert_params(
        shopify_secret=shopify_secret,
        stripe_secret=stripe_secret,
        paypal_secret=paypal_secret,
        woocommerce_secret=woo_secret,
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
                shopify_secret,
                secrets["webhook_secret_key"],
                secrets["webhook_secret_key_id"],
                stripe_secret,
                secrets["webhook_secret_key"],
                secrets["webhook_secret_key_id"],
                paypal_secret,
                secrets["webhook_secret_key"],
                secrets["webhook_secret_key_id"],
                woo_secret,
                secrets["webhook_secret_key"],
                secrets["webhook_secret_key_id"],
            ),
        )
    finally:
        conn.close()
    return {
        "tenant_id": tenant_id,
        "tenant_key": tenant_key,
        "stripe_secret": stripe_secret,
        "shopify_secret": shopify_secret,
        "paypal_secret": paypal_secret,
        "woocommerce_secret": woo_secret,
    }


def _sign_stripe(body: bytes, secret: str) -> str:
    ts = int(time.time())
    sig = hmac.new(
        secret.encode(), f"{ts}.".encode() + body, hashlib.sha256
    ).hexdigest()
    return f"t={ts},v1={sig}"


def _post_stripe_once(
    tenant_key: str, stripe_secret: str, intent_id: str, amount: int
) -> tuple[int, str]:
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


def _post_shopify_once(
    tenant_key: str,
    shopify_secret: str,
    order_id: int,
    total: str,
    created_iso: str | None = None,
) -> tuple[int, str, bytes]:
    """XVI provider parity: real HMAC-signed shopify order through the API.

    Returns (http_status, body_text, exact_sent_bytes) so the proof can
    compare persisted meaning against the independent oracle on the
    identical bytes the provider signed.
    """
    import base64 as _b64

    body = json.dumps(
        {
            "id": order_id,
            "total_price": total,
            "currency": "USD",
            "created_at": created_iso or datetime.now(timezone.utc).isoformat(),
        },
        separators=(",", ":"),
    ).encode()
    sig = _b64.b64encode(
        hmac.new(shopify_secret.encode(), body, hashlib.sha256).digest()
    ).decode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{_TOPO.api_port}/api/webhooks/shopify/order_create",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Skeldir-Tenant-Key": tenant_key,
            "X-Shopify-Hmac-Sha256": sig,
            "X-Shopify-Topic": "orders/create",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode(), body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(), body
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"webhook_post_failed:{type(exc).__name__}:{exc}"[:300])


def _post_woocommerce_once(
    tenant_key: str,
    woo_secret: str,
    order_id: int,
    total: str,
    completed_iso: str | None = None,
) -> tuple[int, str, bytes]:
    """XVI provider parity: real HMAC-signed woocommerce order via the API."""
    import base64 as _b64

    body = json.dumps(
        {
            "id": order_id,
            "total": total,
            "currency": "USD",
            "date_completed": completed_iso or datetime.now(timezone.utc).isoformat(),
        },
        separators=(",", ":"),
    ).encode()
    sig = _b64.b64encode(
        hmac.new(woo_secret.encode(), body, hashlib.sha256).digest()
    ).decode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{_TOPO.api_port}/api/webhooks/woocommerce/order_completed",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Skeldir-Tenant-Key": tenant_key,
            "X-WC-Webhook-Signature": sig,
            "X-WC-Webhook-Topic": "order.completed",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode(), body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(), body
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"webhook_post_failed:{type(exc).__name__}:{exc}"[:300])


_PAYPAL_TEST_STATE: dict = {}


def _paypal_test_credentials() -> dict:
    """Generate one RSA key + self-signed cert for the PayPal test override.

    The API container receives TESTING=1 plus the cert URL/PEM (wired in
    main before the paypal journey); transmissions are RSA-SHA256 signed
    with this key over the provider-canonical message.
    """
    if _PAYPAL_TEST_STATE:
        return _PAYPAL_TEST_STATE
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "paypal-test")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now.replace(year=now.year + 5))
        .sign(key, hashes.SHA256())
    )
    _PAYPAL_TEST_STATE["private_pem"] = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    _PAYPAL_TEST_STATE["cert_pem"] = cert.public_bytes(
        serialization.Encoding.PEM
    ).decode()
    _PAYPAL_TEST_STATE["key"] = key
    return _PAYPAL_TEST_STATE


def _post_paypal_once(
    tenant_key: str,
    webhook_id: str,
    txn_id: str,
    total: str,
    create_iso: str | None = None,
) -> tuple[int, str, bytes]:
    """XVI provider parity: real RSA-signed paypal sale through the API."""
    import base64 as _b64
    import zlib

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    creds = _paypal_test_credentials()
    body = json.dumps(
        {
            "id": txn_id,
            "amount": {"total": total, "currency": "USD"},
            "create_time": create_iso or datetime.now(timezone.utc).isoformat(),
        },
        separators=(",", ":"),
    ).encode()
    transmission_id = f"test-{uuid.uuid4().hex[:12]}"
    transmission_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    crc = zlib.crc32(body) & 0xFFFFFFFF
    canonical = (
        f"{transmission_id}|{transmission_time}|{webhook_id}|{crc}"
    ).encode()
    signature = creds["key"].sign(canonical, padding.PKCS1v15(), hashes.SHA256())
    # The API rebuilds the verification envelope server-side from the
    # individual transmission headers; the Sig header carries only the
    # base64 signature (never a prebuilt envelope).
    req = urllib.request.Request(
        f"http://127.0.0.1:{_TOPO.api_port}/api/webhooks/paypal/sale_completed",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Skeldir-Tenant-Key": tenant_key,
            "PayPal-Transmission-Sig": _b64.b64encode(signature).decode(),
            "PayPal-Transmission-Id": transmission_id,
            "PayPal-Transmission-Time": transmission_time,
            "PayPal-Webhook-Id": webhook_id,
            "PayPal-Auth-Algo": "SHA256withRSA",
            "PayPal-Cert-Url": _PAYPAL_CERT_URL,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode(), body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(), body
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"webhook_post_failed:{type(exc).__name__}:{exc}"[:300])


def _post_root_direct(
    tenant_key: str,
    provider: str,
    raw_body: bytes,
    signature_header: str,
    event_reference: str,
    commerce: dict,
    event_id: str,
) -> tuple[int, str]:
    """XVI hostile journey: valid provider signature, MUTATED handoff.

    Calls the real auth-root process directly with bytes the provider
    genuinely signed but commerce fields the relay did not derive from
    them. The root must refuse (binding law) with zero persistence.
    """
    import base64 as _b64

    payload = {
        "api_key": tenant_key,
        "provider": provider,
        "provider_event_reference": event_reference,
        "raw_body_b64": _b64.b64encode(raw_body).decode(),
        "signature_header": signature_header,
        "event_id": event_id,
        "auth_version": "v1",
        **commerce,
    }
    req = urllib.request.Request(
        f"http://127.0.0.1:{_TOPO.args.auth_port}/v1/authenticate-ingress",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"root_post_failed:{type(exc).__name__}:{exc}"[:300])


def _post_stripe(
    tenant_key: str, stripe_secret: str, intent_id: str, amount: int
) -> tuple[int, str]:
    """POST a provider webhook with one bounded stimulus retry.

    Centralizes the Corrective XVII pattern previously inlined at
    individual outage posts: under CI load the acceptance POST has
    stalled client-side with the API alive at every stimulus site
    (normal journey, recovery outage, F-a, F-b, F-c, F-v across
    heads, on identical runtime bytes). One idempotent retry on the
    same intent (the server dedupes by idempotency key) after a
    liveness probe distinguishes a transient stall (second attempt
    200) from a systematic hang (deterministic failure: dead API
    fails fast with context, live-but-hung API fails the retry).
    Non-timeout transport errors propagate immediately; HTTP error
    statuses are returned, never retried. Every stage assertion is
    unchanged.
    """
    try:
        return _post_stripe_once(tenant_key, stripe_secret, intent_id, amount)
    except RuntimeError as exc:
        if "TimeoutError" not in str(exc) and "timed out" not in str(exc):
            raise
        try:
            _wait_http_ok(f"http://127.0.0.1:{_TOPO.api_port}/health/live", 15)
        except Exception as live_exc:  # noqa: BLE001 - context carrier
            raise RuntimeError(
                f"stimulus_api_not_live:{type(live_exc).__name__}"
            ) from live_exc
        print(
            f"B26_P2_TOPOLOGY_POST_RETRIED intent={intent_id} "
            f"first={str(exc)[:120]}",
            flush=True,
        )
        return _post_stripe_once(tenant_key, stripe_secret, intent_id, amount)


def _broker_outage(block: bool) -> None:
    """Simulate a true broker outage across every publisher principal.

    Corrective V: the API (app_user), the relay (app_relay), the
    scheduler (app_beat), and the worker (app_worker) all hold broker
    transport authority. Revoking from the API alone no longer stops
    publication (the relay lawfully recovers through its own
    credential) -- a faithful outage must fence every publisher.
    """
    for role in ("app_user", "app_relay", "app_beat", "app_worker"):
        if block:
            _query(f"REVOKE INSERT ON TABLE public.kombu_message FROM {role}")
        else:
            _query(f"GRANT INSERT ON TABLE public.kombu_message TO {role}")


def _ingress_by_key(tenant_id: str, idem: str) -> list[tuple]:
    return _query(
        "SELECT id::text, provider, provider_native_event_reference,"
        " provider_native_commerce_reference,"
        " normalized_commerce_reference_kind,"
        " normalized_commerce_reference_value, verified_amount_minor,"
        " verified_amount_currency, verified_amount_scale,"
        " extract(epoch from event_timestamp)::bigint,"
        " verified_commerce_ingress_state, b26_p2_provenance_status,"
        " (SELECT count(*) FROM public.b26_p2_provider_auth_consequence c"
        " WHERE c.webhook_ingress_identity_id = i.id),"
        " (SELECT count(*) FROM public.b26_p2_auth_root_evidence r"
        " WHERE r.webhook_ingress_identity_id = i.id),"
        " (SELECT count(*) FROM public.b26_p2_ingress_auth_witness w"
        " WHERE w.webhook_ingress_identity_id = i.id)"
        " FROM public.webhook_ingress_identities i"
        " WHERE i.tenant_id = %s AND i.idempotency_key = %s",
        (tenant_id, idem),
    )


def _xvi_oracle_expected(provider: str, raw: bytes) -> dict:
    """Independent provider-native expectation (stdlib only, no app import)."""
    import importlib.util as _ilu

    path = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xvi_semantic_oracle.py"
    spec = _ilu.spec_from_file_location("xvi_topo_oracle", path)
    assert spec is not None and spec.loader is not None
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ORACLES[provider](raw)


def _assert_oracle_correspondence(
    provider: str, raw: bytes, row: tuple
) -> dict:
    """Persisted meaning must equal the independent oracle's meaning."""
    expected = _xvi_oracle_expected(provider, raw)
    observed = {
        "provider": row[1],
        "provider_native_event_reference": row[2],
        "provider_native_commerce_reference": row[3],
        "normalized_commerce_reference_kind": row[4],
        "normalized_commerce_reference_value": row[5],
        "verified_amount_minor": int(row[6]),
        "verified_amount_currency": row[7],
        "verified_amount_scale": int(row[8]),
        "event_timestamp_epoch": int(row[9]),
    }
    if observed != expected:
        raise RuntimeError(f"oracle_divergence:{provider}:{observed}:{expected}")
    return observed


def _wait_auth_ok(timeout_s: int = 120) -> None:
    deadline = time.time() + timeout_s
    url = f"http://127.0.0.1:{_TOPO.args.auth_port}/health/live"
    last = "unstarted"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    return
                last = f"http_{resp.status}"
        except Exception as exc:  # noqa: BLE001
            last = type(exc).__name__
        time.sleep(2)
    raise RuntimeError(f"auth_root_not_live:{last}")


def _stop_container(name: str) -> None:
    proc = _docker("stop", name)
    if proc.returncode != 0:
        raise RuntimeError(f"container_stop_failed:{name}:{proc.stderr[-300:]}")


def _wait_state(
    table: str, idcol: str, task_id: str, want: str, timeout_s: int
) -> dict:
    col = "delivery_state" if table == "b23_match_task_dispatches" else "state"
    idf = "task_id" if table == "b23_match_task_dispatches" else "dispatch_task_id"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        rows = _query(f"SELECT {col} FROM public.{table} WHERE {idf} = %s", (task_id,))
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
    return {
        "task_id": str(rows[0][0]),
        "delivery_state": str(rows[0][1]),
        "outbox": str(rows[0][2]),
    }


_TOPO: _Topology


def _dead_edge_probe() -> dict:
    """Prove the natural-dispatch kill-switch is honored (dead edge).

    With SKELDIR_B23_P6_DISABLE_NATURAL_DISPATCH set, the production
    webhook edge must persist ingress but issue NO dispatch/outbox/
    directory rows. XVI (H-XVI-R18): the probe stimulus executes INSIDE
    the shipping API container (the deployed artifact), not via a host
    import of workspace source. Tenant/event/ingress seeding remains a
    host SQL fixture (precondition, like the migrated schema -- not a
    production edge and carrying no financial meaning).
    """
    import psycopg2 as _pg

    tenant_id = str(uuid.uuid4())
    conn = _pg.connect(_TOPO.db_admin)
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash,"
            " notification_email) VALUES (%s, %s, %s, %s)",
            (
                tenant_id,
                "b26p2-iv-deadedge",
                uuid.uuid4().hex,
                "deadedge@example.invalid",
            ),
        )
        cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, false)", (tenant_id,)
        )
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
            ' VALUES (%s, %s, %s, %s, %s, 38000, \'{"order_id": "dead"}\'::jsonb,'
            " %s, 'conversion', 'b26p2ca1_channel', 'dead-campaign', 38000, 'USD',"
            " %s, %s, 'processed')",
            (
                event_uuid,
                tenant_id,
                occurred,
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                f"deadedge:{tenant_id[:8]}",
                occurred,
                occurred,
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
                ingress_id,
                tenant_id,
                event_uuid,
                f"evt-dead-{tenant_id[:8]}",
                f"ord-dead-{tenant_id[:8]}",
                f"ord-dead-{tenant_id[:8]}",
                occurred,
                f"deadedge-ingress:{tenant_id[:8]}",
            ),
        )
    finally:
        conn.close()
    # In-artifact stimulus: the kill-switch probe runs as the API
    # container's own process (image bytes + container DATABASE_URL).
    probe_code = (
        "import asyncio, os;"
        "os.environ['SKELDIR_B23_P6_DISABLE_NATURAL_DISPATCH']='1';"
        "from app.api.webhooks import "
        "_dispatch_b23_match_task_from_persisted_ingress as _d;"
        f"asyncio.run(_d(tenant_id={tenant_id!r},event_id={event_uuid!r},"
        f"event_timestamp={(occurred.isoformat())!r},"
        f"correlation_id={str(uuid.uuid4())!r}))"
    )
    proc = _docker("exec", API_CONTAINER, "python", "-c", probe_code)
    if proc.returncode != 0:
        raise RuntimeError(f"dead_edge_probe_failed:{proc.stderr[-500:]}")
    rows = _query(
        "SELECT count(*) FROM public.b23_match_task_dispatches WHERE tenant_id = %s",
        (tenant_id,),
    )
    if int(rows[0][0]) != 0:
        raise RuntimeError("dead_edge_dispatch_not_suppressed")
    return {"dead_edge_sets": True, "dispatch_rows": 0, "in_artifact": True}


def main() -> int:
    global _TOPO
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-out", type=Path, default=None)
    parser.add_argument("--pg-port", default="5544")
    parser.add_argument("--api-port", default="8000")
    parser.add_argument("--auth-port", default="18001")
    parser.add_argument("--pg-password", default="postgres")
    parser.add_argument("--image-tag", default="ci")
    parser.add_argument("--sweep-interval", default="5")
    parser.add_argument("--staleness-seconds", default="25")
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
        if "202609280002" not in heads.stdout:
            return _fail("migration_head_missing_corrective_xvi")
        details["migration_head"] = "202609280002"
        relay_line = next(
            (ln for ln in procfile.splitlines() if ln.startswith("relay_b26_p2:")),
            "",
        )
        if "DATABASE_URL=$B26_P2_RELAY_DATABASE_URL" not in relay_line:
            return _fail("relay_custody_not_split")
        beat_line = next(
            (ln for ln in procfile.splitlines() if ln.startswith("beat:")),
            "",
        )
        if "DATABASE_URL=$B26_P2_BEAT_DATABASE_URL" not in beat_line:
            return _fail("beat_custody_not_split")
        # Corrective XII: the generic worker must never be MOUNTED the
        # dedicated ingress credential. (It keeps the API DSN by C7
        # design; isolation is enforced at the database layer for
        # every non-ingress principal, at startup for smuggled
        # credentials, and at the session boundary for in-process
        # callers. Explicit blanking `VAR=` is non-possession, proven
        # by the XII process-isolation battery.)
        worker_line = next(
            (ln for ln in procfile.splitlines() if ln.startswith("worker:")),
            "",
        )
        # Shell blanking (`VAR=` / `VAR= cmd`) carries no value:
        # only `VAR=<non-space>` mounts the credential.
        _mount = re.search(r"B26_P2_INGRESS_DATABASE_URL=\S", worker_line)
        if _mount is not None:
            return _fail("generic_worker_holds_ingress_dsn")
        if "B26_P2_INGRESS_DATABASE_URL" not in worker_line:
            return _fail("generic_worker_ingress_not_blanked")
        details["procfile_recovery_custody_ok"] = True
        details["procfile_xi_ingress_custody_ok"] = True
        details["procfile_xii_ingress_blanked"] = True

        # 1. Build + boot the exact production topology.
        print("B26_P2_TOPOLOGY_STAGE build", flush=True)
        details["image_tag"] = _TOPO.image
        image_id = _TOPO.build_image()
        details["image_id"] = image_id
        # XVI (H-XVI-R18): bind the proof to the artifact identity.
        details["artifact_identity"] = _TOPO.image_artifact_identity()
        # XVI: the container commands must equal the shipping Procfile
        # commands (modulo cd/env-prefix/reload/concurrency-default).
        # A CMD override that is not the shipping command voids
        # deployment-equivalence credit.
        _PROCFILE_CMDS = {
            "api": ("web:", ["uvicorn", "app.main:app"]),
            "auth_ingress": ("auth_ingress:", ["uvicorn", "app.auth_service.server:app"]),
            "worker_b23": ("worker_b23:", ["celery", "-A", "app.celery_app.celery_app", "worker"]),
            "relay": ("relay_b26_p2:", ["celery", "-A", "app.celery_app.celery_app", "worker"]),
            "beat": ("beat:", ["celery", "-A", "app.celery_app.celery_app", "beat"]),
        }
        _CI_CMDS = {
            "api": API_CMD,
            "auth_ingress": AUTH_CMD,
            "worker_b23": WORKER_CMD,
            "relay": RELAY_CMD,
            "beat": BEAT_CMD,
        }
        for _svc, (_prefix, _ship) in _PROCFILE_CMDS.items():
            _pline = next(
                (ln for ln in procfile.splitlines() if ln.startswith(_prefix)), ""
            )
            for _tok in _ship:
                if _tok not in _pline:
                    return _fail(f"procfile_cmd_drift:{_svc}:{_tok}")
            for _tok in _CI_CMDS[_svc][: len(_ship)]:
                if _tok not in _pline and _tok not in ("--host", "0.0.0.0"):
                    return _fail(f"ci_cmd_not_shipping:{_svc}:{_tok}")
        details["procfile_cmd_parity"] = True
        print("B26_P2_TOPOLOGY_STAGE postgres", flush=True)
        _TOPO.start_postgres()
        print("B26_P2_TOPOLOGY_STAGE provision", flush=True)
        _TOPO.provision()
        print("B26_P2_TOPOLOGY_STAGE boot_services", flush=True)
        _TOPO.start_auth_root()
        _TOPO.start_api()
        _TOPO.start_worker()
        _TOPO.start_relay()
        _TOPO.start_beat()
        _wait_http_ok(f"http://127.0.0.1:{_TOPO.api_port}/health/live", 120)
        details["api_live"] = True
        details["auth_root_live"] = True
        _wait_log(WORKER_CONTAINER, "ready", 180)
        _wait_log(RELAY_CONTAINER, "ready", 180)
        details["workers_ready"] = True
        print("B26_P2_TOPOLOGY_STAGE services_ready", flush=True)
        # Dead-edge falsifier (in-artifact production webhook function):
        # the kill-switch must suppress dispatch issuance entirely.
        print("B26_P2_TOPOLOGY_STAGE dead_edge", flush=True)
        details["dead_edge"] = _dead_edge_probe()

        # 2. Prove the exact shipped commands are PID 1 in each container.
        pid1 = {
            "api": _pid1_cmdline(API_CONTAINER),
            "auth_ingress": _pid1_cmdline(AUTH_CONTAINER),
            "worker_b23": _pid1_cmdline(WORKER_CONTAINER),
            "relay": _pid1_cmdline(RELAY_CONTAINER),
            "beat": _pid1_cmdline(BEAT_CONTAINER),
        }
        details["pid1"] = pid1
        if "uvicorn app.main:app" not in pid1["api"]:
            return _fail("api_command_not_shipped")
        if "uvicorn app.auth_service.server:app" not in pid1["auth_ingress"]:
            return _fail("auth_root_command_not_shipped")
        if "b23_match_engine" not in pid1["worker_b23"]:
            return _fail("worker_command_not_shipped")
        if "b26_p2_relay" not in pid1["relay"]:
            return _fail("relay_command_not_shipped")
        if "beat" not in pid1["beat"]:
            return _fail("scheduler_command_not_shipped")

        # 3. Capture in-process database principals (not role names in config).
        # XIV: the API holds no ingress credential in any form (relay
        # only); the dedicated auth root is the sole file holder.
        api_ingress_env = _container_env(API_CONTAINER, "B26_P2_INGRESS_DATABASE_URL")
        api_ingress_file = _container_env(
            API_CONTAINER, "B26_P2_INGRESS_DATABASE_URL_FILE"
        )
        api_role = _container_env(API_CONTAINER, "SKELDIR_PROCESS_ROLE")
        auth_role = _container_env(AUTH_CONTAINER, "SKELDIR_PROCESS_ROLE")
        auth_file = _container_env(AUTH_CONTAINER, "B26_P2_INGRESS_DATABASE_URL_FILE")
        details["auth_topology"] = {
            "api_role": api_role,
            "api_ingress_env": api_ingress_env,
            "api_ingress_file": api_ingress_file,
            "auth_role": auth_role,
            "auth_file": auth_file,
        }
        if api_role != "api":
            return _fail(f"api_role_not_relay:{api_role}")
        if api_ingress_env.strip() or api_ingress_file.strip():
            return _fail("api_holds_ingress_credential")
        if auth_role != "auth_ingress":
            return _fail(f"auth_root_role:{auth_role}")
        if not auth_file.strip():
            return _fail("auth_root_no_file_credential")
        principals = {
            "api": _container_current_user(API_CONTAINER, "DATABASE_URL"),
            "worker_b23": _container_current_user(
                WORKER_CONTAINER, "B23_WORKER_DATABASE_URL"
            ),
            "worker_b23_database_url": _container_current_user(
                WORKER_CONTAINER, "DATABASE_URL"
            ),
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
        if principals["relay"] != "app_relay|app_relay":
            return _fail(f"relay_principal_not_relay:{principals['relay']}")
        if principals["beat"] != "app_beat|app_beat":
            return _fail(f"beat_principal_not_beat:{principals['beat']}")

        # 4. Normal journey: REAL signed webhook from OUTSIDE the API process.
        print("B26_P2_TOPOLOGY_STAGE normal_journey", flush=True)
        tenant = _seed_tenant()
        intent = f"pi_{uuid.uuid4().hex[:18]}"
        status, body = _post_stripe(
            tenant["tenant_key"], tenant["stripe_secret"], intent, 38000
        )
        if status != 200:
            return _fail(f"signed_webhook_not_accepted:{status}:{body[:300]}")
        try:
            event_id = str(json.loads(body)["event_id"])
        except (ValueError, KeyError) as exc:
            return _fail(f"webhook_response_missing_event_id:{exc}:{body[:200]}")
        details["webhook_accepted"] = {
            "intent": intent,
            "http": status,
            "event_id": event_id,
        }
        disp = _dispatch_for_ingress(tenant["tenant_id"], event_id)
        details["dispatch_issued"] = disp
        _wait_state(
            "b23_match_task_dispatches", "task", disp["task_id"], "conducted", 180
        )
        _wait_state("b26_p2_execution_outbox", "task", disp["task_id"], "conducted", 60)
        details["conducted"] = {"task_id": disp["task_id"]}
        # Corrective V: the conducted twin must carry a task-specific
        # conduction receipt (the gate's persisted consequence) written
        # by the real worker through the production path.
        receipt = _query(
            "SELECT task_id, b23_processed_count, p2_scope_identity"
            " FROM public.b26_p2_conduction_receipts WHERE task_id = %s",
            (disp["task_id"],),
        )
        if not receipt or len(str(receipt[0][2] or "")) != 64:
            return _fail(f"conduction_receipt_missing:{disp['task_id']}")
        details["conduction_receipt"] = {
            "task_id": str(receipt[0][0]),
            "b23_processed_count": int(receipt[0][1]),
        }
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

        # 4b. XVI provider parity: every supported provider completes one
        # production-realistic authenticated journey (real API + real
        # root + real verifier + sovereign derivation + DB transition)
        # with independent-oracle correspondence, plus one hostile
        # semantic mutation (valid signature, mutated handoff direct to
        # the real root) that must be refused with zero persistence.
        print("B26_P2_TOPOLOGY_STAGE provider_parity", flush=True)
        import uuid as _stage_uuid

        parity: dict[str, dict] = {}
        # Whole-second fixtures: the timestamp law is second precision
        # and the column rounds sub-second inputs; whole-second inputs
        # make oracle correspondence bit-exact by contract.
        fixed_ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        parity_cases = [
            {
                "provider": "shopify",
                "send": lambda: _post_shopify_once(
                    tenant["tenant_key"],
                    tenant["shopify_secret"],
                    900001,
                    "42.50",
                    created_iso=fixed_ts,
                ),
                "idem": str(
                    _stage_uuid.uuid5(
                        _stage_uuid.NAMESPACE_URL, "shopify_order_create_900001"
                    )
                ),
            },
            {
                "provider": "woocommerce",
                "send": lambda: _post_woocommerce_once(
                    tenant["tenant_key"],
                    tenant["woocommerce_secret"],
                    900002,
                    "19.99",
                    completed_iso=fixed_ts,
                ),
                "idem": str(
                    _stage_uuid.uuid5(
                        _stage_uuid.NAMESPACE_URL,
                        "woocommerce_order_completed_900002",
                    )
                ),
            },
        ]
        for case in parity_cases:
            status_p, body_p, raw_p = case["send"]()
            if status_p != 200:
                return _fail(
                    f"parity_journey_rejected:{case['provider']}:{status_p}:{body_p[:200]}"
                )
            rows_p = _ingress_by_key(tenant["tenant_id"], case["idem"])
            if len(rows_p) != 1:
                return _fail(f"parity_no_single_lineage:{case['provider']}")
            row_p = rows_p[0]
            if row_p[11] != "authenticated_known" or int(row_p[12]) != 1:
                return _fail(f"parity_not_authenticated:{case['provider']}")
            try:
                _assert_oracle_correspondence(case["provider"], raw_p, row_p)
            except RuntimeError as exc:
                return _fail(str(exc))
            parity[case["provider"]] = {"http": status_p, "key": case["idem"]}
        # PayPal runs with the test-cert override (TESTING=1 only changes
        # the pool class to NullPool against the same database; the
        # override PEM is test-only and never a production secret).
        # The API is restarted into its exact prior configuration after.
        paypal_creds = _paypal_test_credentials()
        paypal_override_env = [
            "TESTING=1",
            f"SKELDIR_PAYPAL_TEST_CERT_URL={_PAYPAL_CERT_URL}",
            f"SKELDIR_PAYPAL_TEST_CERT_PEM={paypal_creds['cert_pem']}",
        ]
        _TOPO.start_api(extra_env=paypal_override_env)
        _wait_http_ok(f"http://127.0.0.1:{_TOPO.api_port}/health/live", 120)
        # The root re-verifies the same signature: it needs the same
        # test-only override (restarted into the exact prior
        # configuration after the journey).
        _TOPO.start_auth_root(extra_env=paypal_override_env)
        _wait_auth_ok(180)
        paypal_txn = f"PAY-{uuid.uuid4().hex[:10]}"
        status_pp, body_pp, raw_pp = _post_paypal_once(
            tenant["tenant_key"],
            tenant["paypal_secret"],
            paypal_txn,
            "50.00",
            create_iso=fixed_ts,
        )
        if status_pp != 200:
            return _fail(f"parity_journey_rejected:paypal:{status_pp}:{body_pp[:200]}")
        paypal_idem = str(
            _stage_uuid.uuid5(
                _stage_uuid.NAMESPACE_URL, f"paypal_sale_completed_{paypal_txn}"
            )
        )
        rows_pp = _ingress_by_key(tenant["tenant_id"], paypal_idem)
        if len(rows_pp) != 1 or rows_pp[0][11] != "authenticated_known":
            return _fail("parity_no_single_lineage:paypal")
        try:
            _assert_oracle_correspondence("paypal", raw_pp, rows_pp[0])
        except RuntimeError as exc:
            return _fail(str(exc))
        parity["paypal"] = {"http": status_pp, "key": paypal_idem}
        _TOPO.start_api()
        _wait_http_ok(f"http://127.0.0.1:{_TOPO.api_port}/health/live", 120)
        _TOPO.start_auth_root()
        _wait_auth_ok(180)
        details["provider_parity_lawful"] = parity

        # 4c. XVI hostile journeys: fixed signed bytes, mutated handoff
        # direct to the real root (amount/currency/reference each).
        print("B26_P2_TOPOLOGY_STAGE hostile_journeys", flush=True)
        hostile_raw = json.dumps(
            {
                "id": "pi_hostile_1",
                "amount": 5000,
                "currency": "usd",
                "created": int(time.time()),
            },
            separators=(",", ":"),
        ).encode()
        hostile_sig = _sign_stripe(hostile_raw, tenant["stripe_secret"])
        hostile_base_commerce = {
            "provider_native_commerce_reference": "pi_hostile_1",
            "normalized_commerce_reference_kind": "stripe_payment_intent_id",
            "normalized_commerce_reference_value": "pi_hostile_1",
            "verified_amount_minor": 5000,
            "verified_amount_currency": "USD",
            "verified_amount_scale": 2,
            "event_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        hostile_mutations = [
            ("amount", {**hostile_base_commerce, "verified_amount_minor": 5001}),
            ("currency", {**hostile_base_commerce, "verified_amount_currency": "EUR"}),
            (
                "reference",
                {
                    **hostile_base_commerce,
                    "provider_native_commerce_reference": "pi_hostile_X",
                    "normalized_commerce_reference_value": "pi_hostile_X",
                },
            ),
        ]
        for dim, commerce in hostile_mutations:
            hs, hb = _post_root_direct(
                tenant["tenant_key"],
                "stripe",
                hostile_raw,
                hostile_sig,
                "pi_hostile_1",
                commerce,
                f"xvi-hostile-{dim}-{uuid.uuid4().hex[:8]}",
            )
            if hs != 400 or "b26_p2_handoff_binding_refused" not in hb:
                return _fail(f"hostile_not_refused:{dim}:{hs}:{hb[:200]}")
            # Zero persistence for the refused lineage.
            leaked = _query(
                "SELECT count(*) FROM public.webhook_ingress_identities"
                " WHERE tenant_id = %s AND provider_native_commerce_reference = %s",
                (tenant["tenant_id"], "pi_hostile_X" if dim == "reference" else "pi_hostile_1"),
            )
            if dim == "reference" and int(leaked[0][0]) != 0:
                return _fail(f"hostile_persisted:{dim}")
        details["hostile_journeys_refused"] = [d for d, _ in hostile_mutations]

        # 4d. XVI currency law: a lawful-signed non-USD event is
        # governed-excluded to durable DLQ (never authenticated, never
        # lost, never a retry storm).
        eur_intent = f"pi_EUR{uuid.uuid4().hex[:12]}"
        eur_body = json.dumps(
            {
                "id": eur_intent,
                "amount": 5000,
                "currency": "eur",
                "created": int(time.time()),
            },
            separators=(",", ":"),
        ).encode()
        eur_req = urllib.request.Request(
            f"http://127.0.0.1:{_TOPO.api_port}/api/webhooks/stripe/payment_intent_succeeded",
            data=eur_body,
            headers={
                "Content-Type": "application/json",
                "X-Skeldir-Tenant-Key": tenant["tenant_key"],
                "Stripe-Signature": _sign_stripe(eur_body, tenant["stripe_secret"]),
            },
        )
        try:
            with urllib.request.urlopen(eur_req, timeout=60) as eur_resp:
                eur_status, eur_text = eur_resp.status, eur_resp.read().decode()
        except urllib.error.HTTPError as exc:
            eur_status, eur_text = exc.code, exc.read().decode()
        if eur_status != 200 or "dlq_routed" not in eur_text:
            return _fail(f"eur_not_governed:{eur_status}:{eur_text[:200]}")
        eur_idem = str(
            _stage_uuid.uuid5(
                _stage_uuid.NAMESPACE_URL,
                f"stripe_payment_intent_succeeded_{eur_intent}",
            )
        )
        eur_rows = _ingress_by_key(tenant["tenant_id"], eur_idem)
        # A pending precursor may exist (committed before the governed
        # refusal); what must never exist is authenticated truth or any
        # evidence for the excluded currency.
        if any(
            r[11] == "authenticated_known" or int(r[12]) != 0 or int(r[13]) != 0
            for r in eur_rows
        ):
            return _fail("eur_authenticated")
        # The governed exclusion token lives in the durable DLQ row (the
        # response carries only the routing disposition).
        eur_dlq = _query(
            "SELECT count(*) FROM public.dead_events WHERE tenant_id = %s"
            " AND error_message LIKE '%%unsupported_currency%%'",
            (tenant["tenant_id"],),
        )
        if int(eur_dlq[0][0]) < 1:
            return _fail("eur_not_dlq_durable")
        details["currency_law"] = {"eur": "dlq_governed"}

        # 5. Recovery journey: broker outage, NO provider retry, natural recovery.
        print("B26_P2_TOPOLOGY_STAGE recovery_journey", flush=True)
        _broker_outage(True)
        intent2 = f"pi_{uuid.uuid4().hex[:18]}"
        # Stimulus retry lives in _post_stripe (central XVII armor).
        status2, body2 = _post_stripe(
            tenant["tenant_key"], tenant["stripe_secret"], intent2, 12000
        )
        if status2 != 200:
            return _fail(f"outage_webhook_not_accepted:{status2}")
        event_id2 = str(json.loads(body2)["event_id"])
        disp2 = _dispatch_for_ingress(tenant["tenant_id"], event_id2)
        if (
            disp2["delivery_state"] != "pending_publish"
            or disp2["outbox"] != "pending_publish"
        ):
            return _fail(f"outage_not_pending:{disp2}")
        details["outage_pending"] = disp2
        # While the broker is down, the scheduler must NOT conjure recovery.
        time.sleep(int(args.sweep_interval) * 2 + 3)
        still = _dispatch_for_ingress(tenant["tenant_id"], event_id2)
        if still["delivery_state"] != "pending_publish":
            return _fail(f"recovery_without_broker:{still}")
        _broker_outage(False)
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
        _wait_state(
            "b23_match_task_dispatches", "task", disp2["task_id"], "conducted", 240
        )
        _wait_state(
            "b26_p2_execution_outbox", "task", disp2["task_id"], "conducted", 60
        )
        details["natural_recovery"] = {"task_id": disp2["task_id"]}
        recovery_scope = _task_result_scope(disp2["task_id"])
        details["natural_recovery_scope_identity"] = recovery_scope.get(
            "scope_identity"
        )
        if len(str(recovery_scope.get("scope_identity") or "")) != 64:
            return _fail("recovery_scope_identity_malformed")

        # 5b. XVI root-outage matrix through the real processes.
        # (a) root down before authentication: no false 2xx, pending
        # precursor, zero evidence/consequence/witness.
        print("B26_P2_TOPOLOGY_STAGE root_outage", flush=True)
        _stop_container(AUTH_CONTAINER)
        outage_intent = f"pi_OUT{uuid.uuid4().hex[:12]}"
        outage_body = json.dumps(
            {
                "id": outage_intent,
                "amount": 7700,
                "currency": "usd",
                "created": int(time.time()),
            },
            separators=(",", ":"),
        ).encode()
        outage_req = urllib.request.Request(
            f"http://127.0.0.1:{_TOPO.api_port}/api/webhooks/stripe/payment_intent_succeeded",
            data=outage_body,
            headers={
                "Content-Type": "application/json",
                "X-Skeldir-Tenant-Key": tenant["tenant_key"],
                "Stripe-Signature": _sign_stripe(outage_body, tenant["stripe_secret"]),
            },
        )
        try:
            with urllib.request.urlopen(outage_req, timeout=60) as outage_resp:
                outage_status = outage_resp.status
        except urllib.error.HTTPError as exc:
            outage_status = exc.code
        if outage_status == 200:
            return _fail(f"root_down_false_success:{outage_status}")
        outage_idem = str(
            _stage_uuid.uuid5(
                _stage_uuid.NAMESPACE_URL,
                f"stripe_payment_intent_succeeded_{outage_intent}",
            )
        )
        outage_rows = _ingress_by_key(tenant["tenant_id"], outage_idem)
        if len(outage_rows) != 1:
            return _fail("root_down_no_pending_precursor")
        if outage_rows[0][11] == "authenticated_known" or int(outage_rows[0][12]) != 0:
            return _fail("root_down_evidence_without_root")
        details["root_outage_down"] = {"http": outage_status, "pending": True}
        # (b) root restored + provider retry of the EXACT bytes:
        # one lineage, authenticated, complete evidence.
        _TOPO.start_auth_root()
        _wait_auth_ok(180)
        replay_req = urllib.request.Request(
            f"http://127.0.0.1:{_TOPO.api_port}/api/webhooks/stripe/payment_intent_succeeded",
            data=outage_body,
            headers={
                "Content-Type": "application/json",
                "X-Skeldir-Tenant-Key": tenant["tenant_key"],
                "Stripe-Signature": _sign_stripe(outage_body, tenant["stripe_secret"]),
            },
        )
        try:
            with urllib.request.urlopen(replay_req, timeout=60) as replay_resp:
                replay_status = replay_resp.status
        except urllib.error.HTTPError as exc:
            replay_status = exc.code
        if replay_status != 200:
            return _fail(f"root_restored_replay_rejected:{replay_status}")
        healed = _ingress_by_key(tenant["tenant_id"], outage_idem)
        if len(healed) != 1 or healed[0][11] != "authenticated_known":
            return _fail("root_restored_not_authenticated")
        if int(healed[0][12]) != 1 or int(healed[0][13]) != 1:
            return _fail("root_restored_evidence_incomplete")
        details["root_outage_healed"] = {"http": replay_status}
        # (c) already-authenticated replay storm: 10 concurrent
        # duplicates converge to the single lineage (no double
        # consequence, no second lineage).
        import threading as _storm_threading

        storm_results: list[int] = []
        storm_errors: list[str] = []

        def _storm_post() -> None:
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{_TOPO.api_port}/api/webhooks/stripe/payment_intent_succeeded",
                    data=outage_body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Skeldir-Tenant-Key": tenant["tenant_key"],
                        "Stripe-Signature": _sign_stripe(
                            outage_body, tenant["stripe_secret"]
                        ),
                    },
                )
                with urllib.request.urlopen(req, timeout=90) as resp:
                    storm_results.append(resp.status)
            except urllib.error.HTTPError as exc:
                storm_results.append(exc.code)
            except Exception as exc:  # noqa: BLE001
                storm_errors.append(type(exc).__name__)

        storm_threads = [_storm_threading.Thread(target=_storm_post) for _ in range(10)]
        for thread in storm_threads:
            thread.start()
        for thread in storm_threads:
            thread.join()
        if storm_errors or any(s != 200 for s in storm_results):
            return _fail(f"replay_storm_failed:{storm_results}:{storm_errors}")
        converged = _ingress_by_key(tenant["tenant_id"], outage_idem)
        if len(converged) != 1 or int(converged[0][12]) != 1:
            return _fail("replay_storm_split_lineage")
        details["replay_storm_converged"] = {"posts": len(storm_results)}

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
        # Stimulus retry lives in _post_stripe (central XVII armor).
        status3, body3 = _post_stripe(
            tenant["tenant_key"], tenant["stripe_secret"], intent3, 5000
        )
        if status3 != 200:
            return _fail(f"falsifier_webhook_not_accepted:{status3}")
        disp3 = _dispatch_for_ingress(
            tenant["tenant_id"], str(json.loads(body3)["event_id"])
        )
        try:
            _wait_state(
                "b23_match_task_dispatches", "task", disp3["task_id"], "conducted", 60
            )
            return _fail("falsifier_worker_miswire_stayed_green")
        except RuntimeError:
            pass
        meta3 = _query(
            "SELECT status FROM public.celery_taskmeta WHERE task_id = %s",
            (disp3["task_id"],),
        )
        dlq3 = _query(
            "SELECT count(*) FROM public.worker_failed_jobs WHERE task_id = %s",
            (disp3["task_id"],),
        )
        # Corrective VI: the producer credential holds no result-backend
        # writes (telemetry is not truth and must not be forgeable by the
        # issuer). A worker miswired onto the producer DSN therefore fails
        # LOUDLY at the result store itself -- the deployed log shows
        # `permission denied for table celery_taskmeta` for the exact
        # task -- while the deterministic path independently refuses
        # conduction (caller/sovereign law) and the twin stays published
        # (it ages into the governed stale signal instead of vanishing).
        # The task must be provably received AND provably unconducted AND
        # provably refused for the causal reason AND provably retained.
        _mis_logs = _docker("logs", "--tail", "800", WORKER_CONTAINER)
        _mis_output = _mis_logs.stdout + _mis_logs.stderr
        _received = disp3["task_id"] in _mis_output
        _causal = (
            "permission denied for table celery_taskmeta" in _mis_output
            or "b26_p2_result_failure_forge_refused" in _mis_output
            or "b26_p2_receipt_caller_refused" in _mis_output
            or "b26_p2_conducted_caller_refused" in _mis_output
        )
        _still_published = _query(
            "SELECT delivery_state FROM public.b23_match_task_dispatches"
            " WHERE task_id = %s",
            (disp3["task_id"],),
        )
        _retained = (
            bool(_still_published) and str(_still_published[0][0]) == "published"
        )
        meta_failed = bool(meta3) and str(meta3[0][0]) == "FAILURE"
        dlq_count = int(dlq3[0][0]) if dlq3 else 0
        if not _received or not _causal or not _retained:
            return _fail(
                f"falsifier_worker_miswire_inconclusive:received={_received}:"
                f"causal={_causal}:retained={_retained}:"
                f"meta={meta3}:dlq={dlq_count}"
            )
        falsifiers["worker_producer_dsn"] = (
            f"RED_as_required:causal_refusal:retained_published:"
            f"meta={meta_failed}:dlq={dlq_count}"
        )
        _TOPO.start_worker()
        _wait_log(WORKER_CONTAINER, "ready", 180)

        # F-b: scheduler removed -> pending never recovers.
        # The beat stop is asserted and the broker drained first: a
        # relay-task row queued just before the stop would otherwise be
        # consumed after the fresh webhook exists and sweep it.
        _assert_stopped(BEAT_CONTAINER)
        _drain_broker_quiescent()
        _broker_outage(True)
        _wait_http_ok(f"http://127.0.0.1:{args.api_port}/health/live", 60)
        intent4 = f"pi_{uuid.uuid4().hex[:18]}"
        # Stimulus retry lives in _post_stripe (central XVII armor).
        status4, body4 = _post_stripe(
            tenant["tenant_key"], tenant["stripe_secret"], intent4, 6000
        )
        if status4 != 200:
            return _fail(f"falsifier_webhook_not_accepted:{status4}")
        disp4 = _dispatch_for_ingress(
            tenant["tenant_id"], str(json.loads(body4)["event_id"])
        )
        _broker_outage(False)
        try:
            _wait_state(
                "b23_match_task_dispatches",
                "task",
                disp4["task_id"],
                "conducted",
                int(args.sweep_interval) * 3 + 15,
            )
            return _fail("falsifier_missing_scheduler_stayed_green")
        except RuntimeError:
            falsifiers["missing_scheduler"] = "RED_as_required"
        _TOPO.start_beat()
        time.sleep(int(args.sweep_interval) + 2)
        _wait_state(
            "b23_match_task_dispatches", "task", disp4["task_id"], "conducted", 240
        )
        falsifiers["scheduler_restored_green"] = "GREEN"

        # F-c: relay absent + sweep to an unconsumed queue stays pending.
        # Both the relay consumer AND the beat scheduler are stopped
        # BEFORE the webhook is accepted: beat would otherwise sweep the
        # fresh pending dispatch onto the correct queue in the gap
        # between acceptance and the stops (or fire during a stop grace
        # while a consumer still drains), and the live B2.3 worker would
        # conduct it -- a phase-alignment race, not a wrong-queue
        # conduction. All prior stages ended terminal, so with both
        # stopped before acceptance there is no in-flight task and no
        # in-flight task and no
        # future sweep; the only publish path is the manual housekeeping
        # sweep, which no consumer ever executes, so the RED below is
        # deterministic rather than phase-luck. Queued-sweep drain (as in
        # F-b) applies: the stops are asserted and the broker drained
        # before acceptance.
        # Corrective VI: beat now schedules TWO tasks per cadence (relay
        # sweep + operational-health evaluator), so pre-stop in-flight
        # rows are likelier. Inert pre-stop rows are purged as test
        # debris here (they predate the fresh webhook and no stopped
        # consumer can execute them); the falsifier's RED is about the
        # FRESH dispatch never recovering via the wrong-queue sweep.
        _assert_stopped(BEAT_CONTAINER)
        _purge_p2_queues()
        _drain_broker_quiescent()
        _broker_outage(True)
        _wait_http_ok(f"http://127.0.0.1:{args.api_port}/health/live", 60)
        intent5 = f"pi_{uuid.uuid4().hex[:18]}"
        # Stimulus retry lives in _post_stripe (central XVII armor;
        # this site was its first application). The assertion below
        # is unchanged.
        status5, body5 = _post_stripe(
            tenant["tenant_key"], tenant["stripe_secret"], intent5, 7000
        )
        if status5 != 200:
            return _fail(f"falsifier_webhook_not_accepted:{status5}")
        disp5 = _dispatch_for_ingress(
            tenant["tenant_id"], str(json.loads(body5)["event_id"])
        )
        _broker_outage(False)
        _assert_stopped(RELAY_CONTAINER)
        _send_relay_sweep(queue="housekeeping")
        try:
            _wait_state(
                "b23_match_task_dispatches",
                "task",
                disp5["task_id"],
                "conducted",
                int(args.sweep_interval) * 2 + 20,
            )
            return _fail("falsifier_wrong_queue_stayed_green")
        except RuntimeError:
            falsifiers["wrong_relay_queue"] = "RED_as_required"
        _TOPO.start_relay()
        _TOPO.start_beat()
        _wait_log(RELAY_CONTAINER, "ready", 180)
        _wait_state(
            "b23_match_task_dispatches", "task", disp5["task_id"], "conducted", 240
        )
        falsifiers["relay_restored_green"] = "GREEN"

        # F-d: split-brain and orphan writes are refused by the database.
        import psycopg2 as _pg

        user_dsn = f"postgresql://app_user:app_user@127.0.0.1:{args.pg_port}/{DB_NAME}"
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
            # Corrective V: cross-product projections of two real
            # executions refuse at the tuple law (outbox) and the
            # write-time coherence law (directory). The free-slot
            # construction isolates the tuple theorem itself: an
            # occupied slot would refuse earlier at the child UNIQUE,
            # which is defense-in-depth rather than the tuple law.
            disp2row = _dispatch_for_ingress(tenant["tenant_id"], event_id2)
            free_task = f"v-proof-lone-{uuid.uuid4().hex[:8]}"
            free_ingress = str(uuid.uuid4())
            free_event = str(uuid.uuid4())
            # A second free ingress with no execution behind it: the
            # cross-product attempt below (lone task + foreign
            # tenant/ingress) names no canonical execution, so only
            # the tuple law can refuse it. (An occupied slot would
            # refuse earlier at the child UNIQUE -- defense-in-depth
            # proven in the DB battery, not the tuple theorem.)
            stray_ingress = str(uuid.uuid4())
            stray_event = str(uuid.uuid4())
            # Corrective VI: the free-slot dispatch must carry the
            # SOVEREIGN canonical window (UTC day of the ingress event
            # clock), not now()/now()+1day -- the sovereign trigger
            # refuses anything else at issuance. One fixed instant feeds
            # both the ingress clock and the canonical derivation, so no
            # midnight-boundary flake can separate them. The sovereign
            # quantizer is composed with (never reimplemented): the same
            # app.core.day_window law the API and worker use.
            from app.core.day_window import (  # noqa: PLC0415
                quantize_utc_day as _proof_quantize_utc_day,
            )

            _proof_now = datetime.now(timezone.utc)
            _proof_ws, _proof_we = _proof_quantize_utc_day(_proof_now)
            # One setup session with the tenant GUC: the attribution
            # INSERT fires the B24 invalidation trigger, which writes
            # dirty rows under FORCE RLS and therefore needs the same
            # tenant visibility every other writer holds (a superuser
            # session without GUC fails closed here by predecessor
            # design, not by P2 law).
            import psycopg2 as _pgs

            setup_conn = _pgs.connect(_TOPO.db_admin)
            try:
                setup_conn.autocommit = True
                setup_cur = setup_conn.cursor()
                setup_cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant["tenant_id"],),
                )
                setup_cur.execute(
                    "INSERT INTO public.attribution_events (id, tenant_id,"
                    " occurred_at, correlation_id, session_id, revenue_cents,"
                    " raw_payload, idempotency_key, event_type, channel,"
                    " campaign_id, conversion_value_cents, currency,"
                    " event_timestamp, processed_at, processing_status)"
                    " VALUES (%s, %s, now(), %s, %s, 9000,"
                    " '{}'::jsonb, %s, 'conversion', 'b26p2ca1_channel',"
                    " 'proof', 9000, 'USD', now(), now(), 'processed')",
                    (
                        free_event,
                        tenant["tenant_id"],
                        str(uuid.uuid4()),
                        str(uuid.uuid4()),
                        f"proof-free:{free_ingress[:8]}",
                    ),
                )
                setup_cur.execute(
                    "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
                    " event_id, provider, provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " normalized_commerce_reference_kind,"
                    " normalized_commerce_reference_value, verified_amount_minor,"
                    " verified_amount_currency, event_timestamp, idempotency_key,"
                    " verified_commerce_ingress_state)"
                    " VALUES (%s, %s, %s, 'stripe', %s, %s, 'order_reference',"
                    " %s, 9000, 'USD', %s, %s, 'authenticity_verified')",
                    (
                        free_ingress,
                        tenant["tenant_id"],
                        free_event,
                        f"e-proof-{free_ingress[:8]}",
                        f"o-proof-{free_ingress[:8]}",
                        f"o-proof-{free_ingress[:8]}",
                        _proof_now,
                        f"proof-free:{free_ingress[:8]}",
                    ),
                )
                # XIII: dispatch requires terminal authentication. Fully
                # authenticate the lawful fixture via the atomic
                # transition (as admin/migration_owner, allowed) before
                # dispatch. The stray row stays pending (non-dispatchable
                # by law) for the crash test.
                setup_cur.execute(
                    "SELECT public.b26_p2_authenticate_ingress_atomic("
                    "%s, 'stripe', %s, %s, %s,"
                    " 'hmac-sha256-timestamped-hex', 'v1')",
                    (
                        free_ingress,
                        f"e-proof-{free_ingress[:8]}",
                        "a" * 64,
                        "b" * 64,
                    ),
                )
                setup_cur.execute(
                    "INSERT INTO public.attribution_events (id, tenant_id,"
                    " occurred_at, correlation_id, session_id, revenue_cents,"
                    " raw_payload, idempotency_key, event_type, channel,"
                    " campaign_id, conversion_value_cents, currency,"
                    " event_timestamp, processed_at, processing_status)"
                    " VALUES (%s, %s, now(), %s, %s, 9000,"
                    " '{}'::jsonb, %s, 'conversion', 'b26p2ca1_channel',"
                    " 'proof', 9000, 'USD', now(), now(), 'processed')",
                    (
                        stray_event,
                        tenant["tenant_id"],
                        str(uuid.uuid4()),
                        str(uuid.uuid4()),
                        f"proof-stray:{stray_ingress[:8]}",
                    ),
                )
                setup_cur.execute(
                    "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
                    " event_id, provider, provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " normalized_commerce_reference_kind,"
                    " normalized_commerce_reference_value, verified_amount_minor,"
                    " verified_amount_currency, event_timestamp, idempotency_key,"
                    " verified_commerce_ingress_state)"
                    " VALUES (%s, %s, %s, 'stripe', %s, %s, 'order_reference',"
                    " %s, 9000, 'USD', %s, %s, 'authenticity_verified')",
                    (
                        stray_ingress,
                        tenant["tenant_id"],
                        stray_event,
                        f"e-proof-{stray_ingress[:8]}",
                        f"o-proof-{stray_ingress[:8]}",
                        f"o-proof-{stray_ingress[:8]}",
                        _proof_now,
                        f"proof-stray:{stray_ingress[:8]}",
                    ),
                )
                # Dispatch-only execution for the lone task: the task leg
                # passes, so only the forged combination can refuse. The
                # window is the sovereign canonical day (Corrective VI);
                # anything else refuses at issuance before the tuple law
                # is even reached.
                setup_cur.execute(
                    "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                    " webhook_ingress_identity_id, task_id, task_name, queue,"
                    " routing_key, correlation_id, provider,"
                    " provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " normalized_commerce_reference_value, status,"
                    " delivery_state, publish_attempts, window_start, window_end)"
                    " VALUES (%s, %s, %s,"
                    " 'app.tasks.revenue_verification.execute_b23_batch_match_engine',"
                    " 'b23_match_engine', 'b23_match_engine.task', %s, 'stripe',"
                    " 'evt', 'ord', 'ord', 'dispatched', 'pending_publish', 0,"
                    " %s, %s)",
                    (
                        tenant["tenant_id"],
                        free_ingress,
                        free_task,
                        str(uuid.uuid4()),
                        _proof_ws,
                        _proof_we,
                    ),
                )
            finally:
                setup_conn.close()
            try:
                cur.execute(
                    "INSERT INTO public.b26_p2_execution_outbox "
                    "(tenant_id, dispatch_task_id, webhook_ingress_identity_id) "
                    "VALUES (%s, %s, %s)",
                    (tenant["tenant_id"], free_task, stray_ingress),
                )
                return _fail("falsifier_cross_product_outbox_allowed")
            except Exception as exc:
                if "fk_b26_p2_outbox_execution_tuple" not in str(exc).split("\n")[0]:
                    return _fail(
                        f"falsifier_cross_product_wrong_layer:{str(exc)[:150]}"
                    )
                falsifiers["cross_product_outbox"] = "RED_as_required"
            try:
                cur.execute(
                    "INSERT INTO public.b26_p2_task_authority_directory "
                    "(task_id, tenant_id, webhook_ingress_identity_id, window_start, window_end) "
                    "SELECT %s, tenant_id, webhook_ingress_identity_id, "
                    "window_start + interval '30 days', window_end + interval '30 days' "
                    "FROM public.b23_match_task_dispatches WHERE task_id = %s",
                    (f"forged-{uuid.uuid4().hex[:8]}", disp2row["task_id"]),
                )
                return _fail("falsifier_forged_window_allowed")
            except Exception as exc:
                if (
                    "b26_p2_directory_no_canonical_execution"
                    not in str(exc).split("\n")[0]
                ):
                    return _fail(
                        f"falsifier_forged_window_wrong_layer:{str(exc)[:150]}"
                    )
                falsifiers["forged_window"] = "RED_as_required"
            # Corrective VI F-vi1: a forged CANONICAL dispatch window (the
            # auditor-proven root hole: wrong UTC day, coherent otherwise)
            # refuses at issuance through the issuer credential itself.
            # The proof mints a fresh sovereign ingress, then attempts a
            # structurally valid but non-sovereign dispatch for it: the
            # database must refuse before any outbox/directory/admission
            # projection can exist.
            import datetime as _vi_dt

            _vi_now = _vi_dt.datetime.now(_vi_dt.timezone.utc)
            _vi_ws, _vi_we = _proof_quantize_utc_day(_vi_now)
            _vi_ingress = str(uuid.uuid4())
            _vi_event = str(uuid.uuid4())
            setup_conn2 = _pgs.connect(_TOPO.db_admin)
            try:
                setup_conn2.autocommit = True
                setup_cur2 = setup_conn2.cursor()
                setup_cur2.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant["tenant_id"],),
                )
                setup_cur2.execute(
                    "INSERT INTO public.attribution_events (id, tenant_id,"
                    " occurred_at, correlation_id, session_id, revenue_cents,"
                    " raw_payload, idempotency_key, event_type, channel,"
                    " campaign_id, conversion_value_cents, currency,"
                    " event_timestamp, processed_at, processing_status)"
                    " VALUES (%s, %s, %s, %s, %s, 9000,"
                    " '{}'::jsonb, %s, 'conversion', 'b26p2ca1_channel',"
                    " 'proof', 9000, 'USD', %s, %s, 'processed')",
                    (
                        _vi_event,
                        tenant["tenant_id"],
                        _vi_now,
                        str(uuid.uuid4()),
                        str(uuid.uuid4()),
                        f"proof-vi:{_vi_ingress[:8]}",
                        _vi_now,
                        _vi_now,
                    ),
                )
                setup_cur2.execute(
                    "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
                    " event_id, provider, provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " normalized_commerce_reference_kind,"
                    " normalized_commerce_reference_value, verified_amount_minor,"
                    " verified_amount_currency, event_timestamp, idempotency_key,"
                    " verified_commerce_ingress_state)"
                    " VALUES (%s, %s, %s, 'stripe', %s, %s, 'order_reference',"
                    " %s, 9000, 'USD', %s, %s, 'authenticity_verified')",
                    (
                        _vi_ingress,
                        tenant["tenant_id"],
                        _vi_event,
                        f"e-proof-vi-{_vi_ingress[:8]}",
                        f"o-proof-vi-{_vi_ingress[:8]}",
                        f"o-proof-vi-{_vi_ingress[:8]}",
                        _vi_now,
                        f"proof-vi:{_vi_ingress[:8]}",
                    ),
                )
            finally:
                setup_conn2.close()
            try:
                cur.execute(
                    "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                    " webhook_ingress_identity_id, task_id, task_name, queue,"
                    " routing_key, correlation_id, provider,"
                    " provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " normalized_commerce_reference_value, window_start, window_end)"
                    " VALUES (%s, %s, %s,"
                    " 'app.tasks.revenue_verification.execute_b23_batch_match_engine',"
                    " 'b23_match_engine', 'b23_match_engine.task', %s, 'stripe',"
                    " %s, %s, %s, %s, %s)",
                    (
                        tenant["tenant_id"],
                        _vi_ingress,
                        f"vi-forged-{uuid.uuid4().hex[:8]}",
                        str(uuid.uuid4()),
                        f"e-proof-vi-{_vi_ingress[:8]}",
                        f"o-proof-vi-{_vi_ingress[:8]}",
                        f"o-proof-vi-{_vi_ingress[:8]}",
                        _vi_ws + _vi_dt.timedelta(days=5),
                        _vi_we + _vi_dt.timedelta(days=5),
                    ),
                )
                return _fail("falsifier_forged_dispatch_allowed")
            except Exception as exc:
                # XIII terminal law fires before the window check for
                # unauthenticated rows (provenance_unknown/witness_missing);
                # either layer proves forged dispatch cannot conduct.
                _msg0 = str(exc).split("\n")[0]
                if (
                    "b26_p2_dispatch_window_not_sovereign" not in _msg0
                    and "b26_p2_dispatch_provenance_unknown" not in _msg0
                    and "b26_p2_dispatch_witness_missing" not in _msg0
                ):
                    return _fail(
                        f"falsifier_forged_dispatch_wrong_layer:{str(exc)[:150]}"
                    )
                falsifiers["forged_canonical_dispatch"] = "RED_as_required"
            # Corrective VI F-vi2: worker-synthesized completion proof is
            # impossible on the deployed plane. Direct receipt INSERT as
            # the worker login refuses by grant; the owner record function
            # refuses a junk scope witness. (Lawful conduction through the
            # same worker credential is proven by both journeys above.)
            import psycopg2 as _pgw2

            _vi_wconn = _pgw2.connect(
                f"postgresql://app_worker:app_worker@127.0.0.1:{args.pg_port}/{DB_NAME}"
            )
            try:
                _vi_wconn.autocommit = True
                _vi_wcur = _vi_wconn.cursor()
                _vi_wcur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant["tenant_id"],),
                )
                _vi_wcur.execute(
                    "SELECT webhook_ingress_identity_id, window_start, window_end"
                    " FROM public.b23_match_task_dispatches WHERE task_id = %s",
                    (disp["task_id"],),
                )
                _vi_tuple = _vi_wcur.fetchone()
                _vi_task_ingress = str(_vi_tuple[0])
                try:
                    _vi_wcur.execute(
                        "INSERT INTO public.b26_p2_conduction_receipts (task_id,"
                        " tenant_id, webhook_ingress_identity_id, window_start,"
                        " window_end, b23_processed_count, p2_scope_identity)"
                        " VALUES (%s, %s, %s, %s, %s, 0, %s)",
                        (
                            disp["task_id"],
                            tenant["tenant_id"],
                            _vi_task_ingress,
                            _vi_tuple[1],
                            _vi_tuple[2],
                            "f" * 64,
                        ),
                    )
                    return _fail("falsifier_worker_receipt_synthesis_allowed")
                except Exception as exc:
                    if (
                        "denied" not in str(exc).lower()
                        and "permission" not in str(exc).lower()
                    ):
                        return _fail(
                            f"falsifier_worker_receipt_wrong_layer:{str(exc)[:150]}"
                        )
                    falsifiers["worker_receipt_synthesis"] = "RED_as_required"
                try:
                    _vi_wcur.execute(
                        "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                        (
                            disp["task_id"],
                            "SYNTHETIC-FORGED-SCOPE",
                            1,
                            "fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99",
                        ),
                    )
                    return _fail("falsifier_junk_scope_receipt_allowed")
                except Exception as exc:
                    if "b26_p2_receipt_scope_not_bound" not in str(exc).split("\n")[0]:
                        return _fail(
                            f"falsifier_junk_scope_wrong_layer:{str(exc)[:150]}"
                        )
                    falsifiers["junk_scope_receipt"] = "RED_as_required"
            finally:
                _vi_wconn.close()
        finally:
            conn.close()

        # F-v1 + F-v2 (one stopped-worker window): false conducted is
        # refused at the database plane even for the worker credential,
        # and published-but-unconsumed work becomes explicitly stale
        # instead of silently healthy. The gate path already conducted
        # both journeys above through the real worker.
        _assert_stopped(WORKER_CONTAINER)
        _drain_broker_quiescent()
        _wait_http_ok(f"http://127.0.0.1:{args.api_port}/health/live", 60)
        intent6 = f"pi_{uuid.uuid4().hex[:18]}"
        status6, body6 = _post_stripe(
            tenant["tenant_key"], tenant["stripe_secret"], intent6, 9000
        )
        if status6 != 200:
            return _fail(f"falsifier_webhook_not_accepted:{status6}")
        disp6 = _dispatch_for_ingress(
            tenant["tenant_id"], str(json.loads(body6)["event_id"])
        )
        _wait_state(
            "b23_match_task_dispatches", "task", disp6["task_id"], "published", 60
        )
        try:
            _wait_state(
                "b23_match_task_dispatches", "task", disp6["task_id"], "conducted", 20
            )
            return _fail("falsifier_stopped_worker_conducted")
        except RuntimeError:
            falsifiers["stopped_worker_no_conduction"] = "RED_as_required"
        import psycopg2 as _pgw

        worker_dsn = (
            f"postgresql://app_worker:app_worker@127.0.0.1:{args.pg_port}/{DB_NAME}"
        )
        wconn = _pgw.connect(worker_dsn)
        try:
            wconn.autocommit = True
            wcur = wconn.cursor()
            wcur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant["tenant_id"],),
            )
            try:
                wcur.execute(
                    "UPDATE public.b23_match_task_dispatches "
                    "SET delivery_state = 'conducted' WHERE task_id = %s",
                    (disp6["task_id"],),
                )
                return _fail("falsifier_false_conducted_allowed")
            except Exception as exc:
                # Corrective X: the conducted effect guard adjudicates
                # every conducted transition at the effect boundary ahead
                # of the legacy gate-presence guard. Either refusal proves
                # caller-authored conducted is dead.
                _head = str(exc).split("\n")[0]
                if (
                    "b26_p2_conducted_requires_gate" not in _head
                    and "b26_p2_conducted_effect_refused" not in _head
                ):
                    return _fail(
                        f"falsifier_false_conducted_wrong_layer:{str(exc)[:150]}"
                    )
                falsifiers["false_conducted"] = "RED_as_required"
            try:
                wcur.execute(
                    "SELECT public.b26_p2_mark_conducted(%s)", (disp6["task_id"],)
                )
                return _fail("falsifier_gate_without_consequence_allowed")
            except Exception as exc:
                if "b26_p2_conducted_no_receipt" not in str(exc).split("\n")[0]:
                    return _fail(f"falsifier_gate_wrong_layer:{str(exc)[:150]}")
                falsifiers["gate_without_consequence"] = "RED_as_required"
        finally:
            wconn.close()
        # F-v2: the published twin ages past the governed threshold
        # with no consumer. Production health must expose it.
        time.sleep(int(args.staleness_seconds) + 10)
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{args.api_port}/health/b26-p2-conduction",
                timeout=30,
            ) as resp:
                health = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            return _fail(f"conduction_health_unavailable:{exc}")
        if health.get("status") != "stale_unconducted":
            return _fail(f"staleness_not_surfaced:{health}")
        if int(health.get("stale_unconducted_count") or 0) < 1:
            return _fail(f"stale_count_empty:{health}")
        details["staleness_signal"] = health
        falsifiers["published_unconsumed_honest"] = "RED_as_required"
        # Corrective VI: the stale signal is CONSUMED by shipping
        # processes, not merely queryable. (a) The beat-scheduled
        # operational-health evaluator must have EXECUTED inside the
        # deployed relay worker. Evidence is the shipping process's own
        # task-lifecycle channel (received/success for the evaluator
        # task) plus the durable task RESULT payloads, which carry the
        # evaluated stale/quarantine counts -- never a manual CI poll of
        # the endpoint. (b) The health payload carries
        # quarantine/action_required fields. (c) A lawful retry-metadata
        # bump must not hide the stale row (immutable anchor). (d) An
        # absurd threshold refuses instead of suppressing.
        _relay_logs = _docker("logs", "--tail", "500", RELAY_CONTAINER)
        _relay_output = _relay_logs.stdout + _relay_logs.stderr
        if (
            "app.tasks.b26_p2_health.evaluate_b26_p2_operational_health"
            not in _relay_output
        ):
            return _fail("falsifier_health_evaluator_not_wired")
        if '"status": "success"' not in _relay_output:
            return _fail("falsifier_health_evaluator_no_success")
        falsifiers["health_evaluator_wired"] = "RED_as_required"
        import pickle as _ev_pickle  # noqa: PLC0415

        _ev_results = _query(
            "SELECT result FROM public.celery_taskmeta"
            " ORDER BY date_done DESC NULLS LAST LIMIT 120"
        )
        _sweep_signal = False
        _eval_signal = False
        for (raw,) in _ev_results:
            blob = bytes(raw) if isinstance(raw, memoryview) else raw
            if not isinstance(blob, bytes):
                continue
            try:
                payload = _ev_pickle.loads(blob)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            # Relay sweep results carry published/failed/divergent plus
            # the VI stale/quarantine observations.
            if "published" in payload and "stale_unconducted" in payload:
                _sweep_signal = True
            # Evaluator results carry tenants_scanned + quarantine_total
            # but never a published count (it publishes nothing): this
            # shape is unique to the beat-scheduled evaluator execution.
            if (
                "published" not in payload
                and payload.get("tenants_scanned")
                and "quarantine_total" in payload
                and "stale_unconducted" in payload
            ):
                _eval_signal = True
        if not _sweep_signal:
            return _fail("falsifier_sweep_signal_not_recorded")
        if not _eval_signal:
            return _fail("falsifier_evaluator_signal_not_recorded")
        falsifiers["operational_signal_recorded"] = "RED_as_required"
        if "quarantine_count" not in health or "action_required" not in health:
            return _fail(f"health_missing_quarantine_fields:{health}")
        falsifiers["health_quarantine_fields"] = "RED_as_required"
        import psycopg2 as _pgs2

        _stale_conn = _pgs2.connect(user_dsn)
        try:
            _stale_conn.autocommit = True
            _stale_cur = _stale_conn.cursor()
            _stale_cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant["tenant_id"],),
            )
            _stale_cur.execute(
                "UPDATE public.b23_match_task_dispatches"
                " SET publish_attempts = publish_attempts + 1,"
                " last_publish_error = 'proof-retry-note'"
                " WHERE task_id = %s",
                (disp6["task_id"],),
            )
            _stale_cur.execute(
                "SELECT count(*) FROM public.b26_p2_stale_unconducted(%s)",
                (int(args.staleness_seconds),),
            )
            if (_stale_cur.fetchone() or [0])[0] < 1:
                return _fail("falsifier_clock_reset_hidden_stale")
            falsifiers["immutable_progress_clock"] = "RED_as_required"
            try:
                _stale_cur.execute(
                    "SELECT count(*) FROM public.b26_p2_stale_unconducted(9999999)"
                )
                _stale_cur.fetchone()
                return _fail("falsifier_absurd_threshold_suppressed")
            except Exception as exc:
                if (
                    "b26_p2_staleness_threshold_out_of_bounds"
                    not in str(exc).split("\n")[0]
                ):
                    return _fail(f"falsifier_threshold_wrong_layer:{str(exc)[:150]}")
                falsifiers["threshold_authority"] = "RED_as_required"
        finally:
            _stale_conn.close()
        _TOPO.start_worker()
        _wait_log(WORKER_CONTAINER, "ready", 180)
        _wait_state(
            "b23_match_task_dispatches", "task", disp6["task_id"], "conducted", 240
        )
        falsifiers["stopped_worker_drain_green"] = "GREEN"

        # F-v3: recovery principals cannot mint execution authority.
        import psycopg2 as _pgr

        relay_dsn = (
            f"postgresql://app_relay:app_relay@127.0.0.1:{args.pg_port}/{DB_NAME}"
        )
        rconn = _pgr.connect(relay_dsn)
        try:
            rconn.autocommit = True
            rcur = rconn.cursor()
            rcur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant["tenant_id"],),
            )
            try:
                rcur.execute(
                    "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                    " webhook_ingress_identity_id, task_id, task_name, queue,"
                    " routing_key, correlation_id, provider,"
                    " provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " normalized_commerce_reference_value)"
                    " SELECT tenant_id, webhook_ingress_identity_id,"
                    " %s, 'app.tasks.revenue_verification.execute_b23_batch_match_engine',"
                    " 'b23_match_engine', 'b23_match_engine.task', %s, provider,"
                    " provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " normalized_commerce_reference_value"
                    " FROM public.b23_match_task_dispatches WHERE task_id = %s",
                    (
                        f"relay-mint-{uuid.uuid4().hex[:8]}",
                        str(uuid.uuid4()),
                        disp["task_id"],
                    ),
                )
                return _fail("falsifier_relay_mint_allowed")
            except Exception as exc:
                if (
                    "denied" not in str(exc).lower()
                    and "permission" not in str(exc).lower()
                ):
                    return _fail(f"falsifier_relay_mint_wrong_layer:{str(exc)[:150]}")
                falsifiers["relay_mint"] = "RED_as_required"
        finally:
            rconn.close()

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
        # Corrective VI capability-derived class falsification (Gate 29):
        # the reachable mutation surface is enumerated mechanically from
        # the LIVE proof database (roles, grants, memberships, default
        # ACLs, DEFINER writers) and every surface must be exercised by
        # required CI (this proof's falsifiers/journeys, the R6/CP6/OD6
        # battery, the M-VI negative controls). A new sibling
        # grant/function/column capable of a prohibited effect appears
        # here automatically and fails coverage until a falsifier covers
        # it -- the proof can never stay GREEN over an untested sibling.
        from scripts.ci.b26_p2_capability_surface import (  # noqa: PLC0415
            build_manifest as _build_manifest,
        )

        # Coverage registry: prefer the newest (XIV) law; fall back
        # through predecessors for older lanes.
        _covered = None
        for _mod, _attr in (
            ("scripts.ci.b26_p2_xiv_coverage", "XIV_COVERED_SURFACES"),
            ("scripts.ci.b26_p2_xiii_coverage", "XIII_COVERED_SURFACES"),
            ("scripts.ci.b26_p2_xii_coverage", "XII_COVERED_SURFACES"),
            ("scripts.ci.b26_p2_xi_coverage", "XI_COVERED_SURFACES"),
            ("scripts.ci.b26_p2_x_coverage", "X_COVERED_SURFACES"),
            ("scripts.ci.b26_p2_ix_coverage", "IX_COVERED_SURFACES"),
            ("scripts.ci.b26_p2_viii_coverage", "VIII_COVERED_SURFACES"),
            ("scripts.ci.b26_p2_vii_coverage", "VII_COVERED_SURFACES"),
            ("scripts.ci.b26_p2_vi_coverage", "VI_COVERED_SURFACES"),
        ):
            try:
                _m = __import__(_mod, fromlist=[_attr])
                _covered = tuple(sorted(getattr(_m, _attr)))
                break
            except ImportError:
                continue
        if _covered is None:
            raise RuntimeError("no_coverage_registry_importable")
        _manifest = _build_manifest(_TOPO.db_admin, _covered)
        details["capability_coverage"] = {
            name: {
                "reachable": len(effect["reachable_surfaces"]),
                "tested": len(effect["tested_surfaces"]),
                "untested": len(effect["untested_reachable_surfaces"]),
            }
            for name, effect in _manifest["effects"].items()
        }
        _untested_all = sorted(
            {
                surface
                for effect in _manifest["effects"].values()
                for surface in effect["untested_reachable_surfaces"]
            }
        )
        if _untested_all:
            return _fail(
                f"falsifier_capability_coverage_open:{len(_untested_all)}:"
                f"{';'.join(_untested_all[:12])}"
            )
        falsifiers["capability_derived_class_coverage"] = "GREEN"
        details["falsifiers"] = falsifiers
    except RuntimeError as exc:
        details["failure"] = str(exc)[:500]
        try:
            details["diagnostics"] = _collect_diagnostics()
        except Exception as diag_exc:  # noqa: BLE001
            details["diagnostics_error"] = str(diag_exc)[:300]
        _write_failure_evidence(args, details)
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
        _write_failure_evidence(args, details)
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
        "SELECT status, result FROM public.celery_taskmeta WHERE task_id = %s",
        (task_id,),
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
        diag["kombu_messages"] = _query("SELECT count(*) FROM public.kombu_message")[0][
            0
        ]
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

    XVI (H-XVI-R18): the stimulus is published by a shipping container
    (image bytes, container broker), not by a host import of workspace
    source. The API container publishes (it holds the same broker
    transport it uses for natural dispatch; publishing is a broker
    write, not task execution) because this stimulus fires while the
    relay and scheduler are intentionally stopped -- the falsifier's
    very premise. The message is structurally valid and broker
    acceptance succeeds; only the routing is wrong, so no consumer ever
    executes it.
    """
    code = (
        "from app.celery_app import celery_app;"
        "import app.tasks.b26_p2_relay;"
        f"r=celery_app.send_task('app.tasks.b26_p2_relay.relay_b26_p2_pending_dispatches',queue={queue!r});"
        "print('SWEEP_SENT '+str(r.id))"
    )
    proc = _docker("exec", API_CONTAINER, "python", "-c", code)
    if proc.returncode != 0 or "SWEEP_SENT" not in proc.stdout:
        raise RuntimeError(f"sweep_send_failed:{proc.stderr[-500:]}")


if __name__ == "__main__":
    raise SystemExit(main())
