from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import set_tenant_guc_async
from app.security.revocation_runtime import (
    REVOCATION_NOTIFY_CHANNEL_CUTOFF,
    REVOCATION_NOTIFY_CHANNEL_DENYLIST,
)


@dataclass(frozen=True)
class RevocationEvaluation:
    is_denylisted: bool
    is_kill_switched: bool
    denylist_expires_at: datetime | None
    tokens_invalid_before: datetime | None

    @property
    def is_revoked(self) -> bool:
        return self.is_denylisted or self.is_kill_switched


async def evaluate_access_token_revocation(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    jti: UUID,
    issued_at_epoch: int,
) -> RevocationEvaluation:
    await set_tenant_guc_async(session, tenant_id, local=True)
    row = (
        await session.execute(
            text(
                """
                SELECT
                    (
                        SELECT d.expires_at
                        FROM public.auth_access_token_denylist d
                        WHERE d.tenant_id = :tenant_id
                          AND d.user_id = :user_id
                          AND d.jti = :jti
                        LIMIT 1
                    ) AS denylist_expires_at,
                    COALESCE(
                        (
                            SELECT c.tokens_invalid_before
                            FROM public.auth_user_token_cutoffs c
                            WHERE c.tenant_id = :tenant_id
                              AND c.user_id = :user_id
                            LIMIT 1
                        ),
                        NULL
                    ) AS tokens_invalid_before
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
                "jti": str(jti),
                "issued_at_epoch": int(issued_at_epoch),
            },
        )
    ).mappings().one()
    denylist_expires_at = row["denylist_expires_at"]
    tokens_invalid_before = row["tokens_invalid_before"]
    is_denylisted = denylist_expires_at is not None
    is_kill_switched = False
    if tokens_invalid_before is not None:
        is_kill_switched = datetime.fromtimestamp(
            int(issued_at_epoch),
            tz=timezone.utc,
        ) <= tokens_invalid_before.astimezone(timezone.utc)
    return RevocationEvaluation(
        is_denylisted=is_denylisted,
        is_kill_switched=is_kill_switched,
        denylist_expires_at=denylist_expires_at,
        tokens_invalid_before=tokens_invalid_before,
    )


async def denylist_access_token(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    jti: UUID,
    expires_at: datetime,
    reason: str = "logout",
) -> None:
    await set_tenant_guc_async(session, tenant_id, local=True)
    await session.execute(
        text(
            """
            INSERT INTO public.auth_access_token_denylist (
                tenant_id,
                user_id,
                jti,
                expires_at,
                reason
            ) VALUES (
                :tenant_id,
                :user_id,
                :jti,
                :expires_at,
                :reason
            )
            ON CONFLICT (tenant_id, user_id, jti)
            DO UPDATE SET
                revoked_at = now(),
                expires_at = GREATEST(
                    public.auth_access_token_denylist.expires_at,
                    EXCLUDED.expires_at
                ),
                reason = EXCLUDED.reason
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "jti": str(jti),
            "expires_at": expires_at.astimezone(timezone.utc),
            "reason": reason,
        },
    )
    payload = json.dumps(
        {
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "jti": str(jti),
            "expires_at": expires_at.astimezone(timezone.utc).isoformat(),
        },
        separators=(",", ":"),
    )
    await session.execute(
        text("SELECT pg_notify(:channel, :payload)"),
        {
            "channel": REVOCATION_NOTIFY_CHANNEL_DENYLIST,
            "payload": payload,
        },
    )


async def upsert_tokens_invalid_before(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    invalid_before: datetime,
    updated_by_user_id: UUID | None = None,
) -> None:
    await set_tenant_guc_async(session, tenant_id, local=True)
    await session.execute(
        text(
            """
            INSERT INTO public.auth_user_token_cutoffs (
                tenant_id,
                user_id,
                tokens_invalid_before,
                updated_by_user_id
            ) VALUES (
                :tenant_id,
                :user_id,
                :tokens_invalid_before,
                :updated_by_user_id
            )
            ON CONFLICT (tenant_id, user_id)
            DO UPDATE SET
                tokens_invalid_before = GREATEST(
                    public.auth_user_token_cutoffs.tokens_invalid_before,
                    EXCLUDED.tokens_invalid_before
                ),
                updated_at = now(),
                updated_by_user_id = EXCLUDED.updated_by_user_id
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "tokens_invalid_before": invalid_before.astimezone(timezone.utc),
            "updated_by_user_id": str(updated_by_user_id) if updated_by_user_id is not None else None,
        },
    )
    payload = json.dumps(
        {
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "tokens_invalid_before": invalid_before.astimezone(timezone.utc).isoformat(),
        },
        separators=(",", ":"),
    )
    await session.execute(
        text("SELECT pg_notify(:channel, :payload)"),
        {
            "channel": REVOCATION_NOTIFY_CHANNEL_CUTOFF,
            "payload": payload,
        },
    )
