"""
Service layer for platform credentials (encrypted tokens).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from app.core.secrets import resolve_platform_encryption_key_by_id
from app.models.platform_connection import PlatformConnection
from app.models.platform_credential import PlatformCredential
from app.services.platform_connections import PlatformConnectionNotFoundError


class PlatformCredentialExpiredError(RuntimeError):
    pass


class PlatformCredentialNotFoundError(RuntimeError):
    pass


DEFAULT_PROVIDER_REFRESH_LEAD_TIME = timedelta(hours=25)
DEFAULT_PROVIDER_REFRESH_CLAIM_HOLD = timedelta(minutes=5)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def compute_next_refresh_due_at(
    expires_at: datetime | None,
    *,
    now: datetime | None = None,
    lead_time: timedelta = DEFAULT_PROVIDER_REFRESH_LEAD_TIME,
) -> datetime | None:
    if expires_at is None:
        return None
    now_ts = _as_utc(now or datetime.now(timezone.utc))
    due_at = _as_utc(expires_at) - lead_time
    if due_at <= now_ts:
        return now_ts
    return due_at


@dataclass(frozen=True)
class PlatformCredentialRefreshDue:
    id: UUID
    platform_connection_id: UUID
    platform: str
    next_refresh_due_at: datetime
    lifecycle_status: str
    refresh_failure_count: int
    last_failure_class: str | None


@dataclass(frozen=True)
class PlatformCredentialLifecycleSnapshot:
    id: UUID
    platform_connection_id: UUID
    platform: str
    lifecycle_status: str
    expires_at: datetime | None
    next_refresh_due_at: datetime | None
    scope: str | None
    last_failure_class: str | None
    last_failure_at: datetime | None
    last_refresh_at: datetime | None
    revoked_at: datetime | None
    updated_at: datetime


class PlatformCredentialStore:
    @staticmethod
    async def upsert_tokens(
        session: AsyncSession,
        *,
        tenant_id: UUID,
        platform: str,
        platform_account_id: str,
        access_token: str,
        refresh_token: Optional[str],
        expires_at: Optional[datetime],
        scope: Optional[str],
        token_type: Optional[str],
        key_id: str,
        encryption_key: str,
    ) -> dict:
        connection_query = select(PlatformConnection.id).where(
            PlatformConnection.tenant_id == tenant_id,
            PlatformConnection.platform == platform,
            PlatformConnection.platform_account_id == platform_account_id,
        )
        connection_result = await session.execute(connection_query)
        connection_id = connection_result.scalar_one_or_none()
        if not connection_id:
            raise PlatformConnectionNotFoundError()
        now_ts = datetime.now(timezone.utc)
        next_refresh_due_at = compute_next_refresh_due_at(expires_at, now=now_ts)

        encrypted_access = func.pgp_sym_encrypt(access_token, encryption_key)
        encrypted_refresh = (
            func.pgp_sym_encrypt(refresh_token, encryption_key)
            if refresh_token
            else None
        )

        stmt = insert(PlatformCredential).values(
            tenant_id=tenant_id,
            platform_connection_id=connection_id,
            platform=platform,
            encrypted_access_token=encrypted_access,
            encrypted_refresh_token=encrypted_refresh,
            expires_at=expires_at,
            next_refresh_due_at=next_refresh_due_at,
            scope=scope,
            token_type=token_type,
            lifecycle_status="active",
            refresh_failure_count=0,
            last_failure_class=None,
            last_failure_at=None,
            last_refresh_at=None,
            revoked_at=None,
            key_id=key_id,
            created_at=func.now(),
            updated_at=func.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "platform", "platform_connection_id"],
            set_={
                "encrypted_access_token": encrypted_access,
                "encrypted_refresh_token": encrypted_refresh,
                "expires_at": expires_at,
                "next_refresh_due_at": next_refresh_due_at,
                "scope": scope,
                "token_type": token_type,
                "lifecycle_status": "active",
                "refresh_failure_count": 0,
                "last_failure_class": None,
                "last_failure_at": None,
                "last_refresh_at": None,
                "revoked_at": None,
                "key_id": key_id,
                "updated_at": func.now(),
            },
        ).returning(
            PlatformCredential.id,
            PlatformCredential.expires_at,
            PlatformCredential.next_refresh_due_at,
            PlatformCredential.lifecycle_status,
            PlatformCredential.updated_at,
        )
        result = await session.execute(stmt)
        row = result.mappings().first()
        return dict(row)

    @staticmethod
    async def claim_refresh_window(
        session: AsyncSession,
        *,
        tenant_id: UUID,
        credential_id: UUID,
        as_of: datetime | None = None,
        hold_for: timedelta = DEFAULT_PROVIDER_REFRESH_CLAIM_HOLD,
    ) -> bool:
        now_ts = _as_utc(as_of or datetime.now(timezone.utc))
        hold_until = now_ts + hold_for
        result = await session.execute(
            update(PlatformCredential)
            .where(
                PlatformCredential.id == credential_id,
                PlatformCredential.tenant_id == tenant_id,
                PlatformCredential.lifecycle_status.in_(("active", "degraded")),
                PlatformCredential.next_refresh_due_at.is_not(None),
                PlatformCredential.next_refresh_due_at <= now_ts,
            )
            .values(
                next_refresh_due_at=hold_until,
                updated_at=func.now(),
            )
            .returning(PlatformCredential.id)
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def list_refresh_due(
        session: AsyncSession,
        *,
        tenant_id: UUID,
        as_of: datetime,
        limit: int = 100,
    ) -> list[PlatformCredentialRefreshDue]:
        query = (
            select(
                PlatformCredential.id,
                PlatformCredential.platform_connection_id,
                PlatformCredential.platform,
                PlatformCredential.next_refresh_due_at,
                PlatformCredential.lifecycle_status,
                PlatformCredential.refresh_failure_count,
                PlatformCredential.last_failure_class,
            )
            .where(
                PlatformCredential.tenant_id == tenant_id,
                PlatformCredential.lifecycle_status.in_(("active", "degraded")),
                PlatformCredential.next_refresh_due_at.is_not(None),
                PlatformCredential.next_refresh_due_at <= as_of,
            )
            .order_by(PlatformCredential.next_refresh_due_at.asc())
            .limit(max(1, int(limit)))
        )
        result = await session.execute(query)
        due_rows: list[PlatformCredentialRefreshDue] = []
        for row in result.mappings().all():
            due_at = row.get("next_refresh_due_at")
            if due_at is None:
                continue
            due_rows.append(
                PlatformCredentialRefreshDue(
                    id=row["id"],
                    platform_connection_id=row["platform_connection_id"],
                    platform=row["platform"],
                    next_refresh_due_at=due_at,
                    lifecycle_status=row["lifecycle_status"],
                    refresh_failure_count=int(row["refresh_failure_count"]),
                    last_failure_class=row.get("last_failure_class"),
                )
            )
        return due_rows

    @staticmethod
    async def record_refresh_failure(
        session: AsyncSession,
        *,
        tenant_id: UUID,
        credential_id: UUID,
        failure_class: str,
        next_refresh_due_at: datetime | None = None,
        failure_at: datetime | None = None,
    ) -> dict:
        failure_at_ts = failure_at or datetime.now(timezone.utc)
        cleaned_failure_class = failure_class.strip() or "unknown_failure"

        values: dict[str, object] = {
            "refresh_failure_count": PlatformCredential.refresh_failure_count + 1,
            "last_failure_class": cleaned_failure_class,
            "last_failure_at": failure_at_ts,
            "lifecycle_status": "degraded",
            "updated_at": func.now(),
        }
        if next_refresh_due_at is not None:
            values["next_refresh_due_at"] = next_refresh_due_at

        result = await session.execute(
            update(PlatformCredential)
            .where(
                PlatformCredential.id == credential_id,
                PlatformCredential.tenant_id == tenant_id,
                PlatformCredential.lifecycle_status != "revoked",
            )
            .values(values)
            .returning(
                PlatformCredential.id,
                PlatformCredential.lifecycle_status,
                PlatformCredential.refresh_failure_count,
                PlatformCredential.last_failure_class,
                PlatformCredential.last_failure_at,
                PlatformCredential.next_refresh_due_at,
                PlatformCredential.updated_at,
            )
        )
        row = result.mappings().first()
        if not row:
            raise PlatformCredentialNotFoundError()
        return dict(row)

    @staticmethod
    async def mark_refresh_success(
        session: AsyncSession,
        *,
        tenant_id: UUID,
        credential_id: UUID,
        access_token: str,
        refresh_token: Optional[str],
        expires_at: Optional[datetime],
        scope: Optional[str],
        token_type: Optional[str],
        key_id: str,
        encryption_key: str,
        refreshed_at: datetime | None = None,
        next_refresh_due_at: datetime | None = None,
    ) -> dict:
        refreshed_at_ts = refreshed_at or datetime.now(timezone.utc)
        due_at = (
            next_refresh_due_at
            if next_refresh_due_at is not None
            else compute_next_refresh_due_at(expires_at, now=refreshed_at_ts)
        )

        encrypted_access = func.pgp_sym_encrypt(access_token, encryption_key)
        encrypted_refresh = (
            func.pgp_sym_encrypt(refresh_token, encryption_key)
            if refresh_token
            else None
        )

        result = await session.execute(
            update(PlatformCredential)
            .where(
                PlatformCredential.id == credential_id,
                PlatformCredential.tenant_id == tenant_id,
            )
            .values(
                encrypted_access_token=encrypted_access,
                encrypted_refresh_token=encrypted_refresh,
                expires_at=expires_at,
                next_refresh_due_at=due_at,
                scope=scope,
                token_type=token_type,
                lifecycle_status="active",
                refresh_failure_count=0,
                last_failure_class=None,
                last_failure_at=None,
                last_refresh_at=refreshed_at_ts,
                revoked_at=None,
                key_id=key_id,
                updated_at=func.now(),
            )
            .returning(
                PlatformCredential.id,
                PlatformCredential.lifecycle_status,
                PlatformCredential.expires_at,
                PlatformCredential.next_refresh_due_at,
                PlatformCredential.last_refresh_at,
                PlatformCredential.refresh_failure_count,
                PlatformCredential.updated_at,
            )
        )
        row = result.mappings().first()
        if not row:
            raise PlatformCredentialNotFoundError()
        return dict(row)

    @staticmethod
    async def mark_revoked(
        session: AsyncSession,
        *,
        tenant_id: UUID,
        credential_id: UUID,
        revoked_at: datetime | None = None,
    ) -> dict:
        revoked_at_ts = revoked_at or datetime.now(timezone.utc)
        result = await session.execute(
            update(PlatformCredential)
            .where(
                PlatformCredential.id == credential_id,
                PlatformCredential.tenant_id == tenant_id,
            )
            .values(
                lifecycle_status="revoked",
                revoked_at=revoked_at_ts,
                next_refresh_due_at=None,
                updated_at=func.now(),
            )
            .returning(
                PlatformCredential.id,
                PlatformCredential.lifecycle_status,
                PlatformCredential.revoked_at,
                PlatformCredential.next_refresh_due_at,
                PlatformCredential.updated_at,
            )
        )
        row = result.mappings().first()
        if not row:
            raise PlatformCredentialNotFoundError()
        return dict(row)

    @staticmethod
    async def get_valid_token(
        session: AsyncSession,
        *,
        tenant_id: UUID,
        platform: str,
        platform_account_id: str,
    ) -> dict:
        query = (
            select(
                PlatformCredential.expires_at,
                PlatformCredential.updated_at,
                PlatformCredential.key_id,
                PlatformCredential.encrypted_access_token,
            )
            .join(
                PlatformConnection,
                PlatformConnection.id == PlatformCredential.platform_connection_id,
            )
            .where(
                PlatformCredential.tenant_id == tenant_id,
                PlatformCredential.platform == platform,
                PlatformConnection.platform_account_id == platform_account_id,
                PlatformCredential.lifecycle_status.in_(("active", "degraded")),
                PlatformCredential.revoked_at.is_(None),
            )
            .order_by(PlatformCredential.updated_at.desc())
            .limit(1)
        )
        result = await session.execute(query)
        row = result.mappings().first()
        if not row:
            raise PlatformCredentialNotFoundError()

        expires_at = row.get("expires_at")
        if expires_at and expires_at <= datetime.now(timezone.utc):
            raise PlatformCredentialExpiredError()

        key_id = str(row["key_id"])
        key = resolve_platform_encryption_key_by_id(key_id)
        access_token = await _decrypt_ciphertext_once(
            session,
            ciphertext=row["encrypted_access_token"],
            key=key,
        )
        if access_token is None:
            raise PlatformCredentialNotFoundError()

        return {
            "access_token": access_token,
            "expires_at": expires_at,
            "updated_at": row["updated_at"],
        }

    @staticmethod
    async def get_latest_lifecycle_snapshot_for_connection(
        session: AsyncSession,
        *,
        tenant_id: UUID,
        connection_id: UUID,
    ) -> PlatformCredentialLifecycleSnapshot | None:
        query = (
            select(
                PlatformCredential.id,
                PlatformCredential.platform_connection_id,
                PlatformCredential.platform,
                PlatformCredential.lifecycle_status,
                PlatformCredential.expires_at,
                PlatformCredential.next_refresh_due_at,
                PlatformCredential.scope,
                PlatformCredential.last_failure_class,
                PlatformCredential.last_failure_at,
                PlatformCredential.last_refresh_at,
                PlatformCredential.revoked_at,
                PlatformCredential.updated_at,
            )
            .where(
                PlatformCredential.tenant_id == tenant_id,
                PlatformCredential.platform_connection_id == connection_id,
            )
            .order_by(PlatformCredential.updated_at.desc())
            .limit(1)
        )
        row = (await session.execute(query)).mappings().first()
        if not row:
            return None
        return PlatformCredentialLifecycleSnapshot(
            id=row["id"],
            platform_connection_id=row["platform_connection_id"],
            platform=row["platform"],
            lifecycle_status=row["lifecycle_status"],
            expires_at=row.get("expires_at"),
            next_refresh_due_at=row.get("next_refresh_due_at"),
            scope=row.get("scope"),
            last_failure_class=row.get("last_failure_class"),
            last_failure_at=row.get("last_failure_at"),
            last_refresh_at=row.get("last_refresh_at"),
            revoked_at=row.get("revoked_at"),
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True)
class PlatformCredentials:
    id: UUID
    platform_connection_id: UUID
    platform: str
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    next_refresh_due_at: datetime | None
    scope: str | None
    token_type: str | None
    key_id: str
    lifecycle_status: str
    refresh_failure_count: int
    last_failure_class: str | None
    last_failure_at: datetime | None
    last_refresh_at: datetime | None
    revoked_at: datetime | None


class PlatformCredentialService:
    @staticmethod
    async def get_credentials(
        session: AsyncSession,
        *,
        tenant_id: UUID,
        connection_id: UUID,
        encryption_key: Optional[str] = None,
        allow_expired: bool = False,
    ) -> PlatformCredentials:
        query = (
            select(
                PlatformCredential.id,
                PlatformCredential.platform_connection_id,
                PlatformCredential.platform,
                PlatformCredential.expires_at,
                PlatformCredential.next_refresh_due_at,
                PlatformCredential.scope,
                PlatformCredential.token_type,
                PlatformCredential.key_id,
                PlatformCredential.lifecycle_status,
                PlatformCredential.refresh_failure_count,
                PlatformCredential.last_failure_class,
                PlatformCredential.last_failure_at,
                PlatformCredential.last_refresh_at,
                PlatformCredential.revoked_at,
                PlatformCredential.encrypted_access_token,
                PlatformCredential.encrypted_refresh_token,
            )
            .join(
                PlatformConnection,
                PlatformConnection.id == PlatformCredential.platform_connection_id,
            )
            .where(
                PlatformCredential.tenant_id == tenant_id,
                PlatformConnection.id == connection_id,
                PlatformCredential.lifecycle_status.in_(("active", "degraded")),
                PlatformCredential.revoked_at.is_(None),
            )
            .order_by(PlatformCredential.updated_at.desc())
            .limit(1)
        )
        result = await session.execute(query)
        row = result.mappings().first()
        if not row:
            raise PlatformCredentialNotFoundError()

        expires_at = row.get("expires_at")
        if not allow_expired and expires_at and expires_at <= datetime.now(timezone.utc):
            raise PlatformCredentialExpiredError()

        key_id = str(row.get("key_id"))
        if not key_id:
            raise PlatformCredentialNotFoundError()
        key = resolve_platform_encryption_key_by_id(key_id)
        access_token = await _decrypt_ciphertext_once(
            session,
            ciphertext=row.get("encrypted_access_token"),
            key=key,
        )
        refresh_token = await _decrypt_ciphertext_once(
            session,
            ciphertext=row.get("encrypted_refresh_token"),
            key=key,
        )

        if access_token is None:
            raise PlatformCredentialNotFoundError()

        return PlatformCredentials(
            id=row["id"],
            platform_connection_id=row["platform_connection_id"],
            platform=row["platform"],
            access_token=str(access_token),
            refresh_token=str(refresh_token) if refresh_token is not None else None,
            expires_at=expires_at,
            next_refresh_due_at=row.get("next_refresh_due_at"),
            scope=row.get("scope"),
            token_type=row.get("token_type"),
            key_id=key_id,
            lifecycle_status=row.get("lifecycle_status") or "active",
            refresh_failure_count=int(row.get("refresh_failure_count") or 0),
            last_failure_class=row.get("last_failure_class"),
            last_failure_at=row.get("last_failure_at"),
            last_refresh_at=row.get("last_refresh_at"),
            revoked_at=row.get("revoked_at"),
        )

    @staticmethod
    async def get_credentials_by_id(
        session: AsyncSession,
        *,
        tenant_id: UUID,
        credential_id: UUID,
        allow_expired: bool = False,
    ) -> PlatformCredentials:
        query = (
            select(
                PlatformCredential.id,
                PlatformCredential.platform_connection_id,
                PlatformCredential.platform,
                PlatformCredential.expires_at,
                PlatformCredential.next_refresh_due_at,
                PlatformCredential.scope,
                PlatformCredential.token_type,
                PlatformCredential.key_id,
                PlatformCredential.lifecycle_status,
                PlatformCredential.refresh_failure_count,
                PlatformCredential.last_failure_class,
                PlatformCredential.last_failure_at,
                PlatformCredential.last_refresh_at,
                PlatformCredential.revoked_at,
                PlatformCredential.encrypted_access_token,
                PlatformCredential.encrypted_refresh_token,
            )
            .where(
                PlatformCredential.tenant_id == tenant_id,
                PlatformCredential.id == credential_id,
                PlatformCredential.lifecycle_status.in_(("active", "degraded")),
                PlatformCredential.revoked_at.is_(None),
            )
            .limit(1)
        )
        result = await session.execute(query)
        row = result.mappings().first()
        if not row:
            raise PlatformCredentialNotFoundError()

        expires_at = row.get("expires_at")
        if not allow_expired and expires_at and _as_utc(expires_at) <= datetime.now(timezone.utc):
            raise PlatformCredentialExpiredError()

        key_id = str(row.get("key_id"))
        if not key_id:
            raise PlatformCredentialNotFoundError()
        key = resolve_platform_encryption_key_by_id(key_id)
        access_token = await _decrypt_ciphertext_once(
            session,
            ciphertext=row.get("encrypted_access_token"),
            key=key,
        )
        refresh_token = await _decrypt_ciphertext_once(
            session,
            ciphertext=row.get("encrypted_refresh_token"),
            key=key,
        )
        if access_token is None:
            raise PlatformCredentialNotFoundError()

        return PlatformCredentials(
            id=row["id"],
            platform_connection_id=row["platform_connection_id"],
            platform=row["platform"],
            access_token=str(access_token),
            refresh_token=str(refresh_token) if refresh_token is not None else None,
            expires_at=expires_at,
            next_refresh_due_at=row.get("next_refresh_due_at"),
            scope=row.get("scope"),
            token_type=row.get("token_type"),
            key_id=key_id,
            lifecycle_status=row.get("lifecycle_status") or "active",
            refresh_failure_count=int(row.get("refresh_failure_count") or 0),
            last_failure_class=row.get("last_failure_class"),
            last_failure_at=row.get("last_failure_at"),
            last_refresh_at=row.get("last_refresh_at"),
            revoked_at=row.get("revoked_at"),
        )


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


def _coerce_db_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)
