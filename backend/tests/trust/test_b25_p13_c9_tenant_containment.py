"""B2.5-P13 C9: one tenant's failure is not another tenant's scheduling authority.

The planner leases a batch of due tenants in a single call and then works
through them. Until this corrective there was no boundary between the tenants:
an exception raised while planning the first one propagated out of the loop, so
every tenant queued behind it was never reached and never disposed. Their
wake-ups stayed leased under an owner that had already abandoned them, and they
were unschedulable until the lease expired -- punished for their position in an
ordered list.

Retrying the task did not rescue them. The retry leases a *fresh* batch while
the stranded rows are still held by the previous owner, so the retry cannot see
them either.

These proofs are about failure isolation, not data isolation. Data isolation was
never in question -- RLS and the tenant GUC hold regardless. What was missing was
the weaker-sounding but equally real property that a tenant's *availability*
does not depend on the health of whichever tenants happen to sort before it.

Two properties are established, and they are different:

* containment -- a failing tenant does not prevent its batch-mates from being
  planned in the same pass;
* bounded progress -- a tenant that fails *every* time, forever, still does not
  prevent healthy tenants from progressing, pass after pass.

The second does not follow from the first. A system could contain each failure
and still starve healthy tenants if the failing one monopolised the batch, or if
failure left it permanently first in line with the others behind it.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from app.bayesian.model_identity import active_identity
from app.core.secrets import get_database_url
from app.db.dsn import to_sync_postgres_dsn


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_C9_DB_PROOF") != "1",
    reason="B2.5-P13 C9 tenant-containment proofs are opt-in locally",
)

ACTIVE = active_identity()
WINDOW_START = datetime(2026, 11, 2, tzinfo=timezone.utc)
WINDOW_END = WINDOW_START + timedelta(days=1)


def _engine(url: str | None = None):
    return create_engine(
        to_sync_postgres_dsn(url or get_database_url()),
        pool_pre_ping=True,
        future=True,
    )


def _migration_engine():
    return _engine(os.environ.get("MIGRATION_DATABASE_URL"))


def _seed_due_tenant(conn, label: str, *, age_seconds: int):
    """A tenant with one debounce-mature dirty event and its durable wake-up.

    ``age_seconds`` controls where the tenant sorts in the planner's batch. The
    planner leases oldest-first, so a tenant seeded older is leased earlier --
    which is how a failing tenant gets in front of healthy ones.
    """

    tenant_id = uuid.uuid4()
    conn.execute(
        text(
            "INSERT INTO public.tenants (id, name, api_key_hash,"
            " notification_email) VALUES (:t, :n, :h, :e)"
        ),
        {
            "t": str(tenant_id),
            "n": f"c9-containment-{label}-{tenant_id.hex[:8]}",
            "h": uuid.uuid4().hex,
            "e": f"c9c-{tenant_id.hex[:8]}@example.invalid",
        },
    )
    conn.execute(
        text("SELECT set_config('app.current_tenant_id', :t, false)"),
        {"t": str(tenant_id)},
    )
    conn.execute(
        text(
            "INSERT INTO public.b24_dirty_events (tenant_id, model_type,"
            " model_version, source_window_start, source_window_end,"
            " dirty_reason, source_family, observed_at, status) VALUES"
            " (:t, :mt, :mv, :ws, :we, 'c9_containment', 'b23_revenue_events',"
            " now() - make_interval(secs => :age), 'pending')"
        ),
        {
            "t": str(tenant_id),
            "mt": ACTIVE.model_type,
            "mv": ACTIVE.model_version,
            "ws": WINDOW_START,
            "we": WINDOW_END,
            "age": age_seconds,
        },
    )
    return tenant_id


def _wakeups(engine, tenant_ids) -> dict:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT tenant_id, status, lease_owner IS NOT NULL AS leased"
                " FROM public.b24_fit_planner_wakeups"
                " WHERE tenant_id = ANY(CAST(:ids AS uuid[]))"
            ),
            {"ids": [str(t) for t in tenant_ids]},
        ).mappings()
        return {str(row["tenant_id"]): dict(row) for row in rows}


def _run_planner(*, failing: set[str], batch: int = 25) -> dict:
    """Run the real planner task body with one tenant made to fail.

    The failure is injected into ``plan_due_dirty_events`` -- the planner's own
    per-tenant entry point -- rather than into the loop, so what is exercised is
    the real containment boundary and not a simulation of one.
    """

    import app.tasks.bayesian as tasks
    from app.bayesian.worker_boot_probe import (
        bayesian_worker_boot_topology_probe_has_passed,
    )
    from celery import signals

    # The real Celery lifecycle signal, exactly as a booting worker sends it.
    # Bayesian tasks refuse to run in a process that has not registered its
    # generation authority, and that refusal is a guard worth keeping rather
    # than bypassing -- so this satisfies it the way production does.
    if not bayesian_worker_boot_topology_probe_has_passed():
        signals.worker_init.send(sender="b25-p13-c9-containment-proof")
    assert bayesian_worker_boot_topology_probe_has_passed()

    original = tasks.plan_due_dirty_events

    # Forward whatever the task actually passes rather than restating a
    # signature. This stub named three keyword arguments; when XIX began
    # passing the governed quiet period as a fourth, every tenant raised
    # TypeError instead of the one injected failure, so the containment claim
    # became unprovable while still reporting a failure count. The assertion
    # below keeps the stub honest without re-freezing the signature.
    async def failing_planner(*, tenant_id, planner_owner, **planner_kwargs):
        assert "quiet_period_seconds" in planner_kwargs, (
            "the planner task must pass its governed debounce through"
        )
        if str(tenant_id) in failing:
            raise RuntimeError(f"c9 injected planner failure for {tenant_id}")
        return await original(
            tenant_id=tenant_id, planner_owner=planner_owner, **planner_kwargs
        )

    class _Request:
        id = f"c9-containment-{uuid.uuid4().hex[:8]}"

    class _Task:
        request = _Request()

    del _Request, _Task
    tasks.plan_due_dirty_events = failing_planner
    try:
        # ``.run()`` is the right invocation here and would be the wrong one for
        # a transport proof. What is under test is the loop's failure boundary,
        # which is a property of the task body; whether Beat and a broker can
        # deliver that body is a separate question, proven separately, and
        # routing this through a real worker would only add latency and a second
        # thing that could break.
        return tasks.plan_due_fit_intents.run(
            tenant_batch_size=batch, candidate_limit=25
        )
    finally:
        tasks.plan_due_dirty_events = original


def test_c9_a_failing_tenant_does_not_strand_the_tenants_behind_it() -> None:
    """The containment property, observed on the wake-up ledger itself.

    The failing tenant is seeded oldest so the planner leases it first. Every
    healthy tenant behind it must still be planned and disposed in the same
    pass. Before this corrective they were all left ``leased`` by an owner that
    had already stopped running.
    """

    seed_engine = _migration_engine()
    try:
        with seed_engine.begin() as conn:
            failing = _seed_due_tenant(conn, "failing", age_seconds=900)
            healthy = [
                _seed_due_tenant(conn, f"healthy{index}", age_seconds=600 - index * 10)
                for index in range(3)
            ]
    finally:
        seed_engine.dispose()

    everyone = [failing, *healthy]
    engine = _engine()
    try:
        before = _wakeups(engine, everyone)
        assert len(before) == 4, before
        assert all(row["status"] == "pending" for row in before.values()), before

        result = _run_planner(failing={str(failing)})

        # The pass did not abort: it reached every tenant it leased.
        assert result["tenant_count"] >= 4, result
        assert result["failed_tenant_count"] == 1, result
        assert result["failure_classes"] == {"RuntimeError": 1}, result

        after = _wakeups(engine, everyone)
        stranded = {
            tenant: row
            for tenant, row in after.items()
            if row["leased"] and tenant != str(failing)
        }
        assert not stranded, (
            "tenants queued behind a failing tenant were left leased by an owner "
            f"that had already stopped: {stranded}"
        )
        # And the failing tenant's own obligation was conserved, not destroyed.
        assert str(failing) in after, after
        assert after[str(failing)]["status"] == "pending", after[str(failing)]
        assert not after[str(failing)]["leased"], after[str(failing)]
    finally:
        engine.dispose()


def test_c9_a_permanently_failing_tenant_cannot_deny_healthy_tenants_progress() -> None:
    """Bounded forward progress across repeated failure cycles.

    Containment says the other tenants are reached once. This says they are
    reached every time, while one tenant fails on every pass forever -- which is
    the shape a real deployment sees, because a tenant with genuinely broken
    state does not repair itself between passes.

    The failing tenant is deliberately re-seeded oldest each cycle so it is
    leased first every time. If position in the batch were load-bearing, this is
    where it would show.
    """

    seed_engine = _migration_engine()
    try:
        with seed_engine.begin() as conn:
            failing = _seed_due_tenant(conn, "permanent", age_seconds=3600)
            healthy = [
                _seed_due_tenant(conn, f"survivor{index}", age_seconds=1800 - index * 5)
                for index in range(2)
            ]
    finally:
        seed_engine.dispose()

    engine = _engine()
    try:
        planned_cycles = 0
        failures = 0
        for cycle in range(4):
            # Re-arm every tenant, keeping the failing one oldest.
            arm = _migration_engine()
            try:
                with arm.begin() as conn:
                    for tenant, age in (
                        (failing, 3600),
                        *[(t, 1800) for t in healthy],
                    ):
                        conn.execute(
                            text(
                                "SELECT set_config('app.current_tenant_id', :t,"
                                " false)"
                            ),
                            {"t": str(tenant)},
                        )
                        conn.execute(
                            text(
                                "INSERT INTO public.b24_dirty_events (tenant_id,"
                                " model_type, model_version, source_window_start,"
                                " source_window_end, dirty_reason, source_family,"
                                " observed_at, status) VALUES (:t, :mt, :mv, :ws,"
                                " :we, :reason, 'b23_revenue_events',"
                                " now() - make_interval(secs => :age), 'pending')"
                            ),
                            {
                                "t": str(tenant),
                                "mt": ACTIVE.model_type,
                                "mv": ACTIVE.model_version,
                                "ws": WINDOW_START + timedelta(days=cycle + 1),
                                "we": WINDOW_END + timedelta(days=cycle + 1),
                                "reason": f"c9_cycle_{cycle}",
                                "age": age,
                            },
                        )
            finally:
                arm.dispose()

            result = _run_planner(failing={str(failing)})
            failures += result["failed_tenant_count"]

            reached = _wakeups(engine, healthy)
            still_leased = {
                tenant: row for tenant, row in reached.items() if row["leased"]
            }
            assert not still_leased, (
                f"cycle {cycle}: healthy tenants left leased behind a "
                f"permanently failing tenant: {still_leased}"
            )
            planned_cycles += 1

        assert planned_cycles == 4
        assert failures == 4, (
            f"the failing tenant was expected to fail on every cycle; saw "
            f"{failures}"
        )
    finally:
        engine.dispose()
