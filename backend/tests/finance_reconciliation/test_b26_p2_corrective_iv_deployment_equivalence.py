"""B2.6-P2 Corrective IV deployment-plane equivalence DB/physics battery.

Governing class: DEPLOYMENT-PLANE NON-EQUIVALENCE -- the intended
architecture, the deployed architecture, and the CI-proven architecture
must be the same physical system for every load-bearing P2 execution
property. These cells prove the database-physics half against a real
PostgreSQL instance migrated to the Corrective-IV head; the
process/plane half is proven by prove_b26_p2_production_topology.py
against compiled containers.

Every cell seeds durable rows (setup, never authority) and asserts
database behavior -- constraint refusal, trigger refusal, grant shape,
or pure-function identity law. No cell imports broker machinery.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from uuid import UUID

import pytest

DAY_START = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)
DAY_END = datetime(2026, 1, 16, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
async def _fresh_engines_per_test():
    yield
    from app.db.session import b23_engine
    from app.db.session import engine as app_engine

    await b23_engine.dispose()
    await app_engine.dispose()


def _admin_dsn() -> str:
    dsn = os.environ.get("MIGRATION_DATABASE_URL", "").strip()
    if not dsn:
        pytest.skip("P2 Corrective-IV DB cells need MIGRATION_DATABASE_URL")
    return dsn


def _seed_ingress(tag: str) -> dict[str, UUID]:
    """Seed one tenant + one verified ingress; return ids (setup only)."""
    import psycopg2

    tenant_id = uuid.uuid4()
    ingress_id = uuid.uuid4()
    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tenants (id, name, api_key_hash,"
                " notification_email) VALUES (%s, %s, %s, %s)",
                (
                    str(tenant_id),
                    f"b26p2iv-{tag}",
                    uuid.uuid4().hex,
                    f"b26p2iv-{tag}@example.invalid",
                ),
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )
            event_uuid = uuid.uuid4()
            cur.execute(
                "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
                " display_name, state) VALUES ('b26p2ca1_channel', 'b26p2ca1',"
                " true, 'B26P2CA1', 'active') ON CONFLICT (code) DO NOTHING"
            )
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, 38000,"
                " '{\"order_id\": \"iv\"}'::jsonb, %s, 'conversion',"
                " 'b26p2ca1_channel', 'b26p2iv-campaign', 38000, 'USD',"
                " %s, %s, 'processed')",
                (
                    str(event_uuid),
                    str(tenant_id),
                    DAY_START + (DAY_END - DAY_START) / 2,
                    str(uuid.uuid4()),
                    str(uuid.uuid4()),
                    f"b26p2iv:{tag}",
                    DAY_START + (DAY_END - DAY_START) / 2,
                    DAY_START + (DAY_END - DAY_START) / 2,
                ),
            )
            cur.execute(
                "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
                " event_id, provider, provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_kind,"
                " normalized_commerce_reference_value, verified_amount_minor,"
                " verified_amount_currency, event_timestamp, idempotency_key,"
                " verified_commerce_ingress_state)"
                " VALUES (%s, %s, %s, 'stripe', %s, %s, 'order_reference',"
                " %s, 38000, 'USD', %s, %s, 'authenticity_verified')",
                (
                    str(ingress_id),
                    str(tenant_id),
                    str(event_uuid),
                    f"evt-{tag}",
                    f"ord-{tag}",
                    f"ord-{tag}",
                    DAY_START + (DAY_END - DAY_START) / 2,
                    f"b26p2iv:{tag}",
                ),
            )
    finally:
        conn.close()
    return {"tenant_id": tenant_id, "ingress_id": ingress_id}


def _seed_dispatch(tenant_id: UUID, ingress_id: UUID, task_id: str) -> None:
    """Seed one coherent dispatch + outbox + directory triple (setup only)."""
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )
            cur.execute(
                "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                " webhook_ingress_identity_id, task_id, task_name, queue,"
                " routing_key, correlation_id, provider,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_value, status,"
                " delivery_state, publish_attempts, window_start, window_end)"
                " VALUES (%s, %s, %s,"
                " 'app.tasks.revenue_verification.execute_b23_batch_match_engine',"
                " 'b23_match_engine', 'b23_match_engine.task', %s, 'stripe',"
                " 'evt', 'ord', 'ord', 'dispatched', 'pending_publish', 0,"
                " %s, %s)",
                (
                    str(tenant_id),
                    str(ingress_id),
                    task_id,
                    str(uuid.uuid4()),
                    DAY_START,
                    DAY_END,
                ),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_execution_outbox (tenant_id,"
                " dispatch_task_id, webhook_ingress_identity_id)"
                " VALUES (%s, %s, %s)",
                (str(tenant_id), task_id, str(ingress_id)),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_task_authority_directory (task_id,"
                " tenant_id, webhook_ingress_identity_id, window_start,"
                " window_end) VALUES (%s, %s, %s, %s, %s)",
                (task_id, str(tenant_id), str(ingress_id), DAY_START, DAY_END),
            )
    finally:
        conn.close()


def _refused(fn) -> str:
    import psycopg2

    try:
        fn()
    except psycopg2.Error as exc:
        return str(exc).split("\n")[0][:200]
    raise AssertionError("expected database refusal, statement succeeded")


def test_iv_outbox_fk_refuses_unknown_task() -> None:
    ids = _seed_ingress("orphan-outbox")
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )

            def attempt() -> None:
                cur.execute(
                    "INSERT INTO public.b26_p2_execution_outbox (tenant_id,"
                    " dispatch_task_id, webhook_ingress_identity_id)"
                    " VALUES (%s, 'task-that-was-never-dispatched', %s)",
                    (str(ids["tenant_id"]), str(ids["ingress_id"])),
                )

            reason = _refused(attempt)
            assert "fk_b26_p2_outbox_dispatch_task_identity" in reason
    finally:
        conn.close()


def test_iv_directory_fk_refuses_orphan() -> None:
    ids = _seed_ingress("orphan-dir")
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )

            def attempt() -> None:
                cur.execute(
                    "INSERT INTO public.b26_p2_task_authority_directory"
                    " (task_id, tenant_id, webhook_ingress_identity_id,"
                    " window_start, window_end)"
                    " VALUES ('orphan-authority', %s, %s, %s, %s)",
                    (str(ids["tenant_id"]), str(ids["ingress_id"]), DAY_START, DAY_END),
                )

            reason = _refused(attempt)
            assert "fk_b26_p2_directory_dispatch_task_identity" in reason
    finally:
        conn.close()


def test_iv_outbox_fk_refuses_cross_tenant_ingress() -> None:
    first = _seed_ingress("x-tenant-a")
    second = _seed_ingress("x-tenant-b")
    task_id = f"iv-x-tenant-{uuid.uuid4().hex[:8]}"
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(second["tenant_id"]),),
            )
            # A dispatch row for the second tenant WITHOUT outbox/directory
            # yet, so the task-identity FK below passes and only the
            # composite tenant/ingress binding is under test.
            cur.execute(
                "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                " webhook_ingress_identity_id, task_id, task_name, queue,"
                " routing_key, correlation_id, provider,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_value)"
                " VALUES (%s, %s, %s,"
                " 'app.tasks.revenue_verification.execute_b23_batch_match_engine',"
                " 'b23_match_engine', 'b23_match_engine.task', %s,"
                " 'stripe', 'evt', 'ord', 'ord')",
                (
                    str(second["tenant_id"]),
                    str(second["ingress_id"]),
                    task_id,
                    str(uuid.uuid4()),
                ),
            )

            def attempt() -> None:
                # Existing task identity, but the (tenant, ingress) pair
                # crosses tenants: the task-identity FK passes, the
                # composite tenant/ingress FK must refuse.
                cur.execute(
                    "INSERT INTO public.b26_p2_execution_outbox (tenant_id,"
                    " dispatch_task_id, webhook_ingress_identity_id)"
                    " VALUES (%s, %s, %s)",
                    (
                        str(second["tenant_id"]),
                        task_id,
                        str(first["ingress_id"]),
                    ),
                )

            reason = _refused(attempt)
            assert "fk_b26_p2_outbox_tenant_ingress_composite" in reason
    finally:
        conn.close()


def test_iv_split_brain_second_task_for_same_ingress_refused() -> None:
    ids = _seed_ingress("split")
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], f"iv-split-a-{uuid.uuid4().hex[:8]}")
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )

            def attempt() -> None:
                cur.execute(
                    "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                    " webhook_ingress_identity_id, task_id, task_name, queue,"
                    " routing_key, correlation_id, provider,"
                    " provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " normalized_commerce_reference_value)"
                    " VALUES (%s, %s, %s,"
                    " 'app.tasks.revenue_verification.execute_b23_batch_match_engine',"
                    " 'b23_match_engine', 'b23_match_engine.task', %s,"
                    " 'stripe', 'evt', 'ord', 'ord')",
                    (
                        str(ids["tenant_id"]),
                        str(ids["ingress_id"]),
                        f"iv-split-b-{uuid.uuid4().hex[:8]}",
                        str(uuid.uuid4()),
                    ),
                )

            _refused(attempt)
    finally:
        conn.close()


def test_iv_delivery_forward_only() -> None:
    ids = _seed_ingress("delivery")
    task_id = f"iv-delivery-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            # Lawful: pending_publish -> published -> conducted.
            cur.execute(
                "UPDATE public.b23_match_task_dispatches"
                " SET delivery_state = 'published' WHERE task_id = %s",
                (task_id,),
            )
            cur.execute(
                "UPDATE public.b26_p2_execution_outbox"
                " SET state = 'published' WHERE dispatch_task_id = %s",
                (task_id,),
            )
            cur.execute(
                "UPDATE public.b23_match_task_dispatches"
                " SET delivery_state = 'conducted' WHERE task_id = %s",
                (task_id,),
            )
            cur.execute(
                "UPDATE public.b26_p2_execution_outbox"
                " SET state = 'conducted' WHERE dispatch_task_id = %s",
                (task_id,),
            )

            def backward() -> None:
                cur.execute(
                    "UPDATE public.b23_match_task_dispatches"
                    " SET delivery_state = 'published' WHERE task_id = %s",
                    (task_id,),
                )

            reason = _refused(backward)
            assert "b26_p2_dispatch_delivery_illegal_transition" in reason

            def outbox_backward() -> None:
                cur.execute(
                    "UPDATE public.b26_p2_execution_outbox"
                    " SET state = 'published' WHERE dispatch_task_id = %s",
                    (task_id,),
                )

            reason = _refused(outbox_backward)
            assert "b26_p2_outbox_illegal_transition" in reason
    finally:
        conn.close()


def test_iv_delivery_skips_refused() -> None:
    ids = _seed_ingress("skip")
    task_id = f"iv-skip-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )

            def skip() -> None:
                cur.execute(
                    "UPDATE public.b23_match_task_dispatches"
                    " SET delivery_state = 'conducted' WHERE task_id = %s",
                    (task_id,),
                )

            reason = _refused(skip)
            assert "b26_p2_dispatch_delivery_illegal_transition" in reason
    finally:
        conn.close()


def test_iv_attempts_monotonic() -> None:
    ids = _seed_ingress("attempts")
    task_id = f"iv-attempts-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "UPDATE public.b23_match_task_dispatches"
                " SET publish_attempts = 5 WHERE task_id = %s",
                (task_id,),
            )

            def regress() -> None:
                cur.execute(
                    "UPDATE public.b23_match_task_dispatches"
                    " SET publish_attempts = 3 WHERE task_id = %s",
                    (task_id,),
                )

            reason = _refused(regress)
            assert "b26_p2_dispatch_attempts_regression" in reason
            cur.execute(
                "UPDATE public.b26_p2_execution_outbox"
                " SET publish_attempts = 5 WHERE dispatch_task_id = %s",
                (task_id,),
            )

            def outbox_regress() -> None:
                cur.execute(
                    "UPDATE public.b26_p2_execution_outbox"
                    " SET publish_attempts = 0 WHERE dispatch_task_id = %s",
                    (task_id,),
                )

            reason = _refused(outbox_regress)
            assert "b26_p2_outbox_attempts_regression" in reason
    finally:
        conn.close()


def test_iv_window_rewrite_refused() -> None:
    ids = _seed_ingress("window")
    task_id = f"iv-window-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )

            # Same-value rewrite is a no-op (IS DISTINCT FROM false) and
            # stays allowed; moving the window by one day must refuse.
            cur.execute(
                "UPDATE public.b23_match_task_dispatches"
                " SET window_start = %s, window_end = %s WHERE task_id = %s",
                (DAY_START, DAY_END, task_id),
            )

            def rewrite_only() -> None:
                cur.execute(
                    "UPDATE public.b23_match_task_dispatches"
                    " SET window_start = window_start + interval '1 day',"
                    " window_end = window_end + interval '1 day'"
                    " WHERE task_id = %s",
                    (task_id,),
                )

            reason = _refused(rewrite_only)
            assert "b26_p2_dispatch_window_immutable" in reason
    finally:
        conn.close()


def test_iv_worker_grant_shape() -> None:
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT has_table_privilege('app_worker', 'public.tenants', 'SELECT')")
            assert cur.fetchone()[0] is True
            cur.execute(
                "SELECT has_table_privilege('app_worker',"
                " 'public.b23_match_task_dispatches', 'INSERT')"
            )
            assert cur.fetchone()[0] is False
            cur.execute(
                "SELECT has_table_privilege('app_worker',"
                " 'public.b23_match_task_dispatches', 'UPDATE')"
            )
            # Column-scoped UPDATE: table-level UPDATE is denied, column
            # delivery-state UPDATE is allowed.
            assert cur.fetchone()[0] is False
            cur.execute(
                "SELECT has_column_privilege('app_worker',"
                " 'public.b23_match_task_dispatches', 'delivery_state', 'UPDATE')"
            )
            assert cur.fetchone()[0] is True
            cur.execute(
                "SELECT has_column_privilege('app_worker',"
                " 'public.b23_match_task_dispatches', 'task_id', 'UPDATE')"
            )
            assert cur.fetchone()[0] is False
            cur.execute(
                "SELECT has_column_privilege('app_worker',"
                " 'public.b26_p2_execution_outbox', 'state', 'UPDATE')"
            )
            assert cur.fetchone()[0] is True
            cur.execute(
                "SELECT has_function_privilege('app_worker',"
                " 'public.b26_p2_resolve_dispatch_authority(text)', 'EXECUTE')"
            )
            assert cur.fetchone()[0] is True
            cur.execute(
                "SELECT count(*) FROM information_schema.role_routine_grants"
                " WHERE routine_schema = 'public'"
                " AND routine_name = 'b26_p2_resolve_dispatch_authority'"
                " AND grantee = 'PUBLIC'"
            )
            assert cur.fetchone()[0] == 0
            cur.execute(
                "SELECT has_table_privilege('app_worker',"
                " 'public.b26_p2_task_authority_directory', 'UPDATE')"
            )
            assert cur.fetchone()[0] is False
    finally:
        conn.close()


def _scoped_candidate(ingress_id: UUID, tenant_id: UUID):
    from app.finance_reconciliation.candidate_conduction import ScopedCandidate
    from app.finance_reconciliation.scope_authority import CanonicalScopeClassification

    classification = CanonicalScopeClassification(
        tenant_id=tenant_id,
        provider="stripe",
        rail="stripe",
        currency_code="USD",
        window_start=DAY_START,
        window_end=DAY_END,
        scope_policy_version="b2.6-p2-scope-policy-v2",
        disposition="SUPPORTED_AND_IN_SCOPE",
        reason="supported_in_scope",
    )
    return ScopedCandidate(
        ingress_id=ingress_id,
        verified_amount_minor=38000,
        provider_raw="stripe",
        currency_raw="USD",
        provenance="test",
        classification=classification,
    )


def test_iv_identity_v3_ignores_source_bytes() -> None:
    import inspect

    from app.finance_reconciliation.candidate_conduction import _compute_scope_identity

    # Source bytes are not even a parameter of the digest function: no
    # caller can bind them into a scope identity by accident.
    assert "policy_source_sha256" not in inspect.signature(
        _compute_scope_identity
    ).parameters
    tenant_id = uuid.uuid4()
    scoped = (_scoped_candidate(uuid.uuid4(), tenant_id),)
    kwargs = dict(
        tenant=tenant_id,
        window_start=DAY_START,
        window_end=DAY_END,
        scope_policy_version="b2.6-p2-scope-policy-v2",
        scoped=scoped,
        policy_semantic_sha256="2f5739fd235c2dad35a6ae8922cd0fa9be4f3edb71b7765495270ff41f788782",
    )
    first = _compute_scope_identity(**kwargs)
    assert len(first) == 64
    # Semantic SHA change alters identity.
    altered = _compute_scope_identity(
        **{**kwargs, "policy_semantic_sha256": "0" * 64}
    )
    assert altered != first


def test_iv_identity_v3_version_matches_contract() -> None:
    from pathlib import Path

    import yaml

    from app.finance_reconciliation.candidate_conduction import SCOPE_IDENTITY_VERSION

    assert SCOPE_IDENTITY_VERSION == "b2.6-p2-scope-identity-v3"
    contract_path = (
        Path(__file__).resolve().parents[3]
        / "contracts/reconciliation/b2.6/scope-policy.v2.yaml"
    )
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    assert contract["identity_version"] == SCOPE_IDENTITY_VERSION
    assert "policy_source_sha" not in contract["identity_material"]
    assert "policy_semantic_sha" in contract["identity_material"]


def test_iv_beat_schedule_contains_relay_sweep() -> None:
    from app.core.queues import QUEUE_B26_P2_RELAY
    from app.tasks.beat_schedule import build_beat_schedule

    schedule = build_beat_schedule()
    assert "b26-p2-relay-sweep" in schedule
    entry = schedule["b26-p2-relay-sweep"]
    assert (
        entry["task"] == "app.tasks.b26_p2_relay.relay_b26_p2_pending_dispatches"
    )
    assert entry["options"]["queue"] == QUEUE_B26_P2_RELAY == "b26_p2_relay"


def test_iv_relay_role_boots_as_non_bayesian(monkeypatch) -> None:
    import app.tasks.bayesian as bayesian_module

    monkeypatch.setenv("SKELDIR_CELERY_WORKER_ROLE", "b26_p2_relay")
    monkeypatch.delenv("SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS", raising=False)
    assert bayesian_module._bayesian_tasks_registered_for_process() is False


def test_iv_pool_reset_calls_kombu_reset(monkeypatch) -> None:
    from app.celery_app import reset_broker_pools_after_fault

    calls = []
    monkeypatch.setattr("kombu.pools.reset", lambda *a, **k: calls.append(1))
    reset_broker_pools_after_fault(reason="unit-test")
    assert calls == [1]


def test_iv_pool_reset_never_raises(monkeypatch) -> None:
    from app.celery_app import reset_broker_pools_after_fault

    def _boom(*args, **kwargs):
        raise RuntimeError("pool explosion")

    monkeypatch.setattr("kombu.pools.reset", _boom)
    reset_broker_pools_after_fault(reason="unit-test")


def test_iv_pool_reset_heals_send_path(monkeypatch) -> None:
    """pools.reset() alone suicides the app-held pool (proven live: every
    later publish raises 'Acquire on closed pool'). The helper must ALSO
    drop the app-held reference so the next publish recreates fresh."""
    import os

    os.environ["CELERY_BROKER_URL"] = "memory://"
    os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"
    from app.celery_app import celery_app, reset_broker_pools_after_fault

    first = celery_app.send_task(
        "app.tasks.b26_p2_relay.relay_b26_p2_pending_dispatches",
        queue="b26_p2_relay",
    ).id
    assert first
    reset_broker_pools_after_fault(reason="unit-test")
    second = celery_app.send_task(
        "app.tasks.b26_p2_relay.relay_b26_p2_pending_dispatches",
        queue="b26_p2_relay",
    ).id
    assert second and second != first


def test_iv_require_dsn_guard_fails_closed() -> None:
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.db.session",
        ],
        cwd="backend",
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "SKELDIR_B23_REQUIRE_WORKER_DSN": "1",
            "B23_WORKER_DATABASE_URL": "",
        },
    )
    assert proc.returncode != 0
    assert "b23_worker_dsn_required" in proc.stderr


async def test_iv_conducted_mark_advances_published() -> None:
    from app.tasks.revenue_verification import _mark_dispatch_conducted

    ids = _seed_ingress("conducted")
    task_id = f"iv-conducted-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "UPDATE public.b23_match_task_dispatches"
                " SET delivery_state = 'published' WHERE task_id = %s",
                (task_id,),
            )
            cur.execute(
                "UPDATE public.b26_p2_execution_outbox"
                " SET state = 'published' WHERE dispatch_task_id = %s",
                (task_id,),
            )
    finally:
        conn.close()
    await _mark_dispatch_conducted(tenant_id=ids["tenant_id"], broker_task_id=task_id)
    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            # RLS FORCE hides rows without the tenant GUC (read visibility
            # is part of the physics under test).
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "SELECT delivery_state FROM public.b23_match_task_dispatches"
                " WHERE task_id = %s",
                (task_id,),
            )
            assert cur.fetchone()[0] == "conducted"
            cur.execute(
                "SELECT state FROM public.b26_p2_execution_outbox"
                " WHERE dispatch_task_id = %s",
                (task_id,),
            )
            assert cur.fetchone()[0] == "conducted"
    finally:
        conn.close()


def test_iv_duplicate_seed_reuses_winner_task() -> None:
    """Duplicate issuance for one ingress keeps a single coherent triple.

    Corrective IV H-IV-D05: on conflict the first task_id wins and the
    winner is re-read for the outbox/directory rows. The pre-IV pattern
    (ON CONFLICT DO NOTHING without winner reuse) minted parentless
    outbox/directory rows for the loser -- the exact debris the upgrade
    quarantine absorbs and the coherence foreign keys refuse.
    """
    ids = _seed_ingress("winner-reuse")
    first_task = f"iv-winner-a-{uuid.uuid4().hex[:8]}"
    loser_task = f"iv-winner-b-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], first_task)
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                " webhook_ingress_identity_id, task_id, task_name, queue,"
                " routing_key, correlation_id, provider,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_value, status,"
                " delivery_state, publish_attempts, window_start, window_end)"
                " VALUES (%s, %s, %s,"
                " 'app.tasks.revenue_verification.execute_b23_batch_match_engine',"
                " 'b23_match_engine', 'b23_match_engine.task', %s, 'stripe',"
                " 'evt', 'ord', 'ord', 'dispatched', 'pending_publish', 0,"
                " %s, %s)"
                " ON CONFLICT (tenant_id, webhook_ingress_identity_id)"
                " DO NOTHING",
                (
                    str(ids["tenant_id"]),
                    str(ids["ingress_id"]),
                    loser_task,
                    str(uuid.uuid4()),
                    DAY_START,
                    DAY_END,
                ),
            )
            cur.execute(
                "SELECT task_id FROM public.b23_match_task_dispatches"
                " WHERE tenant_id = %s AND webhook_ingress_identity_id = %s",
                (str(ids["tenant_id"]), str(ids["ingress_id"])),
            )
            winner = str(cur.fetchone()[0])
            assert winner == first_task
            cur.execute(
                "INSERT INTO public.b26_p2_execution_outbox (tenant_id,"
                " dispatch_task_id, webhook_ingress_identity_id)"
                " VALUES (%s, %s, %s)"
                " ON CONFLICT (dispatch_task_id) DO NOTHING",
                (str(ids["tenant_id"]), winner, str(ids["ingress_id"])),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_task_authority_directory (task_id,"
                " tenant_id, webhook_ingress_identity_id, window_start,"
                " window_end) VALUES (%s, %s, %s, %s, %s)"
                " ON CONFLICT (task_id) DO NOTHING",
                (
                    winner,
                    str(ids["tenant_id"]),
                    str(ids["ingress_id"]),
                    DAY_START,
                    DAY_END,
                ),
            )
            for table, column in (
                ("b23_match_task_dispatches", "task_id"),
                ("b26_p2_execution_outbox", "dispatch_task_id"),
                ("b26_p2_task_authority_directory", "task_id"),
            ):
                cur.execute(
                    f"SELECT {column} FROM public.{table}"
                    " WHERE webhook_ingress_identity_id = %s",
                    (str(ids["ingress_id"]),),
                )
                rows = cur.fetchall()
                assert [str(row[0]) for row in rows] == [first_task]
    finally:
        conn.close()


def test_iv_resolver_admits_lawful_task_on_bare_session() -> None:
    """Admission resolver admits a lawful task on a bare session.

    The resolver runs as app_worker with no tenant GUC and reads the
    RLS-free admission directory: a coherent triple resolves to its
    tenant, while an unknown task resolves to zero rows. (A dispatch
    JOIN inside the resolver was evaluated and rejected: row_security
    off does not bypass FORCE RLS for non-superuser owners, so Gate 6
    rests on the coherence foreign keys plus the upgrade quarantine.)
    """
    ids = _seed_ingress("resolver-join")
    task_id = f"iv-resolver-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SET ROLE app_worker")
            cur.execute("RESET app.current_tenant_id")
            cur.execute(
                "SELECT tenant_id FROM"
                " public.b26_p2_resolve_dispatch_authority(%s)",
                (task_id,),
            )
            row = cur.fetchone()
            assert row is not None, "lawful task refused by admission resolver"
            assert str(row[0]) == str(ids["tenant_id"])
            cur.execute(
                "SELECT count(*) FROM"
                " public.b26_p2_resolve_dispatch_authority(%s)",
                ("task-that-was-never-issued",),
            )
            assert cur.fetchone()[0] == 0
    finally:
        conn.close()
