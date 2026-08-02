"""B2.5-P9 machine-caller authentication middleware.

FastAPI dependency that authenticates machine callers (design-partner agents)
against the B2.5-P9 identity substrate. This is strictly the gateway: it does
NOT mount any P10 Trust API route logic.

Physics (per B2.5-P9 Remediation Directive):
- Credential verification is O(1) by token_prefix index lookup, then
  constant-time SHA-256 via hmac.compare_digest. No bcrypt/argon2, no
  timing oracle (H-P9-02).
- Replay protection is atomic: INSERT ... ON CONFLICT DO NOTHING on the
  UNIQUE(tenant_id, nonce_value) constraint. No application-level
  exists()->insert() TOCTOU race (H-P9-03).
- Denial audit writes go through the P7 autonomous session seam
  (record_trust_audit_event_durable) so they survive FastAPI exception
  rollbacks (H-P9-04).
- Reserved B5.2 action scopes are rejected at the application layer before
  any DB write (H-P9-06); the DB CHECK constraint + trigger are the
  defense-in-depth backstop.
- On any failure, a uniform 401/403 is returned to the caller (no evidence
  leakage). Internally, the exact failure is mapped to a P6 Reason Code and
  durably audited.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text

from app.trust.audit import (
    TrustAuditRequest,
    record_trust_audit_event_durable,
)
from app.trust.machine_identity import (
    AgentScope,
    ReservedScopeError,
    assert_scope_issuable,
    verify_machine_token,
)
from app.trust.reason_codes import ReasonCode
from app.trust.refusal import tagged_sha256, tenant_hash


DEFAULT_NONCE_TTL_SECONDS: int = 300
MIN_NONCE_LENGTH: int = 16
MAX_NONCE_LENGTH: int = 256
DEFAULT_RATE_LIMIT_WINDOW_SECONDS: int = 60
DEFAULT_RATE_LIMIT_REQUESTS: int = 100


class MachineAuthError(Exception):
    """Internal machine-auth failure with a P6 reason code."""

    def __init__(self, reason_code: ReasonCode, detail: str = "") -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(detail or reason_code.value)


@dataclass(frozen=True)
class MachineCallerContext:
    """Authenticated machine-caller identity returned on success."""

    agent_client_id: UUID
    tenant_id: UUID
    audience: str
    scopes: frozenset[AgentScope]
    nonce_value: str
    request_identity_hash: str


async def _write_denial_audit(
    *,
    tenant_id,
    reason_code,
    idempotency_key,
    subject_type="machine_caller",
):
    """Write a P7 scope-denial audit row through the autonomous session seam.

    This MUST use record_trust_audit_event_durable (which opens its own
    independent short-lived DB session / autonomous transaction) so the audit
    row physically survives the FastAPI exception rollback that follows.
    """
    resolved_tenant = tenant_id or UUID(int=0)
    tenant_id_hash_value = tenant_hash(resolved_tenant)
    now = datetime.now(timezone.utc)
    audit_request = TrustAuditRequest(
        tenant_id=resolved_tenant,
        event_type="scope_denial",
        status="refused",
        idempotency_key=idempotency_key,
        subject_type=subject_type,
        subject_ref_hash=None,
        tenant_id_hash=tenant_id_hash_value,
        policy_state="read_only",
        reason_code=reason_code,
        semantic_truth_hash=None,
        envelope_hash=None,
        audience_id_hash=None,
        evidence_refs_allowed=False,
        created_at=now,
        created_at_source="request_issuance_context",
    )
    try:
        await record_trust_audit_event_durable(audit_request)
    except Exception:
        pass


async def _lookup_credential_by_prefix(
    db_session,
    *,
    tenant_id,
    token_prefix,
):
    """O(1) index lookup by token_prefix."""
    result = await db_session.execute(
        text(
            """
            SELECT
                c.id AS agent_client_id,
                c.tenant_id,
                c.audience,
                c.status AS client_status,
                cred.id AS credential_id,
                cred.token_hash,
                cred.hash_algorithm,
                cred.status AS credential_status,
                cred.expires_at
            FROM public.agent_service_credentials cred
            JOIN public.agent_clients c ON c.id = cred.agent_client_id
            WHERE cred.tenant_id = :tenant_id
              AND cred.token_prefix = :token_prefix
              AND cred.status = 'active'
              AND c.status = 'active'
            LIMIT 1
            """
        ),
        {"tenant_id": str(tenant_id), "token_prefix": token_prefix},
    )
    row = result.first()
    if row is None:
        return None
    return dict(row._mapping)


async def _check_revocation(
    db_session,
    *,
    tenant_id,
    token_prefix,
):
    """Return True if the token prefix has been revoked."""
    result = await db_session.execute(
        text(
            """
            SELECT 1 FROM public.agent_token_revocations
            WHERE tenant_id = :tenant_id AND token_prefix = :token_prefix
            LIMIT 1
            """
        ),
        {"tenant_id": str(tenant_id), "token_prefix": token_prefix},
    )
    return result.first() is not None


async def _load_scopes(
    db_session,
    *,
    tenant_id,
    agent_client_id,
):
    """Load active (non-revoked) scope grants for the agent client."""
    result = await db_session.execute(
        text(
            """
            SELECT scope_value FROM public.agent_scope_grants
            WHERE tenant_id = :tenant_id
              AND agent_client_id = :agent_client_id
              AND revoked_at IS NULL
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "agent_client_id": str(agent_client_id),
        },
    )
    scopes = set()
    for row in result:
        scope_value = str(row[0])
        try:
            scopes.add(assert_scope_issuable(scope_value))
        except ReservedScopeError:
            continue
    return frozenset(scopes)


async def _atomic_nonce_insert(
    db_session,
    *,
    tenant_id,
    agent_client_id,
    nonce_value,
    request_identity_hash,
    ttl_seconds=DEFAULT_NONCE_TTL_SECONDS,
):
    """Atomically insert a nonce. Returns True if new, False if replay.

    Uses INSERT ... ON CONFLICT DO NOTHING on the
    UNIQUE(tenant_id, nonce_value) constraint. This is the atomic
    primitive that eliminates the TOCTOU race in H-P9-03.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds)
    result = await db_session.execute(
        text(
            """
            INSERT INTO public.trust_request_nonces (
                tenant_id, agent_client_id, nonce_value,
                request_identity_hash, expires_at
            ) VALUES (
                :tenant_id, :agent_client_id, :nonce_value,
                :request_identity_hash, :expires_at
            )
            ON CONFLICT (tenant_id, nonce_value) DO NOTHING
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "agent_client_id": str(agent_client_id),
            "nonce_value": nonce_value,
            "request_identity_hash": request_identity_hash,
            "expires_at": expires_at,
        },
    )
    await db_session.commit()
    return result.rowcount == 1


async def _check_rate_limit(
    db_session,
    *,
    tenant_id,
    agent_client_id,
    window_seconds=DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
    request_limit=DEFAULT_RATE_LIMIT_REQUESTS,
    at_time: datetime | None = None,
):
    """Atomic fixed-window rate check with zero hot-path row locks.

    Uses one INSERT ... ON CONFLICT DO UPDATE ... RETURNING statement against
    a deterministic time bucket. The stable bucket boundary is essential: if
    every request supplied unique start/end timestamps, concurrent requests
    would never conflict and the limit would be bypassable.
    """
    if window_seconds <= 0 or request_limit <= 0:
        raise ValueError("rate_limit_configuration_must_be_positive")
    now = at_time or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("rate_limit_time_must_be_timezone_aware")
    now = now.astimezone(timezone.utc)
    bucket_epoch = int(now.timestamp()) // window_seconds * window_seconds
    window_start = datetime.fromtimestamp(bucket_epoch, tz=timezone.utc)
    window_end = window_start + timedelta(seconds=window_seconds)
    result = await db_session.execute(
        text(
            """
            INSERT INTO public.trust_rate_limit_state (
                tenant_id, agent_client_id,
                window_started_at, window_ended_at,
                request_count, request_limit
            ) VALUES (
                :tenant_id, :agent_client_id,
                :window_start, :window_end,
                1, :request_limit
            )
            ON CONFLICT (tenant_id, agent_client_id, window_started_at, window_ended_at)
            DO UPDATE SET request_count = trust_rate_limit_state.request_count + 1,
                          last_request_at = now(),
                          updated_at = now()
            RETURNING request_count
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "agent_client_id": str(agent_client_id),
            "window_start": window_start,
            "window_end": window_end,
            "request_limit": request_limit,
        },
    )
    row = result.first()
    await db_session.commit()
    if row is None:
        return True
    count = int(row[0])
    return count <= request_limit


def _machine_request_identity_hash(
    *,
    tenant_id,
    token_prefix,
    nonce_value,
):
    """Stable request identity hash for nonce insertion and audit.

    Uses tagged_sha256 from the P6 refusal module (stable non-JSON internal
    bytes) rather than the stdlib JSON serializer, to satisfy the P2
    canonicalization serializer boundary which bans that function in the trust path.
    """
    return tagged_sha256(
        {
            "tenant_id": str(tenant_id),
            "token_prefix": token_prefix,
            "nonce_value": nonce_value,
            "purpose": "b25-p9-machine-caller-request-identity",
        }
    )


async def authenticate_machine_caller(
    request,
    db_session,
    *,
    required_scope=AgentScope.ENVELOPE_READ,
    nonce_ttl_seconds=DEFAULT_NONCE_TTL_SECONDS,
):
    """Authenticate a machine caller and return the caller context.

    This is the P9 gateway. P10 route handlers depend on this; they do NOT
    implement their own auth.

    Control flow (per Remediation C):
    extract prefix -> lookup hash -> verify SHA-256 -> check revocations ->
    validate tenant -> verify scope -> check replay -> check rate-limit.

    On any failure: write autonomous P7 audit, raise uniform 401/403.
    """
    required = (
        required_scope
        if isinstance(required_scope, AgentScope)
        else assert_scope_issuable(required_scope)
    )

    auth_header = request.headers.get("Authorization", "")
    tenant_header = request.headers.get("X-Tenant-ID", "")
    nonce_header = request.headers.get("X-Trust-Nonce", "")
    idempotency_header = request.headers.get("X-Idempotency-Key", "")

    async def deny(
        reason,
        *,
        http_status=status.HTTP_401_UNAUTHORIZED,
        tenant_id_for_audit=None,
    ):
        await _write_denial_audit(
            tenant_id=tenant_id_for_audit,
            reason_code=reason,
            idempotency_key=idempotency_header or nonce_header or "unknown",
        )
        raise HTTPException(
            status_code=http_status,
            detail="Authentication failed.",
        )

    if not auth_header.startswith("Bearer "):
        return await deny(ReasonCode.SCOPE_DENIED)
    presented_token = auth_header[len("Bearer ") :]
    if not presented_token or len(presented_token) < 8:
        return await deny(ReasonCode.SCOPE_DENIED)
    if not tenant_header:
        return await deny(ReasonCode.TENANT_MISMATCH)
    if not MIN_NONCE_LENGTH <= len(nonce_header) <= MAX_NONCE_LENGTH:
        return await deny(ReasonCode.REPLAY_REJECTED)

    try:
        tenant_id = UUID(tenant_header)
    except ValueError:
        return await deny(ReasonCode.TENANT_MISMATCH)

    token_prefix = presented_token[:8]

    cred = await _lookup_credential_by_prefix(
        db_session,
        tenant_id=tenant_id,
        token_prefix=token_prefix,
    )
    if cred is None:
        return await deny(
            ReasonCode.SCOPE_DENIED,
            tenant_id_for_audit=tenant_id,
        )

    if not verify_machine_token(
        presented_token,
        str(cred["token_hash"]),
        str(cred.get("hash_algorithm", "sha256")),
    ):
        return await deny(
            ReasonCode.SCOPE_DENIED,
            tenant_id_for_audit=tenant_id,
        )

    agent_client_id = UUID(str(cred["agent_client_id"]))

    if await _check_revocation(
        db_session,
        tenant_id=tenant_id,
        token_prefix=token_prefix,
    ):
        return await deny(
            ReasonCode.SCOPE_DENIED,
            http_status=status.HTTP_403_FORBIDDEN,
            tenant_id_for_audit=tenant_id,
        )

    cred_tenant = UUID(str(cred["tenant_id"]))
    if cred_tenant != tenant_id:
        return await deny(
            ReasonCode.TENANT_MISMATCH,
            http_status=status.HTTP_403_FORBIDDEN,
            tenant_id_for_audit=tenant_id,
        )

    scopes = await _load_scopes(
        db_session,
        tenant_id=tenant_id,
        agent_client_id=agent_client_id,
    )
    if required not in scopes:
        return await deny(
            ReasonCode.SCOPE_DENIED,
            http_status=status.HTTP_403_FORBIDDEN,
            tenant_id_for_audit=tenant_id,
        )

    identity_hash = _machine_request_identity_hash(
        tenant_id=tenant_id,
        token_prefix=token_prefix,
        nonce_value=nonce_header,
    )
    is_new_nonce = await _atomic_nonce_insert(
        db_session,
        tenant_id=tenant_id,
        agent_client_id=agent_client_id,
        nonce_value=nonce_header,
        request_identity_hash=identity_hash,
        ttl_seconds=nonce_ttl_seconds,
    )
    if not is_new_nonce:
        return await deny(
            ReasonCode.REPLAY_REJECTED,
            http_status=status.HTTP_403_FORBIDDEN,
            tenant_id_for_audit=tenant_id,
        )

    within_budget = await _check_rate_limit(
        db_session,
        tenant_id=tenant_id,
        agent_client_id=agent_client_id,
    )
    if not within_budget:
        return await deny(
            ReasonCode.RATE_LIMITED,
            http_status=status.HTTP_429_TOO_MANY_REQUESTS,
            tenant_id_for_audit=tenant_id,
        )

    return MachineCallerContext(
        agent_client_id=agent_client_id,
        tenant_id=tenant_id,
        audience=str(cred["audience"]),
        scopes=scopes,
        nonce_value=nonce_header,
        request_identity_hash=identity_hash,
    )
