"""
PostgreSQL advisory lock helpers for refresh serialization.

B0.5.4.2: Uses xact-scoped advisory locks to bind lock lifetime to the
transaction boundary and avoid crash-sticky session locks.
"""
from dataclasses import dataclass
import hashlib
import logging
import struct
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RefreshLockKey:
    view_key: int
    tenant_key: int
    view_name: str
    tenant_token: str

    def as_dict(self) -> dict:
        return {
            "view_key": self.view_key,
            "tenant_key": self.tenant_key,
            "view_name": self.view_name,
            "tenant_token": self.tenant_token,
        }


def _int32_from_hash(value: str) -> int:
    """
    Convert a string to a deterministic signed int32.

    Uses SHA256 digest and interprets the first 4 bytes as a signed int32.
    """
    digest = hashlib.sha256(value.encode()).digest()
    return struct.unpack("!i", digest[:4])[0]


def build_refresh_lock_key(view_name: str, tenant_id: Optional[UUID]) -> RefreshLockKey:
    """
    Build deterministic advisory lock keys for refresh serialization.

    Keys are derived separately from view_name and tenant_id to reduce
    collision coupling across dimensions.
    """
    tenant_token = str(tenant_id) if tenant_id else "GLOBAL"
    view_key = _int32_from_hash(f"view:{view_name}")
    tenant_key = _int32_from_hash(f"tenant:{tenant_token}")
    return RefreshLockKey(
        view_key=view_key,
        tenant_key=tenant_key,
        view_name=view_name,
        tenant_token=tenant_token,
    )


async def try_acquire_refresh_xact_lock(
    conn: AsyncConnection,
    view_name: str,
    tenant_id: Optional[UUID] = None,
) -> tuple[bool, RefreshLockKey]:
    """
    Try to acquire an xact-scoped advisory lock for matview refresh.

    Returns (acquired, lock_key). Lock is released automatically when the
    transaction ends; no manual unlock is required.
    """
    lock_key = build_refresh_lock_key(view_name, tenant_id)
    logger.debug(
        "trying_to_acquire_refresh_xact_lock",
        extra=lock_key.as_dict(),
    )

    result = await conn.execute(
        text("SELECT pg_try_advisory_xact_lock(:view_key, :tenant_key)"),
        {"view_key": lock_key.view_key, "tenant_key": lock_key.tenant_key},
    )
    acquired = bool(result.scalar())
    if acquired:
        logger.info("refresh_xact_lock_acquired", extra=lock_key.as_dict())
    else:
        logger.info(
            "refresh_xact_lock_already_held",
            extra={**lock_key.as_dict(), "action": "skip_refresh"},
        )
    return acquired, lock_key
