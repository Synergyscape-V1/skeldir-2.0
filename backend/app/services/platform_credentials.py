"""
Service layer for platform credentials (encrypted tokens).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from app.models.platform_connection import PlatformConnection
from app.models.platform_credential import PlatformCredential
from app.core.secrets import resolve_platform_encryption_key_by_id
from app.services.platform_connections import PlatformConnectionNotFoundError


class PlatformCredentialExpiredError(RuntimeError):
    pass


class PlatformCredentialNotFoundError(RuntimeError):
    pass


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
            scope=scope,
            token_type=token_type,
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
                "scope": scope,
                "token_type": token_type,
                "key_id": key_id,
                "updated_at": func.now(),
            },
        ).returning(
            PlatformCredential.id,
            PlatformCredential.expires_at,
            PlatformCredential.updated_at,
        )
        result = await session.execute(stmt)
        row = result.mappings().first()
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


@dataclass(frozen=True)
class PlatformCredentials:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scope: str | None
    token_type: str | None
    key_id: str


class PlatformCredentialService:
    @staticmethod
    async def get_credentials(
        session: AsyncSession,
        *,
        tenant_id: UUID,
        connection_id: UUID,
        encryption_key: Optional[str] = None,
    ) -> PlatformCredentials:
        query = (
            select(
                PlatformCredential.expires_at,
                PlatformCredential.scope,
                PlatformCredential.token_type,
                PlatformCredential.key_id,
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
            access_token=str(access_token),
            refresh_token=str(refresh_token) if refresh_token is not None else None,
            expires_at=expires_at,
            scope=row.get("scope"),
            token_type=row.get("token_type"),
            key_id=key_id,
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
