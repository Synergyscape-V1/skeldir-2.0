from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError

from app.db.session import engine, get_session


START = datetime(2026, 5, 1, tzinfo=timezone.utc)
END = datetime(2026, 6, 1, tzinfo=timezone.utc)
VALID_HASH = "7" * 64


def _require_db_proofs() -> bool:
    return os.getenv("SKELDIR_B24_P7_REQUIRE_DB_PROOFS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def _assert_table_exists(table_name: str) -> None:
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT to_regclass(:qualified_name)"),
                {"qualified_name": f"public.{table_name}"},
            )
    except OperationalError as exc:
        message = f"B2.4-P7 PostgreSQL runtime proof unavailable: {exc}"
        if _require_db_proofs():
            pytest.fail(message)
        pytest.skip(message)
    if result.scalar() is None:
        message = f"B2.4-P7 PostgreSQL runtime proof table is missing: {table_name}"
        if _require_db_proofs():
            pytest.fail(message)
        pytest.skip(message)


async def _insert_test_fit(
    tenant_id: UUID,
    *,
    fit_id: UUID | None = None,
    status: str = "succeeded",
    credible_interval_status: str = "not_available",
    diagnostic_status: str = "failed",
    diagnostic_failure_reason: str | None = "bad_rhat",
    fallback_applied: bool = True,
    fallback_reason: str | None = "no_convergence",
    r_hat_max: float | None = 1.02,
    ess_min: float | None = 500.0,
    divergence_count: int | None = 0,
    hdi_lower: float | None = None,
    hdi_upper: float | None = None,
    interval_element_count: int | None = 0,
) -> UUID:
    resolved_fit_id = fit_id or uuid4()
    async with get_session(tenant_id) as session:
        await session.execute(
            text(
                """
                INSERT INTO public.bayesian_model_fits (
                    tenant_id,
                    id,
                    model_type,
                    model_version,
                    source_window_start,
                    source_window_end,
                    source_snapshot_hash,
                    status,
                    eligibility_status,
                    data_completeness_status,
                    fallback_applied,
                    fallback_reason,
                    max_runtime_seconds,
                    max_samples,
                    max_cores,
                    n_chains,
                    n_samples_actual,
                    r_hat_max,
                    ess_min,
                    divergence_count,
                    hdi_lower,
                    hdi_upper,
                    interval_shape,
                    interval_element_count,
                    interval_summary_bytes,
                    credible_interval_status,
                    diagnostic_status,
                    diagnostic_failure_reason,
                    diagnostic_policy_version,
                    diagnostic_target_filter_version,
                    interval_policy_version,
                    diagnostics_computed_at
                )
                VALUES (
                    :tenant_id,
                    :fit_id,
                    'bayesian_attribution_confidence',
                    :model_version,
                    :source_window_start,
                    :source_window_end,
                    :source_snapshot_hash,
                    :status,
                    'eligible',
                    'complete',
                    :fallback_applied,
                    :fallback_reason,
                    60,
                    1000,
                    2,
                    2,
                    1000,
                    :r_hat_max,
                    :ess_min,
                    :divergence_count,
                    :hdi_lower,
                    :hdi_upper,
                    CAST(:interval_shape AS jsonb),
                    :interval_element_count,
                    256,
                    :credible_interval_status,
                    :diagnostic_status,
                    :diagnostic_failure_reason,
                    'b24-p7-diagnostic-policy-v1',
                    'b24-p7-target-filter-v1',
                    'b24-p7-interval-policy-v1',
                    now()
                )
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "fit_id": str(resolved_fit_id),
                "model_version": f"b24-p7-db-{uuid4().hex[:12]}",
                "source_window_start": START,
                "source_window_end": END,
                "source_snapshot_hash": VALID_HASH,
                "status": status,
                "fallback_applied": fallback_applied,
                "fallback_reason": fallback_reason,
                "r_hat_max": r_hat_max,
                "ess_min": ess_min,
                "divergence_count": divergence_count,
                "hdi_lower": hdi_lower,
                "hdi_upper": hdi_upper,
                "interval_shape": "[]",
                "interval_element_count": interval_element_count,
                "credible_interval_status": credible_interval_status,
                "diagnostic_status": diagnostic_status,
                "diagnostic_failure_reason": diagnostic_failure_reason,
            },
        )
    return resolved_fit_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p7_db_rejects_available_interval_without_passed_diagnostics(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    tenant_id, _ = test_tenant_pair

    with pytest.raises((IntegrityError, DBAPIError)):
        await _insert_test_fit(
            tenant_id,
            credible_interval_status="available",
            diagnostic_status="failed",
            diagnostic_failure_reason="bad_rhat",
            fallback_applied=True,
            fallback_reason="no_convergence",
            r_hat_max=1.02,
            ess_min=500.0,
            divergence_count=0,
            hdi_lower=-0.1,
            hdi_upper=0.1,
            interval_element_count=1,
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p7_db_accepts_available_interval_only_with_passed_diagnostics(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    tenant_id, _ = test_tenant_pair

    fit_id = await _insert_test_fit(
        tenant_id,
        credible_interval_status="available",
        diagnostic_status="passed",
        diagnostic_failure_reason=None,
        fallback_applied=False,
        fallback_reason=None,
        r_hat_max=1.0,
        ess_min=500.0,
        divergence_count=0,
        hdi_lower=-0.1,
        hdi_upper=0.1,
        interval_element_count=1,
    )

    async with get_session(tenant_id) as session:
        row = (
            (
                await session.execute(
                    text(
                        """
                        SELECT credible_interval_status,
                               diagnostic_status,
                               diagnostic_failure_reason,
                               fallback_applied,
                               hdi_lower,
                               hdi_upper,
                               interval_element_count
                        FROM public.bayesian_model_fits
                        WHERE tenant_id = :tenant_id
                          AND id = :fit_id
                        """
                    ),
                    {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
                )
            )
            .mappings()
            .one()
        )

    assert row["credible_interval_status"] == "available"
    assert row["diagnostic_status"] == "passed"
    assert row["diagnostic_failure_reason"] is None
    assert row["fallback_applied"] is False
    assert float(row["hdi_lower"]) == pytest.approx(-0.1)
    assert float(row["hdi_upper"]) == pytest.approx(0.1)
    assert int(row["interval_element_count"]) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p7_db_persists_representative_failure_states_unavailable(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    tenant_id, _ = test_tenant_pair
    cases = {
        "timeout": ("timeout", "timeout", "unavailable", "skipped_non_sampled"),
        "worker_failure": (
            "failed",
            "worker_failure",
            "unavailable",
            "skipped_non_sampled",
        ),
        "insufficient_data": (
            "fallback_only",
            "insufficient_data",
            "unavailable",
            "skipped_non_sampled",
        ),
        "source_snapshot_mismatch": (
            "failed",
            "source_snapshot_mismatch",
            "unavailable",
            "skipped_non_sampled",
        ),
        "input_too_large": (
            "fallback_only",
            "input_too_large",
            "unavailable",
            "skipped_non_sampled",
        ),
        "feature_width_exceeded": (
            "fallback_only",
            "feature_width_exceeded",
            "unavailable",
            "skipped_non_sampled",
        ),
        "memory_bound_exceeded": (
            "fallback_only",
            "memory_bound_exceeded",
            "unavailable",
            "skipped_non_sampled",
        ),
        "sampler_health_failed": (
            "failed",
            "sampler_health_failed",
            "unavailable",
            "skipped_non_sampled",
        ),
        "policy_rejected": (
            "failed",
            "policy_rejected",
            "unavailable",
            "skipped_non_sampled",
        ),
        "duplicate_fit_suppressed": (
            "failed",
            "duplicate_fit_suppressed",
            "unavailable",
            "skipped_non_sampled",
        ),
        "diagnostics_failed": (
            "succeeded",
            "no_convergence",
            "error",
            "diagnostics_failed",
        ),
        "diagnostics_timeout": (
            "succeeded",
            "no_convergence",
            "error",
            "diagnostics_timeout",
        ),
        "diagnostic_scope_too_large": (
            "succeeded",
            "no_convergence",
            "failed",
            "diagnostic_scope_too_large",
        ),
        "interval_dimension_exceeded": (
            "succeeded",
            "no_convergence",
            "failed",
            "interval_dimension_exceeded",
        ),
        "interval_payload_too_large": (
            "succeeded",
            "no_convergence",
            "failed",
            "interval_payload_too_large",
        ),
    }

    inserted: list[UUID] = []
    for _, (status, fallback_reason, diagnostic_status, diagnostic_reason) in cases.items():
        inserted.append(
            await _insert_test_fit(
                tenant_id,
                status=status,
                credible_interval_status="not_available",
                diagnostic_status=diagnostic_status,
                diagnostic_failure_reason=diagnostic_reason,
                fallback_applied=True,
                fallback_reason=fallback_reason,
                r_hat_max=None,
                ess_min=None,
                divergence_count=0,
                hdi_lower=None,
                hdi_upper=None,
                interval_element_count=0,
            )
        )

    async with get_session(tenant_id) as session:
        rows = (
            (
                await session.execute(
                    text(
                        """
                        SELECT credible_interval_status,
                               fallback_reason,
                               diagnostic_status,
                               diagnostic_failure_reason
                        FROM public.bayesian_model_fits
                        WHERE tenant_id = :tenant_id
                          AND id = ANY(CAST(:fit_ids AS uuid[]))
                        """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "fit_ids": [str(fit_id) for fit_id in inserted],
                    },
                )
            )
            .mappings()
            .all()
        )

    assert len(rows) == len(cases)
    for row in rows:
        assert row["credible_interval_status"] == "not_available"
        assert row["fallback_reason"] is not None
        assert row["diagnostic_status"] in {"failed", "error", "unavailable"}
        assert row["diagnostic_failure_reason"] is not None
