"""Fail-closed tenant-context enforcement for authenticated Trust API callers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.trust.audit import TrustAuditRequest, record_trust_audit_event_durable
from app.trust.machine_auth import MachineCallerContext
from app.trust.reason_codes import ReasonCode
from app.trust.refusal import tagged_sha256, tenant_hash


logger = logging.getLogger(__name__)
TENANT_CONTEXT_FAILURE_STAGE = "post_auth_transaction_rls_assertion"
TENANT_CONTEXT_EXTERNAL_REASON = "tenant_context_unavailable"


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
                    )
                """
            )
        )
        row = result.first()
    except Exception:
        raise _tenant_context_exception(request, caller) from None

    if row is None or bool(row[1]):
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
) -> None:
    """Commit the security failure through P7's independent audit transaction."""
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
    await record_trust_audit_event_durable(audit_request, access_log_only=True)


async def tenant_context_missing_exception_handler(
    request: Request,
    exc: TenantContextMissingException,
) -> JSONResponse:
    """Durably audit and emit one sanitized, non-oracular availability failure."""
    try:
        await record_tenant_context_failure_durable(exc)
    except Exception:
        logger.critical(
            "Trust tenant-context audit persistence failed",
            extra={
                "event_type": "tenant_context_audit_failure",
                "tenant_id_hash": tenant_hash(exc.tenant_id),
                "agent_client_id_hash": tagged_sha256(str(exc.agent_client_id)),
                "correlation_identity_hash": tagged_sha256(exc.correlation_identity),
                "route_template": exc.route_template,
                "failure_stage": exc.failure_stage,
            },
            exc_info=True,
        )
    return JSONResponse(
        status_code=503,
        content={
            "status": "unavailable",
            "reason_code": TENANT_CONTEXT_EXTERNAL_REASON,
        },
    )
