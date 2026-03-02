from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

import bcrypt
from sqlalchemy import Select, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock as clock_module
from app.db.session import set_tenant_guc_async
from app.models.auth_substrate import AuthRefreshToken
from app.security.auth import mint_internal_jwt

ACCESS_TOKEN_TTL_SECONDS = 15 * 60
REFRESH_TOKEN_TTL_DAYS = 30


@dataclass(frozen=True)
class LoginIdentity:
    user_id: UUID
    is_active: bool
    auth_provider: str
    password_hash: str | None


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    user_id: UUID
    tenant_id: UUID
    expires_in_seconds: int


def _canonicalize_login_identifier(value: str) -> str:
    return value.strip().lower()


def hash_login_identifier(identifier: str, pepper: str | None) -> str:
    canonical = _canonicalize_login_identifier(identifier)
    prefix = (pepper or "").strip()
    payload = f"{prefix}:{canonical}" if prefix else canonical
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def hash_password_for_storage(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _refresh_token_digest(refresh_token: str) -> bytes:
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest().encode("utf-8")


def hash_refresh_token_for_storage(refresh_token: str) -> str:
    if os.getenv("SKELDIR_B12_P4_STORE_PLAINTEXT") == "1":
        return refresh_token
    return bcrypt.hashpw(_refresh_token_digest(refresh_token), bcrypt.gensalt()).decode("utf-8")


def verify_refresh_token(refresh_token: str, token_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_refresh_token_digest(refresh_token), token_hash.encode("utf-8"))
    except ValueError:
        return False


def _mint_refresh_token_value(*, tenant_id: UUID, token_id: UUID) -> str:
    # Prefix carries tenant + token row id for bounded lookup without plaintext persistence.
    return f"{tenant_id}.{token_id}.{secrets.token_urlsafe(48)}"


def parse_refresh_token(refresh_token: str) -> tuple[UUID, UUID] | None:
    parts = refresh_token.split(".")
    if len(parts) != 3:
        return None
    try:
        tenant_id = UUID(parts[0])
        token_id = UUID(parts[1])
    except ValueError:
        return None
    if not parts[2]:
        return None
    return tenant_id, token_id


async def lookup_identity_by_login(
    session: AsyncSession,
    *,
    login_identifier: str,
    login_pepper: str | None,
) -> LoginIdentity | None:
    login_hash = hash_login_identifier(login_identifier, login_pepper)
    row = (
        await session.execute(
            text(
                """
                SELECT user_id, is_active, auth_provider, password_hash
                FROM auth.lookup_user_auth_by_login_hash(:login_hash)
                """
            ),
            {"login_hash": login_hash},
        )
    ).mappings().one_or_none()
    if row is None:
        return None
    return LoginIdentity(
        user_id=UUID(str(row["user_id"])),
        is_active=bool(row["is_active"]),
        auth_provider=str(row["auth_provider"]),
        password_hash=str(row["password_hash"]) if row["password_hash"] is not None else None,
    )


async def resolve_tenant_membership(
    session: AsyncSession,
    *,
    user_id: UUID,
    requested_tenant_id: UUID | None,
) -> UUID | None:
    base_query = (
        text(
            """
            SELECT tenant_id
            FROM public.tenant_memberships
            WHERE user_id = :user_id
              AND membership_status = 'active'
            ORDER BY created_at DESC
            LIMIT :limit
            """
        )
        if requested_tenant_id is None
        else text(
            """
            SELECT tenant_id
            FROM public.tenant_memberships
            WHERE user_id = :user_id
              AND tenant_id = :tenant_id
              AND membership_status = 'active'
            LIMIT 1
            """
        )
    )
    params: dict[str, object] = {"user_id": str(user_id)}
    if requested_tenant_id is None:
        params["limit"] = 2
    else:
        params["tenant_id"] = str(requested_tenant_id)

    rows = (await session.execute(base_query, params)).all()
    if requested_tenant_id is not None:
        if not rows:
            return None
        return UUID(str(rows[0][0]))
    if len(rows) != 1:
        return None
    return UUID(str(rows[0][0]))


async def _create_refresh_token_row(
    session: AsyncSession,
    *,
    user_id: UUID,
    tenant_id: UUID,
    family_id: UUID | None,
) -> tuple[AuthRefreshToken, str]:
    token_id = uuid4()
    refresh_token = _mint_refresh_token_value(tenant_id=tenant_id, token_id=token_id)
    token_row = AuthRefreshToken(
        id=token_id,
        tenant_id=tenant_id,
        user_id=user_id,
        family_id=family_id or uuid4(),
        token_hash=hash_refresh_token_for_storage(refresh_token),
        expires_at=clock_module.utcnow() + timedelta(days=REFRESH_TOKEN_TTL_DAYS),
    )
    session.add(token_row)
    await session.flush()
    return token_row, refresh_token


async def issue_login_token_pair(
    session: AsyncSession,
    *,
    user_id: UUID,
    tenant_id: UUID,
) -> TokenPair:
    await set_tenant_guc_async(session, tenant_id, local=True)
    _, refresh_token = await _create_refresh_token_row(
        session,
        user_id=user_id,
        tenant_id=tenant_id,
        family_id=None,
    )
    return TokenPair(
        access_token=mint_internal_jwt(
            tenant_id=tenant_id,
            user_id=user_id,
            expires_in_seconds=ACCESS_TOKEN_TTL_SECONDS,
        ),
        refresh_token=refresh_token,
        user_id=user_id,
        tenant_id=tenant_id,
        expires_in_seconds=ACCESS_TOKEN_TTL_SECONDS,
    )


async def rotate_refresh_token(
    session: AsyncSession,
    *,
    refresh_token: str,
    requested_tenant_id: UUID | None,
) -> TokenPair | None:
    parsed = parse_refresh_token(refresh_token)
    if parsed is None:
        return None
    token_tenant_id, token_id = parsed
    if requested_tenant_id is not None and requested_tenant_id != token_tenant_id:
        return None

    await set_tenant_guc_async(session, token_tenant_id, local=True)
    query: Select[tuple[AuthRefreshToken]] = (
        select(AuthRefreshToken)
        .where(AuthRefreshToken.id == token_id)
        .with_for_update()
    )
    token_row = (await session.execute(query)).scalar_one_or_none()
    if token_row is None:
        return None

    now = clock_module.utcnow()
    if (
        token_row.tenant_id != token_tenant_id
        or token_row.revoked_at is not None
        or token_row.rotated_at is not None
        or token_row.expires_at <= now
        or not verify_refresh_token(refresh_token, token_row.token_hash)
    ):
        return None

    new_row, new_refresh = await _create_refresh_token_row(
        session,
        user_id=token_row.user_id,
        tenant_id=token_row.tenant_id,
        family_id=token_row.family_id,
    )
    token_row.last_used_at = now
    if os.getenv("SKELDIR_B12_P4_DISABLE_ROTATION_UPDATE") != "1":
        token_row.rotated_at = now
        token_row.replaced_by_id = new_row.id
    await session.flush()

    return TokenPair(
        access_token=mint_internal_jwt(
            tenant_id=token_row.tenant_id,
            user_id=token_row.user_id,
            expires_in_seconds=ACCESS_TOKEN_TTL_SECONDS,
        ),
        refresh_token=new_refresh,
        user_id=token_row.user_id,
        tenant_id=token_row.tenant_id,
        expires_in_seconds=ACCESS_TOKEN_TTL_SECONDS,
    )
