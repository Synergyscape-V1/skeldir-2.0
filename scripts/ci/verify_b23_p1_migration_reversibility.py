#!/usr/bin/env python3
"""Verify B2.3-P1 migration reversibility (upgrade -> downgrade -1 -> re-upgrade)."""

from __future__ import annotations

import argparse
import json
import os
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
TARGET_FUNCTIONS = ("fn_b23_p1_apply_lifecycle",)
TARGET_POLICIES = (
    "tenant_isolation_policy_b23_match_verdicts",
    "tenant_isolation_policy_b23_exception_records",
    "tenant_isolation_policy_b23_revenue_events",
    "tenant_isolation_policy_b23_webhook_ingestion_logs",
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
    signature: dict[str, Any] = {
        "tables": {},
        "indexes": {},
        "policies": {},
        "constraints": {},
        "force_rls": {},
        "functions": {},
        "cron_jobs": [],
    }
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
                    SELECT conname, contype, pg_get_constraintdef(c.oid)
                    FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    JOIN pg_namespace n ON n.oid = t.relnamespace
                    WHERE n.nspname = 'public' AND t.relname = %s
                    ORDER BY conname
                    """,
                    (table,),
                )
                signature["constraints"][table] = cursor.fetchall()

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
                policies = cursor.fetchall()
                signature["policies"][table] = policies

                cursor.execute(
                    """
                    SELECT relrowsecurity, relforcerowsecurity
                    FROM pg_class
                    JOIN pg_namespace n ON n.oid = pg_class.relnamespace
                    WHERE n.nspname = 'public' AND relname = %s
                    """,
                    (table,),
                )
                row = cursor.fetchone()
                signature["force_rls"][table] = row

            for policy_name in TARGET_POLICIES:
                if not any(policy_name == pol[0] for table in signature["policies"].values() for pol in table):
                    signature["policies"].setdefault("missing", []).append(policy_name)

            for function_name in TARGET_FUNCTIONS:
                cursor.execute(
                    """
                    SELECT
                        p.proname,
                        pg_get_function_identity_arguments(p.oid),
                        pg_get_functiondef(p.oid)
                    FROM pg_proc p
                    JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = 'public' AND p.proname = %s
                    ORDER BY p.proname
                    """,
                    (function_name,),
                )
                signature["functions"][function_name] = cursor.fetchall()

            cursor.execute("SELECT to_regnamespace('cron')")
            cron_ns = cursor.fetchone()
            if cron_ns and cron_ns[0] is not None:
                cursor.execute(
                    """
                    SELECT jobname, schedule, command
                    FROM cron.job
                    WHERE jobname = 'b23_p1_apply_lifecycle_daily'
                    ORDER BY jobname
                    """
                )
                signature["cron_jobs"] = cursor.fetchall()
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
