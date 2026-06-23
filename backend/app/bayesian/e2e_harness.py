"""Internal B2.4-P12 E2E proof harness helpers.

These helpers are intentionally internal. They support CI/local composition
proofs without creating a public B2.4 route or action authority.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from threading import Event
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.bayesian.confidence_metadata import B24ConfidenceProjection
from app.bayesian.enums import FitStatus
from app.bayesian.tenant_context import bind_transaction_local_tenant


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


class P12TerminalStateTimeout(TimeoutError):
    """Raised when a state-driven P12 wait reaches its monotonic deadline."""

    def __init__(self, *, fit_id: UUID, last_observed: dict[str, object] | None) -> None:
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
