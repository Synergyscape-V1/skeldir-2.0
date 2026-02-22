#!/usr/bin/env python3
"""Phase 2 (B0.3) schema-closure gate.

Enforces:
- EG2.1 canonical schema parity (migrations -> dump -> canonical)
- EG2.2 migration determinism (upgrade/downgrade/upgrade dump stability)
- EG2.3 tenant/RLS structural checks for tenant-scoped llm_* tables
- EG2.4 mandatory ledger table presence + runtime-role write privileges
- EG2.5 versioned ledger schema contract parity

Also runs a non-vacuous negative control proving the contract checker fails on
meaningful schema violations.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2


def _import_db_secret_access():
    try:
        from scripts.security.db_secret_access import resolve_migration_database_url, resolve_runtime_database_url
        return resolve_migration_database_url, resolve_runtime_database_url
    except ModuleNotFoundError:
        for parent in Path(__file__).resolve().parents:
            if (parent / "scripts" / "security" / "db_secret_access.py").exists():
                sys.path.insert(0, str(parent))
                from scripts.security.db_secret_access import resolve_migration_database_url, resolve_runtime_database_url
                return resolve_migration_database_url, resolve_runtime_database_url
        raise


resolve_migration_database_url, resolve_runtime_database_url = _import_db_secret_access()


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class GateResult:
    gate: str
    passed: bool
    details: dict[str, Any]


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _run(cmd: list[str], *, env: dict[str, str], cwd: Path, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as handle:
        proc = subprocess.run(cmd, stdout=handle, stderr=subprocess.STDOUT, text=True, env=env, cwd=cwd)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}; log={log_path}")


def _normalize_schema(text: str) -> str:
    keep: list[str] = []
    not_null_constraint_re = re.compile(r"\bCONSTRAINT\s+[A-Za-z0-9_]+\s+NOT\s+NULL\b")
    qualifier_re = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\.")
    replacements = {
        "Ã‚Â±": "±",
        "Â±": "±",
    }
    in_matview_query = False
    for raw in text.splitlines():
        line = raw.rstrip()
        for src, dst in replacements.items():
            line = line.replace(src, dst)
        if "--" in line:
            line = line.split("--", 1)[0].rstrip()
        line = not_null_constraint_re.sub("NOT NULL", line)
        if line.startswith("CREATE MATERIALIZED VIEW "):
            in_matview_query = True
        if line.lstrip().startswith(
            (
                "SELECT ",
                "FROM ",
                "WHERE ",
                "GROUP BY ",
                "ORDER BY ",
                "JOIN ",
                "LEFT JOIN ",
                "RIGHT JOIN ",
                "INNER JOIN ",
                "FULL JOIN ",
                "ON ",
                "AND ",
                "OR ",
            )
        ):
            line = qualifier_re.sub("", line)
        elif in_matview_query:
            # Normalize pg_dump alias qualification noise inside materialized-view query bodies.
            line = qualifier_re.sub("", line)
            if "WITH NO DATA;" in line:
                in_matview_query = False
        if line.startswith("--"):
            continue
        if line.startswith("SET "):
            continue
        if line.startswith("SELECT pg_catalog.set_config"):
            continue
        if line.startswith("SELECT set_config("):
            continue
        if line.startswith("\\restrict"):
            continue
        if line.startswith("\\unrestrict"):
            continue
        if line.startswith("COMMENT ON EXTENSION"):
            continue
        keep.append(line)

    normalized: list[str] = []
    last_blank = False
    for line in keep:
        blank = line.strip() == ""
        if blank and last_blank:
            continue
        normalized.append(line)
        last_blank = blank
    return "\n".join(normalized).strip() + "\n"


def _schema_dump(db_url: str) -> str:
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise RuntimeError("pg_dump not found on PATH")
    proc = subprocess.run(
        [
            pg_dump,
            "--schema-only",
            "--no-owner",
            "--no-privileges",
            "--no-comments",
            db_url,
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"pg_dump failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


def _diff_text(left: str, right: str, left_name: str, right_name: str) -> str:
    return "".join(
        difflib.unified_diff(
            left.splitlines(keepends=True),
            right.splitlines(keepends=True),
            fromfile=left_name,
            tofile=right_name,
        )
    )


def _connect(db_url: str):
    normalized = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return psycopg2.connect(normalized)


def _query_rows(db_url: str, sql: str, params: tuple[Any, ...] | None = None) -> list[tuple[Any, ...]]:
    with _connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def _query_dict_rows(db_url: str, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    with _connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            columns = [desc[0] for desc in cur.description]
            out: list[dict[str, Any]] = []
            for row in cur.fetchall():
                out.append({k: v for k, v in zip(columns, row)})
            return out


def _apply_migrations(migration_url: str, env: dict[str, str], log_dir: Path) -> None:
    _ensure_schema_create_for_migration_role(migration_url)
    mig_env = env.copy()
    mig_env["MIGRATION_DATABASE_URL"] = migration_url
    mig_env["DATABASE_URL"] = migration_url
    _run(["alembic", "upgrade", "head"], env=mig_env, cwd=REPO_ROOT, log_path=log_dir / "alembic_upgrade_head.log")


def _downgrade_base_then_upgrade(migration_url: str, env: dict[str, str], log_dir: Path, prefix: str) -> None:
    mig_env = env.copy()
    mig_env["MIGRATION_DATABASE_URL"] = migration_url
    mig_env["DATABASE_URL"] = migration_url
    _run(["alembic", "downgrade", "base"], env=mig_env, cwd=REPO_ROOT, log_path=log_dir / f"{prefix}_alembic_downgrade_base.log")
    _ensure_schema_create_for_migration_role(migration_url)
    _run(["alembic", "upgrade", "head"], env=mig_env, cwd=REPO_ROOT, log_path=log_dir / f"{prefix}_alembic_upgrade_head.log")


def _ensure_schema_create_for_migration_role(migration_url: str) -> None:
    with _connect(migration_url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("GRANT USAGE, CREATE ON SCHEMA public TO current_user")


def _reset_public_schema(migration_url: str) -> None:
    with _connect(migration_url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA IF EXISTS public CASCADE")
            cur.execute("CREATE SCHEMA public")
            cur.execute("GRANT ALL ON SCHEMA public TO current_user")
            cur.execute("GRANT USAGE, CREATE ON SCHEMA public TO app_user")
            cur.execute("GRANT USAGE ON SCHEMA public TO app_rw")
            cur.execute("GRANT USAGE ON SCHEMA public TO app_ro")


def _run_runtime_probe(runtime_url: str, env: dict[str, str], log_dir: Path) -> None:
    probe = (
        "import asyncio\n"
        "from app.db.session import validate_database_connection\n"
        "from app.main import app\n"
        "async def main():\n"
        "    await validate_database_connection()\n"
        "    print('runtime_probe_ok', bool(app))\n"
        "asyncio.run(main())\n"
    )
    probe_env = env.copy()
    probe_env["DATABASE_URL"] = runtime_url
    _run([sys.executable, "-c", probe], env=probe_env, cwd=REPO_ROOT / "backend", log_path=log_dir / "runtime_probe.log")


def _load_contract(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_contract_type(raw: str) -> str:
    aliases = {
        "integer": "integer",
        "int": "integer",
        "bool": "boolean",
        "boolean": "boolean",
        "uuid": "uuid",
        "text": "text",
        "jsonb": "jsonb",
        "jsonb_ref": "jsonb",
        "varchar": "character varying",
        "timestamptz": "timestamp with time zone",
        "timestamp with time zone": "timestamp with time zone",
    }
    key = raw.strip().lower()
    return aliases.get(key, key)


def _db_columns(db_url: str, schema: str, table: str) -> dict[str, dict[str, Any]]:
    rows = _query_dict_rows(
        db_url,
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
        """,
        (schema, table),
    )
    return {
        row["column_name"]: {
            "type": row["data_type"],
            "nullable": row["is_nullable"] == "YES",
        }
        for row in rows
    }


def _db_uniques(db_url: str, schema: str, table: str) -> list[frozenset[str]]:
    rows = _query_rows(
        db_url,
        """
        SELECT array_agg(att.attname ORDER BY ord.ordinality) AS cols
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
        JOIN unnest(con.conkey) WITH ORDINALITY AS ord(attnum, ordinality) ON true
        JOIN pg_attribute att ON att.attrelid = rel.oid AND att.attnum = ord.attnum
        WHERE con.contype = 'u' AND nsp.nspname = %s AND rel.relname = %s
        GROUP BY con.conname
        ORDER BY con.conname
        """,
        (schema, table),
    )
    return [frozenset(cols) for (cols,) in rows]


def _check_contract(db_url: str, contract: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for table_spec in contract.get("tables", []):
        schema = table_spec["schema"]
        table = table_spec["table"]
        required_columns = table_spec.get("required_columns", [])
        required_uniques = table_spec.get("required_uniques", [])

        actual_columns = _db_columns(db_url, schema, table)
        actual_uniques = _db_uniques(db_url, schema, table)

        table_failures: list[dict[str, Any]] = []
        for col in required_columns:
            name = col["name"]
            expected_type = _normalize_contract_type(col["type"])
            expected_nullable = bool(col["nullable"])
            if name not in actual_columns:
                table_failures.append({"type": "missing_column", "column": name})
                continue
            actual = actual_columns[name]
            actual_type = _normalize_contract_type(str(actual["type"]))
            if actual_type != expected_type:
                table_failures.append(
                    {
                        "type": "type_mismatch",
                        "column": name,
                        "expected": expected_type,
                        "actual": actual_type,
                    }
                )
            if bool(actual["nullable"]) != expected_nullable:
                table_failures.append(
                    {
                        "type": "nullability_mismatch",
                        "column": name,
                        "expected_nullable": expected_nullable,
                        "actual_nullable": bool(actual["nullable"]),
                    }
                )

        for uniq in required_uniques:
            uniq_set = frozenset(uniq)
            if uniq_set not in actual_uniques:
                table_failures.append({"type": "missing_unique", "columns": list(uniq)})

        if table_failures:
            failures.append({"schema": schema, "table": table, "failures": table_failures})

    return (len(failures) == 0, {"failures": failures})


def _check_negative_control(db_url: str, contract: dict[str, Any]) -> dict[str, Any]:
    simulated = json.loads(json.dumps(contract))
    if not simulated.get("tables") or not simulated["tables"][0].get("required_columns"):
        raise RuntimeError("contract missing required test structure")
    injected = {
        "name": "__negative_control_missing_column__",
        "type": "text",
        "nullable": False,
    }
    simulated["tables"][0]["required_columns"].append(injected)

    ok, detail = _check_contract(db_url, simulated)
    if ok:
        raise RuntimeError("negative control failed: tampered contract unexpectedly passed")
    return {
        "negative_control_passed": True,
        "injected_column": injected["name"],
        "reason": "tampered contract failed against real migrated schema as expected",
        "result": detail,
    }


def _eg21_parity(
    *,
    migration_url: str,
    canonical_path: Path,
    env: dict[str, str],
    artifacts_dir: Path,
    log_dir: Path,
) -> GateResult:
    _apply_migrations(migration_url, env, log_dir)
    dump_raw = _schema_dump(migration_url)
    dump_norm = _normalize_schema(dump_raw)
    canonical_norm = _normalize_schema(canonical_path.read_text(encoding="utf-8", errors="replace"))

    (artifacts_dir / "eg2_1_migrated_schema.raw.sql").write_text(dump_raw, encoding="utf-8")
    (artifacts_dir / "eg2_1_migrated_schema.normalized.sql").write_text(dump_norm, encoding="utf-8")
    (artifacts_dir / "eg2_1_canonical_schema.normalized.sql").write_text(canonical_norm, encoding="utf-8")

    diff = _diff_text(canonical_norm, dump_norm, str(canonical_path), "migrated.normalized.sql")
    (artifacts_dir / "eg2_1_parity.diff").write_text(diff, encoding="utf-8")
    passed = dump_norm == canonical_norm
    return GateResult(
        gate="EG2.1",
        passed=passed,
        details={"canonical": str(canonical_path), "diff_path": str(artifacts_dir / "eg2_1_parity.diff")},
    )


def _eg22_determinism(*, migration_url: str, env: dict[str, str], artifacts_dir: Path, log_dir: Path) -> GateResult:
    _reset_public_schema(migration_url)
    _apply_migrations(migration_url, env, log_dir)
    dump_a = _normalize_schema(_schema_dump(migration_url))
    (artifacts_dir / "eg2_2_cycle_a.normalized.sql").write_text(dump_a, encoding="utf-8")

    _reset_public_schema(migration_url)
    _apply_migrations(migration_url, env, log_dir)
    dump_b = _normalize_schema(_schema_dump(migration_url))
    (artifacts_dir / "eg2_2_cycle_b.normalized.sql").write_text(dump_b, encoding="utf-8")

    diff = _diff_text(dump_a, dump_b, "cycle_a.normalized.sql", "cycle_b.normalized.sql")
    (artifacts_dir / "eg2_2_determinism.diff").write_text(diff, encoding="utf-8")
    return GateResult(
        gate="EG2.2",
        passed=dump_a == dump_b,
        details={"diff_path": str(artifacts_dir / "eg2_2_determinism.diff")},
    )


def _eg23_eg24_structural(*, runtime_url: str, contract: dict[str, Any], artifacts_dir: Path) -> tuple[GateResult, GateResult]:
    tenant_scoped_llm_rows = _query_dict_rows(
        runtime_url,
        """
        SELECT c.table_name
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.table_name LIKE 'llm\\_%' ESCAPE '\\'
          AND c.column_name = 'tenant_id'
        ORDER BY c.table_name
        """,
    )
    tenant_scoped_llm_tables = [row["table_name"] for row in tenant_scoped_llm_rows]

    rls_rows = _query_dict_rows(
        runtime_url,
        """
        SELECT cls.relname AS table_name,
               cls.relrowsecurity AS rls_enabled,
               cls.relforcerowsecurity AS rls_forced,
               EXISTS (
                 SELECT 1
                 FROM pg_policies pol
                 WHERE pol.schemaname = 'public'
                   AND pol.tablename = cls.relname
               ) AS has_policy
        FROM pg_class cls
        JOIN pg_namespace nsp ON nsp.oid = cls.relnamespace
        WHERE nsp.nspname = 'public'
          AND cls.relname = ANY(%s)
        ORDER BY cls.relname
        """,
        (tenant_scoped_llm_tables,),
    )

    structural_violations: list[dict[str, Any]] = []
    for row in rls_rows:
        if not row["rls_enabled"] or not row["rls_forced"] or not row["has_policy"]:
            structural_violations.append(row)

    # Mandatory ledger list from contract + mandatory minimum.
    contract_tables = [f"{item['schema']}.{item['table']}" for item in contract.get("tables", [])]
    contract_by_fqtn = {
        f"{item['schema']}.{item['table']}": item for item in contract.get("tables", [])
    }
    mandatory_tables = sorted(set(["public.llm_api_calls", "public.llm_call_audit", *contract_tables]))
    exists_rows = _query_dict_rows(
        runtime_url,
        """
        SELECT table_schema || '.' || table_name AS fqtn
        FROM information_schema.tables
        WHERE table_schema = 'public'
        """,
    )
    existing = {row["fqtn"] for row in exists_rows}
    missing_mandatory = [tbl for tbl in mandatory_tables if tbl not in existing]

    priv_rows: list[dict[str, Any]] = []
    for table_name in mandatory_tables:
        priv_rows.extend(
            _query_dict_rows(
                runtime_url,
                """
                SELECT %s::text AS table_name,
                       has_table_privilege(current_user, %s::text, 'INSERT') AS can_insert,
                       has_table_privilege(current_user, %s::text, 'SELECT') AS can_select,
                       has_table_privilege(current_user, %s::text, 'UPDATE') AS can_update,
                       has_table_privilege(current_user, %s::text, 'DELETE') AS can_delete
                """,
                (table_name, table_name, table_name, table_name, table_name),
            )
        )

    append_only_violations: list[dict[str, Any]] = []
    append_only_trigger_violations: list[dict[str, Any]] = []
    insert_violations: list[dict[str, Any]] = []
    for row in priv_rows:
        table_name = row["table_name"]
        if not row["can_insert"]:
            insert_violations.append(row)
        append_only = bool(contract_by_fqtn.get(table_name, {}).get("append_only", False))
        if append_only and (row["can_update"] or row["can_delete"]):
            append_only_violations.append(row)
        if append_only:
            schema_name, rel_name = table_name.split(".", 1)
            trg_rows = _query_dict_rows(
                runtime_url,
                """
                SELECT trigger_name
                FROM information_schema.triggers
                WHERE event_object_schema = %s
                  AND event_object_table = %s
                  AND action_timing = 'BEFORE'
                  AND event_manipulation IN ('UPDATE', 'DELETE')
                """,
                (schema_name, rel_name),
            )
            if not trg_rows:
                append_only_trigger_violations.append(
                    {
                        "table_name": table_name,
                        "reason": "missing BEFORE UPDATE/DELETE trigger for append-only enforcement",
                    }
                )

    fingerprint_violations: list[dict[str, Any]] = []
    for table_name in mandatory_tables:
        table_contract = contract_by_fqtn.get(table_name)
        if table_contract is None:
            continue
        required = {
            col["name"] for col in table_contract.get("required_columns", [])
        }
        if "prompt_fingerprint" not in required:
            continue
        schema_name, rel_name = table_name.split(".", 1)
        rows = _query_dict_rows(
            runtime_url,
            """
            SELECT column_name, is_nullable
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s AND column_name = 'prompt_fingerprint'
            """,
            (schema_name, rel_name),
        )
        if not rows:
            fingerprint_violations.append(
                {"table_name": table_name, "reason": "missing prompt_fingerprint column"}
            )
            continue
        if rows[0]["is_nullable"] != "NO":
            fingerprint_violations.append(
                {"table_name": table_name, "reason": "prompt_fingerprint must be NOT NULL"}
            )

    payload = {
        "tenant_scoped_llm_tables": tenant_scoped_llm_tables,
        "rls_rows": rls_rows,
        "structural_violations": structural_violations,
        "mandatory_tables": mandatory_tables,
        "missing_mandatory": missing_mandatory,
        "runtime_privileges": priv_rows,
        "insert_violations": insert_violations,
        "append_only_violations": append_only_violations,
        "append_only_trigger_violations": append_only_trigger_violations,
        "prompt_fingerprint_violations": fingerprint_violations,
    }
    (artifacts_dir / "eg2_3_eg2_4_structural_probe.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    eg23 = GateResult(
        gate="EG2.3",
        passed=(len(structural_violations) == 0),
        details={"probe": str(artifacts_dir / "eg2_3_eg2_4_structural_probe.json")},
    )
    eg24 = GateResult(
        gate="EG2.4",
        passed=(
            len(missing_mandatory) == 0
            and len(insert_violations) == 0
            and len(append_only_violations) == 0
            and len(append_only_trigger_violations) == 0
            and len(fingerprint_violations) == 0
        ),
        details={"probe": str(artifacts_dir / "eg2_3_eg2_4_structural_probe.json")},
    )
    return eg23, eg24


def _eg25_contract(*, runtime_url: str, contract: dict[str, Any], artifacts_dir: Path) -> GateResult:
    ok, detail = _check_contract(runtime_url, contract)
    negative_control = _check_negative_control(runtime_url, contract)
    payload = {
        "contract_id": contract.get("contract_id"),
        "contract_version": contract.get("contract_version"),
        "contract_check": detail,
        "negative_control": negative_control,
    }
    out = artifacts_dir / "eg2_5_contract_probe.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return GateResult(gate="EG2.5", passed=ok and negative_control["negative_control_passed"], details={"probe": str(out)})


def _runtime_mutation_check(*, migration_url: str, runtime_url: str, env: dict[str, str], artifacts_dir: Path, log_dir: Path) -> GateResult:
    # Migrate, dump baseline.
    _downgrade_base_then_upgrade(migration_url, env, log_dir, "runtime_mutation")
    baseline = _normalize_schema(_schema_dump(migration_url))
    (artifacts_dir / "runtime_vs_migrated_before_runtime.normalized.sql").write_text(baseline, encoding="utf-8")

    _run_runtime_probe(runtime_url, env, log_dir)

    after = _normalize_schema(_schema_dump(migration_url))
    (artifacts_dir / "runtime_vs_migrated_after_runtime.normalized.sql").write_text(after, encoding="utf-8")

    diff = _diff_text(baseline, after, "before_runtime.normalized.sql", "after_runtime.normalized.sql")
    diff_path = artifacts_dir / "runtime_vs_migrated.diff"
    diff_path.write_text(diff, encoding="utf-8")

    return GateResult(gate="runtime_schema_mutation", passed=(baseline == after), details={"diff_path": str(diff_path)})


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 2 schema closure gate")
    parser.add_argument("--canonical", default="db/schema/canonical_schema.sql")
    parser.add_argument("--contract", default="contracts-internal/llm/b03_phase2_ledger_schema_contract.json")
    parser.add_argument("--evidence-dir", default="backend/validation/evidence/database/phase2_b03")
    args = parser.parse_args()

    migration_url = resolve_migration_database_url()
    runtime_url = resolve_runtime_database_url()
    if not migration_url or not runtime_url:
        print("MIGRATION_DATABASE_URL or DATABASE_URL must be set", file=sys.stderr)
        return 2

    canonical_path = (REPO_ROOT / args.canonical).resolve()
    contract_path = (REPO_ROOT / args.contract).resolve()
    evidence_dir = (REPO_ROOT / args.evidence_dir).resolve()
    log_dir = evidence_dir / "logs"
    artifacts_dir = evidence_dir / "artifacts"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    if not canonical_path.exists():
        print(f"canonical schema not found: {canonical_path}", file=sys.stderr)
        return 2
    if not contract_path.exists():
        print(f"ledger contract not found: {contract_path}", file=sys.stderr)
        return 2

    env = os.environ.copy()
    env["MIGRATION_DATABASE_URL"] = migration_url
    env["DATABASE_URL"] = runtime_url

    contract = _load_contract(contract_path)

    results: list[GateResult] = []
    try:
        results.append(_runtime_mutation_check(migration_url=migration_url, runtime_url=runtime_url, env=env, artifacts_dir=artifacts_dir, log_dir=log_dir))
        results.append(_eg21_parity(migration_url=migration_url, canonical_path=canonical_path, env=env, artifacts_dir=artifacts_dir, log_dir=log_dir))
        results.append(_eg22_determinism(migration_url=migration_url, env=env, artifacts_dir=artifacts_dir, log_dir=log_dir))
        eg23, eg24 = _eg23_eg24_structural(runtime_url=runtime_url, contract=contract, artifacts_dir=artifacts_dir)
        results.extend([eg23, eg24])
        results.append(_eg25_contract(runtime_url=runtime_url, contract=contract, artifacts_dir=artifacts_dir))
    except Exception as exc:  # pragma: no cover - fails closed and records evidence.
        summary = {
            "phase": "B0.3",
            "timestamp": _utc_now(),
            "status": "failure",
            "error": str(exc),
            "gates": [{"gate": r.gate, "passed": r.passed, "details": r.details} for r in results],
        }
        (evidence_dir / "phase2_b03_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"Phase2 schema closure failed: {exc}", file=sys.stderr)
        return 1

    all_passed = all(r.passed for r in results)
    summary = {
        "phase": "B0.3",
        "timestamp": _utc_now(),
        "status": "success" if all_passed else "failure",
        "canonical": str(canonical_path),
        "contract": str(contract_path),
        "evidence_dir": str(evidence_dir),
        "gates": [{"gate": r.gate, "passed": r.passed, "details": r.details} for r in results],
    }
    (evidence_dir / "phase2_b03_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
