import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.pg_locks import build_refresh_lock_key
from app.matviews import executor, registry

logger = logging.getLogger(__name__)


def _run_sha() -> str:
    return os.getenv("GITHUB_SHA") or os.getenv("CI_COMMIT_SHA") or "local"


def _emit_gate(marker: str, payload: dict) -> None:
    payload_with_sha = {"sha": _run_sha(), **payload}
    logger.info(
        "EG_B0542_%s_BEGIN %s EG_B0542_%s_END",
        marker,
        json.dumps(payload_with_sha, separators=(",", ":"), sort_keys=True),
        marker,
    )


@pytest.mark.asyncio
async def test_b0542_gate_2a_serialization_lock(monkeypatch):
    view_name = "mv_realtime_revenue"
    tenant_id = uuid4()
    original = registry.get_entry(view_name)

    async def slow_refresh() -> None:
        await asyncio.sleep(0.25)

    patched = registry.MatviewRegistryEntry(
        name=original.name,
        kind=original.kind,
        refresh_sql=None,
        refresh_fn=slow_refresh,
        dependencies=original.dependencies,
        max_staleness_seconds=original.max_staleness_seconds,
        schedule_class=original.schedule_class,
        schedule_source=original.schedule_source,
    )
    monkeypatch.setitem(registry._REGISTRY, view_name, patched)

    results = await asyncio.gather(
        executor.refresh_single_async(view_name, tenant_id, "corr-1"),
        executor.refresh_single_async(view_name, tenant_id, "corr-1"),
    )
    outcomes = [result.outcome for result in results]
    _emit_gate(
        "G2A",
        {
            "view_name": view_name,
            "tenant_id": str(tenant_id),
            "outcomes": [outcome.value for outcome in outcomes],
            "lock_keys": [
                result.lock_key_debug.as_dict() if result.lock_key_debug else None
                for result in results
            ],
        },
    )

    assert executor.RefreshOutcome.SUCCESS in outcomes
    assert executor.RefreshOutcome.SKIPPED_LOCK_HELD in outcomes


def test_b0542_gate_2b_lock_key_correctness():
    tenant_a = uuid4()
    tenant_b = uuid4()
    view_a = "mv_realtime_revenue"
    view_b = "mv_daily_revenue_summary"

    key_a = build_refresh_lock_key(view_a, tenant_a)
    key_b = build_refresh_lock_key(view_a, tenant_b)
    key_c = build_refresh_lock_key(view_b, tenant_a)
    key_global = build_refresh_lock_key(view_a, None)

    _emit_gate(
        "G2B",
        {
            "view_a": view_a,
            "view_b": view_b,
            "tenant_a": str(tenant_a),
            "tenant_b": str(tenant_b),
            "key_a": key_a.as_dict(),
            "key_b": key_b.as_dict(),
            "key_c": key_c.as_dict(),
            "key_global": key_global.as_dict(),
        },
    )

    assert key_a.view_key == key_b.view_key
    assert key_a.tenant_key != key_b.tenant_key
    assert key_a.view_key != key_c.view_key
    assert key_global.tenant_token == "GLOBAL"


@pytest.mark.asyncio
async def test_b0542_gate_2c_executor_api_and_order(monkeypatch):
    called: list[str] = []
    tenant_id = uuid4()

    async def fake_refresh_single_async(view_name: str, tenant_id_arg, correlation_id=None):
        called.append(view_name)
        return executor.RefreshResult(
            view_name=view_name,
            tenant_id=tenant_id_arg,
            correlation_id=correlation_id,
            outcome=executor.RefreshOutcome.SUCCESS,
            started_at=datetime.now(timezone.utc),
            duration_ms=0,
            error_type=None,
            error_message=None,
            lock_key_debug=None,
        )

    entries = registry.list_entries()
    ordered = list(reversed(entries))

    monkeypatch.setattr(executor, "_topological_order", lambda _entries: ordered)
    monkeypatch.setattr(executor, "refresh_single_async", fake_refresh_single_async)

    results = await executor.refresh_all_for_tenant_async(tenant_id, "corr-2")
    expected_order = [entry.name for entry in ordered]

    _emit_gate(
        "G2C",
        {
            "tenant_id": str(tenant_id),
            "expected_order": expected_order,
            "observed_order": called,
            "results_count": len(results),
            "has_refresh_single": hasattr(executor, "refresh_single"),
            "has_refresh_all_for_tenant": hasattr(executor, "refresh_all_for_tenant"),
        },
    )

    assert called == expected_order
    assert len(results) == len(expected_order)
