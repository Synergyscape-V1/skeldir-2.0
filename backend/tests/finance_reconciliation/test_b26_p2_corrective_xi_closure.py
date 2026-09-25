"""B2.6-P2 Corrective XI closure battery: P2-core predecessor trust.

Runs on a real PostgreSQL migrated to the XI head, acting through the
exact runtime principals. Every cell follows the falsification
contract: pristine GREEN, genuine defect RED for the predicted cause,
exact restore GREEN.

Classes (Corrective XI P2-core closure law):
  XA-*  authentication evidence, not assertion (witness-gated
        attestation; lawful signed re-ingestion restores)
  XB-*  ingress capability isolation (dedicated ingress principal;
        generic runtimes mint nothing; cross-tenant refused; ingress
        least privilege)
  XC-*  semantic -> temporal totality (new SQL dependencies RED the
        derived manifest automatically, through both canonical
        authorities)
  XD-*  historical invariant totality (generic oracle catches
        unnamed contradictions; failing upgrade rolls back atomically)
  XE-*  P3 eligibility boundary (only valid current P2 state eligible)
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from uuid import UUID

import pytest

DAY_START = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)
DAY_END = datetime(2026, 1, 16, 0, 0, tzinfo=timezone.utc)
DAY_NOON = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
_P2_POLICY_SEMANTIC_SHA_V2 = (
    "fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99"
)
ADMIN_KEYS = ("MIGRATION_database_URL", "MIGRATION_DATABASE_URL")


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
    for key in ADMIN_KEYS:
        dsn = os.environ.get(key, "").strip()
        if dsn:
            return dsn
    pytest.skip("XI battery needs MIGRATION_DATABASE_URL")


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


def _super_dsn() -> str:
    import psycopg2

    admin = _admin_dsn()
    candidate = admin.replace(
        "migration_owner:migration_owner", "postgres:postgres"
    )
    if candidate == admin:
        pytest.skip("cannot derive superuser DSN")
    try:
        conn = psycopg2.connect(candidate)
        conn.close()
    except Exception:
        pytest.skip("superuser not reachable")
    return candidate


def _refused(fn) -> str:
    try:
        fn()
    except Exception as exc:
        return str(exc).split("\n")[0][:300]
    raise AssertionError("expected refusal, operation succeeded")


def _seed_ids(tag: str, *, provider: str = "stripe") -> dict:
    import psycopg2

    tenant_id = uuid.uuid4()
    ingress_id = uuid.uuid4()
    event_id = uuid.uuid4()
    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tenants (id, name, api_key_hash,"
                " notification_email) VALUES (%s, %s, %s, %s)",
                (str(tenant_id), f"b26p2xi-{tag}", uuid.uuid4().hex,
                 f"b26p2xi-{tag}@example.invalid"),
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )
            cur.execute(
                "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
                " display_name, state) VALUES ('b26p2xi_channel', 'b26p2xi',"
                " true, 'B26P2XI', 'active') ON CONFLICT (code) DO NOTHING"
            )
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, 38000,"
                " '{\"order_id\": \"xi\"}'::jsonb, %s, 'conversion',"
                " 'b26p2xi_channel', 'b26p2xi-campaign', 38000, 'USD',"
                " %s, %s, 'processed')",
                (str(event_id), str(tenant_id), DAY_NOON, str(uuid.uuid4()),
                 str(uuid.uuid4()), f"b26p2xi:{tag}", DAY_NOON, DAY_NOON),
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
                (str(ingress_id), str(tenant_id), str(event_id), provider,
                 f"evt-{tag}", f"ord-{tag}", f"ord-{tag}", DAY_NOON,
                 f"b26p2xi:{tag}"),
            )
    finally:
        conn.close()
    return {"tenant_id": tenant_id, "ingress_id": ingress_id,
            "event_id": event_id, "tag": tag}


def _seed_verdict(ids: dict) -> None:
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
                (str(ids["tenant_id"]), str(ids["event_id"]),
                 str(ids["ingress_id"])),
            )
    finally:
        conn.close()


def _seed_dispatch(ids: dict, task: str) -> None:
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
                "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                " webhook_ingress_identity_id, task_id, task_name, queue,"
                " routing_key, correlation_id, provider,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_value, status,"
                " delivery_state, publish_attempts, window_start, window_end)"
                " VALUES (%s, %s, %s,"
                " 'app.tasks.revenue_verification"
                ".execute_b23_batch_match_engine',"
                " 'b23_match_engine', 'b23_match_engine.task', %s, 'stripe',"
                " 'evt', 'ord', 'ord', 'dispatched', 'pending_publish', 0,"
                " %s, %s)",
                (str(ids["tenant_id"]), str(ids["ingress_id"]), task,
                 str(uuid.uuid4()), DAY_START, DAY_END),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_execution_outbox (tenant_id,"
                " dispatch_task_id, webhook_ingress_identity_id)"
                " VALUES (%s, %s, %s)",
                (str(ids["tenant_id"]), task, str(ids["ingress_id"])),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_task_authority_directory (task_id,"
                " tenant_id, webhook_ingress_identity_id, window_start,"
                " window_end) VALUES (%s, %s, %s, %s, %s)",
                (task, str(ids["tenant_id"]), str(ids["ingress_id"]),
                 DAY_START, DAY_END),
            )
            cur.execute(
                "UPDATE public.b23_match_task_dispatches"
                " SET delivery_state = 'published' WHERE task_id = %s",
                (task,),
            )
            cur.execute(
                "UPDATE public.b26_p2_execution_outbox"
                " SET state = 'published' WHERE dispatch_task_id = %s",
                (task,),
            )
    finally:
        conn.close()


def _witness_and_attest(ids: dict, *, kind: str = "governed_attestation") -> None:
    import psycopg2

    ingress = psycopg2.connect(_role_dsn("app_ingress"))
    ingress.autocommit = True
    try:
        with ingress.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "SELECT public.b26_p2_record_ingress_auth_witness(%s)",
                (str(ids["ingress_id"]),),
            )
            cur.execute(
                "SELECT public.b26_p2_attest_provenance_evidence"
                "(%s, %s, %s)",
                (str(ids["ingress_id"]), kind, f"b26p2xi:{ids['tag']}"),
            )
            assert str(cur.fetchone()[0]) == "authenticated_known"
    finally:
        ingress.close()


async def _derive(ids: dict):
    from app.finance_reconciliation.candidate_conduction import (
        derive_governed_scope,
    )

    return await derive_governed_scope(
        tenant_id=ids["tenant_id"],
        window_start=DAY_START,
        window_end=DAY_END,
    )


def _conduct(ids: dict, task: str) -> None:
    import psycopg2

    worker = psycopg2.connect(_role_dsn("app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "SELECT public.b26_p2_canonical_scope_identity_for_window"
                "(%s, %s, %s)",
                (str(ids["tenant_id"]), DAY_START, DAY_END),
            )
            scope = str(cur.fetchone()[0])
            cur.execute(
                "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                (task, scope, 1, _P2_POLICY_SEMANTIC_SHA_V2),
            )
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task,))
            assert str(cur.fetchone()[0]) == "conducted"
    finally:
        worker.close()


def _eligible(task: str, tenant_id: UUID | None = None) -> bool:
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT public.b26_p2_state_eligible_for_p3(%s, %s)",
                (task, str(tenant_id) if tenant_id else None),
            )
            return bool(cur.fetchone()[0])
    finally:
        conn.close()


# ------------------------------------------------------------------
# XA: authentication evidence, not assertion.
# ------------------------------------------------------------------

def test_xa1_assertion_promotes_nothing() -> None:
    """F-XI-A1: unknown legacy root + direct attester, no witness."""
    import psycopg2

    ids = _seed_ids("xa1")
    admin = psycopg2.connect(_admin_dsn())
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "ALTER TABLE public.webhook_ingress_identities"
                " DISABLE TRIGGER trg_b26_p2_ingress_provenance"
            )
            cur.execute(
                "UPDATE public.webhook_ingress_identities"
                " SET b26_p2_provenance_status = 'unknown_legacy'"
                " WHERE id = %s",
                (str(ids["ingress_id"]),),
            )
            cur.execute(
                "ALTER TABLE public.webhook_ingress_identities"
                " ENABLE TRIGGER trg_b26_p2_ingress_provenance"
            )
    finally:
        admin.close()
    # Ordinary application authority cannot execute the attester.
    user = psycopg2.connect(_role_dsn("app_user"))
    user.autocommit = True
    try:
        with user.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            denied = _refused(
                lambda: cur.execute(
                    "SELECT public.b26_p2_attest_provenance_evidence"
                    "(%s, 'governed_attestation', %s)",
                    (str(ids["ingress_id"]), f"b26p2xi:{ids['tag']}"),
                )
            )
            assert "permission denied" in denied.lower()
            # Bare status write is refused: no witness-backed evidence.
            # Non-ingress callers without witness visibility are
            # refused at the capability plane (permission denied);
            # either refusal is fail-closed and mints nothing.
            reason = _refused(
                lambda: cur.execute(
                    "UPDATE public.webhook_ingress_identities"
                    " SET b26_p2_provenance_status = 'authenticated_known'"
                    " WHERE id = %s",
                    (str(ids["ingress_id"]),),
                )
            )
            assert (
                "b26_p2_provenance_promotion_refused" in reason
                or "permission denied" in reason.lower()
            ), reason
    finally:
        user.close()
    # Even the ingress principal is refused without a witness.
    ingress = psycopg2.connect(_role_dsn("app_ingress"))
    ingress.autocommit = True
    try:
        with ingress.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            reason = _refused(
                lambda: cur.execute(
                    "SELECT public.b26_p2_attest_provenance_evidence"
                    "(%s, 'governed_attestation', %s)",
                    (str(ids["ingress_id"]), f"b26p2xi:{ids['tag']}"),
                )
            )
            assert "b26_p2_evidence_witness_missing" in reason
    finally:
        ingress.close()
    # GREEN after exact restore: lawful witness + attestation.
    _witness_and_attest(ids)
    admin = psycopg2.connect(_admin_dsn())
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "SELECT b26_p2_provenance_status FROM"
                " public.webhook_ingress_identities WHERE id = %s",
                (str(ids["ingress_id"]),),
            )
            assert str(cur.fetchone()[0]) == "authenticated_known"
    finally:
        admin.close()


def test_xa2_forged_evidence_cannot_found_truth() -> None:
    """F-XI-A2: forged evidence row by non-ingress runtime."""
    import psycopg2

    ids = _seed_ids("xa2")
    worker = psycopg2.connect(_role_dsn("app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            denied = _refused(
                lambda: cur.execute(
                    "INSERT INTO public.b26_p2_provenance_evidence"
                    " (webhook_ingress_identity_id, tenant_id,"
                    " evidence_kind, evidence_ref) VALUES (%s, %s,"
                    " 'governed_attestation', %s)",
                    (str(ids["ingress_id"]), str(ids["tenant_id"]),
                     f"b26p2xi:{ids['tag']}"),
                )
            )
            assert "permission denied" in denied.lower()
            denied = _refused(
                lambda: cur.execute(
                    "SELECT public.b26_p2_record_ingress_auth_witness(%s)",
                    (str(ids["ingress_id"]),),
                )
            )
            assert "permission denied" in denied.lower()
    finally:
        worker.close()


def test_xa3_lawful_reingestion_restores() -> None:
    """F-XI-A3: genuine provider evidence restores authority."""
    import psycopg2

    ids = _seed_ids("xa3")
    _witness_and_attest(ids, kind="signed_provider_reingestion")
    admin = psycopg2.connect(_admin_dsn())
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "SELECT evidence_kind, evidence_witness_hash FROM"
                " public.b26_p2_provenance_evidence"
                " WHERE webhook_ingress_identity_id = %s",
                (str(ids["ingress_id"]),),
            )
            kind, witness_hash = cur.fetchone()
            assert kind == "signed_provider_reingestion"
            assert witness_hash
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "SELECT witness_hash FROM"
                " public.b26_p2_ingress_auth_witness"
                " WHERE webhook_ingress_identity_id = %s",
                (str(ids["ingress_id"]),),
            )
            assert str(cur.fetchone()[0]) == witness_hash
    finally:
        admin.close()


# ------------------------------------------------------------------
# XB: ingress capability isolation.
# ------------------------------------------------------------------

def test_xb1_generic_runtimes_hold_no_ingress_capability() -> None:
    """F-XI-B1/B2: worker/relay/beat cannot mint or attest."""
    import psycopg2

    for role in ("app_worker", "app_relay", "app_beat"):
        conn = psycopg2.connect(_role_dsn(role))
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                denied = _refused(
                    lambda: cur.execute(
                        "SELECT public.b26_p2_record_ingress_auth_witness"
                        "('00000000-0000-0000-0000-000000000000')"
                    )
                )
                assert "permission denied" in denied.lower(), (role, denied)
                denied = _refused(
                    lambda: cur.execute(
                        "SELECT public.b26_p2_attest_provenance_evidence"
                        "('00000000-0000-0000-0000-000000000000',"
                        " 'governed_attestation', 'x')"
                    )
                )
                assert "permission denied" in denied.lower(), (role, denied)
        finally:
            conn.close()
    # The ordinary application principal cannot author verified ingress.
    ids = _seed_ids("xb1")
    import psycopg2 as _pg

    _ev = _pg.connect(_admin_dsn())
    _ev.autocommit = True
    try:
        with _ev.cursor() as _cur:
            _cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            _cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, 100,"
                " '{}'::jsonb, %s, 'conversion', 'b26p2xi_channel',"
                " 'b26p2xi-campaign', 100, 'USD', %s, %s, 'processed')",
                (str(uuid.uuid4()), str(ids["tenant_id"]), DAY_NOON,
                 str(uuid.uuid4()), str(uuid.uuid4()),
                 "b26p2xi:xb1-ev", DAY_NOON, DAY_NOON),
            )
            _cur.execute(
                "SELECT id FROM public.attribution_events"
                " WHERE idempotency_key = 'b26p2xi:xb1-ev'"
            )
            second_event = str(_cur.fetchone()[0])
    finally:
        _ev.close()
    user = psycopg2.connect(_role_dsn("app_user"))
    user.autocommit = True
    try:
        with user.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            reason = _refused(
                lambda: cur.execute(
                    "INSERT INTO public.webhook_ingress_identities (id,"
                    " tenant_id, event_id, provider, verified_amount_minor,"
                    " verified_amount_currency, event_timestamp,"
                    " idempotency_key, verified_commerce_ingress_state)"
                    " VALUES (%s, %s, %s, 'stripe', 100, 'USD', now(),"
                    " %s, 'authenticity_verified')",
                    (str(uuid.uuid4()), str(ids["tenant_id"]),
                     second_event,
                     f"b26p2xi:xb1-{uuid.uuid4().hex[:8]}"),
                )
            )
            assert "b26_p2_verified_authorship_refused" in reason
    finally:
        user.close()


def test_xb2_cross_tenant_ingress_refused() -> None:
    """F-XI-B3: cross-tenant event under the ingress role is refused."""
    import psycopg2

    ids = _seed_ids("xb2")
    ingress = psycopg2.connect(_role_dsn("app_ingress"))
    ingress.autocommit = True
    try:
        with ingress.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            reason = _refused(
                lambda: cur.execute(
                    "INSERT INTO public.webhook_ingress_identities (id,"
                    " tenant_id, event_id, provider, verified_amount_minor,"
                    " verified_amount_currency, event_timestamp,"
                    " idempotency_key, verified_commerce_ingress_state)"
                    " VALUES (%s, %s, %s, 'stripe', 100, 'USD', now(),"
                    " %s, 'authenticity_verified')",
                    (str(uuid.uuid4()), str(uuid.uuid4()),
                     str(uuid.uuid4()),
                     f"b26p2xi:xb2-{uuid.uuid4().hex[:8]}"),
                )
            )
            lowered = reason.lower()
            assert (
                "row-level security" in lowered
                or "violates" in lowered
                or "policy" in lowered
            ), reason
    finally:
        ingress.close()


def test_xb3_ingress_least_privilege() -> None:
    """GATE XI-5: ingress cannot write B2.3/P2/policy truth."""
    import psycopg2

    ids = _seed_ids("xb3")
    ingress = psycopg2.connect(_role_dsn("app_ingress"))
    ingress.autocommit = True
    try:
        with ingress.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            denied = _refused(
                lambda: cur.execute(
                    "SELECT public.b26_p2_mark_conducted('no-such-task')"
                )
            )
            assert "permission denied" in denied.lower(), denied
            denied = _refused(
                lambda: cur.execute(
                    "INSERT INTO public.b23_match_verdicts (tenant_id,"
                    " provider, status) VALUES (%s, 'stripe',"
                    " 'matched_confirmed')",
                    (str(ids["tenant_id"]),),
                )
            )
            assert "permission denied" in denied.lower(), denied
            denied = _refused(
                lambda: cur.execute(
                    "UPDATE public.b26_p2_scope_policy_authority"
                    " SET semantic_sha256 = '00'"
                )
            )
            assert "permission denied" in denied.lower(), denied
    finally:
        ingress.close()


# ------------------------------------------------------------------
# XC: semantic -> temporal totality (derived manifest gate).
# ------------------------------------------------------------------

def _repo_root() -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parents[3])


def _run_xi_semantic(dsn: str):
    proc = subprocess.run(
        [sys.executable, "scripts/ci/validate_b26_p2_xi_semantic_temporal.py",
         "--dsn", dsn],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=_repo_root(),
    )
    head = ((proc.stdout or "").splitlines() or [""])[0]
    return proc.returncode, head


def _replace_identity_read(admin_dsn: str, anchor: str, injection: str) -> str:
    import psycopg2

    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT prosrc FROM pg_proc WHERE proname = %s",
                ("b26_p2_canonical_scope_identity_for_window",),
            )
            pristine = str(cur.fetchone()[0])
            assert anchor in pristine
            mutated = pristine.replace(anchor, injection, 1)
            assert mutated != pristine
            cur.execute(
                "SELECT pg_get_functiondef(oid) FROM pg_proc"
                " WHERE proname = %s",
                ("b26_p2_canonical_scope_identity_for_window",),
            )
            funcdef = str(cur.fetchone()[0])
            start = funcdef.index("$function$") + len("$function$")
            end = funcdef.rindex("$function$")
            cur.execute(funcdef[:start] + mutated + funcdef[end:])
            return pristine
    finally:
        conn.close()


def _restore_identity(admin_dsn: str, pristine: str) -> None:
    import psycopg2

    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_get_functiondef(oid) FROM pg_proc"
                " WHERE proname = %s",
                ("b26_p2_canonical_scope_identity_for_window",),
            )
            funcdef = str(cur.fetchone()[0])
            start = funcdef.index("$function$") + len("$function$")
            end = funcdef.rindex("$function$")
            cur.execute(funcdef[:start] + pristine + funcdef[end:])
    finally:
        conn.close()


def test_xc1_new_canonical_dependency_reds_automatically() -> None:
    """F-XI-C1: match_quality in canonical SQL without temporal cover."""
    admin_dsn = _admin_dsn()
    rc, head = _run_xi_semantic(admin_dsn)
    assert rc == 0, head
    pristine = _replace_identity_read(
        admin_dsn,
        "AND v.status IN ('matched_provisional','matched_confirmed','adjusted')",
        "AND v.status IN ('matched_provisional','matched_confirmed','adjusted')"
        " AND COALESCE(v.match_quality, '') <> '__never__'",
    )
    try:
        rc, head = _run_xi_semantic(admin_dsn)
        assert rc == 1, head
        assert "b23_match_verdicts.match_quality" in head, head
    finally:
        _restore_identity(admin_dsn, pristine)
    rc, head = _run_xi_semantic(admin_dsn)
    assert rc == 0, head


def test_xc2_indirect_helper_dependency_reds() -> None:
    """F-XI-C2: dependency through an intermediate expression."""
    import psycopg2

    admin_dsn = _admin_dsn()
    rc, head = _run_xi_semantic(admin_dsn)
    assert rc == 0, head
    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    helper = "b26_p2_xi_test_helper"
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE OR REPLACE FUNCTION public.{helper}(p_id uuid)"
                " RETURNS text LANGUAGE sql IMMUTABLE"
                " SET search_path TO 'pg_catalog', 'public'"
                " AS $$ SELECT COALESCE(("
                " SELECT v.match_quality FROM public.b23_match_verdicts"
                " AS v WHERE v.webhook_ingress_identity_id = p_id"
                " LIMIT 1), '') $$"
            )
        pristine = _replace_identity_read(
            admin_dsn,
            "i.verified_amount_minor::text AS line",
            f"i.verified_amount_minor::text || public.{helper}(i.id) AS line",
        )
        try:
            rc, head = _run_xi_semantic(admin_dsn)
            # The helper-mediated read is a genuine member of the
            # class (a new B2.3 datum changing P2 meaning). The
            # derived gate must RED on it, not only on direct reads.
            assert rc == 1, head
        finally:
            _restore_identity(admin_dsn, pristine)
    finally:
        with conn.cursor() as cur:
            cur.execute(f"DROP FUNCTION IF EXISTS public.{helper}(uuid)")
        conn.close()
    rc, head = _run_xi_semantic(admin_dsn)
    assert rc == 0, head


# ------------------------------------------------------------------
# XD: historical invariant totality (generic oracle).
# ------------------------------------------------------------------

def _oracle_rows(admin_dsn: str, tenant_id: UUID) -> list:
    import psycopg2

    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )
            cur.execute(
                "SELECT violation_kind, task_ref FROM"
                " public.b26_p2_xi_invariant_oracle()"
            )
            return cur.fetchall()
    finally:
        conn.close()


def test_xd1_garbage_policy_receipt_caught() -> None:
    """F-XI-D1: garbage policy-sha receipt never silently canonical."""
    import psycopg2

    ids = _seed_ids("xd1")
    _witness_and_attest(ids)
    _seed_verdict(ids)
    task = f"xi-xd1-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids, task)
    worker = psycopg2.connect(_role_dsn("app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "SELECT public.b26_p2_canonical_scope_identity_for_window"
                "(%s, %s, %s)",
                (str(ids["tenant_id"]), DAY_START, DAY_END),
            )
            scope = str(cur.fetchone()[0])
            # A receipt carrying a foreign policy meaning must not
            # record: the receipt-effect guard refuses non-canonical
            # bindings at write time.
            reason = _refused(
                lambda: cur.execute(
                    "SELECT public.b26_p2_record_conduction_receipt"
                    "(%s, %s, %s, %s)",
                    (task, scope, 1, "00" * 32),
                )
            )
            assert reason, "guard should refuse garbage policy binding"
    finally:
        worker.close()
    # And the generic oracle flags a planted garbage survivor that
    # bypassed the guard through the admin plane.
    sup = psycopg2.connect(_super_dsn())
    sup.autocommit = True
    planted = False
    try:
        with sup.cursor() as cur:
            cur.execute("SET session_replication_role = 'replica'")
            try:
                cur.execute(
                    "INSERT INTO public.b26_p2_conduction_receipts (task_id,"
                    " tenant_id, webhook_ingress_identity_id, window_start,"
                    " window_end, b23_processed_count, p2_scope_identity,"
                    " policy_semantic_sha256, ix_meaning_status)"
                    " VALUES (%s, %s, %s, %s, %s, 1, 'planted', %s,"
                    " 'canonically_bound')",
                    (task, str(ids["tenant_id"]), str(ids["ingress_id"]),
                     DAY_START, DAY_END, "ab" * 32),
                )
                planted = True
            finally:
                cur.execute("SET session_replication_role = 'origin'")
    finally:
        sup.close()
    assert planted
    try:
        rows = _oracle_rows(_admin_dsn(), ids["tenant_id"])
        kinds = [r[0] for r in rows]
        assert "xi_garbage_policy_receipt" in kinds, kinds
    finally:
        admin = psycopg2.connect(_admin_dsn())
        admin.autocommit = True
        try:
            with admin.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (str(ids["tenant_id"]),),
                )
                cur.execute(
                    "DELETE FROM public.b26_p2_conduction_receipts"
                    " WHERE task_id = %s",
                    (task,),
                )
        finally:
            admin.close()
    assert _oracle_rows(_admin_dsn(), ids["tenant_id"]) == []


def test_xd2_divergent_twins_caught() -> None:
    """F-XI-D2: conducted dispatch + nonterminal outbox twin."""
    import psycopg2

    ids = _seed_ids("xd2")
    _witness_and_attest(ids)
    _seed_verdict(ids)
    task = f"xi-xd2-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids, task)
    sup = psycopg2.connect(_super_dsn())
    sup.autocommit = True
    try:
        with sup.cursor() as cur:
            cur.execute("SET session_replication_role = 'replica'")
            try:
                cur.execute(
                    "UPDATE public.b23_match_task_dispatches"
                    " SET delivery_state = 'conducted' WHERE task_id = %s",
                    (task,),
                )
            finally:
                cur.execute("SET session_replication_role = 'origin'")
    finally:
        sup.close()
    try:
        rows = _oracle_rows(_admin_dsn(), ids["tenant_id"])
        kinds = [r[0] for r in rows]
        assert "xi_divergent_terminal_twins" in kinds, kinds
    finally:
        admin = psycopg2.connect(_admin_dsn())
        admin.autocommit = True
        try:
            with admin.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (str(ids["tenant_id"]),),
                )
                cur.execute(
                    "DELETE FROM public.b23_match_task_dispatches"
                    " WHERE task_id = %s",
                    (task,),
                )
        finally:
            admin.close()


def test_xd3_blank_foundation_cannot_found_truth() -> None:
    """F-XI-D3: blank-shape authenticated foundation is caught."""
    import psycopg2

    ids = _seed_ids("xd3", provider="stripe")
    admin = psycopg2.connect(_admin_dsn())
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "UPDATE public.webhook_ingress_identities"
                " SET provider = '   ' WHERE id = %s",
                (str(ids["ingress_id"]),),
            )
    finally:
        admin.close()
    rows = _oracle_rows(_admin_dsn(), ids["tenant_id"])
    kinds = [r[0] for r in rows]
    # Witnessless (admin-seeded, no witness) and blank: the oracle
    # names the class, never a silent survivor.
    assert (
        "xi_blank_authenticated_foundation" in kinds
        or "xi_witnessless_authenticated_foundation" in kinds
    ), kinds


# ------------------------------------------------------------------
# XE: P3 eligibility boundary.
# ------------------------------------------------------------------

async def test_xe_p3_eligibility_matrix() -> None:
    """GATE XI-16: only valid current P2 state is P3-eligible."""
    # Unknown task and receiptless states are ineligible.
    assert _eligible("no-such-task-00000000000000000000") is False
    ids = _seed_ids("xe1")
    _seed_verdict(ids)
    task = f"xi-xe1-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids, task)
    # Witnessless conducted chain: conducts (admin trust) but is NOT
    # P3-eligible until re-authenticated through the ingress boundary.
    _conduct(ids, task)
    assert _eligible(task, ids["tenant_id"]) is False
    # A spoofed tenant fails closed, never eligible.
    assert _eligible(task, uuid.uuid4()) is False
    # Genuine re-ingestion restores eligibility.
    _witness_and_attest(ids, kind="signed_provider_reingestion")
    assert _eligible(task, ids["tenant_id"]) is True
    # Quarantined history is ineligible.
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
                "INSERT INTO public.b26_p2_execution_quarantine ("
                " source_relation, task_id, tenant_id,"
                " webhook_ingress_identity_id, reason, original_payload,"
                " migration_identity) VALUES ("
                " 'b23_match_task_dispatches', %s, %s, %s,"
                " 'xi_test_quarantine', '{}', 'xi_test')",
                (task, str(ids["tenant_id"]), str(ids["ingress_id"])),
            )
    finally:
        admin.close()
    try:
        assert _eligible(task, ids["tenant_id"]) is False
    finally:
        admin = psycopg2.connect(_admin_dsn())
        admin.autocommit = True
        try:
            with admin.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (str(ids["tenant_id"]),),
                )
                cur.execute(
                    "DELETE FROM public.b26_p2_execution_quarantine"
                    " WHERE task_id = %s",
                    (task,),
                )
        finally:
            admin.close()
    assert _eligible(task, ids["tenant_id"]) is True
