from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text

from app.core.identity import SYSTEM_USER_ID
from app.db.session import engine, get_session
from app.models.llm import LLMApiCall, LLMValidationFailure
from app.schemas.llm_payloads import LLMTaskPayload
from app.services.llm_validation_failures import LLMValidationFailureService
from app.services.llm_validation_observability import (
    LLMValidationObservabilityService,
)
from app.workers.llm import generate_explanation


def _payload(
    tenant_id: UUID,
    *,
    request_id: str,
    prompt: dict | None = None,
) -> LLMTaskPayload:
    now = datetime.now(timezone.utc)
    return LLMTaskPayload.model_validate(
        {
            "tenant_id": tenant_id,
            "user_id": SYSTEM_USER_ID,
            "correlation_id": f"corr-{request_id}",
            "request_id": request_id,
            "prompt": prompt or {"cache_enabled": False},
            "max_cost_cents": 50,
            "created_at": now,
            "scheduled_at": now,
            "attempt": 0,
        }
    )


def _api_call(
    *,
    tenant_id: UUID,
    endpoint: str,
    model: str,
    request_id: str,
    created_at: datetime,
) -> LLMApiCall:
    return LLMApiCall(
        tenant_id=tenant_id,
        user_id=SYSTEM_USER_ID,
        created_at=created_at,
        endpoint=endpoint,
        request_id=request_id,
        provider="stub",
        model=model,
        input_tokens=1,
        output_tokens=1,
        cost_cents=1,
        latency_ms=1,
        was_cached=False,
        distillation_eligible=False,
        request_metadata_ref={},
        response_metadata_ref={},
        reasoning_trace_ref={},
        prompt_fingerprint=f"fp-{request_id}",
        status="success",
        block_reason=None,
        failure_reason=None,
        breaker_state="closed",
        provider_attempted=True,
        budget_reservation_cents=1,
        budget_settled_cents=1,
        cache_key=None,
        cache_watermark=1,
        complexity_score=0.2,
        complexity_bucket=2,
        chosen_tier="cheap",
        chosen_provider="openai",
        chosen_model=model,
        policy_id="test-policy",
        policy_version="v1",
        routing_reason="bucket_policy",
    )


@pytest.mark.asyncio
async def test_b16_p5_structured_failure_rows_are_metric_grade(
    test_tenant: UUID,
) -> None:
    request_id = f"b16-p5-metric-grade-{uuid4().hex[:8]}"

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        failed = await generate_explanation(
            _payload(
                test_tenant,
                request_id=request_id,
                prompt={
                    "cache_enabled": False,
                    "simulated_output_text": '{"summary":"schema mismatch"}',
                },
            ),
            session=session,
        )
        assert failed["status"] == "failed"

        rows = (
            (
                await session.execute(
                    select(LLMValidationFailure).where(
                        LLMValidationFailure.tenant_id == test_tenant,
                        LLMValidationFailure.endpoint == "app.tasks.llm.explanation",
                        LLMValidationFailure.request_payload["request_id"].astext
                        == request_id,
                    )
                )
            )
            .scalars()
            .all()
        )

    assert rows
    for row in rows:
        payload = dict(row.request_payload or {})
        response = dict(row.response_payload or {})
        assert payload.get("feature") == "app.tasks.llm.explanation"
        assert payload.get("request_id") == request_id
        assert payload.get("correlation_id") == f"corr-{request_id}"
        assert payload.get("validation_code") in {
            "schema_failed",
            "normalization_failed",
            "numeric_mismatch",
        }
        assert payload.get("validation_stage") == "provider"
        assert response.get("feature") == "app.tasks.llm.explanation"
        assert isinstance(response.get("model"), str)
        assert response.get("model")
        assert response.get("validation_code") == payload.get("validation_code")
        assert response.get("validation_stage") == payload.get("validation_stage")


def test_b16_p5_privilege_fix_is_in_authoritative_migration_surface() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    migration = (
        repo_root
        / "alembic/versions/007_skeldir_foundation/202603301230_b16_p1_validation_failure_sink_grants.py"
    )
    assert migration.exists()
    body = migration.read_text(encoding="utf-8")
    assert (
        '_grant_if_role_exists("app_rw", "SELECT, INSERT", "llm_validation_failures")'
        in body
    )
    assert (
        '_grant_if_role_exists("app_user", "SELECT, INSERT", "llm_validation_failures")'
        in body
    )
    assert (
        '_grant_if_role_exists("app_ro", "SELECT", "llm_validation_failures")' in body
    )


@pytest.mark.asyncio
async def test_b16_p5_runtime_identity_has_insert_privilege_on_failure_sink(
    test_tenant: UUID,
) -> None:
    async with engine.begin() as conn:
        role_exists = bool(
            (
                await conn.execute(
                    text(
                        "SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname = 'app_rw')"
                    )
                )
            ).scalar_one()
        )
        if not role_exists:
            pytest.skip("app_rw role not present in this runtime")

        grants = (
            (
                await conn.execute(
                    text(
                        """
                    SELECT privilege_type
                    FROM information_schema.role_table_grants
                    WHERE table_schema = 'public'
                      AND table_name = 'llm_validation_failures'
                      AND grantee = 'app_rw'
                    """
                    )
                )
            )
            .scalars()
            .all()
        )

    assert {"SELECT", "INSERT"}.issubset({str(item).upper() for item in grants})

    service = LLMValidationFailureService()
    request_id = f"b16-p5-runtime-write-{uuid4().hex[:8]}"
    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        failure_id = await service.record_failure(
            session,
            tenant_id=test_tenant,
            endpoint="app.tasks.llm.explanation",
            validation_error="validation_schema_failed",
            request_payload={
                "request_id": request_id,
                "correlation_id": f"corr-{request_id}",
            },
            response_payload={"model": "stub:model"},
        )
        inserted = (
            (
                await session.execute(
                    select(LLMValidationFailure).where(
                        LLMValidationFailure.tenant_id == test_tenant,
                        LLMValidationFailure.id == failure_id,
                    )
                )
            )
            .scalars()
            .one()
        )

    assert str(inserted.id) == str(failure_id)


@pytest.mark.asyncio
async def test_b16_p5_rejection_rate_computation_by_feature_model_window(
    test_tenant: UUID,
) -> None:
    service = LLMValidationFailureService()
    metrics = LLMValidationObservabilityService()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    window_start = now - timedelta(hours=1)
    window_end = now + timedelta(minutes=5)

    scoped_calls = [
        _api_call(
            tenant_id=test_tenant,
            endpoint="app.tasks.llm.investigation",
            model="openai:gpt-4o-mini",
            request_id=f"inv-{idx}",
            created_at=now - timedelta(minutes=10 - idx),
        )
        for idx in range(1, 5)
    ]
    scoped_calls.extend(
        [
            _api_call(
                tenant_id=test_tenant,
                endpoint="app.tasks.llm.budget_optimization",
                model="anthropic:claude-4.5-opus",
                request_id=f"bud-{idx}",
                created_at=now - timedelta(minutes=20 - idx),
            )
            for idx in range(1, 4)
        ]
    )
    scoped_calls.append(
        _api_call(
            tenant_id=test_tenant,
            endpoint="app.tasks.llm.explanation",
            model="openai:gpt-4o-mini",
            request_id="exp-1",
            created_at=now - timedelta(minutes=3),
        )
    )
    outside_window_call = _api_call(
        tenant_id=test_tenant,
        endpoint="app.tasks.llm.investigation",
        model="openai:gpt-4o-mini",
        request_id="inv-old",
        created_at=now - timedelta(days=2),
    )

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        for row in scoped_calls:
            session.add(row)
        session.add(outside_window_call)
        await session.flush()

        await service.record_failure(
            session,
            tenant_id=test_tenant,
            endpoint="app.tasks.llm.investigation",
            validation_error="numeric_mismatch",
            request_payload={"request_id": "inv-1", "stage": "provider"},
            response_payload={"model": "openai:gpt-4o-mini"},
        )
        await service.record_failure(
            session,
            tenant_id=test_tenant,
            endpoint="app.tasks.llm.budget_optimization",
            validation_error="numeric_mismatch",
            request_payload={"request_id": "bud-1", "stage": "provider"},
            response_payload={"model": "anthropic:claude-4.5-opus"},
        )
        await service.record_failure(
            session,
            tenant_id=test_tenant,
            endpoint="app.tasks.llm.budget_optimization",
            validation_error="cache_numeric_mismatch",
            request_payload={"request_id": "bud-2", "stage": "cache"},
            response_payload={"model": "anthropic:claude-4.5-opus"},
        )
        await service.record_failure(
            session,
            tenant_id=test_tenant,
            endpoint="app.tasks.llm.budget_optimization",
            validation_error="cache_numeric_mismatch",
            request_payload={"request_id": "bud-2", "stage": "cache"},
            response_payload={"model": "anthropic:claude-4.5-opus"},
        )

        old_failure = LLMValidationFailure(
            tenant_id=test_tenant,
            created_at=now - timedelta(days=2),
            endpoint="app.tasks.llm.investigation",
            validation_error="numeric_mismatch",
            request_payload={
                "request_id": "inv-old",
                "feature": "app.tasks.llm.investigation",
                "validation_code": "numeric_mismatch",
                "validation_stage": "provider",
            },
            response_payload={
                "model": "openai:gpt-4o-mini",
                "feature": "app.tasks.llm.investigation",
                "validation_code": "numeric_mismatch",
                "validation_stage": "provider",
            },
        )
        session.add(old_failure)
        await session.flush()

        computed = await metrics.compute_rejection_rates(
            session,
            tenant_id=test_tenant,
            window_start=window_start,
            window_end=window_end,
        )

    matrix = {(item.feature, item.model): item for item in computed}
    inv = matrix[("app.tasks.llm.investigation", "openai:gpt-4o-mini")]
    budget = matrix[("app.tasks.llm.budget_optimization", "anthropic:claude-4.5-opus")]
    explanation = matrix[("app.tasks.llm.explanation", "openai:gpt-4o-mini")]

    assert inv.total_requests == 4
    assert inv.rejected_requests == 1
    assert inv.rejection_rate == pytest.approx(0.25, abs=1e-9)

    assert budget.total_requests == 3
    assert budget.rejected_requests == 2
    assert budget.rejection_rate == pytest.approx(2 / 3, abs=1e-9)

    assert explanation.total_requests == 1
    assert explanation.rejected_requests == 0
    assert explanation.rejection_rate == pytest.approx(0.0, abs=1e-9)


@pytest.mark.asyncio
async def test_b16_p5_alert_threshold_simulation_breach_and_non_breach(
    test_tenant: UUID,
) -> None:
    service = LLMValidationFailureService()
    metrics = LLMValidationObservabilityService()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    window_start = now - timedelta(hours=1)
    window_end = now + timedelta(minutes=5)

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        for idx in range(1, 6):
            session.add(
                _api_call(
                    tenant_id=test_tenant,
                    endpoint="app.tasks.llm.investigation",
                    model="openai:gpt-4o-mini",
                    request_id=f"sim-hi-{idx}",
                    created_at=now - timedelta(minutes=idx),
                )
            )
        for idx in range(1, 6):
            session.add(
                _api_call(
                    tenant_id=test_tenant,
                    endpoint="app.tasks.llm.budget_optimization",
                    model="anthropic:claude-4.5-opus",
                    request_id=f"sim-lo-{idx}",
                    created_at=now - timedelta(minutes=idx + 10),
                )
            )
        await session.flush()

        for request_id in ("sim-hi-1", "sim-hi-2"):
            await service.record_failure(
                session,
                tenant_id=test_tenant,
                endpoint="app.tasks.llm.investigation",
                validation_error="numeric_mismatch",
                request_payload={"request_id": request_id},
                response_payload={"model": "openai:gpt-4o-mini"},
            )

        await service.record_failure(
            session,
            tenant_id=test_tenant,
            endpoint="app.tasks.llm.budget_optimization",
            validation_error="numeric_mismatch",
            request_payload={"request_id": "sim-lo-1"},
            response_payload={"model": "anthropic:claude-4.5-opus"},
        )

        decisions = await metrics.simulate_alert_threshold(
            session,
            tenant_id=test_tenant,
            window_start=window_start,
            window_end=window_end,
            threshold_ratio=0.30,
            min_requests=3,
        )

    matrix = {(item.feature, item.model): item for item in decisions}
    high = matrix[("app.tasks.llm.investigation", "openai:gpt-4o-mini")]
    low = matrix[("app.tasks.llm.budget_optimization", "anthropic:claude-4.5-opus")]

    assert high.total_requests == 5
    assert high.rejected_requests == 2
    assert high.rejection_rate == pytest.approx(0.4, abs=1e-9)
    assert high.alert_triggered is True

    assert low.total_requests == 5
    assert low.rejected_requests == 1
    assert low.rejection_rate == pytest.approx(0.2, abs=1e-9)
    assert low.alert_triggered is False
