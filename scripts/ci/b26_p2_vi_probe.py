#!/usr/bin/env python3
"""B2.6-P2 Corrective VI physics probe (auditor-style, exact principals).

Exercises the VI laws against a live migration-built database using only
the runtime credentials (plus owner for setup/teardown only). Exits
nonzero on the first violated expectation. Used for implementation
verification and as the seed vocabulary for the blind round (which must
use NEW primitives, not these).
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone

DAY = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
WS = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)
WE = datetime(2026, 1, 16, 0, 0, tzinfo=timezone.utc)
WRONG_WS = datetime(2026, 1, 20, 0, 0, tzinfo=timezone.utc)
WRONG_WE = datetime(2026, 1, 21, 0, 0, tzinfo=timezone.utc)
TASK_NAME = "app.tasks.revenue_verification.execute_b23_batch_match_engine"

PASS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if not cond:
        print(f"FAIL:{name} {detail}")
        sys.exit(1)
    PASS.append(name)
    print(f"ok:{name}")


def _conn(dsn: str, role: str | None = None):
    import psycopg2

    if role is None:
        return psycopg2.connect(dsn)
    admin = dsn
    cand = admin.replace("migration_owner:migration_owner", f"{role}:{role}")
    c = psycopg2.connect(cand)
    c.autocommit = True
    return c


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-dsn", required=True)
    args = parser.parse_args()
    import psycopg2

    admin_dsn = args.admin_dsn
    setup = psycopg2.connect(admin_dsn)
    setup.autocommit = True
    tenant = str(uuid.uuid4())
    ingress = str(uuid.uuid4())
    event_uuid = str(uuid.uuid4())
    ingress2 = str(uuid.uuid4())
    event_uuid2 = str(uuid.uuid4())
    ingress3 = str(uuid.uuid4())
    event_uuid3 = str(uuid.uuid4())
    ingress4 = str(uuid.uuid4())
    event_uuid4 = str(uuid.uuid4())
    with setup.cursor() as cur:
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
            " VALUES (%s, %s, %s, %s)",
            (tenant, f"vi-{tenant[:8]}", uuid.uuid4().hex, "vi@example.invalid"),
        )
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES ('vi_channel', 'vi',"
            " true, 'VI', 'active') ON CONFLICT (code) DO NOTHING"
        )
        cur.execute(
            "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
            " correlation_id, session_id, revenue_cents, raw_payload,"
            " idempotency_key, event_type, channel, campaign_id,"
            " conversion_value_cents, currency, event_timestamp, processed_at,"
            " processing_status) VALUES (%s, %s, %s, %s, %s, 38000,"
            " '{\"order_id\": \"vi\"}'::jsonb, %s, 'conversion', 'vi_channel',"
            " 'vi-campaign', 38000, 'USD', %s, %s, 'processed')",
            (event_uuid, tenant, DAY, str(uuid.uuid4()), str(uuid.uuid4()),
             f"vi:{tenant[:8]}", DAY, DAY),
        )
        cur.execute(
            "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
            " correlation_id, session_id, revenue_cents, raw_payload,"
            " idempotency_key, event_type, channel, campaign_id,"
            " conversion_value_cents, currency, event_timestamp, processed_at,"
            " processing_status) VALUES (%s, %s, %s, %s, %s, 38000,"
            " '{\"order_id\": \"vi2\"}'::jsonb, %s, 'conversion', 'vi_channel',"
            " 'vi-campaign', 38000, 'USD', %s, %s, 'processed')",
            (event_uuid2, tenant, DAY, str(uuid.uuid4()), str(uuid.uuid4()),
             f"vi2:{tenant[:8]}", DAY, DAY),
        )
        cur.execute(
            "INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id,"
            " provider, provider_native_event_reference,"
            " provider_native_commerce_reference,"
            " normalized_commerce_reference_kind,"
            " normalized_commerce_reference_value, verified_amount_minor,"
            " verified_amount_currency, event_timestamp, idempotency_key,"
            " verified_commerce_ingress_state)"
            " VALUES (%s, %s, %s, 'stripe', %s, %s, 'order_reference',"
            " %s, 38000, 'USD', %s, %s, 'authenticity_verified')",
            (ingress, tenant, event_uuid, f"evt-{tenant[:8]}",
             f"ord-{tenant[:8]}", f"ord-{tenant[:8]}", DAY, f"vi:{tenant[:8]}"),
        )
        cur.execute(
            "INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id,"
            " provider, provider_native_event_reference,"
            " provider_native_commerce_reference,"
            " normalized_commerce_reference_kind,"
            " normalized_commerce_reference_value, verified_amount_minor,"
            " verified_amount_currency, event_timestamp, idempotency_key,"
            " verified_commerce_ingress_state)"
            " VALUES (%s, %s, %s, 'stripe', %s, %s, 'order_reference',"
            " %s, 38000, 'USD', %s, %s, 'authenticity_verified')",
            (ingress2, tenant, event_uuid2, f"evt2-{tenant[:8]}",
             f"ord2-{tenant[:8]}", f"ord2-{tenant[:8]}", DAY, f"vi2:{tenant[:8]}"),
        )
        cur.execute(
            "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
            " correlation_id, session_id, revenue_cents, raw_payload,"
            " idempotency_key, event_type, channel, campaign_id,"
            " conversion_value_cents, currency, event_timestamp, processed_at,"
            " processing_status) VALUES (%s, %s, %s, %s, %s, 38000,"
            " '{\"order_id\": \"vi3\"}'::jsonb, %s, 'conversion', 'vi_channel',"
            " 'vi-campaign', 38000, 'USD', %s, %s, 'processed')",
            (event_uuid3, tenant, DAY, str(uuid.uuid4()), str(uuid.uuid4()),
             f"vi3:{tenant[:8]}", DAY, DAY),
        )
        cur.execute(
            "INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id,"
            " provider, provider_native_event_reference,"
            " provider_native_commerce_reference,"
            " normalized_commerce_reference_kind,"
            " normalized_commerce_reference_value, verified_amount_minor,"
            " verified_amount_currency, event_timestamp, idempotency_key,"
            " verified_commerce_ingress_state)"
            " VALUES (%s, %s, %s, 'stripe', %s, %s, 'order_reference',"
            " %s, 38000, 'USD', %s, %s, 'authenticity_verified')",
            (ingress3, tenant, event_uuid3, f"evt3-{tenant[:8]}",
             f"ord3-{tenant[:8]}", f"ord3-{tenant[:8]}", DAY, f"vi3:{tenant[:8]}"),
        )
        cur.execute(
            "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
            " correlation_id, session_id, revenue_cents, raw_payload,"
            " idempotency_key, event_type, channel, campaign_id,"
            " conversion_value_cents, currency, event_timestamp, processed_at,"
            " processing_status) VALUES (%s, %s, %s, %s, %s, 38000,"
            " '{\"order_id\": \"vi4\"}'::jsonb, %s, 'conversion', 'vi_channel',"
            " 'vi-campaign', 38000, 'USD', %s, %s, 'processed')",
            (event_uuid4, tenant, DAY, str(uuid.uuid4()), str(uuid.uuid4()),
             f"vi4:{tenant[:8]}", DAY, DAY),
        )
        cur.execute(
            "INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id,"
            " provider, provider_native_event_reference,"
            " provider_native_commerce_reference,"
            " normalized_commerce_reference_kind,"
            " normalized_commerce_reference_value, verified_amount_minor,"
            " verified_amount_currency, event_timestamp, idempotency_key,"
            " verified_commerce_ingress_state)"
            " VALUES (%s, %s, %s, 'stripe', %s, %s, 'order_reference',"
            " %s, 38000, 'USD', %s, %s, 'authenticity_verified')",
            (ingress4, tenant, event_uuid4, f"evt4-{tenant[:8]}",
             f"ord4-{tenant[:8]}", f"ord4-{tenant[:8]}", DAY, f"vi4:{tenant[:8]}"),
        )
    setup.close()

    user = _conn(admin_dsn, "app_user")
    worker = _conn(admin_dsn, "app_worker")

    def ucur():
        cur = user.cursor()
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        return cur

    # R6-01: lawful dispatch accepted as app_user.
    task = f"vi-lawful-{uuid.uuid4().hex[:8]}"
    with ucur() as cur:
        cur.execute(
            "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
            " webhook_ingress_identity_id, task_id, task_name, queue, routing_key,"
            " correlation_id, provider, provider_native_event_reference,"
            " provider_native_commerce_reference,"
            " normalized_commerce_reference_value, window_start, window_end)"
            " VALUES (%s, %s, %s, %s, 'b23_match_engine', 'b23_match_engine.task',"
            " %s, 'stripe', %s, %s, %s, %s, %s)",
            (tenant, ingress, task, TASK_NAME, str(uuid.uuid4()),
             f"evt-{tenant[:8]}", f"ord-{tenant[:8]}", f"ord-{tenant[:8]}", WS, WE),
        )
        cur.execute(
            "INSERT INTO public.b26_p2_execution_outbox (tenant_id, dispatch_task_id,"
            " webhook_ingress_identity_id) VALUES (%s, %s, %s)",
            (tenant, task, ingress),
        )
        cur.execute(
            "INSERT INTO public.b26_p2_task_authority_directory (task_id, tenant_id,"
            " webhook_ingress_identity_id, window_start, window_end)"
            " VALUES (%s, %s, %s, %s, %s)",
            (task, tenant, ingress, WS, WE),
        )
    check("R6-01 lawful dispatch accepted", True)

    # R6-03: wrong UTC day refused as app_user.
    try:
        with ucur() as cur:
            cur.execute(
                "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                " webhook_ingress_identity_id, task_id, task_name, queue, routing_key,"
                " correlation_id, provider, provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_value, window_start, window_end)"
                " VALUES (%s, %s, %s, %s, 'b23_match_engine', 'b23_match_engine.task',"
                " %s, 'stripe', %s, %s, %s, %s, %s)",
                (tenant, ingress, f"vi-forged-{uuid.uuid4().hex[:8]}", TASK_NAME,
                 str(uuid.uuid4()), f"evt-{tenant[:8]}", f"ord-{tenant[:8]}",
                 f"ord-{tenant[:8]}", WRONG_WS, WRONG_WE),
            )
        check("R6-03 wrong UTC day refused", False, "forged dispatch ACCEPTED")
    except (psycopg2.errors.RaiseException, psycopg2.errors.InsufficientPrivilege) as exc:
        check("R6-03 wrong UTC day refused", "not_sovereign" in str(exc))
    user.rollback()

    # R6-04: 12-hour window refused.
    try:
        with ucur() as cur:
            cur.execute(
                "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                " webhook_ingress_identity_id, task_id, task_name, queue, routing_key,"
                " correlation_id, provider, provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_value, window_start, window_end)"
                " VALUES (%s, %s, %s, %s, 'b23_match_engine', 'b23_match_engine.task',"
                " %s, 'stripe', %s, %s, %s, %s, %s)",
                (tenant, ingress, f"vi-12h-{uuid.uuid4().hex[:8]}", TASK_NAME,
                 str(uuid.uuid4()), f"evt-{tenant[:8]}", f"ord-{tenant[:8]}",
                 f"ord-{tenant[:8]}",
                 datetime(2026, 1, 15, 6, 0, tzinfo=timezone.utc),
                 datetime(2026, 1, 15, 18, 0, tzinfo=timezone.utc)),
            )
        check("R6-04 12-hour window refused", False, "ACCEPTED")
    except (psycopg2.errors.RaiseException, psycopg2.errors.InsufficientPrivilege) as exc:
        check("R6-04 12-hour window refused", "not_sovereign" in str(exc))
    user.rollback()

    # R6-07: ingress clock mutation refused after D exists.
    try:
        with ucur() as cur:
            cur.execute(
                "UPDATE public.webhook_ingress_identities SET event_timestamp = %s"
                " WHERE id = %s",
                (datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc), ingress),
            )
        check("R6-07 ingress clock immutable", False, "mutation ACCEPTED")
    except (psycopg2.errors.RaiseException, psycopg2.errors.InsufficientPrivilege) as exc:
        check("R6-07 ingress clock immutable", "immutable" in str(exc))
    user.rollback()

    # R6-13: ingress delete refused after D exists (defense in depth:
    # app_user holds no DELETE grant at all; the custody trigger is the
    # second boundary, proven below as the owner with a tenant GUC).
    try:
        with ucur() as cur:
            cur.execute(
                "DELETE FROM public.webhook_ingress_identities WHERE id = %s",
                (ingress,),
            )
        check("R6-13 ingress delete refused", False, "delete ACCEPTED")
    except (psycopg2.errors.RaiseException, psycopg2.errors.InsufficientPrivilege):
        check("R6-13 ingress delete refused", True)
    user.rollback()
    _owner = psycopg2.connect(admin_dsn)
    _owner.autocommit = True
    try:
        with _owner.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            cur.execute(
                "DELETE FROM public.webhook_ingress_identities WHERE id = %s",
                (ingress,),
            )
        check("R6-13 custody trigger fires for owner", False, "delete ACCEPTED")
    except (psycopg2.errors.RaiseException, psycopg2.errors.InsufficientPrivilege) as exc:
        check("R6-13 custody trigger fires for owner", "delete_refused" in str(exc), str(exc)[:200])
    finally:
        _owner.close()

    # Resolver returns canonical window for lawful task.
    with ucur() as cur:
        cur.execute(
            "SELECT window_start, window_end FROM"
            " public.b26_p2_resolve_dispatch_authority(%s)",
            (task,),
        )
        row = cur.fetchone()
    check("resolver returns canonical", row[0] == WS and row[1] == WE, str(row))

    # CP6-04: worker direct receipt INSERT refused.
    try:
        wcur = worker.cursor()
        wcur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        wcur.execute(
            "INSERT INTO public.b26_p2_conduction_receipts (task_id, tenant_id,"
            " webhook_ingress_identity_id, window_start, window_end,"
            " b23_processed_count, p2_scope_identity)"
            " VALUES (%s, %s, %s, %s, %s, 0, %s)",
            (task, tenant, ingress, WS, WE, "f" * 64),
        )
        check("CP6-04 worker direct receipt refused", False, "INSERT ACCEPTED")
    except psycopg2.errors.InsufficientPrivilege:
        check("CP6-04 worker direct receipt refused", True)
    worker.rollback()

    # Record function: bad scope refused, good scope accepted.
    try:
        wcur = worker.cursor()
        wcur.execute(
            "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s)",
            (task, "SYNTHETIC-FORGED-SCOPE", 1),
        )
        check("record refuses junk scope", False, "ACCEPTED")
    except (psycopg2.errors.RaiseException, psycopg2.errors.InsufficientPrivilege) as exc:
        check("record refuses junk scope", "scope_not_bound" in str(exc))
    worker.rollback()
    wcur = worker.cursor()
    wcur.execute(
        "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s)",
        (task, "a" * 64, 1),
    )
    check("record accepts well-formed scope", True)
    worker.commit()

    # Publish twins (relay-shaped writes as the owner acting for the test).
    _pub = psycopg2.connect(admin_dsn)
    _pub.autocommit = True
    with _pub.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "UPDATE public.b23_match_task_dispatches SET delivery_state='published'"
            " WHERE task_id=%s",
            (task,),
        )
        cur.execute(
            "UPDATE public.b26_p2_execution_outbox SET state='published'"
            " WHERE dispatch_task_id=%s",
            (task,),
        )
    _pub.close()

    # Gate without B2.3 refuses (narrow prerequisite).
    try:
        wcur = worker.cursor()
        wcur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task,))
        check("gate refuses without B2.3", False, f"returned {wcur.fetchone()}")
    except (psycopg2.errors.RaiseException, psycopg2.errors.InsufficientPrivilege) as exc:
        check("gate refuses without B2.3", "no_b23_consequence" in str(exc))
    worker.rollback()

    # Seed a pending verdict -> gate must still refuse (narrow status law).
    setup2 = psycopg2.connect(admin_dsn)
    setup2.autocommit = True
    with setup2.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "INSERT INTO public.b23_match_verdicts (tenant_id, attribution_event_id,"
            " webhook_ingress_identity_id, provider, canonical_commerce_reference,"
            " provider_native_event_reference, provider_native_commerce_reference,"
            " status, match_quality, attributed_amount_minor, verified_amount_minor,"
            " currency_code, canonical_expected_gross_amount_minor,"
            " canonical_captured_gross_amount_minor,"
            " canonical_net_verified_amount_minor, discrepancy_amount_minor,"
            " discrepancy_ratio_bps, discrepancy_band)"
            " VALUES (%s, %s, %s, 'stripe', %s, %s, %s,"
            " 'pending', 'high', 38000, 38000, 'USD', 38000, 38000, 38000, 0, 0, 'exact')",
            (tenant, event_uuid, ingress, f"ord-{tenant[:8]}", f"evt-{tenant[:8]}",
             f"ord-{tenant[:8]}"),
        )
    setup2.close()
    try:
        wcur = worker.cursor()
        wcur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task,))
        check("gate refuses pending verdict", False, "CONDUCTED on pending")
    except (psycopg2.errors.RaiseException, psycopg2.errors.InsufficientPrivilege) as exc:
        check("gate refuses pending verdict", "no_b23_consequence" in str(exc))
    worker.rollback()

    # Promote verdict to matched_confirmed + publish twins -> gate conducts.
    setup3 = psycopg2.connect(admin_dsn)
    setup3.autocommit = True
    with setup3.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "UPDATE public.b23_match_verdicts SET status='matched_confirmed'"
            " WHERE tenant_id=%s AND webhook_ingress_identity_id=%s",
            (tenant, ingress),
        )
        cur.execute(
            "UPDATE public.b23_match_task_dispatches SET delivery_state='published'"
            " WHERE task_id=%s",
            (task,),
        )
        cur.execute(
            "UPDATE public.b26_p2_execution_outbox SET state='published'"
            " WHERE dispatch_task_id=%s",
            (task,),
        )
        cur.execute(
            "SELECT first_published_at FROM public.b23_match_task_dispatches"
            " WHERE task_id=%s",
            (task,),
        )
        anchor = cur.fetchone()[0]
    setup3.close()
    check("anchor set at publish", anchor is not None, str(anchor))
    wcur = worker.cursor()
    wcur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task,))
    check("gate conducts lawful", wcur.fetchone()[0] == "conducted")
    worker.commit()

    # OD: immutable anchor survives metadata bumps (use second task).
    task2 = f"vi-stale-{uuid.uuid4().hex[:8]}"
    # Lawful issuance shape (pending), lawful relay publish (anchor=now
    # by trigger law), then an administrator ages the anchor through a
    # governed trigger park (migration authority only -- runtime cannot).
    with ucur() as cur:
        cur.execute(
            "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
            " webhook_ingress_identity_id, task_id, task_name, queue, routing_key,"
            " correlation_id, provider, provider_native_event_reference,"
            " provider_native_commerce_reference,"
            " normalized_commerce_reference_value, window_start, window_end)"
            " VALUES (%s, %s, %s, %s, 'b23_match_engine', 'b23_match_engine.task',"
            " %s, 'stripe', %s, %s, %s, %s, %s)",
            (tenant, ingress2, task2, TASK_NAME, str(uuid.uuid4()),
             f"evt2-{tenant[:8]}", f"ord2-{tenant[:8]}", f"ord2-{tenant[:8]}", WS, WE),
        )
        cur.execute(
            "INSERT INTO public.b26_p2_execution_outbox (tenant_id, dispatch_task_id,"
            " webhook_ingress_identity_id) VALUES (%s, %s, %s)",
            (tenant, task2, ingress2),
        )
        cur.execute(
            "INSERT INTO public.b26_p2_task_authority_directory (task_id, tenant_id,"
            " webhook_ingress_identity_id, window_start, window_end)"
            " VALUES (%s, %s, %s, %s, %s)",
            (task2, tenant, ingress2, WS, WE),
        )
    _admin = psycopg2.connect(admin_dsn)
    _admin.autocommit = True
    with _admin.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "UPDATE public.b23_match_task_dispatches SET delivery_state='published'"
            " WHERE task_id=%s",
            (task2,),
        )
        cur.execute(
            "UPDATE public.b26_p2_execution_outbox SET state='published'"
            " WHERE dispatch_task_id=%s",
            (task2,),
        )
        cur.execute(
            "SELECT first_published_at FROM public.b23_match_task_dispatches"
            " WHERE task_id=%s",
            (task2,),
        )
        anchor2 = cur.fetchone()[0]
    check("anchor set at publish", anchor2 is not None, str(anchor2))
    with _admin.cursor() as cur:
        cur.execute(
            "ALTER TABLE public.b23_match_task_dispatches"
            " DISABLE TRIGGER trg_b26_p2_dispatch_immutability"
        )
        cur.execute(
            "UPDATE public.b23_match_task_dispatches SET first_published_at ="
            " now() - interval '400 seconds' WHERE task_id=%s",
            (task2,),
        )
        cur.execute(
            "ALTER TABLE public.b23_match_task_dispatches"
            " ENABLE TRIGGER trg_b26_p2_dispatch_immutability"
        )
    _admin.close()
    # Administrator parked the trigger above (migration authority only);
    # runtime must not be able to move the anchor.
    try:
        with ucur() as cur:
            cur.execute(
                "UPDATE public.b23_match_task_dispatches SET first_published_at = now()"
                " WHERE task_id=%s",
                (task2,),
            )
        check("anchor immutable to runtime", False, "anchor moved")
    except psycopg2.errors.InsufficientPrivilege:
        check("anchor immutable to runtime", True)
    user.rollback()
    # Caller-authored future anchor at INSERT is overridden (server law):
    # publication anchors at now(), never at a caller-supplied instant.
    task_anc = f"vi-anchor-{uuid.uuid4().hex[:8]}"
    with ucur() as cur:
        cur.execute(
            "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
            " webhook_ingress_identity_id, task_id, task_name, queue, routing_key,"
            " correlation_id, provider, provider_native_event_reference,"
            " provider_native_commerce_reference,"
            " normalized_commerce_reference_value, window_start, window_end,"
            " delivery_state, first_published_at)"
            " VALUES (%s, %s, %s, %s, 'b23_match_engine', 'b23_match_engine.task',"
            " %s, 'stripe', %s, %s, %s, %s, %s,"
            " 'published', now() + interval '30 days')",
            (tenant, ingress4, task_anc, TASK_NAME, str(uuid.uuid4()),
             f"evt4-{tenant[:8]}", f"ord4-{tenant[:8]}", f"ord4-{tenant[:8]}", WS, WE),
        )
        cur.execute(
            "SELECT first_published_at FROM public.b23_match_task_dispatches"
            " WHERE task_id=%s",
            (task_anc,),
        )
        anc = cur.fetchone()[0]
    check(
        "future anchor overridden at INSERT",
        anc is not None
        and abs((anc - datetime.now(timezone.utc)).total_seconds()) < 120,
        str(anc),
    )
    # Lawful metadata bump must not move the anchor clock.
    with ucur() as cur:
        cur.execute(
            "UPDATE public.b23_match_task_dispatches"
            " SET publish_attempts = publish_attempts + 1,"
            " last_publish_error = 'retry-note' WHERE task_id=%s",
            (task2,),
        )
        cur.execute(
            "SELECT first_published_at FROM public.b23_match_task_dispatches"
            " WHERE task_id=%s",
            (task2,),
        )
        anchor3 = cur.fetchone()[0]
    check("metadata bump keeps anchor", anchor3 is not None)
    with ucur() as cur:
        cur.execute("SELECT count(*) FROM public.b26_p2_stale_unconducted(300)", ())
        n = cur.fetchone()[0]
    check("aged execution stays stale after bump", n >= 1, f"stale={n}")

    # Absurd threshold refuses instead of suppressing.
    try:
        with ucur() as cur:
            cur.execute("SELECT count(*) FROM public.b26_p2_stale_unconducted(9999999)")
            cur.fetchone()
        check("absurd threshold refused", False, "suppressed silently")
    except (psycopg2.errors.RaiseException, psycopg2.errors.InsufficientPrivilege) as exc:
        check("absurd threshold refused", "out_of_bounds" in str(exc))
    user.rollback()

    # FAILURE without DLQ stays visible; FAILURE+DLQ excluded.
    setup5 = psycopg2.connect(admin_dsn)
    setup5.autocommit = True
    with setup5.cursor() as cur:
        cur.execute(
            "INSERT INTO public.celery_taskmeta (task_id, status, date_done,"
            " traceback, name, worker)"
            " VALUES (%s, 'FAILURE', now(), '', 'x', 'w')"
            " ON CONFLICT (task_id) DO UPDATE SET status='FAILURE'",
            (task2,),
        )
    setup5.close()
    with ucur() as cur:
        cur.execute("SELECT count(*) FROM public.b26_p2_stale_unconducted(300)")
        n_nodlq = cur.fetchone()[0]
    check("FAILURE without DLQ stays stale", n_nodlq >= 1, f"stale={n_nodlq}")
    setup6 = psycopg2.connect(admin_dsn)
    setup6.autocommit = True
    with setup6.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "INSERT INTO public.worker_failed_jobs (id, task_id, task_name, tenant_id,"
            " error_type, exception_class, error_message, status)"
            " VALUES (%s, %s, %s, %s, 't', 'c', 'm', 'pending')",
            (str(uuid.uuid4()), task2, TASK_NAME, tenant),
        )
    setup6.close()
    with ucur() as cur:
        cur.execute("SELECT count(*) FROM public.b26_p2_stale_unconducted(300)")
        n_dlq = cur.fetchone()[0]
    check("FAILURE+DLQ terminal excluded", n_dlq == n_nodlq - 1, f"{n_nodlq}->{n_dlq}")

    # Disposition totality incl. zombie.
    task3 = f"vi-zombie-{uuid.uuid4().hex[:8]}"
    with ucur() as cur:
        cur.execute(
            "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
            " webhook_ingress_identity_id, task_id, task_name, queue, routing_key,"
            " correlation_id, provider, provider_native_event_reference,"
            " provider_native_commerce_reference,"
            " normalized_commerce_reference_value, window_start, window_end)"
            " VALUES (%s, %s, %s, %s, 'b23_match_engine', 'b23_match_engine.task',"
            " %s, 'stripe', %s, %s, %s, %s, %s)",
            (tenant, ingress3, task3, TASK_NAME, str(uuid.uuid4()),
             f"evt3-{tenant[:8]}", f"ord3-{tenant[:8]}", f"ord3-{tenant[:8]}", WS, WE),
        )
        cur.execute(
            "INSERT INTO public.b26_p2_task_authority_directory (task_id, tenant_id,"
            " webhook_ingress_identity_id, window_start, window_end)"
            " VALUES (%s, %s, %s, %s, %s)",
            (task3, tenant, ingress3, WS, WE),
        )
        cur.execute(
            "SELECT public.b26_p2_operational_disposition(%s)", (task3,)
        )
        disp = cur.fetchone()[0]
    check("zombie disposition actionable", disp == "MISSING_CHILD_ACTIONABLE", disp)
    with ucur() as cur:
        cur.execute("SELECT public.b26_p2_operational_disposition(%s)", (task,))
        check("conducted disposition", cur.fetchone()[0] == "CONDUCTED")
        cur.execute("SELECT public.b26_p2_operational_disposition(%s)", (task2,))
        d2 = cur.fetchone()[0]
    check("stale/terminal disposition", d2 in ("STALE_UNCONDUCTED", "TERMINAL_FAILURE_ACTIONABLE"), d2)
    with ucur() as cur:
        cur.execute(
            "SELECT public.b26_p2_operational_disposition(%s)", ("no-such-task",)
        )
        check("unknown disposition explicit", cur.fetchone()[0] == "NOT_ACCEPTED")

    user.close()
    worker.close()
    print(f"VI_PROBE_PASS cells={len(PASS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
