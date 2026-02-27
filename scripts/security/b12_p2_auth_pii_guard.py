#!/usr/bin/env python3
"""Auth substrate PII guard for B1.2-P2."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable

import psycopg2
from psycopg2 import sql


def _import_db_secret_access():
    try:
        from scripts.security.db_secret_access import resolve_runtime_database_url

        return resolve_runtime_database_url
    except ModuleNotFoundError:
        for parent in Path(__file__).resolve().parents:
            if (parent / "scripts" / "security" / "db_secret_access.py").exists():
                sys.path.insert(0, str(parent))
                from scripts.security.db_secret_access import (
                    resolve_runtime_database_url,
                )

                return resolve_runtime_database_url
        raise


resolve_runtime_database_url = _import_db_secret_access()

AUTH_TABLES = ("users", "tenant_memberships", "roles", "tenant_membership_roles")
TEXT_LIKE_TYPES = {"text", "character varying", "json", "jsonb"}

DISALLOWED_COLUMN_RE = re.compile(r"(^|_)(email|ip|ip_address)($|_)", re.IGNORECASE)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE)
IPV4_RE = re.compile(
    r"\b(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}\b"
)
IPV6_RE = re.compile(r"\b(?:[A-F0-9]{1,4}:){2,7}[A-F0-9]{1,4}\b", re.IGNORECASE)


def _sync_dsn(raw: str) -> str:
    return raw.replace("postgresql+asyncpg://", "postgresql://", 1)


def _connect(db_url: str):
    return psycopg2.connect(_sync_dsn(db_url))


def _detect_pii(text: str) -> bool:
    return bool(EMAIL_RE.search(text) or IPV4_RE.search(text) or IPV6_RE.search(text))


def _self_test() -> tuple[bool, list[str]]:
    violations: list[str] = []
    probes = {
        "email": "user@example.com",
        "ipv4": "192.168.1.10",
        "ipv6": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        "safe_hash": "9f86d081884c7d659a2feaa0c55ad015",
    }
    if not _detect_pii(probes["email"]):
        violations.append("self_test: email detector missed canonical email pattern")
    if not _detect_pii(probes["ipv4"]):
        violations.append("self_test: ipv4 detector missed canonical ipv4 pattern")
    if not _detect_pii(probes["ipv6"]):
        violations.append("self_test: ipv6 detector missed canonical ipv6 pattern")
    if _detect_pii(probes["safe_hash"]):
        violations.append("self_test: detector produced false positive on opaque hash")
    return (len(violations) == 0, violations)


def _iter_text_columns(cur, table_name: str) -> Iterable[tuple[str, str]]:
    cur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    for col, data_type in cur.fetchall():
        yield str(col), str(data_type)


def run_scan(db_url: str) -> tuple[int, list[str], dict[str, int]]:
    violations: list[str] = []
    scanned_columns = 0
    scanned_tables = 0

    with _connect(db_url) as conn:
        with conn.cursor() as cur:
            for table_name in AUTH_TABLES:
                scanned_tables += 1
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = %s
                    )
                    """,
                    (table_name,),
                )
                if not bool(cur.fetchone()[0]):
                    violations.append(f"missing_table: public.{table_name}")
                    continue

                for column_name, data_type in _iter_text_columns(cur, table_name):
                    scanned_columns += 1
                    if DISALLOWED_COLUMN_RE.search(column_name):
                        violations.append(
                            f"disallowed_column: public.{table_name}.{column_name}"
                        )

                    if data_type.lower() not in TEXT_LIKE_TYPES:
                        continue

                    query = sql.SQL(
                        """
                        SELECT COUNT(*)
                        FROM public.{table}
                        WHERE {column} IS NOT NULL
                          AND (
                                {column}::text ~* %s
                             OR {column}::text ~* %s
                             OR {column}::text ~* %s
                          )
                        """
                    ).format(
                        table=sql.Identifier(table_name),
                        column=sql.Identifier(column_name),
                    )
                    cur.execute(
                        query,
                        (
                            EMAIL_RE.pattern,
                            IPV4_RE.pattern,
                            IPV6_RE.pattern,
                        ),
                    )
                    match_count = int(cur.fetchone()[0] or 0)
                    if match_count > 0:
                        violations.append(
                            "disallowed_value: "
                            f"public.{table_name}.{column_name} matched_rows={match_count}"
                        )

    status = 1 if violations else 0
    metrics = {
        "scanned_tables": scanned_tables,
        "scanned_columns": scanned_columns,
        "violations": len(violations),
    }
    return status, violations, metrics


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="B1.2-P2 auth substrate PII guard")
    parser.add_argument(
        "--database-url", default="", help="Override runtime database URL"
    )
    parser.add_argument("--report", default="", help="Optional report path")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run detector self-test and exit.",
    )
    parser.add_argument(
        "--simulate-violation",
        action="store_true",
        help="Emit a synthetic violation and exit non-zero (negative-control hook).",
    )
    args = parser.parse_args(argv)

    lines: list[str] = ["b12_p2_auth_pii_guard"]

    ok, self_test_violations = _self_test()
    if not ok:
        lines.append("result=FAIL")
        lines.extend(self_test_violations)
        payload = "\n".join(lines) + "\n"
        if args.report:
            Path(args.report).write_text(payload, encoding="utf-8")
        sys.stdout.write(payload)
        return 1

    if args.self_test:
        payload = "b12_p2_auth_pii_guard\nresult=PASS\nself_test=PASS\n"
        if args.report:
            Path(args.report).write_text(payload, encoding="utf-8")
        sys.stdout.write(payload)
        return 0

    if args.simulate_violation:
        payload = (
            "b12_p2_auth_pii_guard\n"
            "result=FAIL\n"
            "synthetic_violation=disallowed_value: public.users.login_identifier_hash\n"
        )
        if args.report:
            Path(args.report).write_text(payload, encoding="utf-8")
        sys.stdout.write(payload)
        return 1

    db_url = args.database_url.strip() or resolve_runtime_database_url()
    if not db_url:
        raise RuntimeError("DATABASE_URL is required for auth PII scan")

    status, violations, metrics = run_scan(db_url)
    lines.append(f"scanned_tables={metrics['scanned_tables']}")
    lines.append(f"scanned_columns={metrics['scanned_columns']}")
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("no disallowed auth-substrate columns or values detected")

    payload = "\n".join(lines) + "\n"
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(payload, encoding="utf-8")
    sys.stdout.write(payload)
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
