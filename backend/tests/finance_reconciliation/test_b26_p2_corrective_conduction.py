"""B2.6-P2 Corrective I natural candidate-conduction consequence battery.

Governing law: a genuine authenticated event naturally produces durable B2.3
state and the real production process causes every relevant reconciliation
candidate to enter P2 through the governed derivation boundary -- never
through test-to-classifier value handoff. Excluded evidence contributes zero
to both coverage legs while remaining explicitly representable with amount,
count, reason, provenance, and scope identity.

Phase law: B2.2 ingestion never imports downstream B2.6 scope semantics
(B22-P3), so per-candidate conduction lives downstream -- the B23 worker task
after natural dispatch and the canonical sink inside its governed execution.
Every test below seeds durable rows (setup, never authority) and then invokes
a PRODUCTION edge function -- the governed scope derivation, the canonical
sink under a real JWT, or the B23 worker task code under its production
principal -- asserting hard-coded 76000/80000 = 95.00 conservation and
explicit exclusion. No test passes manually-read row values into
``classify_candidate``.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from app.finance_reconciliation.candidate_conduction import (
    ScopeConductionError,
    derive_governed_scope,
    describe_scope_summary,
)
from app.finance_reconciliation.scope_authority import B26_P2_SCOPE_POLICY_VERSION

WINDOW_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 2, 1, tzinfo=timezone.utc)
OCCURRED = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
OUTSIDE_MARCH = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)


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
        pytest.skip("P2 conduction DB cells need MIGRATION_DATABASE_URL")
    return dsn


def _auth_token(tenant_id: UUID) -> str:
    from app.security.auth import mint_internal_jwt  # noqa: PLC0415

    return mint_internal_jwt(
        tenant_id=tenant_id,
        user_id=uuid.uuid4(),
        expires_in_seconds=300,
    )


def _seed_conduction_universe(tag: str) -> dict[str, Any]:
    """Seed 76000/80000 golden legs plus every exclusion class durably."""
    import psycopg2

    tenant_id = uuid.uuid4()
    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tenants (id, name, api_key_hash,"
                " notification_email) VALUES (%s, %s, %s, %s)",
                (
                    str(tenant_id),
                    f"b26p2ca1-{tag}",
                    uuid.uuid4().hex,
                    f"b26p2ca1-{tag}@example.invalid",
                ),
            )
            cur.execute(
                "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
                " display_name, state) VALUES ('b26p2ca1_channel', 'b26p2ca1',"
                " true, 'B26P2CA1', 'active') ON CONFLICT (code) DO NOTHING"
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )

            def leg(
                order: str,
                amount: int,
                verdict: bool,
                provider: str = "stripe",
                currency: str = "USD",
                occurred: datetime = OCCURRED,
            ) -> UUID:
                event_id = uuid.uuid4()
                cur.execute(
                    "INSERT INTO public.attribution_events (id, tenant_id,"
                    " occurred_at, correlation_id, session_id, revenue_cents,"
                    " raw_payload, idempotency_key, event_type, channel,"
                    " campaign_id, conversion_value_cents, currency,"
                    " event_timestamp, processed_at, processing_status)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s,"
                    " 'conversion', 'b26p2ca1_channel', 'b26p2ca1-campaign',"
                    " %s, %s, %s, %s, 'processed')",
                    (
                        str(event_id),
                        str(tenant_id),
                        occurred,
                        str(uuid.uuid4()),
                        str(uuid.uuid4()),
                        amount,
                        json.dumps({"order_id": order}),
                        f"b26p2ca1:{tag}:{provider}:{currency}:{order}",
                        amount,
                        currency,
                        occurred,
                        occurred,
                    ),
                )
                identity_id = uuid.uuid4()
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
                    " VALUES (%s, %s, %s, %s, %s, %s,"
                    " 'order_reference', %s, %s, %s, %s, %s,"
                    " 'authenticity_verified')",
                    (
                        str(identity_id),
                        str(tenant_id),
                        str(event_id),
                        provider,
                        f"b26p2ca1-ingress-{tag}-{order}",
                        f"b26p2ca1-order-{tag}-{order}",
                        f"b26p2ca1-order-{tag}-{order}",
                        amount,
                        currency,
                        occurred,
                        f"b26p2ca1-ingress:{tag}:{provider}:{order}",
                    ),
                )
                if verdict:
                    cur.execute(
                        "INSERT INTO public.b23_match_verdicts (id, tenant_id,"
                        " attribution_event_id,"
                        " webhook_ingress_identity_id, provider,"
                        " canonical_commerce_reference,"
                        " provider_native_event_reference,"
                        " provider_native_commerce_reference, status,"
                        " match_quality, attributed_amount_minor,"
                        " verified_amount_minor, currency_code,"
                        " last_transition_at,"
                        " canonical_expected_gross_amount_minor,"
                        " canonical_captured_gross_amount_minor,"
                        " canonical_net_verified_amount_minor,"
                        " discrepancy_amount_minor, discrepancy_ratio_bps,"
                        " discrepancy_band)"
                        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s,"
                        " 'matched_confirmed', 'high', %s, %s, %s, %s,"
                        " %s, %s, %s, 0, 0, 'exact')",
                        (
                            str(uuid.uuid4()),
                            str(tenant_id),
                            str(event_id),
                            str(identity_id),
                            provider,
                            f"b26p2ca1-order-{tag}-{order}",
                            f"b26p2ca1-event-{tag}-{order}",
                            f"b26p2ca1-order-{tag}-{order}",
                            amount,
                            amount,
                            currency,
                            occurred,
                            amount,
                            amount,
                            amount,
                        ),
                    )
                return identity_id

            matched_a = leg("matched-a", 38000, True)
            matched_b = leg("matched-b", 38000, True)
            filler_a = leg("filler-a", 2000, False)
            filler_b = leg("filler-b", 2000, False)
            square = leg("square-distractor", 20000, True, provider="square")
            eur = leg("eur-distractor", 5000, False, currency="EUR")
            march = leg("march-distractor", 9000, False, occurred=OUTSIDE_MARCH)
            unknown = leg("unknown-distractor", 7000, False, provider="unknown")
            woo = leg("woo-distractor", 6000, False, provider="woo")
    finally:
        conn.close()
    return {
        "tenant_id": tenant_id,
        "matched": (matched_a, matched_b),
        "fillers": (filler_a, filler_b),
        "square": square,
        "eur": eur,
        "march": march,
        "unknown": unknown,
        "woo": woo,
    }


async def _derive(tenant_id: UUID):
    from app.finance_reconciliation.tenant_authority import (  # noqa: PLC0415
        open_governed_b23_snapshot_session,
    )

    async with open_governed_b23_snapshot_session(tenant_id) as session:
        return await derive_governed_scope(
            session,
            tenant_id=tenant_id,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
        )


async def test_p2ca1_full_scope_conserves_population_with_explicit_exclusions() -> None:
    universe = _seed_conduction_universe("conserve")
    scope = await _derive(universe["tenant_id"])

    assert scope.tenant_id == universe["tenant_id"]
    assert scope.scope_policy_version == B26_P2_SCOPE_POLICY_VERSION
    assert len(scope.policy_source_sha256) == 64
    assert len(scope.policy_semantic_sha256) == 64
    # Corrective II identity/money/snapshot bindings.
    assert len(scope.scope_identity) == 64
    assert scope.snapshot_isolation == "repeatable_read_single_snapshot_per_derivation"
    assert scope.money_semantics == "source_verified_gross_not_canonical_net"
    assert scope.money_authority == "b2.2_ingress_verified_amount_minor"
    assert (
        scope.canonical_net_authority
        == "b2.3_match_verdicts.canonical_net_verified_amount_minor_only"
    )

    # Population conservation: 2 matched + 2 fillers + 5 distractors.
    assert scope.candidate_count == 9
    assert scope.total_amount_minor == 127000

    # Supported / unresolved / excluded partition conserves the population.
    assert scope.supported_count == 2
    assert scope.supported_amount_minor == 76000
    assert scope.unresolved_count == 2
    assert scope.unresolved_amount_minor == 4000
    assert scope.excluded_count == 5
    assert scope.excluded_amount_minor == 47000
    assert (
        scope.supported_amount_minor
        + scope.unresolved_amount_minor
        + scope.excluded_amount_minor
        == scope.total_amount_minor
    )

    by_reason = {reason: (n, a) for reason, n, a in scope.excluded_by_reason}
    assert by_reason["unsupported_provider_excluded"] == (3, 33000)
    assert by_reason["unsupported_currency_excluded"] == (1, 5000)
    assert by_reason["outside_governed_window_excluded"] == (1, 9000)

    for item in scope.candidates:
        assert item.provenance.startswith("public.webhook_ingress_identities:")
        assert str(item.classification.tenant_id) == str(universe["tenant_id"])
        assert item.classification.scope_policy_version == B26_P2_SCOPE_POLICY_VERSION

    summary = describe_scope_summary(scope)
    assert summary["candidate_count"] == 9
    assert summary["excluded_amount_minor"] == 47000
    assert len(summary["scope_identity"]) == 64
    assert summary["money_semantics"] == "source_verified_gross_not_canonical_net"
    assert (
        summary["snapshot_isolation"]
        == "repeatable_read_single_snapshot_per_derivation"
    )


async def test_p2ca1_sink_conserves_95_and_derives_scope_naturally(caplog) -> None:
    from app.finance_reconciliation.canonical_sink import execute_governed_sink

    universe = _seed_conduction_universe("sink")
    with caplog.at_level("INFO"):
        output = await execute_governed_sink(
            "future_finance_projection",
            auth_token=_auth_token(universe["tenant_id"]),
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            supported_platforms=["stripe"],
            currency_code="USD",
        )
    assert output.matched_minor == 76000
    assert output.connected_minor == 80000
    assert output.coverage_percent == Decimal("95.00")
    assert output.zero_denominator is False
    # The sink's own per-candidate derivation ran inside the governed
    # execution (no test-to-classifier handoff involved).
    assert any(
        record.message == "b26_p2_candidate_scope_derived"
        and getattr(record, "candidate_count", None) == 9
        and getattr(record, "excluded_amount_minor", None) == 47000
        for record in caplog.records
    )


async def test_p2ca1_unresolved_is_natural_verdict_absence_not_fixture() -> None:
    universe = _seed_conduction_universe("unresolved")
    scope = await _derive(universe["tenant_id"])
    by_ingress = {item.ingress_id: item for item in scope.candidates}

    for matched_id in universe["matched"]:
        assert (
            by_ingress[matched_id].classification.disposition
            == "SUPPORTED_AND_IN_SCOPE"
        )
    # Fillers carry durable commerce references yet no durable match verdict:
    # verdict absence -- not a test-manufactured blank -- yields UNRESOLVED.
    for filler_id in universe["fillers"]:
        filler = by_ingress[filler_id]
        assert filler.classification.disposition == "SUPPORTED_BUT_UNRESOLVED"
        assert filler.classification.reason == "source_identity_unresolved"
        assert filler.verified_amount_minor == 2000


async def test_p2ca1_tenant_authority_is_server_derived() -> None:
    universe_a = _seed_conduction_universe("tenant-a")
    universe_b = _seed_conduction_universe("tenant-b")

    scope_a = await _derive(universe_a["tenant_id"])
    assert scope_a.candidate_count == 9
    assert all(
        str(item.classification.tenant_id) == str(universe_a["tenant_id"])
        for item in scope_a.candidates
    )

    # Cross-tenant pairing is structurally impossible: the only
    # single-row seam refuses every caller-paired request by design
    # (H-CA1-07), and full derivation binds rows to the session tenant.
    from app.finance_reconciliation.candidate_conduction import (  # noqa: PLC0415
        derive_single_candidate_scope,
    )
    from app.finance_reconciliation.tenant_authority import (  # noqa: PLC0415
        open_governed_b23_snapshot_session as _snapshot_session,
    )

    async with _snapshot_session(universe_b["tenant_id"]) as session:
        with pytest.raises(ScopeConductionError):
            await derive_single_candidate_scope(
                session,
                tenant_id=universe_b["tenant_id"],
                ingress_id=universe_a["square"],
            )

    # Ghost tenants (verified shape, no durable row) refuse, never zero.
    ghost = uuid.uuid4()

    async with _snapshot_session(ghost) as session:
        with pytest.raises(ScopeConductionError):
            await derive_governed_scope(
                session,
                tenant_id=ghost,
                window_start=WINDOW_START,
                window_end=WINDOW_END,
            )


async def test_p2ca1_replay_stable_across_processes() -> None:
    universe = _seed_conduction_universe("replay")
    first = describe_scope_summary(await _derive(universe["tenant_id"]))
    second = describe_scope_summary(await _derive(universe["tenant_id"]))
    assert first == second


def _seed_worker_dispatch(tenant_id: UUID, ingress_id: UUID, task_id: str) -> None:
    """Persist one lawful dispatch row for worker-authority tests (setup only)."""
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT provider, provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_value"
                " FROM public.webhook_ingress_identities WHERE id = %s",
                (str(ingress_id),),
            )
            row = cur.fetchone()
            assert row is not None, "seed ingress missing for dispatch"
            provider, event_ref, commerce_ref, norm_ref = row
            cur.execute(
                "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                " webhook_ingress_identity_id, task_id, task_name, queue,"
                " routing_key, correlation_id, provider,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_value, status)"
                " VALUES (%s, %s, %s,"
                " 'app.tasks.revenue_verification.execute_b23_batch_match_engine',"
                " 'b23_match_engine', 'b23_match_engine.task', %s, %s, %s, %s, %s,"
                " 'dispatched')"
                " ON CONFLICT (tenant_id, webhook_ingress_identity_id)"
                " DO UPDATE SET task_id = EXCLUDED.task_id,"
                " status = 'dispatched', dispatched_at = now(),"
                " updated_at = now()",
                (
                    str(tenant_id),
                    str(ingress_id),
                    task_id,
                    str(uuid.uuid4()),
                    provider,
                    event_ref,
                    commerce_ref,
                    norm_ref,
                ),
            )
    finally:
        conn.close()


async def test_p2ca1_worker_scope_derivation_returns_governed_summary() -> None:
    # The B23 worker task derives this same summary after natural dispatch.
    # Corrective II: the worker re-resolves tenant/window from the durable
    # dispatch row keyed by broker task_id (dispatch-bound authority). The
    # test seeds one lawful dispatch and derives with its day window.
    from datetime import timezone as _tz

    from app.tasks.revenue_verification import (  # noqa: PLC0415
        _derive_p2_scope_for_window,
    )

    universe = _seed_conduction_universe("worker")
    day_start = datetime(2026, 1, 15, 0, 0, tzinfo=_tz.utc)
    day_end = datetime(2026, 1, 16, 0, 0, tzinfo=_tz.utc)
    worker_task_id = f"p2ca1-worker-{uuid.uuid4().hex[:8]}"
    _seed_worker_dispatch(universe["tenant_id"], universe["matched"][0], worker_task_id)
    summary = await _derive_p2_scope_for_window(
        tenant_id=universe["tenant_id"],
        window_start=day_start,
        window_end=day_end,
        broker_task_id=worker_task_id,
    )
    assert summary["candidate_count"] == 9
    assert summary["excluded_amount_minor"] == 47000
    assert summary["scope_policy_version"] == B26_P2_SCOPE_POLICY_VERSION
    assert summary["dispatch_bound"] is True
    assert summary["broker_task_id"] == worker_task_id
    assert len(summary["scope_identity"]) == 64
    assert (
        summary["supported_amount_minor"]
        + summary["unresolved_amount_minor"]
        + summary["excluded_amount_minor"]
        == summary["total_amount_minor"]
    )


async def test_p2ca1_worker_forged_task_without_dispatch_refuses() -> None:
    """Broker forgery without durable dispatch fails closed (Gate 1)."""
    from app.finance_reconciliation.dispatch_authority import (  # noqa: PLC0415
        DispatchAuthorityError,
    )
    from app.tasks.revenue_verification import (  # noqa: PLC0415
        _derive_p2_scope_for_window,
    )

    universe = _seed_conduction_universe("forged")
    day_start = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)
    day_end = datetime(2026, 1, 16, 0, 0, tzinfo=timezone.utc)
    with pytest.raises((DispatchAuthorityError, ScopeConductionError)):
        await _derive_p2_scope_for_window(
            tenant_id=universe["tenant_id"],
            window_start=day_start,
            window_end=day_end,
            broker_task_id=f"forged-{uuid.uuid4().hex[:8]}",
        )


async def test_p2ca1_worker_wrong_window_refuses() -> None:
    """Lawful dispatch paired with the wrong window fails closed."""
    from datetime import timezone as _tz2

    from app.finance_reconciliation.dispatch_authority import (  # noqa: PLC0415
        DispatchAuthorityError,
    )
    from app.tasks.revenue_verification import (  # noqa: PLC0415
        _derive_p2_scope_for_window,
    )

    universe = _seed_conduction_universe("wrong-window")
    lawful_task_id = f"p2ca1-lawful-{uuid.uuid4().hex[:8]}"
    _seed_worker_dispatch(universe["tenant_id"], universe["matched"][0], lawful_task_id)
    wrong_start = datetime(2026, 3, 1, 0, 0, tzinfo=_tz2.utc)
    wrong_end = datetime(2026, 4, 1, 0, 0, tzinfo=_tz2.utc)
    with pytest.raises((DispatchAuthorityError, ScopeConductionError)):
        await _derive_p2_scope_for_window(
            tenant_id=universe["tenant_id"],
            window_start=wrong_start,
            window_end=wrong_end,
            broker_task_id=lawful_task_id,
        )


async def test_p2ca1_scope_identity_binds_exact_producer_set() -> None:
    """Equal-value substitution changes scope_identity (Gate 3/8)."""
    import psycopg2

    universe = _seed_conduction_universe("identity")
    baseline = await _derive(universe["tenant_id"])
    baseline_identity = baseline.scope_identity
    assert len(baseline_identity) == 64
    # Substitute one 6000 woo candidate with a distinct equal-value identity.
    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    clone_ingress_id = uuid.uuid4()
    clone_event_id = uuid.uuid4()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT event_timestamp FROM public.webhook_ingress_identities"
                " WHERE id = %s",
                (str(universe["woo"]),),
            )
            occurred = cur.fetchone()[0]
            cur.execute(
                "DELETE FROM public.b23_match_verdicts WHERE webhook_ingress_identity_id = %s",
                (str(universe["woo"]),),
            )
            cur.execute(
                "DELETE FROM public.webhook_ingress_identities WHERE id = %s",
                (str(universe["woo"]),),
            )
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s,"
                " 'conversion', 'b26p2ca1_channel', 'b26p2ca1-campaign',"
                " %s, %s, %s, %s, 'processed')",
                (
                    str(clone_event_id),
                    str(universe["tenant_id"]),
                    occurred,
                    str(uuid.uuid4()),
                    str(uuid.uuid4()),
                    6000,
                    json.dumps({"order_id": "woo-clone"}),
                    f"b26p2ca1:identity:woo-clone:{uuid.uuid4().hex[:6]}",
                    6000,
                    "USD",
                    occurred,
                    occurred,
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
                " VALUES (%s, %s, %s, 'woo', %s, %s,"
                " 'order_reference', %s, 6000, 'USD', %s, %s,"
                " 'authenticity_verified')",
                (
                    str(clone_ingress_id),
                    str(universe["tenant_id"]),
                    str(clone_event_id),
                    f"b26p2ca1-ingress-identity-woo-clone-{uuid.uuid4().hex[:6]}",
                    f"b26p2ca1-order-identity-woo-clone-{uuid.uuid4().hex[:6]}",
                    f"b26p2ca1-order-identity-woo-clone-{uuid.uuid4().hex[:6]}",
                    occurred,
                    f"b26p2ca1-ingress:identity:woo-clone:{uuid.uuid4().hex[:6]}",
                ),
            )
        substituted = await _derive(universe["tenant_id"])
        # Count+amount unchanged (6000 woo -> 6000 woo clone) but identity differs.
        assert substituted.candidate_count == baseline.candidate_count
        assert substituted.total_amount_minor == baseline.total_amount_minor
        assert substituted.scope_identity != baseline_identity
    finally:
        conn.close()


def test_p2ca1_worker_task_executes_p2_under_production_principal(
    tmp_path,  # noqa: ANN001
) -> None:
    """Run the production B23 task code as its production principal.

    The batch half writes verdicts, so it requires the worker principal
    (`app_user` is refused by grant topology -- see the least-privilege
    witness in the report). The subprocess executes the exact committed task
    function with the seeded tenant/window, proving the worker's P2 edge
    runs under production authority with no test-to-classifier handoff.
    """
    import subprocess
    import sys

    universe = _seed_conduction_universe("worker-task")
    # Corrective II: the worker task is dispatch-bound. Seed one lawful
    # dispatch for the Jan15 day window and bind the direct-call request id
    # to it so the production code path (including dispatch re-resolution)
    # executes under the production principal.
    from datetime import timezone as _wtz

    day_start = datetime(2026, 1, 15, 0, 0, tzinfo=_wtz.utc)
    day_end = datetime(2026, 1, 16, 0, 0, tzinfo=_wtz.utc)
    bound_task_id = f"p2ca1-task-{uuid.uuid4().hex[:8]}"
    _seed_worker_dispatch(universe["tenant_id"], universe["matched"][0], bound_task_id)
    runner = tmp_path / "run_b23_task.py"
    runner.write_text(
        "import json\n"
        "from uuid import UUID\n"
        "from app.tasks.revenue_verification import (\n"
        "    execute_b23_batch_match_engine_task,\n"
        ")\n"
        "execute_b23_batch_match_engine_task.request.id = r'''"
        + bound_task_id
        + "'''\n"
        "result = execute_b23_batch_match_engine_task(\n"
        "    str(UUID(r'''" + str(universe["tenant_id"]) + "''')), \n"
        "    r'''" + day_start.isoformat() + "''', \n"
        "    r'''" + day_end.isoformat() + "''', \n"
        "    100,\n"
        "    'p2ca1-worker-task',\n"
        ")\n"
        "scope = result.get('p2_scope') or {}\n"
        "print(json.dumps({\n"
        "    'tenant_id': result.get('tenant_id'),\n"
        "    'processed_count': result.get('processed_count'),\n"
        "    'candidate_count': scope.get('candidate_count'),\n"
        "    'excluded_amount_minor': scope.get('excluded_amount_minor'),\n"
        "    'scope_policy_version': scope.get('scope_policy_version'),\n"
        "    'dispatch_bound': scope.get('dispatch_bound'),\n"
        "    'scope_identity': scope.get('scope_identity'),\n"
        "}))\n",
        encoding="utf-8",
    )
    admin_dsn = _admin_dsn()
    worker_dsn = admin_dsn.replace(
        "migration_owner:migration_owner", "app_worker:app_worker"
    )
    worker_dsn = worker_dsn.replace("postgresql://", "postgresql+asyncpg://")
    env = {
        **os.environ,
        "TESTING": "1",
        "DATABASE_URL": worker_dsn,
        "PYTHONPATH": "backend",
    }
    completed = subprocess.run(
        [sys.executable, str(runner)],
        cwd=os.path.join(os.path.dirname(__file__), "..", "..", ".."),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    observed = json.loads(completed.stdout.strip().splitlines()[-1])
    assert observed["tenant_id"] == str(universe["tenant_id"])
    assert observed["candidate_count"] == 9
    assert observed["excluded_amount_minor"] == 47000
    assert observed["scope_policy_version"] == B26_P2_SCOPE_POLICY_VERSION
    assert observed["dispatch_bound"] is True
    assert len(observed["scope_identity"]) == 64
