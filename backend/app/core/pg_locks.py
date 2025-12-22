"""
PostgreSQL advisory lock helpers for task serialization.

B0.5.4.0: Implements G12 remediation - prevents duplicate refresh execution
via pg_advisory_lock primitive.
"""
import hashlib
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger(__name__)


def _lock_key_from_string(s: str) -> int:
    """
    Convert string to deterministic 32-bit integer for pg_advisory_lock.

    Uses first 8 hex chars of SHA256 hash, converted to signed int32.
    Postgres advisory locks require int32 or (int32, int32) keys.

    Args:
        s: String to hash (e.g., "matview_refresh:mv_test:GLOBAL")

    Returns:
        Signed 32-bit integer lock key (-2^31 to 2^31-1)
    """
    h = hashlib.sha256(s.encode()).hexdigest()[:8]
    # Convert to signed int32 (-2^31 to 2^31-1)
    unsigned = int(h, 16)
    if unsigned >= 2**31:
        return unsigned - 2**32
    return unsigned


async def try_acquire_refresh_lock(
    conn: AsyncConnection,
    view_name: str,
    tenant_id: Optional[UUID] = None
) -> bool:
    """
    Try to acquire advisory lock for matview refresh.

    Lock key is deterministic based on (view_name, tenant_id).
    Returns True if lock acquired, False if already held.

    This function is NON-BLOCKING. If lock is held by another session,
    it immediately returns False (does not wait).

    Args:
        conn: SQLAlchemy async connection
        view_name: Name of materialized view
        tenant_id: Optional tenant UUID (None for global refresh)

    Returns:
        True if lock acquired, False if already locked by another session

    Example:
        async with engine.begin() as conn:
            if await try_acquire_refresh_lock(conn, "mv_test"):
                # Refresh the view
                await conn.execute(...)
                await release_refresh_lock(conn, "mv_test")
            else:
                logger.info("Skipped - already refreshing")
    """
    # Build deterministic lock key
    tenant_str = str(tenant_id) if tenant_id else "GLOBAL"
    lock_str = f"matview_refresh:{view_name}:{tenant_str}"
    lock_key = _lock_key_from_string(lock_str)

    logger.debug(
        "trying_to_acquire_refresh_lock",
        extra={
            "view_name": view_name,
            "tenant_id": tenant_str,
            "lock_key": lock_key,
            "lock_string": lock_str
        }
    )

    # Try to acquire lock (non-blocking)
    # pg_try_advisory_lock returns true if lock acquired, false if already held
    result = await conn.execute(
        text("SELECT pg_try_advisory_lock(:lock_key)"),
        {"lock_key": lock_key}
    )
    acquired = result.scalar()

    if acquired:
        logger.info(
            "refresh_lock_acquired",
            extra={
                "view_name": view_name,
                "tenant_id": tenant_str,
                "lock_key": lock_key
            }
        )
    else:
        logger.info(
            "refresh_lock_already_held",
            extra={
                "view_name": view_name,
                "tenant_id": tenant_str,
                "lock_key": lock_key,
                "action": "skip_refresh"
            }
        )

    return bool(acquired)


async def release_refresh_lock(
    conn: AsyncConnection,
    view_name: str,
    tenant_id: Optional[UUID] = None
) -> None:
    """
    Release advisory lock for matview refresh.

    IMPORTANT: Only the session that acquired the lock can release it.
    Calling this without holding the lock will return False but not error.

    Args:
        conn: SQLAlchemy async connection (must be same session that acquired lock)
        view_name: Name of materialized view
        tenant_id: Optional tenant UUID (None for global refresh)

    Raises:
        No exceptions - if lock not held, unlock returns false but doesn't error
    """
    tenant_str = str(tenant_id) if tenant_id else "GLOBAL"
    lock_str = f"matview_refresh:{view_name}:{tenant_str}"
    lock_key = _lock_key_from_string(lock_str)

    # Release the lock
    # pg_advisory_unlock returns true if lock was held and released
    # Returns false if lock was not held by this session
    result = await conn.execute(
        text("SELECT pg_advisory_unlock(:lock_key)"),
        {"lock_key": lock_key}
    )
    released = result.scalar()

    if released:
        logger.info(
            "refresh_lock_released",
            extra={
                "view_name": view_name,
                "tenant_id": tenant_str,
                "lock_key": lock_key
            }
        )
    else:
        logger.warning(
            "refresh_lock_not_held_on_release",
            extra={
                "view_name": view_name,
                "tenant_id": tenant_str,
                "lock_key": lock_key,
                "note": "Lock was not held by this session"
            }
        )
