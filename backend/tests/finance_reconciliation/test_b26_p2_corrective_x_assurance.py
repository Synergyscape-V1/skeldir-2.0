"""B2.6-P2 Corrective X assurance battery: single authority + effect law.

Runs on a real PostgreSQL migrated to the X head, acting through the
exact runtime principals. Every cell follows the falsification
contract: pristine GREEN, genuine defect RED for the predicted cause,
exact restore GREEN.

Classes (Corrective X assurance-sovereignty law):
  XA-*  single semantic authority (adapter/SQL agreement, thin
        adapter, no second identity implementation, truth-path import
        ban)
  XG-*  effect-bound conducted/receipt invariants (direct writes,
        junk receipts, overload absence)
  XH-*  evidence-backed provenance (bare promotion refused, attester
        restores, re-ingestion chain conducts)
  XO-*  observability execution (inline tick executes, evaluator
        observes scheduler-plane absence)
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
_P2_POLICY_SEMANTIC_SHA_V2 = (
    "fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99"
)
TAB = chr(9)
NBSP = chr(0xA0)


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
    pytest.skip("X battery needs MIGRATION_DATABASE_URL")


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
                (str(tenant_id), f"b26p2x-{tag}", uuid.uuid4().hex,
                 f"b26p2x-{tag}@example.invalid"),
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )
            cur.execute(
                "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
                " display_name, state) VALUES ('b26p2x_channel', 'b26p2x',"
                " true, 'B26P2X', 'active') ON CONFLICT (code) DO NOTHING"
            )
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, 38000,"
                " '{\"order_id\": \"x\"}'::jsonb, %s, 'conversion',"
                " 'b26p2x_channel', 'b26p2x-campaign', 38000, 'USD',"
                " %s, %s, 'processed')",
                (str(event_id), str(tenant_id), DAY_NOON, str(uuid.uuid4()),
                 str(uuid.uuid4()), f"b26p2x:{tag}", DAY_NOON, DAY_NOON),
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
                 f"b26p2x:{tag}"),
            )
    finally:
        conn.close()
    return {"tenant_id": tenant_id, "ingress_id": ingress_id,
            "event_id": event_id}


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


def _seed_dispatch(ids: dict, task: str, *, provider: str = "stripe") -> None:
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
                " VALUES (%s, %s, %s, %s,"
                " 'b23_match_engine', 'b23_match_engine.task', %s, %s,"
                " 'evt', 'ord', 'ord', 'dispatched', 'pending_publish', 0,"
                " %s, %s)",
                (str(ids["tenant_id"]), str(ids["ingress_id"]), task,
                 TASK_NAME, str(uuid.uuid4()), provider, DAY_START, DAY_END),
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


async def _derive(ids: dict):
    from app.finance_reconciliation import candidate_conduction as conduction
    from app.finance_reconciliation.tenant_authority import (
        open_governed_b23_snapshot_session,
    )

    async with open_governed_b23_snapshot_session(
        ids["tenant_id"]
    ) as session:
        return await conduction.derive_governed_scope(
            session,
            tenant_id=ids["tenant_id"],
            window_start=DAY_START,
            window_end=DAY_END,
        )


def _refused(fn) -> str:
    import psycopg2

    try:
        fn()
    except psycopg2.Error as exc:
        return str(exc).split("\n")[0][:300]
    raise AssertionError("expected database refusal, statement succeeded")


async def test_xa_tab_provider_conducts_through_adapter() -> None:
    """XA-01: the former-divergent tab cell conducts with one meaning."""
    ids = _seed_ids("xa-tab", provider=TAB + "stripe")
    _seed_verdict(ids)
    task = f"x-tab-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids, task, provider=TAB + "stripe")
    scope = await _derive(ids)
    assert scope.supported_count == 1
    assert scope.candidates[0].classification.provider == "stripe"
    assert scope.candidates[0].classification.disposition == (
        "SUPPORTED_AND_IN_SCOPE"
    )
    import psycopg2

    worker = psycopg2.connect(_role_dsn("app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute(
                "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                (task, scope.scope_identity, 1, _P2_POLICY_SEMANTIC_SHA_V2),
            )
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task,))
            assert str(cur.fetchone()[0]) == "conducted"
    finally:
        worker.close()


async def test_xa_nbsp_provider_excluded_on_both_planes() -> None:
    """XA-02: Unicode-only whitespace never normalizes (ascii law)."""
    ids = _seed_ids("xa-nbsp", provider=NBSP + "stripe")
    scope = await _derive(ids)
    assert scope.excluded_count == 1
    assert scope.candidates[0].classification.reason == (
        "unsupported_provider_excluded"
    )


async def test_xa_adapter_identity_equals_canonical() -> None:
    """XA-03: the adapter observes identity; it never formats one."""
    ids = _seed_ids("xa-ident")
    _seed_verdict(ids)
    scope = await _derive(ids)
    import psycopg2

    admin = psycopg2.connect(_admin_dsn())
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT public.b26_p2_canonical_scope_identity_for_window"
                "(%s,%s,%s)",
                (str(ids["tenant_id"]), DAY_START, DAY_END),
            )
            assert str(cur.fetchone()[0]) == scope.scope_identity
    finally:
        admin.close()


def test_xa_no_second_identity_implementation() -> None:
    """XA-04: the Python digest formatter is deleted, not deprecated."""
    from app.finance_reconciliation import candidate_conduction

    assert not hasattr(candidate_conduction, "_compute_scope_identity")
    assert candidate_conduction.SCOPE_IDENTITY_VERSION == (
        "b2.6-p2-scope-identity-v3"
    )


def test_xa_truth_path_import_ban() -> None:
    """XA-05: truth-path modules never import the frozen pure surface."""
    import ast
    from pathlib import Path

    banned = {
        "classify_candidate", "normalize_provider", "normalize_currency",
        "normalize_rail", "normalize_provider_set",
        "assert_aggregate_scope_supported",
    }
    truth = {
        "candidate_conduction.py", "conduction_state.py",
        "canonical_sink.py", "dispatch_authority.py",
    }
    base = (
        Path(__file__).resolve().parents[3] / "backend" / "app"
        / "finance_reconciliation"
    )
    for name in sorted(truth):
        tree = ast.parse((base / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (
                node.module or ""
            ).endswith("scope_authority"):
                hit = {a.name for a in node.names} & banned
                assert not hit, f"{name} imports frozen surface: {hit}"
    tasks = (
        Path(__file__).resolve().parents[3] / "backend" / "app" / "tasks"
        / "revenue_verification.py"
    )
    tree = ast.parse(tasks.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (
            node.module or ""
        ).endswith("scope_authority"):
            hit = {a.name for a in node.names} & banned
            assert not hit, f"worker imports frozen surface: {hit}"


def test_xg_direct_outbox_conducted_refused_as_worker() -> None:
    """XG-01: the effect guard refuses twin writes from any path."""
    ids = _seed_ids("xg-direct")
    task = f"x-direct-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids, task)
    import psycopg2

    worker = psycopg2.connect(_role_dsn("app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )

            def attempt() -> None:
                cur.execute(
                    "UPDATE public.b26_p2_execution_outbox"
                    " SET state = 'conducted' WHERE dispatch_task_id = %s",
                    (task,),
                )

            reason = _refused(attempt)
            assert "b26_p2_conducted_effect_refused" in reason
    finally:
        worker.close()


def test_xg_junk_receipt_refused_at_effect_boundary() -> None:
    """XG-02: authoritative-looking receipt evidence needs consequence."""
    ids = _seed_ids("xg-junk")
    task = f"x-junk-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids, task)
    import psycopg2

    admin = psycopg2.connect(_admin_dsn())
    admin.autocommit = True
    try:
        with admin.cursor() as cur:

            def attempt() -> None:
                cur.execute(
                    "INSERT INTO public.b26_p2_conduction_receipts (task_id,"
                    " tenant_id, webhook_ingress_identity_id, window_start,"
                    " window_end, b23_processed_count, p2_scope_identity,"
                    " policy_semantic_sha256, ix_meaning_status)"
                    " VALUES (%s, %s, %s, %s, %s, 1, %s, %s,"
                    " 'canonically_bound')",
                    (task, str(ids["tenant_id"]), str(ids["ingress_id"]),
                     DAY_START, DAY_END, "ab" * 32,
                     _P2_POLICY_SEMANTIC_SHA_V2),
                )

            reason = _refused(attempt)
            assert "b26_p2_receipt_effect_refused" in reason
    finally:
        admin.close()


def test_xg_conducted_signatures_are_singletons() -> None:
    """XG-03: no overload/helper signature carries a write effect."""
    import psycopg2

    admin = psycopg2.connect(_admin_dsn())
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            for name, allowed in (
                ("b26_p2_mark_conducted", 1),
                ("b26_p2_record_conduction_receipt", 1),
            ):
                cur.execute(
                    "SELECT count(*) FROM pg_proc AS p"
                    " JOIN pg_namespace AS n ON n.oid = p.pronamespace"
                    " WHERE n.nspname = 'public' AND p.proname = %s",
                    (name,),
                )
                assert int(cur.fetchone()[0]) == allowed, name
    finally:
        admin.close()


async def test_xh_bare_promotion_refused_attester_restores() -> None:
    """XH-01/02: promotion needs evidence; the attester provides it."""
    ids = _seed_ids("xh-prov")
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
            cur.execute(
                "SELECT idempotency_key FROM public.webhook_ingress_identities"
                " WHERE id = %s",
                (str(ids["ingress_id"]),),
            )
            idem = str(cur.fetchone()[0])
    finally:
        admin.close()
    api = psycopg2.connect(_role_dsn("app_user"))
    api.autocommit = True
    try:
        with api.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )

            def attempt() -> None:
                cur.execute(
                    "UPDATE public.webhook_ingress_identities"
                    " SET b26_p2_provenance_status = 'authenticated_known'"
                    " WHERE id = %s",
                    (str(ids["ingress_id"]),),
                )

            reason = _refused(attempt)
            # Corrective XI: non-ingress callers without witness
            # visibility are refused at the capability plane
            # (permission denied); either refusal mints nothing.
            assert (
                "b26_p2_provenance_promotion_refused" in reason
                or "permission denied" in reason.lower()
            ), reason
            # Corrective XI: caller assertions promote nothing. The
            # ordinary application principal cannot execute the
            # attester at all (permission denied at the grant plane).
            denied = _refused(
                lambda: cur.execute(
                    "SELECT public.b26_p2_attest_provenance_evidence"
                    "(%s, 'governed_attestation', %s)",
                    (str(ids["ingress_id"]), idem),
                )
            )
            assert "permission denied" in denied.lower()
    finally:
        api.close()
    # Corrective XII restoration: predecessor consequence first (API
    # application principal, standing in for the HMAC-verified path),
    # then the bound witness and the signed attestation (ingress
    # principal). governed_attestation is migration/admin custody
    # only and is never exercised here.
    user = psycopg2.connect(_role_dsn("app_user"))
    user.autocommit = True
    try:
        with user.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "SELECT provider_native_event_reference FROM"
                " public.webhook_ingress_identities WHERE id = %s",
                (str(ids["ingress_id"]),),
            )
            evt_ref = str(cur.fetchone()[0])
            cur.execute(
                "SELECT public.b26_p2_record_provider_auth_consequence"
                "(%s, 'stripe', %s, %s, %s,"
                " 'hmac-sha256-timestamped-hex', 'v1')",
                (str(ids["ingress_id"]), evt_ref, "c" * 64, "d" * 64),
            )
    finally:
        user.close()
    ingress = psycopg2.connect(_role_dsn("app_ingress"))
    ingress.autocommit = True
    try:
        with ingress.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(ids["tenant_id"]),),
            )
            cur.execute(
                "SELECT provider_native_event_reference FROM"
                " public.webhook_ingress_identities WHERE id = %s",
                (str(ids["ingress_id"]),),
            )
            evt_ref = str(cur.fetchone()[0])
            cur.execute(
                "SELECT public.b26_p2_record_ingress_auth_witness"
                "(%s, 'stripe', %s, %s)",
                (str(ids["ingress_id"]), evt_ref, "c" * 64),
            )
            cur.execute(
                "SELECT public.b26_p2_attest_provenance_evidence"
                "(%s, 'signed_provider_reingestion', %s)",
                (str(ids["ingress_id"]), idem),
            )
            assert str(cur.fetchone()[0]) == "authenticated_known"
    finally:
        ingress.close()
    # The restored root conducts the full lawful chain.
    _seed_verdict(ids)
    task = f"x-restored-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids, task)
    scope = await _derive(ids)
    import psycopg2 as _pg2

    worker = _pg2.connect(_role_dsn("app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute(
                "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                (task, scope.scope_identity, 1, _P2_POLICY_SEMANTIC_SHA_V2),
            )
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task,))
            assert str(cur.fetchone()[0]) == "conducted"
    finally:
        worker.close()


async def test_xo_inline_tick_executes_and_evaluator_observes() -> None:
    """XO-01/02: the beat plane ticks inline; the relay consumer observes."""
    import subprocess
    import sys

    import psycopg2

    _seed_ids("xo-tick")
    from app.celery_beat import execute_scheduler_plane_tick_inline

    env_key = "B26_P2_BEAT_DATABASE_URL"
    beat_dsn = os.environ.get(env_key, "").strip()
    if not beat_dsn:
        admin = _admin_dsn()
        beat_dsn = admin.replace(
            "migration_owner:migration_owner", "app_beat:app_beat"
        )
        try:
            probe = psycopg2.connect(beat_dsn)
            probe.close()
        except Exception:
            pytest.skip("beat principal not provisioned")
    result = execute_scheduler_plane_tick_inline(
        beat_instance_id=str(uuid.uuid4()), dsn=beat_dsn
    )
    assert result["failed"] == 0
    assert result["ticked"] >= 1
    # The evaluator runs as the relay consumer (its credential), in a
    # fresh process so the test engine (API credential) is never used.
    relay_dsn = _admin_dsn().replace(
        "migration_owner:migration_owner", "app_relay:app_relay"
    )
    if "asyncpg" not in relay_dsn:
        relay_dsn = relay_dsn.replace("postgresql://", "postgresql+asyncpg://")
    env = dict(os.environ)
    env["DATABASE_URL"] = relay_dsn
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [env.get("PYTHONPATH", ""), "backend"])
    )
    proc = subprocess.run(
        [sys.executable, "scripts/ci/run_b26_p2_evaluator_once.py"],
        capture_output=True, text=True, timeout=300, env=env,
        cwd=os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))),
        ),
    )
    assert proc.returncode == 0, proc.stderr[-500:]
    import json as _json

    health = _json.loads((proc.stdout or "").strip().splitlines()[-1])
    assert health["scheduler_plane_absent_total"] == 0
    assert health["status"] in ("ok", "action_required")


def test_xo_scheduler_intercept_single_definition() -> None:
    """XO-03: the inline intercept is the effective apply_entry.

    Regression guard for a shadowed duplicate: exactly one
    apply_entry definition exists on HealingBeatScheduler and it
    dispatches the scheduler-plane entry inline.
    """
    import ast
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "celery_beat.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    scheduler = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and node.name == "HealingBeatScheduler"
    )
    entries = [
        node
        for node in scheduler.body
        if isinstance(node, ast.FunctionDef) and node.name == "apply_entry"
    ]
    assert len(entries) == 1
    body = ast.dump(entries[0])
    assert "B26_P2_SCHEDULER_HEARTBEAT_ENTRY" in body
    assert "_apply_scheduler_plane_tick_inline" in body
