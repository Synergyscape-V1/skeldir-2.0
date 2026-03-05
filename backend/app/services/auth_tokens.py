from __future__ import annotations

import hashlib
import logging
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
from app.security.rbac import normalize_role_claims, primary_role_from_claims

ACCESS_TOKEN_TTL_SECONDS = 15 * 60
REFRESH_TOKEN_TTL_DAYS = 30
logger = logging.getLogger(__name__)
_DUMMY_REFRESH_MISS_DIGEST = hashlib.sha256(b"skeldir-refresh-selector-miss").hexdigest().encode("utf-8")
_DUMMY_REFRESH_MISS_HASH = bcrypt.hashpw(_DUMMY_REFRESH_MISS_DIGEST, bcrypt.gensalt())


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


def _refresh_secret_digest(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest().encode("utf-8")


def _refresh_blob_digest(refresh_token: str) -> bytes:
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest().encode("utf-8")


def hash_refresh_token_for_storage(*, secret: str, refresh_token: str) -> str:
    if os.getenv("SKELDIR_B12_P4_STORE_PLAINTEXT") == "1":
        return refresh_token
    digest = (
        _refresh_blob_digest(refresh_token)
        if os.getenv("SKELDIR_B12_P4_HASH_BLOB") == "1"
        else _refresh_secret_digest(secret)
    )
    return bcrypt.hashpw(digest, bcrypt.gensalt()).decode("utf-8")


def verify_refresh_token(*, secret: str, refresh_token: str, token_hash: str) -> bool:
    digest = (
        _refresh_blob_digest(refresh_token)
        if os.getenv("SKELDIR_B12_P4_HASH_BLOB") == "1"
        else _refresh_secret_digest(secret)
    )
    try:
        return bcrypt.checkpw(digest, token_hash.encode("utf-8"))
    except ValueError:
        return False


def _verify_dummy_refresh_miss_cost() -> None:
    # Constant-cost miss path prevents selector enumeration via latency.
    bcrypt.checkpw(_DUMMY_REFRESH_MISS_DIGEST, _DUMMY_REFRESH_MISS_HASH)


def _mint_refresh_token_value(*, tenant_id: UUID, token_id: UUID, secret: str) -> str:
    # Prefix carries tenant + token row id for bounded lookup without plaintext persistence.
    return f"{tenant_id}.{token_id}.{secret}"


def parse_refresh_token(refresh_token: str) -> tuple[UUID, UUID, str] | None:
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
    return tenant_id, token_id, parts[2]


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
    requested_tenant_id: UUID,
) -> UUID | None:
    await set_tenant_guc_async(session, requested_tenant_id, local=True)
    base_query = text(
        """
        SELECT tenant_id
        FROM public.tenant_memberships
        WHERE user_id = :user_id
          AND tenant_id = :tenant_id
          AND membership_status = 'active'
        LIMIT 1
        """
    )
    params: dict[str, object] = {
        "user_id": str(user_id),
        "tenant_id": str(requested_tenant_id),
    }

    rows = (await session.execute(base_query, params)).all()
    if not rows:
        return None
    return UUID(str(rows[0][0]))


async def resolve_membership_roles(
    session: AsyncSession,
    *,
    user_id: UUID,
    tenant_id: UUID,
) -> list[str]:
    await set_tenant_guc_async(session, tenant_id, local=True)
    rows = (
        await session.execute(
            text(
                """
                SELECT DISTINCT tmr.role_code
                FROM public.tenant_membership_roles tmr
                JOIN public.tenant_memberships tm
                  ON tm.id = tmr.membership_id
                 AND tm.tenant_id = tmr.tenant_id
                WHERE tm.tenant_id = :tenant_id
                  AND tm.user_id = :user_id
                  AND tm.membership_status = 'active'
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
            },
        )
    ).all()
    claims = normalize_role_claims(row[0] for row in rows)
    if claims:
        return claims
    return ["viewer"]


async def assign_membership_primary_role(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    role_code: str,
) -> bool:
    normalized_role = role_code.strip().lower()
    if normalized_role not in {"admin", "manager", "viewer"}:
        raise ValueError("Unsupported role code")

    await set_tenant_guc_async(session, tenant_id, local=True)
    role_exists = (
        await session.execute(
            text("SELECT 1 FROM public.roles WHERE code = :code LIMIT 1"),
            {"code": normalized_role},
        )
    ).scalar_one_or_none()
    if role_exists is None:
        raise ValueError("Role code not present in catalog")

    membership_row = (
        await session.execute(
            text(
                """
                SELECT id
                FROM public.tenant_memberships
                WHERE tenant_id = :tenant_id
                  AND user_id = :user_id
                  AND membership_status = 'active'
                LIMIT 1
                FOR UPDATE
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
            },
        )
    ).mappings().one_or_none()
    if membership_row is None:
        raise ValueError("Active tenant membership not found")
    membership_id = str(membership_row["id"])

    existing_rows = (
        await session.execute(
            text(
                """
                SELECT role_code
                FROM public.tenant_membership_roles
                WHERE tenant_id = :tenant_id
                  AND membership_id = :membership_id
                FOR UPDATE
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "membership_id": membership_id,
            },
        )
    ).all()
    existing = {str(row[0]).strip().lower() for row in existing_rows}
    changed = existing != {normalized_role}
    if not changed:
        return False

    await session.execute(
        text(
            """
            DELETE FROM public.tenant_membership_roles
            WHERE tenant_id = :tenant_id
              AND membership_id = :membership_id
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "membership_id": membership_id,
        },
    )
    await session.execute(
        text(
            """
            INSERT INTO public.tenant_membership_roles (
                id,
                tenant_id,
                membership_id,
                role_code,
                created_at,
                updated_at
            ) VALUES (
                gen_random_uuid(),
                :tenant_id,
                :membership_id,
                :role_code,
                now(),
                now()
            )
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "membership_id": membership_id,
            "role_code": normalized_role,
        },
    )
    await session.execute(
        text(
            """
            UPDATE public.tenant_memberships
            SET updated_at = now()
            WHERE id = :membership_id
              AND tenant_id = :tenant_id
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "membership_id": membership_id,
        },
    )
    return True


async def revoke_refresh_family(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    family_id: UUID,
    reason: str,
    trigger_token_id: UUID,
) -> None:
    now = clock_module.utcnow()
    where_clauses = [
        AuthRefreshToken.tenant_id == tenant_id,
        AuthRefreshToken.user_id == user_id,
    ]
    if os.getenv("SKELDIR_B12_P4_REVOKE_ALL_FAMILIES") != "1":
        where_clauses.append(AuthRefreshToken.family_id == family_id)
    rows = (await session.execute(select(AuthRefreshToken).where(*where_clauses).with_for_update())).scalars().all()
    for row in rows:
        if row.revoked_at is None:
            row.revoked_at = now
    await session.flush()
    logger.warning(
        "auth_refresh_family_revoked_on_reuse",
        extra={
            "event_type": "auth_security",
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "family_id": str(family_id),
            "trigger_token_id": str(trigger_token_id),
            "reason": reason,
            "family_row_count": len(rows),
        },
    )


async def _create_refresh_token_row(
    session: AsyncSession,
    *,
    user_id: UUID,
    tenant_id: UUID,
    family_id: UUID | None,
) -> tuple[AuthRefreshToken, str]:
    token_id = uuid4()
    secret = secrets.token_urlsafe(48)
    refresh_token = _mint_refresh_token_value(tenant_id=tenant_id, token_id=token_id, secret=secret)
    token_row = AuthRefreshToken(
        id=token_id,
        tenant_id=tenant_id,
        user_id=user_id,
        family_id=family_id or uuid4(),
        token_hash=hash_refresh_token_for_storage(secret=secret, refresh_token=refresh_token),
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
    role_claims = await resolve_membership_roles(
        session,
        user_id=user_id,
        tenant_id=tenant_id,
    )
    return TokenPair(
        access_token=mint_internal_jwt(
            tenant_id=tenant_id,
            user_id=user_id,
            expires_in_seconds=ACCESS_TOKEN_TTL_SECONDS,
            additional_claims={
                "role": primary_role_from_claims(role_claims),
                "roles": role_claims,
            },
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
    token_tenant_id, token_id, secret = parsed
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
        if os.getenv("SKELDIR_B12_P4_DISABLE_MISS_DUMMY_BCRYPT") != "1":
            _verify_dummy_refresh_miss_cost()
        return None

    now = clock_module.utcnow()
    if token_row.tenant_id != token_tenant_id:
        return None
    if not verify_refresh_token(secret=secret, refresh_token=refresh_token, token_hash=token_row.token_hash):
        return None
    if token_row.rotated_at is not None or token_row.revoked_at is not None:
        if os.getenv("SKELDIR_B12_P4_DISABLE_FAMILY_REVOKE_ON_REUSE") != "1":
            await revoke_refresh_family(
                session,
                tenant_id=token_row.tenant_id,
                user_id=token_row.user_id,
                family_id=token_row.family_id,
                reason="refresh_token_reuse_detected",
                trigger_token_id=token_row.id,
            )
        return None
    if (
        token_row.expires_at <= now
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
    if os.getenv("SKELDIR_B12_P6_NEGATIVE_COPY_ROLE_FORWARD") == "1":
        # Negative control: intentionally bypass DB role truth to prove EG6.R1 would fail.
        role_claims = ["admin"]
    else:
        role_claims = await resolve_membership_roles(
            session,
            user_id=token_row.user_id,
            tenant_id=token_row.tenant_id,
        )

    return TokenPair(
        access_token=mint_internal_jwt(
            tenant_id=token_row.tenant_id,
            user_id=token_row.user_id,
            expires_in_seconds=ACCESS_TOKEN_TTL_SECONDS,
            additional_claims={
                "role": primary_role_from_claims(role_claims),
                "roles": role_claims,
            },
        ),
        refresh_token=new_refresh,
        user_id=token_row.user_id,
        tenant_id=token_row.tenant_id,
        expires_in_seconds=ACCESS_TOKEN_TTL_SECONDS,
    )
