"""Fail-closed tenant-context enforcement for authenticated Trust API callers."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.trust.audit import (
    AuditSessionFactory,
    TrustAuditRequest,
    record_trust_audit_event,
)
from app.trust.machine_auth import MachineCallerContext
from app.trust.reason_codes import ReasonCode
from app.trust.refusal import tagged_sha256, tenant_hash


logger = logging.getLogger(__name__)
TENANT_CONTEXT_FAILURE_STAGE = "post_auth_transaction_rls_assertion"
TENANT_CONTEXT_EXTERNAL_REASON = "tenant_context_unavailable"
TENANT_AUDIT_ACQUIRE_TIMEOUT_SECONDS = 0.250
TENANT_AUDIT_OPERATION_TIMEOUT_SECONDS = 0.750
TENANT_HANDLER_TIMEOUT_SECONDS = 1.500
TENANT_EMERGENCY_SIGNAL_TIMEOUT_SECONDS = 0.250
TENANT_FAILURE_MAX_IN_FLIGHT = 16
TENANT_EMERGENCY_BUFFER_SIZE = 256
_TENANT_FAILURE_SLOTS = asyncio.Semaphore(TENANT_FAILURE_MAX_IN_FLIGHT)
_EMERGENCY_LOG_SLOTS = asyncio.Semaphore(8)
TENANT_EMERGENCY_SIGNALS: deque[dict[str, str]] = deque(
    maxlen=TENANT_EMERGENCY_BUFFER_SIZE
)


class TenantContextMissingException(RuntimeError):
    """Authenticated request whose transaction-local RLS identity is unsafe."""

    def __init__(
        self,
        *,
        tenant_id: UUID,
        agent_client_id: UUID,
        correlation_identity: str,
        route_template: str,
        method: str,
        failure_stage: str = TENANT_CONTEXT_FAILURE_STAGE,
    ) -> None:
        self.tenant_id = tenant_id
        self.agent_client_id = agent_client_id
        self.correlation_identity = correlation_identity
        self.route_template = route_template
        self.method = method
        self.failure_stage = failure_stage
        super().__init__(ReasonCode.TENANT_CONTEXT_MISSING.value)

    def __str__(self) -> str:
        return ReasonCode.TENANT_CONTEXT_MISSING.value


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    value = getattr(route, "path", None)
    if isinstance(value, str) and value.startswith("/api/trust/"):
        return value
    return "/api/trust/unknown"


def _correlation_identity(request: Request, caller: MachineCallerContext) -> str:
    raw = request.headers.get("X-Correlation-ID", "")
    try:
        return str(UUID(raw))
    except (TypeError, ValueError):
        return caller.request_identity_hash


def _tenant_context_exception(
    request: Request,
    caller: MachineCallerContext,
) -> TenantContextMissingException:
    return TenantContextMissingException(
        tenant_id=caller.tenant_id,
        agent_client_id=caller.agent_client_id,
        correlation_identity=_correlation_identity(request, caller),
        route_template=_route_template(request),
        method=request.method,
    )


async def assert_authenticated_tenant_context(
    request: Request,
    session: AsyncSession,
    caller: MachineCallerContext,
) -> MachineCallerContext:
    """Prove principal, header, transaction GUC, and RLS role are coherent."""
    request.state.machine_caller = caller
    try:
        requested_tenant = UUID(request.headers.get("X-Tenant-ID", ""))
    except (TypeError, ValueError):
        raise _tenant_context_exception(request, caller) from None
    if requested_tenant != caller.tenant_id:
        raise _tenant_context_exception(request, caller)

    try:
        result = await session.execute(
            text(
                """
                SELECT
                    current_setting('app.current_tenant_id', true),
                    COALESCE(
                        (
                            SELECT rolbypassrls
                            FROM pg_catalog.pg_roles
                            WHERE rolname = current_user
                        ),
                        false
                    ),
                    COALESCE(
                        (
                            SELECT rolsuper
                            FROM pg_catalog.pg_roles
                            WHERE rolname = current_user
                        ),
                        false
                    )
                """
            )
        )
        row = result.first()
    except Exception:
        raise _tenant_context_exception(request, caller) from None

    if row is None or bool(row[1]) or bool(row[2]):
        raise _tenant_context_exception(request, caller)
    try:
        transaction_tenant = UUID(str(row[0]))
    except (TypeError, ValueError):
        raise _tenant_context_exception(request, caller) from None
    if transaction_tenant != caller.tenant_id:
        raise _tenant_context_exception(request, caller)
    return caller


async def record_tenant_context_failure_durable(
    exc: TenantContextMissingException,
    *,
    audit_session_factory: AuditSessionFactory | None = None,
) -> None:
    """Commit through P7 with separate acquisition and operation deadlines."""
    client_hash = tagged_sha256(
        {
            "agent_client_id": str(exc.agent_client_id),
            "purpose": "b25-p10-machine-client-audit-identity",
        }
    )
    audit_request = TrustAuditRequest(
        tenant_id=exc.tenant_id,
        event_type="scope_denial",
        status="refused",
        idempotency_key=exc.correlation_identity,
        subject_type=(
            f"trust_api:{exc.method}:{exc.route_template}:{exc.failure_stage}"
        ),
        subject_ref_hash=None,
        tenant_id_hash=tenant_hash(exc.tenant_id),
        policy_state="blocked",
        reason_code=ReasonCode.TENANT_CONTEXT_MISSING,
        semantic_truth_hash=None,
        envelope_hash=None,
        audience_id_hash=client_hash,
        evidence_refs_allowed=False,
        created_at=datetime.now(timezone.utc),
        created_at_source="request_issuance_context",
    )
    if audit_session_factory is None:
        from app.db.session import AsyncSessionLocal

        audit_session_factory = AsyncSessionLocal

    async with audit_session_factory() as audit_session:
        await asyncio.wait_for(
            audit_session.connection(),
            timeout=TENANT_AUDIT_ACQUIRE_TIMEOUT_SECONDS,
        )

        async def _persist_and_commit() -> None:
            await audit_session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(exc.tenant_id)},
            )
            await record_trust_audit_event(
                audit_session,
                audit_request,
                access_log_only=True,
            )
            await audit_session.commit()

        await asyncio.wait_for(
            _persist_and_commit(),
            timeout=TENANT_AUDIT_OPERATION_TIMEOUT_SECONDS,
        )


def _emergency_signal_material(exc: TenantContextMissingException) -> dict[str, str]:
    return {
        "event_type": "tenant_context_audit_failure",
        "tenant_id_hash": tenant_hash(exc.tenant_id),
        "agent_client_id_hash": tagged_sha256(str(exc.agent_client_id)),
        "correlation_identity_hash": tagged_sha256(exc.correlation_identity),
        "route_template": exc.route_template,
        "failure_stage": exc.failure_stage,
        "audit_outcome": "emergency_only",
    }


async def _emit_tenant_context_emergency_signal(
    exc: TenantContextMissingException,
    failure: BaseException,
) -> None:
    """Dispatch a bounded PII-free critical signal even when the DB is unavailable."""
    material = _emergency_signal_material(exc)
    TENANT_EMERGENCY_SIGNALS.append(material)

    def _write_log() -> None:
        logger.critical(
            "Trust tenant-context audit persistence failed",
            extra=material,
            exc_info=(type(failure), failure, failure.__traceback__),
        )

    async def _bounded_log_slot() -> None:
        async with _EMERGENCY_LOG_SLOTS:
            await asyncio.to_thread(_write_log)

    try:
        await asyncio.wait_for(
            _bounded_log_slot(),
            timeout=TENANT_EMERGENCY_SIGNAL_TIMEOUT_SECONDS,
        )
    except Exception:
        # The bounded in-memory signal above remains authoritative emergency
        # evidence even when logging infrastructure is itself unavailable.
        return


async def tenant_context_missing_exception_handler(
    request: Request,
    exc: TenantContextMissingException,
) -> JSONResponse:
    """Finish durable-audit or emergency-only handling within 1.5 seconds."""

    def _set_audit_outcome(value: str) -> None:
        state = getattr(request, "state", None)
        if state is not None:
            state.tenant_context_audit_outcome = value

    async def _audit_or_signal() -> None:
        acquired = False
        try:
            await asyncio.wait_for(_TENANT_FAILURE_SLOTS.acquire(), timeout=0.010)
            acquired = True
            await record_tenant_context_failure_durable(exc)
            _set_audit_outcome("durable_committed")
        except Exception as failure:
            _set_audit_outcome("emergency_only")
            await _emit_tenant_context_emergency_signal(exc, failure)
        finally:
            if acquired:
                _TENANT_FAILURE_SLOTS.release()

    try:
        await asyncio.wait_for(
            _audit_or_signal(),
            timeout=TENANT_HANDLER_TIMEOUT_SECONDS,
        )
    except Exception:
        _set_audit_outcome("emergency_only")
        TENANT_EMERGENCY_SIGNALS.append(_emergency_signal_material(exc))
    return JSONResponse(
        status_code=503,
        content={
            "status": "unavailable",
            "reason_code": TENANT_CONTEXT_EXTERNAL_REASON,
        },
    )
