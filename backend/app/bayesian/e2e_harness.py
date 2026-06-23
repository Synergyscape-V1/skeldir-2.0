"""Internal B2.4-P12 E2E proof harness helpers.

These helpers are intentionally internal. They support CI/local composition
proofs without creating a public B2.4 route or action authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.bayesian.artifact_repository import persist_artifact_sync
from app.bayesian.confidence_metadata import B24ConfidenceProjection
from app.bayesian.dispatch_authority import (
    BAYESIAN_FIT_EXECUTION_TASK,
    BayesianDispatchClaim,
    BayesianDispatchLease,
    BayesianWorkerClaimAuthority,
    DispatchClaimOutcome,
    bind_dispatch_write_context_sync,
    claim_fit_dispatch_sync,
    complete_dispatch_sync,
    dispatch_payload_hash,
    mark_dispatch_running_sync,
    register_worker_process_authority_sync,
)
from app.bayesian.enums import FitStatus
from app.bayesian.source_snapshot import (
    load_p6_observed_input_from_source_snapshot_sync,
)
from app.bayesian.tenant_context import bind_transaction_local_tenant


P12_CA1_WORKER_TELEMETRY_SCHEMA_VERSION = "b24-p12-ca1-worker-telemetry-v1"
P12_CA1_MEMORY_CEILING_BYTES = 256 * 1024 * 1024
P12_CA1_DIAGNOSTIC_POLICY_VERSION = "b24-p12-ca1-diagnostic-proof-v1"
P12_CA1_INTERVAL_POLICY_VERSION = "b24-p12-ca1-interval-proof-v1"
P12_CA1_TARGET_FILTER_VERSION = "b24-p12-ca1-target-filter-proof-v1"

P12_TERMINAL_FIT_STATUSES = frozenset(
    {
        FitStatus.SUCCEEDED.value,
        FitStatus.FAILED.value,
        FitStatus.TIMEOUT.value,
        FitStatus.WORKER_LOST.value,
        FitStatus.FALLBACK_ONLY.value,
        FitStatus.CANCELLED.value,
    }
)


@dataclass(frozen=True)
class FitTerminalState:
    fit_id: UUID
    tenant_id: UUID
    status: str
    fallback_reason: str | None
    diagnostic_status: str | None
    credible_interval_status: str
    artifact_ref: str | None
    artifact_hash: str | None


@dataclass(frozen=True)
class P12WorkerBoundarySubprocessResult:
    returncode: int
    worker_process_id: int | None
    stdout: str
    stderr: str
    telemetry: dict[str, object]


class P12TerminalStateTimeout(TimeoutError):
    """Raised when a state-driven P12 wait reaches its monotonic deadline."""

    def __init__(
        self, *, fit_id: UUID, last_observed: dict[str, object] | None
    ) -> None:
        super().__init__(
            "B2.4-P12 terminal-state wait timed out; "
            f"fit_id={fit_id}; last_observed={last_observed!r}"
        )
        self.fit_id = fit_id
        self.last_observed = last_observed


def _load_fit_state(conn, *, tenant_id: UUID, fit_id: UUID) -> dict[str, object] | None:
    bind_transaction_local_tenant(conn, tenant_id=tenant_id)
    row = (
        conn.execute(
            text(
                """
                SELECT id,
                       tenant_id,
                       status,
                       fallback_reason,
                       diagnostic_status,
                       credible_interval_status,
                       artifact_ref,
                       artifact_hash
                FROM public.bayesian_model_fits
                WHERE tenant_id = :tenant_id
                  AND id = :fit_id
                """
            ),
            {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row is not None else None


def wait_for_fit_terminal_state_sync(
    *,
    engine: Engine,
    tenant_id: UUID,
    fit_id: UUID,
    deadline_seconds: float,
    poll_interval_seconds: float = 0.05,
) -> FitTerminalState:
    """Poll a named DB terminal state until a monotonic deadline expires."""

    deadline = time.monotonic() + max(0.001, float(deadline_seconds))
    poll_interval = max(0.001, min(float(poll_interval_seconds), 1.0))
    last_observed: dict[str, object] | None = None
    while time.monotonic() < deadline:
        with engine.begin() as conn:
            last_observed = _load_fit_state(conn, tenant_id=tenant_id, fit_id=fit_id)
        if last_observed and str(last_observed["status"]) in P12_TERMINAL_FIT_STATUSES:
            return FitTerminalState(
                fit_id=last_observed["id"],
                tenant_id=last_observed["tenant_id"],
                status=str(last_observed["status"]),
                fallback_reason=last_observed["fallback_reason"],
                diagnostic_status=last_observed["diagnostic_status"],
                credible_interval_status=str(last_observed["credible_interval_status"]),
                artifact_ref=last_observed["artifact_ref"],
                artifact_hash=last_observed["artifact_hash"],
            )
        remaining = deadline - time.monotonic()
        if remaining > 0:
            Event().wait(min(poll_interval, remaining))
    raise P12TerminalStateTimeout(fit_id=fit_id, last_observed=last_observed)


def _peak_rss_bytes() -> int:
    try:
        import resource

        peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if sys.platform == "darwin":
            return peak
        return peak * 1024
    except Exception:
        pass
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class ProcessMemoryCounters(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(ProcessMemoryCounters)
            psapi = ctypes.WinDLL("Psapi.dll")
            kernel32 = ctypes.WinDLL("Kernel32.dll")
            if psapi.GetProcessMemoryInfo(
                kernel32.GetCurrentProcess(),
                ctypes.byref(counters),
                counters.cb,
            ):
                return int(counters.PeakWorkingSetSize)
        except Exception:
            pass
    return 0


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_telemetry(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _load_fit_worker_identity(conn, *, tenant_id: UUID, fit_id: UUID):
    bind_transaction_local_tenant(conn, tenant_id=tenant_id)
    return (
        conn.execute(
            text(
                """
                SELECT id,
                       tenant_id,
                       model_type,
                       model_version,
                       source_window_start,
                       source_window_end,
                       source_snapshot_hash,
                       status
                FROM public.bayesian_model_fits
                WHERE tenant_id = :tenant_id
                  AND id = :fit_id
                """
            ),
            {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
        )
        .mappings()
        .one_or_none()
    )


def _mark_p12_ca1_success(
    conn,
    *,
    lease: BayesianDispatchLease,
    runtime_seconds: int,
    telemetry: dict[str, object],
) -> dict[str, object]:
    bind_transaction_local_tenant(conn, tenant_id=lease.tenant_id)
    bind_dispatch_write_context_sync(conn, lease=lease)
    artifact = persist_artifact_sync(
        conn,
        tenant_id=lease.tenant_id,
        fit_id=lease.fit_id,
        artifact_type="diagnostics",
        payload=telemetry,
        retention_class="audit",
    )
    if artifact.get("rejected") is True:
        raise RuntimeError("p12_ca1_artifact_rejected")
    conn.execute(
        text(
            """
            UPDATE public.bayesian_model_fits
            SET status = 'succeeded',
                fallback_applied = false,
                fallback_reason = NULL,
                credible_interval_status = 'available',
                diagnostic_status = 'passed',
                diagnostic_failure_reason = NULL,
                diagnostic_policy_version = :diagnostic_policy_version,
                diagnostic_target_filter_version = :target_filter_version,
                interval_policy_version = :interval_policy_version,
                diagnostics_computed_at = now(),
                runtime_seconds = :runtime_seconds,
                n_chains = 1,
                n_samples_actual = 400,
                r_hat_max = 1.0,
                ess_min = 500.0,
                divergence_count = 0,
                hdi_lower = 1.0,
                hdi_upper = 2.0,
                interval_shape = '[2]'::jsonb,
                interval_element_count = 2,
                interval_summary_bytes = 32,
                artifact_ref = :artifact_ref,
                artifact_hash = :artifact_hash,
                last_fit_at = now(),
                completed_at = now(),
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND id = :fit_id
              AND status IN ('pending', 'queued', 'running', 'persist_pending')
            """
        ),
        {
            "tenant_id": str(lease.tenant_id),
            "fit_id": str(lease.fit_id),
            "diagnostic_policy_version": P12_CA1_DIAGNOSTIC_POLICY_VERSION,
            "target_filter_version": P12_CA1_TARGET_FILTER_VERSION,
            "interval_policy_version": P12_CA1_INTERVAL_POLICY_VERSION,
            "runtime_seconds": runtime_seconds,
            "artifact_ref": str(artifact["artifact_ref"]),
            "artifact_hash": str(artifact["artifact_hash"]),
        },
    )
    complete_dispatch_sync(conn, lease=lease)
    return artifact


def _p12_worker_boundary_main(args: argparse.Namespace) -> int:
    started = time.monotonic()
    telemetry_path = Path(args.telemetry_path)
    fit_id = UUID(args.fit_id)
    tenant_id = UUID(args.tenant_id)
    dispatch_claim = BayesianDispatchClaim(
        dispatch_id=UUID(args.dispatch_id),
        fit_id=fit_id,
        task_name=BAYESIAN_FIT_EXECUTION_TASK,
        attempt_id=UUID(args.attempt_id),
        payload_hash=args.payload_hash,
        recovery_generation=int(args.recovery_generation),
    )
    worker_authority = BayesianWorkerClaimAuthority(
        generation_id=args.worker_generation_id,
        pid=os.getpid(),
        process_token=args.worker_process_token,
    )
    engine = create_engine(
        args.database_url,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    telemetry: dict[str, object] = {
        "schema_version": P12_CA1_WORKER_TELEMETRY_SCHEMA_VERSION,
        "worker_process_id": os.getpid(),
        "worker_parent_process_id": os.getppid(),
        "worker_generation_id": args.worker_generation_id,
        "worker_process_token_sha256": _sha256_text(args.worker_process_token),
        "tenant_id": str(tenant_id),
        "fit_id": str(fit_id),
        "dispatch_id": args.dispatch_id,
        "attempt_id": args.attempt_id,
        "task_name": BAYESIAN_FIT_EXECUTION_TASK,
        "memory_ceiling_bytes": int(args.memory_ceiling_bytes),
        "claim_outcome": None,
        "compute_started": False,
        "terminal_status": None,
    }
    try:
        with engine.begin() as conn:
            register_worker_process_authority_sync(
                conn,
                generation_id=args.worker_generation_id,
                pid=os.getpid(),
                parent_pid=os.getppid(),
                topology_fingerprint=args.topology_fingerprint,
                process_token=args.worker_process_token,
                ttl_seconds=3600,
            )
            telemetry["worker_db_backend_pid"] = int(
                conn.execute(text("SELECT pg_backend_pid()")).scalar_one()
            )
        engine.dispose()
        if args.preclaim_visibility_negative_control:
            with engine.begin() as conn:
                row = _load_fit_worker_identity(
                    conn, tenant_id=tenant_id, fit_id=fit_id
                )
            if row is None:
                telemetry.update(
                    {
                        "terminal_status": "not_visible",
                        "negative_control": "separate_worker_connection_cannot_observe_uncommitted_fit",
                        "peak_rss_bytes": _peak_rss_bytes(),
                    }
                )
                _write_telemetry(telemetry_path, telemetry)
                return 3

        with engine.begin() as conn:
            claim_result = claim_fit_dispatch_sync(
                conn,
                claim=dispatch_claim,
                worker_authority=worker_authority,
                lease_seconds=300,
            )
        if isinstance(claim_result, DispatchClaimOutcome):
            telemetry.update(
                {
                    "claim_outcome": claim_result.value,
                    "terminal_status": claim_result.value.lower(),
                    "peak_rss_bytes": _peak_rss_bytes(),
                }
            )
            _write_telemetry(telemetry_path, telemetry)
            return 4

        lease = claim_result
        with engine.begin() as conn:
            row = _load_fit_worker_identity(
                conn, tenant_id=lease.tenant_id, fit_id=lease.fit_id
            )
        if row is None:
            telemetry.update(
                {
                    "terminal_status": "claimed_fit_not_visible",
                    "peak_rss_bytes": _peak_rss_bytes(),
                }
            )
            _write_telemetry(telemetry_path, telemetry)
            return 7
        with engine.begin() as conn:
            bind_transaction_local_tenant(conn, tenant_id=lease.tenant_id)
            mark_dispatch_running_sync(conn, lease=lease)
            conn.execute(
                text(
                    """
                    UPDATE public.bayesian_model_fits
                    SET status = 'running',
                        sampling_started_at = COALESCE(sampling_started_at, now()),
                        updated_at = now()
                    WHERE tenant_id = :tenant_id
                      AND id = :fit_id
                      AND status IN ('pending', 'queued', 'running')
                    """
                ),
                {"tenant_id": str(lease.tenant_id), "fit_id": str(lease.fit_id)},
            )

        with engine.connect() as replay_conn:
            replay_conn = replay_conn.execution_options(
                isolation_level="REPEATABLE READ"
            )
            with replay_conn.begin():
                replay_conn.execute(text("SET TRANSACTION READ ONLY"))
                telemetry["worker_replay_db_backend_pid"] = int(
                    replay_conn.execute(text("SELECT pg_backend_pid()")).scalar_one()
                )
                observed = load_p6_observed_input_from_source_snapshot_sync(
                    replay_conn,
                    tenant_id=lease.tenant_id,
                    model_type=str(row["model_type"]),
                    model_version=str(row["model_version"]),
                    source_window_start=row["source_window_start"],
                    source_window_end=row["source_window_end"],
                    source_snapshot_hash=str(row["source_snapshot_hash"]),
                    preflight_lease_id=args.worker_generation_id,
                )

        telemetry.update(
            {
                "claim_outcome": lease.outcome.value,
                "compute_started": True,
                "terminal_status": "succeeded",
                "source_snapshot_hash": observed.source_snapshot_hash,
                "observed_signal_version": observed.observed_signal_version,
                "streamed_chunk_count": observed.streamed_chunk_count,
                "streamed_source_row_count": observed.streamed_source_row_count,
                "source_amount_minor_total": observed.source_amount_minor_total,
                "resource_policy_version": observed.resource_policy_version,
                "representative_scale": {
                    "minimum_streamed_source_row_count": int(
                        args.expected_min_source_rows
                    ),
                    "expected_channel_count": int(args.expected_channel_count),
                    "expected_campaign_or_feature_count": int(
                        args.expected_campaign_count
                    ),
                },
            }
        )
        telemetry["peak_rss_bytes"] = _peak_rss_bytes()
        if int(telemetry["peak_rss_bytes"]) > int(args.memory_ceiling_bytes):
            telemetry["terminal_status"] = "memory_ceiling_exceeded"
            _write_telemetry(telemetry_path, telemetry)
            return 5
        if observed.streamed_source_row_count < int(args.expected_min_source_rows):
            telemetry["terminal_status"] = "representative_source_scale_not_met"
            _write_telemetry(telemetry_path, telemetry)
            return 6

        runtime_seconds = max(0, int(time.monotonic() - started))
        with engine.begin() as conn:
            artifact = _mark_p12_ca1_success(
                conn,
                lease=lease,
                runtime_seconds=runtime_seconds,
                telemetry=telemetry,
            )
        telemetry["artifact_ref"] = str(artifact["artifact_ref"])
        telemetry["artifact_hash"] = str(artifact["artifact_hash"])
        telemetry["runtime_seconds"] = runtime_seconds
        _write_telemetry(telemetry_path, telemetry)
        return 0
    except Exception as exc:
        telemetry.update(
            {
                "terminal_status": "worker_exception",
                "exception_type": type(exc).__name__,
                "exception_message": str(exc)[:500],
                "peak_rss_bytes": _peak_rss_bytes(),
            }
        )
        _write_telemetry(telemetry_path, telemetry)
        return 2
    finally:
        engine.dispose()


def run_p12_worker_boundary_subprocess(
    *,
    database_url: str,
    tenant_id: UUID,
    fit_id: UUID,
    dispatch_id: UUID,
    attempt_id: UUID,
    worker_generation_id: str,
    worker_process_token: str,
    telemetry_path: Path,
    expected_min_source_rows: int,
    expected_channel_count: int,
    expected_campaign_count: int,
    memory_ceiling_bytes: int = P12_CA1_MEMORY_CEILING_BYTES,
    timeout_seconds: float = 20.0,
    preclaim_visibility_negative_control: bool = False,
) -> P12WorkerBoundarySubprocessResult:
    """Run the P12 CA1 worker proof in a separate OS process."""

    backend_dir = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = (
        str(backend_dir)
        if not env.get("PYTHONPATH")
        else str(backend_dir) + os.pathsep + env["PYTHONPATH"]
    )
    command = [
        sys.executable,
        "-m",
        "app.bayesian.e2e_harness",
        "p12-worker-boundary",
        "--database-url",
        database_url,
        "--tenant-id",
        str(tenant_id),
        "--fit-id",
        str(fit_id),
        "--dispatch-id",
        str(dispatch_id),
        "--attempt-id",
        str(attempt_id),
        "--payload-hash",
        dispatch_payload_hash(fit_id=fit_id),
        "--worker-generation-id",
        worker_generation_id,
        "--worker-process-token",
        worker_process_token,
        "--topology-fingerprint",
        hashlib.sha256(worker_generation_id.encode("utf-8")).hexdigest(),
        "--telemetry-path",
        str(telemetry_path),
        "--memory-ceiling-bytes",
        str(memory_ceiling_bytes),
        "--expected-min-source-rows",
        str(expected_min_source_rows),
        "--expected-channel-count",
        str(expected_channel_count),
        "--expected-campaign-count",
        str(expected_campaign_count),
    ]
    if preclaim_visibility_negative_control:
        command.append("--preclaim-visibility-negative-control")
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    deadline = time.monotonic() + max(0.001, float(timeout_seconds))
    while proc.poll() is None and time.monotonic() < deadline:
        Event().wait(min(0.05, max(0.001, deadline - time.monotonic())))
    if proc.poll() is None:
        proc.kill()
    stdout, stderr = proc.communicate(timeout=5)
    telemetry = (
        json.loads(telemetry_path.read_text(encoding="utf-8"))
        if telemetry_path.exists()
        else {}
    )
    return P12WorkerBoundarySubprocessResult(
        returncode=int(proc.returncode or 0),
        worker_process_id=(
            int(telemetry["worker_process_id"])
            if telemetry.get("worker_process_id") is not None
            else None
        ),
        stdout=stdout,
        stderr=stderr,
        telemetry=telemetry,
    )


def canonical_projection_json(projection: B24ConfidenceProjection) -> bytes:
    """Serialize one projection as deterministic, schema-bound JSON bytes."""

    payload = projection.model_dump(mode="json")
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    worker = subparsers.add_parser("p12-worker-boundary")
    worker.add_argument("--database-url", required=True)
    worker.add_argument("--tenant-id", required=True)
    worker.add_argument("--fit-id", required=True)
    worker.add_argument("--dispatch-id", required=True)
    worker.add_argument("--attempt-id", required=True)
    worker.add_argument("--payload-hash", required=True)
    worker.add_argument("--worker-generation-id", required=True)
    worker.add_argument("--worker-process-token", required=True)
    worker.add_argument("--topology-fingerprint", required=True)
    worker.add_argument("--telemetry-path", required=True)
    worker.add_argument("--memory-ceiling-bytes", type=int, required=True)
    worker.add_argument("--expected-min-source-rows", type=int, required=True)
    worker.add_argument("--expected-channel-count", type=int, required=True)
    worker.add_argument("--expected-campaign-count", type=int, required=True)
    worker.add_argument("--preclaim-visibility-negative-control", action="store_true")
    worker.add_argument("--recovery-generation", type=int, default=0)
    args = parser.parse_args()
    if args.command == "p12-worker-boundary":
        return _p12_worker_boundary_main(args)
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
