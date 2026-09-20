"""B2.6-P2 Corrective VII battery: committed root, P2-equivalence, temporal,
finiteness, observability, open-world discovery, interleaving.

Runs on a real PostgreSQL migrated to the VII head, acting through the
exact runtime principals. Every cell seeds via the migration-owner (setup)
and asserts database behavior as app_user/app_worker/app_relay.

Classes (directive §§7-14, Gates 4/8/11/14/17/19-22):
  R7-*  committed-state root serialization + custody (RC7 family subset)
  C7-*  P2/completion extensional equivalence (blank + policy + drift)
  T7-*  temporal conservation (post-conduction regression + gate race)
  OF7-* pending finiteness + disposition totality
  OI7-* observability independence (API vs relay/beat)
  OW7-* open-world authority discovery (unseen definer/role/grant)
  RC7-* barrier interleavings (production READ COMMITTED, both orderings)
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from datetime import datetime, timezone
from uuid import UUID

import pytest

DAY_START = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)
DAY_END = datetime(2026, 1, 16, 0, 0, tzinfo=timezone.utc)
DAY_NOON = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
NEXT_DAY_NOON = datetime(2026, 1, 16, 8, 0, tzinfo=timezone.utc)
TASK_NAME = "app.tasks.revenue_verification.execute_b23_batch_match_engine"
SCOPE_HEX = "cd" * 32


@pytest.fixture(autouse=True)
async def _fresh_engines_per_test():
    yield
    try:
        from app.db.session import b23_engine
        from app.db.session import engine as app_engine

        await b23_engine.dispose()
        await app_engine.dispose()
    except Exception:
        pass


def _admin_dsn() -> str:
    for key in ("MIGRATION_database_URL", "MIGRATION_DATABASE_URL"):
        dsn = os.environ.get(key, "").strip()
        if dsn:
            return dsn
    pytest.skip("VII battery needs MIGRATION_DATABASE_URL")


def _role_dsn(role: str) -> str:
    import psycopg2

    admin = _admin_dsn()
    candidate = admin.replace("migration_owner:migration_owner", f"{role}:{role}")
    if candidate == admin:
        pytest.skip(f"cannot derive {role} DSN")
    try:
        conn = psycopg2.connect(candidate)
        conn.close()
    except Exception:
        pytest.skip(f"role {role} not provisioned")
    return candidate


def _seed_ingress(tag: str, *, provider: str = "stripe", currency: str = "USD") -> dict:
    import psycopg2

    tenant_id = uuid.uuid4()
    ingress_id = uuid.uuid4()
    event_uuid = uuid.uuid4()
    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tenants (id, name, api_key_hash,"
                " notification_email) VALUES (%s, %s, %s, %s)",
                (str(tenant_id), f"b26p2vii-{tag}", uuid.uuid4().hex,
                 f"b26p2vii-{tag}@example.invalid"),
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )
            cur.execute(
                "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
                " display_name, state) VALUES ('b26p2vii_channel', 'b26p2vii',"
                " true, 'B26P2VII', 'active') ON CONFLICT (code) DO NOTHING"
            )
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, 38000,"
                " '{\"order_id\": \"vii\"}'::jsonb, %s, 'conversion',"
                " 'b26p2vii_channel', 'b26p2vii-campaign', 38000, 'USD',"
                " %s, %s, 'processed')",
                (str(event_uuid), str(tenant_id), DAY_NOON, str(uuid.uuid4()),
                 str(uuid.uuid4()), f"b26p2vii:{tag}", DAY_NOON, DAY_NOON),
            )
            cur.execute(
                "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
                " event_id, provider, provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_kind,"
                " normalized_commerce_reference_value, verified_amount_minor,"
                " verified_amount_currency, event_timestamp, idempotency_key,"
                " verified_commerce_ingress_state)"
                " VALUES (%s, %s, %s, %s, %s, %s, 'order_reference',"
                " %s, 38000, %s, %s, %s, 'authenticity_verified')",
                (str(ingress_id), str(tenant_id), str(event_uuid), provider,
                 f"evt-{tag}", f"ord-{tag}", f"ord-{tag}", currency,
                 DAY_NOON, f"b26p2vii:{tag}"),
            )
    finally:
        conn.close()
    return {"tenant_id": tenant_id, "ingress_id": ingress_id, "event_id": event_uuid}


def _seed_dispatch(tenant_id: UUID, ingress_id: UUID, task: str) -> None:
    import psycopg2

    conn = psycopg2.connect(_role_dsn("app_user"))
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
                " normalized_commerce_reference_value, window_start,"
                " window_end) VALUES (%s, %s, %s,"
                f" '{TASK_NAME}',"
                " 'b23_match_engine', 'b23_match_engine.task', %s,"
                " 'stripe', 'evt', 'ord', 'ord', %s, %s)",
                (
                    str(tenant_id),
                    str(ingress_id),
                    task,
                    str(uuid.uuid4()),
                    DAY_START,
                    DAY_END,
                ),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_execution_outbox (tenant_id,"
                " dispatch_task_id, webhook_ingress_identity_id)"
                " VALUES (%s, %s, %s)",
                (str(tenant_id), task, str(ingress_id)),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_task_authority_directory (task_id,"
                " tenant_id, webhook_ingress_identity_id, window_start,"
                " window_end) VALUES (%s, %s, %s, %s, %s)",
                (task, str(tenant_id), str(ingress_id), DAY_START, DAY_END),
            )
    finally:
        conn.close()


# --- R7: custody completeness -------------------------------------------

def test_r7_verified_state_immutable_once_referenced():
    """R7-01: verified flag cannot drift once a dispatch references ingress."""
    import psycopg2

    ids = _seed_ingress("r7verified")
    task = f"r7-verified-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task)
    conn = psycopg2.connect(_role_dsn("app_user"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            with pytest.raises(Exception, match="verified_state_immutable|authorship|immutable"):
                cur.execute(
                    "UPDATE public.webhook_ingress_identities"
                    " SET verified_commerce_ingress_state = 'received'"
                    " WHERE id = %s",
                    (str(ids["ingress_id"]),),
                )
    finally:
        conn.close()


def test_r7_currency_immutable_once_referenced():
    """R7-02: currency cannot drift once authoritative."""
    import psycopg2

    ids = _seed_ingress("r7currency")
    task = f"r7-curr-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task)
    conn = psycopg2.connect(_role_dsn("app_user"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            with pytest.raises(Exception, match="currency_immutable"):
                cur.execute(
                    "UPDATE public.webhook_ingress_identities"
                    " SET verified_amount_currency = 'EUR'"
                    " WHERE id = %s",
                    (str(ids["ingress_id"]),),
                )
    finally:
        conn.close()


def test_r7_worker_cannot_mint_verified_ingress():
    """R7-03: lower-authority worker cannot author verified state (B01 law)."""
    import psycopg2

    ids = _seed_ingress("r7authorship")
    conn = psycopg2.connect(_role_dsn("app_worker"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            event_uuid = uuid.uuid4()
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, 100,"
                " '{}'::jsonb, %s, 'conversion', 'b26p2vii_channel',"
                " 'c', 100, 'USD', %s, %s, 'processed')",
                (str(event_uuid), str(ids["tenant_id"]), DAY_NOON,
                 str(uuid.uuid4()), str(uuid.uuid4()), f"r7w:{uuid.uuid4().hex[:6]}",
                 DAY_NOON, DAY_NOON),
            )
            with pytest.raises(Exception, match="verified_authorship_refused"):
                cur.execute(
                    "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
                    " event_id, provider, provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " normalized_commerce_reference_kind,"
                    " normalized_commerce_reference_value, verified_amount_minor,"
                    " verified_amount_currency, event_timestamp, idempotency_key,"
                    " verified_commerce_ingress_state)"
                    " VALUES (%s, %s, %s, 'stripe', 'e', 'o', 'order_reference',"
                    " 'o', 100, 'USD', %s, %s, 'authenticity_verified')",
                    (str(uuid.uuid4()), str(ids["tenant_id"]), str(event_uuid),
                     DAY_NOON, f"r7w:{uuid.uuid4().hex[:6]}"),
                )
    finally:
        conn.close()


# --- RC7: barrier interleavings (production READ COMMITTED) --------------

def _barrier_race(*, reverse: bool = False, field: str = "clock") -> dict:
    """Dispatch INSERT vs ingress mutation, both orderings, RC.

    Returns final committed (event_clock, dispatch_window_start, provider).
    """
    import psycopg2

    ids = _seed_ingress(f"rc7-{field}-{uuid.uuid4().hex[:6]}")
    tenant = str(ids["tenant_id"])
    ingress = str(ids["ingress_id"])
    task = f"rc7-{uuid.uuid4().hex[:8]}"
    barrier = threading.Barrier(2)
    outcomes: dict = {}

    def _t1():
        c = psycopg2.connect(_role_dsn("app_user"))
        c.autocommit = False
        try:
            cur = c.cursor()
            cur.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
            cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
            cur.execute(
                "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                " webhook_ingress_identity_id, task_id, task_name, queue,"
                " routing_key, correlation_id, provider,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_value, window_start,"
                " window_end) VALUES (%s, %s, %s,"
                f" '{TASK_NAME}',"
                " 'b23_match_engine', 'b23_match_engine.task', %s,"
                " 'stripe', 'evt', 'ord', 'ord', %s, %s)",
                (tenant, ingress, task, str(uuid.uuid4()), DAY_START, DAY_END),
            )
            barrier.wait(timeout=15)
            time.sleep(0.6 if not reverse else 0.1)
            c.commit()
            outcomes["t1"] = "committed"
        except Exception as exc:  # noqa: BLE001
            try:
                c.rollback()
            except Exception:
                pass
            outcomes["t1"] = f"aborted:{exc}"
        finally:
            c.close()

    def _t2():
        c = psycopg2.connect(_role_dsn("app_user"))
        c.autocommit = False
        try:
            cur = c.cursor()
            cur.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
            cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
            barrier.wait(timeout=15)
            time.sleep(0.1 if not reverse else 0.6)
            if field == "clock":
                cur.execute(
                    "UPDATE public.webhook_ingress_identities"
                    " SET event_timestamp = %s WHERE id = %s",
                    (NEXT_DAY_NOON, ingress),
                )
            else:
                cur.execute(
                    "UPDATE public.webhook_ingress_identities"
                    " SET provider = 'paypal' WHERE id = %s",
                    (ingress,),
                )
            c.commit()
            outcomes["t2"] = "committed"
        except Exception as exc:  # noqa: BLE001
            try:
                c.rollback()
            except Exception:
                pass
            outcomes["t2"] = f"aborted:{exc}"
        finally:
            c.close()

    th1 = threading.Thread(target=_t1)
    th2 = threading.Thread(target=_t2)
    th1.start()
    th2.start()
    th1.join(timeout=30)
    th2.join(timeout=30)
    admin = psycopg2.connect(_admin_dsn())
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT event_timestamp, provider FROM public.webhook_ingress_identities"
                " WHERE id = %s",
                (ingress,),
            )
            row = cur.fetchone()
            clock, prov = (row[0], row[1]) if row else (None, None)
            cur.execute(
                "SELECT window_start, provider FROM public.b23_match_task_dispatches"
                " WHERE task_id = %s",
                (task,),
            )
            drow = cur.fetchone()
            ws, dprov = (drow[0], drow[1]) if drow else (None, None)
    finally:
        admin.close()
    return {"t1": outcomes.get("t1"), "t2": outcomes.get("t2"),
            "clock": clock, "ingress_provider": prov,
            "window_start": ws, "dispatch_provider": dprov}


def test_rc7_clock_write_skew_closed_both_orderings():
    """RC7-01/02: no committed E/D clock contradiction under RC."""
    for reverse in (False, True):
        res = _barrier_race(reverse=reverse, field="clock")
        if res["window_start"] is None or res["clock"] is None:
            continue  # one side aborted: serialization held
        # Both committed: window must be canonical of the committed clock.
        from datetime import timezone as _tz

        clock = res["clock"]
        if clock.tzinfo is None:
            clock = clock.replace(tzinfo=_tz.utc)
        exp_start = datetime(2026, 1, 16, 0, 0, tzinfo=timezone.utc) if clock.day == 16 else DAY_START
        assert res["window_start"] == exp_start, f"write-skew committed: {res}"


def test_rc7_provider_write_skew_closed():
    """RC7-03: no committed provider divergence."""
    res = _barrier_race(reverse=False, field="provider")
    if res["window_start"] is None:
        return
    assert res["ingress_provider"] == res["dispatch_provider"], f"provider skew: {res}"


# --- C7: P2-equivalence -----------------------------------------------

def _publish_and_verdict(
    tenant_id: UUID, ingress_id: UUID, task: str, event_id: UUID | None = None
) -> None:
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
                "UPDATE public.b23_match_task_dispatches SET delivery_state='published',"
                " first_published_at=now() WHERE task_id=%s",
                (task,),
            )
            cur.execute(
                "UPDATE public.b26_p2_execution_outbox SET state='published'"
                " WHERE dispatch_task_id=%s",
                (task,),
            )
            if event_id is None:
                cur.execute(
                    "SELECT event_id FROM public.webhook_ingress_identities WHERE id=%s",
                    (str(ingress_id),),
                )
                row = cur.fetchone()
                event_id = UUID(str(row[0])) if row else uuid.uuid4()
            cur.execute(
                "INSERT INTO public.b23_match_verdicts (tenant_id,"
                " attribution_event_id, webhook_ingress_identity_id,"
                " provider, canonical_commerce_reference,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference, status,"
                " match_quality, attributed_amount_minor,"
                " verified_amount_minor, currency_code,"
                " canonical_expected_gross_amount_minor,"
                " canonical_captured_gross_amount_minor,"
                " canonical_net_verified_amount_minor,"
                " discrepancy_amount_minor, discrepancy_ratio_bps,"
                " discrepancy_band)"
                " VALUES (%s, %s, %s, 'stripe', 'ord', 'evt', 'ord',"
                " 'matched_confirmed', 'high', 38000, 38000, 'USD',"
                " 38000, 38000, 38000, 0, 0, 'exact')",
                (str(tenant_id), str(event_id), str(ingress_id)),
            )
    finally:
        conn.close()


def test_c7_blank_provider_gate_refuses():
    """C7-01: blank-provider root cannot be issued nor conducted."""
    import psycopg2

    # Blank ingress is DB-accepted (predecessor envelope), but sovereign
    # dispatch issuance must refuse blank==blank (P2 INVALID == root REFUSE,
    # stronger than gate-only). This proves extensional equivalence at the
    # root: no blank root reaches B2.3/gate.
    ids = _seed_ingress("c7blank", provider="stripe")
    # Corrupt ingress to blank BEFORE dispatch (pre-authority, allowed by
    # custody since no dispatch references yet; shape law triggers at dispatch).
    admin = psycopg2.connect(_admin_dsn())
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "UPDATE public.webhook_ingress_identities SET provider='' WHERE id=%s",
                (str(ids["ingress_id"]),),
            )
    finally:
        admin.close()
    user = psycopg2.connect(_role_dsn("app_user"))
    user.autocommit = True
    try:
        with user.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            with pytest.raises(Exception, match="shape_refused|provider_shape"):
                cur.execute(
                    "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                    " webhook_ingress_identity_id, task_id, task_name, queue,"
                    " routing_key, correlation_id, provider,"
                    " provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " normalized_commerce_reference_value, window_start,"
                    " window_end) VALUES (%s, %s, %s,"
                    f" '{TASK_NAME}',"
                    " 'b23_match_engine', 'b23_match_engine.task', %s,"
                    " '', 'evt', 'ord', 'ord', %s, %s)",
                    (
                        str(ids["tenant_id"]),
                        str(ids["ingress_id"]),
                        f"c7-blank-{uuid.uuid4().hex[:8]}",
                        str(uuid.uuid4()),
                        DAY_START,
                        DAY_END,
                    ),
                )
    finally:
        user.close()


def test_c7_policy_table_bound():
    """C7-02: policy authority row pins v2 semantic identity."""
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT scope_policy_version, semantic_sha256 FROM"
                " public.b26_p2_scope_policy_authority"
                " ORDER BY scope_policy_version DESC LIMIT 1"
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "b2.6-p2-scope-policy-v2"
            assert row[1] == "fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99"
    finally:
        conn.close()


# --- T7: temporal conservation ----------------------------------------

def test_t7_conducted_verdict_regression_refused():
    """T7-01: qualifying->pending regression after conducted refuses."""
    import psycopg2

    ids = _seed_ingress("t7regress")
    task = f"t7-regress-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task)
    _publish_and_verdict(ids["tenant_id"], ids["ingress_id"], task)
    worker = psycopg2.connect(_role_dsn("app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "SELECT public.b26_p2_record_conduction_receipt(%s, %s, 1)",
                (task, SCOPE_HEX),
            )
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task,))
            assert cur.fetchone()[0] == "conducted"
            with pytest.raises(Exception, match="regression_refused|immutable"):
                cur.execute(
                    "UPDATE public.b23_match_verdicts SET status='pending'"
                    " WHERE tenant_id=%s AND webhook_ingress_identity_id=%s",
                    (str(ids["tenant_id"]), str(ids["ingress_id"])),
                )
    finally:
        worker.close()


# --- OF7: finiteness ---------------------------------------------------

def test_of7_expired_pending_actionable():
    """OF7-01: pending beyond horizon is actionable, fresh is not."""
    import psycopg2

    ids = _seed_ingress("of7pending")
    task = f"of7-pend-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task)
    import time as _time

    admin = psycopg2.connect(_admin_dsn())
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "SELECT public.b26_p2_operational_disposition(%s, 86400)",
                (task,),
            )
            assert cur.fetchone()[0] == "PENDING_PUBLICATION"
            # Age beyond the governed horizon without mutating immutable
            # dispatched_at: wait, then evaluate with a tight horizon.
            _time.sleep(2)
            cur.execute(
                "SELECT public.b26_p2_operational_disposition(%s, 1)",
                (task,),
            )
            assert cur.fetchone()[0] == "PENDING_PUBLICATION_ACTIONABLE"
    finally:
        admin.close()


# --- OI7/OW7 ------------------------------------------------------------

def test_oi7_health_endpoint_independent_fields():
    """OI7-01: health signal carries independent pending-actionable truth."""
    import pathlib

    src = pathlib.Path("backend/app/api/health.py").read_text()
    assert "pending_actionable_total" in src
    assert "evaluator_absent_total" in src


def test_ow7_open_world_definer_census():
    """OW7-01: open-world definer inventory sees all runtime definers."""
    import sys

    sys.path.insert(0, "scripts/ci")
    from b26_p2_capability_surface import (  # noqa: PLC0415
        KNOWN_P2_DEFINERS,
        _all_runtime_definers,
        _connect,
    )

    conn = _connect(_admin_dsn())
    try:
        cur = conn.cursor()
        definers = {d for d, _ in _all_runtime_definers(cur)}
        assert "b26_p2_mark_conducted" in definers
        assert "b26_p2_record_conduction_receipt" in definers
        for known in KNOWN_P2_DEFINERS:
            assert known in definers, f"P2 definer missing from census: {known}"
    finally:
        conn.close()
