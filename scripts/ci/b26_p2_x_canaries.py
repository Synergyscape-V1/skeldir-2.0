"""B2.6-P2 Corrective X live effect canaries (part of x_authority).

Each canary executes the actual function under actual runtime
principals against live fixtures. The gate evaluates RESULTS: a
prohibited effect that occurs is RED; a refusal for the predicted
cause is GREEN. Nothing is inferred from source names.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

DAY_START = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)
DAY_END = datetime(2026, 1, 16, 0, 0, tzinfo=timezone.utc)
DAY_NOON = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
TASK_NAME = "app.tasks.revenue_verification.execute_b23_batch_match_engine"
POLICY_SEMANTIC_SHA_V2 = (
    "fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99"
)


def _role_dsn(admin_dsn: str, role: str) -> str:
    candidate = admin_dsn.replace(
        "migration_owner:migration_owner", f"{role}:{role}"
    )
    if candidate == admin_dsn:
        raise RuntimeError(f"x_canary_cannot_derive_{role}_dsn")
    return candidate


def _seed_tenant(cur, tag: str) -> str:
    tenant = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO public.tenants (id, name, api_key_hash,"
        " notification_email) VALUES (%s, %s, %s, %s)",
        (tenant, f"x-canary-{tag}", uuid.uuid4().hex,
         f"x-canary-{tag}@example.invalid"),
    )
    cur.execute(
        "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
    )
    cur.execute(
        "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
        " display_name, state) VALUES ('x_canary_chan', 'x_canary',"
        " true, 'XCANARY', 'active') ON CONFLICT (code) DO NOTHING"
    )
    return tenant


def _seed_ingress(cur, tenant: str, tag: str,
                  provider: str = "stripe") -> tuple[str, str]:
    event_id = str(uuid.uuid4())
    ingress_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO public.attribution_events (id, tenant_id,"
        " occurred_at, correlation_id, session_id, revenue_cents,"
        " raw_payload, idempotency_key, event_type, channel,"
        " campaign_id, conversion_value_cents, currency,"
        " event_timestamp, processed_at, processing_status)"
        " VALUES (%s, %s, %s, %s, %s, 38000,"
        " '{\"order_id\": \"x\"}'::jsonb, %s, 'conversion',"
        " 'x_canary_chan', 'x-canary-camp', 38000, 'USD',"
        " %s, %s, 'processed')",
        (event_id, tenant, DAY_NOON, str(uuid.uuid4()), str(uuid.uuid4()),
         f"x-canary:{tag}", DAY_NOON, DAY_NOON),
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
        " %s, 38000, 'USD', %s, %s, 'authenticity_verified')",
        (ingress_id, tenant, event_id, provider, f"evt-{tag}", f"ord-{tag}",
         f"ord-{tag}", DAY_NOON, f"x-canary:{tag}"),
    )
    return ingress_id, event_id


def _seed_verdict(cur, tenant: str, ingress_id: str, event_id: str) -> None:
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
        (tenant, event_id, ingress_id),
    )


def _seed_dispatch(cur, tenant: str, ingress_id: str, task: str) -> None:
    cur.execute(
        "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
        " webhook_ingress_identity_id, task_id, task_name, queue,"
        " routing_key, correlation_id, provider,"
        " provider_native_event_reference,"
        " provider_native_commerce_reference,"
        " normalized_commerce_reference_value, status,"
        " delivery_state, publish_attempts, window_start, window_end)"
        " VALUES (%s, %s, %s, %s,"
        " 'b23_match_engine', 'b23_match_engine.task', %s, 'stripe',"
        " 'evt', 'ord', 'ord', 'dispatched', 'pending_publish', 0,"
        " %s, %s)",
        (tenant, ingress_id, task, TASK_NAME, str(uuid.uuid4()),
         DAY_START, DAY_END),
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
        " SET delivery_state = 'published' WHERE task_id = %s", (task,)
    )
    cur.execute(
        "UPDATE public.b26_p2_execution_outbox"
        " SET state = 'published' WHERE dispatch_task_id = %s", (task,)
    )


def _canonical(cur, tenant: str) -> str:
    cur.execute(
        "SELECT public.b26_p2_canonical_scope_identity_for_window(%s,%s,%s)",
        (tenant, DAY_START, DAY_END),
    )
    return str(cur.fetchone()[0])


def _attempt(cur, sql: str, params: tuple) -> str | None:
    """Run a statement; return None on success, else the refusal head."""
    try:
        cur.execute(sql, params)
    except Exception as exc:  # noqa: BLE001
        return str(exc).split("\n")[0][:300]
    row = None
    try:
        row = cur.fetchone()
    except Exception:  # noqa: BLE001
        pass
    if row is not None:
        return f"SUCCEEDED:{row[0]}"
    return None


def run_canaries(admin_dsn: str, violations: list[str],
                 checks: dict[str, object]) -> None:
    """Execute the live effect canary battery. Results adjudicate."""
    import psycopg2  # type: ignore[import-untyped]  # noqa: PLC0415

    results: dict[str, bool] = {}
    notes: dict[str, str] = {}
    try:
        worker_dsn = _role_dsn(admin_dsn, "app_worker")
        api_dsn = _role_dsn(admin_dsn, "app_user")
    except RuntimeError as exc:
        violations.append(f"x_canary_principal_unavailable:{exc}")
        checks["live_canaries"] = "principal_unavailable"
        return

    admin = psycopg2.connect(admin_dsn)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            # C1: task with no B2.3 verdict must never conduct.
            tenant = _seed_tenant(cur, "c1")
            ingress, _event = _seed_ingress(cur, tenant, "c1")
            task = f"x-c1-{uuid.uuid4().hex[:8]}"
            _seed_dispatch(cur, tenant, ingress, task)
            scope = _canonical(cur, tenant)
        worker = psycopg2.connect(worker_dsn)
        worker.autocommit = True
        try:
            with worker.cursor() as wcur:
                wcur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,),
                )
                refusal = _attempt(
                    wcur,
                    "SELECT public.b26_p2_record_conduction_receipt"
                    "(%s, %s, %s, %s)",
                    (task, scope, 1, POLICY_SEMANTIC_SHA_V2),
                )
                # The recorder binds canonical meaning, not B2.3
                # consequence: recording without a verdict is lawful;
                # the gate below must refuse the terminal.
                results["no_verdict_receipt_recorded"] = (
                    refusal is None or refusal.startswith("SUCCEEDED")
                )
                notes["c1_receipt"] = str(refusal)[:160]
                refusal = _attempt(
                    wcur, "SELECT public.b26_p2_mark_conducted(%s)", (task,)
                )
                results["no_verdict_conducted_refused"] = refusal is not None and (
                    (not refusal.startswith("SUCCEEDED"))
                    and (
                        "no_b23_consequence" in refusal
                        or "effect_refused" in refusal
                    )
                )
                notes["c1_mark"] = str(refusal)[:160]
                # C2: junk scope never records.
                refusal = _attempt(
                    wcur,
                    "SELECT public.b26_p2_record_conduction_receipt"
                    "(%s, %s, %s, %s)",
                    (task, "ab" * 32, 1, POLICY_SEMANTIC_SHA_V2),
                )
                results["junk_scope_refused"] = refusal is not None and (
                    "scope_not_canonical" in refusal
                    or "effect_refused" in refusal
                )
                notes["c2"] = str(refusal)[:160]
                # C6: direct conducted UPDATE as worker is refused.
                refusal = _attempt(
                    wcur,
                    "UPDATE public.b23_match_task_dispatches"
                    " SET delivery_state = 'conducted' WHERE task_id = %s",
                    (task,),
                )
                results["direct_worker_conducted_refused"] = (
                    refusal is not None
                    and "effect_refused" in refusal
                )
                notes["c6"] = str(refusal)[:160]
        finally:
            worker.close()

        with admin.cursor() as cur:
            # C5: published + verdict but no receipt must not conduct.
            tenant5 = _seed_tenant(cur, "c5")
            ingress5, event5 = _seed_ingress(cur, tenant5, "c5")
            task5 = f"x-c5-{uuid.uuid4().hex[:8]}"
            _seed_dispatch(cur, tenant5, ingress5, task5)
            _seed_verdict(cur, tenant5, ingress5, event5)
        worker = psycopg2.connect(worker_dsn)
        worker.autocommit = True
        try:
            with worker.cursor() as wcur:
                wcur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant5,),
                )
                refusal = _attempt(
                    wcur, "SELECT public.b26_p2_mark_conducted(%s)", (task5,)
                )
                results["missing_receipt_conducted_refused"] = (
                    refusal is not None
                    and not refusal.startswith("SUCCEEDED")
                    and ("no_receipt" in refusal or "effect_refused" in refusal)
                )
                notes["c5"] = str(refusal)[:160]
                # C4: wrong-tenant reads never show another tenant's
                # truth (RLS): with tenant5's GUC, tenant C1's rows
                # are invisible.
                wcur.execute(
                    "SELECT count(*) FROM public.b26_p2_conduction_receipts"
                )
                visible = int(wcur.fetchone()[0])
                results["cross_tenant_rows_invisible"] = visible == 0
                notes["c4"] = f"tenant5_visible_receipts={visible}"
        finally:
            worker.close()

        # C8: bare provenance promotion refused; attester restores.
        api = psycopg2.connect(api_dsn)
        api.autocommit = True
        try:
            with admin.cursor() as cur:
                tenant8 = _seed_tenant(cur, "c8")
                ingress8, _e8 = _seed_ingress(cur, tenant8, "c8")
                cur.execute(
                    "ALTER TABLE public.webhook_ingress_identities"
                    " DISABLE TRIGGER trg_b26_p2_ingress_provenance"
                )
                cur.execute(
                    "UPDATE public.webhook_ingress_identities"
                    " SET b26_p2_provenance_status = 'unknown_legacy'"
                    " WHERE id = %s",
                    (ingress8,),
                )
                cur.execute(
                    "ALTER TABLE public.webhook_ingress_identities"
                    " ENABLE TRIGGER trg_b26_p2_ingress_provenance"
                )
                cur.execute(
                    "SELECT idempotency_key FROM"
                    " public.webhook_ingress_identities WHERE id = %s",
                    (ingress8,),
                )
                idem8 = str(cur.fetchone()[0])
            with api.cursor() as acur:
                acur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant8,),
                )
                refusal = _attempt(
                    acur,
                    "UPDATE public.webhook_ingress_identities"
                    " SET b26_p2_provenance_status = 'authenticated_known'"
                    " WHERE id = %s",
                    (ingress8,),
                )
                results["bare_promotion_refused"] = (
                    refusal is not None
                    and "promotion_refused" in refusal
                )
                notes["c8_bare"] = str(refusal)[:160]
                restored = _attempt(
                    acur,
                    "SELECT public.b26_p2_attest_provenance_evidence"
                    "(%s, 'governed_attestation', %s)",
                    (ingress8, idem8),
                )
                results["attester_restores"] = (
                    restored is not None
                    and restored == "SUCCEEDED:authenticated_known"
                )
                notes["c8_attest"] = str(restored)[:160]
        finally:
            api.close()
    finally:
        admin.close()
    checks["live_canaries"] = results
    checks["live_canary_notes"] = notes
    for name, ok in results.items():
        if not ok:
            violations.append(f"x_canary_failed:{name}")
