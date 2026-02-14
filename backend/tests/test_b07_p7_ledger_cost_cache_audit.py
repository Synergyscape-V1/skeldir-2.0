from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.core.identity import SYSTEM_USER_ID
from app.db.session import engine, get_session
from app.llm.budget_policy import PRICING_CATALOG, BudgetPolicyEngine
from app.schemas.llm_payloads import LLMTaskPayload
from app.workers.llm import _PROVIDER_BOUNDARY, generate_explanation


def _payload(
    tenant_id: UUID,
    user_id: UUID,
    *,
    request_id: str,
    prompt: dict,
    max_cost_cents: int = 20,
) -> LLMTaskPayload:
    return LLMTaskPayload(
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=request_id,
        request_id=request_id,
        prompt=prompt,
        max_cost_cents=max_cost_cents,
    )


def _artifact_dir() -> Path | None:
    raw = os.getenv("B07_P2_ARTIFACT_DIR")
    if not raw:
        return None
    path = Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_artifact(name: str, payload: dict) -> None:
    out_dir = _artifact_dir()
    if out_dir is None:
        return
    (out_dir / name).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


async def _discover_llm_tenant_tables(conn) -> list[str]:
    rows = await conn.execute(
        text(
            """
            SELECT DISTINCT table_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name LIKE 'llm_%'
              AND column_name = 'tenant_id'
            ORDER BY table_name
            """
        )
    )
    return [str(v) for v in rows.scalars().all()]


async def _table_columns(conn, table_name: str) -> list[dict]:
    rows = await conn.execute(
        text(
            """
            SELECT
                column_name,
                data_type,
                udt_name,
                is_nullable,
                column_default,
                is_identity
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
            ORDER BY ordinal_position
            """
        ),
        {"table_name": table_name},
    )
    return [dict(r) for r in rows.mappings().all()]


def _column_value(*, table_name: str, column: str, data_type: str, marker: str, tenant_id: UUID, user_id: UUID) -> object:
    now = datetime.now(UTC)
    if column == "id":
        return str(uuid4())
    if column == "tenant_id":
        return str(tenant_id)
    if column == "user_id":
        return str(user_id)
    if column in {"month"}:
        return date(now.year, now.month, 1)
    if column in {"hour_start"}:
        return now.replace(minute=0, second=0, microsecond=0)
    if column in {"created_at", "updated_at", "opened_at", "last_trip_at", "disabled_until"}:
        return now
    if column in {"request_id", "correlation_id"}:
        return f"{table_name}-{column}-{marker}"
    if column == "endpoint":
        return "app.tasks.llm.explanation"
    if column in {"requested_model", "resolved_model", "model", "chosen_model"}:
        return "stub:model"
    if column in {"provider", "chosen_provider"}:
        return "stub"
    if column in {"decision"}:
        return "ALLOW"
    if column == "state":
        if table_name == "llm_budget_reservations":
            return "reserved"
        if table_name == "llm_breaker_state":
            return "closed"
        return "reserved"
    if column == "status":
        return "success"
    if column == "breaker_state":
        return "closed"
    if column == "breaker_key":
        return "llm-provider"
    if column in {"reason", "routing_reason"}:
        return "phase7_probe"
    if column == "prompt_fingerprint":
        return hashlib.sha256(f"probe:{marker}".encode("utf-8")).hexdigest()
    if column == "cache_key":
        return hashlib.sha256(f"cache:{marker}".encode("utf-8")).hexdigest()
    if column == "response_text":
        return f"response-{marker}"
    if column == "chosen_tier":
        return "cheap"
    if column == "policy_id":
        return "probe-policy"
    if column == "policy_version":
        return "1"
    if column == "model_breakdown":
        return json.dumps({"stub:model": {"calls": 1, "cost_cents": 0}})
    if data_type in {"integer", "bigint", "smallint"}:
        if column == "complexity_bucket":
            return 1
        return 0
    if data_type == "boolean":
        return False
    if data_type in {"json", "jsonb"}:
        return "{}"
    if data_type in {"uuid"}:
        return str(uuid4())
    if data_type in {"timestamp with time zone", "timestamp without time zone"}:
        return now
    if data_type == "date":
        return date(now.year, now.month, 1)
    return f"{column}-{marker}"


@pytest.mark.asyncio
async def test_p7_runtime_probe_discovers_llm_tables_and_validates_insert_select_rls(test_tenant_pair):
    tenant_a, tenant_b = test_tenant_pair
    user_id = uuid4()
    marker = uuid4().hex[:10]

    async with engine.begin() as conn:
        current_user = str((await conn.execute(text("SELECT current_user"))).scalar_one())
        expected_user = os.getenv("EXPECTED_RUNTIME_DB_USER")
        if expected_user:
            assert current_user == expected_user

        discovered = await _discover_llm_tenant_tables(conn)
        required_tables = {"llm_api_calls", "llm_call_audit"}
        assert required_tables.issubset(set(discovered))

        privilege_matrix: list[dict] = []
        probe_rows: list[dict] = []
        for table_name in discovered:
            privileges = (
                await conn.execute(
                    text(
                        """
                        SELECT
                            has_table_privilege(current_user, :table_fqn, 'SELECT') AS can_select,
                            has_table_privilege(current_user, :table_fqn, 'INSERT') AS can_insert
                        """
                    ),
                    {"table_fqn": f"public.{table_name}"},
                )
            ).mappings().one()
            privilege_matrix.append(
                {
                    "table": table_name,
                    "can_select": bool(privileges["can_select"]),
                    "can_insert": bool(privileges["can_insert"]),
                }
            )
            assert bool(privileges["can_select"]), f"runtime user missing SELECT on {table_name}"
            assert bool(privileges["can_insert"]), f"runtime user missing INSERT on {table_name}"

            cols = await _table_columns(conn, table_name)
            required_insert_cols = [
                c for c in cols if c["is_nullable"] == "NO" and c["column_default"] is None and c["is_identity"] != "YES"
            ]
            params: dict[str, object] = {}
            for col in required_insert_cols:
                col_name = str(col["column_name"])
                params[col_name] = _column_value(
                    table_name=table_name,
                    column=col_name,
                    data_type=str(col["data_type"]),
                    marker=marker,
                    tenant_id=tenant_a,
                    user_id=user_id,
                )
            column_names = {str(c["column_name"]) for c in cols}
            if "tenant_id" in column_names:
                params["tenant_id"] = str(tenant_a)
            if "user_id" in column_names:
                params["user_id"] = str(user_id)
            if "id" not in params and any(str(c["column_name"]) == "id" for c in cols):
                params["id"] = str(uuid4())

            insert_cols = ", ".join(params.keys())
            insert_vals = ", ".join(f":{name}" for name in params.keys())
            row_id = str(params.get("id"))

            tx = await conn.begin_nested()
            try:
                await conn.execute(text("SELECT set_config('app.current_tenant_id', :tid, false)"), {"tid": str(tenant_a)})
                await conn.execute(text("SELECT set_config('app.current_user_id', :uid, false)"), {"uid": str(user_id)})
                await conn.execute(text(f"INSERT INTO {table_name} ({insert_cols}) VALUES ({insert_vals})"), params)

                visible_same = int(
                    (
                        await conn.execute(
                            text(f"SELECT COUNT(*) FROM {table_name} WHERE id = :row_id"),
                            {"row_id": row_id},
                        )
                    ).scalar_one()
                )
                await conn.execute(text("SELECT set_config('app.current_tenant_id', :tid, false)"), {"tid": str(tenant_b)})
                await conn.execute(text("SELECT set_config('app.current_user_id', :uid, false)"), {"uid": str(user_id)})
                visible_cross = int(
                    (
                        await conn.execute(
                            text(f"SELECT COUNT(*) FROM {table_name} WHERE id = :row_id"),
                            {"row_id": row_id},
                        )
                    ).scalar_one()
                )
                probe_rows.append({"table": table_name, "visible_same": visible_same, "visible_cross": visible_cross})
                assert visible_same == 1
                assert visible_cross == 0
            finally:
                await tx.rollback()

        _write_artifact(
            "p7_runtime_probe.json",
            {
                "current_user": current_user,
                "tenant_tables": discovered,
                "privileges": privilege_matrix,
                "probe_rows": probe_rows,
            },
        )


@pytest.mark.asyncio
async def test_p7_outcome_matrix_emits_complete_ledger_and_audit_and_no_raw_prompt_persistence(monkeypatch, caplog, test_tenant_pair):
    tenant_a, tenant_b = test_tenant_pair
    user_id = SYSTEM_USER_ID
    canary = f"PHASE7_RAW_PROMPT_CANARY_{uuid4().hex}"

    monkeypatch.setattr(settings, "LLM_MONTHLY_CAP_CENTS", 50, raising=False)
    monkeypatch.setattr(settings, "LLM_HOURLY_SHUTOFF_CENTS", 1_000, raising=False)
    monkeypatch.setattr(settings, "LLM_PROVIDER_TIMEOUT_MS", 10, raising=False)

    outcomes: dict[str, str] = {}
    calls = {"provider": 0}

    async def _provider_stub(*, requested_model, prompt, reservation):
        calls["provider"] += 1
        if prompt.get("force_provider_exception"):
            raise RuntimeError("phase7_provider_exception")
        if prompt.get("force_provider_slow"):
            import asyncio

            await asyncio.sleep(0.05)
        digest = hashlib.sha256(json.dumps(prompt, sort_keys=True).encode("utf-8")).hexdigest()[:12]
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": f"stub:{digest}",
            "reasoning_trace": {"digest": digest},
            "response_metadata": {"source": "phase7"},
            "usage": {"input_tokens": 2, "output_tokens": 1, "cost_cents": 1},
        }

    async def _breaker_open(*args, **kwargs):
        return True

    async def _breaker_closed(*args, **kwargs):
        return False

    monkeypatch.setattr(_PROVIDER_BOUNDARY, "_provider_call", _provider_stub, raising=True)
    monkeypatch.setattr(_PROVIDER_BOUNDARY, "_breaker_open", _breaker_closed, raising=True)

    async with get_session(tenant_id=tenant_a, user_id=user_id) as session:
        success_id = f"p7-success-{uuid4().hex[:8]}"
        success = await generate_explanation(
            _payload(
                tenant_a,
                user_id,
                request_id=success_id,
                prompt={"input": canary, "cache_enabled": False},
                max_cost_cents=3,
            ),
            session=session,
        )
        outcomes[success_id] = success["status"]

        kill_id = f"p7-kill-{uuid4().hex[:8]}"
        kill = await generate_explanation(
            _payload(tenant_a, user_id, request_id=kill_id, prompt={"kill_switch": True, "cache_enabled": False}),
            session=session,
        )
        outcomes[kill_id] = kill["status"]

        breaker_id = f"p7-breaker-{uuid4().hex[:8]}"
        monkeypatch.setattr(_PROVIDER_BOUNDARY, "_breaker_open", _breaker_open, raising=True)
        breaker = await generate_explanation(
            _payload(tenant_a, user_id, request_id=breaker_id, prompt={"cache_enabled": False}),
            session=session,
        )
        outcomes[breaker_id] = breaker["status"]
        monkeypatch.setattr(_PROVIDER_BOUNDARY, "_breaker_open", _breaker_closed, raising=True)

        timeout_id = f"p7-timeout-{uuid4().hex[:8]}"
        timeout = await generate_explanation(
            _payload(
                tenant_a,
                user_id,
                request_id=timeout_id,
                prompt={"force_provider_slow": True, "cache_enabled": False},
                max_cost_cents=4,
            ),
            session=session,
        )
        outcomes[timeout_id] = timeout["status"]

        budget_id = f"p7-budget-{uuid4().hex[:8]}"
        budget = await generate_explanation(
            _payload(
                tenant_a,
                user_id,
                request_id=budget_id,
                prompt={"cache_enabled": False},
                max_cost_cents=500,
            ),
            session=session,
        )
        outcomes[budget_id] = budget["status"]

        error_id = f"p7-error-{uuid4().hex[:8]}"
        error = await generate_explanation(
            _payload(
                tenant_a,
                user_id,
                request_id=error_id,
                prompt={"force_provider_exception": True, "cache_enabled": False},
                max_cost_cents=4,
            ),
            session=session,
        )
        outcomes[error_id] = error["status"]

        cache_prompt = {"input": "repeat-me", "cache_enabled": True, "cache_watermark": 11}
        cache_seed_id = f"p7-cache-seed-{uuid4().hex[:8]}"
        cache_hit_id = f"p7-cache-hit-{uuid4().hex[:8]}"
        seeded = await generate_explanation(
            _payload(tenant_a, user_id, request_id=cache_seed_id, prompt=cache_prompt, max_cost_cents=3),
            session=session,
        )
        hit = await generate_explanation(
            _payload(tenant_a, user_id, request_id=cache_hit_id, prompt=cache_prompt, max_cost_cents=3),
            session=session,
        )
        outcomes[cache_seed_id] = seeded["status"]
        outcomes[cache_hit_id] = hit["status"]

    assert success["status"] == "accepted"
    assert kill["status"] == "blocked"
    assert breaker["status"] == "blocked"
    assert timeout["status"] == "failed"
    assert budget["status"] == "blocked"
    assert error["status"] == "failed"
    assert seeded["status"] == "accepted" and seeded["was_cached"] is False
    assert hit["status"] == "accepted" and hit["was_cached"] is True

    request_ids = list(outcomes.keys())
    async with get_session(tenant_id=tenant_a, user_id=user_id) as session:
        api_rows = (
            await session.execute(
                text(
                    """
                    SELECT request_id, status, block_reason, failure_reason, provider_attempted, was_cached
                    FROM llm_api_calls
                    WHERE tenant_id = :tenant_id
                      AND user_id = :user_id
                      AND endpoint = 'app.tasks.llm.explanation'
                      AND request_id = ANY(:request_ids)
                    """
                ),
                {"tenant_id": str(tenant_a), "user_id": str(user_id), "request_ids": request_ids},
            )
        ).mappings().all()
        audit_rows = (
            await session.execute(
                text(
                    """
                    SELECT request_id, decision, reason, prompt_fingerprint
                    FROM llm_call_audit
                    WHERE tenant_id = :tenant_id
                      AND user_id = :user_id
                      AND request_id = ANY(:request_ids)
                    """
                ),
                {"tenant_id": str(tenant_a), "user_id": str(user_id), "request_ids": request_ids},
            )
        ).mappings().all()
        canary_leak_count = int(
            (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM llm_api_calls
                        WHERE tenant_id = :tenant_id
                          AND user_id = :user_id
                          AND request_id = :request_id
                          AND (
                            COALESCE(request_metadata_ref::text, '') LIKE :needle
                            OR COALESCE(response_metadata_ref::text, '') LIKE :needle
                            OR COALESCE(reasoning_trace_ref::text, '') LIKE :needle
                          )
                        """
                    ),
                    {"tenant_id": str(tenant_a), "user_id": str(user_id), "request_id": success_id, "needle": f"%{canary}%"},
                )
            ).scalar_one()
        )

    assert len(api_rows) == len(request_ids)
    assert len(audit_rows) == len(request_ids)
    assert all(row["prompt_fingerprint"] for row in audit_rows)
    assert canary_leak_count == 0
    assert canary not in caplog.text

    async with get_session(tenant_id=tenant_b, user_id=user_id) as session:
        cross_api = int(
            (
                await session.execute(
                    text("SELECT COUNT(*) FROM llm_api_calls WHERE request_id = ANY(:request_ids)"),
                    {"request_ids": request_ids},
                )
            ).scalar_one()
        )
        cross_audit = int(
            (
                await session.execute(
                    text("SELECT COUNT(*) FROM llm_call_audit WHERE request_id = ANY(:request_ids)"),
                    {"request_ids": request_ids},
                )
            ).scalar_one()
        )
    assert cross_api == 0
    assert cross_audit == 0

    _write_artifact(
        "p7_outcome_matrix_summary.json",
        {
            "provider_calls": calls["provider"],
            "outcomes": outcomes,
            "api_rows": [dict(r) for r in api_rows],
            "audit_rows": [dict(r) for r in audit_rows],
        },
    )


def _expected_cost_cents(input_tokens: int, output_tokens: int, model: str) -> int:
    pricing = PRICING_CATALOG[model]
    input_cost = (Decimal(input_tokens) / Decimal(1000)) * pricing.input_per_1k_usd
    output_cost = (Decimal(output_tokens) / Decimal(1000)) * pricing.output_per_1k_usd
    usd = (input_cost + output_cost).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return int((usd * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def test_p7_cost_golden_vectors_unit_correctness_non_vacuous():
    engine_instance = BudgetPolicyEngine()
    vectors = [
        ("gpt-4", 1000, 1000),
        ("gpt-4-turbo", 2500, 750),
        ("claude-3-haiku", 4000, 2000),
    ]
    for model, in_tokens, out_tokens in vectors:
        expected = _expected_cost_cents(in_tokens, out_tokens, model)
        observed = int(
            engine_instance.estimate_cost_cents(
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                model=model,
            )
        )
        assert observed == expected
        assert observed >= 0
        if expected > 0:
            assert observed != expected * 100, "regression trap: cents multiplied by 100"
            assert observed != max(0, expected // 100), "regression trap: cents divided by 100"


@pytest.mark.asyncio
async def test_p7_rollup_reconciliation_sum_calls_equals_monthly_rollup(test_tenant):
    tenant_id = test_tenant
    user_id = SYSTEM_USER_ID
    costs = [2, 3, 5, 7]

    async with get_session(tenant_id=tenant_id, user_id=user_id) as session:
        for idx, cents in enumerate(costs):
            rid = f"p7-reconcile-{idx}-{uuid4().hex[:8]}"
            await generate_explanation(
                _payload(
                    tenant_id,
                    user_id,
                    request_id=rid,
                    prompt={"simulated_cost_cents": cents, "cache_enabled": False},
                    max_cost_cents=cents,
                ),
                session=session,
            )

    month = date(datetime.now(UTC).year, datetime.now(UTC).month, 1)
    async with get_session(tenant_id=tenant_id, user_id=user_id) as session:
        raw_sum = int(
            (
                await session.execute(
                    text(
                        """
                        SELECT COALESCE(SUM(cost_cents), 0)
                        FROM llm_api_calls
                        WHERE tenant_id = :tenant_id
                          AND user_id = :user_id
                          AND endpoint = 'app.tasks.llm.explanation'
                          AND created_at >= :month_start
                          AND status = 'success'
                        """
                    ),
                    {"tenant_id": str(tenant_id), "user_id": str(user_id), "month_start": month},
                )
            ).scalar_one()
        )
        rollup_sum = int(
            (
                await session.execute(
                    text(
                        """
                        SELECT COALESCE(SUM(total_cost_cents), 0)
                        FROM llm_monthly_costs
                        WHERE tenant_id = :tenant_id
                          AND user_id = :user_id
                          AND month = :month_start
                        """
                    ),
                    {"tenant_id": str(tenant_id), "user_id": str(user_id), "month_start": month},
                )
            ).scalar_one()
        )
    assert raw_sum == sum(costs)
    assert rollup_sum == raw_sum

    _write_artifact(
        "p7_rollup_reconciliation.json",
        {
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "month": str(month),
            "raw_sum_cost_cents": raw_sum,
            "rollup_sum_cost_cents": rollup_sum,
        },
    )


@pytest.mark.asyncio
async def test_p7_cache_performance_binding_and_negative_controls(monkeypatch, test_tenant):
    tenant_id = test_tenant
    user_id = SYSTEM_USER_ID

    monkeypatch.setattr(settings, "LLM_MONTHLY_CAP_CENTS", 20_000, raising=False)
    monkeypatch.setattr(settings, "LLM_HOURLY_SHUTOFF_CENTS", 20_000, raising=False)

    calls = {"count": 0}

    async def _provider_stub(*, requested_model, prompt, reservation):
        calls["count"] += 1
        digest = hashlib.sha256(json.dumps(prompt, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": f"out:{digest}",
            "reasoning_trace": {"digest": digest},
            "response_metadata": {"source": "cache_perf_probe"},
            "usage": {"input_tokens": 1, "output_tokens": 1, "cost_cents": 1},
        }

    monkeypatch.setattr(_PROVIDER_BOUNDARY, "_provider_call", _provider_stub, raising=True)

    repeated_total = 100
    unique_prompts = 40
    repeat_pool = 20
    hits = 0
    calls["count"] = 0
    output_by_prompt: dict[str, str] = {}
    async with get_session(tenant_id=tenant_id, user_id=user_id) as session:
        for i in range(repeated_total):
            prompt_index = i if i < unique_prompts else i % repeat_pool
            prompt = {"input": f"cache-workload-{prompt_index}", "cache_enabled": True, "cache_watermark": 3}
            request_id = f"p7-perf-{i}-{uuid4().hex[:6]}"
            result = await generate_explanation(
                _payload(tenant_id, user_id, request_id=request_id, prompt=prompt, max_cost_cents=2),
                session=session,
            )
            if result["was_cached"]:
                hits += 1
            output_by_prompt.setdefault(prompt["input"], result["explanation"])
            assert output_by_prompt[prompt["input"]] == result["explanation"]

    hit_rate = hits / repeated_total
    provider_calls = calls["count"]
    assert hit_rate >= 0.40
    assert provider_calls <= unique_prompts + 5

    unique_hits = 0
    calls["count"] = 0
    unique_total = 30
    async with get_session(tenant_id=tenant_id, user_id=user_id) as session:
        for i in range(unique_total):
            prompt = {"input": f"unique-{uuid4().hex}-{i}", "cache_enabled": True, "cache_watermark": 3}
            request_id = f"p7-unique-{i}-{uuid4().hex[:6]}"
            result = await generate_explanation(
                _payload(tenant_id, user_id, request_id=request_id, prompt=prompt, max_cost_cents=2),
                session=session,
            )
            if result["was_cached"]:
                unique_hits += 1
    assert unique_hits <= 1
    assert calls["count"] == unique_total

    calls["count"] = 0
    disabled_total = 20
    async with get_session(tenant_id=tenant_id, user_id=user_id) as session:
        for i in range(disabled_total):
            prompt = {"input": "same-but-disabled", "cache_enabled": False}
            request_id = f"p7-disabled-{i}-{uuid4().hex[:6]}"
            result = await generate_explanation(
                _payload(tenant_id, user_id, request_id=request_id, prompt=prompt, max_cost_cents=2),
                session=session,
            )
            assert result["was_cached"] is False
    assert calls["count"] == disabled_total

    _write_artifact(
        "p7_cache_performance.json",
        {
            "workload_total": repeated_total,
            "workload_unique_prompts": unique_prompts,
            "hit_rate": hit_rate,
            "provider_call_count": provider_calls,
            "negative_unique_hits": unique_hits,
            "negative_unique_provider_calls": unique_total,
            "negative_cache_disabled_provider_calls": disabled_total,
        },
    )
