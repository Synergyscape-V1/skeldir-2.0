"""B2.6-P2 Corrective VIII battery: authenticated-root adoption, policy
meaning, temporal identity, historical census, heartbeat integrity.

Runs on a real PostgreSQL migrated to the VIII head, acting through the
exact runtime principals. Every cell follows the falsification contract:
pristine GREEN, genuine defect RED for the predicted cause, exact restore
GREEN.

Classes (directive §§5-15, Gates 2/3/6/8/10/11/12/13/19/22/29/30):
  AR8-*  authenticated-root adoption matrix (DB law + promotion end-path)
  PM8-*  policy meaning binding (recorder/gate/immutability)
  TC8-*  temporal consequence identity (identity move, phantom, sovereignty)
  HC8-*  historical census (pristine zero, dirty VII->VIII closure)
  HB8-*  heartbeat integrity (forge refused, evaluation function honest)
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from uuid import UUID

import pytest

DAY_START = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)
DAY_END = datetime(2026, 1, 16, 0, 0, tzinfo=timezone.utc)
DAY_NOON = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
TASK_NAME = "app.tasks.revenue_verification.execute_b23_batch_match_engine"
SCOPE_HEX = "cd" * 32
# Corrective VIII policy-meaning binding: every conduction receipt
# carries the caller-observed policy semantic SHA.
_P2_POLICY_SEMANTIC_SHA_V2 = (
    "fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99"
)


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
    pytest.skip("VIII battery needs MIGRATION_DATABASE_URL")


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


def _superuser_dsn() -> str:
    """Superuser lane DSN for RLS-bypass historical checks.

    Inside the candidate-image proof the database host is `pg`, not
    localhost; the proof harness exports B26_P2_SUPERUSER_DSN for that
    topology (host runs fall back to the local superuser form).
    """
    explicit = os.environ.get("B26_P2_SUPERUSER_DSN", "").strip()
    if explicit:
        return explicit
    admin = _admin_dsn()
    db = admin.rsplit("/", 1)[-1]
    return "postgresql://postgres:postgres@localhost:5432/" + db


def _seed_ingress(
    tag: str,
    *,
    provider: str = "stripe",
    currency: str = "USD",
    amount: int = 38000,
    state: str = "authenticity_verified",
    event_time: datetime = DAY_NOON,
) -> dict:
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
                (str(tenant_id), f"b26p2viii-{tag}", uuid.uuid4().hex,
                 f"b26p2viii-{tag}@example.invalid"),
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )
            cur.execute(
                "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
                " display_name, state) VALUES ('b26p2viii_channel', 'b26p2viii',"
                " true, 'B26P2VIII', 'active') ON CONFLICT (code) DO NOTHING"
            )
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, 38000,"
                " '{\"order_id\": \"viii\"}'::jsonb, %s, 'conversion',"
                " 'b26p2viii_channel', 'b26p2viii-campaign', 38000, 'USD',"
                " %s, %s, 'processed')",
                (str(event_uuid), str(tenant_id), event_time, str(uuid.uuid4()),
                 str(uuid.uuid4()), f"b26p2viii:{tag}", event_time, event_time),
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
                " %s, %s, %s, %s, %s, %s)",
                (str(ingress_id), str(tenant_id), str(event_uuid), provider,
                 f"evt-{tag}", f"ord-{tag}", f"ord-{tag}", amount, currency,
                 event_time, f"b26p2viii:{tag}", state),
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


def _conduct(task: str) -> str:
    import psycopg2

    worker = psycopg2.connect(_role_dsn("app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute(
                "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                (task, SCOPE_HEX, 1, _P2_POLICY_SEMANTIC_SHA_V2),
            )
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task,))
            return str(cur.fetchone()[0])
    finally:
        worker.close()


# --- AR8: authenticated-root adoption -----------------------------------

def test_ar8_worker_verified_mint_refused():
    """AR8-01: lower-authority verified authorship is refused at the plane."""
    import psycopg2

    ids = _seed_ingress("ar8a1")
    conn = psycopg2.connect(_role_dsn("app_worker"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
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
                    " 'o', 1, 'USD', %s, %s, 'authenticity_verified')",
                    (str(uuid.uuid4()), str(ids["tenant_id"]), str(uuid.uuid4()),
                     DAY_NOON, f"ar8a1:{uuid.uuid4().hex[:6]}"),
                )
    finally:
        conn.close()


def test_ar8_precursor_promote_signal_and_promotion_wins():
    """AR8-02/08: pending precursor + genuine arrival -> explicit promote
    signal; promotion under app_user authority makes the authenticated
    sovereign values canonical (amount 999000, not the precursor's 1)."""
    import psycopg2

    ids = _seed_ingress("ar8a2", state="pending", amount=1)
    tenant = str(ids["tenant_id"])
    # Genuine arrival collides: explicit promote signal, never silent adopt.
    user = psycopg2.connect(_role_dsn("app_user"))
    user.autocommit = True
    try:
        with user.cursor() as cur:
            cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
            with pytest.raises(Exception, match="precursor_present_promote_required"):
                cur.execute(
                    "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
                    " event_id, provider, provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " normalized_commerce_reference_kind,"
                    " normalized_commerce_reference_value, verified_amount_minor,"
                    " verified_amount_currency, event_timestamp, idempotency_key,"
                    " verified_commerce_ingress_state)"
                    " VALUES (%s, %s, %s, 'stripe', 'evt-ar8a2', 'ord-ar8a2',"
                    " 'order_reference', 'ord-ar8a2', 999000, 'USD', %s,"
                    " 'b26p2viii:ar8a2', 'authenticity_verified')",
                    (str(uuid.uuid4()), tenant, str(uuid.uuid4()), DAY_NOON),
                )
            # Promote: authenticated values win under app_user authority.
            cur.execute(
                "UPDATE public.webhook_ingress_identities"
                " SET provider='stripe', provider_native_event_reference='evt-ar8a2',"
                " provider_native_commerce_reference='ord-ar8a2',"
                " normalized_commerce_reference_value='ord-ar8a2',"
                " verified_amount_minor=999000, verified_amount_currency='USD',"
                " event_timestamp=%s,"
                " verified_commerce_ingress_state='authenticity_verified'"
                " WHERE id=%s",
                (DAY_NOON, str(ids["ingress_id"])),
            )
            cur.execute(
                "SELECT verified_amount_minor FROM public.webhook_ingress_identities"
                " WHERE id=%s",
                (str(ids["ingress_id"]),),
            )
            assert cur.fetchone()[0] == 999000
    finally:
        user.close()


def test_ar8_verified_mismatch_fails_closed():
    """AR8-03/04/05/07: verified-vs-verified sovereign mismatch fails
    closed; the canonical amount is never silently replaced."""
    import psycopg2

    ids = _seed_ingress("ar8cf", amount=38000)
    tenant = str(ids["tenant_id"])
    user = psycopg2.connect(_role_dsn("app_user"))
    user.autocommit = True
    try:
        with user.cursor() as cur:
            cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
            with pytest.raises(Exception, match="authenticated_conflict"):
                cur.execute(
                    "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
                    " event_id, provider, provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " normalized_commerce_reference_kind,"
                    " normalized_commerce_reference_value, verified_amount_minor,"
                    " verified_amount_currency, event_timestamp, idempotency_key,"
                    " verified_commerce_ingress_state)"
                    " VALUES (%s, %s, %s, 'stripe', 'evt-ar8cf', 'ord-ar8cf',"
                    " 'order_reference', 'ord-ar8cf', 999000, 'USD', %s,"
                    " 'b26p2viii:ar8cf', 'authenticity_verified')",
                    (str(uuid.uuid4()), tenant, str(uuid.uuid4()), DAY_NOON),
                )
            cur.execute(
                "SELECT verified_amount_minor FROM public.webhook_ingress_identities"
                " WHERE id=%s",
                (str(ids["ingress_id"]),),
            )
            assert cur.fetchone()[0] == 38000
    finally:
        user.close()


# --- PM8: policy meaning binding ----------------------------------------

def test_pm8_recorder_requires_semantic_binding():
    """PM8-01: the recorder refuses unbound, wrongly bound, and stale
    policy meaning; the bound path conducts."""
    import psycopg2

    ids = _seed_ingress("pm8")
    task = f"pm8-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task)
    _publish_and_verdict(ids["tenant_id"], ids["ingress_id"], task)
    worker = psycopg2.connect(_role_dsn("app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            with pytest.raises(Exception, match="policy_semantic_binding_required"):
                cur.execute(
                    "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                    (task, SCOPE_HEX, 1, None),
                )
            with pytest.raises(Exception, match="policy_semantic_not_bound"):
                cur.execute(
                    "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                    (task, SCOPE_HEX, 1, "00" * 32),
                )
            cur.execute(
                "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                (task, SCOPE_HEX, 1, _P2_POLICY_SEMANTIC_SHA_V2),
            )
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task,))
            assert cur.fetchone()[0] == "conducted"
    finally:
        worker.close()


def test_pm8_same_version_tamper_breaks_conduction():
    """PM8-02: semantic mutation under the same version is refused by the
    immutability trigger (superuser bypass), so stale completion is
    impossible without a version bump."""
    import psycopg2

    sup0 = psycopg2.connect(_superuser_dsn())
    sup0.autocommit = True
    try:
        with sup0.cursor() as cur:
            with pytest.raises(Exception, match="policy_semantic_mutation_refused"):
                cur.execute(
                    "UPDATE public.b26_p2_scope_policy_authority"
                    " SET semantic_sha256='ff' || substr(semantic_sha256, 3)"
                    " WHERE scope_policy_version='b2.6-p2-scope-policy-v2'"
                )
    finally:
        sup0.close()
    # Superuser bypass proves the gate binds meaning, not the label.
    sup = psycopg2.connect(_superuser_dsn())
    sup.autocommit = True
    try:
        with sup.cursor() as cur:
            cur.execute("SET session_replication_role = replica")
            cur.execute(
                "UPDATE public.b26_p2_scope_policy_authority"
                " SET semantic_sha256=%s"
                " WHERE scope_policy_version='b2.6-p2-scope-policy-v2'",
                ("00" * 32,),
            )
            cur.execute("SET session_replication_role = DEFAULT")
            ids = _seed_ingress("pm8b")
            task = f"pm8b-{uuid.uuid4().hex[:8]}"
            _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task)
            _publish_and_verdict(ids["tenant_id"], ids["ingress_id"], task)
            worker = psycopg2.connect(_role_dsn("app_worker"))
            worker.autocommit = True
            try:
                with worker.cursor() as wcur:
                    with pytest.raises(Exception, match="policy_not_bound"):
                        wcur.execute(
                            "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                            (task, SCOPE_HEX, 1, _P2_POLICY_SEMANTIC_SHA_V2),
                        )
            finally:
                worker.close()
    finally:
        with sup.cursor() as cur:
            cur.execute("SET session_replication_role = replica")
            cur.execute(
                "UPDATE public.b26_p2_scope_policy_authority"
                " SET semantic_sha256=%s"
                " WHERE scope_policy_version='b2.6-p2-scope-policy-v2'",
                (_P2_POLICY_SEMANTIC_SHA_V2,),
            )
            cur.execute("SET session_replication_role = DEFAULT")
        sup.close()


# --- TC8: temporal consequence identity ----------------------------------

def test_tc8_identity_move_refused_without_status_change():
    """TC8-01/02: moving the sole qualifying verdict to another ingress
    (status untouched) is refused; conducted keeps its consequence."""
    import psycopg2

    ids = _seed_ingress("tc8id")
    other = _seed_ingress("tc8other")
    task = f"tc8id-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task)
    _publish_and_verdict(ids["tenant_id"], ids["ingress_id"], task)
    assert _conduct(task) == "conducted"
    worker = psycopg2.connect(_role_dsn("app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            # Same-tenant fixture required: move within the conducted tenant
            # to another ingress of the same tenant is refused.
            with pytest.raises(Exception, match="identity_refused|regression_refused"):
                cur.execute(
                    "UPDATE public.b23_match_verdicts"
                    " SET webhook_ingress_identity_id=%s"
                    " WHERE tenant_id=%s AND webhook_ingress_identity_id=%s",
                    (str(other["ingress_id"]), str(ids["tenant_id"]),
                     str(ids["ingress_id"])),
                )
    finally:
        worker.close()


def test_tc8_phantom_insert_refused_under_conducted():
    """TC8-04: a qualifying INSERT against a conducted parent fails
    closed; the set cannot grow silently beneath the terminal."""
    import psycopg2

    ids = _seed_ingress("tc8ph")
    task = f"tc8ph-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task)
    _publish_and_verdict(ids["tenant_id"], ids["ingress_id"], task)
    assert _conduct(task) == "conducted"
    worker = psycopg2.connect(_role_dsn("app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            with pytest.raises(Exception, match="set_insert_refused"):
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
                    " VALUES (%s, %s, %s, 'stripe', 'ord2', 'evt2', 'ord2',"
                    " 'matched_confirmed', 'high', 100, 100, 'USD',"
                    " 100, 100, 100, 0, 0, 'exact')",
                    (str(ids["tenant_id"]), str(uuid.uuid4()), str(ids["ingress_id"])),
                )
    finally:
        worker.close()


def test_tc8_new_link_into_conducted_refused():
    """TC8-02b: moving a qualifying verdict INTO a conducted execution
    from elsewhere (new-link arm) is refused with identity refusal."""
    import psycopg2

    ids = _seed_ingress("tc8nl")
    task = f"tc8nl-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task)
    _publish_and_verdict(ids["tenant_id"], ids["ingress_id"], task)
    assert _conduct(task) == "conducted"
    tenant = str(ids["tenant_id"])
    admin = psycopg2.connect(_admin_dsn())
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
            second_ingress = str(uuid.uuid4())
            second_event = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, 100,"
                " '{}'::jsonb, %s, 'conversion',"
                " 'b26p2viii_channel', 'c', 100, 'USD',"
                " %s, %s, 'processed')",
                (second_event, tenant, DAY_NOON, str(uuid.uuid4()),
                 str(uuid.uuid4()), f"tc8nl:{uuid.uuid4().hex[:6]}",
                 DAY_NOON, DAY_NOON),
            )
            cur.execute(
                "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
                " event_id, provider, provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_kind,"
                " normalized_commerce_reference_value, verified_amount_minor,"
                " verified_amount_currency, event_timestamp, idempotency_key,"
                " verified_commerce_ingress_state)"
                " VALUES (%s, %s, %s, 'stripe', 'e2', 'o2', 'order_reference',"
                " 'o2', 100, 'USD', %s, %s, 'authenticity_verified')",
                (second_ingress, tenant, second_event, DAY_NOON,
                 f"tc8nl:{uuid.uuid4().hex[:6]}"),
            )
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
                " VALUES (%s, %s, %s, 'stripe', 'o2', 'e2', 'o2',"
                " 'matched_confirmed', 'high', 100, 100, 'USD',"
                " 100, 100, 100, 0, 0, 'exact')",
                (tenant, second_event, second_ingress),
            )
    finally:
        admin.close()
    worker = psycopg2.connect(_role_dsn("app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
            with pytest.raises(Exception, match="conducted_verdict_identity_refused"):
                cur.execute(
                    "UPDATE public.b23_match_verdicts"
                    " SET webhook_ingress_identity_id=%s"
                    " WHERE tenant_id=%s AND webhook_ingress_identity_id=%s"
                    " AND canonical_commerce_reference='o2'",
                    (str(ids["ingress_id"]), tenant, second_ingress),
                )
    finally:
        worker.close()


def test_tc8_non_footprint_correction_preserved():
    import psycopg2

    ids = _seed_ingress("tc8sv")
    task = f"tc8sv-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task)
    _publish_and_verdict(ids["tenant_id"], ids["ingress_id"], task)
    assert _conduct(task) == "conducted"
    worker = psycopg2.connect(_role_dsn("app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "UPDATE public.b23_match_verdicts SET match_quality='low'"
                " WHERE tenant_id=%s AND webhook_ingress_identity_id=%s",
                (str(ids["tenant_id"]), str(ids["ingress_id"])),
            )
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task,))
            assert cur.fetchone()[0] == "already_conducted"
    finally:
        worker.close()


# --- HC8: historical census ----------------------------------------------

def test_hc8_pristine_census_zero():
    """HC8-01: the VIII census finds zero contradictions on a lane the
    VIII migration (which fails closed on any residual) produced."""
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM public.b23_match_task_dispatches AS d"
                " JOIN public.webhook_ingress_identities AS i"
                " ON i.id = d.webhook_ingress_identity_id"
                " AND i.tenant_id = d.tenant_id"
                " WHERE d.window_start IS DISTINCT FROM"
                " public.b26_p2_canonical_day_start(i.event_timestamp)"
                " OR d.window_end IS DISTINCT FROM"
                " public.b26_p2_canonical_day_end(i.event_timestamp)"
                " OR btrim(COALESCE(i.provider, '')) = ''"
                " OR btrim(COALESCE(d.provider, '')) = ''"
                " OR i.verified_commerce_ingress_state IS DISTINCT FROM"
                " 'authenticity_verified'"
            )
            assert cur.fetchone()[0] == 0
            cur.execute(
                "SELECT count(*) FROM public.b23_match_task_dispatches AS d"
                " WHERE d.delivery_state = 'conducted' AND NOT EXISTS ("
                " SELECT 1 FROM public.b23_match_verdicts AS v"
                " WHERE v.tenant_id = d.tenant_id"
                " AND v.webhook_ingress_identity_id = d.webhook_ingress_identity_id"
                " AND v.status IN ('matched_provisional', 'matched_confirmed',"
                " 'adjusted'))"
            )
            assert cur.fetchone()[0] == 0
    finally:
        conn.close()


# --- OB8: shipping observability consumer -------------------------------

def test_ob8_probe_decision_law():
    """OB8-01..10: the deployed probe consumes the shipping observer path.
    Forged-healthy timestamps without genuine evaluation content still
    read degraded; only a fully healthy payload reads healthy."""
    import importlib.util as _ilu
    from pathlib import Path as _probe_path

    _probe_file = (
        _probe_path(__file__).resolve().parents[3]
        / "scripts"
        / "ops"
        / "conduction_health_probe.py"
    )
    _spec = _ilu.spec_from_file_location("conduction_health_probe", str(_probe_file))
    assert _spec is not None and _spec.loader is not None
    _probe_module = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_probe_module)
    evaluate = _probe_module.evaluate

    healthy, _ = evaluate(
        {
            "status": "ok",
            "action_required": False,
            "evaluator_absent_total": 0,
            "pending_actionable_total": 0,
            "stale_unconducted_count": 0,
            "quarantine_count": 0,
        }
    )
    assert healthy is True
    # Fresh tick but outstanding work: still degraded (heartbeat content,
    # not freshness, is the signal).
    for payload in (
        {"status": "ok", "action_required": True,
         "evaluator_absent_total": 0, "pending_actionable_total": 1,
         "stale_unconducted_count": 0, "quarantine_count": 0},
        {"status": "ok", "action_required": True,
         "evaluator_absent_total": 2, "pending_actionable_total": 0,
         "stale_unconducted_count": 0, "quarantine_count": 0},
        {"status": "ok", "action_required": True,
         "evaluator_absent_total": 0, "pending_actionable_total": 0,
         "stale_unconducted_count": 3, "quarantine_count": 0},
        {"status": "ok", "action_required": True,
         "evaluator_absent_total": 0, "pending_actionable_total": 0,
         "stale_unconducted_count": 0, "quarantine_count": 1},
        {"status": "unavailable"},
        {"status": "weird"},
        "not-a-dict",
    ):
        degraded, _reason = evaluate(payload)
        assert degraded is False, payload


def test_ob8_shipping_consumer_wired():
    """OB8-05: the deployment references actual consumers with operational
    effect (deployed probe executable from the production image; alert
    rules consume the exported signal; the beat-scheduled evaluator and
    relay WARNING consume degradation on cadence). A JSON field no
    production actor reads is a diagnostic, not operational closure.

    Boundary note: compose.local.yml is M1 local-dev authority, not
    a P2 surface — P2 does not override another phase's fenced file to
    claim wiring. The shipping consumers above are all P2-owned or
    platform contracts.
    """
    from pathlib import Path as _Path

    repo = _Path(__file__).resolve().parents[3]
    probe = (repo / "scripts/ops/conduction_health_probe.py").read_text(
        encoding="utf-8"
    )
    assert "def evaluate" in probe
    assert "/health/b26-p2-conduction" in probe
    alerts = (repo / "monitoring/alerts/b26-p2-conduction.alerts.yaml").read_text(
        encoding="utf-8"
    )
    assert "B26_P2_Conduction_ActionRequired" in alerts
    assert "B26_P2_Evaluator_Absent" in alerts
    metrics = (
        repo / "monitoring/prometheus/b26-p2-conduction-metrics.yml"
    ).read_text(encoding="utf-8")
    assert "b26_p2_conduction_action_required" in metrics
    assert "conduction_health_probe" in metrics


# --- HB8: heartbeat integrity --------------------------------------------

def test_hb8_relay_cannot_forge_heartbeat():
    """HB8-01/07: the monitored relay credential cannot write heartbeat
    evidence directly; only the evaluation function (which recomputes the
    counts) can advance it."""
    import psycopg2

    ids = _seed_ingress("hb8")
    tenant = str(ids["tenant_id"])
    relay = psycopg2.connect(_role_dsn("app_relay"))
    relay.autocommit = True
    try:
        with relay.cursor() as cur:
            cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
            with pytest.raises(Exception, match="denied|refused|permission"):
                cur.execute(
                    "INSERT INTO public.b26_p2_evaluator_heartbeat"
                    " (tenant_id, last_tick, tick_count, updated_at)"
                    " VALUES (%s, now(), 42, now())",
                    (tenant,),
                )
            cur.execute(
                "SELECT public.b26_p2_record_evaluator_heartbeat(300)"
            )
            assert cur.fetchone()[0] == "evaluated"
            cur.execute(
                "SELECT tick_count FROM public.b26_p2_evaluator_heartbeat"
                " WHERE tenant_id=%s",
                (tenant,),
            )
            assert cur.fetchone()[0] >= 1
    finally:
        relay.close()
    worker = psycopg2.connect(_role_dsn("app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
            # No EXECUTE grant (least privilege) and, defense in depth, an
            # explicit caller refusal inside the function either way.
            with pytest.raises(Exception, match="heartbeat_caller_refused|permission denied"):
                cur.execute("SELECT public.b26_p2_record_evaluator_heartbeat(300)")
    finally:
        worker.close()


def test_hc8_dirty_vii_contradictions_quarantined_on_upgrade():
    """HC8-02/03: VII-legal contradictions (write-skew root, false
    conducted) do not silently survive the VII->VIII upgrade: the generic
    census quarantines them children-first with corrective_viii provenance
    while B2.3 verdict history is preserved."""
    import subprocess
    import sys

    import psycopg2

    from pathlib import Path as _Path

    repo_root = _Path(__file__).resolve().parents[3]
    env = dict(os.environ)
    env["MIGRATION_DATABASE_URL"] = _admin_dsn()
    env["DATABASE_URL"] = _admin_dsn()

    def alembic(*args: str) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert proc.returncode == 0, f"alembic {' '.join(args)} failed: {proc.stderr[-2000:]}"

    alembic("downgrade", "202609210001")
    try:
        skew_ids = _seed_ingress("hc8skew")
        skew_task = f"hc8skew-{uuid.uuid4().hex[:8]}"
        admin = psycopg2.connect(_admin_dsn())
        admin.autocommit = True
        try:
            with admin.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (str(skew_ids["tenant_id"]),),
                )
                # Bypass the sovereign window check (owner DDL, test-only)
                # to plant a VII-legal write-skew root: live clock Jan16,
                # dispatch canonical of the dead Jan15 clock.
                cur.execute(
                    "ALTER TABLE public.b23_match_task_dispatches"
                    " DISABLE TRIGGER trg_b26_p2_dispatch_sovereign_window"
                )
                cur.execute(
                    "UPDATE public.webhook_ingress_identities"
                    " SET event_timestamp=%s WHERE id=%s",
                    (datetime(2026, 1, 16, 8, 0, tzinfo=timezone.utc),
                     str(skew_ids["ingress_id"])),
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
                    (str(skew_ids["tenant_id"]), str(skew_ids["ingress_id"]),
                     skew_task, str(uuid.uuid4()), DAY_START, DAY_END),
                )
                cur.execute(
                    "ALTER TABLE public.b23_match_task_dispatches"
                    " ENABLE TRIGGER trg_b26_p2_dispatch_sovereign_window"
                )
        finally:
            admin.close()
        # False conducted: lawful conduction, then VII-legal regression
        # via trigger bypass.
        false_ids = _seed_ingress("hc8false")
        false_task = f"hc8false-{uuid.uuid4().hex[:8]}"
        _seed_dispatch(false_ids["tenant_id"], false_ids["ingress_id"], false_task)
        _publish_and_verdict(
            false_ids["tenant_id"], false_ids["ingress_id"], false_task
        )
        # Conduct under VII (3-argument recorder) before upgrading.
        worker = psycopg2.connect(_role_dsn("app_worker"))
        worker.autocommit = True
        try:
            with worker.cursor() as cur:
                cur.execute(
                    "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s)",
                    (false_task, SCOPE_HEX, 1),
                )
                cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (false_task,))
                assert cur.fetchone()[0] == "conducted"
        finally:
            worker.close()
        admin2 = psycopg2.connect(_admin_dsn())
        admin2.autocommit = True
        try:
            with admin2.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (str(false_ids["tenant_id"]),),
                )
                cur.execute(
                    "ALTER TABLE public.b23_match_verdicts"
                    " DISABLE TRIGGER trg_b26_p2_verdict_temporal_conservation"
                )
                cur.execute(
                    "UPDATE public.b23_match_verdicts SET status='unmatched'"
                    " WHERE tenant_id=%s AND webhook_ingress_identity_id=%s",
                    (str(false_ids["tenant_id"]), str(false_ids["ingress_id"])),
                )
                cur.execute(
                    "ALTER TABLE public.b23_match_verdicts"
                    " ENABLE TRIGGER trg_b26_p2_verdict_temporal_conservation"
                )
        finally:
            admin2.close()
        alembic("upgrade", "head")
        # Quarantine/history assertions bypass RLS as the auditor does:
        # the migration owner's lane connection carries no tenant GUC.
        check = psycopg2.connect(_superuser_dsn())
        check.autocommit = True
        try:
            with check.cursor() as cur:
                cur.execute(
                    "SELECT reason FROM public.b26_p2_execution_quarantine"
                    " WHERE task_id=%s",
                    (skew_task,),
                )
                reasons = [r[0] for r in cur.fetchall()]
                assert any(
                    r.startswith("corrective_viii:window_mismatch") for r in reasons
                ), reasons
                cur.execute(
                    "SELECT reason FROM public.b26_p2_execution_quarantine"
                    " WHERE task_id=%s",
                    (false_task,),
                )
                reasons = [r[0] for r in cur.fetchall()]
                assert any(
                    "false_conducted_no_consequence" in r for r in reasons
                ), reasons
                # B2.3 verdict history preserved, never rewritten.
                cur.execute(
                    "SELECT count(*) FROM public.b23_match_verdicts"
                    " WHERE tenant_id=%s",
                    (str(false_ids["tenant_id"]),),
                )
                assert cur.fetchone()[0] >= 1
                # No residual contradiction.
                cur.execute(
                    "SELECT count(*) FROM public.b23_match_task_dispatches AS d"
                    " WHERE d.task_id IN (%s, %s)",
                    (skew_task, false_task),
                )
                assert cur.fetchone()[0] == 0
        finally:
            check.close()
    finally:
        alembic("upgrade", "head")
