"""B2.4-P6 fit execution orchestration.

Parent-side only: this module may use SQLAlchemy and Celery task metadata. The
sampler child remains DB-airgapped and receives only bounded file inputs.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from uuid import UUID
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.bayesian.compiledir_reaper import cleanup_compiledir, create_compiledir_lease
from app.bayesian.enums import FallbackReason, FitStatus
from app.bayesian.result_contract import validate_result_summary
from app.bayesian.rng_policy import RngSeedMaterial, derive_rng_seed
from app.bayesian.sampler_supervisor import (
    build_child_env_for_lease,
    run_supervised_sampler,
    sampler_child_command,
)
from app.bayesian.sampling_policy import DEFAULT_P6_SAMPLING_POLICY
from app.bayesian.source_snapshot import (
    P6SourceAuthorityError,
    P6SourceObservedInput,
    load_p6_observed_input_from_source_snapshot_sync,
)


TERMINAL_OR_POST_SAMPLE_STATUSES = {
    FitStatus.SAMPLED_UNVALIDATED.value,
    FitStatus.DIAGNOSTICS_PENDING.value,
    FitStatus.SUCCEEDED.value,
    FitStatus.FAILED.value,
    FitStatus.TIMEOUT.value,
    FitStatus.WORKER_LOST.value,
    FitStatus.FALLBACK_ONLY.value,
    FitStatus.CANCELLED.value,
}


def _set_tenant_context(conn, tenant_id: UUID) -> None:
    conn.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


def _fit_identity(conn, *, fit_id: UUID) -> UUID | None:
    conn.execute(
        text("SELECT set_config('app.b24_fit_resolution_id', :fit_id, true)"),
        {"fit_id": str(fit_id)},
    )
    rows = (
        conn.execute(
            text(
                """
                SELECT tenant_id
                FROM public.bayesian_model_fits
                WHERE id = :fit_id
                LIMIT 2
                """
            ),
            {"fit_id": str(fit_id)},
        )
        .mappings()
        .all()
    )
    if not rows:
        return None
    if len(rows) > 1:
        raise RuntimeError("duplicate_fit_suppressed")
    return UUID(str(rows[0]["tenant_id"]))


_LoadFitRow = dict[str, object]


def _load_fit_for_execution(
    conn, *, tenant_id: UUID, fit_id: UUID
) -> _LoadFitRow | None:
    _set_tenant_context(conn, tenant_id)
    row = (
        conn.execute(
            text(
                """
                SELECT
                    id,
                    tenant_id,
                    model_type,
                    model_version,
                    source_window_start,
                    source_window_end,
                    source_snapshot_hash,
                    status,
                    max_runtime_seconds,
                    max_samples,
                    max_cores
                FROM public.bayesian_model_fits
                WHERE tenant_id = :tenant_id
                  AND id = :fit_id
                FOR UPDATE
                """
            ),
            {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row is not None else None


def _mark_fit_failure(
    conn,
    *,
    tenant_id: UUID,
    fit_id: UUID,
    status: FitStatus,
    fallback_reason: FallbackReason,
    runtime_seconds: int | None = None,
) -> None:
    _set_tenant_context(conn, tenant_id)
    conn.execute(
        text(
            """
            UPDATE public.bayesian_model_fits
            SET status = :status,
                fallback_applied = true,
                fallback_reason = :fallback_reason,
                credible_interval_status = 'not_available',
                diagnostic_status = 'unavailable',
                diagnostic_failure_reason = 'skipped_non_sampled',
                hdi_lower = NULL,
                hdi_upper = NULL,
                interval_shape = '[]'::jsonb,
                interval_element_count = 0,
                runtime_seconds = COALESCE(:runtime_seconds, runtime_seconds),
                completed_at = now(),
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND id = :fit_id
              AND status IN (
                  'pending',
                  'queued',
                  'running',
                  'persist_pending'
              )
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "fit_id": str(fit_id),
            "status": status.value,
            "fallback_reason": fallback_reason.value,
            "runtime_seconds": runtime_seconds,
        },
    )


def _mark_fit_diagnostic_error(
    conn,
    *,
    tenant_id: UUID,
    fit_id: UUID,
    diagnostic_failure_reason: str,
    runtime_seconds: int | None = None,
) -> None:
    _set_tenant_context(conn, tenant_id)
    conn.execute(
        text(
            """
            UPDATE public.bayesian_model_fits
            SET status = 'failed',
                fallback_applied = true,
                fallback_reason = 'no_convergence',
                credible_interval_status = 'not_available',
                diagnostic_status = 'error',
                diagnostic_failure_reason = :diagnostic_failure_reason,
                hdi_lower = NULL,
                hdi_upper = NULL,
                interval_shape = '[]'::jsonb,
                interval_element_count = 0,
                runtime_seconds = COALESCE(:runtime_seconds, runtime_seconds),
                completed_at = now(),
                diagnostics_computed_at = COALESCE(diagnostics_computed_at, now()),
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND id = :fit_id
              AND status IN (
                  'pending',
                  'queued',
                  'running',
                  'persist_pending'
              )
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "fit_id": str(fit_id),
            "diagnostic_failure_reason": diagnostic_failure_reason,
            "runtime_seconds": runtime_seconds,
        },
    )


def _iso(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


_SamplerInput = dict[str, object]


def _build_sampler_input(
    row: _LoadFitRow,
    *,
    execution_id: str,
    observed_input: P6SourceObservedInput,
) -> _SamplerInput:
    policy = DEFAULT_P6_SAMPLING_POLICY
    policy.validate()
    max_samples = int(row["max_samples"] or 0)
    max_cores = int(row["max_cores"] or 0)
    if max_samples < policy.sample_count or max_cores < policy.cores:
        raise RuntimeError("policy_rejected")
    seed = derive_rng_seed(
        RngSeedMaterial(
            tenant_id=str(row["tenant_id"]),
            fit_id=str(row["id"]),
            source_snapshot_hash=str(row["source_snapshot_hash"]),
            model_type=str(row["model_type"]),
            model_version=str(row["model_version"]),
            source_window_start=_iso(row["source_window_start"]),
            source_window_end=_iso(row["source_window_end"]),
            sampling_policy_version=policy.policy_version,
        )
    )
    return {
        "schema_version": "b24-p6-parent-input-v1",
        "execution_id": execution_id,
        "fit_id": str(row["id"]),
        "tenant_id": str(row["tenant_id"]),
        "model_type": str(row["model_type"]),
        "model_version": str(row["model_version"]),
        "source_snapshot_hash": str(row["source_snapshot_hash"]),
        "source_window_start": _iso(row["source_window_start"]),
        "source_window_end": _iso(row["source_window_end"]),
        "random_seed": seed,
        "max_samples": max_samples,
        "max_cores": max_cores,
        "max_runtime_seconds": int(row["max_runtime_seconds"] or 60),
        "observed_signal": observed_input.observed_signal,
        "observed_signal_source": observed_input.metadata(),
    }


def _write_input_file(path: Path, payload: _SamplerInput) -> None:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if len(encoded) > 64 * 1024:
        raise RuntimeError("transport_rejected")
    with path.open("wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    if os.name != "nt":
        fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _summary_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _stage_markers(path: Path) -> list[str]:
    if not path.exists():
        return []
    stages: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        stage = payload.get("stage")
        if isinstance(stage, str):
            stages.append(stage)
    return stages


def _diagnostic_stage_failure_reason(
    marker_path: Path, *, timed_out: bool
) -> str | None:
    stages = _stage_markers(marker_path)
    if "diagnostics_started" in stages and "diagnostics_completed" not in stages:
        return "diagnostics_timeout" if timed_out else "diagnostics_failed"
    if "intervals_started" in stages and "intervals_completed" not in stages:
        return "diagnostics_timeout" if timed_out else "diagnostics_failed"
    return None


def _persist_result_summary(
    conn,
    *,
    tenant_id: UUID,
    fit_id: UUID,
    source_snapshot_hash: str,
    runtime_seconds: int,
    result_summary: dict[str, object],
    result_hash: str,
) -> None:
    diagnostic_status = result_summary.get("diagnostic_status")
    if diagnostic_status is None:
        conn.execute(
            text(
                """
                UPDATE public.bayesian_model_fits
                SET status = 'sampled_unvalidated',
                    credible_interval_status = 'pending',
                    runtime_seconds = :runtime_seconds,
                    n_chains = :n_chains,
                    n_samples_actual = :n_samples_actual,
                    divergence_count = :divergence_count,
                    artifact_ref = :artifact_ref,
                    artifact_hash = :artifact_hash,
                    last_fit_at = now(),
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND id = :fit_id
                  AND source_snapshot_hash = :source_snapshot_hash
                  AND status IN ('pending', 'queued', 'running', 'persist_pending')
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "fit_id": str(fit_id),
                "source_snapshot_hash": source_snapshot_hash,
                "runtime_seconds": runtime_seconds,
                "n_chains": int(result_summary["n_chains"]),
                "n_samples_actual": int(result_summary["n_samples_actual"]),
                "divergence_count": int(result_summary["divergence_count"]),
                "artifact_ref": f"b24://p6-summary/{fit_id}/{result_hash}",
                "artifact_hash": result_hash,
            },
        )
        return

    credible_interval_status = str(result_summary["credible_interval_status"])
    diagnostic_failure_reason = result_summary.get("diagnostic_failure_reason")
    interval_available = credible_interval_status == "available"
    fallback_reason = None if interval_available else FallbackReason.NO_CONVERGENCE.value
    conn.execute(
        text(
            """
            UPDATE public.bayesian_model_fits
            SET status = 'succeeded',
                fallback_applied = :fallback_applied,
                fallback_reason = :fallback_reason,
                credible_interval_status = :credible_interval_status,
                diagnostic_status = :diagnostic_status,
                diagnostic_failure_reason = :diagnostic_failure_reason,
                diagnostic_policy_version = :diagnostic_policy_version,
                diagnostic_target_filter_version = :diagnostic_target_filter_version,
                interval_policy_version = :interval_policy_version,
                diagnostics_computed_at = now(),
                runtime_seconds = :runtime_seconds,
                n_chains = :n_chains,
                n_samples_actual = :n_samples_actual,
                r_hat_max = :r_hat_max,
                ess_min = :ess_min,
                divergence_count = :divergence_count,
                hdi_lower = :hdi_lower,
                hdi_upper = :hdi_upper,
                interval_shape = CAST(:interval_shape AS jsonb),
                interval_element_count = :interval_element_count,
                interval_summary_bytes = :interval_summary_bytes,
                artifact_ref = :artifact_ref,
                artifact_hash = :artifact_hash,
                last_fit_at = now(),
                completed_at = now(),
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND id = :fit_id
              AND source_snapshot_hash = :source_snapshot_hash
              AND status IN ('pending', 'queued', 'running', 'persist_pending')
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "fit_id": str(fit_id),
            "source_snapshot_hash": source_snapshot_hash,
            "fallback_applied": not interval_available,
            "fallback_reason": fallback_reason,
            "credible_interval_status": credible_interval_status,
            "diagnostic_status": str(diagnostic_status),
            "diagnostic_failure_reason": diagnostic_failure_reason,
            "diagnostic_policy_version": str(result_summary["diagnostic_policy_version"]),
            "diagnostic_target_filter_version": str(
                result_summary["diagnostic_target_filter_version"]
            ),
            "interval_policy_version": str(result_summary["interval_policy_version"]),
            "runtime_seconds": runtime_seconds,
            "n_chains": int(result_summary["n_chains"]),
            "n_samples_actual": int(result_summary["n_samples_actual"]),
            "r_hat_max": result_summary.get("r_hat_max"),
            "ess_min": result_summary.get("ess_min"),
            "divergence_count": int(result_summary["divergence_count"]),
            "hdi_lower": result_summary.get("hdi_lower"),
            "hdi_upper": result_summary.get("hdi_upper"),
            "interval_shape": json.dumps(result_summary.get("interval_shape", [])),
            "interval_element_count": int(result_summary["interval_element_count"]),
            "interval_summary_bytes": int(result_summary["interval_summary_bytes"]),
            "artifact_ref": f"b24://p6-summary/{fit_id}/{result_hash}",
            "artifact_hash": result_hash,
        },
    )


def execute_fit_intent_sync(
    *,
    engine: Engine,
    fit_id: UUID,
    task_id: str,
) -> dict[str, object]:
    started = time.monotonic()
    try:
        with engine.begin() as conn:
            tenant_id = _fit_identity(conn, fit_id=fit_id)
    except RuntimeError as exc:
        if str(exc) == "duplicate_fit_suppressed":
            return {
                "status": "failed",
                "fallback_reason": FallbackReason.DUPLICATE_FIT_SUPPRESSED.value,
                "task_id": task_id,
                "fit_id": str(fit_id),
                "compute_started": False,
            }
        raise
    if tenant_id is None:
        return {
            "status": "not_found",
            "task_id": task_id,
            "fit_id": str(fit_id),
            "compute_started": False,
        }

    lease = create_compiledir_lease(
        execution_id=f"{fit_id}-{task_id}-{uuid4().hex}",
        worker_id=os.getenv("B24_BAYESIAN_WORKER_RUNTIME_ID", "bayesian-worker"),
    )
    ipc_dir = lease.path / "ipc"
    ipc_dir.mkdir(parents=True, exist_ok=False)
    input_path = ipc_dir / "b24_p6_child_input.json"
    output_path = ipc_dir / "b24_p6_child_result.json"
    marker_path = ipc_dir / "b24_p6_stage_markers.jsonl"

    try:
        with engine.begin() as conn:
            row = _load_fit_for_execution(conn, tenant_id=tenant_id, fit_id=fit_id)
            if row is None:
                return {
                    "status": "not_found",
                    "task_id": task_id,
                    "fit_id": str(fit_id),
                    "compute_started": False,
                }
            current_status = str(row["status"])
            if current_status in TERMINAL_OR_POST_SAMPLE_STATUSES:
                return {
                    "status": current_status,
                    "task_id": task_id,
                    "fit_id": str(fit_id),
                    "tenant_id": str(tenant_id),
                    "idempotent_replay": True,
                    "compute_started": False,
                }
        try:
            with engine.connect() as replay_conn:
                replay_conn = replay_conn.execution_options(
                    isolation_level="REPEATABLE READ"
                )
                with replay_conn.begin():
                    replay_conn.execute(text("SET TRANSACTION READ ONLY"))
                    observed_input = load_p6_observed_input_from_source_snapshot_sync(
                        replay_conn,
                        tenant_id=tenant_id,
                        model_type=str(row["model_type"]),
                        model_version=str(row["model_version"]),
                        source_window_start=row["source_window_start"],
                        source_window_end=row["source_window_end"],
                        source_snapshot_hash=str(row["source_snapshot_hash"]),
                        preflight_lease_id=lease.execution_id,
                    )
            sampler_input = _build_sampler_input(
                row,
                execution_id=lease.execution_id,
                observed_input=observed_input,
            )
        except P6SourceAuthorityError as exc:
            with engine.begin() as conn:
                _mark_fit_failure(
                    conn,
                    tenant_id=tenant_id,
                    fit_id=fit_id,
                    status=FitStatus.FAILED,
                    fallback_reason=exc.reason,
                )
            return {
                "status": "failed",
                "fallback_reason": exc.reason.value,
                "task_id": task_id,
                "fit_id": str(fit_id),
                "tenant_id": str(tenant_id),
                "compute_started": False,
            }
        except RuntimeError as exc:
            reason = FallbackReason.POLICY_REJECTED
            if str(exc) == "transport_rejected":
                reason = FallbackReason.TRANSPORT_REJECTED
            with engine.begin() as conn:
                _mark_fit_failure(
                    conn,
                    tenant_id=tenant_id,
                    fit_id=fit_id,
                    status=FitStatus.FAILED,
                    fallback_reason=reason,
                )
            return {
                "status": "failed",
                "fallback_reason": reason.value,
                "task_id": task_id,
                "fit_id": str(fit_id),
                "tenant_id": str(tenant_id),
                "compute_started": False,
            }

        with engine.begin() as conn:
            _set_tenant_context(conn, tenant_id)
            conn.execute(
                text(
                    """
                    UPDATE public.bayesian_model_fits
                    SET status = 'running',
                        sampling_started_at = COALESCE(sampling_started_at, now()),
                        updated_at = now()
                    WHERE tenant_id = :tenant_id
                      AND id = :fit_id
                      AND source_snapshot_hash = :source_snapshot_hash
                      AND status IN ('pending', 'queued', 'running')
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "fit_id": str(fit_id),
                    "source_snapshot_hash": str(sampler_input["source_snapshot_hash"]),
                },
            )

        _write_input_file(input_path, sampler_input)
        source_env = {
            **os.environ,
            "B24_STAGE_MARKER_PATH": str(marker_path),
        }
        deadline = max(1, min(int(sampler_input["max_runtime_seconds"] or 60), 240))
        result = run_supervised_sampler(
            sampler_child_command(
                mode="real-fit",
                input_path=input_path,
                output=output_path,
            ),
            deadline_seconds=deadline,
            env=build_child_env_for_lease(lease, source_env=source_env),
            compiledir_lease=lease,
            cleanup_compiledir_on_exit=False,
        )
        runtime_seconds = int(time.monotonic() - started)

        if result.status == "timeout":
            diagnostic_reason = _diagnostic_stage_failure_reason(
                marker_path, timed_out=True
            )
            with engine.begin() as conn:
                if diagnostic_reason is not None:
                    _mark_fit_diagnostic_error(
                        conn,
                        tenant_id=tenant_id,
                        fit_id=fit_id,
                        diagnostic_failure_reason=diagnostic_reason,
                        runtime_seconds=runtime_seconds,
                    )
                else:
                    _mark_fit_failure(
                        conn,
                        tenant_id=tenant_id,
                        fit_id=fit_id,
                        status=FitStatus.TIMEOUT,
                        fallback_reason=FallbackReason.TIMEOUT,
                        runtime_seconds=runtime_seconds,
                    )
            return {
                "status": "failed" if diagnostic_reason is not None else "timeout",
                "diagnostic_failure_reason": diagnostic_reason,
                "task_id": task_id,
                "fit_id": str(fit_id),
                "tenant_id": str(tenant_id),
                "runtime_seconds": runtime_seconds,
                "stderr_total_bytes": result.stderr.total_bytes,
            }
        if result.returncode != 0 or not output_path.exists():
            diagnostic_reason = _diagnostic_stage_failure_reason(
                marker_path, timed_out=False
            )
            with engine.begin() as conn:
                if diagnostic_reason is not None:
                    _mark_fit_diagnostic_error(
                        conn,
                        tenant_id=tenant_id,
                        fit_id=fit_id,
                        diagnostic_failure_reason=diagnostic_reason,
                        runtime_seconds=runtime_seconds,
                    )
                else:
                    _mark_fit_failure(
                        conn,
                        tenant_id=tenant_id,
                        fit_id=fit_id,
                        status=FitStatus.FAILED,
                        fallback_reason=FallbackReason.WORKER_FAILURE,
                        runtime_seconds=runtime_seconds,
                    )
            return {
                "status": "failed",
                "fallback_reason": (
                    FallbackReason.NO_CONVERGENCE.value
                    if diagnostic_reason is not None
                    else FallbackReason.WORKER_FAILURE.value
                ),
                "diagnostic_failure_reason": diagnostic_reason,
                "task_id": task_id,
                "fit_id": str(fit_id),
                "tenant_id": str(tenant_id),
                "returncode": result.returncode,
                "stderr_retained": result.stderr.retained_text,
                "stderr_total_bytes": result.stderr.total_bytes,
            }

        result_summary = json.loads(output_path.read_text(encoding="utf-8"))
        validate_result_summary(result_summary)
        result_hash = _summary_hash(result_summary)

        with engine.begin() as conn:
            _set_tenant_context(conn, tenant_id)
            _persist_result_summary(
                conn,
                tenant_id=tenant_id,
                fit_id=fit_id,
                source_snapshot_hash=str(sampler_input["source_snapshot_hash"]),
                runtime_seconds=runtime_seconds,
                result_summary=result_summary,
                result_hash=result_hash,
            )

        return {
            "status": (
                "succeeded"
                if result_summary.get("diagnostic_status") is not None
                else "sampled_unvalidated"
            ),
            "diagnostic_status": result_summary.get("diagnostic_status"),
            "credible_interval_status": result_summary.get(
                "credible_interval_status"
            ),
            "diagnostic_failure_reason": result_summary.get(
                "diagnostic_failure_reason"
            ),
            "task_id": task_id,
            "fit_id": str(fit_id),
            "tenant_id": str(tenant_id),
            "compute_started": True,
            "runtime_seconds": runtime_seconds,
            "result_hash": result_hash,
            "stdout_total_bytes": result.stdout.total_bytes,
            "stderr_total_bytes": result.stderr.total_bytes,
        }
    finally:
        if lease.path.exists():
            cleanup_compiledir(lease)
