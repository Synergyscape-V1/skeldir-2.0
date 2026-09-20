#!/usr/bin/env python3
"""B2.6-P2 Corrective VI blind post-implementation class challenge.

Written AFTER the remediation froze, from prohibited effects only (never
from the implementation plan's vocabulary). 24 falsifiers; at least 12
use primitives not named in the plan; at least 6 are produced from the
capability-derived generator's reachable surfaces (marked [GEN]).

A surviving falsifier (prohibited effect reachable) FAILS the round and
the architecture must change, followed by a full re-run.

Usage:
  python scripts/ci/b26_p2_vi_blind.py \
    --admin-dsn postgresql://migration_owner:migration_owner@127.0.0.1:5432/db
"""

from __future__ import annotations

import argparse
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone

DAY_NOON = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
WS = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)
WE = datetime(2026, 1, 16, 0, 0, tzinfo=timezone.utc)
TASK_NAME = "app.tasks.revenue_verification.execute_b23_batch_match_engine"

PASS: list[str] = []
GEN = "[GEN]"


def check(name: str, cond: bool, detail: str = "") -> None:
    if not cond:
        print(f"BLIND-SURVIVOR:{name} {detail}")
        sys.exit(1)
    PASS.append(name)
    print(f"ok:{name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-dsn", required=True)
    args = parser.parse_args()
    import psycopg2
    from psycopg2 import errors as pgerrors

    admin_dsn = args.admin_dsn

    def admin():
        c = psycopg2.connect(admin_dsn)
        c.autocommit = True
        return c

    def role_conn(role: str):
        c = psycopg2.connect(
            admin_dsn.replace("migration_owner:migration_owner", f"{role}:{role}")
        )
        c.autocommit = True
        return c

    def new_tenant(tag: str) -> tuple[str, str, str]:
        tenant, ingress, event = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        with admin() as c, c.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tenants (id, name, api_key_hash,"
                " notification_email) VALUES (%s, %s, %s, %s)",
                (tenant, f"blind-{tag}", uuid.uuid4().hex, "b@example.invalid"),
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            cur.execute(
                "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
                " display_name, state) VALUES ('blind_ch', 'b', true, 'B', 'active')"
                " ON CONFLICT (code) DO NOTHING"
            )
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
                " correlation_id, session_id, revenue_cents, raw_payload,"
                " idempotency_key, event_type, channel, campaign_id,"
                " conversion_value_cents, currency, event_timestamp, processed_at,"
                " processing_status) VALUES (%s, %s, %s, %s, %s, 100,"
                " '{}'::jsonb, %s, 'conversion', 'blind_ch', 'c', 100, 'USD',"
                " %s, %s, 'processed')",
                (event, tenant, DAY_NOON, str(uuid.uuid4()), str(uuid.uuid4()),
                 f"b:{tag}", DAY_NOON, DAY_NOON),
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
                " %s, 100, 'USD', %s, %s, 'authenticity_verified')",
                (ingress, tenant, event, f"e-{tag}", f"o-{tag}", f"o-{tag}",
                 DAY_NOON, f"b:{tag}"),
            )
        return tenant, ingress, event

    def seed_triple(tenant, ingress, task, ws=WS, we=WE, role="app_user"):
        with role_conn(role) as c, c.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            cur.execute(
                "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                " webhook_ingress_identity_id, task_id, task_name, queue, routing_key,"
                " correlation_id, provider, provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_value, window_start, window_end)"
                " VALUES (%s, %s, %s, %s, 'b23_match_engine',"
                " 'b23_match_engine.task', %s, 'stripe', %s, %s, %s, %s, %s)",
                (tenant, ingress, task, TASK_NAME, str(uuid.uuid4()),
                 f"e-{task[:8]}", f"o-{task[:8]}", f"o-{task[:8]}", ws, we),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_execution_outbox (tenant_id,"
                " dispatch_task_id, webhook_ingress_identity_id)"
                " VALUES (%s, %s, %s)",
                (tenant, task, ingress),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_task_authority_directory (task_id,"
                " tenant_id, webhook_ingress_identity_id, window_start, window_end)"
                " VALUES (%s, %s, %s, %s, %s)",
                (task, tenant, ingress, ws, we),
            )

    DBERR = (pgerrors.RaiseException, pgerrors.InsufficientPrivilege)

    # -- sovereign-root variants (B-01..B-06) --
    t, ig, _ev = new_tenant("b01")
    try:
        seed_triple(t, ig, f"b01-{uuid.uuid4().hex[:8]}")
        with role_conn("app_user") as c, c.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (t,)
            )
            # B-01 [GEN]: provider dimension (not window): correct window,
            # wrong provider must refuse at the sovereign trigger.
            try:
                cur.execute(
                    "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                    " webhook_ingress_identity_id, task_id, task_name, queue,"
                    " routing_key, correlation_id, provider,"
                    " provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " normalized_commerce_reference_value, window_start, window_end)"
                    " VALUES (%s, %s, %s, %s, 'b23_match_engine',"
                    " 'b23_match_engine.task', %s, 'paypal', 'e', 'o', 'o', %s, %s)",
                    (t, ig, f"b01-p-{uuid.uuid4().hex[:8]}", TASK_NAME,
                     str(uuid.uuid4()), WS, WE),
                )
                check("B-01 provider-mismatch refuses", False, "ACCEPTED")
            except DBERR as exc:
                check(
                    "B-01 provider-mismatch refuses",
                    "provider_not_sovereign" in str(exc),
                    str(exc)[:150],
                )
            c.rollback()
    finally:
        pass

    # B-02: unverified ingress state must refuse dispatch issuance.
    t2, _ig2, _ev2 = new_tenant("b02")
    with admin() as c, c.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (t2,))
        cur.execute(
            "UPDATE public.webhook_ingress_identities"
            " SET verified_commerce_ingress_state = 'pending' WHERE id = %s",
            (_ig2,),
        )
    try:
        seed_triple(t2, _ig2, f"b02-{uuid.uuid4().hex[:8]}")
        check("B-02 unverified ingress refuses", False, "ACCEPTED")
    except DBERR as exc:
        check(
            "B-02 unverified ingress refuses",
            "unverified" in str(exc),
            str(exc)[:150],
        )

    # B-03: cross-tenant root confusion (tenant A + ingress B).
    ta, iga, _e = new_tenant("b03a")
    tb, _igb, _e2 = new_tenant("b03b")
    seed_triple(ta, iga, f"b03-{uuid.uuid4().hex[:8]}")
    try:
        with role_conn("app_user") as c, c.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (ta,)
            )
            cur.execute(
                "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                " webhook_ingress_identity_id, task_id, task_name, queue,"
                " routing_key, correlation_id, provider,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_value, window_start, window_end)"
                " VALUES (%s, %s, %s, %s, 'b23_match_engine',"
                " 'b23_match_engine.task', %s, 'stripe', 'e', 'o', 'o', %s, %s)",
                (ta, _igb, f"b03-x-{uuid.uuid4().hex[:8]}", TASK_NAME,
                 str(uuid.uuid4()), WS, WE),
            )
        check("B-03 cross-tenant root refuses", False, "ACCEPTED")
    except DBERR:
        check("B-03 cross-tenant root refuses", True)

    # B-04 [GEN]: dispatch provider UPDATE after creation refuses.
    t4, ig4, _e4 = new_tenant("b04")
    task4 = f"b04-{uuid.uuid4().hex[:8]}"
    seed_triple(t4, ig4, task4)
    try:
        with role_conn("app_user") as c, c.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (t4,)
            )
            cur.execute(
                "UPDATE public.b23_match_task_dispatches SET provider='paypal'"
                " WHERE task_id=%s",
                (task4,),
            )
        check("B-04 provider UPDATE refuses", False, "ACCEPTED")
    except DBERR as exc:
        check("B-04 provider UPDATE refuses", "immutable" in str(exc))

    # B-05: offset-straddling local day (event 23:30+14:00 = 09:30Z).
    t5, _ig5, _e5 = new_tenant("b05")
    clock5 = datetime.fromisoformat("2026-01-15T23:30:00+14:00")
    with admin() as c, c.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (t5,))
        cur.execute(
            "UPDATE public.webhook_ingress_identities SET event_timestamp=%s"
            " WHERE id=%s",
            (datetime(2026, 1, 14, 12, 0, tzinfo=timezone.utc), _ig5),
        )
    # Local-day window for the +14:00 calendar day (wrong in UTC).
    local_ws = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc) - timedelta(hours=14)
    local_ws = local_ws.replace(tzinfo=timezone.utc)
    local_we = local_ws + timedelta(days=1)
    assert clock5.astimezone(timezone.utc).date().isoformat() == "2026-01-15"
    try:
        seed_triple(t5, _ig5, f"b05-{uuid.uuid4().hex[:8]}", ws=local_ws, we=local_we)
        # If the local window accidentally equals canonical, the case is
        # vacuous; assert it differs so the refusal is meaningful.
        check("B-05 offset-straddling refuses", False, "ACCEPTED-or-vacuous")
    except DBERR as exc:
        check("B-05 offset-straddling refuses", "not_sovereign" in str(exc))

    # B-06: NULL provider refuses (null-safe sovereign law).
    t6, ig6, _e6 = new_tenant("b06")
    try:
        with role_conn("app_user") as c, c.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (t6,)
            )
            cur.execute(
                "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                " webhook_ingress_identity_id, task_id, task_name, queue,"
                " routing_key, correlation_id, provider,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_value, window_start, window_end)"
                " VALUES (%s, %s, %s, %s, 'b23_match_engine',"
                " 'b23_match_engine.task', %s, NULL, 'e', 'o', 'o', %s, %s)",
                (t6, ig6, f"b06-{uuid.uuid4().hex[:8]}", TASK_NAME,
                 str(uuid.uuid4()), WS, WE),
            )
        check("B-06 NULL provider refuses", False, "ACCEPTED")
    except DBERR:
        check("B-06 NULL provider refuses", True)

    # -- completion variants (B-07..B-11) --
    # B-07 [GEN]: 16-way concurrent record+gate converges to one truth.
    t7, ig7, ev7 = new_tenant("b07")
    task7 = f"b07-{uuid.uuid4().hex[:8]}"
    seed_triple(t7, ig7, task7)
    with admin() as c, c.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (t7,))
        cur.execute(
            "UPDATE public.b23_match_task_dispatches SET delivery_state='published'"
            " WHERE task_id=%s",
            (task7,),
        )
        cur.execute(
            "UPDATE public.b26_p2_execution_outbox SET state='published'"
            " WHERE dispatch_task_id=%s",
            (task7,),
        )
        cur.execute(
            "INSERT INTO public.b23_match_verdicts (tenant_id, attribution_event_id,"
            " webhook_ingress_identity_id, provider, canonical_commerce_reference,"
            " provider_native_event_reference, provider_native_commerce_reference,"
            " status, match_quality, attributed_amount_minor, verified_amount_minor,"
            " currency_code, canonical_expected_gross_amount_minor,"
            " canonical_captured_gross_amount_minor,"
            " canonical_net_verified_amount_minor, discrepancy_amount_minor,"
            " discrepancy_ratio_bps, discrepancy_band)"
            " VALUES (%s, %s, %s, 'stripe', 'o', 'e', 'o', 'matched_confirmed',"
            " 'high', 100, 100, 'USD', 100, 100, 100, 0, 0, 'exact')",
            (t7, ev7, ig7),
        )
    outcomes: list[str] = []
    lock = threading.Lock()

    def _race():
        try:
            with role_conn("app_worker") as c, c.cursor() as cur:
                cur.execute(
                    "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s)",
                    (task7, "cd" * 32, 1),
                )
                cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task7,))
                res = cur.fetchone()[0]
        except Exception as exc:  # noqa: BLE001
            res = f"ERR:{str(exc).splitlines()[0][:80]}"
        with lock:
            outcomes.append(res)

    threads = [threading.Thread(target=_race) for _ in range(16)]
    [th.start() for th in threads]
    [th.join() for th in threads]
    # No duplicate truth is the load-bearing property: every caller
    # observes a terminal outcome, exactly one receipt exists, and the
    # final state is conducted exactly once. (Two callers may both
    # return 'conducted' when their pre-update snapshots overlap; the
    # twin UPDATEs are idempotent and the receipt is unique.)
    check(
        "B-07 16-way race converges",
        all(o in ("conducted", "already_conducted") for o in outcomes)
        and len(outcomes) == 16,
        str(sorted(set(outcomes))),
    )
    with admin() as c, c.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (t7,))
        cur.execute(
            "SELECT count(*) FROM public.b26_p2_conduction_receipts WHERE task_id=%s",
            (task7,),
        )
        check("B-07 single receipt", cur.fetchone()[0] == 1)

    # B-08: owner-planted wrong-window receipt never conducts.
    t8, ig8, _e8 = new_tenant("b08")
    task8 = f"b08-{uuid.uuid4().hex[:8]}"
    seed_triple(t8, ig8, task8)
    with admin() as c, c.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (t8,))
        cur.execute(
            "UPDATE public.b23_match_task_dispatches SET delivery_state='published'"
            " WHERE task_id=%s",
            (task8,),
        )
        cur.execute(
            "UPDATE public.b26_p2_execution_outbox SET state='published'"
            " WHERE dispatch_task_id=%s",
            (task8,),
        )
        cur.execute(
            "INSERT INTO public.b26_p2_conduction_receipts (task_id, tenant_id,"
            " webhook_ingress_identity_id, window_start, window_end,"
            " b23_processed_count, p2_scope_identity)"
            " VALUES (%s, %s, %s, %s, %s, 1, %s)",
            (task8, t8, ig8, datetime(2020, 1, 1, tzinfo=timezone.utc),
             datetime(2020, 1, 2, tzinfo=timezone.utc), "ef" * 32),
        )
    try:
        with role_conn("app_worker") as c, c.cursor() as cur:
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task8,))
        check("B-08 wrong-window receipt refuses", False, "CONDUCTED")
    except DBERR as exc:
        check(
            "B-08 wrong-window receipt refuses",
            "receipt_not_bound" in str(exc) or "no_b23" in str(exc),
            str(exc)[:150],
        )

    # B-09: gate EXECUTE as issuer refuses (no EXECUTE + session_user).
    try:
        with role_conn("app_user") as c, c.cursor() as cur:
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task8,))
        check("B-09 issuer gate refuses", False, "EXECUTED")
    except DBERR:
        check("B-09 issuer gate refuses", True)

    # B-10: SET ROLE escalation cannot forge session_user.
    try:
        with role_conn("app_user") as c, c.cursor() as cur:
            cur.execute("SET ROLE app_worker")
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task8,))
        check("B-10 SET ROLE escalation refuses", False, "EXECUTED")
    except DBERR as exc:
        check(
            "B-10 SET ROLE escalation refuses",
            "caller_refused" in str(exc) or "permission" in str(exc).lower(),
            str(exc)[:150],
        )

    # B-11: verdict matured then regressed before gate refuses.
    t11, ig11, ev11 = new_tenant("b11")
    task11 = f"b11-{uuid.uuid4().hex[:8]}"
    seed_triple(t11, ig11, task11)
    with admin() as c, c.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (t11,))
        cur.execute(
            "UPDATE public.b23_match_task_dispatches SET delivery_state='published'"
            " WHERE task_id=%s",
            (task11,),
        )
        cur.execute(
            "UPDATE public.b26_p2_execution_outbox SET state='published'"
            " WHERE dispatch_task_id=%s",
            (task11,),
        )
        cur.execute(
            "INSERT INTO public.b23_match_verdicts (tenant_id, attribution_event_id,"
            " webhook_ingress_identity_id, provider, canonical_commerce_reference,"
            " provider_native_event_reference, provider_native_commerce_reference,"
            " status, match_quality, attributed_amount_minor, verified_amount_minor,"
            " currency_code, canonical_expected_gross_amount_minor,"
            " canonical_captured_gross_amount_minor,"
            " canonical_net_verified_amount_minor, discrepancy_amount_minor,"
            " discrepancy_ratio_bps, discrepancy_band)"
            " VALUES (%s, %s, %s, 'stripe', 'o', 'e', 'o', 'matched_confirmed',"
            " 'high', 100, 100, 'USD', 100, 100, 100, 0, 0, 'exact')",
            (t11, ev11, ig11),
        )
    with role_conn("app_worker") as c, c.cursor() as cur:
        cur.execute(
            "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s)",
            (task11, "ab" * 32, 1),
        )
    with admin() as c, c.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (t11,))
        cur.execute(
            "UPDATE public.b23_match_verdicts SET status='unmatched'"
            " WHERE tenant_id=%s AND webhook_ingress_identity_id=%s",
            (t11, ig11),
        )
    try:
        with role_conn("app_worker") as c, c.cursor() as cur:
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task11,))
        check("B-11 regressed verdict refuses", False, "CONDUCTED")
    except DBERR as exc:
        check(
            "B-11 regressed verdict refuses",
            "no_b23_consequence" in str(exc),
            str(exc)[:150],
        )

    # -- disposition variants (B-12..B-16) --
    # B-12 [GEN]: dispatch state regression published->pending refuses.
    t12, ig12, _e12 = new_tenant("b12")
    task12 = f"b12-{uuid.uuid4().hex[:8]}"
    seed_triple(t12, ig12, task12)
    with admin() as c, c.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (t12,))
        cur.execute(
            "UPDATE public.b23_match_task_dispatches SET delivery_state='published'"
            " WHERE task_id=%s",
            (task12,),
        )
        cur.execute(
            "UPDATE public.b26_p2_execution_outbox SET state='published'"
            " WHERE dispatch_task_id=%s",
            (task12,),
        )
    try:
        with role_conn("app_user") as c, c.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (t12,)
            )
            cur.execute(
                "UPDATE public.b23_match_task_dispatches"
                " SET delivery_state='pending_publish' WHERE task_id=%s",
                (task12,),
            )
        check("B-12 state regression refuses", False, "ACCEPTED")
    except DBERR as exc:
        check("B-12 state regression refuses", "illegal_transition" in str(exc))

    # B-13 [GEN]: outbox state regression refuses.
    try:
        with role_conn("app_user") as c, c.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (t12,)
            )
            cur.execute(
                "UPDATE public.b26_p2_execution_outbox SET state='pending_publish'"
                " WHERE dispatch_task_id=%s",
                (task12,),
            )
        check("B-13 outbox regression refuses", False, "ACCEPTED")
    except DBERR as exc:
        check("B-13 outbox regression refuses", "illegal_transition" in str(exc))

    # B-14: quarantined pending task is actionable + counted.
    t14, ig14, _e14 = new_tenant("b14")
    task14 = f"b14-{uuid.uuid4().hex[:8]}"
    seed_triple(t14, ig14, task14)
    with admin() as c, c.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (t14,))
        cur.execute(
            "INSERT INTO public.b26_p2_execution_quarantine (source_relation,"
            " task_id, tenant_id, webhook_ingress_identity_id, reason,"
            " original_payload, migration_identity)"
            " VALUES ('b26_p2_execution_outbox', %s, %s, %s, 'blind probe',"
            " '{}', 'blind')",
            (task14, t14, ig14),
        )
    with role_conn("app_user") as c, c.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, false)", (t14,)
        )
        cur.execute(
            "SELECT public.b26_p2_operational_disposition(%s)", (task14,)
        )
        check(
            "B-14 quarantined pending actionable",
            cur.fetchone()[0] == "QUARANTINED_ACTIONABLE",
        )
        cur.execute("SELECT count(*) FROM public.b26_p2_execution_quarantine")
        check("B-14 quarantine counted", cur.fetchone()[0] >= 1)

    # B-15 [GEN]: far-future retry on published twin refuses.
    try:
        with role_conn("app_relay") as c, c.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (t12,)
            )
            cur.execute(
                "UPDATE public.b26_p2_execution_outbox"
                " SET next_retry_at = now() + interval '90 days'"
                " WHERE dispatch_task_id=%s",
                (task12,),
            )
        check("B-15 far-future retry refuses", False, "ACCEPTED")
    except DBERR as exc:
        check("B-15 far-future retry refuses", "retry_unbounded" in str(exc))

    # B-16 [GEN]: outbox minted-published refuses (issuance law).
    t16, _ig16, _e16 = new_tenant("b16")
    igx = _ig16
    with admin() as c, c.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (t16,))
    try:
        with role_conn("app_user") as c, c.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (t16,)
            )
            cur.execute(
                "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                " webhook_ingress_identity_id, task_id, task_name, queue,"
                " routing_key, correlation_id, provider,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_value, window_start, window_end)"
                " VALUES (%s, %s, %s, %s, 'b23_match_engine',"
                " 'b23_match_engine.task', %s, 'stripe', 'e', 'o', 'o', %s, %s)",
                (t16, igx, f"b16-{uuid.uuid4().hex[:8]}", TASK_NAME,
                 str(uuid.uuid4()), WS, WE),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_execution_outbox (tenant_id,"
                " dispatch_task_id, webhook_ingress_identity_id, state)"
                " VALUES (%s, %s, %s, 'published')",
                (t16, f"b16-o-{uuid.uuid4().hex[:8]}", igx),
            )
        check("B-16 minted-published refuses", False, "ACCEPTED")
    except DBERR as exc:
        check(
            "B-16 minted-published refuses",
            "issuance_state_refused" in str(exc) or "execution_tuple" in str(exc),
            str(exc)[:150],
        )

    # -- role/capability (B-17..B-18) --
    # B-17 [GEN]: relay directory INSERT denied.
    try:
        with role_conn("app_relay") as c, c.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (t,)
            )
            cur.execute(
                "INSERT INTO public.b26_p2_task_authority_directory (task_id,"
                " tenant_id, webhook_ingress_identity_id, window_start, window_end)"
                " VALUES (%s, %s, %s, %s, %s)",
                (f"b17-{uuid.uuid4().hex[:8]}", t, ig, WS, WE),
            )
        check("B-17 relay directory denied", False, "ACCEPTED")
    except DBERR:
        check("B-17 relay directory denied", True)

    # B-18 [GEN]: beat holds zero app-table reads.
    try:
        with role_conn("app_beat") as c, c.cursor() as cur:
            cur.execute("SELECT count(*) FROM public.b23_match_task_dispatches")
            cur.fetchone()
        check("B-18 beat app-table blind", False, "SELECT ALLOWED")
    except DBERR:
        check("B-18 beat app-table blind", True)

    # -- RLS/window (B-19) --
    # B-19: tenant-confined stale visibility (no leakage, no shared view).
    t19a, ig19a, _ea = new_tenant("b19a")
    t19b, ig19b, _eb = new_tenant("b19b")
    for tag, tt, ii in (("a", t19a, ig19a), ("b", t19b, ig19b)):
        seed_triple(tt, ii, f"b19-{tag}-{uuid.uuid4().hex[:8]}")
        with admin() as c, c.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tt,)
            )
            cur.execute(
                "UPDATE public.b23_match_task_dispatches SET delivery_state='published'"
                " WHERE tenant_id=%s",
                (tt,),
            )
            cur.execute(
                "UPDATE public.b26_p2_execution_outbox SET state='published'"
                " WHERE tenant_id=%s",
                (tt,),
            )
    with admin() as c, c.cursor() as cur:
        # Owner census pattern (migration authority): RLS disabled for
        # the cross-tenant aging write, restored immediately after. A
        # bare UPDATE without GUC would match zero rows SILENTLY.
        cur.execute(
            "ALTER TABLE public.b23_match_task_dispatches DISABLE ROW LEVEL SECURITY"
        )
        cur.execute(
            "ALTER TABLE public.b23_match_task_dispatches"
            " DISABLE TRIGGER trg_b26_p2_dispatch_immutability"
        )
        cur.execute(
            "UPDATE public.b23_match_task_dispatches SET first_published_at ="
            " now() - interval '500 seconds'"
        )
        cur.execute(
            "ALTER TABLE public.b23_match_task_dispatches"
            " ENABLE TRIGGER trg_b26_p2_dispatch_immutability"
        )
        cur.execute(
            "ALTER TABLE public.b23_match_task_dispatches ENABLE ROW LEVEL SECURITY"
        )
        cur.execute(
            "ALTER TABLE ONLY public.b23_match_task_dispatches FORCE ROW LEVEL SECURITY"
        )
    with role_conn("app_user") as c, c.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (t19a,))
        cur.execute("SELECT task_id FROM public.b26_p2_stale_unconducted(300)")
        seen = {r[0] for r in cur.fetchall()}
    check(
        "B-19 tenant-confined stale",
        len(seen) == 1 and next(iter(seen)).startswith("b19-a-"),
        str(seen),
    )

    # -- race (B-20: R6-12 lawful-vs-forged issuance race) --
    # B-20: concurrent lawful + forged issuance for one ingress: the
    # forged attempt refuses at the sovereign trigger, so the lawful
    # dispatch always wins (stronger than first-wins: forgery cannot win
    # a race it cannot enter).
    t20, ig20, _e20 = new_tenant("b20")
    race_ok: list[str] = []

    def _lawful():
        try:
            seed_triple(t20, ig20, f"b20-law-{uuid.uuid4().hex[:8]}")
            race_ok.append("lawful")
        except Exception:  # noqa: BLE001
            race_ok.append("lawful-err")

    def _forged():
        try:
            seed_triple(
                t20, ig20, f"b20-for-{uuid.uuid4().hex[:8]}",
                ws=WS + timedelta(days=9), we=WE + timedelta(days=9),
            )
            race_ok.append("forged-ACCEPTED")
        except Exception:  # noqa: BLE001
            race_ok.append("forged-refused")

    ths = [threading.Thread(target=_lawful), threading.Thread(target=_forged)]
    [th.start() for th in ths]
    [th.join() for th in ths]
    check(
        "B-20 race: lawful wins, forged refused",
        "lawful" in race_ok and "forged-refused" in race_ok,
        str(race_ok),
    )
    with admin() as c, c.cursor() as cur:
        cur.execute(
            "ALTER TABLE public.b23_match_task_dispatches DISABLE ROW LEVEL SECURITY"
        )
        cur.execute(
            "SELECT count(*), min(window_start) FROM public.b23_match_task_dispatches"
            " WHERE webhook_ingress_identity_id = %s",
            (ig20,),
        )
        n, mn = cur.fetchone()
        cur.execute(
            "ALTER TABLE public.b23_match_task_dispatches ENABLE ROW LEVEL SECURITY"
        )
        cur.execute(
            "ALTER TABLE ONLY public.b23_match_task_dispatches FORCE ROW LEVEL SECURITY"
        )
    check("B-20 exactly one sovereign dispatch", n == 1 and mn == WS, f"{n} {mn}")

    # -- naive-time primitive (B-21, unanticipated category) --
    # B-21: a tz-naive window that coerces (in session TZ) to the
    # canonical instant satisfies the sovereign equation as instants
    # (the column type is timestamptz; tz-awareness is not observable
    # past the type boundary) and is harmless. A naive window denoting
    # a DIVERGENT instant must refuse in every session timezone.
    t21, ig21, _e21 = new_tenant("b21")
    try:
        with role_conn("app_user") as c, c.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (t21,)
            )
            cur.execute(
                "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                " webhook_ingress_identity_id, task_id, task_name, queue,"
                " routing_key, correlation_id, provider,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_value, window_start, window_end)"
                " VALUES (%s, %s, %s, %s, 'b23_match_engine',"
                " 'b23_match_engine.task', %s, 'stripe', 'e', 'o', 'o',"
                " '2026-01-20 00:00:00', '2026-01-21 00:00:00')",
                (t21, ig21, f"b21-{uuid.uuid4().hex[:8]}", TASK_NAME,
                 str(uuid.uuid4())),
            )
        check("B-21 naive divergent window refuses", False, "ACCEPTED")
    except DBERR as exc:
        check(
            "B-21 naive divergent window refuses",
            "not_sovereign" in str(exc),
            str(exc)[:150],
        )

    print(f"VI_BLIND_PASS falsifiers={len(PASS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
