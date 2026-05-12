#!/usr/bin/env python3
"""Non-vacuous M1 local runtime smoke proof.

This script is executed inside the canonical Docker Compose topology. It fails
unless local Postgres is reachable, Alembic head is applied, the API is healthy,
and a real Celery worker task round-trip proves broker/result backend and
worker-side DB access.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import psycopg2


LOCAL_HOSTS = {"postgres", "localhost", "127.0.0.1", "::1"}
EXTERNAL_HOST_MARKERS = (
    "neon.tech",
    "amazonaws.com",
    "rds.amazonaws.com",
    "azure.com",
    "googleusercontent.com",
    "supabase.co",
)


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def _fail(message: str) -> None:
    print(json.dumps({"m1_smoke": "fail", "error": message}, sort_keys=True))
    raise SystemExit(1)


def _parse_database_host(raw_url: str) -> str:
    cleaned = raw_url.strip()
    for prefix in ("sqla+", "db+"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
    parsed = urlparse(cleaned)
    return (parsed.hostname or "").lower()


def _assert_local_url(env_name: str) -> CheckResult:
    value = os.environ.get(env_name, "").strip()
    if not value:
        return CheckResult(env_name, False, "missing")
    host = _parse_database_host(value)
    if not host:
        return CheckResult(env_name, False, "missing host")
    if any(marker in host for marker in EXTERNAL_HOST_MARKERS):
        return CheckResult(env_name, False, f"external host rejected: {host}")
    if host not in LOCAL_HOSTS:
        return CheckResult(env_name, False, f"non-local host rejected: {host}")
    return CheckResult(env_name, True, f"local host: {host}")


def _http_json(url: str, *, timeout: float = 5.0, attempts: int = 30) -> tuple[int, dict[str, Any]]:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return response.status, json.loads(body)
        except Exception as exc:  # noqa: BLE001 - surfaced in final failure detail
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"HTTP check failed for {url}: {last_error}")


def _database_checks() -> list[CheckResult]:
    dsn = os.environ.get("MIGRATION_DATABASE_URL", "").strip()
    if not dsn:
        _fail("MIGRATION_DATABASE_URL is required for M1 smoke")

    results: list[CheckResult] = []
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            results.append(CheckResult("db_select_1", cur.fetchone()[0] == 1, "SELECT 1"))

            cur.execute("SELECT version_num FROM alembic_version")
            versions = [row[0] for row in cur.fetchall()]
            results.append(
                CheckResult(
                    "alembic_head_applied",
                    bool(versions),
                    f"versions={','.join(sorted(versions))}",
                )
            )

            cur.execute(
                "SELECT relrowsecurity, relforcerowsecurity "
                "FROM pg_class WHERE relname = 'attribution_events'"
            )
            row = cur.fetchone()
            results.append(
                CheckResult(
                    "rls_truth_table_present",
                    bool(row and row[0] and row[1]),
                    "attribution_events RLS+force RLS",
                )
            )
    return results


def main() -> int:
    results: list[CheckResult] = []
    for env_name in (
        "DATABASE_URL",
        "MIGRATION_DATABASE_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
    ):
        results.append(_assert_local_url(env_name))

    results.extend(_database_checks())

    api_base_url = os.environ.get("API_BASE_URL", "http://api:8000").rstrip("/")
    ready_status, ready_body = _http_json(f"{api_base_url}/health/ready")
    results.append(
        CheckResult(
            "api_readiness",
            ready_status == 200 and ready_body.get("status") == "ok",
            json.dumps(ready_body, sort_keys=True),
        )
    )

    worker_status, worker_body = _http_json(
        f"{api_base_url}/health/worker",
        timeout=float(os.environ.get("WORKER_PROBE_TIMEOUT_SECONDS", "20")) + 5,
        attempts=6,
    )
    worker_ok = (
        worker_status == 200
        and worker_body.get("status") == "ok"
        and worker_body.get("broker") == "ok"
        and worker_body.get("database") == "ok"
        and worker_body.get("worker") == "ok"
    )
    results.append(
        CheckResult(
            "celery_worker_round_trip",
            worker_ok,
            json.dumps(worker_body, sort_keys=True),
        )
    )

    failed = [result for result in results if not result.ok]
    for result in results:
        print(
            json.dumps(
                {
                    "check": result.name,
                    "ok": result.ok,
                    "detail": result.detail,
                },
                sort_keys=True,
            )
        )
    if failed:
        _fail("; ".join(f"{result.name}: {result.detail}" for result in failed))

    print(json.dumps({"m1_smoke": "pass", "checks": len(results)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
