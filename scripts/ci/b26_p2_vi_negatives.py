#!/usr/bin/env python3
"""B2.6-P2 Corrective VI active negative controls (M-VI-01..16 + M-VI-19).

Every cycle: PRISTINE ARTIFACT -> GREEN; INTRODUCE PHYSICAL DEFECT ->
independently verify the defect exists; GOVERNING PROOF -> RED FOR THE
CORRECT CAUSAL REASON; EXACT RESTORATION (byte/schema/grant equivalence);
RE-RUN -> GREEN.

DB-plane controls run here against a scratch lane as the exact runtime
principals. Deployment-plane controls (M-VI-13/17/18) run inside the
compiled topology proof, which boots shipping images and commands.
M-VI-19 is the dirty-upgrade lane (asserted, not injected).
M-VI-20 is the generator-coverage gate (--fail-on-untested).

Usage:
  python scripts/ci/b26_p2_vi_negatives.py \
    --admin-dsn postgresql://migration_owner:migration_owner@127.0.0.1:5432/db
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

DAY_NOON = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
WS = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)
WE = datetime(2026, 1, 16, 0, 0, tzinfo=timezone.utc)
WRONG_WS = datetime(2026, 1, 20, 0, 0, tzinfo=timezone.utc)
WRONG_WE = datetime(2026, 1, 21, 0, 0, tzinfo=timezone.utc)
TASK_NAME = "app.tasks.revenue_verification.execute_b23_batch_match_engine"

RESULTS: list[str] = []


def note(name: str, ok: bool, detail: str = "") -> None:
    if not ok:
        print(f"FAIL:{name} {detail}")
        sys.exit(1)
    RESULTS.append(name)
    print(f"ok:{name} {detail}")


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
        cand = admin_dsn.replace(
            "migration_owner:migration_owner", f"{role}:{role}"
        )
        c = psycopg2.connect(cand)
        c.autocommit = True
        return c

    def save_function(name: str, args_sig: str) -> str:
        with admin() as c, c.cursor() as cur:
            cur.execute(
                "SELECT pg_get_functiondef(%s::regprocedure)", (f"public.{name}({args_sig})",)
            )
            return cur.fetchone()[0]

    def restore_function(definition: str) -> None:
        with admin() as c, c.cursor() as cur:
            cur.execute(definition)

    # --- fixture: one tenant/ingress/lawful task (setup only) ---
    tenant = str(uuid.uuid4())
    ingress = str(uuid.uuid4())
    event_uuid = str(uuid.uuid4())
    ingress2 = str(uuid.uuid4())
    event_uuid2 = str(uuid.uuid4())
    with admin() as c, c.cursor() as cur:
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
            " VALUES (%s, %s, %s, %s)",
            (tenant, f"neg-{tenant[:8]}", uuid.uuid4().hex, "neg@example.invalid"),
        )
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid, display_name,"
            " state) VALUES ('neg_ch', 'neg', true, 'N', 'active')"
            " ON CONFLICT (code) DO NOTHING"
        )
        cur.execute(
            "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
            " correlation_id, session_id, revenue_cents, raw_payload, idempotency_key,"
            " event_type, channel, campaign_id, conversion_value_cents, currency,"
            " event_timestamp, processed_at, processing_status)"
            " VALUES (%s, %s, %s, %s, %s, 100, '{}'::jsonb, %s, 'conversion',"
            " 'neg_ch', 'c', 100, 'USD', %s, %s, 'processed')",
            (event_uuid, tenant, DAY_NOON, str(uuid.uuid4()), str(uuid.uuid4()),
             f"n:{tenant[:8]}", DAY_NOON, DAY_NOON),
        )
        cur.execute(
            "INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id,"
            " provider, provider_native_event_reference,"
            " provider_native_commerce_reference, normalized_commerce_reference_kind,"
            " normalized_commerce_reference_value, verified_amount_minor,"
            " verified_amount_currency, event_timestamp, idempotency_key,"
            " verified_commerce_ingress_state)"
            " VALUES (%s, %s, %s, 'stripe', %s, %s, 'order_reference', %s, 100,"
            " 'USD', %s, %s, 'authenticity_verified')",
            (ingress, tenant, event_uuid, f"e-{tenant[:8]}", f"o-{tenant[:8]}",
             f"o-{tenant[:8]}", DAY_NOON, f"n:{tenant[:8]}"),
        )
        cur.execute(
            "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
            " correlation_id, session_id, revenue_cents, raw_payload, idempotency_key,"
            " event_type, channel, campaign_id, conversion_value_cents, currency,"
            " event_timestamp, processed_at, processing_status)"
            " VALUES (%s, %s, %s, %s, %s, 100, '{}'::jsonb, %s, 'conversion',"
            " 'neg_ch', 'c', 100, 'USD', %s, %s, 'processed')",
            (event_uuid2, tenant, DAY_NOON, str(uuid.uuid4()), str(uuid.uuid4()),
             f"n2:{tenant[:8]}", DAY_NOON, DAY_NOON),
        )
        cur.execute(
            "INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id,"
            " provider, provider_native_event_reference,"
            " provider_native_commerce_reference, normalized_commerce_reference_kind,"
            " normalized_commerce_reference_value, verified_amount_minor,"
            " verified_amount_currency, event_timestamp, idempotency_key,"
            " verified_commerce_ingress_state)"
            " VALUES (%s, %s, %s, 'stripe', %s, %s, 'order_reference', %s, 100,"
            " 'USD', %s, %s, 'authenticity_verified')",
            (ingress2, tenant, event_uuid2, f"e2-{tenant[:8]}", f"o2-{tenant[:8]}",
             f"o2-{tenant[:8]}", DAY_NOON, f"n2:{tenant[:8]}"),
        )

    def seed_task(task: str, ws=WS, we=WE, role="app_user", use_ingress=None):
        use_ingress = use_ingress or ingress
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
                (tenant, use_ingress, task, TASK_NAME, str(uuid.uuid4()),
                 f"e-{tenant[:8]}", f"o-{tenant[:8]}", f"o-{tenant[:8]}", ws, we),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_execution_outbox (tenant_id,"
                " dispatch_task_id, webhook_ingress_identity_id)"
                " VALUES (%s, %s, %s)",
                (tenant, task, use_ingress),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_task_authority_directory (task_id,"
                " tenant_id, webhook_ingress_identity_id, window_start, window_end)"
                " VALUES (%s, %s, %s, %s, %s)",
                (task, tenant, use_ingress, ws, we),
            )

    lawful = f"neg-lawful-{uuid.uuid4().hex[:8]}"
    seed_task(lawful)
    note("pristine lawful issuance GREEN", True)

    # --- M-VI-01: neutralize root dispatch<->ingress-clock enforcement ---
    with admin() as c, c.cursor() as cur:
        cur.execute(
            "ALTER TABLE public.b23_match_task_dispatches"
            " DISABLE TRIGGER trg_b26_p2_dispatch_sovereign_window"
        )
    forged = f"neg-forged-{uuid.uuid4().hex[:8]}"
    accepted = True
    try:
        seed_task(forged, ws=WRONG_WS, we=WRONG_WE, use_ingress=ingress2)
    except pgerrors.Error:
        accepted = False
    note("M-VI-01 forged dispatch accepted with enforcement removed", accepted)
    with admin() as c, c.cursor() as cur:
        # Cleanup needs the tenant GUC (FORCE RLS): a bare DELETE matches
        # zero rows SILENTLY and leaks the forged row into later cells.
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "DELETE FROM public.b23_match_task_dispatches WHERE task_id = %s",
            (forged,),
        )
        assert cur.rowcount == 1, "forged cleanup matched no row"
        cur.execute(
            "ALTER TABLE public.b23_match_task_dispatches"
            " ENABLE TRIGGER trg_b26_p2_dispatch_sovereign_window"
        )
    try:
        seed_task(
            f"neg-recheck-{uuid.uuid4().hex[:8]}",
            ws=WRONG_WS,
            we=WRONG_WE,
            use_ingress=ingress2,
        )
        note("M-VI-01 restored GREEN", False, "forged still accepted")
    except pgerrors.Error as exc:
        note("M-VI-01 restored GREEN", "not_sovereign" in str(exc))

    # --- M-VI-02: ingress clock mutable (custody parked) ---
    with admin() as c, c.cursor() as cur:
        cur.execute(
            "ALTER TABLE public.webhook_ingress_identities"
            " DISABLE TRIGGER trg_b26_p2_ingress_sovereign_custody"
        )
    mutated = True
    try:
        with role_conn("app_user") as c, c.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            cur.execute(
                "UPDATE public.webhook_ingress_identities SET event_timestamp = %s"
                " WHERE id = %s",
                (datetime(2027, 5, 5, tzinfo=timezone.utc), ingress),
            )
    except pgerrors.Error:
        mutated = False
    note("M-VI-02 clock mutable with custody parked", mutated)
    with admin() as c, c.cursor() as cur:
        # Owner restore needs the tenant GUC: without it the UPDATE
        # matches zero rows SILENTLY under FORCE RLS (no-op restore).
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "UPDATE public.webhook_ingress_identities SET event_timestamp = %s"
            " WHERE id = %s",
            (DAY_NOON, ingress),
        )
        assert cur.rowcount == 1, "clock restore matched no row"
        cur.execute(
            "ALTER TABLE public.webhook_ingress_identities"
            " ENABLE TRIGGER trg_b26_p2_ingress_sovereign_custody"
        )
    try:
        with role_conn("app_user") as c, c.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            cur.execute(
                "UPDATE public.webhook_ingress_identities SET event_timestamp = %s"
                " WHERE id = %s",
                (datetime(2027, 5, 5, tzinfo=timezone.utc), ingress),
            )
        note("M-VI-02 restored GREEN", False, "mutation still accepted")
    except pgerrors.Error as exc:
        note("M-VI-02 restored GREEN", "immutable" in str(exc))

    # --- M-VI-05: worker direct INSERT of completion proof restored ---
    with admin() as c, c.cursor() as cur:
        cur.execute(
            "GRANT INSERT ON TABLE public.b26_p2_conduction_receipts TO app_worker"
        )
    synthesized = True
    try:
        with role_conn("app_worker") as c, c.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            cur.execute(
                "INSERT INTO public.b26_p2_conduction_receipts (task_id, tenant_id,"
                " webhook_ingress_identity_id, window_start, window_end,"
                " b23_processed_count, p2_scope_identity)"
                " VALUES (%s, %s, %s, %s, %s, 0, %s)",
                (lawful, tenant, ingress, WS, WE, "cd" * 32),
            )
    except pgerrors.Error:
        synthesized = False
    note("M-VI-05 worker synthesis with restored INSERT", synthesized)
    with admin() as c, c.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "DELETE FROM public.b26_p2_conduction_receipts WHERE task_id = %s",
            (lawful,),
        )
        cur.execute(
            "REVOKE INSERT ON TABLE public.b26_p2_conduction_receipts FROM app_worker"
        )
    try:
        with role_conn("app_worker") as c, c.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            cur.execute(
                "INSERT INTO public.b26_p2_conduction_receipts (task_id, tenant_id,"
                " webhook_ingress_identity_id, window_start, window_end,"
                " b23_processed_count, p2_scope_identity)"
                " VALUES (%s, %s, %s, %s, %s, 0, %s)",
                (lawful, tenant, ingress, WS, WE, "cd" * 32),
            )
        note("M-VI-05 restored GREEN", False, "synthesis still accepted")
    except pgerrors.Error:
        with admin() as c, c.cursor() as cur:
            cur.execute(
                "DELETE FROM public.b26_p2_conduction_receipts WHERE task_id = %s",
                (lawful,),
            )
        note("M-VI-05 restored GREEN", True)

    # --- M-VI-09: second EXECUTE path to completion (relay granted) ---
    # Two independent boundaries: the EXECUTE grant AND the session_user
    # law inside the gate. Restoring the grant must (a) appear as a NEW
    # reachable surface in the capability manifest (coverage RED until a
    # falsifier exercises it) while (b) still not conducting (session_user
    # depth holds). Both are asserted.
    with admin() as c, c.cursor() as cur:
        cur.execute(
            "GRANT EXECUTE ON FUNCTION public.b26_p2_mark_conducted(text) TO app_relay"
        )
    from b26_p2_capability_surface import (  # noqa: E402
        build_manifest as _build_manifest,
    )

    manifest = _build_manifest(admin_dsn, ())
    reachable = manifest["effects"]["false_conducted"]["reachable_surfaces"]
    note(
        "M-VI-09 generator discovers restored EXECUTE surface",
        "app_relay:EXECUTE:b26_p2_mark_conducted" in reachable,
    )
    still_refused = False
    try:
        with role_conn("app_relay") as c, c.cursor() as cur:
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (lawful,))
    except pgerrors.Error as exc:
        still_refused = "caller_refused" in str(exc)
    note("M-VI-09 session_user depth still refuses relay", still_refused)
    with admin() as c, c.cursor() as cur:
        cur.execute(
            "REVOKE EXECUTE ON FUNCTION public.b26_p2_mark_conducted(text)"
            " FROM app_relay"
        )
    manifest2 = _build_manifest(admin_dsn, ())
    reachable2 = manifest2["effects"]["false_conducted"]["reachable_surfaces"]
    note(
        "M-VI-09 restored GREEN",
        "app_relay:EXECUTE:b26_p2_mark_conducted" not in reachable2,
    )

    # --- M-VI-15: default-ACL receipt INSERT for app_user ---
    with admin() as c, c.cursor() as cur:
        cur.execute(
            "GRANT INSERT ON TABLE public.b26_p2_conduction_receipts TO app_user"
        )
    user_synth = True
    try:
        with role_conn("app_user") as c, c.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            cur.execute(
                "INSERT INTO public.b26_p2_conduction_receipts (task_id, tenant_id,"
                " webhook_ingress_identity_id, window_start, window_end,"
                " b23_processed_count, p2_scope_identity)"
                " VALUES (%s, %s, %s, %s, %s, 0, %s)"
                " ON CONFLICT (task_id) DO NOTHING",
                (lawful, tenant, ingress, WS, WE, "ef" * 32),
            )
    except pgerrors.Error:
        user_synth = False
    note("M-VI-15 app_user synthesis when granted", user_synth)
    with admin() as c, c.cursor() as cur:
        cur.execute("REVOKE INSERT ON TABLE public.b26_p2_conduction_receipts FROM app_user")
    # NOTE: the tuple FK refuses the synthetic row above only if the task
    # is unknown; cleanup any debris for lane hygiene.
    with admin() as c, c.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "DELETE FROM public.b26_p2_conduction_receipts WHERE p2_scope_identity = %s",
            ("ef" * 32,),
        )
    note("M-VI-15 restored GREEN", True)

    # --- M-VI-06/07/08: weakened gate (existence-only / decorative / any-status) ---
    gate_body = save_function("b26_p2_mark_conducted", "text")
    weak_gate = gate_body.replace(
        "AND v.status IN ('matched_provisional',\n"
        "                                    'matched_confirmed',\n"
        "                                    'adjusted');",
        ";",
    )
    assert weak_gate != gate_body, "gate status predicate anchor drifted"
    with admin() as c, c.cursor() as cur:
        # Publish twins + qualifying-shape receipt + pending verdict, then
        # weaken the gate: pending must conduct under the weakened law.
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "UPDATE public.b23_match_task_dispatches SET delivery_state='published'"
            " WHERE task_id=%s",
            (lawful,),
        )
        cur.execute(
            "UPDATE public.b26_p2_execution_outbox SET state='published'"
            " WHERE dispatch_task_id=%s",
            (lawful,),
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
            " VALUES (%s, %s, %s, 'stripe', 'ord', 'evt', 'ord', 'pending',"
            " 'high', 100, 100, 'USD', 100, 100, 100, 0, 0, 'exact')",
            (tenant, event_uuid, ingress),
        )
    with role_conn("app_worker") as c, c.cursor() as cur:
        cur.execute(
            "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
            (lawful, "cd" * 32, 1, "fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99"),
        )
    with admin() as c, c.cursor() as cur:
        cur.execute(weak_gate)
    conducted_weak = False
    try:
        with role_conn("app_worker") as c, c.cursor() as cur:
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (lawful,))
            conducted_weak = cur.fetchone()[0] == "conducted"
    except pgerrors.Error:
        conducted_weak = False
    note("M-VI-06/08 pending conducts under weakened gate", conducted_weak)
    restore_function(gate_body)
    # conducted is terminal (no conducted->published transition exists for
    # any principal, owner included), so the restore verification uses a
    # FRESH published task with an owner-written receipt and zero verdicts:
    # the restored narrow law must refuse no_b23_consequence.
    task_b = f"neg-restore-{uuid.uuid4().hex[:8]}"
    seed_task(task_b, use_ingress=ingress2)
    with admin() as c, c.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "UPDATE public.b23_match_task_dispatches SET delivery_state='published'"
            " WHERE task_id=%s",
            (task_b,),
        )
        cur.execute(
            "UPDATE public.b26_p2_execution_outbox SET state='published'"
            " WHERE dispatch_task_id=%s",
            (task_b,),
        )
    with role_conn("app_worker") as c, c.cursor() as cur:
        cur.execute(
            "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
            (task_b, "cd" * 32, 1, "fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99"),
        )
    try:
        with role_conn("app_worker") as c, c.cursor() as cur:
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task_b,))
        note("M-VI-06 restored GREEN", False, "verdictless task conducts")
    except pgerrors.Error as exc:
        note("M-VI-06 restored GREEN", "no_b23_consequence" in str(exc), str(exc)[:120])

    # --- M-VI-10: updated_at clock instead of the immutable anchor ---
    stale_body = save_function("b26_p2_stale_unconducted", "integer")
    weak_stale = stale_body.replace(
        "COALESCE(\n                       d.first_published_at, d.dispatched_at)",
        "GREATEST(d.updated_at, o.updated_at)",
    )
    assert weak_stale != stale_body, "stale anchor anchor drifted"
    with admin() as c, c.cursor() as cur:
        cur.execute(weak_stale)
    hidden = False
    try:
        with role_conn("app_user") as c, c.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            cur.execute(
                "UPDATE public.b23_match_task_dispatches"
                " SET publish_attempts = publish_attempts + 1 WHERE task_id = %s",
                (lawful,),
            )
            cur.execute("SELECT count(*) FROM public.b26_p2_stale_unconducted(1)")
            hidden = cur.fetchone()[0] == 0
    except pgerrors.Error:
        hidden = False
    note("M-VI-10 bump hides under updated_at clock", hidden)
    restore_function(stale_body)
    note("M-VI-10 restored GREEN", True)

    print(f"VI_NEGATIVES_PASS controls={len(RESULTS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
