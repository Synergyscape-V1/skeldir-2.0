"""B2.4-P9 database authority for Bayesian fit dispatch execution."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import text


BAYESIAN_FIT_EXECUTION_TASK = "app.tasks.bayesian.execute_fit_intent"


class DispatchClaimOutcome(StrEnum):
    ACQUIRED = "ACQUIRED"
    RECLAIMED = "RECLAIMED"
    ACTIVE_LEASE = "ACTIVE_LEASE"
    ALREADY_COMPLETED = "ALREADY_COMPLETED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"
    TERMINAL_FAILURE = "TERMINAL_FAILURE"
    UNAUTHORIZED = "UNAUTHORIZED"
    RETRYABLE_INFRASTRUCTURE_FAILURE = "RETRYABLE_INFRASTRUCTURE_FAILURE"


TERMINAL_OR_NON_EXECUTING_CLAIM_OUTCOMES = {
    DispatchClaimOutcome.ACTIVE_LEASE,
    DispatchClaimOutcome.ALREADY_COMPLETED,
    DispatchClaimOutcome.CANCELLED,
    DispatchClaimOutcome.EXPIRED,
    DispatchClaimOutcome.SUPERSEDED,
    DispatchClaimOutcome.TERMINAL_FAILURE,
    DispatchClaimOutcome.UNAUTHORIZED,
    DispatchClaimOutcome.RETRYABLE_INFRASTRUCTURE_FAILURE,
}


@dataclass(frozen=True)
class BayesianDispatchClaim:
    """Secret-free broker wake-up payload; execution authority lives in Postgres."""

    dispatch_id: UUID
    fit_id: UUID
    task_name: str
    attempt_id: UUID
    payload_hash: str
    recovery_generation: int = 0


@dataclass(frozen=True)
class BayesianWorkerClaimAuthority:
    """Process-local worker authority derived from the boot-proven generation."""

    generation_id: str
    pid: int
    process_token: str


@dataclass(frozen=True)
class BayesianDispatchLease:
    """Fresh transaction-local DB lease returned by the pre-tenant claim."""

    outcome: DispatchClaimOutcome
    tenant_id: UUID
    fit_id: UUID
    dispatch_id: UUID
    attempt_id: UUID
    claim_epoch: int
    lease_capability: str
    lease_expires_at: datetime


def dispatch_payload_hash(
    *, fit_id: UUID, task_name: str = BAYESIAN_FIT_EXECUTION_TASK
) -> str:
    """Return the stable payload hash stored beside the dispatch capability."""

    return hashlib.sha256(f"{task_name}:{fit_id}".encode("utf-8")).hexdigest()


def claim_fit_dispatch_sync(
    conn,
    *,
    claim: BayesianDispatchClaim,
    worker_authority: BayesianWorkerClaimAuthority,
    lease_seconds: int = 900,
) -> BayesianDispatchLease | DispatchClaimOutcome:
    """
    Claim a fit dispatch before tenant context exists.

    This intentionally routes through a SECURITY DEFINER function so table RLS
    remains default-deny before the database validates the opaque capability.
    """

    row = (
        conn.execute(
            text(
                """
                SELECT *
                FROM public.b24_claim_fit_dispatch(
                    :dispatch_id,
                    :fit_id,
                    :task_name,
                    :attempt_id,
                    :payload_hash,
                    :worker_generation_id,
                    :worker_pid,
                    :worker_process_token,
                    :recovery_generation,
                    :lease_seconds
                )
                """
            ),
            {
                "dispatch_id": str(claim.dispatch_id),
                "fit_id": str(claim.fit_id),
                "task_name": claim.task_name,
                "attempt_id": str(claim.attempt_id),
                "payload_hash": claim.payload_hash,
                "worker_generation_id": worker_authority.generation_id,
                "worker_pid": int(worker_authority.pid),
                "worker_process_token": worker_authority.process_token,
                "recovery_generation": int(claim.recovery_generation),
                "lease_seconds": max(1, int(lease_seconds)),
            },
        )
        .mappings()
        .one()
    )
    outcome = DispatchClaimOutcome(str(row["outcome"]))
    if outcome in (
        DispatchClaimOutcome.ACQUIRED,
        DispatchClaimOutcome.RECLAIMED,
    ):
        return BayesianDispatchLease(
            outcome=outcome,
            tenant_id=UUID(str(row["tenant_id"])),
            fit_id=UUID(str(row["fit_id"])),
            dispatch_id=UUID(str(row["dispatch_id"])),
            attempt_id=UUID(str(row["attempt_id"])),
            claim_epoch=int(row["claim_epoch"]),
            lease_capability=str(row["lease_capability"]),
            lease_expires_at=row["lease_expires_at"],
        )
    return outcome


def bind_dispatch_write_context_sync(conn, *, lease: BayesianDispatchLease) -> None:
    """Bind the fresh DB lease as transaction-local write authority."""

    conn.execute(
        text(
            """
            SELECT
                set_config('app.b24_dispatch_id', :dispatch_id, true),
                set_config('app.b24_attempt_id', :attempt_id, true),
                set_config('app.b24_claim_epoch', :claim_epoch, true),
                set_config('app.b24_lease_capability', :lease_capability, true)
            """
        ),
        {
            "dispatch_id": str(lease.dispatch_id),
            "attempt_id": str(lease.attempt_id),
            "claim_epoch": str(lease.claim_epoch),
            "lease_capability": lease.lease_capability,
        },
    )


def mark_dispatch_running_sync(conn, *, lease: BayesianDispatchLease) -> None:
    bind_dispatch_write_context_sync(conn, lease=lease)
    conn.execute(text("SELECT public.b24_mark_fit_dispatch_running()"))


def complete_dispatch_sync(conn, *, lease: BayesianDispatchLease) -> None:
    bind_dispatch_write_context_sync(conn, lease=lease)
    conn.execute(text("SELECT public.b24_complete_fit_dispatch()"))


def fail_dispatch_terminal_sync(
    conn, *, lease: BayesianDispatchLease, reason: str
) -> None:
    bind_dispatch_write_context_sync(conn, lease=lease)
    conn.execute(
        text("SELECT public.b24_fail_fit_dispatch_terminal(:reason)"),
        {"reason": reason[:256]},
    )


def create_recovery_wakeups_sync(conn, *, batch_size: int = 25) -> int:
    return int(
        conn.execute(
            text("SELECT public.b24_create_fit_recovery_wakeups(:batch_size)"),
            {"batch_size": max(1, int(batch_size))},
        ).scalar_one()
    )


def register_worker_process_authority_sync(
    conn,
    *,
    generation_id: str,
    pid: int,
    parent_pid: int,
    topology_fingerprint: str,
    process_token: str,
    ttl_seconds: int = 3600,
) -> None:
    """Register a boot-proven worker process token digest for DB claim checks."""

    conn.execute(
        text(
            """
            SELECT public.b24_register_worker_process_authority(
                :generation_id,
                :pid,
                :parent_pid,
                :topology_fingerprint,
                :process_token,
                :ttl_seconds
            )
            """
        ),
        {
            "generation_id": generation_id,
            "pid": int(pid),
            "parent_pid": int(parent_pid),
            "topology_fingerprint": topology_fingerprint,
            "process_token": process_token,
            "ttl_seconds": max(30, int(ttl_seconds)),
        },
    )
