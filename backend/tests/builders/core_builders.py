"""
Approved builder functions for core tables used by the schema contract guard.

Each builder returns a mapping containing at minimum:
  - id: primary identifier for the inserted row
  - tenant_id: owning tenant (for RLS context)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, Set
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.session import engine


async def _required_columns(table_name: str) -> Set[str]:
    """Return required columns (NOT NULL and no default, excluding identity) for a table."""
    query = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = :table_name
          AND is_nullable = 'NO'
          AND column_default IS NULL
          AND (is_identity IS NULL OR is_identity = 'NO')
        """
    )
    async with engine.begin() as conn:
        result = await conn.execute(query, {"table_name": table_name})
    return set(result.scalars().all())


async def _table_columns(table_name: str) -> Set[str]:
    """Return all column names for a table."""
    query = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = :table_name
        """
    )
    async with engine.begin() as conn:
        result = await conn.execute(query, {"table_name": table_name})
    return set(result.scalars().all())


async def _ensure_channel_code(code: str = "direct") -> None:
    """Ensure a channel_taxonomy row exists with required fields populated."""
    required = await _required_columns("channel_taxonomy")
    columns = await _table_columns("channel_taxonomy")
    insert_cols = ["code"]
    params: Dict[str, object] = {"code": code}

    # Populate any required non-null columns with deterministic defaults
    now = datetime.now(timezone.utc)
    defaults = {
        "family": "organic",
        "name": code,
        "display_name": code,
        "description": f"{code} channel",
        "created_at": now,
        "updated_at": now,
        "is_active": True,
        "is_paid": False,
    }
    for col in required:
        if col == "code":
            continue
        params[col] = defaults.get(col, defaults.get("name", code))
        insert_cols.append(col)

    values = ", ".join(f":{col}" for col in insert_cols)
    channel_sql = text(
        f"INSERT INTO channel_taxonomy ({', '.join(insert_cols)}) "
        f"VALUES ({values}) ON CONFLICT (code) DO NOTHING"
    )
    async with engine.begin() as conn:
        await conn.execute(channel_sql, params)


async def build_tenant(name: str | None = None) -> Dict[str, UUID]:
    """Create a tenant row satisfying required columns."""
    tenant_id = uuid4()
    required = await _required_columns("tenants")
    insert_cols = ["id", "name"]
    params = {
        "id": str(tenant_id),
        "name": name or f"Test Tenant {str(tenant_id)[:8]}",
        "api_key_hash": f"hash_{tenant_id.hex[:16]}",
        "notification_email": f"{tenant_id.hex[:8]}@test.invalid",
        "shopify_webhook_secret": "test_secret",
    }
    if "api_key_hash" in required:
        insert_cols.append("api_key_hash")
    if "notification_email" in required:
        insert_cols.append("notification_email")
    # Optional but tolerated required additions
    if "shopify_webhook_secret" in required:
        insert_cols.append("shopify_webhook_secret")

    values_clause = ", ".join(f":{col}" for col in insert_cols)
    sql = text(
        # RAW_SQL_ALLOWLIST: approved builder insert into tenants
        f"INSERT INTO tenants ({', '.join(insert_cols)}) VALUES ({values_clause})"
    )
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_id)},
            )
            await conn.execute(sql, params)
    except IntegrityError as exc:
        raise RuntimeError(
            f"Tenant builder failed. Required columns: {sorted(required)}"
        ) from exc

    return {"id": tenant_id, "tenant_id": tenant_id}


async def build_attribution_event(
    tenant_id: UUID | None = None, idempotency_key: str | None = None
) -> Dict[str, UUID]:
    """Create an attribution_events row for the given tenant (or a new one)."""
    if tenant_id is None:
        tenant_result = await build_tenant()
        tenant_id = tenant_result["tenant_id"]
    required = await _required_columns("attribution_events")
    columns = await _table_columns("attribution_events")
    event_id = uuid4()
    session_id = uuid4()
    now = datetime.now(timezone.utc)
    payload = {
        "id": str(event_id),
        "tenant_id": str(tenant_id),
        "session_id": str(session_id),
        "idempotency_key": idempotency_key or f"idemp-{event_id.hex[:12]}",
        "event_type": "click",
        "channel": "direct",
        "channel_code": "direct",
        "occurred_at": now,
        "event_timestamp": now,
        "raw_payload": json.dumps({"source": "test", "version": 1}),
    }

    insert_cols = []
    for col in required:
        if col not in payload:
            raise RuntimeError(
                f"Missing payload value for required attribution_events column '{col}'"
            )
        insert_cols.append(col)
    if "id" in columns and "id" not in insert_cols:
        insert_cols.insert(0, "id")
        payload["id"] = str(event_id)

    placeholders = ", ".join(f":{col}" for col in insert_cols)
    sql = text(
        # RAW_SQL_ALLOWLIST: approved builder insert into attribution_events
        f"INSERT INTO attribution_events ({', '.join(insert_cols)}) VALUES ({placeholders})"
    )
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_id)},
            )
            await conn.execute(sql, payload)
    except IntegrityError as exc:
        raise RuntimeError(
            f"Attribution event builder failed. Required columns: {sorted(required)}"
        ) from exc

    return {"id": event_id, "tenant_id": tenant_id}


async def build_attribution_allocation(
    tenant_id: UUID | None = None,
    event_id: UUID | None = None,
) -> Dict[str, UUID]:
    """Create an attribution_allocations row; will create tenant/event as needed."""
    if tenant_id is None:
        tenant_result = await build_tenant()
        tenant_id = tenant_result["tenant_id"]
    if event_id is None:
        event_result = await build_attribution_event(tenant_id=tenant_id)
        event_id = event_result["id"]

    required = await _required_columns("attribution_allocations")
    columns = await _table_columns("attribution_allocations")

    # Ensure channel_taxonomy has the referenced code
    await _ensure_channel_code("direct")

    allocation_id = uuid4()
    payload = {
        "id": str(allocation_id),
        "tenant_id": str(tenant_id),
        "event_id": str(event_id),
        "channel_code": "direct",
        "allocated_revenue_cents": 0,
        "model_version": "v1",
        "model_type": "deterministic",
        "allocation_ratio": 0.5,
        "confidence_score": 0.5,
    }

    insert_cols = []
    for col in required:
        if col not in payload:
            raise RuntimeError(
                f"Missing payload value for required attribution_allocations column '{col}'"
            )
        insert_cols.append(col)
    if "id" in columns and "id" not in insert_cols:
        insert_cols.insert(0, "id")
        payload["id"] = str(allocation_id)

    placeholders = ", ".join(f":{col}" for col in insert_cols)
    sql = text(
        # RAW_SQL_ALLOWLIST: approved builder insert into attribution_allocations
        f"INSERT INTO attribution_allocations ({', '.join(insert_cols)}) "
        f"VALUES ({placeholders})"
    )
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_id)},
            )
            await conn.execute(sql, payload)
    except IntegrityError as exc:
        raise RuntimeError(
            f"Attribution allocation builder failed. Required columns: {sorted(required)}"
        ) from exc

    return {"id": allocation_id, "tenant_id": tenant_id}


async def build_revenue_ledger(tenant_id: UUID | None = None) -> Dict[str, UUID]:
    """Create a revenue_ledger row for the given tenant (or a new one)."""
    if tenant_id is None:
        tenant_result = await build_tenant()
        tenant_id = tenant_result["tenant_id"]

    allocation_result = await build_attribution_allocation(tenant_id=tenant_id)
    allocation_id = allocation_result["id"]

    required = await _required_columns("revenue_ledger")
    columns = await _table_columns("revenue_ledger")

    ledger_id = uuid4()
    now = datetime.now(timezone.utc)
    payload = {
        "id": str(ledger_id),
        "tenant_id": str(tenant_id),
        "allocation_id": str(allocation_id),
        "transaction_id": f"txn-{ledger_id.hex[:12]}",
        "state": "authorized",
        "amount_cents": 100,
        "currency": "USD",
        "verification_source": "test",
        "verification_timestamp": now,
    }

    insert_cols = []
    for col in required:
        if col not in payload:
            raise RuntimeError(
                f"Missing payload value for required revenue_ledger column '{col}'"
            )
        insert_cols.append(col)
    if "id" in columns and "id" not in insert_cols:
        insert_cols.insert(0, "id")
        payload["id"] = str(ledger_id)

    placeholders = ", ".join(f":{col}" for col in insert_cols)
    sql = text(
        # RAW_SQL_ALLOWLIST: approved builder insert into revenue_ledger
        f"INSERT INTO revenue_ledger ({', '.join(insert_cols)}) "
        f"VALUES ({placeholders})"
    )
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_id)},
            )
            await conn.execute(sql, payload)
    except IntegrityError as exc:
        raise RuntimeError(
            f"Revenue ledger builder failed. Required columns: {sorted(required)}"
        ) from exc

    return {"id": ledger_id, "tenant_id": tenant_id}


async def build_platform_connection(
    *,
    tenant_id: UUID | None = None,
    platform: str = "stripe",
    platform_account_id: str = "acct_test",
    status: str = "active",
    metadata: dict | None = None,
) -> Dict[str, UUID]:
    """Create a platform_connections row for the given tenant (or a new one)."""
    if tenant_id is None:
        tenant_result = await build_tenant()
        tenant_id = tenant_result["tenant_id"]

    required = await _required_columns("platform_connections")
    columns = await _table_columns("platform_connections")
    connection_id = uuid4()
    now = datetime.now(timezone.utc)
    payload = {
        "id": str(connection_id),
        "tenant_id": str(tenant_id),
        "platform": platform,
        "platform_account_id": platform_account_id,
        "status": status,
        "connection_metadata": json.dumps(metadata) if metadata is not None else None,
        "created_at": now,
        "updated_at": now,
    }

    insert_cols = []
    for col in required:
        if col not in payload:
            raise RuntimeError(
                f"Missing payload value for required platform_connections column '{col}'"
            )
        insert_cols.append(col)
    if "id" in columns and "id" not in insert_cols:
        insert_cols.insert(0, "id")
    if "connection_metadata" in columns and "connection_metadata" not in insert_cols:
        insert_cols.append("connection_metadata")
    if "created_at" in columns and "created_at" not in insert_cols:
        insert_cols.append("created_at")
    if "updated_at" in columns and "updated_at" not in insert_cols:
        insert_cols.append("updated_at")

    placeholders = ", ".join(f":{col}" for col in insert_cols)
    sql = text(
        # RAW_SQL_ALLOWLIST: approved builder insert into platform_connections
        f"INSERT INTO platform_connections ({', '.join(insert_cols)}) "
        f"VALUES ({placeholders})"
    )
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_id)},
            )
            await conn.execute(sql, payload)
    except IntegrityError as exc:
        raise RuntimeError(
            f"Platform connection builder failed. Required columns: {sorted(required)}"
        ) from exc

    return {"id": connection_id, "tenant_id": tenant_id}


async def build_platform_credentials(
    *,
    tenant_id: UUID,
    platform: str = "stripe",
    platform_connection_id: UUID,
    access_token: str = "test-access-token",
    refresh_token: str | None = None,
    expires_at: datetime | None = None,
    scope: str | None = None,
    token_type: str | None = None,
    key_id: str = "test-key",
    encryption_key: str = "test-platform-key",
) -> Dict[str, UUID]:
    """Create a platform_credentials row for the given connection."""
    columns = await _table_columns("platform_credentials")
    credential_id = uuid4()
    now = datetime.now(timezone.utc)

    insert_cols: list[str] = []
    value_exprs: list[str] = []
    params: Dict[str, object] = {
        "id": str(credential_id),
        "tenant_id": str(tenant_id),
        "platform_connection_id": str(platform_connection_id),
        "platform": platform,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
        "scope": scope,
        "token_type": token_type,
        "key_id": key_id,
        "created_at": now,
        "updated_at": now,
        "encryption_key": encryption_key,
    }

    def add(col: str, expr: str) -> None:
        if col in columns:
            insert_cols.append(col)
            value_exprs.append(expr)

    add("id", ":id")
    add("tenant_id", ":tenant_id")
    add("platform_connection_id", ":platform_connection_id")
    add("platform", ":platform")
    add(
        "encrypted_access_token",
        "pgp_sym_encrypt(CAST(:access_token AS text), :encryption_key)",
    )
    add(
        "encrypted_refresh_token",
        "CASE WHEN CAST(:refresh_token AS text) IS NULL THEN NULL::bytea "
        "ELSE pgp_sym_encrypt(CAST(:refresh_token AS text), :encryption_key) END",
    )
    add("expires_at", ":expires_at")
    add("scope", ":scope")
    add("token_type", ":token_type")
    add("key_id", ":key_id")
    add("created_at", ":created_at")
    add("updated_at", ":updated_at")

    sql = text(
        # RAW_SQL_ALLOWLIST: approved builder insert into platform_credentials
        f"INSERT INTO platform_credentials ({', '.join(insert_cols)}) "
        f"VALUES ({', '.join(value_exprs)})"
    )
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_id)},
            )
            await conn.execute(sql, params)
    except IntegrityError as exc:
        raise RuntimeError("Platform credential builder failed.") from exc

    return {"id": credential_id, "tenant_id": tenant_id}
