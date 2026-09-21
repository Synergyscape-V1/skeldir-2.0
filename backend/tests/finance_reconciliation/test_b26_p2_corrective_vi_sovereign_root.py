"""B2.6-P2 Corrective VI sovereign-root / consequence / disposition battery.

Governing classes (Corrective VI directive, hypothesis groups A-C):

A. CANONICAL EXECUTION ROOT: dispatch.window must equal the canonical
   UTC day of the authenticated ingress clock at the database plane
   (not merely at issuance), the ingress clock must be immutable once
   authoritative, and pre-B2.3 admission must re-establish D from E.
B. P2 CONSEQUENCE PROOF: the conduction receipt must stop being
   self-authenticating (worker INSERT revoked; owner-function writer;
   gate independently re-verifies sovereign window, narrow B2.3
   statuses, receipt binding, scope shape).
C. TOTAL OPERATIONAL DISPOSITION: immutable progress anchor, bounded
   threshold authority, telemetry-agreement exclusion, quarantine and
   zombie actionability.

Every cell seeds durable rows (setup, never authority) and asserts
database behavior against a real PostgreSQL instance migrated to the
Corrective-VI head, acting through the exact runtime principals.
Closure levels follow the directive: CLASS CLOSED only when the
prohibited EFFECT has no reachable representation across the
mechanically enumerated authority surface (see
scripts/ci/b26_p2_capability_surface.py).
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
OTHER_DAY_START = datetime(2026, 1, 20, 0, 0, tzinfo=timezone.utc)
OTHER_DAY_END = datetime(2026, 1, 21, 0, 0, tzinfo=timezone.utc)

TASK_NAME = "app.tasks.revenue_verification.execute_b23_batch_match_engine"
SCOPE_HEX = "ab" * 32
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
    dsn = os.environ.get("MIGRATION_database_URL", "").strip()
    if not dsn:
        dsn = os.environ.get("MIGRATION_DATABASE_URL", "").strip()
    if not dsn:
        pytest.skip("P2 Corrective-VI DB cells need MIGRATION_DATABASE_URL")
    return dsn


def _role_dsn(role: str) -> str:
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
                    f"b26p2vi-{tag}",
                    uuid.uuid4().hex,
                    f"b26p2vi-{tag}@example.invalid",
                ),
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )
            cur.execute(
                "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
                " display_name, state) VALUES ('b26p2vi_channel', 'b26p2vi',"
                " true, 'B26P2VI', 'active') ON CONFLICT (code) DO NOTHING"
            )
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, 38000,"
                " '{\"order_id\": \"vi\"}'::jsonb, %s, 'conversion',"
                " 'b26p2vi_channel', 'b26p2vi-campaign', 38000, 'USD',"
                " %s, %s, 'processed')",
                (
                    str(event_uuid),
                    str(tenant_id),
                    DAY_NOON,
                    str(uuid.uuid4()),
                    str(uuid.uuid4()),
                    f"b26p2vi:{tag}",
                    DAY_NOON,
                    DAY_NOON,
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
                    DAY_NOON,
                    f"b26p2vi:{tag}",
                ),
            )
    finally:
        conn.close()
    return {"tenant_id": tenant_id, "ingress_id": ingress_id, "event_id": event_uuid}


def _seed_extra_ingress(tenant_id: UUID, tag: str) -> UUID:
    import psycopg2

    ingress_id = uuid.uuid4()
    event_uuid = uuid.uuid4()
    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, 38000,"
                " '{\"order_id\": \"vi\"}'::jsonb, %s, 'conversion',"
                " 'b26p2vi_channel', 'b26p2vi-campaign', 38000, 'USD',"
                " %s, %s, 'processed')",
                (
                    str(event_uuid),
                    str(tenant_id),
                    DAY_NOON,
                    str(uuid.uuid4()),
                    str(uuid.uuid4()),
                    f"b26p2vi:{tag}",
                    DAY_NOON,
                    DAY_NOON,
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
                    DAY_NOON,
                    f"b26p2vi:{tag}",
                ),
            )
    finally:
        conn.close()
    return ingress_id


def _seed_dispatch(
    tenant_id: UUID,
    ingress_id: UUID,
    task_id: str,
    *,
    window_start: datetime = DAY_START,
    window_end: datetime = DAY_END,
    dsn: str | None = None,
) -> None:
    import psycopg2

    conn = psycopg2.connect(dsn or _admin_dsn())
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
                    task_id,
                    str(uuid.uuid4()),
                    window_start,
                    window_end,
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
                (
                    task_id,
                    str(tenant_id),
                    str(ingress_id),
                    window_start,
                    window_end,
                ),
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


def _seed_verdict(
    tenant_id: UUID, ingress_id: UUID, event_id: UUID, *, status: str
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
                " %s, 'high', 38000, 38000, 'USD',"
                " 38000, 38000, 38000, 0, 0, 'exact')",
                (str(tenant_id), str(event_id), str(ingress_id), status),
            )
    finally:
        conn.close()


# ======================================================================
# R6: root-authority experiment family (H-VI-A01..A06).
# ======================================================================


def test_vi_r6_03_wrong_utc_day_refused_at_issuance() -> None:
    """H-VI-A01: window present+ordered is not enough; sovereign equality
    is enforced at INSERT for the issuer principal."""
    ids = _seed_ingress("r6-03")
    import psycopg2

    conn = psycopg2.connect(_role_dsn("app_user"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )

            def attempt() -> None:
                _seed_dispatch(
                    ids["tenant_id"],
                    ids["ingress_id"],
                    f"vi-r6-03-{uuid.uuid4().hex[:8]}",
                    window_start=OTHER_DAY_START,
                    window_end=OTHER_DAY_END,
                    dsn=_role_dsn("app_user"),
                )

            reason = _refused(attempt)
            assert "b26_p2_dispatch_window_not_sovereign" in reason
    finally:
        conn.close()


def test_vi_r6_04_12h_window_refused() -> None:
    """H-VI-A01 sibling: structurally valid 12-hour window refuses."""
    ids = _seed_ingress("r6-04")
    noon_end = datetime(2026, 1, 15, 18, 0, tzinfo=timezone.utc)
    noon_start = datetime(2026, 1, 15, 6, 0, tzinfo=timezone.utc)

    def attempt() -> None:
        _seed_dispatch(
            ids["tenant_id"],
            ids["ingress_id"],
            f"vi-r6-04-{uuid.uuid4().hex[:8]}",
            window_start=noon_start,
            window_end=noon_end,
            dsn=_role_dsn("app_user"),
        )

    reason = _refused(attempt)
    assert "b26_p2_dispatch_window_not_sovereign" in reason


def test_vi_r6_07_ingress_clock_immutable_once_authoritative() -> None:
    """H-VI-A02/A06: the authoritative event clock cannot drift after D."""
    ids = _seed_ingress("r6-07")
    task_id = f"vi-r6-07-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    import psycopg2

    conn = psycopg2.connect(_role_dsn("app_user"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )

            def attempt() -> None:
                cur.execute(
                    "UPDATE public.webhook_ingress_identities"
                    " SET event_timestamp = %s WHERE id = %s",
                    (
                        datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc),
                        str(ids["ingress_id"]),
                    ),
                )

            reason = _refused(attempt)
            assert "b26_p2_ingress_event_clock_immutable" in reason
    finally:
        conn.close()


def test_vi_r6_07b_ingress_identity_immutable_once_authoritative() -> None:
    """H-VI-A06 sibling: tenant/provider reassignment of an authoritative
    ingress refuses alongside the event clock."""
    ids = _seed_ingress("r6-07b")
    task_id = f"vi-r6-07b-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    import psycopg2

    conn = psycopg2.connect(_role_dsn("app_user"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )

            def attempt_provider() -> None:
                cur.execute(
                    "UPDATE public.webhook_ingress_identities"
                    " SET provider = 'paypal' WHERE id = %s",
                    (str(ids["ingress_id"]),),
                )

            reason = _refused(attempt_provider)
            assert "b26_p2_ingress_provider_immutable" in reason

            def attempt_tenant() -> None:
                cur.execute(
                    "UPDATE public.webhook_ingress_identities"
                    " SET tenant_id = %s WHERE id = %s",
                    (str(uuid.uuid4()), str(ids["ingress_id"])),
                )

            reason = _refused(attempt_tenant)
            assert "b26_p2_ingress_tenant_immutable" in reason
    finally:
        conn.close()


def test_vi_r6_08_dispatch_window_mutation_refused() -> None:
    """Window immutability preserved under VI (Corrective-V law holds)."""
    ids = _seed_ingress("r6-08")
    task_id = f"vi-r6-08-{uuid.uuid4().hex[:8]}"
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
                    "UPDATE public.b23_match_task_dispatches"
                    " SET window_start = %s WHERE task_id = %s",
                    (OTHER_DAY_START, task_id),
                )

            reason = _refused(attempt)
            assert "b26_p2_dispatch_window_immutable" in reason
    finally:
        conn.close()


def test_vi_r6_08b_dispatch_identity_frozen_matrix() -> None:
    """Every sovereign/identity column of the dispatch tuple refuses
    UPDATE through the issuer credential: the frozen-column matrix is
    mechanical (one attempt per column), not sampled."""
    ids = _seed_ingress("r6-08b")
    task_id = f"vi-r6-08b-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    import psycopg2

    cases = (
        ("tenant_id", str(uuid.uuid4()), "b26_p2_dispatch_tenant_immutable"),
        (
            "webhook_ingress_identity_id",
            str(uuid.uuid4()),
            "b26_p2_dispatch_ingress_immutable",
        ),
        ("task_id", "renamed-task", "b26_p2_dispatch_task_id_immutable"),
        ("task_name", "other.task", "b26_p2_dispatch_task_name_immutable"),
        ("queue", "other_queue", "b26_p2_dispatch_queue_immutable"),
        ("provider", "paypal", "b26_p2_dispatch_provider_immutable"),
        (
            "window_end",
            OTHER_DAY_END,
            "b26_p2_dispatch_window_immutable",
        ),
    )
    conn = psycopg2.connect(_role_dsn("app_user"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            for column, value, expected in cases:

                def attempt(col=column, val=value) -> None:
                    cur.execute(
                        "UPDATE public.b23_match_task_dispatches"
                        f" SET {col} = %s WHERE task_id = %s",
                        (val, task_id),
                    )

                reason = _refused(attempt)
                assert expected in reason, (column, reason)
    finally:
        conn.close()


def test_vi_r6_09_resolver_returns_canonical_refuses_forged() -> None:
    """H-VI-A03/A04: admission resolves the canonical window from E.

    The lawful task resolves to the sovereign UTC day (not the stored
    copy -- they coincide here), and a structurally coherent but
    non-sovereign projection cannot be constructed to test the
    resolver against (dispatch INSERT already refuses), so the
    sovereign refusal path is proven by planting a forged root with
    triggers parked (migration authority) and observing resolver RED.
    """
    ids = _seed_ingress("r6-09")
    task_id = f"vi-r6-09-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    import psycopg2

    for dsn in (_admin_dsn(), _role_dsn("app_user"), _role_dsn("app_worker")):
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (str(ids["tenant_id"]),),
                )
                cur.execute(
                    "SELECT window_start, window_end FROM"
                    " public.b26_p2_resolve_dispatch_authority(%s)",
                    (task_id,),
                )
                row = cur.fetchone()
                assert row is not None
                assert row[0] == DAY_START and row[1] == DAY_END
        finally:
            conn.close()


def test_vi_r6_11_task_kind_locked_by_check() -> None:
    """H-VI-A05: task_name/queue/status admit exactly one governed value
    (CHECK physics), so no caller-conventional execution kind survives."""
    ids = _seed_ingress("r6-11")
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
                    " normalized_commerce_reference_value, window_start,"
                    " window_end) VALUES (%s, %s, %s,"
                    " 'app.tasks.something_else',"
                    " 'b23_match_engine', 'b23_match_engine.task', %s,"
                    " 'stripe', 'evt', 'ord', 'ord', %s, %s)",
                    (
                        str(ids["tenant_id"]),
                        str(ids["ingress_id"]),
                        f"vi-r6-11-{uuid.uuid4().hex[:8]}",
                        str(uuid.uuid4()),
                        DAY_START,
                        DAY_END,
                    ),
                )

            reason = _refused(attempt)
            assert "ck_b23_match_task_dispatches_task_name" in reason
    finally:
        conn.close()


# ======================================================================
# CP6: consequence-proof experiment family (H-VI-B01..B07).
# ======================================================================


def test_vi_cp6_04_worker_direct_receipt_insert_refused() -> None:
    """H-VI-B01: the worker credential cannot synthesize proof rows."""
    ids = _seed_ingress("cp6-04")
    task_id = f"vi-cp6-04-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    import psycopg2

    conn = psycopg2.connect(_role_dsn("app_worker"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )

            def attempt() -> None:
                cur.execute(
                    "INSERT INTO public.b26_p2_conduction_receipts (task_id,"
                    " tenant_id, webhook_ingress_identity_id, window_start,"
                    " window_end, b23_processed_count, p2_scope_identity)"
                    " VALUES (%s, %s, %s, %s, %s, 1, %s)",
                    (
                        task_id,
                        str(ids["tenant_id"]),
                        str(ids["ingress_id"]),
                        DAY_START,
                        DAY_END,
                        SCOPE_HEX,
                    ),
                )

            reason = _refused(attempt)
            assert "permission denied" in reason or "denied" in reason
    finally:
        conn.close()


def test_vi_cp6_05_bogus_scope_refused_by_record_and_gate() -> None:
    """H-VI-B03/B05: decorative scope/window never certify completion."""
    ids = _seed_ingress("cp6-05")
    task_id = f"vi-cp6-05-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    _publish(task_id, ids["tenant_id"])
    _seed_verdict(
        ids["tenant_id"], ids["ingress_id"], ids["event_id"],
        status="matched_confirmed",
    )
    import psycopg2

    worker_dsn = _role_dsn("app_worker")
    conn = psycopg2.connect(worker_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:

            def attempt_record() -> None:
                cur.execute(
                    "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                    (task_id, "SYNTHETIC-FORGED-SCOPE", 1, _P2_POLICY_SEMANTIC_SHA_V2),
                )

            reason = _refused(attempt_record)
            assert "b26_p2_receipt_scope_not_bound" in reason
    finally:
        conn.close()


def test_vi_cp6_12_pending_verdict_never_conducts() -> None:
    """H-VI-B04: the narrow B2.3 prerequisite -- pending/unmatched never
    satisfy the gate, even with a well-formed owner-written receipt."""
    ids = _seed_ingress("cp6-12")
    task_id = f"vi-cp6-12-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    _publish(task_id, ids["tenant_id"])
    _seed_verdict(
        ids["tenant_id"], ids["ingress_id"], ids["event_id"], status="pending"
    )
    import psycopg2

    worker_dsn = _role_dsn("app_worker")
    conn = psycopg2.connect(worker_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                (task_id, SCOPE_HEX, 1, _P2_POLICY_SEMANTIC_SHA_V2),
            )

            def attempt() -> None:
                cur.execute(
                    "SELECT public.b26_p2_mark_conducted(%s)", (task_id,)
                )

            reason = _refused(attempt)
            assert "b26_p2_conducted_no_b23_consequence" in reason
    finally:
        conn.close()


def test_vi_cp6_01_lawful_conduction_still_converges() -> None:
    """Honest path preserved: sovereign D + qualifying B2.3 + bound
    receipt conducts exactly once through the worker principal."""
    ids = _seed_ingress("cp6-01")
    task_id = f"vi-cp6-01-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    _publish(task_id, ids["tenant_id"])
    _seed_verdict(
        ids["tenant_id"], ids["ingress_id"], ids["event_id"],
        status="matched_confirmed",
    )
    import psycopg2

    worker_dsn = _role_dsn("app_worker")
    conn = psycopg2.connect(worker_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                (task_id, SCOPE_HEX, 1, _P2_POLICY_SEMANTIC_SHA_V2),
            )
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


# ======================================================================
# OD6: operational-disposition experiment family (H-VI-C01..C07).
# ======================================================================


def _age_anchor_admin(task_id: str, tenant_id: UUID, seconds: int) -> None:
    """Park the immutability trigger (migration authority), age the
    immutable anchor, restore the trigger. Test setup only."""
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            # The migrating principal holds no tenant GUC; without it a
            # bare UPDATE matches zero rows SILENTLY under FORCE RLS.
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )
            cur.execute(
                "ALTER TABLE public.b23_match_task_dispatches"
                " DISABLE TRIGGER trg_b26_p2_dispatch_immutability"
            )
            cur.execute(
                "UPDATE public.b23_match_task_dispatches"
                " SET first_published_at = now() - (%s || ' seconds')::interval"
                " WHERE task_id = %s",
                (str(seconds), task_id),
            )
            assert cur.rowcount == 1, "anchor aging matched no row"
            cur.execute(
                "ALTER TABLE public.b23_match_task_dispatches"
                " ENABLE TRIGGER trg_b26_p2_dispatch_immutability"
            )
    finally:
        conn.close()


def test_vi_od6_08_metadata_bump_keeps_stale_actionable() -> None:
    """H-VI-C01/C02: retry/error bookkeeping cannot make old work young --
    through EVERY runtime principal that holds the metadata writes
    (issuer, worker, relay), on both twins."""
    ids = _seed_ingress("od6-08")
    task_id = f"vi-od6-08-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    _publish(task_id, ids["tenant_id"])
    _age_anchor_admin(task_id, ids["tenant_id"], 400)
    import psycopg2

    for role in ("app_user", "app_worker", "app_relay"):
        conn = psycopg2.connect(_role_dsn(role))
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (str(ids["tenant_id"]),),
                )
                for _ in range(3):
                    cur.execute(
                        "UPDATE public.b23_match_task_dispatches"
                        " SET publish_attempts = publish_attempts + 1,"
                        " last_publish_error = 'retry-note' WHERE task_id = %s",
                        (task_id,),
                    )
                    cur.execute(
                        "UPDATE public.b26_p2_execution_outbox"
                        " SET publish_attempts = publish_attempts + 1,"
                        " last_publish_error = 'retry-note',"
                        " next_retry_at = now() + interval '60 seconds'"
                        " WHERE dispatch_task_id = %s",
                        (task_id,),
                    )
                cur.execute(
                    "SELECT count(*) FROM public.b26_p2_stale_unconducted(300)"
                )
                assert cur.fetchone()[0] >= 1, role
                cur.execute(
                    "SELECT public.b26_p2_operational_disposition(%s)", (task_id,)
                )
                assert cur.fetchone()[0] == "STALE_UNCONDUCTED", role
        finally:
            conn.close()


def test_vi_od6_threshold_bounds_refuse_absurd_suppression() -> None:
    """H-VI-C07: threshold authority is explicit and bounded; absurd
    values refuse instead of silencing detection."""
    ids = _seed_ingress("od6-thr")
    import psycopg2

    conn = psycopg2.connect(_role_dsn("app_user"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )

            def attempt() -> None:
                cur.execute(
                    "SELECT count(*) FROM public.b26_p2_stale_unconducted(9999999)"
                )

            reason = _refused(attempt)
            assert "b26_p2_staleness_threshold_out_of_bounds" in reason
    finally:
        conn.close()


def test_vi_od6_10_failure_without_dlq_stays_visible() -> None:
    """H-VI-C03/C04: transport telemetry disagreement never hides
    accepted work; joint DLQ+FAILURE agreement is the only terminal
    exclusion."""
    ids = _seed_ingress("od6-10")
    task_id = f"vi-od6-10-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    _publish(task_id, ids["tenant_id"])
    _age_anchor_admin(task_id, ids["tenant_id"], 400)
    import psycopg2

    admin = psycopg2.connect(_admin_dsn())
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "INSERT INTO public.celery_taskmeta (task_id, status,"
                " date_done, traceback, name, worker)"
                " VALUES (%s, 'FAILURE', now(), '', 'x', 'w')"
                " ON CONFLICT (task_id) DO UPDATE SET status = 'FAILURE'",
                (task_id,),
            )
    finally:
        admin.close()
    conn = psycopg2.connect(_role_dsn("app_user"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "SELECT count(*) FROM public.b26_p2_stale_unconducted(300)"
            )
            assert cur.fetchone()[0] >= 1
    finally:
        conn.close()


def test_vi_od6_13_quarantine_and_zombie_actionable() -> None:
    """H-VI-C05/C06 + Gate 17: quarantine rows are disposition-visible
    and a dispatch without its outbox twin resolves explicitly."""
    ids = _seed_ingress("od6-13")
    zombie = f"vi-od6-13-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], zombie)
    import psycopg2

    admin = psycopg2.connect(_admin_dsn())
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "DELETE FROM public.b26_p2_execution_outbox"
                " WHERE dispatch_task_id = %s",
                (zombie,),
            )
    finally:
        admin.close()
    conn = psycopg2.connect(_role_dsn("app_user"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "SELECT public.b26_p2_operational_disposition(%s)", (zombie,)
            )
            assert cur.fetchone()[0] == "MISSING_CHILD_ACTIONABLE"
            cur.execute(
                "SELECT public.b26_p2_operational_disposition(%s)",
                ("task-never-issued",),
            )
            assert cur.fetchone()[0] == "NOT_ACCEPTED"
    finally:
        conn.close()


def test_vi_anchor_preset_stripped_and_stamped() -> None:
    """H-VI-C01 hardening: a caller-authored anchor never survives a
    write. Pending rows are stripped to NULL; the publish transition
    stamps now() unconditionally (a preset future anchor cannot ride
    into published life and suppress the signal)."""
    ids = _seed_ingress("anchor-preset")
    task_id = f"vi-anchor-{uuid.uuid4().hex[:8]}"
    import psycopg2

    conn = psycopg2.connect(_role_dsn("app_user"))
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
                " normalized_commerce_reference_value, window_start,"
                " window_end, first_published_at) VALUES (%s, %s, %s,"
                f" '{TASK_NAME}',"
                " 'b23_match_engine', 'b23_match_engine.task', %s,"
                " 'stripe', 'evt', 'ord', 'ord', %s, %s,"
                " now() + interval '30 days')",
                (
                    str(ids["tenant_id"]),
                    str(ids["ingress_id"]),
                    task_id,
                    str(uuid.uuid4()),
                    DAY_START,
                    DAY_END,
                ),
            )
            cur.execute(
                "SELECT first_published_at FROM public.b23_match_task_dispatches"
                " WHERE task_id = %s",
                (task_id,),
            )
            assert cur.fetchone()[0] is None
            cur.execute(
                "UPDATE public.b23_match_task_dispatches"
                " SET publish_attempts = publish_attempts + 1"
                " WHERE task_id = %s",
                (task_id,),
            )
            cur.execute(
                "SELECT first_published_at FROM public.b23_match_task_dispatches"
                " WHERE task_id = %s",
                (task_id,),
            )
            assert cur.fetchone()[0] is None
    finally:
        conn.close()


def test_vi_anchor_takes_precedence_over_dispatched_fallback() -> None:
    """The dispatched_at fallback serves pre-VI rows only: for every
    row published under VI law the immutable anchor governs age, so a
    caller-supplied ancient dispatched_at can neither hide nor invent
    staleness."""
    ids = _seed_ingress("anchor-prec")
    task_id = f"vi-prec-{uuid.uuid4().hex[:8]}"
    import psycopg2

    conn = psycopg2.connect(_role_dsn("app_user"))
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
                " normalized_commerce_reference_value, window_start,"
                " window_end, dispatched_at) VALUES (%s, %s, %s,"
                f" '{TASK_NAME}',"
                " 'b23_match_engine', 'b23_match_engine.task', %s,"
                " 'stripe', 'evt', 'ord', 'ord', %s, %s,"
                " now() - interval '30 days')",
                (
                    str(ids["tenant_id"]),
                    str(ids["ingress_id"]),
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
                (str(ids["tenant_id"]), task_id, str(ids["ingress_id"])),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_task_authority_directory (task_id,"
                " tenant_id, webhook_ingress_identity_id, window_start,"
                " window_end) VALUES (%s, %s, %s, %s, %s)",
                (
                    task_id,
                    str(ids["tenant_id"]),
                    str(ids["ingress_id"]),
                    DAY_START,
                    DAY_END,
                ),
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
            # Freshly published (anchor=now) despite the ancient
            # dispatched_at: not stale under the governed threshold.
            cur.execute(
                "SELECT count(*) FROM public.b26_p2_stale_unconducted(300)"
                " WHERE task_id = %s",
                (task_id,),
            )
            assert cur.fetchone()[0] == 0
    finally:
        conn.close()


def test_vi_outbox_issuance_and_retry_bound() -> None:
    """Outbox twins are minted pending_publish only, with a bounded
    retry horizon: minted-published twins and far-future retries
    refuse, so intent cannot bypass the relay or strand outside it."""
    ids = _seed_ingress("outbox-law")
    extra_ingress = _seed_extra_ingress(ids["tenant_id"], "outbox-law-x")
    task_id = f"vi-outbox-{uuid.uuid4().hex[:8]}"
    twin_task = f"vi-outbox-twin-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    import psycopg2

    conn = psycopg2.connect(_role_dsn("app_user"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            # A dispatch-only execution on the free ingress: no outbox
            # twin exists yet, so the mint-published attempt below
            # reaches the issuance law itself (not a UNIQUE conflict).
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
                    str(ids["tenant_id"]),
                    str(extra_ingress),
                    twin_task,
                    str(uuid.uuid4()),
                    DAY_START,
                    DAY_END,
                ),
            )

            def attempt_mint_published() -> None:
                cur.execute(
                    "INSERT INTO public.b26_p2_execution_outbox (tenant_id,"
                    " dispatch_task_id, webhook_ingress_identity_id, state)"
                    " VALUES (%s, %s, %s, 'published')",
                    (str(ids["tenant_id"]), twin_task, str(extra_ingress)),
                )

            reason = _refused(attempt_mint_published)
            assert "b26_p2_outbox_issuance_state_refused" in reason

            def attempt_far_retry() -> None:
                cur.execute(
                    "UPDATE public.b26_p2_execution_outbox"
                    " SET next_retry_at = now() + interval '30 days'"
                    " WHERE dispatch_task_id = %s",
                    (task_id,),
                )

            reason = _refused(attempt_far_retry)
            assert "b26_p2_outbox_retry_unbounded" in reason
    finally:
        conn.close()


def test_vi_taskmeta_failure_forge_refused_for_issuer() -> None:
    """H-VI-C03/C04 hardening, P2-namespaced: FAILURE is the only
    result-backend state that can terminalize a stale execution, so
    exactly that status -- for exactly P2 execution task ids -- is
    closed to non-transport principals. Non-P2 telemetry (other phases'
    convergence, least-privilege round-trips) and non-terminal statuses
    keep flowing."""
    ids = _seed_ingress("taskmeta-ns")
    task_id = f"vi-ns-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    import psycopg2

    conn = psycopg2.connect(_role_dsn("app_user"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:

            def attempt_p2_failure() -> None:
                cur.execute(
                    "INSERT INTO public.celery_taskmeta (task_id, status,"
                    " date_done, traceback, name, worker)"
                    " VALUES (%s, 'FAILURE', now(), '', 'x', 'w')",
                    (task_id,),
                )

            reason = _refused(attempt_p2_failure)
            assert "b26_p2_result_failure_forge_refused" in reason
            # Non-P2 task ids (other phases' telemetry): FAILURE flows.
            _other = f"vi-other-{uuid.uuid4().hex[:8]}"
            cur.execute(
                "INSERT INTO public.celery_taskmeta (task_id, status,"
                " date_done, traceback, name, worker)"
                " VALUES (%s, 'FAILURE', now(), '', 'x', 'w')",
                (_other,),
            )
            # Non-terminal statuses flow for every task class.
            _rt_task = f"vi-roundtrip-{uuid.uuid4().hex[:8]}"
            cur.execute(
                "INSERT INTO public.celery_taskmeta (task_id, status,"
                " date_done, traceback, name, worker)"
                " VALUES (%s, 'SUCCESS', now(), '', 'x', 'w')",
                (_rt_task,),
            )
            cur.execute(
                "DELETE FROM public.celery_taskmeta WHERE task_id IN (%s, %s)",
                (_other, _rt_task),
            )
    finally:
        conn.close()


def test_vi_dispatch_preexisting_failure_refuses() -> None:
    """Pre-registration closure: minting an execution over a recorded
    FAILURE row refuses -- genuine issuance never reuses a failed task
    identity (relay republishes; duplicates reuse the winner)."""
    ids = _seed_ingress("preexist")
    import psycopg2

    ghost = f"vi-ghost-{uuid.uuid4().hex[:8]}"
    admin = psycopg2.connect(_admin_dsn())
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "INSERT INTO public.celery_taskmeta (task_id, status,"
                " date_done, traceback, name, worker)"
                " VALUES (%s, 'FAILURE', now(), '', 'x', 'w')",
                (ghost,),
            )
    finally:
        admin.close()
    conn = psycopg2.connect(_role_dsn("app_user"))
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
                    " normalized_commerce_reference_value, window_start,"
                    " window_end) VALUES (%s, %s, %s,"
                    f" '{TASK_NAME}',"
                    " 'b23_match_engine', 'b23_match_engine.task', %s,"
                    " 'stripe', 'evt', 'ord', 'ord', %s, %s)",
                    (
                        str(ids["tenant_id"]),
                        str(ids["ingress_id"]),
                        ghost,
                        str(uuid.uuid4()),
                        DAY_START,
                        DAY_END,
                    ),
                )

            reason = _refused(attempt)
            assert "b26_p2_dispatch_result_preexists" in reason
    finally:
        conn.close()
        admin = psycopg2.connect(_admin_dsn())
        admin.autocommit = True
        try:
            with admin.cursor() as cur:
                cur.execute(
                    "DELETE FROM public.celery_taskmeta WHERE task_id = %s",
                    (ghost,),
                )
        finally:
            admin.close()


def test_vi_dispatched_at_frozen() -> None:
    """The issuance instant is part of the anchor fallback law and can
    never move after mint."""
    ids = _seed_ingress("dispatched-frozen")
    task_id = f"vi-dispatched-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    import psycopg2

    conn = psycopg2.connect(_role_dsn("app_user"))
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
                    " SET dispatched_at = now() WHERE task_id = %s",
                    (task_id,),
                )

            reason = _refused(attempt)
            assert "b26_p2_dispatch_dispatched_immutable" in reason
    finally:
        conn.close()


def test_vi_pending_and_terminal_dispositions() -> None:
    """Totality ladder: pending publication and joint-telemetry terminal
    states resolve explicitly per task."""
    ids = _seed_ingress("od6-ladder")
    pending = f"vi-pend-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], pending)
    import psycopg2

    conn = psycopg2.connect(_role_dsn("app_user"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "SELECT public.b26_p2_operational_disposition(%s)", (pending,)
            )
            assert cur.fetchone()[0] == "PENDING_PUBLICATION"
    finally:
        conn.close()


def test_vi_worker_ingress_cannot_become_execution() -> None:
    """Directive 9.1: the worker's ingress-plane INSERTs (inherited via
    app_rw) cannot reach execution authority -- the mint chain dies at
    the dispatch INSERT denial, and no P2 effect follows."""
    ids = _seed_ingress("worker-ingress")
    worker_ingress = _seed_extra_ingress(ids["tenant_id"], "worker-ingress-w")
    import psycopg2

    conn = psycopg2.connect(_role_dsn("app_worker"))
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
                    " normalized_commerce_reference_value, window_start,"
                    " window_end) VALUES (%s, %s, %s,"
                    f" '{TASK_NAME}',"
                    " 'b23_match_engine', 'b23_match_engine.task', %s,"
                    " 'stripe', 'evt', 'ord', 'ord', %s, %s)",
                    (
                        str(ids["tenant_id"]),
                        str(worker_ingress),
                        f"vi-wmint-{uuid.uuid4().hex[:8]}",
                        str(uuid.uuid4()),
                        DAY_START,
                        DAY_END,
                    ),
                )

            reason = _refused(attempt_dispatch)
            assert "denied" in reason.lower() or "permission" in reason.lower()
    finally:
        conn.close()


def test_vi_direct_publish_stays_governed() -> None:
    """Delivery-state writes held by issuer/worker advance transport
    only: publishing twins directly (bypassing the relay) neither
    conducts nor hides -- receipt, verdicts, and the anchor still
    govern, and staleness still fires."""
    ids = _seed_ingress("direct-pub")
    import psycopg2

    for role in ("app_user", "app_worker"):
        task_id = f"vi-dpub-{role[:3]}-{uuid.uuid4().hex[:8]}"
        ingress = _seed_extra_ingress(ids["tenant_id"], f"dpub-{role}")
        _seed_dispatch(ids["tenant_id"], ingress, task_id)
        conn = psycopg2.connect(_role_dsn(role))
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

                def attempt_gate() -> None:
                    cur.execute(
                        "SELECT public.b26_p2_mark_conducted(%s)", (task_id,)
                    )

                # No receipt yet: the gate refuses despite published twins.
                if role == "app_worker":
                    reason = _refused(attempt_gate)
                    assert "b26_p2_conducted_no_receipt" in reason
                cur.execute(
                    "SELECT public.b26_p2_operational_disposition(%s)", (task_id,)
                )
                assert cur.fetchone()[0] == "PUBLISHED_IN_FLIGHT"
        finally:
            conn.close()


def test_vi_pending_publication_disposition() -> None:
    """Totality ladder base: a freshly issued twin resolves to an
    explicit pending state (never an empty row set)."""
    ids = _seed_ingress("od6-pend")
    pending = f"vi-pend-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], pending)
    import psycopg2

    conn = psycopg2.connect(_role_dsn("app_user"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "SELECT public.b26_p2_operational_disposition(%s)", (pending,)
            )
            assert cur.fetchone()[0] == "PENDING_PUBLICATION"
    finally:
        conn.close()


def test_vi_worker_verdict_maturity_duty() -> None:
    """B2.3 authorship is the worker's duty: maturing its own pending
    verdict to matched_confirmed is lawful, and the gate still enforces
    every other independent check (sovereign window, bound receipt,
    published twins) before conducting."""
    ids = _seed_ingress("worker-duty")
    task_id = f"vi-duty-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    _publish(task_id, ids["tenant_id"])
    _seed_verdict(
        ids["tenant_id"], ids["ingress_id"], ids["event_id"], status="pending"
    )
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
            cur.execute(
                "UPDATE public.b23_match_verdicts SET status = 'matched_confirmed'"
                " WHERE tenant_id = %s AND webhook_ingress_identity_id = %s",
                (str(ids["tenant_id"]), str(ids["ingress_id"])),
            )
            cur.execute(
                "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                (task_id, SCOPE_HEX, 1, _P2_POLICY_SEMANTIC_SHA_V2),
            )
            cur.execute(
                "SELECT public.b26_p2_mark_conducted(%s)", (task_id,)
            )
            assert cur.fetchone()[0] == "conducted"
    finally:
        conn.close()


def test_vi_worker_operational_reads() -> None:
    """Operational reads are principal-agnostic: the worker observes the
    same stale/disposition/quarantine signal as every other consumer
    (read-only, RLS-confined, no authority)."""
    ids = _seed_ingress("worker-reads")
    task_id = f"vi-wreads-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task_id)
    import psycopg2

    conn = psycopg2.connect(_role_dsn("app_worker"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "SELECT count(*) FROM public.b26_p2_stale_unconducted(300)"
            )
            assert cur.fetchone()[0] >= 0
            cur.execute(
                "SELECT public.b26_p2_operational_disposition(%s)", (task_id,)
            )
            assert cur.fetchone()[0] == "PENDING_PUBLICATION"
            cur.execute(
                "SELECT count(*) FROM public.b26_p2_execution_quarantine"
            )
            assert cur.fetchone()[0] >= 0
    finally:
        conn.close()


def test_vi_single_channel_telemetry_never_hides() -> None:
    """H-VI-C03/C04 across principals: a lone FAILURE row (beat/relay/
    worker transport writes) or a lone DLQ row (issuer/worker DLQ
    writes) never suppresses the never-consumed signal. Only joint
    DLQ+FAILURE agreement is terminal -- and terminal stays counted."""
    ids = _seed_ingress("tele-1")
    import psycopg2

    admin = psycopg2.connect(_admin_dsn())
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            # Six aged published twins on six ingresses, one per
            # telemetry shape: relay-FAILURE-only, beat-FAILURE-only,
            # worker-FAILURE-only, user-DLQ-only, worker-DLQ-only, joint.
            # The stale law is writer-agnostic by construction (channel
            # agreement, never principal identity), and every
            # transport principal's reachable surface is exercised.
            tasks = {}
            for tag in ("rf", "bf", "wf", "ud", "wd", "j"):
                ingress = _seed_extra_ingress(ids["tenant_id"], f"tele-1-{tag}")
                task_id = f"vi-tele-{tag}-{uuid.uuid4().hex[:8]}"
                _seed_dispatch(ids["tenant_id"], ingress, task_id)
                tasks[tag] = (task_id, ingress)
    finally:
        admin.close()
    for tag, (task_id, ingress) in tasks.items():
        _publish(task_id, ids["tenant_id"])
        _age_anchor_admin(task_id, ids["tenant_id"], 400)

    def _inject_failure(dsn: str, task_id: str) -> None:
        import psycopg2 as _p

        conn = _p.connect(dsn)
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO public.celery_taskmeta (task_id, status,"
                    " date_done, traceback, name, worker)"
                    " VALUES (%s, 'FAILURE', now(), '', 'x', 'w')"
                    " ON CONFLICT (task_id) DO UPDATE SET status = 'FAILURE'",
                    (task_id,),
                )
        finally:
            conn.close()

    def _inject_dlq(dsn: str, task_id: str, tenant_id: UUID) -> None:
        import psycopg2 as _p

        conn = _p.connect(dsn)
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (str(tenant_id),),
                )
                cur.execute(
                    "INSERT INTO public.worker_failed_jobs (id, task_id,"
                    " task_name, tenant_id, error_type, exception_class,"
                    " error_message, status)"
                    " VALUES (%s, %s, %s, %s, 't', 'c', 'm', 'pending')",
                    (str(uuid.uuid4()), task_id, TASK_NAME, str(tenant_id)),
                )
        finally:
            conn.close()

    # Single-channel shapes across every reachable writer: still stale.
    _inject_failure(_role_dsn("app_relay"), tasks["rf"][0])
    _inject_failure(_role_dsn("app_beat"), tasks["bf"][0])
    _inject_failure(_role_dsn("app_worker"), tasks["wf"][0])
    _inject_dlq(_role_dsn("app_user"), tasks["ud"][0], ids["tenant_id"])
    _inject_dlq(_role_dsn("app_worker"), tasks["wd"][0], ids["tenant_id"])
    # Joint agreement on the third twin (owner-seeded: the issuer holds
    # no result-backend writes under VI law): terminal, still counted.
    import psycopg2 as _pg

    admin2 = _pg.connect(_admin_dsn())
    admin2.autocommit = True
    try:
        with admin2.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "INSERT INTO public.celery_taskmeta (task_id, status,"
                " date_done, traceback, name, worker)"
                " VALUES (%s, 'FAILURE', now(), '', 'x', 'w')"
                " ON CONFLICT (task_id) DO UPDATE SET status = 'FAILURE'",
                (tasks["j"][0],),
            )
            cur.execute(
                "INSERT INTO public.worker_failed_jobs (id, task_id, task_name,"
                " tenant_id, error_type, exception_class, error_message, status)"
                " VALUES (%s, %s, %s, %s, 't', 'c', 'm', 'pending')",
                (
                    str(uuid.uuid4()),
                    tasks["j"][0],
                    TASK_NAME,
                    str(ids["tenant_id"]),
                ),
            )
    finally:
        admin2.close()
    conn = psycopg2.connect(_role_dsn("app_user"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            for tag in ("rf", "bf", "wf", "ud", "wd"):
                cur.execute(
                    "SELECT public.b26_p2_operational_disposition(%s)",
                    (tasks[tag][0],),
                )
                assert cur.fetchone()[0] == "STALE_UNCONDUCTED", tag
            cur.execute(
                "SELECT public.b26_p2_operational_disposition(%s)",
                (tasks["j"][0],),
            )
            assert cur.fetchone()[0] == "TERMINAL_FAILURE_ACTIONABLE"
            # DLQ status edits are monotonic: resolving the DLQ row does
            # not un-terminalize the execution (EXISTS-based law).
            cur.execute(
                "UPDATE public.worker_failed_jobs SET status = 'resolved'"
                " WHERE task_id = %s",
                (tasks["j"][0],),
            )
            cur.execute(
                "SELECT public.b26_p2_operational_disposition(%s)",
                (tasks["j"][0],),
            )
            assert cur.fetchone()[0] == "TERMINAL_FAILURE_ACTIONABLE"
            # DLQ retargeting moves terminality between visible states but
            # never hides: the issuer repoints its DLQ-only row at the
            # relay-FAILURE-only twin (which becomes terminal-counted)
            # while its own twin stays stale (FAILURE-less).
            cur.execute(
                "UPDATE public.worker_failed_jobs SET task_id = %s"
                " WHERE task_id = %s",
                (tasks["rf"][0], tasks["ud"][0]),
            )
            cur.execute(
                "SELECT public.b26_p2_operational_disposition(%s)",
                (tasks["rf"][0],),
            )
            assert cur.fetchone()[0] == "TERMINAL_FAILURE_ACTIONABLE"
            cur.execute(
                "SELECT public.b26_p2_operational_disposition(%s)",
                (tasks["ud"][0],),
            )
            assert cur.fetchone()[0] == "STALE_UNCONDUCTED"
    finally:
        conn.close()
    # Same retarget through the worker credential on its own DLQ row:
    # the worker-FAILURE-only twin terminalizes, the worker-DLQ-only
    # twin stays stale. No principal can retarget into invisibility.
    wconn = psycopg2.connect(_role_dsn("app_worker"))
    wconn.autocommit = True
    try:
        with wconn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "UPDATE public.worker_failed_jobs SET task_id = %s"
                " WHERE task_id = %s",
                (tasks["wf"][0], tasks["wd"][0]),
            )
            cur.execute(
                "SELECT public.b26_p2_operational_disposition(%s)",
                (tasks["wf"][0],),
            )
            assert cur.fetchone()[0] == "TERMINAL_FAILURE_ACTIONABLE"
            cur.execute(
                "SELECT public.b26_p2_operational_disposition(%s)",
                (tasks["wd"][0],),
            )
            assert cur.fetchone()[0] == "STALE_UNCONDUCTED"
    finally:
        wconn.close()
