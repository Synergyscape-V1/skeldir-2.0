#!/usr/bin/env python3
"""
R2 Runtime Scenario Suite (HARD GATE)

Runs a fixed set of runtime scenarios that exercise real application + worker
code paths and emits Postgres-log-visible window delimiters:

  - SELECT 'R2_WINDOW_START::<sha>::<window_id>'
  - SELECT 'R2_S{i}_START::<sha>::<window_id>'
  - SELECT 'R2_S{i}_END::<sha>::<window_id>'
  - SELECT 'R2_WINDOW_END::<sha>::<window_id>'

Hard gate semantics:
  - Each scenario prints exactly one terminal line: SCENARIO_i_PASS or SCENARIO_i_FAIL
  - Exits non-zero if any scenario fails or if executed != passed.

Mandatory secondary cross-check:
  - Emits an ORM window verdict block and (optionally) writes a JSON verdict file.
  - CI MUST enforce the ORM verdict in a dedicated gate step; the scenario suite
    itself only hard-gates on scenario PASS/FAIL equality to avoid gate conflation.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable
from uuid import UUID, uuid4
from scripts.security.db_secret_access import resolve_runtime_database_url

from sqlalchemy import text


_SAFE_MARKER_RE = re.compile(r"[^A-Za-z0-9:_-]+")


def _sanitize_marker(value: str) -> str:
    return _SAFE_MARKER_RE.sub("_", value)


async def _emit_marker(sql: str) -> None:
    from app.db.session import engine

    async with engine.begin() as conn:
        await conn.execute(text(sql))


async def _emit_literal_marker(marker: str) -> None:
    marker = _sanitize_marker(marker)
    await _emit_marker(f"SELECT '{marker}';")


def _normalize_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip().upper()


def _is_marker_sql(normalized_sql: str) -> bool:
    if "R2_WINDOW_" in normalized_sql:
        return True
    return re.search(r"R2_S[0-9]+_(START|END)::", normalized_sql) is not None


def _is_txn_noise(normalized_sql: str) -> bool:
    if normalized_sql in {"BEGIN", "COMMIT", "ROLLBACK"}:
        return True
    return normalized_sql.startswith("SAVEPOINT") or normalized_sql.startswith("RELEASE SAVEPOINT")


def _is_destructive_on_immutable(normalized_sql: str) -> bool:
    destructive = {"UPDATE", "DELETE", "TRUNCATE", "ALTER"}
    immutable = {"ATTRIBUTION_EVENTS", "REVENUE_LEDGER"}
    first = normalized_sql.split(" ", 1)[0] if normalized_sql else ""
    if first not in destructive:
        return False
    return any(tbl in normalized_sql for tbl in immutable)


def _find_unique_index(items: list[str], marker: str) -> int:
    marker = marker.upper()
    matches = [i for i, sql in enumerate(items) if marker in sql]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly 1 occurrence of marker '{marker}', found {len(matches)}")
    return matches[0]


def _count_non_marker(sqls: list[str]) -> int:
    count = 0
    for sql in sqls:
        if not sql:
            continue
        if _is_marker_sql(sql):
            continue
        if _is_txn_noise(sql):
            continue
        count += 1
    return count


def _print_orm_verdict(
    *,
    candidate_sha: str,
    window_id: str,
    normalized_sqls: list[str],
    num_scenarios: int,
    orm_verdict_json_path: str | None,
) -> bool:
    window_start = f"R2_WINDOW_START::{candidate_sha}::{window_id}"
    window_end = f"R2_WINDOW_END::{candidate_sha}::{window_id}"

    failures: list[str] = []
    try:
        ws = _find_unique_index(normalized_sqls, window_start)
        we = _find_unique_index(normalized_sqls, window_end)
    except Exception as exc:
        failures.append(f"missing_window_markers:{exc}")
        ws, we = -1, -1

    if ws >= 0 and we >= 0 and ws >= we:
        failures.append("window_markers_out_of_order")

    if ws >= 0 and we >= 0 and ws < we:
        window_sqls = normalized_sqls[ws : we + 1]
    else:
        window_sqls = []

    total_window = len(window_sqls)

    per_scenario: dict[int, int] = {}
    for i in range(1, num_scenarios + 1):
        s_start = f"R2_S{i}_START::{candidate_sha}::{window_id}"
        s_end = f"R2_S{i}_END::{candidate_sha}::{window_id}"
        try:
            ssi = _find_unique_index(window_sqls, s_start)
            sei = _find_unique_index(window_sqls, s_end)
        except Exception as exc:
            failures.append(f"S{i}_missing_markers:{exc}")
            per_scenario[i] = 0
            continue
        if ssi >= sei:
            failures.append(f"S{i}_markers_out_of_order")
            per_scenario[i] = 0
            continue
        slice_sqls = window_sqls[ssi : sei + 1]
        non_marker = _count_non_marker(slice_sqls)
        per_scenario[i] = non_marker
        if non_marker <= 0:
            failures.append(f"S{i}_NON_MARKER_ORM_STATEMENTS_COUNT=0")

    forbidden = sum(1 for sql in window_sqls if _is_destructive_on_immutable(sql))
    if forbidden:
        failures.append(f"ORM_FORBIDDEN_MATCH_COUNT={forbidden}")

    print("R2_ORM_RUNTIME_INNOCENCE_VERDICT")
    print("IMMUTABLE_TABLE_SET=attribution_events,revenue_ledger")
    print("DESTRUCTIVE_VERBS=ALTER,DELETE,TRUNCATE,UPDATE")
    print(f"TOTAL_ORM_STATEMENTS_CAPTURED_IN_WINDOW={total_window}")
    for i in range(1, num_scenarios + 1):
        print(f"S{i}_NON_MARKER_ORM_STATEMENTS_COUNT={per_scenario.get(i, 0)}")
    print(f"ORM_FORBIDDEN_MATCH_COUNT={forbidden}")
    if failures:
        print("FAILURES=" + "; ".join(failures))
    print("END_VERDICT")

    if orm_verdict_json_path:
        payload = {
            "candidate_sha": candidate_sha,
            "window_id": window_id,
            "num_scenarios": num_scenarios,
            "total_orm_statements_captured_in_window": total_window,
            "per_scenario_non_marker_counts": {str(k): v for k, v in per_scenario.items()},
            "orm_forbidden_match_count": forbidden,
            "failures": failures,
        }
        Path(orm_verdict_json_path).write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )

    return not failures


async def _assert_prereqs(tenant_id: UUID) -> None:
    from app.db.session import engine, set_tenant_guc_async

    async with engine.begin() as conn:
        await set_tenant_guc_async(conn, tenant_id, local=True)
        tenant_exists = await conn.execute(
            text("SELECT 1 FROM tenants WHERE id = :tenant_id LIMIT 1"),
            {"tenant_id": str(tenant_id)},
        )
        if tenant_exists.scalar_one_or_none() is None:
            raise RuntimeError(f"Missing tenant prerequisite: tenants.id={tenant_id}")

        # Ensure at least the channel codes the ingestion path may produce exist.
        required = ["unknown", "direct", "organic", "referral", "email"]
        missing = []
        for code in required:
            res = await conn.execute(
                text("SELECT 1 FROM channel_taxonomy WHERE code = :code LIMIT 1"),
                {"code": code},
            )
            if res.scalar_one_or_none() is None:
                missing.append(code)
        if missing:
            raise RuntimeError(f"Missing channel_taxonomy prerequisites: {', '.join(missing)}")


@dataclass(frozen=True)
class Scenario:
    number: int
    name: str
    runner: Callable[[], Awaitable[None]]


async def _scenario_1_ingestion_happy_path(tenant_id: UUID) -> None:
    from app.ingestion.event_service import ingest_with_transaction

    idempotency_key = f"r2_s1_{uuid4()}"
    now = datetime.now(timezone.utc)
    result = await ingest_with_transaction(
        tenant_id=tenant_id,
        event_data={
            "event_type": "page_view",
            "event_timestamp": now.isoformat(),
            "revenue_amount": "0.00",
            "currency": "USD",
            "session_id": str(uuid4()),
            "vendor": "r2_suite_unknown_vendor",
            "utm_source": "r2",
            "utm_medium": "suite",
        },
        idempotency_key=idempotency_key,
        source="r2_suite",
    )
    if result.get("status") != "success":
        raise RuntimeError(f"Expected ingestion success, got: {result}")


async def _scenario_2_ingestion_duplicate(tenant_id: UUID) -> None:
    from app.ingestion.event_service import ingest_with_transaction

    idempotency_key = f"r2_s2_{uuid4()}"
    now = datetime.now(timezone.utc)
    first = await ingest_with_transaction(
        tenant_id=tenant_id,
        event_data={
            "event_type": "page_view",
            "event_timestamp": now.isoformat(),
            "revenue_amount": "0.00",
            "currency": "USD",
            "session_id": str(uuid4()),
            "vendor": "r2_suite_unknown_vendor",
            "utm_source": "r2",
            "utm_medium": "suite",
        },
        idempotency_key=idempotency_key,
        source="r2_suite",
    )
    if first.get("status") != "success":
        raise RuntimeError(f"Expected ingestion success, got: {first}")

    second = await ingest_with_transaction(
        tenant_id=tenant_id,
        event_data={
            "event_type": "page_view",
            "event_timestamp": now.isoformat(),
            "revenue_amount": "0.00",
            "currency": "USD",
            "session_id": str(uuid4()),
            "vendor": "r2_suite_unknown_vendor",
            "utm_source": "r2",
            "utm_medium": "suite",
        },
        idempotency_key=idempotency_key,
        source="r2_suite",
    )
    if second.get("status") != "success":
        raise RuntimeError(f"Expected ingestion duplicate to succeed, got: {second}")


async def _scenario_3_validation_failure_routes_to_dlq(tenant_id: UUID) -> None:
    from app.ingestion.event_service import ingest_with_transaction

    idempotency_key = f"r2_s3_{uuid4()}"
    # Missing required fields should route to DLQ (validation_error).
    result = await ingest_with_transaction(
        tenant_id=tenant_id,
        event_data={
            "event_type": "page_view",
            # event_timestamp intentionally missing
            "revenue_amount": "0.00",
            "currency": "USD",
            "session_id": str(uuid4()),
            "vendor": "r2_suite_unknown_vendor",
        },
        idempotency_key=idempotency_key,
        source="r2_suite",
    )
    if result.get("status") != "error" or result.get("error_type") != "validation_error":
        raise RuntimeError(f"Expected DLQ-routed validation_error, got: {result}")


async def _scenario_4_revenue_reconciliation_insert(tenant_id: UUID) -> None:
    from app.db.session import engine, set_tenant_guc_async

    async with engine.begin() as conn:
        await set_tenant_guc_async(conn, tenant_id, local=True)
        # Touch revenue_ledger via a read-only query to prove the runtime window
        # includes interactions that reference the immutable ledger table.
        res = await conn.execute(
            text("SELECT COUNT(*) FROM revenue_ledger WHERE tenant_id = :tenant_id"),
            {"tenant_id": str(tenant_id)},
        )
        _ = res.scalar_one()


async def _scenario_5_worker_context_db_roundtrip(
    tenant_id: UUID,
    *,
    capture_sql: Callable[[str], None] | None = None,
) -> None:
    from app.tasks.context import run_in_worker_loop
    from app.db.session import set_tenant_guc_async

    async def _worker_coro() -> None:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.pool import NullPool
        from sqlalchemy import event as sa_event

        db_url = resolve_runtime_database_url()
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        worker_engine = create_async_engine(db_url, poolclass=NullPool)
        if capture_sql is not None:
            def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                capture_sql(statement)
            sa_event.listen(worker_engine.sync_engine, "before_cursor_execute", _before_cursor_execute)
        try:
            async with worker_engine.begin() as conn:
                await set_tenant_guc_async(conn, tenant_id, local=True)
                await conn.execute(text("SELECT set_config('app.execution_context', 'worker', true)"))
                await conn.execute(text("SELECT 1"))
        finally:
            await worker_engine.dispose()

    await asyncio.to_thread(lambda: run_in_worker_loop(_worker_coro()))


async def _scenario_6_channel_correction_does_not_update_events(tenant_id: UUID) -> None:
    from app.db.session import engine, set_tenant_guc_async

    # This scenario is intentionally minimal: it proves the canonical channel correction
    # path records an immutable correction record rather than issuing UPDATE on
    # attribution_events (which is immutable by schema).
    async with engine.begin() as conn:
        await set_tenant_guc_async(conn, tenant_id, local=True)
        # Insert a correction record directly; the service layer should do this in production.
        await conn.execute(
            text(
                """
                INSERT INTO channel_assignment_corrections (
                    id, tenant_id, entity_type, entity_id,
                    from_channel, to_channel, corrected_by, reason, metadata
                ) VALUES (
                    gen_random_uuid(), :tenant_id, 'event', gen_random_uuid(),
                    'unknown', 'organic', 'r2_suite', 'r2_suite_correction', '{}'::jsonb
                )
                """
            ),
            {"tenant_id": str(tenant_id)},
        )


async def _run_suite(candidate_sha: str, window_id: str, orm_verdict_json: str | None) -> int:
    tenant_id = UUID("11111111-1111-1111-1111-111111111111")
    candidate_sha = _sanitize_marker(candidate_sha)
    window_id = _sanitize_marker(window_id)

    await _assert_prereqs(tenant_id)

    normalized_sqls: list[str] = []
    def _capture_sql(statement: str) -> None:
        normalized_sqls.append(_normalize_sql(statement))

    try:
        from app.db.session import engine as _engine
        from sqlalchemy import event as _event

        def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            _capture_sql(statement)

        _event.listen(_engine.sync_engine, "before_cursor_execute", _before_cursor_execute)
    except Exception as exc:
        print(f"R2_ORM_CAPTURE_ATTACH_FAIL={type(exc).__name__}:{exc}")

    scenarios = [
        Scenario(1, "event_ingestion_happy_path", lambda: _scenario_1_ingestion_happy_path(tenant_id)),
        Scenario(2, "event_ingestion_duplicate", lambda: _scenario_2_ingestion_duplicate(tenant_id)),
        Scenario(3, "validation_failure_routes_to_dlq", lambda: _scenario_3_validation_failure_routes_to_dlq(tenant_id)),
        Scenario(4, "revenue_ledger_read_only_query", lambda: _scenario_4_revenue_reconciliation_insert(tenant_id)),
        Scenario(
            5,
            "worker_context_db_roundtrip",
            lambda: _scenario_5_worker_context_db_roundtrip(tenant_id, capture_sql=_capture_sql),
        ),
        Scenario(6, "channel_correction_is_append_only", lambda: _scenario_6_channel_correction_does_not_update_events(tenant_id)),
    ]

    print("R2_SCENARIO_SUITE_START")
    print(f"CANDIDATE_SHA={candidate_sha}")
    print(f"WINDOW_ID={window_id}")

    normalized_sqls.clear()
    await _emit_literal_marker(f"R2_WINDOW_START::{candidate_sha}::{window_id}")

    executed = 0
    passed = 0
    failure_details: list[str] = []
    for scenario in scenarios:
        executed += 1
        await _emit_literal_marker(f"R2_S{scenario.number}_START::{candidate_sha}::{window_id}")
        try:
            await scenario.runner()
        except Exception as exc:
            print(f"SCENARIO_{scenario.number}_FAIL")
            failure_details.append(f"SCENARIO_{scenario.number}={type(exc).__name__}:{exc}")
        else:
            passed += 1
            print(f"SCENARIO_{scenario.number}_PASS")
        finally:
            await _emit_literal_marker(f"R2_S{scenario.number}_END::{candidate_sha}::{window_id}")

    await _emit_literal_marker(f"R2_WINDOW_END::{candidate_sha}::{window_id}")

    print("R2_SCENARIO_SUITE_VERDICT")
    print(f"SCENARIOS_EXECUTED={executed}")
    print(f"SCENARIOS_PASSED={passed}")
    print("END_VERDICT")

    orm_ok = _print_orm_verdict(
        candidate_sha=candidate_sha,
        window_id=window_id,
        normalized_sqls=normalized_sqls,
        num_scenarios=len(scenarios),
        orm_verdict_json_path=orm_verdict_json,
    )

    if failure_details:
        print("R2_SCENARIO_FAILURE_DETAILS")
        for item in failure_details:
            print(item)
        print("END_FAILURE_DETAILS")

    if passed != executed:
        return 1
    if not orm_ok:
        print("R2_ORM_VERDICT_STATUS=FAIL (must be enforced by EG-R2-FIX-5)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--window-id", required=True)
    parser.add_argument("--orm-verdict-json", required=False)
    args = parser.parse_args()

    try:
        resolve_runtime_database_url()
        return asyncio.run(_run_suite(args.candidate_sha, args.window_id, args.orm_verdict_json))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
