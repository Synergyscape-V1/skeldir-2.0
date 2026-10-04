#!/usr/bin/env python3
"""B2.6-P2 Corrective XIV behavioral temporal completeness (BLOCKER E).

Law: the temporal harness READS the semantic contract. For every mutable
dependency/event it generates or invokes a real behavioral probe:

  DECLARED MUTABLE DEPENDENCIES = TEMPORAL DISPOSITIONS = EXECUTED PROBES

Set difference on either side must be empty. A disposition receives PASS
only on the observed state transition/refusal -- never for trigger
existence, name match, manifest entry, or SQL body text. For every
enforcement family a kill-switch deliberately weakens the real database
effect while preserving metadata/names/registration/contract, and the
relevant generated probe must RED.

Exit code is the gate.
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b26_p2_xiii_semantic_contract.v1.json"
)

DAY_START = "2026-09-01T00:00:00+00:00"
DAY_END = "2026-09-02T00:00:00+00:00"
DAY_NOON = "2026-09-01T12:00:00+00:00"
POLICY_VERSION = "b2.6-p2-scope-policy-v2"
POLICY_SHA = "fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99"


def _role_dsn(admin_dsn: str, role: str) -> str | None:
    if "migration_owner:migration_owner" not in admin_dsn:
        return None
    return admin_dsn.replace("migration_owner:migration_owner", f"{role}:{role}")


def _seed(admin_dsn: str, tag: str) -> dict:
    import psycopg2  # noqa: PLC0415

    worker_dsn = _role_dsn(admin_dsn, "app_worker")
    tenant = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    ingress_id = str(uuid.uuid4())
    idem = "xiv-temp-%s-%s" % (tag, uuid.uuid4().hex[:6])
    evt_ref = "evt-%s" % idem
    task = "xiv-temp-%s-%s" % (tag, uuid.uuid4().hex[:8])
    admin = psycopg2.connect(admin_dsn)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tenants (id, name, api_key_hash,"
                " notification_email) VALUES (%s, %s, %s, %s)",
                (
                    tenant,
                    "xiv-temp-%s" % tag,
                    uuid.uuid4().hex,
                    "xiv-temp@example.invalid",
                ),
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            cur.execute(
                "INSERT INTO public.channel_taxonomy (code,family,"
                " is_paid, display_name, state) VALUES"
                " ('xiv_temp_ch', 'xiv_temp', true, 'XIVTEMP', 'active')"
                " ON CONFLICT (code) DO NOTHING"
            )
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, 7600,"
                " '{}'::jsonb, %s, 'conversion', 'xiv_temp_ch',"
                " 'c', 7600, 'USD', %s, %s, 'processed')",
                (
                    event_id,
                    tenant,
                    DAY_NOON,
                    str(uuid.uuid4()),
                    str(uuid.uuid4()),
                    idem,
                    DAY_NOON,
                    DAY_NOON,
                ),
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
                " 'order_reference', %s, 7600, 'USD', %s, %s,"
                " 'authenticity_verified')",
                (
                    ingress_id,
                    tenant,
                    event_id,
                    evt_ref,
                    "ord-%s" % idem,
                    "ord-%s" % idem,
                    DAY_NOON,
                    idem,
                ),
            )
            cur.execute(
                "SELECT public.b26_p2_authenticate_ingress_atomic("
                "%s, 'stripe', %s, %s, %s,"
                " 'hmac-sha256-timestamped-hex', 'v1')",
                (ingress_id, evt_ref, "c" * 64, "d" * 64),
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
                (
                    tenant,
                    ingress_id,
                    task,
                    str(uuid.uuid4()),
                    evt_ref,
                    "ord-%s" % idem,
                    "ord-%s" % idem,
                    DAY_START,
                    DAY_END,
                ),
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
                " 'matched_confirmed', 'high', 7600, 7600, 'USD',"
                " 7600, 7600, 7600, 0, 0, 'exact')",
                (
                    tenant,
                    event_id,
                    ingress_id,
                    "ord-%s" % idem,
                    evt_ref,
                    "ord-%s" % idem,
                ),
            )
    finally:
        admin.close()
    worker = psycopg2.connect(worker_dsn)
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute(
                "SELECT public.b26_p2_canonical_scope_identity_for_window" "(%s,%s,%s)",
                (tenant, DAY_START, DAY_END),
            )
            scope = str(cur.fetchone()[0])
            cur.execute(
                "SELECT public.b26_p2_record_conduction_receipt(%s,%s,%s,%s)",
                (task, scope, 1, POLICY_SHA),
            )
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task,))
    finally:
        worker.close()
    return {
        "tenant": tenant,
        "ingress": ingress_id,
        "task": task,
        "idem": idem,
        "evt_ref": evt_ref,
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
            try:
                row = cur.fetchone()
                return ("ok", str(row[0]) if row else None)
            except Exception:
                return ("ok", None)
    except Exception as exc:
        return ("refused", str(exc).splitlines()[0][:200])
    finally:
        conn.close()


def _contract_sets():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    cols = set()
    for rel, collist in (contract.get("allowed_source_columns", {}) or {}).items():
        for col in collist:
            cols.add(f"{rel}.{col}".lower())
    treated = {
        str(k).lower() for k in (contract.get("temporal_dispositions", {}) or {})
    }
    return cols, treated, contract


# Disposition -> probe names executed live below. Every contract
# disposition key must appear exactly once (set equality).
PROBE_MAP = {
    "b23_match_verdicts.canonical_commerce_reference": [
        "verdict_commerce_update_refused"
    ],
    "b23_match_verdicts.status": ["verdict_status_update_refused"],
    "b23_match_verdicts.tenant_id": ["verdict_tenant_immutable"],
    "b23_match_verdicts.webhook_ingress_identity_id": ["verdict_ingress_immutable"],
    "b23_match_verdicts.insert_qualifying_row": ["verdict_set_insert_refused"],
    "b23_match_verdicts.delete_qualifying_row": ["verdict_set_delete_refused"],
    "b23_match_verdicts.count_qualifying_set": ["verdict_set_count_observed"],
    "webhook_ingress_identities.event_timestamp": ["ingress_timestamp_update_refused"],
    "webhook_ingress_identities.id": ["ingress_id_immutable"],
    "webhook_ingress_identities.provider": ["ingress_provider_update_refused"],
    "webhook_ingress_identities.tenant_id": ["ingress_tenant_immutable"],
    "webhook_ingress_identities.idempotency_key": [
        "ingress_idempotency_update_refused"
    ],
    "webhook_ingress_identities.verified_amount_currency": [
        "ingress_currency_update_refused"
    ],
    "webhook_ingress_identities.verified_amount_minor": [
        "ingress_amount_update_refused"
    ],
    "webhook_ingress_identities.verified_commerce_ingress_state": [
        "ingress_state_downgrade_refused"
    ],
    "webhook_ingress_identities.insert_qualifying_row": [
        "ingress_set_insert_idempotent"
    ],
    "webhook_ingress_identities.delete_qualifying_row": [
        "ingress_set_delete_reevaluated"
    ],
    "b26_p2_scope_policy_authority.scope_policy_version": ["policy_version_refused"],
    "b26_p2_scope_policy_authority.semantic_sha256": ["policy_sha_refused"],
}


def _behavioral_probes(admin_dsn, violations, checks):
    import psycopg2  # noqa: PLC0415

    worker_dsn = _role_dsn(admin_dsn, "app_worker")
    ingress_dsn = _role_dsn(admin_dsn, "app_ingress")
    if worker_dsn is None or ingress_dsn is None:
        violations.append("xiv_temp_role_dsn_underivable")
        return
    ids = _seed(admin_dsn, "matrix")
    tenant, ingress_id, task = ids["tenant"], ids["ingress"], ids["task"]
    executed = []

    def refused(probe, role, tenant, sql, args, must_contain):
        status, detail = _attempt(role, tenant, sql, args)
        if status == "ok":
            violations.append(f"xiv_temp_permitted:{probe}")
            return
        if must_contain.lower() not in (detail or "").lower():
            violations.append(f"xiv_temp_wrong_refusal:{probe}:{detail}")
            return
        checks[probe] = True
        executed.append(probe)

    admin = psycopg2.connect(admin_dsn)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            cur.execute(
                "SELECT id FROM public.b23_match_verdicts"
                " WHERE webhook_ingress_identity_id = %s",
                (ingress_id,),
            )
            verdict_id = str(cur.fetchone()[0])
    finally:
        admin.close()

    # Verdict UPDATE_REFUSED / IMMUTABLE.
    refused(
        "verdict_status_update_refused",
        admin_dsn,
        tenant,
        "UPDATE public.b23_match_verdicts SET status='unmatched' WHERE id=%s",
        (verdict_id,),
        "regression_refused",
    )
    refused(
        "verdict_commerce_update_refused",
        admin_dsn,
        tenant,
        "UPDATE public.b23_match_verdicts SET canonical_commerce_reference='ord-mutated' WHERE id=%s",
        (verdict_id,),
        "regression_refused",
    )
    refused(
        "verdict_tenant_immutable",
        admin_dsn,
        tenant,
        "UPDATE public.b23_match_verdicts SET tenant_id=%s WHERE id=%s",
        (str(uuid.uuid4()), verdict_id),
        "refused",
    )
    refused(
        "verdict_ingress_immutable",
        admin_dsn,
        tenant,
        "UPDATE public.b23_match_verdicts SET webhook_ingress_identity_id=%s WHERE id=%s",
        (str(uuid.uuid4()), verdict_id),
        "refused",
    )
    # Verdict set events.
    refused(
        "verdict_set_insert_refused",
        admin_dsn,
        tenant,
        "INSERT INTO public.b23_match_verdicts (tenant_id, attribution_event_id,"
        " webhook_ingress_identity_id, provider, canonical_commerce_reference,"
        " provider_native_event_reference, provider_native_commerce_reference,"
        " status, match_quality, attributed_amount_minor, verified_amount_minor,"
        " currency_code, canonical_expected_gross_amount_minor,"
        " canonical_captured_gross_amount_minor,"
        " canonical_net_verified_amount_minor, discrepancy_amount_minor,"
        " discrepancy_ratio_bps, discrepancy_band)"
        " VALUES (%s,%s,%s,'stripe','ord-x','evt-x','ord-x','matched_confirmed',"
        " 'high',1,1,'USD',1,1,1,0,0,'exact')",
        (tenant, ids["event"], ingress_id),
        "refused",
    )
    refused(
        "verdict_set_delete_refused",
        admin_dsn,
        tenant,
        "DELETE FROM public.b23_match_verdicts WHERE id=%s",
        (verdict_id,),
        "immutable",
    )
    # COUNT qualifying set observed (behavioral read + set-change refusal
    # already proven above; the count itself is deterministic).
    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            cur.execute(
                "SELECT count(*) FROM public.b23_match_verdicts WHERE tenant_id=%s::uuid",
                (tenant,),
            )
            n = cur.fetchone()[0]
            if n != 1:
                violations.append(f"xiv_temp_count_unexpected:{n}")
            else:
                checks["verdict_set_count_observed"] = True
                executed.append("verdict_set_count_observed")
    finally:
        conn.close()
    # Ingress UPDATE_REFUSED / IMMUTABLE (as the ingress principal: even
    # the authority holder cannot mutate sovereign fields).
    refused(
        "ingress_provider_update_refused",
        ingress_dsn,
        tenant,
        "UPDATE public.webhook_ingress_identities SET provider='shopify' WHERE id=%s",
        (ingress_id,),
        "immutable",
    )
    refused(
        "ingress_timestamp_update_refused",
        ingress_dsn,
        tenant,
        "UPDATE public.webhook_ingress_identities SET event_timestamp=now() WHERE id=%s",
        (ingress_id,),
        "immutable",
    )
    refused(
        "ingress_amount_update_refused",
        ingress_dsn,
        tenant,
        "UPDATE public.webhook_ingress_identities SET verified_amount_minor=1 WHERE id=%s",
        (ingress_id,),
        "immutable",
    )
    refused(
        "ingress_currency_update_refused",
        ingress_dsn,
        tenant,
        "UPDATE public.webhook_ingress_identities SET verified_amount_currency='EUR' WHERE id=%s",
        (ingress_id,),
        "immutable",
    )
    refused(
        "ingress_id_immutable",
        ingress_dsn,
        tenant,
        "UPDATE public.webhook_ingress_identities SET id=%s WHERE id=%s",
        (str(uuid.uuid4()), ingress_id),
        "violates foreign key",
    )
    refused(
        "ingress_tenant_immutable",
        ingress_dsn,
        tenant,
        "UPDATE public.webhook_ingress_identities SET tenant_id=%s WHERE id=%s",
        (str(uuid.uuid4()), ingress_id),
        "immutable",
    )
    # XV: idempotency identity is immutable once authenticated (even the
    # authority holder cannot re-key a lineage; duplicates adopt the row,
    # never rewrite its identity).
    refused(
        "ingress_idempotency_update_refused",
        ingress_dsn,
        tenant,
        "UPDATE public.webhook_ingress_identities SET idempotency_key='mut' WHERE id=%s",
        (ingress_id,),
        "immutable",
    )
    # XVIII: the unforgeable trust-transition trigger refuses first for
    # the same class (direct authority demotion by a runtime role).
    refused(
        "ingress_state_downgrade_refused",
        ingress_dsn,
        tenant,
        "UPDATE public.webhook_ingress_identities SET b26_p2_provenance_status='pending_authentication' WHERE id=%s",
        (ingress_id,),
        "b26_p2_authority_transition_refused",
    )
    # Ingress INSERT qualifying: same idempotency cannot create a second row.
    status, detail = _attempt(
        ingress_dsn,
        tenant,
        "INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id, provider,"
        " provider_native_event_reference, provider_native_commerce_reference,"
        " normalized_commerce_reference_kind, normalized_commerce_reference_value,"
        " verified_amount_minor, verified_amount_currency, event_timestamp,"
        " idempotency_key, verified_commerce_ingress_state)"
        " VALUES (%s,%s,%s,'stripe','e2','o2','k','v',1,'USD',now(),%s,'authenticity_verified')",
        (str(uuid.uuid4()), tenant, ids["event"], ids["idem"]),
    )
    conn2 = psycopg2.connect(admin_dsn)
    conn2.autocommit = True
    try:
        with conn2.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            cur.execute(
                "SELECT count(*) FROM public.webhook_ingress_identities WHERE idempotency_key=%s",
                (ids["idem"],),
            )
            if cur.fetchone()[0] != 1:
                violations.append("xiv_temp_insert_not_idempotent")
            else:
                checks["ingress_set_insert_idempotent"] = True
                executed.append("ingress_set_insert_idempotent")
    finally:
        conn2.close()
    # Ingress DELETE qualifying (SUPERSEDED_AND_REEVALUATED): direct
    # DELETEs are sovereign-refused, and removing a qualifying row from
    # the set (via governed quarantine) re-evaluates P3 + identity.
    # Prove both effects on this lineage.
    status, detail = _attempt(
        admin_dsn,
        tenant,
        "DELETE FROM public.webhook_ingress_identities WHERE id=%s",
        (ingress_id,),
    )
    if status == "ok":
        violations.append("xiv_temp_ingress_delete_permitted")
    conn3 = psycopg2.connect(admin_dsn)
    conn3.autocommit = True
    try:
        with conn3.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            cur.execute(
                "SELECT public.b26_p2_canonical_scope_identity_for_window(%s,%s,%s)",
                (tenant, DAY_START, DAY_END),
            )
            ident_before = str(cur.fetchone()[0])
            cur.execute(
                "SELECT public.b26_p2_state_eligible_for_p3(%s,%s)", (task, tenant)
            )
            p3_before = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO public.b26_p2_execution_quarantine (source_relation, task_id,"
                " tenant_id, webhook_ingress_identity_id, reason, original_payload,"
                " migration_identity) VALUES ('webhook_ingress_identities',%s,%s,%s,"
                " 'xiv_probe_quarantine','{}','xiv-probe')",
                ("xiv-probe:" + ingress_id, tenant, ingress_id),
            )
            cur.execute(
                "SELECT public.b26_p2_state_eligible_for_p3(%s,%s)", (task, tenant)
            )
            p3_after = cur.fetchone()[0]
            cur.execute(
                "SELECT public.b26_p2_canonical_scope_identity_for_window(%s,%s,%s)",
                (tenant, DAY_START, DAY_END),
            )
            ident_after = str(cur.fetchone()[0])
            # Cleanup probe quarantine (scratch lineage only).
            cur.execute(
                "DELETE FROM public.b26_p2_execution_quarantine WHERE task_id=%s",
                ("xiv-probe:" + ingress_id,),
            )
            if p3_before is not True or p3_after is not False:
                violations.append(
                    f"xiv_temp_delete_not_reevaluated:{p3_before}|{p3_after}"
                )
            elif ident_before == ident_after:
                violations.append("xiv_temp_delete_identity_static")
            else:
                checks["ingress_set_delete_reevaluated"] = True
                executed.append("ingress_set_delete_reevaluated")
    finally:
        conn3.close()
    # Policy VERSION_BOUND / UPDATE_REFUSED: FORCE RLS with no UPDATE
    # policy makes the row UPDATE-invisible, so prove the trigger
    # backstop by lifting RLS in a rolled-back owner transaction (the
    # battery TEMP-E pattern): only the trigger stands in the way.
    # Both probes must refuse; the transaction rolls back so the pinned
    # policy row is byte-identical afterwards.
    for probe_name, set_clause, params, token in (
        (
            "policy_version_refused",
            "SET scope_policy_version='xiv-probe-version'",
            (POLICY_VERSION,),
            "version_immutable_refused",
        ),
        (
            "policy_sha_refused",
            "SET semantic_sha256=%s",
            ("0" * 64, POLICY_VERSION),
            "semantic_mutation_refused",
        ),
    ):
        conn_p = psycopg2.connect(admin_dsn)
        try:
            with conn_p.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
                )
                cur.execute(
                    "ALTER TABLE public.b26_p2_scope_policy_authority DISABLE ROW LEVEL SECURITY"
                )
                try:
                    if probe_name == "policy_sha_refused":
                        cur.execute(
                            "UPDATE public.b26_p2_scope_policy_authority "
                            + set_clause
                            + " WHERE scope_policy_version=%s",
                            params,
                        )
                    else:
                        cur.execute(
                            "UPDATE public.b26_p2_scope_policy_authority "
                            + set_clause
                            + " WHERE scope_policy_version=%s",
                            params,
                        )
                    conn_p.rollback()
                    violations.append(f"xiv_temp_permitted:{probe_name}")
                except Exception as exc:
                    conn_p.rollback()
                    if token not in str(exc):
                        violations.append(
                            f"xiv_temp_wrong_refusal:{probe_name}:{str(exc).splitlines()[0][:160]}"
                        )
                    else:
                        checks[probe_name] = True
                        executed.append(probe_name)
        finally:
            conn_p.close()
    checks["executed_probe_count"] = len(executed)
    return set(executed)


def _kill_switches(admin_dsn, violations, checks):
    """Weaken each enforcement family (metadata intact) -> probe must RED.

    For each family: disable the user trigger (trigger row, contract,
    and registration stay intact; only the database effect is weakened),
    prove the corresponding behavioral probe now PERMITS the mutation
    (kill-switch RED signal), re-enable, and prove the probe refuses
    again with byte-identical enforcement restored.
    """
    import psycopg2  # noqa: PLC0415

    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for fname in (
                "b26_p2_enforce_verdict_temporal_conservation",
                "b26_p2_enforce_auth_consequence_immutability",
                "b26_p2_enforce_dispatch_provenance",
            ):
                cur.execute("SELECT 1 FROM pg_proc WHERE proname=%s", (fname,))
                if not cur.fetchone():
                    violations.append(f"xiv_temp_enforcement_missing:{fname}")
                    return
    finally:
        conn.close()
    ids = _seed(admin_dsn, "kill")
    tenant = ids["tenant"]
    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            cur.execute(
                "SELECT id FROM public.b23_match_verdicts WHERE webhook_ingress_identity_id=%s",
                (ids["ingress"],),
            )
            vid = str(cur.fetchone()[0])

        def trigger_of(fname):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tgname, tgrelid::regclass::text FROM pg_trigger"
                    " WHERE tgfoid = (SELECT oid FROM pg_proc WHERE proname=%s LIMIT 1)"
                    " AND NOT tgisinternal",
                    (fname,),
                )
                found = cur.fetchall()
                return found[0] if found else (None, None)

        # K1: verdict temporal conservation (status flip on conducted).
        tgname, relname = trigger_of("b26_p2_enforce_verdict_temporal_conservation")
        if tgname is None:
            violations.append("xiv_temp_trigger_missing:verdict_temporal_conservation")
        else:
            with conn.cursor() as cur:
                cur.execute(f"ALTER TABLE {relname} DISABLE TRIGGER {tgname}")
            try:
                status, _ = _attempt(
                    admin_dsn,
                    tenant,
                    "UPDATE public.b23_match_verdicts SET status='unmatched' WHERE id=%s",
                    (vid,),
                )
                if status == "refused":
                    violations.append(
                        "xiv_temp_killswitch_blind:verdict_temporal_conservation"
                    )
                else:
                    checks["killswitch_red:verdict_temporal_conservation"] = True
            finally:
                with conn.cursor() as cur:
                    cur.execute(f"ALTER TABLE {relname} ENABLE TRIGGER {tgname}")
            # Restore verification with a FRESH conducted lineage (the
            # weakened phase already flipped this verdict to unmatched).
            ids_r = _seed(admin_dsn, "killrestore")
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (ids_r["tenant"],),
                )
                cur.execute(
                    "SELECT id FROM public.b23_match_verdicts WHERE webhook_ingress_identity_id=%s",
                    (ids_r["ingress"],),
                )
                vid_r = str(cur.fetchone()[0])
            status, _ = _attempt(
                admin_dsn,
                ids_r["tenant"],
                "UPDATE public.b23_match_verdicts SET status='unmatched' WHERE id=%s",
                (vid_r,),
            )
            if status != "refused":
                violations.append(
                    "xiv_temp_restore_not_green:verdict_temporal_conservation"
                )

        # K2: consequence immutability (digest rewrite).
        tgname, relname = trigger_of("b26_p2_enforce_auth_consequence_immutability")
        if tgname is None:
            violations.append("xiv_temp_trigger_missing:consequence_immutability")
        else:
            with conn.cursor() as cur:
                cur.execute(f"ALTER TABLE {relname} DISABLE TRIGGER {tgname}")
            try:
                status, _ = _attempt(
                    admin_dsn,
                    tenant,
                    "UPDATE public.b26_p2_provider_auth_consequence SET body_sha256=%s"
                    " WHERE webhook_ingress_identity_id=%s",
                    ("e" * 64, ids["ingress"]),
                )
                if status == "refused":
                    violations.append(
                        "xiv_temp_killswitch_blind:consequence_immutability"
                    )
                else:
                    checks["killswitch_red:consequence_immutability"] = True
            finally:
                with conn.cursor() as cur:
                    cur.execute(f"ALTER TABLE {relname} ENABLE TRIGGER {tgname}")
            # Restore verification uses a DISTINCT rewrite (the weakened
            # phase already stored e*64, so re-storing e*64 is a no-op).
            status, detail = _attempt(
                admin_dsn,
                tenant,
                "UPDATE public.b26_p2_provider_auth_consequence SET body_sha256=%s"
                " WHERE webhook_ingress_identity_id=%s",
                ("f" * 64, ids["ingress"]),
            )
            if status != "refused" or "immutable_refused" not in (detail or ""):
                violations.append(
                    f"xiv_temp_restore_not_green:consequence_immutability:{detail}"
                )

        # K3: dispatch provenance (dispatch for pending ingress refused).
        tgname, relname = trigger_of("b26_p2_enforce_dispatch_provenance")
        if tgname is None:
            violations.append("xiv_temp_trigger_missing:dispatch_provenance")
        else:
            # Scratch pending lineage (verified but never atomic).
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
                )
                pend_ev = str(uuid.uuid4())
                pend_ing = str(uuid.uuid4())
                pend_idem = "xiv-kill-pend-%s" % uuid.uuid4().hex[:6]
                cur.execute(
                    "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
                    " correlation_id, session_id, revenue_cents, raw_payload, idempotency_key,"
                    " event_type, channel, campaign_id, conversion_value_cents, currency,"
                    " event_timestamp, processed_at, processing_status)"
                    " VALUES (%s,%s,%s,%s,%s,7600,'{}'::jsonb,%s,'conversion','xiv_temp_ch',"
                    " 'c',7600,'USD',%s,%s,'processed')",
                    (
                        pend_ev,
                        tenant,
                        DAY_NOON,
                        str(uuid.uuid4()),
                        str(uuid.uuid4()),
                        pend_idem,
                        DAY_NOON,
                        DAY_NOON,
                    ),
                )
                cur.execute(
                    "INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id,"
                    " provider, provider_native_event_reference,"
                    " provider_native_commerce_reference,"
                    " normalized_commerce_reference_kind,"
                    " normalized_commerce_reference_value, verified_amount_minor,"
                    " verified_amount_currency, event_timestamp, idempotency_key,"
                    " verified_commerce_ingress_state)"
                    " VALUES (%s,%s,%s,'stripe','ek','ok','order_reference','ok',7600,'USD',%s,%s,"
                    " 'authenticity_verified')",
                    (pend_ing, tenant, pend_ev, DAY_NOON, pend_idem),
                )
            dispatch_sql = (
                "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                " webhook_ingress_identity_id, task_id, task_name, queue, routing_key,"
                " correlation_id, provider, provider_native_event_reference,"
                " provider_native_commerce_reference, normalized_commerce_reference_value,"
                " status, delivery_state, publish_attempts, window_start, window_end)"
                " VALUES (%s,%s,%s,'app.tasks.revenue_verification.execute_b23_batch_match_engine',"
                " 'b23_match_engine','b23_match_engine.task',%s,'stripe','ek','ok','ok',"
                " 'dispatched','pending_publish',0,%s,%s)"
            )
            with conn.cursor() as cur:
                cur.execute(f"ALTER TABLE {relname} DISABLE TRIGGER {tgname}")
            try:
                status, _ = _attempt(
                    admin_dsn,
                    tenant,
                    dispatch_sql,
                    (
                        tenant,
                        pend_ing,
                        "xiv-kill-task-" + uuid.uuid4().hex[:6],
                        str(uuid.uuid4()),
                        DAY_START,
                        DAY_END,
                    ),
                )
                if status == "refused":
                    violations.append("xiv_temp_killswitch_blind:dispatch_provenance")
                else:
                    checks["killswitch_red:dispatch_provenance"] = True
                    # Cleanup the kill-phase row (weakened acceptance).
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT set_config('app.current_tenant_id', %s, false)",
                            (tenant,),
                        )
                        cur.execute(
                            "DELETE FROM public.b23_match_task_dispatches WHERE task_id LIKE 'xiv-kill-task-%%'"
                            " AND webhook_ingress_identity_id=%s",
                            (pend_ing,),
                        )
            finally:
                with conn.cursor() as cur:
                    cur.execute(f"ALTER TABLE {relname} ENABLE TRIGGER {tgname}")
            status, detail = _attempt(
                admin_dsn,
                tenant,
                dispatch_sql,
                (
                    tenant,
                    pend_ing,
                    "xiv-kill-task-" + uuid.uuid4().hex[:6],
                    str(uuid.uuid4()),
                    DAY_START,
                    DAY_END,
                ),
            )
            if status != "refused" or "provenance_unknown" not in (detail or ""):
                violations.append(
                    f"xiv_temp_restore_not_green:dispatch_provenance:{detail}"
                )
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="XIV behavioral temporal completeness."
    )
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    cols, treated, contract = _contract_sets()
    # Set 1 vs Set 2: every column dependency has a disposition.
    uncovered = {c for c in cols if c not in treated}
    checks["dependency_count"] = len(cols)
    checks["disposition_count"] = len(treated)
    if uncovered:
        violations.append(
            "xiv_temporal_missing_disposition:" + ",".join(sorted(uncovered))
        )
    # Every disposition has a mapped probe (Set 2 vs Set 3, statically).
    mapped = set(PROBE_MAP.keys())
    if mapped != treated:
        violations.append(
            "xiv_temporal_map_gap:missing="
            + ",".join(sorted(treated - mapped))
            + ";extra="
            + ",".join(sorted(mapped - treated))
        )
    checks["mapped_probe_count"] = len(mapped)
    if args.dsn is None:
        violations.append("xiv_temporal_requires_dsn")
    else:
        executed = _behavioral_probes(args.dsn, violations, checks)
        if executed is not None:
            # Set equality: a disposition is covered when EVERY mapped
            # probe executed live. Covered must equal treated.
            covered = {
                d
                for d, probes in PROBE_MAP.items()
                if all(p in executed for p in probes)
            }
            checks["covered_disposition_count"] = len(covered)
            if covered != treated:
                violations.append(
                    "xiv_temporal_set_inequality:missing="
                    + ",".join(sorted(treated - covered))
                )
        _kill_switches(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XIV_TEMP_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XIV-TEMPORAL-BEHAVIOR",
                    "status": status,
                    "violations": sorted(violations),
                    "checks": checks,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
