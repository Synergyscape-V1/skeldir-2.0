from __future__ import annotations

import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.bayesian.api_projection import (
    build_b24_confidence_projection_query,
    build_projection_models,
)
from app.bayesian.artifact_repository import (
    persist_artifact_sync,
    prune_expired_artifacts_sync,
    verify_artifact_bytes_sync,
)
from app.bayesian.enums import FallbackReason
from app.bayesian.feature_authority import (
    FeatureAuthorityStatus,
    SourceWindowFeatureAuthority,
    upsert_source_window_feature_authority,
)
from app.bayesian.input_profile import B24InputProfile
from app.bayesian.model_spec import B24_P6_MODEL_TYPE, B24_P6_MODEL_VERSION
from app.bayesian.resource_profile import evaluate_input_profile_resource_bounds
from app.bayesian.dispatch_authority import (
    BAYESIAN_FIT_EXECUTION_TASK,
    BayesianDispatchClaim,
    BayesianDispatchLease,
    BayesianWorkerClaimAuthority,
    claim_fit_dispatch_sync,
    dispatch_payload_hash,
    mark_dispatch_running_sync,
    register_worker_process_authority_sync,
)
from app.bayesian.e2e_harness import (
    P12_CA1_MEMORY_CEILING_BYTES,
    P12TerminalStateTimeout,
    canonical_projection_json,
    run_p12_worker_boundary_subprocess,
    wait_for_fit_terminal_state_sync,
)
from app.bayesian.resource_bounds import (
    B24_RESOURCE_POLICY,
    B24_RESOURCE_POLICY_VERSION,
)
from app.bayesian.source_snapshot import compute_source_snapshot_hash
from app.core.secrets import get_database_url
from app.db.dsn import to_sync_postgres_dsn
from app.db.session import AsyncSessionLocal, engine, get_session


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts/ci/validate_b24_p12_internal_e2e.py"
P12_TEST = ROOT / "backend/tests/test_b24_p12_internal_e2e.py"
P12_HARNESS = ROOT / "backend/app/bayesian/e2e_harness.py"
FIT_CLAIM = ROOT / "backend/app/bayesian/fit_claim.py"
FIT_EXECUTION = ROOT / "backend/app/bayesian/fit_execution.py"
RESOURCE_PROFILE = ROOT / "backend/app/bayesian/resource_profile.py"
RESOURCE_BOUNDS = ROOT / "backend/app/bayesian/resource_bounds.py"
ENUMS = ROOT / "backend/app/bayesian/enums.py"
API_PROJECTION = ROOT / "backend/app/bayesian/api_projection.py"
MAIN = ROOT / "backend/app/main.py"
API_DIR = ROOT / "backend/app/api"
START = datetime(2026, 5, 1, tzinfo=timezone.utc)
END = datetime(2026, 6, 1, tzinfo=timezone.utc)
P12_CA1_REPRESENTATIVE_EVENT_COUNT = 512
P12_CA1_REPRESENTATIVE_CHANNEL_COUNT = 32
P12_CA1_REPRESENTATIVE_CAMPAIGN_COUNT = 128
P12_CA1_EXPECTED_SOURCE_ROWS = P12_CA1_REPRESENTATIVE_EVENT_COUNT * 3
DB_PROOF_SKIP = pytest.mark.skipif(
    os.getenv("SKELDIR_B24_P12_REQUIRE_DB_PROOFS", "0").strip().lower()
    not in {"1", "true", "yes", "on"}
    and os.getenv("CI", "").strip().lower() != "true",
    reason="B2.4-P12 PostgreSQL proof is opt-in for local runs",
)



from app.bayesian.inference_profile import B24_INFERENCE_PROFILE

#: Budget and producing regime, exactly as the production claim path
#: stamps them at insert. The literals these replace were 60/160/1 -- a
#: sample budget the current policy refuses -- and the regime was absent
#: entirely, so the completion write became a policy change after
#: sampling had already started.
_C11_FIT_AUTHORITY_PARAMS = {
    "max_runtime_seconds": B24_INFERENCE_PROFILE.fit_execution_budget_seconds,
    "max_samples": B24_INFERENCE_PROFILE.total_chain_iterations,
    "max_cores": B24_INFERENCE_PROFILE.cores,
    "inference_profile_version": B24_INFERENCE_PROFILE.profile_version,
    "runtime_policy_version": B24_INFERENCE_PROFILE.runtime_policy_version,
    "sampling_policy_version": B24_INFERENCE_PROFILE.sampling_policy_version,
    "diagnostic_policy_version": (
        B24_INFERENCE_PROFILE.diagnostic_policy_version
    ),
    "policy_bundle_hash": B24_INFERENCE_PROFILE.policy_bundle_hash(),
    "authorized_chains": B24_INFERENCE_PROFILE.chains,
    "authorized_posterior_draws_total": (
        B24_INFERENCE_PROFILE.posterior_draws_total
    ),
}


def _require_db_proofs() -> bool:
    import os

    return os.getenv("SKELDIR_B24_P12_REQUIRE_DB_PROOFS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _sync_engine():
    return create_engine(
        to_sync_postgres_dsn(get_database_url()),
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=0,
    )


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _p12_ca1_telemetry_path(name: str) -> Path:
    root = os.getenv("SKELDIR_B24_P12_CA1_TELEMETRY_DIR")
    base = Path(root) if root else ROOT / "artifacts/b24_p12_ca1"
    return base / name


async def _assert_table_exists(table_name: str) -> None:
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT to_regclass(:qualified_name)"),
                {"qualified_name": f"public.{table_name}"},
            )
    except OperationalError as exc:
        message = f"B2.4-P12 PostgreSQL proof unavailable: {exc}"
        if _require_db_proofs():
            pytest.fail(message)
        pytest.skip(message)
    if result.scalar() is None:
        message = f"B2.4-P12 PostgreSQL proof table is missing: {table_name}"
        if _require_db_proofs():
            pytest.fail(message)
        pytest.skip(message)


async def _insert_test_fit(
    tenant_id: UUID,
    *,
    fit_id: UUID,
    source_hash: str,
    status: str = "queued",
    model_version: str | None = None,
) -> None:
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
                    max_runtime_seconds,
                    max_samples,
                    max_cores,
                    inference_profile_version,
                    runtime_policy_version,
                    sampling_policy_version,
                    diagnostic_policy_version,
                    policy_bundle_hash,
                    authorized_chains,
                    authorized_posterior_draws_total
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
                    false,
                    :max_runtime_seconds,
                    :max_samples,
                    :max_cores,
                    :inference_profile_version,
                    :runtime_policy_version,
                    :sampling_policy_version,
                    :diagnostic_policy_version,
                    :policy_bundle_hash,
                    :authorized_chains,
                    :authorized_posterior_draws_total
                )
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "fit_id": str(fit_id),
                "model_version": model_version or f"b24-p12-{uuid4().hex[:12]}",
                "source_window_start": START,
                "source_window_end": END,
                "source_snapshot_hash": source_hash,
                **_C11_FIT_AUTHORITY_PARAMS,
                "status": status,
            },
        )


def _insert_test_fit_sync(
    conn,
    tenant_id: UUID,
    *,
    fit_id: UUID,
    source_hash: str,
    status: str = "queued",
    model_version: str | None = None,
) -> None:
    conn.execute(
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
                max_runtime_seconds,
                max_samples,
                max_cores,
                inference_profile_version,
                runtime_policy_version,
                sampling_policy_version,
                diagnostic_policy_version,
                policy_bundle_hash,
                authorized_chains,
                authorized_posterior_draws_total
            )
            VALUES (
                :tenant_id,
                :fit_id,
                :model_type,
                :model_version,
                :source_window_start,
                :source_window_end,
                :source_snapshot_hash,
                :status,
                'eligible',
                'complete',
                false,
                :max_runtime_seconds,
                :max_samples,
                :max_cores,
                :inference_profile_version,
                :runtime_policy_version,
                :sampling_policy_version,
                :diagnostic_policy_version,
                :policy_bundle_hash,
                :authorized_chains,
                :authorized_posterior_draws_total
            )
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "fit_id": str(fit_id),
            "model_type": B24_P6_MODEL_TYPE,
            "model_version": model_version or f"b24-p12-{uuid4().hex[:12]}",
            "source_window_start": START,
            "source_window_end": END,
            "source_snapshot_hash": source_hash,
            **_C11_FIT_AUTHORITY_PARAMS,
            "status": status,
        },
    )


async def _seed_p12_ca1_representative_source_rows(
    tenant_id: UUID, suffix: str
) -> None:
    async with engine.begin() as conn:
        for index in range(P12_CA1_REPRESENTATIVE_CHANNEL_COUNT):
            await conn.execute(
                text(
                    """
                    INSERT INTO public.channel_taxonomy (
                        code,
                        family,
                        is_paid,
                        display_name,
                        state
                    )
                    VALUES (:code, 'b24_p12_ca1', true, :display_name, 'active')
                    ON CONFLICT (code) DO NOTHING
                    """
                ),
                {
                    "code": f"p12ca1_{suffix}_{index:02d}",
                    "display_name": f"P12 CA1 {suffix} {index:02d}",
                },
            )

    async with get_session(tenant_id) as session:
        for index in range(P12_CA1_REPRESENTATIVE_EVENT_COUNT):
            event_id = uuid4()
            verdict_id = uuid4()
            revenue_cents = 10_000 + index
            occurred_at = START + timedelta(days=index % 30, seconds=index)
            channel_index = index % P12_CA1_REPRESENTATIVE_CHANNEL_COUNT
            campaign_index = index % P12_CA1_REPRESENTATIVE_CAMPAIGN_COUNT
            channel = f"p12ca1_{suffix}_{channel_index:02d}"
            await session.execute(
                text(
                    """
                    INSERT INTO public.attribution_events (
                        id,
                        tenant_id,
                        occurred_at,
                        correlation_id,
                        session_id,
                        revenue_cents,
                        raw_payload,
                        idempotency_key,
                        event_type,
                        channel,
                        campaign_id,
                        conversion_value_cents,
                        currency,
                        event_timestamp,
                        processed_at,
                        processing_status
                    )
                    VALUES (
                        :event_id,
                        :tenant_id,
                        :occurred_at,
                        :correlation_id,
                        :session_id,
                        :revenue_cents,
                        CAST(:raw_payload AS jsonb),
                        :idempotency_key,
                        'conversion',
                        :channel,
                        :campaign_id,
                        :revenue_cents,
                        'USD',
                        :occurred_at,
                        :occurred_at,
                        'processed'
                    )
                    """
                ),
                {
                    "event_id": str(event_id),
                    "tenant_id": str(tenant_id),
                    "occurred_at": occurred_at,
                    "correlation_id": str(uuid4()),
                    "session_id": str(uuid4()),
                    "revenue_cents": revenue_cents,
                    "raw_payload": json.dumps(
                        {
                            "source": "b24_p12_ca1_representative_worker_proof",
                            "n": index,
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    "idempotency_key": f"p12-ca1:{suffix}:{index}",
                    "channel": channel,
                    "campaign_id": f"campaign_{suffix}_{campaign_index:03d}",
                },
            )
            await session.execute(
                text(
                    """
                    INSERT INTO public.b23_match_verdicts (
                        id,
                        tenant_id,
                        attribution_event_id,
                        provider,
                        canonical_commerce_reference,
                        provider_native_event_reference,
                        provider_native_commerce_reference,
                        status,
                        match_quality,
                        attributed_amount_minor,
                        verified_amount_minor,
                        currency_code,
                        confirmed_at,
                        last_transition_at,
                        canonical_expected_gross_amount_minor,
                        canonical_captured_gross_amount_minor,
                        canonical_net_verified_amount_minor,
                        discrepancy_amount_minor,
                        discrepancy_ratio_bps,
                        discrepancy_band
                    )
                    VALUES (
                        :verdict_id,
                        :tenant_id,
                        :event_id,
                        'stripe',
                        :commerce_ref,
                        :event_ref,
                        :commerce_ref,
                        'matched_confirmed',
                        'high',
                        :amount_minor,
                        :amount_minor,
                        'USD',
                        :occurred_at,
                        :occurred_at,
                        :amount_minor,
                        :amount_minor,
                        :amount_minor,
                        0,
                        0,
                        'exact'
                    )
                    """
                ),
                {
                    "verdict_id": str(verdict_id),
                    "tenant_id": str(tenant_id),
                    "event_id": str(event_id),
                    "commerce_ref": f"order_{suffix}_{index:04d}",
                    "event_ref": f"evt_{suffix}_{index:04d}",
                    "amount_minor": revenue_cents,
                    "occurred_at": occurred_at,
                },
            )
            await session.execute(
                text(
                    """
                    INSERT INTO public.b23_revenue_events (
                        tenant_id,
                        match_verdict_id,
                        provider,
                        provider_native_event_reference,
                        provider_native_commerce_reference,
                        canonical_commerce_reference,
                        event_type,
                        currency_code,
                        event_occurred_at,
                        captured_amount_minor,
                        net_effect_sign,
                        is_gross_capture_correction
                    )
                    VALUES (
                        :tenant_id,
                        :verdict_id,
                        'stripe',
                        :event_ref,
                        :commerce_ref,
                        :commerce_ref,
                        'payment_capture',
                        'USD',
                        :occurred_at,
                        :amount_minor,
                        1,
                        false
                    )
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "verdict_id": str(verdict_id),
                    "event_ref": f"capture_{suffix}_{index:04d}",
                    "commerce_ref": f"order_{suffix}_{index:04d}",
                    "occurred_at": occurred_at,
                    "amount_minor": revenue_cents,
                },
            )


async def _p12_ca1_snapshot_hash(tenant_id: UUID):
    async with AsyncSessionLocal() as session:
        return await compute_source_snapshot_hash(
            session,
            tenant_id=tenant_id,
            model_type=B24_P6_MODEL_TYPE,
            model_version=B24_P6_MODEL_VERSION,
            source_window_start=START,
            source_window_end=END,
        )


async def _insert_p12_ca1_feature_authority(
    tenant_id: UUID,
    *,
    source_snapshot_hash: str,
) -> None:
    async with get_session(tenant_id) as session:
        await upsert_source_window_feature_authority(
            session,
            authority=SourceWindowFeatureAuthority(
                tenant_id=tenant_id,
                model_type=B24_P6_MODEL_TYPE,
                model_version=B24_P6_MODEL_VERSION,
                source_window_start=START,
                source_window_end=END,
                source_snapshot_hash=source_snapshot_hash,
                channel_count=P12_CA1_REPRESENTATIVE_CHANNEL_COUNT,
                currency_count=1,
                provider_count=1,
                campaign_or_feature_count=P12_CA1_REPRESENTATIVE_CAMPAIGN_COUNT,
                freshness_status=FeatureAuthorityStatus.FRESH,
                policy_version=B24_RESOURCE_POLICY_VERSION,
                computed_at=START,
            ),
        )


def _insert_p12_ca1_dispatch_outbox(
    conn,
    *,
    tenant_id: UUID,
    fit_id: UUID,
    worker_generation_id: str,
) -> tuple[UUID, UUID]:
    dispatch_id = uuid4()
    attempt_id = uuid4()
    conn.execute(
        text(
            """
            INSERT INTO public.b24_fit_dispatch_outbox (
                tenant_id,
                id,
                fit_id,
                dispatch_key,
                task_name,
                attempt_id,
                payload_hash,
                assigned_worker_generation,
                assignment_generation,
                assignment_expires_at,
                assignment_reason,
                status,
                next_attempt_at,
                next_recovery_at
            )
            VALUES (
                :tenant_id,
                :dispatch_id,
                :fit_id,
                :dispatch_key,
                :task_name,
                :attempt_id,
                :payload_hash,
                :assigned_worker_generation,
                1,
                now() + interval '10 minutes',
                'p12_ca1_worker_boundary_proof',
                'dispatched',
                now(),
                now() + interval '1 hour'
            )
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "dispatch_id": str(dispatch_id),
            "fit_id": str(fit_id),
            "dispatch_key": f"b24-p12-ca1:{tenant_id}:{fit_id}",
            "task_name": BAYESIAN_FIT_EXECUTION_TASK,
            "attempt_id": str(attempt_id),
            "payload_hash": dispatch_payload_hash(fit_id=fit_id),
            "assigned_worker_generation": worker_generation_id,
        },
    )
    return dispatch_id, attempt_id


def _bind_p12_dispatch_context(conn, *, tenant_id: UUID, fit_id: UUID) -> None:
    dispatch_id = uuid4()
    attempt_id = uuid4()
    payload_hash = dispatch_payload_hash(fit_id=fit_id)
    generation_id = f"p12-proof-{uuid4().hex[:16]}"
    worker_authority = BayesianWorkerClaimAuthority(
        generation_id=generation_id,
        pid=4242,
        process_token=f"p12-token-{uuid4().hex}",
    )
    register_worker_process_authority_sync(
        conn,
        generation_id=worker_authority.generation_id,
        pid=worker_authority.pid,
        parent_pid=1,
        topology_fingerprint="c" * 64,
        process_token=worker_authority.process_token,
        ttl_seconds=3600,
    )
    conn.execute(
        text(
            """
            INSERT INTO public.b24_fit_dispatch_outbox (
                tenant_id,
                id,
                fit_id,
                dispatch_key,
                task_name,
                attempt_id,
                payload_hash,
                assigned_worker_generation,
                assignment_generation,
                assignment_expires_at,
                assignment_reason,
                status,
                next_attempt_at,
                next_recovery_at
            )
            VALUES (
                :tenant_id,
                :dispatch_id,
                :fit_id,
                :dispatch_key,
                :task_name,
                :attempt_id,
                :payload_hash,
                :assigned_worker_generation,
                1,
                now() + interval '10 minutes',
                'p12_internal_e2e_proof',
                'dispatched',
                now(),
                now() + interval '1 hour'
            )
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "dispatch_id": str(dispatch_id),
            "fit_id": str(fit_id),
            "dispatch_key": f"b24-p12-test:{tenant_id}:{fit_id}",
            "task_name": BAYESIAN_FIT_EXECUTION_TASK,
            "attempt_id": str(attempt_id),
            "payload_hash": payload_hash,
            "assigned_worker_generation": generation_id,
        },
    )
    lease = claim_fit_dispatch_sync(
        conn,
        claim=BayesianDispatchClaim(
            dispatch_id=dispatch_id,
            fit_id=fit_id,
            task_name=BAYESIAN_FIT_EXECUTION_TASK,
            attempt_id=attempt_id,
            payload_hash=payload_hash,
            recovery_generation=0,
        ),
        worker_authority=worker_authority,
        lease_seconds=300,
    )
    assert isinstance(lease, BayesianDispatchLease)
    mark_dispatch_running_sync(conn, lease=lease)
    conn.execute(
        text(
            """
            UPDATE public.bayesian_model_fits
            SET status = 'running',
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND id = :fit_id
            """
        ),
        {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
    )


def _base_projection_row(**overrides):
    tenant_id = overrides.pop("tenant_id", uuid4())
    fit_id = overrides.pop("fit_id", uuid4())
    row = {
        "tenant_id": tenant_id,
        "currency_code": "USD",
        "deterministic_revenue_minor": 12_345,
        "deterministic_row_count": 3,
        "match_verdict_count": 3,
        "verification_event_count": 3,
        "source_snapshot_mismatch": False,
        "fit_id": fit_id,
        "fit_status": "succeeded",
        "model_type": "bayesian_attribution_confidence",
        "model_version": "b24-p12",
        "data_completeness_status": "complete",
        "fallback_applied": False,
        "fallback_reason": None,
        "r_hat_max": 1.0,
        "ess_min": 500.0,
        "divergence_count": 0,
        "hdi_lower": 12_000.0,
        "hdi_upper": 12_700.0,
        "credible_interval_status": "available",
        "diagnostic_status": "passed",
        "diagnostic_failure_reason": None,
        "diagnostic_policy_version": "b24-p7-diagnostic-policy-v1",
        "interval_policy_version": "b24-p7-interval-policy-v1",
        "hdi_probability": 0.95,
        "artifact_ref": f"b24://artifact/{tenant_id}/{fit_id}/diagnostics/{'a' * 12}",
        "artifact_hash": "a" * 64,
        "artifact_lifecycle_status": "active",
        "artifact_policy_version": "b24-p8-artifact-policy-v1",
    }
    row.update(overrides)
    return row


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_b24_p12_internal_e2e", VALIDATOR
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
@pytest.mark.integration
@DB_PROOF_SKIP
async def test_b24_p12_committed_visibility_and_uncommitted_negative_control(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    tenant_id, _ = test_tenant_pair
    fit_id = uuid4()
    source_hash = "1" * 64
    sync_engine = _sync_engine()
    try:
        writer = sync_engine.connect()
        transaction = writer.begin()
        writer.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        writer.execute(
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
                    max_runtime_seconds,
                    max_samples,
                    max_cores,
                    inference_profile_version,
                    runtime_policy_version,
                    sampling_policy_version,
                    diagnostic_policy_version,
                    policy_bundle_hash,
                    authorized_chains,
                    authorized_posterior_draws_total
                )
                VALUES (
                    :tenant_id,
                    :fit_id,
                    'bayesian_attribution_confidence',
                    :model_version,
                    :source_window_start,
                    :source_window_end,
                    :source_snapshot_hash,
                    'queued',
                    'eligible',
                    'complete',
                    false,
                    :max_runtime_seconds,
                    :max_samples,
                    :max_cores,
                    :inference_profile_version,
                    :runtime_policy_version,
                    :sampling_policy_version,
                    :diagnostic_policy_version,
                    :policy_bundle_hash,
                    :authorized_chains,
                    :authorized_posterior_draws_total
                )
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "fit_id": str(fit_id),
                "model_version": f"b24-p12-visibility-{uuid4().hex[:8]}",
                "source_window_start": START,
                "source_window_end": END,
                "source_snapshot_hash": source_hash,
                **_C11_FIT_AUTHORITY_PARAMS,
            },
        )
        with sync_engine.begin() as observer:
            observer.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            uncommitted_count = observer.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.bayesian_model_fits
                    WHERE tenant_id = :tenant_id AND id = :fit_id
                    """
                ),
                {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
            ).scalar_one()
        assert uncommitted_count == 0
        transaction.commit()
        writer.close()
        with sync_engine.begin() as observer:
            observer.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            committed_count = observer.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.bayesian_model_fits
                    WHERE tenant_id = :tenant_id AND id = :fit_id
                    """
                ),
                {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
            ).scalar_one()
        assert committed_count == 1
    finally:
        sync_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
@DB_PROOF_SKIP
async def test_b24_p12_terminal_waiter_is_state_driven_and_diagnostic(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    tenant_id, _ = test_tenant_pair
    fit_id = uuid4()
    await _insert_test_fit(tenant_id, fit_id=fit_id, source_hash="2" * 64)
    sync_engine = _sync_engine()
    try:
        with pytest.raises(P12TerminalStateTimeout) as exc_info:
            wait_for_fit_terminal_state_sync(
                engine=sync_engine,
                tenant_id=tenant_id,
                fit_id=fit_id,
                deadline_seconds=0.001,
            )
        assert exc_info.value.last_observed is not None
        assert exc_info.value.last_observed["status"] == "queued"
        with sync_engine.begin() as conn:
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            _bind_p12_dispatch_context(conn, tenant_id=tenant_id, fit_id=fit_id)
            conn.execute(
                text(
                    """
                    UPDATE public.bayesian_model_fits
                    SET status = 'failed',
                        fallback_applied = true,
                        fallback_reason = 'worker_failure',
                        diagnostic_status = 'unavailable',
                        diagnostic_failure_reason = 'skipped_non_sampled',
                        completed_at = now(),
                        updated_at = now()
                    WHERE tenant_id = :tenant_id AND id = :fit_id
                    """
                ),
                {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
            )
        terminal = wait_for_fit_terminal_state_sync(
            engine=sync_engine,
            tenant_id=tenant_id,
            fit_id=fit_id,
            deadline_seconds=1,
        )
        assert terminal.status == "failed"
        assert terminal.fallback_reason == "worker_failure"
        assert terminal.credible_interval_status == "not_available"
    finally:
        sync_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
@DB_PROOF_SKIP
async def test_b24_p12_ca1_subprocess_worker_boundary_consumes_committed_representative_state(
    test_tenant_pair,
    record_property,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    await _assert_table_exists("b24_fit_dispatch_outbox")
    await _assert_table_exists("b24_source_window_feature_authority")
    tenant_id, _ = test_tenant_pair
    suffix = uuid4().hex[:8]
    fit_id = uuid4()
    await _seed_p12_ca1_representative_source_rows(tenant_id, suffix)
    snapshot = await _p12_ca1_snapshot_hash(tenant_id)
    assert snapshot.preflight.is_eligible
    assert snapshot.preflight.included_row_counts_by_source == {
        "attribution_events": P12_CA1_REPRESENTATIVE_EVENT_COUNT,
        "attribution_allocations": 0,
        "b23_match_verdicts": P12_CA1_REPRESENTATIVE_EVENT_COUNT,
        "b23_revenue_events": P12_CA1_REPRESENTATIVE_EVENT_COUNT,
    }
    await _insert_p12_ca1_feature_authority(
        tenant_id,
        source_snapshot_hash=snapshot.source_snapshot_hash,
    )
    await _insert_test_fit(
        tenant_id,
        fit_id=fit_id,
        source_hash=snapshot.source_snapshot_hash,
        model_version=B24_P6_MODEL_VERSION,
    )
    worker_generation_id = f"p12-ca1-worker-{uuid4().hex}"
    worker_process_token = f"p12-ca1-token-{uuid4().hex}"
    telemetry_path = _p12_ca1_telemetry_path(f"worker-boundary-{fit_id}.json")
    sync_engine = _sync_engine()
    try:
        with sync_engine.begin() as conn:
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            dispatch_id, attempt_id = _insert_p12_ca1_dispatch_outbox(
                conn,
                tenant_id=tenant_id,
                fit_id=fit_id,
                worker_generation_id=worker_generation_id,
            )
        parent_backend_pid = None
        with sync_engine.begin() as conn:
            parent_backend_pid = int(
                conn.execute(text("SELECT pg_backend_pid()")).scalar_one()
            )
        result = run_p12_worker_boundary_subprocess(
            database_url=to_sync_postgres_dsn(get_database_url()),
            tenant_id=tenant_id,
            fit_id=fit_id,
            dispatch_id=dispatch_id,
            attempt_id=attempt_id,
            worker_generation_id=worker_generation_id,
            worker_process_token=worker_process_token,
            telemetry_path=telemetry_path,
            expected_min_source_rows=P12_CA1_EXPECTED_SOURCE_ROWS,
            expected_channel_count=P12_CA1_REPRESENTATIVE_CHANNEL_COUNT,
            expected_campaign_count=P12_CA1_REPRESENTATIVE_CAMPAIGN_COUNT,
            memory_ceiling_bytes=P12_CA1_MEMORY_CEILING_BYTES,
            preclaim_visibility_negative_control=True,
        )
        if result.returncode != 0:
            pytest.fail(
                json.dumps(
                    {
                        "returncode": result.returncode,
                        "telemetry": result.telemetry,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                    },
                    indent=2,
                    sort_keys=True,
                ),
                pytrace=False,
            )
        terminal = wait_for_fit_terminal_state_sync(
            engine=sync_engine,
            tenant_id=tenant_id,
            fit_id=fit_id,
            deadline_seconds=5,
        )
        telemetry = result.telemetry
        record_property(
            "b24_p12_ca1_worker_boundary", json.dumps(telemetry, sort_keys=True)
        )
        assert terminal.status == "succeeded"
        assert telemetry["terminal_status"] == "succeeded"
        assert telemetry["claim_outcome"] == "ACQUIRED"
        assert telemetry["compute_started"] is True
        assert telemetry["tenant_id"] == str(tenant_id)
        assert telemetry["fit_id"] == str(fit_id)
        assert telemetry["source_snapshot_hash"] == snapshot.source_snapshot_hash
        assert telemetry["streamed_source_row_count"] == P12_CA1_EXPECTED_SOURCE_ROWS
        assert telemetry["worker_process_id"] != os.getpid()
        assert telemetry["worker_db_backend_pid"] != parent_backend_pid
        assert telemetry["worker_replay_db_backend_pid"] != parent_backend_pid
        assert int(telemetry["peak_rss_bytes"]) > 0
        assert int(telemetry["peak_rss_bytes"]) < P12_CA1_MEMORY_CEILING_BYTES
        assert telemetry["memory_ceiling_bytes"] == P12_CA1_MEMORY_CEILING_BYTES
        assert terminal.artifact_ref == telemetry["artifact_ref"]
        assert terminal.artifact_hash == telemetry["artifact_hash"]
        with sync_engine.begin() as conn:
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            assert verify_artifact_bytes_sync(
                conn,
                tenant_id=tenant_id,
                artifact_ref=str(telemetry["artifact_ref"]),
            )
    finally:
        sync_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
@DB_PROOF_SKIP
async def test_b24_p12_ca1_subprocess_worker_boundary_negative_control_rejects_uncommitted_state(
    test_tenant_pair,
    record_property,
) -> None:
    await _assert_table_exists("bayesian_model_fits")
    await _assert_table_exists("b24_fit_dispatch_outbox")
    tenant_id, _ = test_tenant_pair
    fit_id = uuid4()
    worker_generation_id = f"p12-ca1-negative-worker-{uuid4().hex}"
    worker_process_token = f"p12-ca1-negative-token-{uuid4().hex}"
    telemetry_path = _p12_ca1_telemetry_path(f"worker-boundary-negative-{fit_id}.json")
    sync_engine = _sync_engine()
    writer = sync_engine.connect()
    transaction = writer.begin()
    try:
        writer.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        _insert_test_fit_sync(
            writer,
            tenant_id,
            fit_id=fit_id,
            source_hash="a" * 64,
            model_version=f"b24-p12-ca1-negative-{uuid4().hex[:8]}",
        )
        dispatch_id, attempt_id = _insert_p12_ca1_dispatch_outbox(
            writer,
            tenant_id=tenant_id,
            fit_id=fit_id,
            worker_generation_id=worker_generation_id,
        )
        result = run_p12_worker_boundary_subprocess(
            database_url=to_sync_postgres_dsn(get_database_url()),
            tenant_id=tenant_id,
            fit_id=fit_id,
            dispatch_id=dispatch_id,
            attempt_id=attempt_id,
            worker_generation_id=worker_generation_id,
            worker_process_token=worker_process_token,
            telemetry_path=telemetry_path,
            expected_min_source_rows=P12_CA1_EXPECTED_SOURCE_ROWS,
            expected_channel_count=P12_CA1_REPRESENTATIVE_CHANNEL_COUNT,
            expected_campaign_count=P12_CA1_REPRESENTATIVE_CAMPAIGN_COUNT,
            memory_ceiling_bytes=P12_CA1_MEMORY_CEILING_BYTES,
            preclaim_visibility_negative_control=True,
        )
        telemetry = result.telemetry
        record_property(
            "b24_p12_ca1_worker_negative_control", json.dumps(telemetry, sort_keys=True)
        )
        assert result.returncode == 3
        assert telemetry["worker_process_id"] != os.getpid()
        assert telemetry["terminal_status"] == "not_visible"
        assert telemetry["compute_started"] is False
        assert telemetry["negative_control"] == (
            "separate_worker_connection_cannot_observe_uncommitted_fit"
        )
        with sync_engine.begin() as observer:
            observer.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            assert (
                observer.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM public.bayesian_model_fits
                        WHERE tenant_id = :tenant_id AND id = :fit_id
                        """
                    ),
                    {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
                ).scalar_one()
                == 0
            )
    finally:
        transaction.rollback()
        writer.close()
        sync_engine.dispose()


def test_b24_p12_async_coordination_uses_no_arbitrary_sleep() -> None:
    test_text = _read(P12_TEST)
    harness_text = _read(P12_HARNESS)
    sleep_token = "time." + "sleep("
    assert sleep_token not in test_text
    assert sleep_token not in harness_text
    assert "time.monotonic()" in harness_text
    assert "P12_TERMINAL_FIT_STATUSES" in harness_text
    assert "last_observed" in harness_text


def test_b24_p12_positive_projection_payload_is_backend_owned_and_sealed() -> None:
    projection = build_projection_models(
        [_base_projection_row()],
        source_window_start=START,
        source_window_end=END,
        source_snapshot_hash="3" * 64,
        generated_at=END,
    )[0]
    payload_a = canonical_projection_json(projection)
    payload_b = canonical_projection_json(projection)
    assert payload_a == payload_b
    assert b"confidence_bucket" in payload_a
    assert b"backend_b24_p10_policy" in payload_a
    assert b"<|" not in payload_a
    with pytest.raises(PydanticValidationError):
        build_projection_models(
            [_base_projection_row(fallback_applied=True, fallback_reason="<|system|>")],
            source_window_start=START,
            source_window_end=END,
            source_snapshot_hash="3" * 64,
            generated_at=END,
        )


def test_b24_p12_cold_start_projection_is_reason_coded_without_sampling() -> None:
    projection = build_projection_models(
        [
            _base_projection_row(
                fit_status="fallback_only",
                fallback_applied=True,
                fallback_reason="insufficient_data",
                sampling_started_at=None,
                diagnostic_status="unavailable",
                credible_interval_status="not_available",
                hdi_lower=None,
                hdi_upper=None,
                artifact_ref=None,
                artifact_hash=None,
            )
        ],
        source_window_start=START,
        source_window_end=END,
        source_snapshot_hash="4" * 64,
        generated_at=END,
    )[0]
    assert projection.deterministic.deterministic_revenue_minor == 12_345
    assert projection.confidence.confidence_available is False
    assert projection.confidence.confidence_bucket_reason == "insufficient_data"
    assert projection.bayesian.credible_interval.status == "unavailable"


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        (
            {"diagnostic_status": "failed", "diagnostic_failure_reason": "bad_rhat"},
            "bad_rhat",
        ),
        (
            {"diagnostic_status": "failed", "diagnostic_failure_reason": "low_ess"},
            "low_ess",
        ),
        (
            {"diagnostic_status": "failed", "diagnostic_failure_reason": "divergence"},
            "divergence",
        ),
    ],
)
def test_b24_p12_diagnostic_failures_block_intervals(overrides, reason: str) -> None:
    projection = build_projection_models(
        [_base_projection_row(**overrides)],
        source_window_start=START,
        source_window_end=END,
        source_snapshot_hash="5" * 64,
        generated_at=END,
    )[0]
    assert projection.confidence.confidence_available is False
    assert projection.confidence.confidence_bucket_reason == reason
    assert projection.bayesian.credible_interval.lower is None
    assert projection.bayesian.credible_interval.upper is None


def test_b24_p12_resource_and_duplicate_burst_controls_are_pre_worker() -> None:
    resource_text = "\n".join(
        (_read(RESOURCE_PROFILE), _read(RESOURCE_BOUNDS), _read(ENUMS))
    )
    claim_text = _read(FIT_CLAIM)
    for token in (
        "input_too_large",
        "feature_width_exceeded",
        "memory_bound_exceeded",
        "graph_complexity_exceeded",
    ):
        assert token in resource_text
    assert (
        "P4 resource authority rejected source snapshot before P6 materialization"
        in _read(ROOT / "backend/app/bayesian/source_snapshot.py")
    )
    assert "execution lease key intentionally excludes it" in claim_text
    assert "b24_active_execution_leases" in claim_text
    assert "source_snapshot_hash <> :source_snapshot_hash" in claim_text


def test_b24_p12_ca1_runtime_oversized_rejection_occurs_before_graph_or_sampler() -> (
    None
):
    oversized_profile = B24InputProfile(
        tenant_id=uuid4(),
        preflight_lease_id=f"p12-ca1-oversized-{uuid4().hex}",
        model_type=B24_P6_MODEL_TYPE,
        model_version=B24_P6_MODEL_VERSION,
        source_window_start=START,
        source_window_end=END,
        source_snapshot_hash="b" * 64,
        policy_version=B24_RESOURCE_POLICY_VERSION,
        source_row_count=B24_RESOURCE_POLICY.max_source_rows + 1,
        touchpoint_count=1,
        conversion_count=1,
        channel_count=1,
        currency_count=1,
        provider_count=1,
        campaign_or_feature_count=1,
        window_days=31,
        cardinality_profiled_dimensions=(
            "campaign_or_feature",
            "channel",
            "currency",
            "provider",
        ),
        computed_at=START,
    )
    decision = evaluate_input_profile_resource_bounds(
        input_profile=oversized_profile,
        policy=B24_RESOURCE_POLICY,
    )
    assert decision.allowed is False
    assert decision.failure_reason == FallbackReason.INPUT_TOO_LARGE
    assert decision.input_profile.source_row_count == (
        B24_RESOURCE_POLICY.max_source_rows + 1
    )


@pytest.mark.asyncio
@pytest.mark.integration
@DB_PROOF_SKIP
async def test_b24_p12_artifact_hash_corruption_and_pruning_degrade_auditably(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_artifacts")
    tenant_id, _ = test_tenant_pair
    fit_id = uuid4()
    await _insert_test_fit(tenant_id, fit_id=fit_id, source_hash="6" * 64)
    sync_engine = _sync_engine()
    try:
        with sync_engine.begin() as conn:
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            _bind_p12_dispatch_context(conn, tenant_id=tenant_id, fit_id=fit_id)
            artifact = persist_artifact_sync(
                conn,
                tenant_id=tenant_id,
                fit_id=fit_id,
                artifact_type="diagnostics",
                payload={
                    "schema_version": "b24-p12-artifact-v1",
                    "fit_id": str(fit_id),
                },
                retention_class="ephemeral",
            )
            assert verify_artifact_bytes_sync(
                conn, tenant_id=tenant_id, artifact_ref=str(artifact["artifact_ref"])
            )
            corrupt_hash = "0" * 64
            conn.execute(
                text(
                    """
                    UPDATE public.bayesian_artifacts
                    SET artifact_hash = :corrupt_hash
                    WHERE tenant_id = :tenant_id AND artifact_ref = :artifact_ref
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "artifact_ref": str(artifact["artifact_ref"]),
                    "corrupt_hash": corrupt_hash,
                },
            )
            assert not verify_artifact_bytes_sync(
                conn, tenant_id=tenant_id, artifact_ref=str(artifact["artifact_ref"])
            )
            conn.execute(
                text(
                    """
                    UPDATE public.bayesian_artifacts
                    SET expires_at = now() - interval '1 second'
                    WHERE tenant_id = :tenant_id AND artifact_ref = :artifact_ref
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "artifact_ref": str(artifact["artifact_ref"]),
                },
            )
            pruned = prune_expired_artifacts_sync(conn, tenant_id=tenant_id)
            assert pruned["pruned_count"] == 1
            tombstone = (
                conn.execute(
                    text(
                        """
                        SELECT lifecycle_status,
                               payload_bytes IS NULL AS payload_removed,
                               pruned_metadata->>'artifact_hash' AS pruned_hash
                        FROM public.bayesian_artifacts
                        WHERE tenant_id = :tenant_id AND artifact_ref = :artifact_ref
                        """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "artifact_ref": str(artifact["artifact_ref"]),
                    },
                )
                .mappings()
                .one()
            )
            assert tombstone["lifecycle_status"] == "pruned"
            assert tombstone["payload_removed"] is True
            assert tombstone["pruned_hash"] == corrupt_hash
            assert tombstone["pruned_hash"] != artifact["artifact_hash"]
    finally:
        sync_engine.dispose()


def test_b24_p12_projection_read_only_and_missing_fit_safe() -> None:
    sql = str(build_b24_confidence_projection_query()).lower()
    assert "with deterministic_left as" in sql
    assert "left outer join latest_matching_fit" in sql
    for forbidden in (
        "insert into",
        "update public.",
        "delete from",
        "send_task",
        "apply_async",
    ):
        assert forbidden not in _read(API_PROJECTION).lower()
    projection = build_projection_models(
        [
            _base_projection_row(
                fit_id=None,
                fit_status=None,
                model_type=None,
                model_version=None,
                fallback_applied=None,
                hdi_lower=None,
                hdi_upper=None,
                credible_interval_status=None,
                diagnostic_status=None,
                artifact_ref=None,
                artifact_hash=None,
            )
        ],
        source_window_start=START,
        source_window_end=END,
        source_snapshot_hash="7" * 64,
        generated_at=END,
    )[0]
    assert projection.deterministic.deterministic_revenue_minor == 12_345
    assert projection.confidence.confidence_bucket_reason == "no_fit"
    assert projection.audit.projection_read_only is True


def test_b24_p12_source_snapshot_drift_blocks_current_confidence() -> None:
    projection = build_projection_models(
        [_base_projection_row(source_snapshot_mismatch=True)],
        source_window_start=START,
        source_window_end=END,
        source_snapshot_hash="8" * 64,
        generated_at=END,
    )[0]
    assert projection.confidence.confidence_available is False
    assert projection.confidence.confidence_bucket_reason == "source_snapshot_changed"
    assert projection.deterministic.deterministic_revenue_minor == 12_345


@pytest.mark.asyncio
@pytest.mark.integration
@DB_PROOF_SKIP
async def test_b24_p12_sequential_tenant_artifact_and_projection_isolation(
    test_tenant_pair,
) -> None:
    await _assert_table_exists("bayesian_artifacts")
    tenant_a, tenant_b = test_tenant_pair
    fit_a = uuid4()
    fit_b = uuid4()
    await _insert_test_fit(tenant_a, fit_id=fit_a, source_hash="9" * 64)
    await _insert_test_fit(tenant_b, fit_id=fit_b, source_hash="9" * 64)
    sync_engine = _sync_engine()
    try:
        refs: list[str] = []
        for tenant_id, fit_id in ((tenant_a, fit_a), (tenant_b, fit_b)):
            with sync_engine.begin() as conn:
                conn.execute(
                    text(
                        "SELECT set_config('app.current_tenant_id', :tenant_id, true)"
                    ),
                    {"tenant_id": str(tenant_id)},
                )
                _bind_p12_dispatch_context(conn, tenant_id=tenant_id, fit_id=fit_id)
                artifact = persist_artifact_sync(
                    conn,
                    tenant_id=tenant_id,
                    fit_id=fit_id,
                    artifact_type="diagnostics",
                    payload={
                        "schema_version": "b24-p12-tenant-v1",
                        "fit_id": str(fit_id),
                    },
                    retention_class="standard",
                )
                refs.append(str(artifact["artifact_ref"]))
        assert refs[0] != refs[1]
        assert str(tenant_a) in refs[0]
        assert str(tenant_b) in refs[1]
        projection_a = build_projection_models(
            [
                _base_projection_row(
                    tenant_id=tenant_a, fit_id=fit_a, artifact_ref=refs[0]
                )
            ],
            source_window_start=START,
            source_window_end=END,
            source_snapshot_hash="9" * 64,
            generated_at=END,
        )[0]
        projection_b = build_projection_models(
            [
                _base_projection_row(
                    tenant_id=tenant_b, fit_id=fit_b, artifact_ref=refs[1]
                )
            ],
            source_window_start=START,
            source_window_end=END,
            source_snapshot_hash="9" * 64,
            generated_at=END,
        )[0]
        assert projection_a.deterministic.tenant_id == tenant_a
        assert projection_b.deterministic.tenant_id == tenant_b
        assert projection_a.bayesian.artifact_ref != projection_b.bayesian.artifact_ref
    finally:
        sync_engine.dispose()


def test_b24_p12_boundary_scans_no_public_route_llm_action_or_overclaim() -> None:
    api_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in API_DIR.glob("*.py")
    )
    bayesian_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (ROOT / "backend/app/bayesian").glob("*.py")
    )
    assert "api_projection" not in api_text
    assert "api_projection" not in _read(MAIN)
    for forbidden in (
        "app.llm",
        "openai",
        "anthropic",
        "recommendation",
        "budget_mutation",
    ):
        assert forbidden not in bayesian_text
    assert "cleanup_fit_attempt(workspace=workspace, compiledir=lease)" in _read(
        FIT_EXECUTION
    )
    dispatch_authority = _read(ROOT / "backend/app/bayesian/dispatch_authority.py")
    sentinel = (
        "set_config('app.current_tenant_id', "
        "'00000000-0000-0000-0000-000000000000', true)"
    )
    claim_wrapper = dispatch_authority.split("FROM public.b24_claim_fit_dispatch", 1)[0]
    assert sentinel.replace(" ", "").replace("\n", "") in claim_wrapper.replace(
        " ", ""
    ).replace("\n", "")
    evidence = _read(ROOT / "docs/forensics/B2.4-P12 Remediation Evidence Pack .md")
    assert "internal/local/CI topology substrate composition" in evidence
    assert "does not claim production-topology trust closure" in evidence


def test_b24_p12_validator_negative_controls() -> None:
    validator = _load_validator()
    validator.validate_all()
    validator.run_negative_controls()
