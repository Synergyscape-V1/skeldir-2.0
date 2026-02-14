from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.identity import SYSTEM_USER_ID
from app.db.session import get_session
from app.models.llm import (
    LLMBudgetReservation,
    LLMHourlyShutoffState,
    LLMApiCall,
    LLMMonthlyBudgetState,
)
from app.schemas.llm_payloads import LLMTaskPayload
from app.workers.llm import _PROVIDER_BOUNDARY, generate_explanation


def _payload(
    tenant_id,
    *,
    request_id: str,
    prompt: dict,
    max_cost_cents: int = 20,
) -> LLMTaskPayload:
    return LLMTaskPayload(
        tenant_id=tenant_id,
        user_id=SYSTEM_USER_ID,
        correlation_id=request_id,
        request_id=request_id,
        prompt=prompt,
        max_cost_cents=max_cost_cents,
    )


@pytest.mark.asyncio
async def test_p3_cache_hit_and_watermark_invalidation(test_tenant):
    base_prompt = {
        "simulated_output_text": "cache-me",
        "cache_enabled": True,
        "cache_watermark": 7,
    }

    first_id = str(uuid4())
    second_id = str(uuid4())
    third_id = str(uuid4())

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        first = await generate_explanation(
            _payload(test_tenant, request_id=first_id, prompt=base_prompt),
            session=session,
        )
        second = await generate_explanation(
            _payload(test_tenant, request_id=second_id, prompt=base_prompt),
            session=session,
        )
        invalidating_prompt = {**base_prompt, "cache_watermark": 8}
        third = await generate_explanation(
            _payload(test_tenant, request_id=third_id, prompt=invalidating_prompt),
            session=session,
        )

    assert first["status"] == "accepted"
    assert first["was_cached"] is False
    assert second["status"] == "accepted"
    assert second["was_cached"] is True
    assert third["status"] == "accepted"
    assert third["was_cached"] is False


@pytest.mark.asyncio
async def test_p3_reservation_concurrency_safety(monkeypatch, test_tenant):
    monkeypatch.setattr(settings, "LLM_MONTHLY_CAP_CENTS", 40, raising=False)
    monkeypatch.setattr(settings, "LLM_HOURLY_SHUTOFF_CENTS", 10_000, raising=False)
    monkeypatch.setattr(settings, "LLM_BREAKER_FAILURE_THRESHOLD", 99, raising=False)

    async def _invoke(i: int):
        rid = f"p3-concurrency-{i}-{uuid4().hex[:8]}"
        prompt = {
            "simulated_delay_ms": 250,
            "simulated_cost_cents": 1,
            "cache_enabled": False,
        }
        async with get_session(
            tenant_id=test_tenant, user_id=SYSTEM_USER_ID
        ) as session:
            return await generate_explanation(
                _payload(test_tenant, request_id=rid, prompt=prompt, max_cost_cents=20),
                session=session,
            )

    results = await asyncio.gather(*[_invoke(i) for i in range(5)])
    allowed = [r for r in results if r["status"] == "accepted"]
    blocked = [r for r in results if r["status"] == "blocked"]

    assert len(allowed) == 2
    assert len(blocked) == 3

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        month = date(
            datetime.now(timezone.utc).year, datetime.now(timezone.utc).month, 1
        )
        budget = (
            (
                await session.execute(
                    select(LLMMonthlyBudgetState).where(
                        LLMMonthlyBudgetState.tenant_id == test_tenant,
                        LLMMonthlyBudgetState.user_id == SYSTEM_USER_ID,
                        LLMMonthlyBudgetState.month == month,
                    )
                )
            )
            .scalars()
            .one()
        )
        assert int(budget.spent_cents) + int(budget.reserved_cents) <= 40

        attempted = (
            (
                await session.execute(
                    select(LLMApiCall).where(
                        LLMApiCall.tenant_id == test_tenant,
                        LLMApiCall.endpoint == "app.tasks.llm.explanation",
                    )
                )
            )
            .scalars()
            .all()
        )
        provider_attempt_count = sum(1 for row in attempted if row.provider_attempted)
        assert provider_attempt_count == len(allowed)


@pytest.mark.asyncio
async def test_p3_hourly_shutoff_distinct_from_monthly(monkeypatch, test_tenant):
    monkeypatch.setattr(settings, "LLM_MONTHLY_CAP_CENTS", 2500, raising=False)
    monkeypatch.setattr(settings, "LLM_HOURLY_SHUTOFF_CENTS", 2, raising=False)

    prompt = {"simulated_cost_cents": 1, "cache_enabled": False}
    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        one = await generate_explanation(
            _payload(test_tenant, request_id=str(uuid4()), prompt=prompt),
            session=session,
        )
        two = await generate_explanation(
            _payload(test_tenant, request_id=str(uuid4()), prompt=prompt),
            session=session,
        )
        three = await generate_explanation(
            _payload(test_tenant, request_id=str(uuid4()), prompt=prompt),
            session=session,
        )

    assert one["status"] == "accepted"
    assert two["status"] == "accepted"
    assert three["status"] == "blocked"
    assert three["blocked_reason"] in {
        "hourly_threshold_exceeded",
        "hourly_shutoff_active",
    }

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        shutoff_rows = (
            (
                await session.execute(
                    select(LLMHourlyShutoffState).where(
                        LLMHourlyShutoffState.tenant_id == test_tenant,
                        LLMHourlyShutoffState.user_id == SYSTEM_USER_ID,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert any(row.is_shutoff for row in shutoff_rows)


@pytest.mark.asyncio
async def test_p3_kill_switch_blocks_without_provider_attempt_non_vacuous(
    monkeypatch, test_tenant
):
    monkeypatch.setattr(settings, "LLM_HOURLY_SHUTOFF_CENTS", 10_000, raising=False)
    monkeypatch.setattr(settings, "LLM_MONTHLY_CAP_CENTS", 10_000, raising=False)

    calls = {"count": 0}

    async def _spy_provider(*, requested_model, prompt, reservation):
        calls["count"] += 1
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": "ok",
            "reasoning_trace": {"trace_type": "spy"},
            "response_metadata": {"source": "spy"},
            "usage": {"input_tokens": 1, "output_tokens": 1, "cost_cents": 1},
        }

    monkeypatch.setattr(
        _PROVIDER_BOUNDARY, "_provider_call", _spy_provider, raising=True
    )

    kill_request_id = str(uuid4())
    pass_request_id = str(uuid4())
    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        blocked = await generate_explanation(
            _payload(
                test_tenant,
                request_id=kill_request_id,
                prompt={"kill_switch": True, "cache_enabled": False},
            ),
            session=session,
        )
        allowed = await generate_explanation(
            _payload(
                test_tenant,
                request_id=pass_request_id,
                prompt={"kill_switch": False, "cache_enabled": False},
            ),
            session=session,
        )

    assert blocked["status"] == "blocked"
    assert blocked["blocked_reason"] == "provider_kill_switch"
    assert allowed["status"] == "accepted"
    assert calls["count"] == 1

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        kill_row = (
            (
                await session.execute(
                    select(LLMApiCall).where(
                        LLMApiCall.tenant_id == test_tenant,
                        LLMApiCall.request_id == kill_request_id,
                        LLMApiCall.endpoint == "app.tasks.llm.explanation",
                    )
                )
            )
            .scalars()
            .one()
        )
        pass_row = (
            (
                await session.execute(
                    select(LLMApiCall).where(
                        LLMApiCall.tenant_id == test_tenant,
                        LLMApiCall.request_id == pass_request_id,
                        LLMApiCall.endpoint == "app.tasks.llm.explanation",
                    )
                )
            )
            .scalars()
            .one()
        )
        assert kill_row.provider_attempted is False
        assert int(kill_row.cost_cents) == 0
        assert kill_row.cost_usd == 0
        assert pass_row.provider_attempted is True


@pytest.mark.asyncio
async def test_p3_breaker_open_blocks_without_provider_attempt_non_vacuous(
    monkeypatch, test_tenant
):
    monkeypatch.setattr(settings, "LLM_HOURLY_SHUTOFF_CENTS", 10_000, raising=False)
    monkeypatch.setattr(settings, "LLM_MONTHLY_CAP_CENTS", 10_000, raising=False)

    calls = {"count": 0}

    async def _spy_provider(*, requested_model, prompt, reservation):
        calls["count"] += 1
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": "ok",
            "reasoning_trace": {"trace_type": "spy"},
            "response_metadata": {"source": "spy"},
            "usage": {"input_tokens": 1, "output_tokens": 1, "cost_cents": 1},
        }

    async def _breaker_open(*args, **kwargs):
        return True

    async def _breaker_closed(*args, **kwargs):
        return False

    monkeypatch.setattr(
        _PROVIDER_BOUNDARY, "_provider_call", _spy_provider, raising=True
    )
    monkeypatch.setattr(
        _PROVIDER_BOUNDARY, "_breaker_open", _breaker_open, raising=True
    )

    blocked_request_id = str(uuid4())
    allowed_request_id = str(uuid4())
    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        blocked = await generate_explanation(
            _payload(
                test_tenant,
                request_id=blocked_request_id,
                prompt={"cache_enabled": False},
            ),
            session=session,
        )
        monkeypatch.setattr(
            _PROVIDER_BOUNDARY, "_breaker_open", _breaker_closed, raising=True
        )
        allowed = await generate_explanation(
            _payload(
                test_tenant,
                request_id=allowed_request_id,
                prompt={"cache_enabled": False},
            ),
            session=session,
        )

    assert blocked["status"] == "blocked"
    assert blocked["blocked_reason"] == "breaker_open"
    assert allowed["status"] == "accepted"
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_p3_retry_idempotency_no_double_debit(test_tenant):
    request_id = str(uuid4())
    prompt = {"simulated_cost_cents": 2, "cache_enabled": False}
    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        first = await generate_explanation(
            _payload(test_tenant, request_id=request_id, prompt=prompt),
            session=session,
            force_failure=True,
        )
        retry = await generate_explanation(
            _payload(test_tenant, request_id=request_id, prompt=prompt),
            session=session,
        )

    assert first["status"] == "failed"
    assert retry["status"] == "failed"
    assert first["api_call_id"] == retry["api_call_id"]

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        api_calls = (
            (
                await session.execute(
                    select(LLMApiCall).where(
                        LLMApiCall.tenant_id == test_tenant,
                        LLMApiCall.request_id == request_id,
                        LLMApiCall.endpoint == "app.tasks.llm.explanation",
                    )
                )
            )
            .scalars()
            .all()
        )
        reservations = (
            (
                await session.execute(
                    select(LLMBudgetReservation).where(
                        LLMBudgetReservation.tenant_id == test_tenant,
                        LLMBudgetReservation.request_id == request_id,
                        LLMBudgetReservation.endpoint == "app.tasks.llm.explanation",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(api_calls) == 1
        assert len(reservations) == 1


@pytest.mark.asyncio
async def test_p3_breaker_opens_after_three_failures(monkeypatch, test_tenant):
    monkeypatch.setattr(settings, "LLM_BREAKER_FAILURE_THRESHOLD", 3, raising=False)
    monkeypatch.setattr(settings, "LLM_BREAKER_OPEN_SECONDS", 600, raising=False)
    monkeypatch.setattr(settings, "LLM_HOURLY_SHUTOFF_CENTS", 10_000, raising=False)
    monkeypatch.setattr(settings, "LLM_MONTHLY_CAP_CENTS", 10_000, raising=False)

    fail_prompt = {"raise_error": True, "cache_enabled": False}
    ok_prompt = {"simulated_output_text": "should-block", "cache_enabled": False}
    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        for _ in range(3):
            res = await generate_explanation(
                _payload(test_tenant, request_id=str(uuid4()), prompt=fail_prompt),
                session=session,
            )
            assert res["status"] == "failed"
        blocked = await generate_explanation(
            _payload(test_tenant, request_id=str(uuid4()), prompt=ok_prompt),
            session=session,
        )

    assert blocked["status"] == "blocked"
    assert blocked["blocked_reason"] == "breaker_open"


@pytest.mark.asyncio
async def test_p3_timeout_enforced(monkeypatch, test_tenant):
    monkeypatch.setattr(settings, "LLM_PROVIDER_TIMEOUT_MS", 10, raising=False)
    monkeypatch.setattr(settings, "LLM_HOURLY_SHUTOFF_CENTS", 10_000, raising=False)
    prompt = {"simulated_delay_ms": 100, "cache_enabled": False}
    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        res = await generate_explanation(
            _payload(test_tenant, request_id=str(uuid4()), prompt=prompt),
            session=session,
        )
    assert res["status"] == "failed"
    assert res["failure_reason"] == "provider_timeout"


@pytest.mark.asyncio
async def test_p3_timeout_non_vacuous_negative_control(monkeypatch, test_tenant):
    monkeypatch.setattr(settings, "LLM_HOURLY_SHUTOFF_CENTS", 10_000, raising=False)
    monkeypatch.setattr(settings, "LLM_MONTHLY_CAP_CENTS", 10_000, raising=False)

    calls = {"count": 0}

    async def _slow_provider(*, requested_model, prompt, reservation):
        calls["count"] += 1
        await asyncio.sleep(0.05)
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": "slow-ok",
            "reasoning_trace": {"trace_type": "slow"},
            "response_metadata": {"source": "slow"},
            "usage": {"input_tokens": 1, "output_tokens": 1, "cost_cents": 1},
        }

    monkeypatch.setattr(
        _PROVIDER_BOUNDARY, "_provider_call", _slow_provider, raising=True
    )

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        monkeypatch.setattr(settings, "LLM_PROVIDER_TIMEOUT_MS", 10, raising=False)
        timed_out = await generate_explanation(
            _payload(
                test_tenant, request_id=str(uuid4()), prompt={"cache_enabled": False}
            ),
            session=session,
        )
        monkeypatch.setattr(settings, "LLM_PROVIDER_TIMEOUT_MS", 300, raising=False)
        succeeded = await generate_explanation(
            _payload(
                test_tenant, request_id=str(uuid4()), prompt={"cache_enabled": False}
            ),
            session=session,
        )

    assert timed_out["status"] == "failed"
    assert timed_out["failure_reason"] == "provider_timeout"
    assert succeeded["status"] == "accepted"
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_p3_reservation_and_settlement_use_separate_transactions(
    monkeypatch, test_tenant
):
    monkeypatch.setattr(settings, "LLM_MONTHLY_CAP_CENTS", 10_000, raising=False)
    monkeypatch.setattr(settings, "LLM_HOURLY_SHUTOFF_CENTS", 10_000, raising=False)

    observed = {"in_transaction_during_provider": None}

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:

        async def _inspect_provider(*, requested_model, prompt, reservation):
            observed["in_transaction_during_provider"] = bool(session.in_transaction())
            return {
                "provider": "stub",
                "model": requested_model,
                "output_text": "tx-separation-ok",
                "reasoning_trace": {"trace_type": "test"},
                "response_metadata": {"source": "tx-separation-test"},
                "usage": {"input_tokens": 1, "output_tokens": 1, "cost_cents": 1},
            }

        monkeypatch.setattr(
            _PROVIDER_BOUNDARY, "_provider_call", _inspect_provider, raising=True
        )
        res = await generate_explanation(
            _payload(
                test_tenant, request_id=str(uuid4()), prompt={"cache_enabled": False}
            ),
            session=session,
        )

    assert res["status"] == "accepted"
    assert observed["in_transaction_during_provider"] is False


@pytest.mark.asyncio
async def test_p3_distillation_capture_default_false(test_tenant):
    request_id = str(uuid4())
    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        result = await generate_explanation(
            _payload(
                test_tenant,
                request_id=request_id,
                prompt={"simulated_output_text": "trace-me"},
            ),
            session=session,
        )
    assert result["status"] == "accepted"
    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        row = (
            (
                await session.execute(
                    select(LLMApiCall).where(
                        LLMApiCall.tenant_id == test_tenant,
                        LLMApiCall.request_id == request_id,
                        LLMApiCall.endpoint == "app.tasks.llm.explanation",
                    )
                )
            )
            .scalars()
            .one()
        )
        assert row.distillation_eligible is False
        assert row.reasoning_trace_ref is not None
        assert isinstance(row.reasoning_trace_ref, dict)


@pytest.mark.asyncio
async def test_p3_secret_not_leaked_on_failure(monkeypatch, test_tenant):
    secret = "p3-secret-canary-123"
    monkeypatch.setattr(settings, "LLM_PROVIDER_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "LLM_PROVIDER_API_KEY", secret, raising=False)

    async def _boom(*, requested_model, prompt):
        raise RuntimeError(f"boom:{secret}:{requested_model}:{prompt}")

    monkeypatch.setattr(_PROVIDER_BOUNDARY, "_call_aisuite", _boom, raising=True)

    request_id = str(uuid4())
    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        result = await generate_explanation(
            _payload(
                test_tenant, request_id=request_id, prompt={"cache_enabled": False}
            ),
            session=session,
        )
    assert result["status"] == "failed"
    assert secret not in (result["failure_reason"] or "")

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        row = (
            (
                await session.execute(
                    select(LLMApiCall).where(
                        LLMApiCall.tenant_id == test_tenant,
                        LLMApiCall.request_id == request_id,
                        LLMApiCall.endpoint == "app.tasks.llm.explanation",
                    )
                )
            )
            .scalars()
            .one()
        )
        assert secret not in (row.failure_reason or "")


@pytest.mark.asyncio
async def test_p3_provider_enabled_routes_through_aisuite_boundary(
    monkeypatch, test_tenant
):
    monkeypatch.setattr(settings, "LLM_PROVIDER_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "LLM_PROVIDER_API_KEY", "fake-key", raising=False)

    async def _fake_aisuite(*, requested_model, prompt):
        return {
            "provider": "openai",
            "model": requested_model,
            "output_text": "aisuite-path-ok",
            "reasoning_trace": {"trace_type": "fake"},
            "response_metadata": {"source": "fake-aisuite"},
            "usage": {"input_tokens": 1, "output_tokens": 1, "cost_cents": 0},
        }

    monkeypatch.setattr(
        _PROVIDER_BOUNDARY, "_call_aisuite", _fake_aisuite, raising=True
    )

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        result = await generate_explanation(
            _payload(
                test_tenant,
                request_id=str(uuid4()),
                prompt={"cache_enabled": False, "model": "openai:gpt-4o-mini"},
            ),
            session=session,
        )
    assert result["status"] == "accepted"
    assert result["explanation"] == "aisuite-path-ok"


@pytest.mark.asyncio
async def test_p3_provider_swap_config_only_proof(monkeypatch, test_tenant, tmp_path):
    monkeypatch.setattr(settings, "LLM_PROVIDER_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "LLM_PROVIDER_API_KEY", "fake-key", raising=False)
    monkeypatch.setattr(settings, "LLM_HOURLY_SHUTOFF_CENTS", 10_000, raising=False)
    monkeypatch.setattr(settings, "LLM_MONTHLY_CAP_CENTS", 10_000, raising=False)

    async def _fake_aisuite(*, requested_model, prompt):
        provider_name = requested_model.split(":", 1)[0]
        return {
            "provider": provider_name,
            "model": requested_model,
            "output_text": f"{provider_name}-path-ok",
            "reasoning_trace": {"trace_type": "fake"},
            "response_metadata": {"source": "provider-swap-test"},
            "usage": {"input_tokens": 1, "output_tokens": 1, "cost_cents": 1},
        }

    monkeypatch.setattr(
        _PROVIDER_BOUNDARY, "_call_aisuite", _fake_aisuite, raising=True
    )

    policy_a = tmp_path / "policy_a.json"
    policy_b = tmp_path / "policy_b.json"
    policy_a.write_text(
        json.dumps(
            {
                "policy_id": "swap-proof",
                "policy_version": "a",
                "bucket_tiers": [{"min_bucket": 1, "max_bucket": 10, "tier": "cheap"}],
                "tiers": {"cheap": {"provider": "openai", "model": "gpt-4o-mini"}},
                "budget_downgrade": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )
    policy_b.write_text(
        json.dumps(
            {
                "policy_id": "swap-proof",
                "policy_version": "b",
                "bucket_tiers": [{"min_bucket": 1, "max_bucket": 10, "tier": "cheap"}],
                "tiers": {
                    "cheap": {"provider": "anthropic", "model": "claude-3-5-sonnet"}
                },
                "budget_downgrade": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )

    request_a = str(uuid4())
    request_b = str(uuid4())
    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        monkeypatch.setattr(
            settings, "LLM_COMPLEXITY_POLICY_PATH", str(policy_a), raising=False
        )
        run_a = await generate_explanation(
            _payload(
                test_tenant, request_id=request_a, prompt={"cache_enabled": False}
            ),
            session=session,
        )
        monkeypatch.setattr(
            settings, "LLM_COMPLEXITY_POLICY_PATH", str(policy_b), raising=False
        )
        run_b = await generate_explanation(
            _payload(
                test_tenant, request_id=request_b, prompt={"cache_enabled": False}
            ),
            session=session,
        )

    assert run_a["status"] == "accepted"
    assert run_b["status"] == "accepted"

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        row_a = (
            (
                await session.execute(
                    select(LLMApiCall).where(
                        LLMApiCall.tenant_id == test_tenant,
                        LLMApiCall.request_id == request_a,
                        LLMApiCall.endpoint == "app.tasks.llm.explanation",
                    )
                )
            )
            .scalars()
            .one()
        )
        row_b = (
            (
                await session.execute(
                    select(LLMApiCall).where(
                        LLMApiCall.tenant_id == test_tenant,
                        LLMApiCall.request_id == request_b,
                        LLMApiCall.endpoint == "app.tasks.llm.explanation",
                    )
                )
            )
            .scalars()
            .one()
        )

    assert row_a.provider == "openai"
    assert row_b.provider == "anthropic"
