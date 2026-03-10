"""
Transient OAuth handshake state service.

This service enforces:
- tenant/user/provider binding on callback state
- single-use consume semantics for replay resistance
- bounded expiry + garbage-collection progression
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.secrets import (
    get_platform_encryption_material_for_write,
    resolve_platform_encryption_key_by_id,
)
from app.models.oauth_handshake_session import OAuthHandshakeSession

DEFAULT_GC_GRACE_SECONDS = 24 * 60 * 60


class OAuthHandshakeStateError(RuntimeError):
    pass


class OAuthHandshakeStateConflictError(OAuthHandshakeStateError):
    pass


class OAuthHandshakeStateNotFoundError(OAuthHandshakeStateError):
    pass


class OAuthHandshakeStateReplayError(OAuthHandshakeStateError):
    pass


class OAuthHandshakeStateExpiredError(OAuthHandshakeStateError):
    pass


class OAuthHandshakeStateBindingError(OAuthHandshakeStateError):
    pass


class OAuthHandshakeStateAbortedError(OAuthHandshakeStateError):
    pass


@dataclass(frozen=True)
class OAuthHandshakeCreateResult:
    id: UUID
    state_reference: str
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class OAuthHandshakeConsumeResult:
    id: UUID
    tenant_id: UUID
    user_id: UUID
    platform: str
    created_at: datetime
    expires_at: datetime
    consumed_at: datetime
    pkce_verifier: str | None
    pkce_code_challenge: str | None
    pkce_code_challenge_method: str | None
    redirect_uri: str | None
    provider_session_metadata: dict | None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _state_hash(state_reference: str) -> str:
    cleaned = state_reference.strip()
    if not cleaned:
        raise ValueError("state_reference cannot be empty")
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()


def _gc_after(expires_at: datetime, gc_grace_seconds: int) -> datetime:
    return expires_at + timedelta(seconds=max(0, int(gc_grace_seconds)))


def issue_state_reference() -> str:
    return secrets.token_urlsafe(32)


def _coerce_db_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


async def _decrypt_ciphertext_once(
    session: AsyncSession,
    *,
    ciphertext: bytes | memoryview | None,
    key: str,
) -> str | None:
    if ciphertext is None:
        return None
    if isinstance(ciphertext, memoryview):
        cipher_bytes = bytes(ciphertext)
    elif isinstance(ciphertext, bytes):
        cipher_bytes = ciphertext
    else:
        cipher_bytes = bytes(ciphertext)
    result = await session.execute(
        text("SELECT pgp_sym_decrypt(CAST(:ciphertext AS bytea), CAST(:key AS text)) AS value"),
        {"ciphertext": cipher_bytes, "key": key},
    )
    return _coerce_db_text(result.scalar_one_or_none())


def _is_state_unique_violation(exc: IntegrityError) -> bool:
    text_value = str(exc).lower()
    return "uq_oauth_handshake_sessions_tenant_state_hash" in text_value


async def _classify_consume_failure(
    session: AsyncSession,
    *,
    state_nonce_hash: str,
    tenant_id: UUID,
    user_id: UUID,
    platform: str,
    now: datetime,
) -> str:
    query = (
        select(
            OAuthHandshakeSession.tenant_id,
            OAuthHandshakeSession.user_id,
            OAuthHandshakeSession.platform,
            OAuthHandshakeSession.status,
            OAuthHandshakeSession.expires_at,
            OAuthHandshakeSession.consumed_at,
        )
        .where(OAuthHandshakeSession.state_nonce_hash == state_nonce_hash)
        .order_by(OAuthHandshakeSession.created_at.desc())
        .limit(1)
    )
    result = await session.execute(query)
    row = result.mappings().first()
    if not row:
        return "not_found"
    if (
        row["tenant_id"] != tenant_id
        or row["user_id"] != user_id
        or row["platform"] != platform
    ):
        return "binding_mismatch"

    status = row["status"]
    if status == "aborted":
        return "aborted"
    if status == "consumed" or row["consumed_at"] is not None:
        return "replayed"
    if status == "expired":
        return "expired"
    expires_at = row["expires_at"]
    if expires_at is not None and expires_at <= now:
        return "expired"
    return "not_found"


class OAuthHandshakeStateService:
    @staticmethod
    async def create_session(
        session: AsyncSession,
        *,
        tenant_id: UUID,
        user_id: UUID,
        platform: str,
        expires_at: datetime,
        state_reference: str | None = None,
        pkce_verifier: str | None = None,
        pkce_code_challenge: str | None = None,
        pkce_code_challenge_method: str | None = None,
        redirect_uri: str | None = None,
        provider_session_metadata: Optional[dict] = None,
        now: datetime | None = None,
        gc_grace_seconds: int = DEFAULT_GC_GRACE_SECONDS,
    ) -> OAuthHandshakeCreateResult:
        now_ts = now or _utc_now()
        if expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")
        if expires_at <= now_ts:
            raise ValueError("expires_at must be in the future")

        reference = state_reference or issue_state_reference()
        nonce_hash = _state_hash(reference)
        gc_after_ts = _gc_after(expires_at, gc_grace_seconds)

        encrypted_verifier = None
        pkce_key_id = None
        if pkce_verifier:
            pkce_key_id, encryption_key = get_platform_encryption_material_for_write()
            encrypted_verifier = func.pgp_sym_encrypt(pkce_verifier, encryption_key)

        stmt = (
            insert(OAuthHandshakeSession)
            .values(
                tenant_id=tenant_id,
                user_id=user_id,
                platform=platform,
                state_nonce_hash=nonce_hash,
                encrypted_pkce_verifier=encrypted_verifier,
                pkce_key_id=pkce_key_id,
                pkce_code_challenge=pkce_code_challenge,
                pkce_code_challenge_method=pkce_code_challenge_method,
                redirect_uri=redirect_uri,
                provider_session_metadata=provider_session_metadata,
                status="pending",
                terminal_reason=None,
                created_at=func.now(),
                updated_at=func.now(),
                expires_at=expires_at,
                consumed_at=None,
                gc_after=gc_after_ts,
            )
            .returning(
                OAuthHandshakeSession.id,
                OAuthHandshakeSession.created_at,
                OAuthHandshakeSession.expires_at,
            )
        )
        try:
            result = await session.execute(stmt)
        except IntegrityError as exc:
            if _is_state_unique_violation(exc):
                raise OAuthHandshakeStateConflictError("state reference already exists") from exc
            raise

        row = result.mappings().one()
        return OAuthHandshakeCreateResult(
            id=row["id"],
            state_reference=reference,
            created_at=row["created_at"],
            expires_at=row["expires_at"],
        )

    @staticmethod
    async def consume_session(
        session: AsyncSession,
        *,
        tenant_id: UUID,
        user_id: UUID,
        platform: str,
        state_reference: str,
        now: datetime | None = None,
        gc_grace_seconds: int = DEFAULT_GC_GRACE_SECONDS,
    ) -> OAuthHandshakeConsumeResult:
        now_ts = now or _utc_now()
        state_nonce_hash = _state_hash(state_reference)
        gc_after_ts = now_ts + timedelta(seconds=max(0, int(gc_grace_seconds)))

        stmt = (
            update(OAuthHandshakeSession)
            .where(
                OAuthHandshakeSession.tenant_id == tenant_id,
                OAuthHandshakeSession.user_id == user_id,
                OAuthHandshakeSession.platform == platform,
                OAuthHandshakeSession.state_nonce_hash == state_nonce_hash,
                OAuthHandshakeSession.status == "pending",
                OAuthHandshakeSession.consumed_at.is_(None),
                OAuthHandshakeSession.expires_at > now_ts,
            )
            .values(
                status="consumed",
                consumed_at=now_ts,
                terminal_reason=None,
                gc_after=gc_after_ts,
                updated_at=now_ts,
            )
            .returning(
                OAuthHandshakeSession.id,
                OAuthHandshakeSession.tenant_id,
                OAuthHandshakeSession.user_id,
                OAuthHandshakeSession.platform,
                OAuthHandshakeSession.created_at,
                OAuthHandshakeSession.expires_at,
                OAuthHandshakeSession.consumed_at,
                OAuthHandshakeSession.encrypted_pkce_verifier,
                OAuthHandshakeSession.pkce_key_id,
                OAuthHandshakeSession.pkce_code_challenge,
                OAuthHandshakeSession.pkce_code_challenge_method,
                OAuthHandshakeSession.redirect_uri,
                OAuthHandshakeSession.provider_session_metadata,
            )
        )
        result = await session.execute(stmt)
        row = result.mappings().first()
        if not row:
            reason = await _classify_consume_failure(
                session,
                state_nonce_hash=state_nonce_hash,
                tenant_id=tenant_id,
                user_id=user_id,
                platform=platform,
                now=now_ts,
            )
            if reason == "binding_mismatch":
                raise OAuthHandshakeStateBindingError("state binding mismatch")
            if reason == "expired":
                raise OAuthHandshakeStateExpiredError("state has expired")
            if reason == "replayed":
                raise OAuthHandshakeStateReplayError("state has already been consumed")
            if reason == "aborted":
                raise OAuthHandshakeStateAbortedError("state is aborted")
            raise OAuthHandshakeStateNotFoundError("state not found")

        pkce_verifier = None
        encrypted_verifier = row["encrypted_pkce_verifier"]
        if encrypted_verifier is not None:
            key = resolve_platform_encryption_key_by_id(str(row["pkce_key_id"]))
            pkce_verifier = await _decrypt_ciphertext_once(
                session,
                ciphertext=encrypted_verifier,
                key=key,
            )

        return OAuthHandshakeConsumeResult(
            id=row["id"],
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            platform=row["platform"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            consumed_at=row["consumed_at"],
            pkce_verifier=pkce_verifier,
            pkce_code_challenge=row["pkce_code_challenge"],
            pkce_code_challenge_method=row["pkce_code_challenge_method"],
            redirect_uri=row["redirect_uri"],
            provider_session_metadata=row["provider_session_metadata"],
        )

    @staticmethod
    async def expire_pending_sessions(
        session: AsyncSession,
        *,
        now: datetime | None = None,
        batch_size: int = 500,
    ) -> int:
        now_ts = now or _utc_now()
        result = await session.execute(
            text(
                """
                WITH candidates AS (
                    SELECT id
                    FROM public.oauth_handshake_sessions
                    WHERE status = 'pending'
                      AND expires_at <= :now_ts
                    ORDER BY expires_at ASC
                    LIMIT :batch_size
                )
                UPDATE public.oauth_handshake_sessions AS target
                SET status = 'expired',
                    terminal_reason = COALESCE(target.terminal_reason, 'ttl_expired'),
                    updated_at = :now_ts
                FROM candidates
                WHERE target.id = candidates.id
                RETURNING target.id
                """
            ),
            {"now_ts": now_ts, "batch_size": max(1, int(batch_size))},
        )
        return len(result.fetchall())

    @staticmethod
    async def gc_eligible_sessions(
        session: AsyncSession,
        *,
        now: datetime | None = None,
        batch_size: int = 500,
    ) -> int:
        now_ts = now or _utc_now()
        result = await session.execute(
            text(
                """
                WITH candidates AS (
                    SELECT id
                    FROM public.oauth_handshake_sessions
                    WHERE gc_after <= :now_ts
                      AND (
                          status IN ('consumed', 'expired', 'aborted')
                          OR expires_at <= :now_ts
                      )
                    ORDER BY gc_after ASC
                    LIMIT :batch_size
                )
                DELETE FROM public.oauth_handshake_sessions AS target
                USING candidates
                WHERE target.id = candidates.id
                RETURNING target.id
                """
            ),
            {"now_ts": now_ts, "batch_size": max(1, int(batch_size))},
        )
        return len(result.fetchall())
