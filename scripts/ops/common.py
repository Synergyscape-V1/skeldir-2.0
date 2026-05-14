"""Shared helpers for M4 local operational diagnostics.

These helpers are intentionally local-fixture oriented. They do not provide a
production replay path and they do not bypass webhook authenticity, RLS, or
idempotency semantics.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import psycopg2
import psycopg2.extras


FIXTURE_DIR = Path(".tmp/m4_ops")
FIXTURE_STATE_PATH = FIXTURE_DIR / "diagnostic_fixture.json"

TENANT_NAME_PREFIX = "M4 Ops Diagnostic Tenant"
DLQ_TASK_ID_PREFIX = "m4-dlq-positive"
B23_TASK_ID_PREFIX = "m4-b23-trace-positive"
WEBHOOK_IDEMPOTENCY_PREFIX = "m4-webhook-valid"


def _normalize_database_url(raw: str) -> str:
    if raw.startswith("postgresql+asyncpg://"):
        return raw.replace("postgresql+asyncpg://", "postgresql://", 1)
    return raw


def database_url() -> str:
    raw = (
        os.getenv("OPS_DATABASE_URL")
        or os.getenv("MIGRATION_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or ""
    ).strip()
    if not raw:
        raise SystemExit(
            "OPS_DATABASE_URL, MIGRATION_DATABASE_URL, or DATABASE_URL is required"
        )
    parsed = urlsplit(_normalize_database_url(raw))
    query = "&".join(
        part
        for part in parsed.query.split("&")
        if part and not part.startswith("sslmode=") and not part.startswith("channel_binding=")
    )
    return urlunsplit(parsed._replace(query=query))


def connect():
    return psycopg2.connect(database_url(), cursor_factory=psycopg2.extras.RealDictCursor)


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def ensure_fixture_dir() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)


def write_fixture_state(payload: dict[str, Any]) -> None:
    ensure_fixture_dir()
    FIXTURE_STATE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def read_fixture_state() -> dict[str, Any]:
    if not FIXTURE_STATE_PATH.exists():
        raise SystemExit(
            f"diagnostic fixture state not found at {FIXTURE_STATE_PATH}; run make ops-seed-diagnostics first"
        )
    return json.loads(FIXTURE_STATE_PATH.read_text(encoding="utf-8"))


def table_columns(cur, table_name: str) -> set[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        """,
        (table_name,),
    )
    return {row["column_name"] for row in cur.fetchall()}


def required_columns(cur, table_name: str) -> set[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND is_nullable = 'NO'
          AND column_default IS NULL
          AND (is_identity IS NULL OR is_identity = 'NO')
        """,
        (table_name,),
    )
    return {row["column_name"] for row in cur.fetchall()}


def insert_dynamic(cur, table_name: str, payload: dict[str, Any], conflict: str | None = None) -> None:
    columns = table_columns(cur, table_name)
    required = required_columns(cur, table_name)
    insert_columns: list[str] = []
    values: list[Any] = []
    for column in payload:
        if column in columns:
            insert_columns.append(column)
            values.append(payload[column])
    missing = sorted(column for column in required if column not in insert_columns)
    if missing:
        raise SystemExit(f"{table_name} fixture missing required columns: {missing}")
    placeholders = ", ".join(["%s"] * len(insert_columns))
    column_sql = ", ".join(insert_columns)
    conflict_sql = f" {conflict}" if conflict else ""
    cur.execute(
        f"INSERT INTO public.{table_name} ({column_sql}) VALUES ({placeholders}){conflict_sql}",
        values,
    )


def set_tenant(cur, tenant_id: str, *, local: bool = False) -> None:
    cur.execute(
        "SELECT set_config('app.current_tenant_id', %s, %s)",
        (tenant_id, local),
    )
