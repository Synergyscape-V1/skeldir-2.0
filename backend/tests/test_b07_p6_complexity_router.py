from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.identity import SYSTEM_USER_ID
from app.db.session import get_session
from app.llm import complexity_router
from app.llm.complexity_router import bucket, route_request
from app.llm.provider_boundary import ProviderBoundaryResult
from app.models.llm import LLMApiCall
from app.schemas.llm_payloads import LLMTaskPayload
from app.workers import llm as llm_workers


VECTORS_PATH = Path("backend/tests/fixtures/b07_p6_complexity_vectors_v1.json")


def _load_vectors() -> list[dict]:
    return json.loads(VECTORS_PATH.read_text(encoding="utf-8"))


def _assert_band_binding(decisions: list[tuple[int, str]]) -> None:
    for bucket_value, tier in decisions:
        if 1 <= bucket_value <= 3:
            assert tier == "cheap"
        if 8 <= bucket_value <= 10:
            assert tier == "premium"


def _payload(
    tenant_id, *, request_id: str, prompt: dict, max_cost_cents: int = 40
) -> LLMTaskPayload:
    return LLMTaskPayload(
        tenant_id=tenant_id,
        user_id=SYSTEM_USER_ID,
        correlation_id=request_id,
        request_id=request_id,
        prompt=prompt,
        max_cost_cents=max_cost_cents,
    )


def test_eg60_scorer_non_vacuous_and_margin_alignment():
    vectors = _load_vectors()
    buckets = [
        bucket(complexity_router.complexity_score(v["prompt"], v["feature"], {}))
        for v in vectors
    ]

    assert len(set(buckets)) >= 4
    assert sum(1 for b in buckets if 1 <= b <= 3) >= 3
    assert sum(1 for b in buckets if 8 <= b <= 10) >= 3

    short_prompt = {"input": "Short summary."}
    long_prompt = {"input": "Long text " * 150, "context_items": 20}
    short_bucket = bucket(
        complexity_router.complexity_score(
            short_prompt, "app.tasks.llm.explanation", {}
        )
    )
    long_bucket = bucket(
        complexity_router.complexity_score(long_prompt, "app.tasks.llm.explanation", {})
    )
    assert long_bucket >= short_bucket

    base_prompt = {"input": "Analyze this marketing report."}
    constrained_prompt = {
        "input": "Analyze this marketing report.",
        "response_schema": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
        },
    }
    base_bucket = bucket(
        complexity_router.complexity_score(base_prompt, "app.tasks.llm.explanation", {})
    )
    constrained_bucket = bucket(
        complexity_router.complexity_score(
            constrained_prompt, "app.tasks.llm.explanation", {}
        )
    )
    assert constrained_bucket >= base_bucket


def test_eg60_negative_control_constant_scorer_fails(monkeypatch):
    vectors = _load_vectors()
    monkeypatch.setattr(
        complexity_router,
        "complexity_score",
        lambda prompt, feature, context: 1.0,
        raising=True,
    )
    buckets = [
        bucket(complexity_router.complexity_score(v["prompt"], v["feature"], {}))
        for v in vectors
    ]
    gate_passes = (
        len(set(buckets)) >= 4
        and sum(1 for b in buckets if 1 <= b <= 3) >= 3
        and sum(1 for b in buckets if 8 <= b <= 10) >= 3
    )
    assert gate_passes is False


def test_eg61_determinism_and_mutation_control():
    prompt = {
        "input": "Reconcile variance",
        "context_items": 8,
        "messages": [{"role": "user", "content": "x"}],
    }
    outputs = [
        route_request(
            prompt=prompt,
            feature="app.tasks.llm.explanation",
            context={
                "budget_state": {
                    "cap_cents": 100,
                    "spent_cents": 0,
                    "reserved_cents": 0,
                }
            },
            policy_path=settings.LLM_COMPLEXITY_POLICY_PATH,
        )
        for _ in range(5)
    ]
    assert (
        len(
            {
                (
                    o.complexity_score,
                    o.complexity_bucket,
                    o.chosen_tier,
                    o.chosen_provider,
                    o.chosen_model,
                )
                for o in outputs
            }
        )
        == 1
    )

    mutated = route_request(
        prompt={**prompt, "response_schema": {"type": "object"}, "context_items": 20},
        feature="app.tasks.llm.explanation",
        context={
            "budget_state": {"cap_cents": 100, "spent_cents": 0, "reserved_cents": 0}
        },
        policy_path=settings.LLM_COMPLEXITY_POLICY_PATH,
    )
    baseline = outputs[0]
    assert (
        mutated.complexity_score,
        mutated.complexity_bucket,
        mutated.chosen_tier,
    ) != (
        baseline.complexity_score,
        baseline.complexity_bucket,
        baseline.chosen_tier,
    )


def test_eg62_config_policy_mapping_and_fail_closed(tmp_path):
    policy_a = tmp_path / "policy_a.json"
    policy_b = tmp_path / "policy_b.json"
    policy_a.write_text(
        json.dumps(
            {
                "policy_id": "p6-map",
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
                "policy_id": "p6-map",
                "policy_version": "b",
                "bucket_tiers": [
                    {"min_bucket": 1, "max_bucket": 10, "tier": "premium"}
                ],
                "tiers": {
                    "premium": {"provider": "anthropic", "model": "claude-3-5-opus"}
                },
                "budget_downgrade": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )

    prompt = {"input": "simple"}
    decision_a = route_request(
        prompt=prompt,
        feature="app.tasks.llm.explanation",
        context={
            "budget_state": {"cap_cents": 100, "spent_cents": 0, "reserved_cents": 0}
        },
        policy_path=str(policy_a),
    )
    decision_b = route_request(
        prompt=prompt,
        feature="app.tasks.llm.explanation",
        context={
            "budget_state": {"cap_cents": 100, "spent_cents": 0, "reserved_cents": 0}
        },
        policy_path=str(policy_b),
    )

    assert (
        decision_a.chosen_provider,
        decision_a.chosen_model,
        decision_a.chosen_tier,
    ) != (
        decision_b.chosen_provider,
        decision_b.chosen_model,
        decision_b.chosen_tier,
    )

    with pytest.raises(ValueError):
        route_request(
            prompt=prompt,
            feature="app.tasks.llm.explanation",
            context={
                "budget_state": {
                    "cap_cents": 100,
                    "spent_cents": 0,
                    "reserved_cents": 0,
                }
            },
            policy_path=str(tmp_path / "missing_policy.json"),
        )


def test_eg64_threshold_binding_with_negative_control(tmp_path):
    vectors = _load_vectors()
    decisions = []
    for vector in vectors:
        decision = route_request(
            prompt=vector["prompt"],
            feature=vector["feature"],
            context={
                "budget_state": {
                    "cap_cents": 100,
                    "spent_cents": 0,
                    "reserved_cents": 0,
                }
            },
            policy_path=settings.LLM_COMPLEXITY_POLICY_PATH,
        )
        decisions.append((decision.complexity_bucket, decision.chosen_tier))

    _assert_band_binding(decisions)

    tampered_policy = tmp_path / "tampered_policy.json"
    tampered_policy.write_text(
        json.dumps(
            {
                "policy_id": "tampered",
                "policy_version": "1",
                "bucket_tiers": [
                    {"min_bucket": 1, "max_bucket": 3, "tier": "premium"},
                    {"min_bucket": 4, "max_bucket": 7, "tier": "standard"},
                    {"min_bucket": 8, "max_bucket": 10, "tier": "cheap"},
                ],
                "tiers": {
                    "cheap": {"provider": "openai", "model": "gpt-4o-mini"},
                    "standard": {"provider": "anthropic", "model": "claude-3-5-sonnet"},
                    "premium": {"provider": "anthropic", "model": "claude-3-5-opus"},
                },
                "budget_downgrade": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )

    tampered = []
    for vector in vectors:
        decision = route_request(
            prompt=vector["prompt"],
            feature=vector["feature"],
            context={
                "budget_state": {
                    "cap_cents": 100,
                    "spent_cents": 0,
                    "reserved_cents": 0,
                }
            },
            policy_path=str(tampered_policy),
        )
        tampered.append((decision.complexity_bucket, decision.chosen_tier))

    with pytest.raises(AssertionError):
        _assert_band_binding(tampered)


def test_eg65_budget_pressure_downgrade_and_negative_control(tmp_path):
    downgrade_policy = tmp_path / "downgrade_policy.json"
    downgrade_policy.write_text(
        json.dumps(
            {
                "policy_id": "downgrade",
                "policy_version": "1",
                "bucket_tiers": [
                    {"min_bucket": 1, "max_bucket": 10, "tier": "premium"}
                ],
                "tiers": {
                    "cheap": {"provider": "openai", "model": "gpt-4o-mini"},
                    "standard": {"provider": "anthropic", "model": "claude-3-5-sonnet"},
                    "premium": {"provider": "anthropic", "model": "claude-3-5-opus"},
                },
                "budget_downgrade": {
                    "enabled": True,
                    "pressure_threshold": 0.8,
                    "critical_threshold": 0.95,
                    "downgrade_order": ["premium", "standard", "cheap"],
                },
            }
        ),
        encoding="utf-8",
    )

    high_pressure = route_request(
        prompt={"input": "hard task", "structured_output": True, "context_items": 30},
        feature="app.tasks.llm.investigation",
        context={
            "budget_state": {"cap_cents": 100, "spent_cents": 85, "reserved_cents": 5}
        },
        policy_path=str(downgrade_policy),
    )
    assert high_pressure.chosen_tier == "standard"
    assert high_pressure.routing_reason.startswith("budget_pressure")

    no_downgrade_policy = tmp_path / "no_downgrade_policy.json"
    no_downgrade_policy.write_text(
        json.dumps(
            {
                "policy_id": "downgrade",
                "policy_version": "2",
                "bucket_tiers": [
                    {"min_bucket": 1, "max_bucket": 10, "tier": "premium"}
                ],
                "tiers": {
                    "cheap": {"provider": "openai", "model": "gpt-4o-mini"},
                    "standard": {"provider": "anthropic", "model": "claude-3-5-sonnet"},
                    "premium": {"provider": "anthropic", "model": "claude-3-5-opus"},
                },
                "budget_downgrade": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )

    no_downgrade = route_request(
        prompt={"input": "hard task", "structured_output": True, "context_items": 30},
        feature="app.tasks.llm.investigation",
        context={
            "budget_state": {"cap_cents": 100, "spent_cents": 85, "reserved_cents": 5}
        },
        policy_path=str(no_downgrade_policy),
    )
    assert no_downgrade.chosen_tier == "premium"


@pytest.mark.asyncio
async def test_eg63_chokepoint_enforcement_via_worker_paths(monkeypatch, test_tenant):
    calls: list[str] = []

    async def _fake_complete(*, model, session, endpoint, force_failure=False):
        calls.append(endpoint)
        return ProviderBoundaryResult(
            provider="stub",
            model="stub:model",
            output_text="ok",
            reasoning_trace={},
            usage={
                "input_tokens": 1,
                "output_tokens": 1,
                "cost_cents": 0,
                "latency_ms": 1,
            },
            status="success",
            was_cached=False,
            request_id=model.request_id or "req",
            correlation_id=model.correlation_id or "corr",
            api_call_id=uuid4(),
            response_metadata={"source": "test"},
        )

    monkeypatch.setattr(
        llm_workers._PROVIDER_BOUNDARY, "complete", _fake_complete, raising=True
    )

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        await llm_workers.route_request(
            _payload(
                test_tenant, request_id=str(uuid4()), prompt={"cache_enabled": False}
            ),
            session,
        )
        await llm_workers.generate_explanation(
            _payload(
                test_tenant, request_id=str(uuid4()), prompt={"cache_enabled": False}
            ),
            session,
        )
        await llm_workers.run_investigation(
            _payload(
                test_tenant, request_id=str(uuid4()), prompt={"cache_enabled": False}
            ),
            session,
        )
        await llm_workers.optimize_budget(
            _payload(
                test_tenant, request_id=str(uuid4()), prompt={"cache_enabled": False}
            ),
            session,
        )

    assert calls == [
        "app.tasks.llm.route",
        "app.tasks.llm.explanation",
        "app.tasks.llm.investigation",
        "app.tasks.llm.budget_optimization",
    ]


@pytest.mark.asyncio
async def test_eg66_ledger_persistence_across_success_failure_blocked_cached(
    monkeypatch, test_tenant
):
    monkeypatch.setattr(settings, "LLM_MONTHLY_CAP_CENTS", 10_000, raising=False)
    monkeypatch.setattr(settings, "LLM_HOURLY_SHUTOFF_CENTS", 10_000, raising=False)

    success_id = f"p6-success-{uuid4().hex[:8]}"
    failure_id = f"p6-failure-{uuid4().hex[:8]}"
    blocked_id = f"p6-blocked-{uuid4().hex[:8]}"
    cache_seed_id = f"p6-cache-seed-{uuid4().hex[:8]}"
    cache_hit_id = f"p6-cache-hit-{uuid4().hex[:8]}"

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        success = await llm_workers.generate_explanation(
            _payload(
                test_tenant,
                request_id=success_id,
                prompt={"input": "simple", "cache_enabled": False},
            ),
            session=session,
        )
        failure = await llm_workers.generate_explanation(
            _payload(
                test_tenant,
                request_id=failure_id,
                prompt={"input": "boom", "raise_error": True, "cache_enabled": False},
            ),
            session=session,
        )
        blocked = await llm_workers.generate_explanation(
            _payload(
                test_tenant,
                request_id=blocked_id,
                prompt={
                    "input": "blocked",
                    "kill_switch": True,
                    "cache_enabled": False,
                },
            ),
            session=session,
        )
        await llm_workers.generate_explanation(
            _payload(
                test_tenant,
                request_id=cache_seed_id,
                prompt={"input": "cache", "cache_enabled": True, "cache_watermark": 7},
            ),
            session=session,
        )
        cached = await llm_workers.generate_explanation(
            _payload(
                test_tenant,
                request_id=cache_hit_id,
                prompt={"input": "cache", "cache_enabled": True, "cache_watermark": 7},
            ),
            session=session,
        )

    assert success["status"] == "accepted"
    assert failure["status"] == "failed"
    assert blocked["status"] == "blocked"
    assert cached["was_cached"] is True

    request_ids = [success_id, failure_id, blocked_id, cache_hit_id]
    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        rows = (
            (
                await session.execute(
                    select(LLMApiCall).where(
                        LLMApiCall.tenant_id == test_tenant,
                        LLMApiCall.request_id.in_(request_ids),
                        LLMApiCall.endpoint == "app.tasks.llm.explanation",
                    )
                )
            )
            .scalars()
            .all()
        )

    assert len(rows) == 4
    for row in rows:
        assert row.complexity_score is not None
        assert 0.0 <= float(row.complexity_score) <= 1.0
        assert row.complexity_bucket is not None
        assert 1 <= int(row.complexity_bucket) <= 10
        assert row.chosen_tier
        assert row.chosen_provider
        assert row.chosen_model
        assert row.policy_id
        assert row.policy_version
        assert row.routing_reason
