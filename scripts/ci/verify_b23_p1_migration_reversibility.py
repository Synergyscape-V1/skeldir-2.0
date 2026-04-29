#!/usr/bin/env python3
"""Verify B2.3-P1 migration reversibility (upgrade -> downgrade -1 -> re-upgrade)."""

from __future__ import annotations

import json
import os
import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

import psycopg2


REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET_TABLES = (
    "b23_match_verdicts",
    "b23_exception_records",
    "b23_revenue_events",
    "b23_webhook_ingestion_logs",
)


def _run_alembic(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["alembic", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _database_url_for_sync_pg(dsn_input: str) -> str:
    if not dsn_input:
        raise RuntimeError("B23_P1_MIGRATION_DSN is required")
    dsn = dsn_input
    if dsn.startswith("postgresql+"):
        return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    return dsn


def _capture_signature(database_dsn: str) -> dict[str, Any]:
    signature: dict[str, Any] = {"tables": {}, "indexes": {}, "policies": {}}
    with psycopg2.connect(database_dsn) as conn:
        with conn.cursor() as cursor:
            for table in TARGET_TABLES:
                cursor.execute(
                    """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (table,),
                )
                signature["tables"][table] = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'public' AND tablename = %s
                    ORDER BY indexname
                    """,
                    (table,),
                )
                signature["indexes"][table] = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT polname, pg_get_expr(polqual, polrelid), pg_get_expr(polwithcheck, polrelid)
                    FROM pg_policy
                    JOIN pg_class ON pg_class.oid = pg_policy.polrelid
                    JOIN pg_namespace n ON n.oid = pg_class.relnamespace
                    WHERE n.nspname = 'public' AND pg_class.relname = %s
                    ORDER BY polname
                    """,
                    (table,),
                )
                signature["policies"][table] = cursor.fetchall()
    return signature


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify B2.3-P1 migration reversibility")
    parser.add_argument(
        "--migration-dsn",
        default=os.getenv("B23_P1_MIGRATION_DSN", ""),
        help="Synchronous psycopg2 DSN used for signature capture",
    )
    args = parser.parse_args()

    sync_dsn = _database_url_for_sync_pg(args.migration_dsn)
    if "MIGRATION_DATABASE_URL" not in os.environ:
        os.environ["MIGRATION_DATABASE_URL"] = sync_dsn

    up_proc = _run_alembic("upgrade", "head")
    if up_proc.returncode != 0:
        sys.stdout.write(up_proc.stdout)
        sys.stderr.write(up_proc.stderr)
        print("result=FAIL")
        print("phase=upgrade_head")
        return 1
    before_signature = _capture_signature(sync_dsn)

    down_proc = _run_alembic("downgrade", "-1")
    if down_proc.returncode != 0:
        sys.stdout.write(down_proc.stdout)
        sys.stderr.write(down_proc.stderr)
        print("result=FAIL")
        print("phase=downgrade_one")
        return 1

    reup_proc = _run_alembic("upgrade", "head")
    if reup_proc.returncode != 0:
        sys.stdout.write(reup_proc.stdout)
        sys.stderr.write(reup_proc.stderr)
        print("result=FAIL")
        print("phase=reupgrade_head")
        return 1
    after_signature = _capture_signature(sync_dsn)

    if before_signature != after_signature:
        print("result=FAIL")
        print("phase=signature_compare")
        print("before_signature=" + json.dumps(before_signature, sort_keys=True, default=str))
        print("after_signature=" + json.dumps(after_signature, sort_keys=True, default=str))
        return 1

    print("result=PASS")
    print("phase=reversibility_verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
