"""Boot-time physical topology proof for Bayesian worker DB sessions."""

from __future__ import annotations

import time
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.bayesian.db_engine import (
    create_bayesian_worker_engine,
    runtime_sync_database_url,
)
from app.bayesian.tenant_context import current_tenant_guc


class BayesianWorkerBootTopologyProbeError(RuntimeError):
    """Raised when the worker DB session boundary cannot be physically proven."""


@dataclass(frozen=True)
class BayesianWorkerBootTopologyProbeResult:
    """Non-sensitive evidence from the boot-time topology probe."""

    old_pid: int
    new_pid: int
    lock_key: int
    temp_table_name: str
    elapsed_seconds: float
    worker_connection_count: int
    observer_connection_count: int


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


def _wait_for_backend_absence(
    observer_engine, *, pid: int, timeout_seconds: float, backend_label: str
) -> int:
    deadline = time.monotonic() + max(0.1, float(timeout_seconds))
    last_state: dict[str, object] | None = None
    poll_count = 0
    while time.monotonic() < deadline:
        with observer_engine.connect() as observer:
            poll_count += 1
            last_state = _backend_state(observer, pid)
        if last_state is None:
            return poll_count
        time.sleep(0.05)
    raise BayesianWorkerBootTopologyProbeError(
        f"bayesian_worker_boot_topology_{backend_label}_backend_still_visible"
    )


def run_bayesian_worker_boot_topology_probe(
    database_url: str | None = None,
    *,
    timeout_seconds: float = 5.0,
) -> BayesianWorkerBootTopologyProbeResult:
    """Physically prove direct-Postgres NullPool session replacement at worker boot.

    This is production-path authority, not a pytest helper. It uses the same
    worker engine factory as Bayesian tasks, poisons session-level state, closes
    the worker connection, observes the old backend through an independent
    connection, and verifies that a new worker checkout cannot see the poison.
    """

    started = time.monotonic()
    resolved_url = database_url or runtime_sync_database_url()
    worker_engine = create_bayesian_worker_engine(resolved_url)
    observer_engine = create_engine(
        resolved_url,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
        poolclass=NullPool,
    )
    poison_uuid = uuid4()
    poison_tenant_id = str(poison_uuid)
    temp_table_name = f"p9_boot_probe_poison_{poison_uuid.hex[:12]}"
    lock_key = int(poison_uuid.int % 2_147_483_647) or 1
    try:
        with worker_engine.connect() as conn:
            old_pid = int(conn.execute(text("SELECT pg_backend_pid()")).scalar_one())
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": poison_tenant_id},
            )
            conn.execute(text("SET search_path TO pg_catalog"))
            conn.execute(
                text("SELECT pg_advisory_lock(:lock_key)"), {"lock_key": lock_key}
            )
            conn.execute(text(f"CREATE TEMP TABLE {temp_table_name}(value integer)"))
            conn.execute(text(f"INSERT INTO {temp_table_name}(value) VALUES (1)"))
            conn.commit()
            if current_tenant_guc(conn) != poison_tenant_id:
                raise BayesianWorkerBootTopologyProbeError(
                    "bayesian_worker_boot_topology_guc_poison_not_applied"
                )

        old_backend_observer_polls = _wait_for_backend_absence(
            observer_engine,
            pid=old_pid,
            timeout_seconds=timeout_seconds,
            backend_label="old",
        )

        with worker_engine.connect() as conn:
            new_pid = int(conn.execute(text("SELECT pg_backend_pid()")).scalar_one())
            if new_pid == old_pid:
                raise BayesianWorkerBootTopologyProbeError(
                    "bayesian_worker_boot_topology_backend_not_replaced"
                )
            if current_tenant_guc(conn) is not None:
                raise BayesianWorkerBootTopologyProbeError(
                    "bayesian_worker_boot_topology_guc_poison_survived"
                )
            search_path = str(conn.execute(text("SHOW search_path")).scalar_one())
            if search_path == "pg_catalog":
                raise BayesianWorkerBootTopologyProbeError(
                    "bayesian_worker_boot_topology_search_path_poison_survived"
                )
            temp_table = conn.execute(
                text(f"SELECT to_regclass('pg_temp.{temp_table_name}')")
            ).scalar_one_or_none()
            if temp_table is not None:
                raise BayesianWorkerBootTopologyProbeError(
                    "bayesian_worker_boot_topology_temp_object_survived"
                )
            lock_acquired = bool(
                conn.execute(
                    text("SELECT pg_try_advisory_lock(:lock_key)"),
                    {"lock_key": lock_key},
                ).scalar_one()
            )
            if not lock_acquired:
                raise BayesianWorkerBootTopologyProbeError(
                    "bayesian_worker_boot_topology_advisory_lock_survived"
                )
            conn.execute(
                text("SELECT pg_advisory_unlock(:lock_key)"),
                {"lock_key": lock_key},
            )

        new_backend_observer_polls = _wait_for_backend_absence(
            observer_engine,
            pid=new_pid,
            timeout_seconds=timeout_seconds,
            backend_label="new",
        )

        return BayesianWorkerBootTopologyProbeResult(
            old_pid=old_pid,
            new_pid=new_pid,
            lock_key=lock_key,
            temp_table_name=temp_table_name,
            elapsed_seconds=time.monotonic() - started,
            worker_connection_count=2,
            observer_connection_count=(
                old_backend_observer_polls + new_backend_observer_polls
            ),
        )
    finally:
        worker_engine.dispose()
        observer_engine.dispose()
