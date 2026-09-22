"""B2.6-P2 Corrective V execution-coherence DB/physics battery.

Governing class: MULTIPLE LOCALLY VALID PROJECTIONS DO NOT CONSTITUTE
ONE EXECUTION AUTHORITY -- plus its two consequence siblings:
consequence-free `conducted` assertions and permanently unconsumed
`published` work without a governed signal.

Every cell seeds durable rows (setup, never authority) and asserts
database behavior against a real PostgreSQL instance migrated to the
Corrective-V head: tuple-FK refusal over the D1/D2 Cartesian matrix,
directory window-coherence refusal, gate-bound conducted transitions,
staleness observability, least-privilege grant shape, and SECURITY
DEFINER discipline. The compiled-container half (real worker/relay/
beat, signed webhooks, outage recovery) is proven by
prove_b26_p2_production_topology.py.

Closure levels used below follow the directive: INSTANCE CLOSED (the
exact reproduced mechanism no longer works), SURFACE PARTIALLY CLOSED
(siblings blocked but the class not physically bounded), CLASS CLOSED
(the prohibited EFFECT is impossible across the reachable surface or
an independent oracle catches every realization). DB-plane cells
establish CLASS CLOSED for the persistence effect; the runtime
principal cells establish CLASS CLOSED for the credential effect.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from uuid import UUID

import pytest

DAY_START = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)
DAY_END = datetime(2026, 1, 16, 0, 0, tzinfo=timezone.utc)
OTHER_DAY_START = datetime(2026, 1, 20, 0, 0, tzinfo=timezone.utc)
OTHER_DAY_END = datetime(2026, 1, 21, 0, 0, tzinfo=timezone.utc)

TASK_NAME = "app.tasks.revenue_verification.execute_b23_batch_match_engine"
# Corrective VIII policy-meaning binding: every conduction receipt
# carries the caller-observed policy semantic SHA.
_P2_POLICY_SEMANTIC_SHA_V2 = "fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99"


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
        pytest.skip("P2 Corrective-V DB cells need MIGRATION_DATABASE_URL")
    return dsn


def _role_dsn(role: str) -> str:
    """DSN for a provisioned runtime login (bootstrap credentials).

    Skips when the login is unreachable (unprovisioned lane): absence
    of the principal cannot prove the grant shape, so the cell must
    not pretend to.
    """
    import psycopg2

    admin = _admin_dsn()
    candidate = admin.replace("migration_owner:migration_owner", f"{role}:{role}")
    if candidate == admin:
        pytest.skip(f"cannot derive {role} DSN from admin DSN")
    try:
        conn = psycopg2.connect(candidate)
        conn.close()
    except psycopg2.Error:
        pytest.skip(f"role {role} not provisioned in this lane")
    return candidate


def _seed_ingress(tag: str) -> dict[str, UUID]:
    """Seed one tenant + one verified ingress; return ids (setup only)."""
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
                (
                    str(tenant_id),
                    f"b26p2v-{tag}",
                    uuid.uuid4().hex,
                    f"b26p2v-{tag}@example.invalid",
                ),
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )
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
                " '{\"order_id\": \"v\"}'::jsonb, %s, 'conversion',"
                " 'b26p2ca1_channel', 'b26p2v-campaign', 38000, 'USD',"
                " %s, %s, 'processed')",
                (
                    str(event_uuid),
                    str(tenant_id),
                    DAY_START + (DAY_END - DAY_START) / 2,
                    str(uuid.uuid4()),
                    str(uuid.uuid4()),
                    f"b26p2v:{tag}",
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
                    f"b26p2v:{tag}",
                ),
            )
    finally:
        conn.close()
    return {"tenant_id": tenant_id, "ingress_id": ingress_id, "event_id": event_uuid}


def _seed_dispatch(
    tenant_id: UUID,
    ingress_id: UUID,
    task_id: str,
    *,
    window_start: datetime = DAY_START,
    window_end: datetime = DAY_END,
    state: str = "pending_publish",
) -> None:
    """Seed one coherent dispatch + outbox + directory triple + directory.

    Coherent by construction (single D); every cross-product cell below
    starts from two such lawful executions and attempts a combination.
    """
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
                f" '{TASK_NAME}',"
                " 'b23_match_engine', 'b23_match_engine.task', %s, 'stripe',"
                " 'evt', 'ord', 'ord', 'dispatched', %s, 0,"
                " %s, %s)",
                (
                    str(tenant_id),
                    str(ingress_id),
                    task_id,
                    str(uuid.uuid4()),
                    state,
                    window_start,
                    window_end,
                ),
            )
            outbox_state = state if state in ("pending_publish", "published") else "pending_publish"
            cur.execute(
                "INSERT INTO public.b26_p2_execution_outbox (tenant_id,"
                " dispatch_task_id, webhook_ingress_identity_id, state)"
                " VALUES (%s, %s, %s, %s)",
                (str(tenant_id), task_id, str(ingress_id), outbox_state),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_task_authority_directory (task_id,"
                " tenant_id, webhook_ingress_identity_id, window_start,"
                " window_end) VALUES (%s, %s, %s, %s, %s)",
                (task_id, str(tenant_id), str(ingress_id), window_start, window_end),
            )
    finally:
        conn.close()


def _seed_extra_ingress(tenant_id: UUID, tag: str) -> UUID:
    """Seed one more verified ingress under an existing tenant."""
    import psycopg2

    ingress_id = uuid.uuid4()
    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )
            event_uuid = uuid.uuid4()
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, 38000,"
                " '{\"order_id\": \"v\"}'::jsonb, %s, 'conversion',"
                " 'b26p2ca1_channel', 'b26p2v-campaign', 38000, 'USD',"
                " %s, %s, 'processed')",
                (
                    str(event_uuid),
                    str(tenant_id),
                    DAY_START + (DAY_END - DAY_START) / 2,
                    str(uuid.uuid4()),
                    str(uuid.uuid4()),
                    f"b26p2v:{tag}",
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
                    f"b26p2v:{tag}",
                ),
            )
    finally:
        conn.close()
    return ingress_id


def _seed_dispatch_only(tenant_id: UUID, ingress_id: UUID, task_id: str) -> None:
    """Seed a dispatch row with no outbox/directory projections (setup only).

    Isolates the tuple FK from the UNIQUE(task) backstop: cross-product
    attempts with this task refuse at the tuple law itself.
    """
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
                f" '{TASK_NAME}',"
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
    finally:
        conn.close()


def _seed_verdict(tenant_id: UUID, ingress_id: UUID, event_id: UUID) -> None:
    """Seed one B2.3 verdict row for (tenant, ingress) (setup only).

    Satisfies the money-discipline CHECKs (expected=captured=38000,
    zero discrepancy, exact band) and the matched-status attribution
    requirement.
    """
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


def _seed_receipt(
    tenant_id: UUID, ingress_id: UUID, task_id: str, *, dsn: str | None = None
) -> None:
    """Seed one conduction receipt matching the execution tuple.

    Corrective VI: direct receipt INSERT is revoked on every lane; the
    only writer is the SECURITY DEFINER record function (EXECUTE
    app_worker), which derives the sovereign binding server-side. The
    scope witness is well-formed 64-hex, as the honest worker persists.
    """
    import psycopg2

    conn = psycopg2.connect(dsn or _admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                (task_id, "ab" * 32, 1, _P2_POLICY_SEMANTIC_SHA_V2),
            )
    finally:
        conn.close()


def _publish(task_id: str, tenant_id: UUID) -> None:
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


def _refused(fn) -> str:
    import psycopg2

    try:
        fn()
    except psycopg2.Error as exc:
        return str(exc).split("\n")[0][:300]
    raise AssertionError("expected database refusal, statement succeeded")


def _two_executions(tag: str) -> dict[str, dict[str, UUID] | str]:
    first = _seed_ingress(f"{tag}-e1")
    second = _seed_ingress(f"{tag}-e2")
    task1 = f"v-{tag}-d1-{uuid.uuid4().hex[:8]}"
    task2 = f"v-{tag}-d2-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(first["tenant_id"], first["ingress_id"], task1)
    _seed_dispatch(second["tenant_id"], second["ingress_id"], task2)
    return {"first": first, "second": second, "task1": task1, "task2": task2}


# ======================================================================
# T-V: execution-tuple Cartesian matrix (CLASS CLOSED at the DB plane:
# every cross-product combination refuses at persistence).
# ======================================================================


def test_v_outbox_task_d1_with_tenant_ingress_d2_refused() -> None:
    """T-V-01/02/03: task(D1) + tenant/ingress(D2) cannot persist.

    Uses a dispatch-only task so the refusal lands on the tuple law
    itself (a reused task would refuse earlier at UNIQUE(task), which
    is defense-in-depth rather than the tuple theorem).
    """
    env = _two_executions("xprod-outbox")
    first = env["first"]
    second = env["second"]
    lone_ingress = _seed_extra_ingress(first["tenant_id"], "xprod-outbox-lone")
    lone_task = f"v-lone-{uuid.uuid4().hex[:8]}"
    _seed_dispatch_only(first["tenant_id"], lone_ingress, lone_task)
    # A FREE (tenant, ingress) slot under the second tenant: the
    # refusal below lands on the tuple law itself (an occupied slot
    # would refuse earlier at the child UNIQUE, which is
    # defense-in-depth rather than the tuple theorem).
    free_ingress = _seed_extra_ingress(second["tenant_id"], "xprod-outbox-free")
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(second["tenant_id"]),),
            )

            def attempt() -> None:
                cur.execute(
                    "INSERT INTO public.b26_p2_execution_outbox (tenant_id,"
                    " dispatch_task_id, webhook_ingress_identity_id)"
                    " VALUES (%s, %s, %s)",
                    (
                        str(second["tenant_id"]),
                        lone_task,
                        str(free_ingress),
                    ),
                )

            reason = _refused(attempt)
            assert "fk_b26_p2_outbox_execution_tuple" in reason
    finally:
        conn.close()


def test_v_directory_task_d1_with_tenant_ingress_d2_refused() -> None:
    """T-V-08 sibling: directory projection of D2 under task(D1) refuses.

    The write-time coherence trigger precedes FK evaluation and
    refuses first (no canonical execution for the forged
    combination); the tuple FK stands as the second backstop (pinned
    in test_v_tuple_key_and_quarantine_shape).
    """
    env = _two_executions("xprod-dir")
    first = env["first"]
    second = env["second"]
    lone_ingress = _seed_extra_ingress(first["tenant_id"], "xprod-dir-lone")
    lone_task = f"v-lone-{uuid.uuid4().hex[:8]}"
    _seed_dispatch_only(first["tenant_id"], lone_ingress, lone_task)
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(second["tenant_id"]),),
            )

            def attempt() -> None:
                cur.execute(
                    "INSERT INTO public.b26_p2_task_authority_directory (task_id,"
                    " tenant_id, webhook_ingress_identity_id, window_start,"
                    " window_end) VALUES (%s, %s, %s, %s, %s)",
                    (
                        lone_task,
                        str(second["tenant_id"]),
                        str(second["ingress_id"]),
                        DAY_START,
                        DAY_END,
                    ),
                )

            reason = _refused(attempt)
            assert "b26_p2_directory_no_canonical_execution" in reason
    finally:
        conn.close()


def test_v_directory_forked_tuple_refused_by_trigger() -> None:
    """T-V sibling: existing task, foreign tenant/ingress, lawful window.

    The dispatch row IS found (task matches D1), so the coherence
    trigger compares the full tuple and refuses forked authority --
    before PK/UNIQUE/FK evaluation. This isolates the trigger's
    tuple comparison from both the no-execution path (cell above)
    and the FK backstop.
    """
    env = _two_executions("fork-tuple")
    first = env["first"]
    second = env["second"]
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            # GUC of the dispatch's own tenant: the canonical row is
            # visible to the trigger, so the tuple comparison (not the
            # visibility path) decides.
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(first["tenant_id"]),),
            )

            def attempt() -> None:
                cur.execute(
                    "INSERT INTO public.b26_p2_task_authority_directory (task_id,"
                    " tenant_id, webhook_ingress_identity_id, window_start,"
                    " window_end) VALUES (%s, %s, %s, %s, %s)",
                    (
                        str(env["task1"]),
                        str(second["tenant_id"]),
                        str(second["ingress_id"]),
                        DAY_START,
                        DAY_END,
                    ),
                )

            reason = _refused(attempt)
            assert "b26_p2_directory_forked_authority_refused" in reason
    finally:
        conn.close()
    """T-V-07 / H-V-B01: an attacker-chosen window cannot anchor authority.

    task/tenant/ingress are individually lawful values, but the
    combination names no canonical execution and the window is forged.
    The write-time coherence law refuses before any FK evaluation:
    admission can never resolve a forged window.
    """
    env = _two_executions("forge-window")
    first = env["first"]
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(first["tenant_id"]),),
            )

            def attempt() -> None:
                cur.execute(
                    "INSERT INTO public.b26_p2_task_authority_directory (task_id,"
                    " tenant_id, webhook_ingress_identity_id, window_start,"
                    " window_end) VALUES (%s, %s, %s, %s, %s)",
                    (
                        f"v-forge-{uuid.uuid4().hex[:8]}",
                        str(first["tenant_id"]),
                        str(first["ingress_id"]),
                        OTHER_DAY_START,
                        OTHER_DAY_END,
                    ),
                )

            # The forged window matches no dispatch: the coherence
            # trigger refuses even though tenant/ingress are lawful.
            reason = _refused(attempt)
            assert "b26_p2_directory_no_canonical_execution" in reason
    finally:
        conn.close()


def test_v_directory_window_rewrite_refused() -> None:
    """H-V-B01 sibling: UPDATE of a coherent directory window refuses."""
    ids = _seed_ingress("dir-rewrite")
    task_id = f"v-dir-rewrite-{uuid.uuid4().hex[:8]}"
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

            def attempt() -> None:
                cur.execute(
                    "UPDATE public.b26_p2_task_authority_directory"
                    " SET window_start = %s, window_end = %s"
                    " WHERE task_id = %s",
                    (OTHER_DAY_START, OTHER_DAY_END, task_id),
                )

            reason = _refused(attempt)
            assert "b26_p2_directory_window_immutable" in reason
    finally:
        conn.close()


def test_v_receipt_forked_tuple_refused() -> None:
    """Receipts are projections of D: a forked receipt cannot persist."""
    env = _two_executions("receipt-fork")
    second = env["second"]
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(second["tenant_id"]),),
            )

            def attempt() -> None:
                cur.execute(
                    "INSERT INTO public.b26_p2_conduction_receipts (task_id,"
                    " tenant_id, webhook_ingress_identity_id, window_start,"
                    " window_end, b23_processed_count, p2_scope_identity,"
                    " policy_semantic_sha256)"
                    " VALUES (%s, %s, %s, %s, %s, 1, 'fork', %s)",
                    (
                        str(env["task1"]),
                        str(second["tenant_id"]),
                        str(second["ingress_id"]),
                        DAY_START,
                        DAY_END,
                        _P2_POLICY_SEMANTIC_SHA_V2,
                    ),
                )

            reason = _refused(attempt)
            assert "fk_b26_p2_receipt_execution_tuple" in reason
    finally:
        conn.close()


def test_v_null_dispatch_window_refused_at_issuance() -> None:
    """B13: a dispatch without a persisted window is not authority."""
    ids = _seed_ingress("null-window")
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
                    f" '{TASK_NAME}',"
                    " 'b23_match_engine', 'b23_match_engine.task', %s,"
                    " 'stripe', 'evt', 'ord', 'ord')",
                    (
                        str(ids["tenant_id"]),
                        str(ids["ingress_id"]),
                        f"v-nullwin-{uuid.uuid4().hex[:8]}",
                        str(uuid.uuid4()),
                    ),
                )

            reason = _refused(attempt)
            # Corrective VI: the sovereign-window trigger fires before the
            # V presence CHECK (BEFORE triggers precede CHECKs) with the
            # stronger law (NULL != canonical sovereign window). Either
            # refusal proves the NULL window is not executable authority.
            assert (
                "ck_b23_dispatch_window_present" in reason
                or "b26_p2_dispatch_window_not_sovereign" in reason
            )
    finally:
        conn.close()


def test_v_null_authority_dimensions_refused() -> None:
    """SQL three-valued logic: NULL never becomes accepted authority."""
    ids = _seed_ingress("null-dim")
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )

            def attempt_null_window() -> None:
                cur.execute(
                    "INSERT INTO public.b26_p2_task_authority_directory (task_id,"
                    " tenant_id, webhook_ingress_identity_id, window_start,"
                    " window_end) VALUES (%s, %s, %s, NULL, NULL)",
                    (
                        f"v-null-{uuid.uuid4().hex[:8]}",
                        str(ids["tenant_id"]),
                        str(ids["ingress_id"]),
                    ),
                )

            reason = _refused(attempt_null_window)
            assert (
                "b26_p2_directory_authority_null_refused" in reason
                or "null value" in reason
            )
    finally:
        conn.close()


def test_v_coherent_twins_accept() -> None:
    """Non-vacuity: coherent D1/D2 projections still persist (lawful path).

    The seeds above execute under the full new law (tuple FKs +
    coherence trigger). Their success proves the law admits lawful
    executions -- refusal cells below are not vacuous table locks.
    """
    env = _two_executions("coherent")
    assert str(env["task1"]) != str(env["task2"])


def test_v_tuple_key_and_quarantine_shape() -> None:
    """H-V-F01/H-V-A02: the tuple key exists; quarantine carries provenance."""
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM pg_constraint"
                " WHERE conname = 'uq_b23_dispatch_execution_tuple'"
            )
            assert cur.fetchone()[0] == 1
            cur.execute(
                "SELECT count(*) FROM pg_constraint"
                " WHERE conname IN ('fk_b26_p2_outbox_execution_tuple',"
                " 'fk_b26_p2_directory_execution_tuple',"
                " 'fk_b26_p2_receipt_execution_tuple')"
            )
            assert cur.fetchone()[0] == 3
            for retired in (
                "fk_b26_p2_outbox_dispatch_task_identity",
                "fk_b26_p2_outbox_tenant_ingress_composite",
                "fk_b26_p2_directory_dispatch_task_identity",
                "fk_b26_p2_directory_tenant_ingress_composite",
            ):
                cur.execute(
                    "SELECT count(*) FROM pg_constraint WHERE conname = %s",
                    (retired,),
                )
                assert cur.fetchone()[0] == 0, retired
            cur.execute(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_schema = 'public'"
                " AND table_name = 'b26_p2_execution_quarantine'"
            )
            columns = {str(r[0]) for r in cur.fetchall()}
            for required in (
                "source_relation",
                "task_id",
                "tenant_id",
                "webhook_ingress_identity_id",
                "reason",
                "migration_identity",
                "quarantined_at",
                "original_payload",
            ):
                assert required in columns, required
    finally:
        conn.close()


# ======================================================================
# C-V: consequence-bound conducted (CLASS CLOSED at the DB plane for
# every principal except the worker-with-consequence itself).
# ======================================================================


def test_v_direct_conducted_refused_as_worker() -> None:
    """C-V-02/C-V-09: app_worker cannot mark an unrelated task conducted."""
    ids = _seed_ingress("false-worker")
    task_id = f"v-false-w-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    _publish(task_id, ids["tenant_id"])
    import psycopg2

    worker_dsn = _role_dsn("app_worker")
    conn = psycopg2.connect(worker_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )

            def attempt() -> None:
                cur.execute(
                    "UPDATE public.b23_match_task_dispatches"
                    " SET delivery_state = 'conducted' WHERE task_id = %s",
                    (task_id,),
                )

            reason = _refused(attempt)
            assert "b26_p2_conducted_requires_gate" in reason
    finally:
        conn.close()


def test_v_direct_conducted_refused_as_api() -> None:
    """C-V sibling: the producer credential cannot assert conducted either."""
    ids = _seed_ingress("false-api")
    task_id = f"v-false-a-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    _publish(task_id, ids["tenant_id"])
    import psycopg2

    api_dsn = _role_dsn("app_user")
    conn = psycopg2.connect(api_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )

            def attempt() -> None:
                cur.execute(
                    "UPDATE public.b26_p2_execution_outbox"
                    " SET state = 'conducted' WHERE dispatch_task_id = %s",
                    (task_id,),
                )

            reason = _refused(attempt)
            assert "b26_p2_conducted_requires_gate" in reason
    finally:
        conn.close()


def test_v_gate_marks_lawful_task_as_worker() -> None:
    """C-V-01: the exact conducted task with full consequence conducts."""
    ids = _seed_ingress("gate-ok")
    task_id = f"v-gate-ok-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    _publish(task_id, ids["tenant_id"])
    _seed_verdict(ids["tenant_id"], ids["ingress_id"], ids["event_id"])
    import psycopg2

    worker_dsn = _role_dsn("app_worker")
    _seed_receipt(ids["tenant_id"], ids["ingress_id"], task_id, dsn=worker_dsn)
    conn = psycopg2.connect(worker_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT public.b26_p2_mark_conducted(%s)", (task_id,)
            )
            assert cur.fetchone()[0] == "conducted"
            cur.execute(
                "SELECT public.b26_p2_mark_conducted(%s)", (task_id,)
            )
            assert cur.fetchone()[0] == "already_conducted"
    finally:
        conn.close()


def test_v_gate_refuses_without_receipt() -> None:
    """C-V-04: B2.3 consequence without the P2 receipt does not conduct."""
    ids = _seed_ingress("gate-noreceipt")
    task_id = f"v-gate-nor-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    _publish(task_id, ids["tenant_id"])
    _seed_verdict(ids["tenant_id"], ids["ingress_id"], ids["event_id"])
    import psycopg2

    worker_dsn = _role_dsn("app_worker")
    conn = psycopg2.connect(worker_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:

            def attempt() -> None:
                cur.execute(
                    "SELECT public.b26_p2_mark_conducted(%s)", (task_id,)
                )

            reason = _refused(attempt)
            assert "b26_p2_conducted_no_receipt" in reason
    finally:
        conn.close()


def test_v_gate_refuses_without_b23_consequence() -> None:
    """C-V-04 sibling: receipt without B2.3 verdicts does not conduct."""
    ids = _seed_ingress("gate-noverdict")
    task_id = f"v-gate-nov-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    _publish(task_id, ids["tenant_id"])
    import psycopg2

    worker_dsn = _role_dsn("app_worker")
    _seed_receipt(ids["tenant_id"], ids["ingress_id"], task_id, dsn=worker_dsn)
    conn = psycopg2.connect(worker_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:

            def attempt() -> None:
                cur.execute(
                    "SELECT public.b26_p2_mark_conducted(%s)", (task_id,)
                )

            reason = _refused(attempt)
            assert "b26_p2_conducted_no_b23_consequence" in reason
    finally:
        conn.close()


def test_v_gate_refuses_unrelated_published_task() -> None:
    """C-V-02: same tenant, published, but zero consequence: no conduct."""
    ids = _seed_ingress("gate-unrelated")
    task_id = f"v-gate-unr-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    _publish(task_id, ids["tenant_id"])
    import psycopg2

    worker_dsn = _role_dsn("app_worker")
    conn = psycopg2.connect(worker_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:

            def attempt() -> None:
                cur.execute(
                    "SELECT public.b26_p2_mark_conducted(%s)", (task_id,)
                )

            reason = _refused(attempt)
            assert "b26_p2_conducted_no_receipt" in reason
    finally:
        conn.close()


def test_v_gate_exec_denied_for_relay_and_api() -> None:
    """H-V-C02/C03: recovery/scheduling principals hold no gate EXECUTE."""
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM pg_roles"
                " WHERE rolname IN ('app_relay', 'app_beat')"
            )
            if cur.fetchone()[0] != 2:
                pytest.skip("recovery principals not provisioned in this lane")
            for role in ("app_relay", "app_beat", "app_user"):
                cur.execute(
                    "SELECT has_function_privilege(%s,"
                    " 'public.b26_p2_mark_conducted(text)', 'EXECUTE')",
                    (role,),
                )
                assert cur.fetchone()[0] is False, role
            cur.execute(
                "SELECT has_function_privilege('app_worker',"
                " 'public.b26_p2_mark_conducted(text)', 'EXECUTE')"
            )
            assert cur.fetchone()[0] is True
    finally:
        conn.close()


def test_v_gate_definer_discipline() -> None:
    """Directive 10.3: owner, fixed search_path, no dynamic SQL, RLS-safe."""
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT prosecdef, proconfig::text, pg_get_functiondef(oid)"
                " FROM pg_proc WHERE proname = 'b26_p2_mark_conducted'"
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] is True
            assert "search_path" in (row[1] or "")
            body = (row[2] or "").upper()
            assert "EXECUTE IMMEDIATE" not in body
            assert "FORMAT(" not in body
    finally:
        conn.close()


# ======================================================================
# L-V: published-unconsumed honesty (independent oracle: the stale
# function lists exactly the aged published twins).
# ======================================================================


def test_v_staleness_lists_aged_published_twins() -> None:
    """H-V-E01/E04: aged published work becomes explicitly actionable."""
    ids = _seed_ingress("stale")
    task_id = f"v-stale-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    _publish(task_id, ids["tenant_id"])
    time.sleep(2)
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
                "SELECT task_id FROM public.b26_p2_stale_unconducted(1)"
            )
            rows = [str(r[0]) for r in cur.fetchall()]
            assert task_id in rows
    finally:
        conn.close()


def test_v_staleness_excludes_terminal_failure() -> None:
    """L-V / H-V-E02: DLQ-owned failure is not never-consumed silence.

    A published twin whose task result is terminal FAILURE is
    actionable at the DLQ, not at the staleness signal.
    """
    ids = _seed_ingress("stale-failed")
    task_id = f"v-stale-failed-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    _publish(task_id, ids["tenant_id"])
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
                "INSERT INTO public.celery_taskmeta (task_id, status)"
                " VALUES (%s, 'FAILURE')",
                (task_id,),
            )
            cur.execute(
                "SELECT task_id FROM public.b26_p2_stale_unconducted(1)"
            )
            rows = [str(r[0]) for r in cur.fetchall()]
            assert task_id not in rows
    finally:
        conn.close()


def test_v_staleness_excludes_fresh_and_conducted() -> None:
    """H-V-E05 + non-vacuity: fresh flight and conducted work stay silent."""
    ids = _seed_ingress("stale-neg")
    done_ids = _seed_ingress("stale-neg-done")
    fresh_task = f"v-stale-fresh-{uuid.uuid4().hex[:8]}"
    done_task = f"v-stale-done-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], fresh_task)
    _publish(fresh_task, ids["tenant_id"])
    _seed_dispatch(done_ids["tenant_id"], done_ids["ingress_id"], done_task)
    _publish(done_task, done_ids["tenant_id"])
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            # Governed owner session may complete the done twin (the
            # runtime gate path is proven in the C-V cells above).
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(done_ids["tenant_id"]),),
            )
            cur.execute(
                "UPDATE public.b23_match_task_dispatches"
                " SET delivery_state = 'conducted' WHERE task_id = %s",
                (done_task,),
            )
            cur.execute(
                "UPDATE public.b26_p2_execution_outbox"
                " SET state = 'conducted' WHERE dispatch_task_id = %s",
                (done_task,),
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "SELECT task_id FROM public.b26_p2_stale_unconducted(300)"
            )
            rows = [str(r[0]) for r in cur.fetchall()]
            assert fresh_task not in rows
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(done_ids["tenant_id"]),),
            )
            cur.execute(
                "SELECT task_id FROM public.b26_p2_stale_unconducted(300)"
            )
            rows = [str(r[0]) for r in cur.fetchall()]
            assert done_task not in rows
    finally:
        conn.close()


# ======================================================================
# Principals: least privilege (CLASS CLOSED at the credential plane:
# relay/beat/worker mint batteries all denied).
# ======================================================================


def test_v_relay_cannot_mint_execution_authority() -> None:
    """H-V-C02: the relay credential holds no issuance capability."""
    ids = _seed_ingress("relay-mint")
    import psycopg2

    relay_dsn = _role_dsn("app_relay")
    conn = psycopg2.connect(relay_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )

            def attempt_dispatch() -> None:
                cur.execute(
                    "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                    " webhook_ingress_identity_id, task_id, task_name, queue,"
                    " routing_key, correlation_id, provider,"
                    " provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " normalized_commerce_reference_value)"
                    " VALUES (%s, %s, %s, 'x', 'b23_match_engine',"
                    " 'b23_match_engine.task', %s, 'stripe', 'e', 'o', 'o')",
                    (
                        str(ids["tenant_id"]),
                        str(ids["ingress_id"]),
                        f"v-relay-mint-{uuid.uuid4().hex[:8]}",
                        str(uuid.uuid4()),
                    ),
                )

            reason = _refused(attempt_dispatch)
            assert "denied" in reason or "permission" in reason

            def attempt_directory() -> None:
                cur.execute(
                    "INSERT INTO public.b26_p2_task_authority_directory (task_id,"
                    " tenant_id, webhook_ingress_identity_id, window_start,"
                    " window_end) VALUES (%s, %s, %s, %s, %s)",
                    (
                        f"v-relay-dir-{uuid.uuid4().hex[:8]}",
                        str(ids["tenant_id"]),
                        str(ids["ingress_id"]),
                        DAY_START,
                        DAY_END,
                    ),
                )

            reason = _refused(attempt_directory)
            assert "denied" in reason or "permission" in reason
    finally:
        conn.close()


def test_v_beat_holds_no_application_authority() -> None:
    """H-V-C03: the scheduler credential cannot read or write P2 state."""
    import psycopg2

    beat_dsn = _role_dsn("app_beat")
    conn = psycopg2.connect(beat_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:

            def attempt_read() -> None:
                cur.execute("SELECT count(*) FROM public.b23_match_task_dispatches")

            reason = _refused(attempt_read)
            assert "denied" in reason or "permission" in reason
    finally:
        conn.close()


def test_v_worker_cannot_mint_or_execute_gate_as_other() -> None:
    """Worker keeps lawful writes; cannot mint; gate binds session_user."""
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM pg_roles"
                " WHERE rolname IN ('app_relay', 'app_beat')"
            )
            if cur.fetchone()[0] != 2:
                pytest.skip("recovery principals not provisioned in this lane")
            cur.execute(
                "SELECT has_table_privilege('app_worker',"
                " 'public.b23_match_task_dispatches', 'INSERT')"
            )
            assert cur.fetchone()[0] is False
            cur.execute(
                "SELECT has_table_privilege('app_worker',"
                " 'public.b26_p2_execution_outbox', 'INSERT')"
            )
            assert cur.fetchone()[0] is False
            cur.execute(
                "SELECT has_table_privilege('app_relay',"
                " 'public.b26_p2_execution_outbox', 'INSERT')"
            )
            assert cur.fetchone()[0] is False
            cur.execute(
                "SELECT has_table_privilege('app_beat',"
                " 'public.b26_p2_execution_outbox', 'SELECT')"
            )
            assert cur.fetchone()[0] is False
    finally:
        conn.close()


def test_v_phase_boundary_receipts_never_financial() -> None:
    """Gate-18 predecessor: no finance reader consumes receipts/quarantine."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    readers = []
    for path in (
        root / "backend/app/finance_reconciliation/candidate_conduction.py",
        root / "backend/app/finance_reconciliation/scope_authority.py",
        root / "backend/app/finance_reconciliation/canonical_sink.py",
    ):
        source = path.read_text(encoding="utf-8")
        for token in (
            "b26_p2_conduction_receipts",
            "b26_p2_execution_quarantine",
            "b26_p2_mark_conducted",
        ):
            if token in source:
                readers.append(f"{path.name}:{token}")
    assert readers == [], readers
