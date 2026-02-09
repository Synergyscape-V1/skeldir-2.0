#!/usr/bin/env python3
"""Assert runtime proofs use runtime DB identity and not migration identity."""

from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urlparse

import psycopg2


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _current_user(dsn: str) -> str:
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user")
            value = cur.fetchone()
            if not value:
                raise RuntimeError("current_user query returned no rows")
            return str(value[0])


def _dsn_user(dsn: str) -> str:
    parsed = urlparse(dsn)
    return parsed.username or ""


def _print(msg: str) -> None:
    print(f"[runtime-identity] {msg}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-dsn-env", default="DATABASE_URL")
    parser.add_argument("--migration-dsn-env", default="MIGRATION_DATABASE_URL")
    parser.add_argument("--expected-runtime-user-env", default="EXPECTED_RUNTIME_DB_USER")
    parser.add_argument("--allow-missing-migration-dsn", action="store_true")
    args = parser.parse_args()

    try:
        runtime_dsn = _require(args.runtime_dsn_env)
        expected_runtime_user = _require(args.expected_runtime_user_env)
        runtime_current_user = _current_user(runtime_dsn)
        runtime_dsn_user = _dsn_user(runtime_dsn)
        _print(f"{args.runtime_dsn_env} current_user={runtime_current_user}")

        if runtime_current_user != expected_runtime_user:
            raise RuntimeError(
                f"runtime identity mismatch: current_user={runtime_current_user}, expected={expected_runtime_user}"
            )
        if runtime_dsn_user and runtime_dsn_user != expected_runtime_user:
            raise RuntimeError(
                f"runtime DSN username mismatch: username={runtime_dsn_user}, expected={expected_runtime_user}"
            )

        migration_dsn = os.getenv(args.migration_dsn_env)
        if not migration_dsn and not args.allow_missing_migration_dsn:
            raise RuntimeError(f"{args.migration_dsn_env} is required")
        if migration_dsn:
            migration_current_user = _current_user(migration_dsn)
            _print(f"{args.migration_dsn_env} current_user={migration_current_user}")
            if migration_current_user == runtime_current_user:
                raise RuntimeError(
                    "runtime and migration identities are identical; expected strict separation"
                )

        _print("PASS: runtime identity parity invariant holds")
        return 0
    except Exception as exc:
        _print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
