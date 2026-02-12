#!/usr/bin/env python3
"""Phase 4 security closure probe.

EG4.1 automatic tenant table discovery
EG4.2 RLS/FORCE/policy coverage
EG4.3 runtime identity least privilege
EG4.4 tenant context propagation fail-closed checks
EG4.5 sentinel secret leak scan
EG4.6 DLQ tenant/quarantine lane isolation
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import psycopg2
from psycopg2 import sql


EVIDENCE_DIR = Path("backend/validation/evidence/security")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


class ProbeFailure(RuntimeError):
    pass


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ProbeFailure(f"{name} is required")
    return value


def _connect(dsn: str):
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    return conn


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


@dataclass
class RoleIdentity:
    current_user: str
    session_user: str
    rolsuper: bool
    rolbypassrls: bool


def fetch_identity(conn) -> RoleIdentity:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT current_user, session_user, r.rolsuper, r.rolbypassrls
            FROM pg_roles r
            WHERE r.rolname = current_user
            """
        )
        row = cur.fetchone()
    if not row:
        raise ProbeFailure("identity query returned no rows")
    return RoleIdentity(
        current_user=str(row[0]),
        session_user=str(row[1]),
        rolsuper=bool(row[2]),
        rolbypassrls=bool(row[3]),
    )


def discover_tenant_tables(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH tenant_scoped AS (
                SELECT c.oid, c.relname, 'tenant_id'::text AS scope
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_attribute a ON a.attrelid = c.oid
                WHERE n.nspname = 'public'
                  AND c.relkind = 'r'
                  AND a.attname = 'tenant_id'
                  AND a.attnum > 0
                  AND NOT a.attisdropped
            ),
            user_scoped AS (
                SELECT c.oid, c.relname, 'user_id'::text AS scope
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_attribute a ON a.attrelid = c.oid
                JOIN pg_constraint con
                  ON con.conrelid = c.oid
                 AND con.contype = 'f'
                JOIN pg_class refc ON refc.oid = con.confrelid
                JOIN pg_namespace refn ON refn.oid = refc.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relkind = 'r'
                  AND a.attname = 'user_id'
                  AND a.attnum > 0
                  AND NOT a.attisdropped
                  AND refn.nspname = 'public'
                  AND refc.relname = 'users'
            ),
            scoped AS (
                SELECT * FROM tenant_scoped
                UNION
                SELECT * FROM user_scoped
            )
            SELECT s.relname, c.relrowsecurity, c.relforcerowsecurity, s.scope
            FROM scoped s
            JOIN pg_class c ON c.oid = s.oid
            ORDER BY s.relname
            """
        )
        rows = cur.fetchall()

    table_names = [str(r[0]) for r in rows]
    policies_by_table: dict[str, set[str]] = {t: set() for t in table_names}
    if table_names:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tablename, cmd
                FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename = ANY(%s)
                """,
                (table_names,),
            )
            for tablename, polcmd in cur.fetchall():
                policies_by_table[str(tablename)].add(str(polcmd))

    discovered = []
    for name, rls_enabled, force_rls, scope in rows:
        cmd_set = policies_by_table.get(str(name), set())
        discovered.append(
            {
                "table_name": str(name),
                "scope": str(scope),
                "rls_enabled": bool(rls_enabled),
                "force_rls": bool(force_rls),
                "policy_cmds": sorted(cmd_set),
                "policy_count": len(cmd_set),
            }
        )
    return discovered


def assert_rls_coverage(discovered: list[dict]) -> None:
    if not discovered:
        raise ProbeFailure("tenant-scoped discovery returned zero tables")

    missing: list[str] = []
    for row in discovered:
        cmd_set = {str(c).upper() for c in row["policy_cmds"]}
        has_full_coverage = (
            "ALL" in cmd_set
            or "*" in cmd_set
            or {"R", "A", "W", "D"}.issubset(cmd_set)
            or {"SELECT", "INSERT", "UPDATE", "DELETE"}.issubset(cmd_set)
        )
        is_quarantine = row["table_name"] == "dead_events_quarantine"
        has_quarantine_coverage = {"SELECT", "INSERT"}.issubset(cmd_set)
        if not row["rls_enabled"]:
            missing.append(f"{row['table_name']}: RLS disabled")
        if not row["force_rls"]:
            missing.append(f"{row['table_name']}: FORCE RLS disabled")
        if is_quarantine:
            if not has_quarantine_coverage:
                missing.append(f"{row['table_name']}: missing quarantine policy coverage cmds={sorted(cmd_set)}")
        elif not has_full_coverage:
            missing.append(f"{row['table_name']}: missing policy coverage cmds={sorted(cmd_set)}")
    if missing:
        raise ProbeFailure("RLS coverage failure:\n" + "\n".join(missing))


def _seed_tenant(conn, tenant_id: uuid.UUID, label: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tenants (id, api_key_hash, name, notification_email)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                str(tenant_id),
                f"phase4_{label}_{tenant_id.hex}",
                f"Phase4 {label}",
                f"phase4_{label}_{tenant_id.hex[:8]}@test.invalid",
            ),
        )


def _set_tenant_context(conn, tenant_id: uuid.UUID | None) -> None:
    with conn.cursor() as cur:
        if tenant_id is None:
            cur.execute("RESET app.current_tenant_id")
        else:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )


def _count_marked_dead_events(conn, marker: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM dead_events
            WHERE source = 'phase4_probe'
              AND raw_payload->>'marker' LIKE %s
            """,
            (f"{marker}%",),
        )
        return int(cur.fetchone()[0] or 0)


def _seed_dead_event(conn, tenant_id: uuid.UUID, marker: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO dead_events
            (
                tenant_id,
                source,
                error_code,
                error_detail,
                raw_payload,
                event_type,
                error_type,
                error_message
            )
            VALUES
            (
                %s,
                'phase4_probe',
                'PHASE4',
                '{}'::jsonb,
                %s::jsonb,
                'purchase',
                'validation_error',
                'phase4 marker'
            )
            """,
            (
                str(tenant_id),
                json.dumps({"marker": f"{marker}_{tenant_id.hex[:10]}"}),
            ),
        )


def _insert_dlq_row(
    conn,
    *,
    tenant_id: uuid.UUID | None,
    marker: str,
    source: str,
    error_type: str,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO dead_events_quarantine
            (
                tenant_id, source, raw_payload, error_type, error_code,
                error_message, error_detail, correlation_id
            )
            VALUES (%s, %s, %s::jsonb, %s, %s, %s, '{}'::jsonb, %s)
            """,
            (
                str(tenant_id) if tenant_id else None,
                source,
                json.dumps({"marker": marker}),
                error_type,
                "PHASE4",
                f"phase4:{marker}",
                str(uuid.uuid4()),
            ),
        )


def _count_dlq_rows(conn, marker: str, tenant_id: uuid.UUID | None) -> int:
    with conn.cursor() as cur:
        if tenant_id is None:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM dead_events_quarantine
                WHERE raw_payload->>'marker' = %s
                  AND tenant_id IS NULL
                """,
                (marker,),
            )
        else:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM dead_events_quarantine
                WHERE raw_payload->>'marker' = %s
                  AND tenant_id = %s::uuid
                """,
                (marker, str(tenant_id)),
            )
        return int(cur.fetchone()[0] or 0)


def behavioral_rls_checks(runtime_conn, ops_conn) -> dict:
    marker = f"phase4_{uuid.uuid4().hex[:10]}"
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    _seed_tenant(runtime_conn, tenant_a, "A")
    _seed_tenant(runtime_conn, tenant_b, "B")
    _set_tenant_context(runtime_conn, tenant_a)
    _seed_dead_event(runtime_conn, tenant_a, marker)
    _set_tenant_context(runtime_conn, tenant_b)
    _seed_dead_event(runtime_conn, tenant_b, marker)
    runtime_conn.commit()

    _set_tenant_context(runtime_conn, tenant_a)
    visible_a = _count_marked_dead_events(runtime_conn, marker)
    _set_tenant_context(runtime_conn, tenant_b)
    visible_b = _count_marked_dead_events(runtime_conn, marker)
    _set_tenant_context(runtime_conn, None)
    missing_context_visible: int | None = None
    missing_context_exception: str | None = None
    try:
        missing_context_visible = _count_marked_dead_events(runtime_conn, marker)
    except Exception as exc:
        runtime_conn.rollback()
        missing_context_exception = str(exc)

    _set_tenant_context(runtime_conn, tenant_a)
    spoof_blocked = False
    try:
        _seed_dead_event(runtime_conn, tenant_b, marker + "_spoof")
        runtime_conn.commit()
    except Exception:
        runtime_conn.rollback()
        spoof_blocked = True
    if not spoof_blocked:
        raise ProbeFailure("cross-tenant insert spoof succeeded; WITH CHECK enforcement failed")

    marker_a = marker + "_dlq_a"
    marker_b = marker + "_dlq_b"
    marker_q = marker + "_dlq_q"
    _set_tenant_context(runtime_conn, tenant_a)
    _insert_dlq_row(runtime_conn, tenant_id=tenant_a, marker=marker_a, source="webhook", error_type="validation")
    _set_tenant_context(runtime_conn, tenant_b)
    _insert_dlq_row(runtime_conn, tenant_id=tenant_b, marker=marker_b, source="webhook", error_type="validation")
    _set_tenant_context(runtime_conn, None)
    _insert_dlq_row(runtime_conn, tenant_id=None, marker=marker_q, source="webhook", error_type="unresolved_tenant")
    runtime_conn.commit()

    _set_tenant_context(runtime_conn, tenant_a)
    tenant_a_own = _count_dlq_rows(runtime_conn, marker_a, tenant_a)
    tenant_a_other = _count_dlq_rows(runtime_conn, marker_b, tenant_b)
    tenant_a_null = _count_dlq_rows(runtime_conn, marker_q, None)

    _set_tenant_context(runtime_conn, tenant_b)
    tenant_b_own = _count_dlq_rows(runtime_conn, marker_b, tenant_b)
    tenant_b_other = _count_dlq_rows(runtime_conn, marker_a, tenant_a)
    tenant_b_null = _count_dlq_rows(runtime_conn, marker_q, None)

    with ops_conn.cursor() as cur:
        cur.execute("SELECT current_user, session_user")
        ops_identity = cur.fetchone()
    ops_conn.commit()
    ops_null = _count_dlq_rows(ops_conn, marker_q, None)
    ops_tenant_a = _count_dlq_rows(ops_conn, marker_a, tenant_a)

    checks = {
        "visible_with_tenant_a_context": visible_a,
        "visible_with_tenant_b_context": visible_b,
        "visible_with_missing_context": missing_context_visible,
        "missing_context_exception": missing_context_exception,
        "cross_tenant_insert_spoof_blocked": spoof_blocked,
        "dlq_tenant_a_own": tenant_a_own,
        "dlq_tenant_a_other": tenant_a_other,
        "dlq_tenant_a_null_lane": tenant_a_null,
        "dlq_tenant_b_own": tenant_b_own,
        "dlq_tenant_b_other": tenant_b_other,
        "dlq_tenant_b_null_lane": tenant_b_null,
        "ops_identity": {"current_user": str(ops_identity[0]), "session_user": str(ops_identity[1])},
        "ops_quarantine_visible": ops_null,
        "ops_tenant_lane_visible": ops_tenant_a,
    }

    if visible_a < 1 or visible_b < 1:
        raise ProbeFailure(f"tenant context visibility failure: {checks}")
    if missing_context_visible not in (None, 0):
        raise ProbeFailure(f"missing tenant context did not fail closed: {checks}")
    if tenant_a_other != 0 or tenant_b_other != 0:
        raise ProbeFailure(f"cross-tenant DLQ visibility leak detected: {checks}")
    if tenant_a_null != 0 or tenant_b_null != 0:
        raise ProbeFailure(f"tenant can see quarantine lane rows: {checks}")
    if ops_null < 1:
        raise ProbeFailure(f"ops role cannot see quarantine lane rows: {checks}")
    if ops_tenant_a != 0:
        raise ProbeFailure(f"ops role can see tenant lane rows unexpectedly: {checks}")

    return checks


def _iter_scan_files(scan_dirs: Iterable[str]) -> Iterable[Path]:
    for raw in scan_dirs:
        p = Path(raw).resolve()
        if not p.exists():
            continue
        if p.is_file():
            yield p
            continue
        for file_path in p.rglob("*"):
            if file_path.is_file():
                yield file_path


def _scan_files_for_secret(scan_dirs: Iterable[str], secret: str) -> list[str]:
    hits: list[str] = []
    for file_path in _iter_scan_files(scan_dirs):
        try:
            data = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if secret in data:
            hits.append(str(file_path))
    return hits


def _scan_database_for_secret(conn, secret: str) -> list[str]:
    hits: list[str] = []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_schema, table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND data_type IN ('text', 'character varying', 'json', 'jsonb', 'uuid')
            ORDER BY table_name, column_name
            """
        )
        cols = cur.fetchall()

    for schema_name, table_name, column_name, _ in cols:
        query = sql.SQL(
            "SELECT 1 FROM {}.{} WHERE CAST({} AS text) LIKE %s LIMIT 1"
        ).format(
            sql.Identifier(str(schema_name)),
            sql.Identifier(str(table_name)),
            sql.Identifier(str(column_name)),
        )
        with conn.cursor() as cur:
            cur.execute(query, (f"%{secret}%",))
            found = cur.fetchone()
        if found:
            hits.append(f"{schema_name}.{table_name}.{column_name}")
    return hits


def secret_scan_checks(runtime_conn, sentinel: str) -> dict:
    scan_dirs_env = os.getenv(
        "PHASE4_SCAN_DIRS",
        "backend/validation/evidence,artifacts,.tmp_ci_artifacts",
    )
    scan_dirs = [p.strip() for p in scan_dirs_env.split(",") if p.strip()]

    # Non-vacuous scanner check: ensure sentinel detection works when a hit exists.
    canary_file = EVIDENCE_DIR / ".phase4_secret_canary.txt"
    canary_file.write_text(f"probe={sentinel}", encoding="utf-8")
    canary_hits = _scan_files_for_secret([str(EVIDENCE_DIR)], sentinel)
    canary_file.unlink(missing_ok=True)
    if not canary_hits:
        raise ProbeFailure("secret scanner negative control failed; sentinel canary was not detected")

    file_hits = _scan_files_for_secret(scan_dirs, sentinel)
    db_hits = _scan_database_for_secret(runtime_conn, sentinel)
    if file_hits or db_hits:
        raise ProbeFailure(
            "secret leak detected: "
            + json.dumps({"file_hits": file_hits, "db_hits": db_hits}, sort_keys=True)
        )
    return {
        "scan_dirs": scan_dirs,
        "file_hit_count": 0,
        "db_hit_count": 0,
    }


def run() -> int:
    runtime_dsn = _required_env("DATABASE_URL")
    migration_dsn = _required_env("MIGRATION_DATABASE_URL")
    ops_dsn = _required_env("OPS_DATABASE_URL")
    expected_runtime_user = _required_env("EXPECTED_RUNTIME_DB_USER")
    sentinel = os.getenv("SKELDIR_TEST_SECRET", f"SKELDIR_TEST_SECRET_{secrets.token_hex(8)}")

    now = datetime.now(timezone.utc).isoformat()

    with _connect(runtime_dsn) as runtime_conn, _connect(migration_dsn) as migration_conn, _connect(ops_dsn) as ops_conn:
        runtime_identity = fetch_identity(runtime_conn)
        migration_identity = fetch_identity(migration_conn)
        ops_identity = fetch_identity(ops_conn)

        if runtime_identity.current_user != expected_runtime_user:
            raise ProbeFailure(
                f"runtime identity mismatch: current_user={runtime_identity.current_user} expected={expected_runtime_user}"
            )
        if runtime_identity.current_user in {migration_identity.current_user, "postgres", "migration_owner"}:
            raise ProbeFailure(
                f"runtime identity is privileged or equal to migration identity: {runtime_identity.current_user}"
            )
        if runtime_identity.rolsuper or runtime_identity.rolbypassrls:
            raise ProbeFailure(
                f"runtime identity can bypass RLS: super={runtime_identity.rolsuper} bypassrls={runtime_identity.rolbypassrls}"
            )

        discovered = discover_tenant_tables(runtime_conn)
        artifact_tables = {
            "timestamp": now,
            "runtime_user": runtime_identity.current_user,
            "tenant_scoped_tables": discovered,
        }
        _write_json(EVIDENCE_DIR / "phase4_tenant_tables.json", artifact_tables)
        assert_rls_coverage(discovered)
        behavior = behavioral_rls_checks(runtime_conn, ops_conn)
        secret_scan = secret_scan_checks(runtime_conn, sentinel)

        summary = {
            "timestamp": now,
            "eg4_1_table_discovery": {"pass": True, "tenant_table_count": len(discovered)},
            "eg4_2_rls_force_coverage": {"pass": True},
            "eg4_3_runtime_identity": {
                "pass": True,
                "runtime": runtime_identity.__dict__,
                "migration": migration_identity.__dict__,
                "ops": ops_identity.__dict__,
            },
            "eg4_4_context_fail_closed": {"pass": True, "details": behavior},
            "eg4_5_secret_scan": {"pass": True, "details": secret_scan},
            "eg4_6_dlq_two_lane": {"pass": True, "details": behavior},
            "eg4_7_phase3_perf_non_regression": {
                "pass": True,
                "mode": "delegated_to_r3_harness",
                "note": "Executed by scripts/r3/ingestion_under_fire.py from B0.4 gate",
            },
        }
        _write_json(EVIDENCE_DIR / "phase4_gate_summary.json", summary)
    return 0


def main() -> int:
    try:
        return run()
    except Exception as exc:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "failure",
            "error": str(exc),
        }
        _write_json(EVIDENCE_DIR / "phase4_gate_summary.json", payload)
        print(f"PHASE4_PROBE_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
