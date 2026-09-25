#!/usr/bin/env python3
"""B2.6-P2 Corrective XII behavioral temporal coverage (BLOCKER E).

Law: temporal coverage is not a textual property. For each semantically
mutable dependency, a change after P2 conduction produces exactly one
governed effect: mutation refused, old consequence superseded/staled
with mandatory re-adjudication, or old consequence historically bound
and unconsumable as current. Set-level semantics (INSERT/DELETE,
existence, count, membership, lookup/version rows) receive the same
treatment when they can alter P2 meaning.

Mechanism: live mutation probes on a scratch tenant through a lawfully
conducted XII lineage (provider-bound consequence, bound witness,
signed attestation, qualifying verdict, published dispatch/outbox,
canonical receipt, mark_conducted). Each probe attempts a real
post-conduction mutation and requires the governed refusal; a
weakened trigger that retains every textual reference still REDs
because the mutation succeeds.

Stale honesty: moving live identity after conduction flips P3
eligibility FALSE; the stale terminal is quarantined explicitly
(never silently current); replay/conduction under the stale snapshot
is refused.

Concurrency: barrier-controlled mark_conducted races serialize to one
reconstructible ordering; a presence-flip committed between snapshot
and conduction refuses instead of mixing versions.

Exit code is the gate: 0 on PASS, 1 plus a violation list on FAIL.
"""

from __future__ import annotations

import argparse
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

DAY_START = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)
DAY_END = datetime(2026, 1, 16, 0, 0, tzinfo=timezone.utc)
DAY_NOON = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
TASK_NAME = "app.tasks.revenue_verification.execute_b23_batch_match_engine"
POLICY_SHA = "fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99"


def _role_dsn(admin_dsn: str, role: str) -> str | None:
    if "migration_owner:migration_owner" not in admin_dsn:
        return None
    return admin_dsn.replace(
        "migration_owner:migration_owner", f"{role}:{role}"
    )


def _seed_conducted_lineage(admin_dsn: str, tag: str, conduct: bool = True):
    import psycopg2  # noqa: PLC0415

    ingress_dsn = _role_dsn(admin_dsn, "app_ingress")
    user_dsn = _role_dsn(admin_dsn, "app_user")
    worker_dsn = _role_dsn(admin_dsn, "app_worker")
    tenant = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    ingress_id = str(uuid.uuid4())
    idem = "xii-temp-%s-%s" % (tag, uuid.uuid4().hex[:6])
    evt_ref = "evt-%s" % idem
    task = "xii-temp-%s-%s" % (tag, uuid.uuid4().hex[:8])
    admin = psycopg2.connect(admin_dsn)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tenants (id, name, api_key_hash,"
                " notification_email) VALUES (%s, %s, %s, %s)",
                (tenant, "xii-temp-%s" % tag, uuid.uuid4().hex,
                 "xii-temp@example.invalid"),
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            cur.execute(
                "INSERT INTO public.channel_taxonomy (code,family,"
                " is_paid, display_name, state) VALUES"
                " ('xii_temp_ch', 'xii_temp', true, 'XIITEMP', 'active')"
                " ON CONFLICT (code) DO NOTHING"
            )
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, 38000,"
                " '{}'::jsonb, %s, 'conversion', 'xii_temp_ch',"
                " 'c', 38000, 'USD', %s, %s, 'processed')",
                (event_id, tenant, DAY_NOON, str(uuid.uuid4()),
                 str(uuid.uuid4()), idem, DAY_NOON, DAY_NOON),
            )
            cur.execute(
                "INSERT INTO public.webhook_ingress_identities (id,"
                " tenant_id, event_id, provider,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_kind,"
                " normalized_commerce_reference_value,"
                " verified_amount_minor, verified_amount_currency,"
                " event_timestamp, idempotency_key,"
                " verified_commerce_ingress_state)"
                " VALUES (%s, %s, %s, 'stripe', %s, %s,"
                " 'order_reference', %s, 38000, 'USD', %s, %s,"
                " 'authenticity_verified')",
                (ingress_id, tenant, event_id, evt_ref,
                 "ord-%s" % idem, "ord-%s" % idem, DAY_NOON, idem),
            )
            cur.execute(
                "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                " webhook_ingress_identity_id, task_id, task_name, queue,"
                " routing_key, correlation_id, provider,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_value, status,"
                " delivery_state, publish_attempts, window_start,"
                " window_end) VALUES (%s, %s, %s,"
                " 'app.tasks.revenue_verification."
                "execute_b23_batch_match_engine',"
                " 'b23_match_engine', 'b23_match_engine.task', %s,"
                " 'stripe', %s, %s, %s, 'dispatched', 'pending_publish',"
                " 0, %s, %s)",
                (tenant, ingress_id, task, str(uuid.uuid4()), evt_ref,
                 "ord-%s" % idem, "ord-%s" % idem, DAY_START, DAY_END),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_execution_outbox (tenant_id,"
                " dispatch_task_id, webhook_ingress_identity_id)"
                " VALUES (%s, %s, %s)",
                (tenant, task, ingress_id),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_task_authority_directory (task_id,"
                " tenant_id, webhook_ingress_identity_id, window_start,"
                " window_end) VALUES (%s, %s, %s, %s, %s)",
                (task, tenant, ingress_id, DAY_START, DAY_END),
            )
            cur.execute(
                "UPDATE public.b23_match_task_dispatches"
                " SET delivery_state='published', first_published_at=now()"
                " WHERE task_id=%s",
                (task,),
            )
            cur.execute(
                "UPDATE public.b26_p2_execution_outbox SET state='published'"
                " WHERE dispatch_task_id=%s",
                (task,),
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
                " VALUES (%s, %s, %s, 'stripe', %s, %s, %s,"
                " 'matched_confirmed', 'high', 38000, 38000, 'USD',"
                " 38000, 38000, 38000, 0, 0, 'exact')",
                (tenant, event_id, ingress_id, "ord-%s" % idem, evt_ref,
                 "ord-%s" % idem),
            )
    finally:
        admin.close()
    # Lawful XII authentication chain through exact runtime principals.
    user = psycopg2.connect(user_dsn)
    user.autocommit = True
    try:
        with user.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            cur.execute(
                "SELECT public.b26_p2_record_provider_auth_consequence("
                "%s,'stripe',%s,%s,%s,'hmac-sha256-timestamped-hex','v1')",
                (ingress_id, evt_ref, "c" * 64, "d" * 64),
            )
    finally:
        user.close()
    ingress = psycopg2.connect(ingress_dsn)
    ingress.autocommit = True
    try:
        with ingress.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            cur.execute(
                "SELECT public.b26_p2_record_ingress_auth_witness"
                "(%s,'stripe',%s,%s)",
                (ingress_id, evt_ref, "c" * 64),
            )
            cur.execute(
                "SELECT public.b26_p2_attest_provenance_evidence"
                "(%s,'signed_provider_reingestion',%s)",
                (ingress_id, idem),
            )
            assert str(cur.fetchone()[0]) == "authenticated_known"
    finally:
        ingress.close()
    # Canonical receipt through the worker principal; conduction is
    # optional so flip-then-conduct races can stage a published (not
    # conducted) terminal.
    worker = psycopg2.connect(worker_dsn)
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute(
                "SELECT public.b26_p2_canonical_scope_identity_for_window"
                "(%s,%s,%s)",
                (tenant, DAY_START, DAY_END),
            )
            scope = str(cur.fetchone()[0])
            cur.execute(
                "SELECT public.b26_p2_record_conduction_receipt(%s,%s,%s,%s)",
                (task, scope, 1, POLICY_SHA),
            )
            if conduct:
                cur.execute(
                    "SELECT public.b26_p2_mark_conducted(%s)", (task,)
                )
                assert str(cur.fetchone()[0]) == "conducted"
    finally:
        worker.close()
    return {
        "tenant": tenant, "ingress": ingress_id, "task": task,
        "idem": idem, "evt_ref": evt_ref, "scope": scope,
        "event": event_id,
    }


def _attempt(role_dsn, tenant, sql, args):
    import psycopg2  # noqa: PLC0415

    conn = psycopg2.connect(role_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            cur.execute(sql, args)
            return ("ok", None)
    except Exception as exc:
        return ("refused", str(exc).splitlines()[0][:160])
    finally:
        conn.close()


def _behavioral_probes(admin_dsn, violations, checks) -> None:
    import psycopg2  # noqa: PLC0415

    admin_role_dsn = admin_dsn
    worker_dsn = _role_dsn(admin_dsn, "app_worker")
    ingress_dsn = _role_dsn(admin_dsn, "app_ingress")
    if worker_dsn is None or ingress_dsn is None:
        violations.append("xii_temp_role_dsn_underivable")
        return
    ids = _seed_conducted_lineage(admin_dsn, "behavior")
    tenant = ids["tenant"]
    task = ids["task"]
    ingress_id = ids["ingress"]
    checks["conducted_task"] = task

    # TEMP-A: qualifying verdict presence flip refused.
    admin = psycopg2.connect(admin_role_dsn)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            cur.execute(
                "SELECT id FROM public.b23_match_verdicts"
                " WHERE webhook_ingress_identity_id = %s",
                (ingress_id,),
            )
            verdict_id = str(cur.fetchone()[0])
    finally:
        admin.close()
    status, detail = _attempt(
        admin_role_dsn, tenant,
        "UPDATE public.b23_match_verdicts SET status='unmatched'"
        " WHERE id = %s",
        (verdict_id,),
    )
    if status == "ok":
        violations.append("xii_temp_presence_flip_permitted")
    elif "b26_p2_conducted_verdict_regression_refused" not in (detail or ""):
        violations.append("xii_temp_presence_flip_wrong_refusal:%s" % detail)
    else:
        checks["presence_flip_refused"] = True

    # TEMP-B: qualifying verdict INSERT into the conducted set refused.
    status, detail = _attempt(
        admin_role_dsn, tenant,
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
        " VALUES (%s, %s, %s, 'stripe', 'ord-x', 'evt-x', 'ord-x',"
        " 'matched_confirmed', 'high', 1, 1, 'USD', 1, 1, 1, 0, 0, 'exact')",
        (tenant, ids["event"], ingress_id),
    )
    if status == "ok":
        violations.append("xii_temp_conducted_insert_permitted")
    elif "b26_p2_conducted_set_insert_refused" not in (detail or ""):
        violations.append("xii_temp_conducted_insert_wrong_refusal:%s" % detail)
    else:
        checks["conducted_insert_refused"] = True

    # TEMP-C: qualifying verdict DELETE refused.
    status, detail = _attempt(
        admin_role_dsn, tenant,
        "DELETE FROM public.b23_match_verdicts WHERE id = %s",
        (verdict_id,),
    )
    if status == "ok":
        violations.append("xii_temp_conducted_delete_permitted")
    elif "b26_p2_conducted_verdict_immutable" not in (detail or ""):
        violations.append("xii_temp_conducted_delete_wrong_refusal:%s" % detail)
    else:
        checks["conducted_delete_refused"] = True

    # TEMP-D: dispatch-bearing sovereign mutation refused (custody).
    status, detail = _attempt(
        ingress_dsn, tenant,
        "UPDATE public.webhook_ingress_identities SET provider='shopify'"
        " WHERE id = %s",
        (ingress_id,),
    )
    if status == "ok":
        violations.append("xii_temp_custody_permitted")
    elif "immutable" not in (detail or "").lower():
        violations.append("xii_temp_custody_wrong_refusal:%s" % detail)
    else:
        checks["custody_refused"] = True

    # TEMP-E: policy semantic mutation under a fixed version refused.
    # RLS makes the row UPDATE-invisible to every runtime principal;
    # the trigger is the backstop. Prove the trigger behaviorally by
    # lifting RLS in a rolled-back transaction (owner-only ALTER) and
    # attempting the mutation: only the trigger stands in the way.
    admin = psycopg2.connect(admin_role_dsn)
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            cur.execute(
                "SELECT scope_policy_version"
                " FROM public.b26_p2_scope_policy_authority"
                " ORDER BY scope_policy_version DESC LIMIT 1"
            )
            policy_version = str(cur.fetchone()[0])
            cur.execute(
                "ALTER TABLE public.b26_p2_scope_policy_authority"
                " DISABLE ROW LEVEL SECURITY"
            )
            try:
                cur.execute(
                    "UPDATE public.b26_p2_scope_policy_authority"
                    " SET semantic_sha256 = %s"
                    " WHERE scope_policy_version = %s",
                    ("0" * 64, policy_version),
                )
                violations.append("xii_temp_policy_mutation_permitted")
            except Exception as exc:
                detail = str(exc).splitlines()[0][:160]
                if "b26_p2_policy_semantic_mutation_refused" not in str(exc):
                    violations.append(
                        "xii_temp_policy_wrong_refusal:%s" % detail
                    )
                else:
                    checks["policy_refused"] = True
            finally:
                admin.rollback()
    finally:
        admin.close()

    # TEMP-F: stale honesty. Move live identity with a second lawful
    # ingress in the same window; old eligibility must not stay current.
    ids2 = _seed_conducted_lineage(admin_dsn, "stale")
    # ids2 is a different tenant; instead move identity on the SAME
    # tenant with a second lawful ingress (no conduction needed: the
    # aggregate reads every verified non-quarantined row).
    admin = psycopg2.connect(admin_role_dsn)
    admin.autocommit = True
    ingress2 = str(uuid.uuid4())
    event2 = str(uuid.uuid4())
    idem2 = "xii-temp-stale2-%s" % uuid.uuid4().hex[:6]
    evt2 = "evt-%s" % idem2
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, 100,"
                " '{}'::jsonb, %s, 'conversion', 'xii_temp_ch',"
                " 'c', 100, 'USD', %s, %s, 'processed')",
                (event2, tenant, DAY_NOON, str(uuid.uuid4()),
                 str(uuid.uuid4()), idem2, DAY_NOON, DAY_NOON),
            )
    finally:
        admin.close()
    ingress = psycopg2.connect(ingress_dsn)
    ingress.autocommit = True
    try:
        with ingress.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            cur.execute(
                "INSERT INTO public.webhook_ingress_identities (id,"
                " tenant_id, event_id, provider,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_kind,"
                " normalized_commerce_reference_value,"
                " verified_amount_minor, verified_amount_currency,"
                " event_timestamp, idempotency_key,"
                " verified_commerce_ingress_state)"
                " VALUES (%s, %s, %s, 'stripe', %s, %s,"
                " 'order_reference', %s, 200, 'USD', %s, %s,"
                " 'authenticity_verified')",
                (ingress2, tenant, event2, evt2, "ord-%s" % idem2,
                 "ord-%s" % idem2, DAY_NOON, idem2),
            )
    finally:
        ingress.close()
    user_dsn = _role_dsn(admin_dsn, "app_user")
    user = psycopg2.connect(user_dsn)
    user.autocommit = True
    try:
        with user.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            cur.execute(
                "SELECT public.b26_p2_record_provider_auth_consequence("
                "%s,'stripe',%s,%s,%s,'hmac-sha256-timestamped-hex','v1')",
                (ingress2, evt2, "e" * 64, "f" * 64),
            )
    finally:
        user.close()
    ingress = psycopg2.connect(ingress_dsn)
    ingress.autocommit = True
    try:
        with ingress.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            cur.execute(
                "SELECT public.b26_p2_record_ingress_auth_witness"
                "(%s,'stripe',%s,%s)",
                (ingress2, evt2, "e" * 64),
            )
            cur.execute(
                "SELECT public.b26_p2_attest_provenance_evidence"
                "(%s,'signed_provider_reingestion',%s)",
                (ingress2, idem2),
            )
    finally:
        ingress.close()
    worker = psycopg2.connect(worker_dsn)
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute(
                "SELECT public.b26_p2_state_eligible_for_p3(%s, %s)",
                (task, tenant),
            )
            if cur.fetchone()[0] is True:
                violations.append("xii_temp_stale_eligibility_current")
            else:
                checks["stale_not_current"] = True
    finally:
        worker.close()
    # Explicit governed disposition (never silently current): the
    # stale terminal must be DETECTED by the invariant oracle...
    admin = psycopg2.connect(admin_role_dsn)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            cur.execute(
                "SELECT violation_kind, task_ref"
                " FROM public.b26_p2_xi_invariant_oracle()"
                " WHERE task_ref = %s",
                (task,),
            )
            oracle_rows = cur.fetchall()
            if not any(
                r[0] == "xi_stale_terminal_binding" for r in oracle_rows
            ):
                violations.append(
                    "xii_temp_stale_undetected:%s" % (oracle_rows[:2],)
                )
            else:
                checks["stale_detected"] = True
            # ...and then quarantined explicitly.
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_execution_quarantine ("
                " source_relation, task_id, tenant_id,"
                " webhook_ingress_identity_id, window_start, window_end,"
                " reason, original_payload, migration_identity)"
                " VALUES ('b23_match_task_dispatches', %s, %s, %s, %s, %s,"
                " 'xii_temporal_probe:stale_terminal', '{}'::jsonb,"
                " '202609250001')",
                (task, tenant, ingress_id, DAY_START, DAY_END),
            )
    finally:
        admin.close()
    worker = psycopg2.connect(worker_dsn)
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute(
                "SELECT public.b26_p2_state_eligible_for_p3(%s, %s)",
                (task, tenant),
            )
            if cur.fetchone()[0] is True:
                violations.append("xii_temp_quarantined_eligible")
            else:
                checks["quarantined_ineligible"] = True
    finally:
        worker.close()
    checks["stale_control_lineage"] = ids2["task"]
    checks["behavioral_done"] = True


def _concurrency_probe(admin_dsn, violations, checks) -> None:
    import psycopg2  # noqa: PLC0415

    worker_dsn = _role_dsn(admin_dsn, "app_worker")
    if worker_dsn is None:
        violations.append("xii_temp_worker_dsn_underivable")
        return
    ids = _seed_conducted_lineage(admin_dsn, "race", conduct=False)
    # Barrier race: two workers conduct the same published terminal at
    # once. The FOR UPDATE serialization admits exactly one conductor;
    # the other observes already_conducted. No mixed-version
    # consequence exists.
    barrier = threading.Barrier(2)
    outcomes = {}

    def conduct(name):
        conn = psycopg2.connect(worker_dsn)
        conn.autocommit = True
        try:
            barrier.wait(timeout=30)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT public.b26_p2_mark_conducted(%s)", (ids["task"],)
                )
                outcomes[name] = str(cur.fetchone()[0])
        except Exception as exc:
            outcomes[name] = "error:%s" % str(exc).splitlines()[0][:100]
        finally:
            conn.close()

    threads = [
        threading.Thread(target=conduct, args=("t1",)),
        threading.Thread(target=conduct, args=("t2",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    checks["race_outcomes"] = outcomes
    values = sorted(outcomes.values())
    if values != ["already_conducted", "conducted"]:
        violations.append("xii_temp_race_not_serialized:%s" % values)
    # Flip-then-conduct refuses instead of mixing versions: a second
    # lineage is published (not conducted) with its receipt bound to
    # the pre-flip scope; a presence flip commits lawfully (no
    # conducted parent yet); conduction under the stale snapshot
    # refuses canonically.
    ids3 = _seed_conducted_lineage(admin_dsn, "fliprace", conduct=False)
    admin = psycopg2.connect(admin_dsn)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (ids3["tenant"],),
            )
            try:
                cur.execute(
                    "UPDATE public.b23_match_verdicts SET status='unmatched'"
                    " WHERE webhook_ingress_identity_id = %s",
                    (ids3["ingress"],),
                )
            except Exception as exc:
                violations.append("xii_temp_flip_setup_refused:%s" % str(exc)[:120])
                return
            checks["flip_committed"] = True
    finally:
        admin.close()
    worker = psycopg2.connect(worker_dsn)
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            try:
                cur.execute(
                    "SELECT public.b26_p2_mark_conducted(%s)", (ids3["task"],)
                )
                if str(cur.fetchone()[0]) == "conducted":
                    violations.append("xii_temp_flip_conducted_mixed")
                else:
                    checks["flip_conduct_idempotent"] = True
            except Exception as exc:
                if "b26_p2_conducted_scope_not_canonical" not in str(exc):
                    violations.append(
                        "xii_temp_flip_wrong_refusal:" + str(exc)[:120]
                    )
                else:
                    checks["flip_refused"] = True
    finally:
        worker.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate B2.6-P2 XII behavioral temporal law."
    )
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    if args.dsn is None:
        violations.append("xii_temp_live_check_required_no_dsn")
    else:
        try:
            _behavioral_probes(args.dsn, violations, checks)
            _concurrency_probe(args.dsn, violations, checks)
        except Exception as exc:
            violations.append(f"xii_temp_crash:{exc}"[:200])
    status = "PASS" if not violations else "FAIL"
    evidence = {
        "gate_id": "B26-P2-XII-TEMPORAL-BEHAVIORAL",
        "validator": "validate_b26_p2_xii_temporal_behavioral",
        "status": status,
        "violations": sorted(violations),
        "checks": checks,
    }
    if args.evidence_out is not None:
        args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if args.evidence_dir is not None:
        args.evidence_dir.mkdir(parents=True, exist_ok=True)
        (args.evidence_dir / "xii-temporal-behavioral.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if violations:
        print("B26_P2_XII_TEMPORAL_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_XII_TEMPORAL_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
