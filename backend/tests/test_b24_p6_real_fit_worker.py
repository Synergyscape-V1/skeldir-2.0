from __future__ import annotations

import asyncio
import ast
import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text

from app.bayesian.feature_authority import (
    FeatureAuthorityStatus,
    SourceWindowFeatureAuthority,
    upsert_source_window_feature_authority,
)
from app.bayesian.fit_execution import execute_fit_intent_sync
from app.bayesian.model_spec import B24_P6_MODEL_TYPE, B24_P6_MODEL_VERSION
from app.bayesian.resource_bounds import B24_RESOURCE_POLICY_VERSION
from app.bayesian.source_snapshot import compute_source_snapshot_hash
from app.core.secrets import get_database_url
from app.db.dsn import to_sync_postgres_dsn
from app.db.session import AsyncSessionLocal, engine, get_session


ROOT = Path(__file__).resolve().parents[2]
FIT_EXECUTION = ROOT / "backend/app/bayesian/fit_execution.py"
SOURCE_SNAPSHOT = ROOT / "backend/app/bayesian/source_snapshot.py"
SAMPLER_CHILD = ROOT / "backend/app/bayesian/sampler_child.py"
VALIDATOR = ROOT / "scripts/ci/validate_b24_p6_real_fit_worker.py"
MIGRATION = (
    ROOT
    / "alembic/versions/007_skeldir_foundation/202606031200_b24_p6_fit_id_resolution_policy.py"
)
START = datetime(2026, 5, 1, tzinfo=timezone.utc)
END = START + timedelta(days=30)


def _require_real_fit_proof() -> bool:
    return os.getenv("SKELDIR_B24_P6_REQUIRE_REAL_FIT_PROOF", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def _assert_p6_tables_exist() -> None:
    try:
        async with engine.begin() as conn:
            rows = (
                (
                    await conn.execute(
                        text(
                            """
                        SELECT to_regclass(:fits) AS fits,
                               to_regclass(:authority) AS authority
                        """
                        ),
                        {
                            "fits": "public.bayesian_model_fits",
                            "authority": "public.b24_source_window_feature_authority",
                        },
                    )
                )
                .mappings()
                .one()
            )
    except Exception as exc:
        message = f"B2.4-P6 PostgreSQL real-fit proof unavailable: {exc}"
        if _require_real_fit_proof():
            pytest.fail(message)
        pytest.skip(message)
    missing = [name for name, value in rows.items() if value is None]
    if missing:
        message = f"B2.4-P6 PostgreSQL proof tables are missing: {missing}"
        if _require_real_fit_proof():
            pytest.fail(message)
        pytest.skip(message)


async def _insert_test_tenant(tenant_id: UUID) -> None:
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'tenants'
                """
            )
        )
        columns = set(result.scalars().all())
        insert_cols = ["id", "name"]
        params = {
            "id": str(tenant_id),
            "name": f"B2.4-P6 Test Tenant {str(tenant_id)[:8]}",
            "api_key_hash": f"p6_test_hash_{str(tenant_id)[:8]}",
            "notification_email": f"p6_{str(tenant_id)[:8]}@test.local",
        }
        if "api_key_hash" in columns:
            insert_cols.append("api_key_hash")
        if "notification_email" in columns:
            insert_cols.append("notification_email")
        values_clause = ", ".join(f":{column}" for column in insert_cols)
        await conn.execute(
            text(
                f"""
                INSERT INTO public.tenants ({', '.join(insert_cols)})
                VALUES ({values_clause})
                ON CONFLICT (id) DO NOTHING
                """
            ),
            params,
        )


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_b24_p6_real_fit_worker", VALIDATOR
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_b24_p6_hash_derived_observed_signal_is_erased() -> None:
    text = _read(FIT_EXECUTION)
    assert "_observed_signal_from_hash" not in text
    assert "int(source_snapshot_hash[:" not in text
    assert 'int(row["source_snapshot_hash"]' not in text
    assert "load_p6_observed_input_from_source_snapshot_sync" in text
    assert '"observed_signal_source": observed_input.metadata()' in text


def test_b24_p6_observed_signal_is_source_snapshot_replay_derived() -> None:
    text = _read(SOURCE_SNAPSHOT)
    for token in (
        "P6_SOURCE_OBSERVED_SIGNAL_VERSION",
        "run_eligibility_preflight_sync",
        "load_source_window_feature_authority_sync",
        "evaluate_source_snapshot_resource_bounds",
        "_SOURCE_QUERIES.items()",
        "_STREAM_EXECUTION_OPTIONS",
        "canonical_json_bytes(payload)",
        "verified_hash != source_snapshot_hash",
        "SOURCE_SNAPSHOT_MISMATCH",
        "_bounded_signal_from_source_rows",
    ):
        assert token in text


def test_b24_p6_fit_id_only_resolution_is_explicit_rls_capability() -> None:
    fit_execution = _read(FIT_EXECUTION)
    migration = _read(MIGRATION)
    assert "app.b24_fit_resolution_id" in fit_execution
    assert "app.b24_fit_resolution_id" in migration
    assert "tenant_id = NULLIF(current_setting('app.current_tenant_id'" in migration
    assert "WITH CHECK" in migration
    assert "app.b24_fit_resolution_id" not in migration.split("WITH CHECK", 1)[1]


def test_b24_p6_parent_keeps_pymc_child_only() -> None:
    tree = ast.parse(_read(FIT_EXECUTION))
    imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    from_imports = {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "pymc" not in imports
    assert "pymc" not in from_imports
    assert "app.bayesian.sampler_child" not in from_imports
    child = _read(SAMPLER_CHILD)
    assert "with pm.Model() as model:" in child
    assert "run_single_process_pymc_sample(" in child


def test_b24_p6_ci_validator_negative_controls() -> None:
    validator = _load_validator()
    validator.validate_all()
    validator.run_negative_controls()


async def _seed_source_rows(tenant_id: UUID, suffix: str) -> None:
    async with engine.begin() as conn:
        for index in range(20):
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
                    VALUES (:code, 'b24_p6_proof', true, :display_name, 'active')
                    ON CONFLICT (code) DO NOTHING
                    """
                ),
                {
                    "code": f"p6_{suffix}_{index:02d}",
                    "display_name": f"P6 {suffix} {index:02d}",
                },
            )

    async with get_session(tenant_id) as session:
        for index in range(20):
            event_id = uuid4()
            verdict_id = uuid4()
            revenue_cents = 10_000 + index
            occurred_at = START + timedelta(days=index)
            channel = f"p6_{suffix}_{index:02d}"
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
                        {"source": "b24_p6_real_fit_proof", "n": index},
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    "idempotency_key": f"p6:{suffix}:{index}",
                    "channel": channel,
                    "campaign_id": f"campaign_{suffix}_{index:02d}",
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
                    "commerce_ref": f"order_{suffix}_{index:02d}",
                    "event_ref": f"evt_{suffix}_{index:02d}",
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
                    "event_ref": f"capture_{suffix}_{index:02d}",
                    "commerce_ref": f"order_{suffix}_{index:02d}",
                    "occurred_at": occurred_at,
                    "amount_minor": revenue_cents,
                },
            )


async def _snapshot_hash(tenant_id: UUID):
    async with AsyncSessionLocal() as session:
        return await compute_source_snapshot_hash(
            session,
            tenant_id=tenant_id,
            model_type=B24_P6_MODEL_TYPE,
            model_version=B24_P6_MODEL_VERSION,
            source_window_start=START,
            source_window_end=END,
        )


async def _insert_authority_and_fit(
    tenant_id: UUID,
    *,
    fit_id: UUID,
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
                channel_count=20,
                currency_count=1,
                provider_count=1,
                campaign_or_feature_count=20,
                freshness_status=FeatureAuthorityStatus.FRESH,
                policy_version=B24_RESOURCE_POLICY_VERSION,
                computed_at=START,
            ),
        )
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
                    max_cores
                )
                VALUES (
                    :tenant_id,
                    :fit_id,
                    :model_type,
                    :model_version,
                    :source_window_start,
                    :source_window_end,
                    :source_snapshot_hash,
                    'queued',
                    'eligible',
                    'complete',
                    false,
                    60,
                    160,
                    1
                )
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "fit_id": str(fit_id),
                "model_type": B24_P6_MODEL_TYPE,
                "model_version": B24_P6_MODEL_VERSION,
                "source_window_start": START,
                "source_window_end": END,
                "source_snapshot_hash": source_snapshot_hash,
            },
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p6_real_fit_uses_frozen_source_snapshot_authority() -> None:
    if importlib.util.find_spec("pymc") is None:
        message = "PyMC is not installed for the B2.4-P6 real-fit proof"
        if _require_real_fit_proof():
            pytest.fail(message)
        pytest.skip(message)
    await _assert_p6_tables_exist()
    tenant_id = uuid4()
    await _insert_test_tenant(tenant_id)
    suffix = uuid4().hex[:8]
    fit_id = uuid4()
    await _seed_source_rows(tenant_id, suffix)
    snapshot = await _snapshot_hash(tenant_id)
    assert snapshot.preflight.is_eligible
    assert snapshot.source_snapshot_hash != ("a" * 64)
    await _insert_authority_and_fit(
        tenant_id,
        fit_id=fit_id,
        source_snapshot_hash=snapshot.source_snapshot_hash,
    )

    sync_engine = create_engine(
        to_sync_postgres_dsn(get_database_url()),
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    try:
        payload = await asyncio.to_thread(
            execute_fit_intent_sync,
            engine=sync_engine,
            fit_id=fit_id,
            task_id=f"p6-real-fit-{suffix}",
        )
    finally:
        sync_engine.dispose()

    assert payload["status"] == "sampled_unvalidated", payload
    assert payload["compute_started"] is True
    async with get_session(tenant_id) as session:
        row = (
            (
                await session.execute(
                    text(
                        """
                        SELECT status,
                               credible_interval_status,
                               n_samples_actual,
                               divergence_count,
                               artifact_hash IS NOT NULL AS has_artifact_hash
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
    assert row == {
        "status": "sampled_unvalidated",
        "credible_interval_status": "pending",
        "n_samples_actual": 64,
        "divergence_count": 0,
        "has_artifact_hash": True,
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_b24_p6_source_snapshot_mismatch_fails_before_sampler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _assert_p6_tables_exist()
    tenant_id = uuid4()
    await _insert_test_tenant(tenant_id)
    suffix = uuid4().hex[:8]
    fit_id = uuid4()
    await _seed_source_rows(tenant_id, suffix)
    snapshot = await _snapshot_hash(tenant_id)
    bad_hash = "b" * 64 if snapshot.source_snapshot_hash != "b" * 64 else "c" * 64
    await _insert_authority_and_fit(
        tenant_id,
        fit_id=fit_id,
        source_snapshot_hash=bad_hash,
    )

    def _unexpected_sampler(*_args, **_kwargs):
        raise AssertionError("P6 sampler launched before source authority matched")

    monkeypatch.setattr(
        "app.bayesian.fit_execution.run_supervised_sampler", _unexpected_sampler
    )
    sync_engine = create_engine(
        to_sync_postgres_dsn(get_database_url()),
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    try:
        payload = await asyncio.to_thread(
            execute_fit_intent_sync,
            engine=sync_engine,
            fit_id=fit_id,
            task_id=f"p6-mismatch-{suffix}",
        )
    finally:
        sync_engine.dispose()

    assert payload["status"] == "failed"
    assert payload["fallback_reason"] == "source_snapshot_mismatch"
    assert payload["compute_started"] is False
