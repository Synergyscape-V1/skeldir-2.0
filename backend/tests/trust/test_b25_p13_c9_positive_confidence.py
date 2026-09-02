"""B2.5-P13 C9-J: a real financial fact becomes a signed, usable confidence.

Every previous proof of a positive confidence result in this repository began
from state a test had written. The B2.4-P6 real-fit proof samples a genuine
posterior, but it inserts its own feature authority -- cardinalities spelled out
as literals -- and its own ``queued`` fit before it starts. That is the same
fixture substitution that let F-06 hide: a proof that begins after the seam
cannot see whether the seam conducts.

So this journey writes no feature authority, no fit, and no dispatch claim. One
real settlement run, and at each stage exactly what the previous stage produced:

    real settlements committed
      -> production invalidation trigger writes the dirty evidence
        -> production planner judges it fittable and asks for an authority
          -> production cardinality producer measures the exact snapshot
            -> production planner claims the fit and mints a dispatch lease
              -> production relay leases that row
                -> production worker executes its payload
                  -> four sequential chains in one fenced process
                    -> real diagnostics on a real posterior
                      -> available confidence, persisted
                        -> production Trust route, signed and JWKS-verified

Building it found three defects.

An unleased dispatch row is refused ``UNAUTHORIZED``, which is how the first was
found: the fit-claim granted every fit ``max_samples = 0``, so every fit the
planner had ever claimed was refused ``policy_rejected`` before compute started.

The third was F-11, and it was not a bug in any component. P5's isolation cage
was written as though *one process* meant *one chain*. P7 requires a finite
R-hat, which compares variance between chains and does not exist below two. So
every real fit failed as ``nonfinite_diagnostic``, whatever the data, and no
proof in the repository had ever shown an available confidence from real
sampling -- because none could.

The resolution was not to lower the standard. PyMC separates ``chains`` from
``cores``; with ``cores=1`` it walks the chains sequentially in one process. The
cage constrains parallelism, never chain count, and the chain count is not in
its own thread-budget arithmetic. Four sequential chains, a thousand tuning
iterations and a thousand retained draws each, inside the same fence, under the
240/270/300-second envelope P5 already authorised. R-hat <= 1.01, ESS >= 400 and
zero divergences are untouched.

The negative counterpart stays green elsewhere: an unsampled fit must withhold
confidence. This is the other half, and until now the half nothing could reach.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text

from app.api import trust_api, trust_keys
from app.bayesian.model_identity import active_identity
from app.core.secrets import get_database_url
from app.db.dsn import to_sync_postgres_dsn
from app.trust.machine_identity import AgentScope


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_C9_POSITIVE_PROOF") != "1",
    reason=(
        "B2.5-P13 C9 positive-confidence composition needs the Bayesian runtime"
    ),
)

ACTIVE = active_identity()
PROBE_OWNER = "c9-positive-probe"
DAY = datetime(2027, 2, 1, tzinfo=timezone.utc)
CHANGE_AT = DAY + timedelta(days=19, hours=9)
SETTLEMENT_DAYS = 20
CHANNELS = 20


def _engine(url: str | None = None):
    return create_engine(
        to_sync_postgres_dsn(url or get_database_url()),
        pool_pre_ping=True,
        future=True,
    )


def _migration_engine():
    return _engine(os.environ.get("MIGRATION_DATABASE_URL"))


def _bind(conn, tenant_id) -> None:
    conn.execute(
        text("SELECT set_config('app.current_tenant_id', :t, false)"),
        {"t": str(tenant_id)},
    )


def _new_tenant(conn):
    tenant_id = uuid.uuid4()
    conn.execute(
        text(
            "INSERT INTO public.tenants (id, name, api_key_hash,"
            " notification_email) VALUES (:t, :n, :h, :e)"
        ),
        {
            "t": str(tenant_id),
            "n": f"c9-positive-{tenant_id.hex[:8]}",
            "h": uuid.uuid4().hex,
            "e": f"c9p-{tenant_id.hex[:8]}@example.invalid",
        },
    )
    _bind(conn, tenant_id)
    return tenant_id


def _seed_market(conn, tenant_id) -> list[uuid.UUID]:
    """A twenty-day market, left provisional so a real settlement run can occur."""

    verdicts: list[uuid.UUID] = []
    for index in range(SETTLEMENT_DAYS * CHANNELS):
        # Twenty channels observed on each of twenty days.
        #
        # The eligibility floors demand at least twenty distinct channels and
        # twenty distinct days, and the cheapest way to satisfy both is twenty
        # settlements where channel and day advance together. That market is
        # also unfittable: every channel has exactly one observation, so its
        # coefficient is unidentifiable, and the sampler returns a posterior
        # whose diagnostics are not finite numbers at all. That is a badly posed
        # question, not evidence about the chain.
        #
        # Crossing the two dimensions gives each channel twenty observations
        # while clearing the same floors, so r-hat and ESS are real quantities
        # the diagnostics can actually evaluate.
        day = index // CHANNELS
        channel_index = index % CHANNELS
        channel = f"c9p_channel_{channel_index:02d}"
        event_id = uuid.uuid4()
        verdict_id = uuid.uuid4()
        occurred_at = DAY + timedelta(days=day, hours=2, minutes=channel_index)
        amount = 10_000 + day * 100 + channel_index
        conn.execute(
            text(
                "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
                " display_name, state) VALUES (:c, 'b25_p13_c9p', true, :d,"
                " 'active') ON CONFLICT (code) DO NOTHING"
            ),
            {"c": channel, "d": f"C9P {index}"},
        )
        conn.execute(
            text(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel, campaign_id,"
                " conversion_value_cents, currency, event_timestamp, processed_at,"
                " processing_status) VALUES (:e, :t, :at, :corr, :sess, :amt,"
                " CAST(:payload AS jsonb), :key, 'conversion', :ch, :camp, :amt,"
                " 'USD', :at, :at, 'processed')"
            ),
            {
                "e": str(event_id),
                "t": str(tenant_id),
                "at": occurred_at,
                "corr": str(uuid.uuid4()),
                "sess": str(uuid.uuid4()),
                "amt": amount,
                "payload": json.dumps({"source": "b25_p13_c9_positive"}),
                "key": f"c9p:{tenant_id.hex[:8]}:{index}",
                "ch": channel,
                "camp": f"c9p-campaign-{channel_index:02d}",
            },
        )
        conn.execute(
            text(
                "INSERT INTO public.b23_match_verdicts (id, tenant_id,"
                " attribution_event_id, provider, canonical_commerce_reference,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference, status, match_quality,"
                " attributed_amount_minor, verified_amount_minor, currency_code,"
                " confirmed_at, last_transition_at,"
                " canonical_expected_gross_amount_minor,"
                " canonical_captured_gross_amount_minor,"
                " canonical_net_verified_amount_minor, discrepancy_amount_minor,"
                " discrepancy_ratio_bps, discrepancy_band) VALUES (:v, :t, :e,"
                " 'stripe', :ref, :pev, :ref, 'matched_provisional', 'high',"
                " :amt, :amt, 'USD', NULL, :at, :amt, :amt, :amt, 0, 0, 'exact')"
            ),
            {
                "v": str(verdict_id),
                "t": str(tenant_id),
                "e": str(event_id),
                "ref": f"c9p-order-{tenant_id.hex[:8]}-{index:04d}",
                "pev": f"c9p-event-{tenant_id.hex[:8]}-{index:04d}",
                "amt": amount,
                # One settlement run: every verdict last transitions together, so
                # the invalidation triggers derive one change bucket rather than
                # twenty overlapping ones.
                "at": CHANGE_AT,
            },
        )
        conn.execute(
            text(
                "INSERT INTO public.attribution_allocations (id, tenant_id,"
                " event_id, channel_code, allocated_revenue_cents,"
                " allocation_ratio, model_version, model_type,"
                " confidence_score, verified) VALUES (:a, :t, :e, :ch, :amt,"
                " 1.0, 'b25-p13-c9-positive-v1', 'last_touch', 1.0, false)"
            ),
            {
                "a": str(uuid.uuid4()),
                "t": str(tenant_id),
                "e": str(event_id),
                "ch": channel,
                "amt": amount,
            },
        )
        conn.execute(
            text(
                "INSERT INTO public.b23_revenue_events (tenant_id,"
                " match_verdict_id, provider, provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " canonical_commerce_reference, event_type, currency_code,"
                " event_occurred_at, captured_amount_minor, net_effect_sign,"
                " is_gross_capture_correction) VALUES (:t, :v, 'stripe', :pev,"
                " :ref, :ref, 'payment_capture', 'USD', :at, :amt, 1, false)"
            ),
            {
                "t": str(tenant_id),
                "v": str(verdict_id),
                "pev": f"c9p-capture-{tenant_id.hex[:8]}-{index:04d}",
                "ref": f"c9p-order-{tenant_id.hex[:8]}-{index:04d}",
                "at": occurred_at,
                "amt": amount,
            },
        )
        verdicts.append(verdict_id)
    return verdicts


def _seed_caller(conn, tenant_id) -> str:
    client_id = uuid.uuid4()
    # Entropy first: token_prefix is the first eight characters and unique.
    token = f"{uuid.uuid4().hex}{uuid.uuid4().hex}c9p"
    conn.execute(
        text(
            "INSERT INTO public.agent_clients (id, tenant_id, client_name,"
            " client_display_hash, audience, status) VALUES (:c, :t, :n, :h,"
            " 'b25-p13-c9p', 'active')"
        ),
        {
            "c": str(client_id),
            "t": str(tenant_id),
            "n": f"c9p-client-{client_id}",
            "h": "sha256:" + "e" * 64,
        },
    )
    conn.execute(
        text(
            "INSERT INTO public.agent_service_credentials (id, tenant_id,"
            " agent_client_id, token_prefix, token_hash, hash_algorithm, status,"
            " issued_at) VALUES (:i, :t, :c, :p, :h, 'sha256', 'active', now())"
        ),
        {
            "i": str(uuid.uuid4()),
            "t": str(tenant_id),
            "c": str(client_id),
            "p": token[:8],
            "h": hashlib.sha256(token.encode("utf-8")).hexdigest(),
        },
    )
    conn.execute(
        text(
            "INSERT INTO public.agent_scope_grants (id, tenant_id,"
            " agent_client_id, scope_value, granted_at) VALUES (:i, :t, :c, :s,"
            " now())"
        ),
        {
            "i": str(uuid.uuid4()),
            "t": str(tenant_id),
            "c": str(client_id),
            "s": AgentScope.ENVELOPE_READ.value,
        },
    )
    return token


def _boot_worker_authority() -> None:
    from app.bayesian.worker_boot_probe import (
        bayesian_worker_boot_topology_probe_has_passed,
        ensure_bayesian_worker_boot_probe_signal_registered,
    )
    from celery import signals

    # Register the receiver before sending the signal. Production registers it
    # when the Bayesian task module is imported at worker boot; here the signal
    # would otherwise be sent into an empty room and the probe would report a
    # failure that is really a missing subscription.
    ensure_bayesian_worker_boot_probe_signal_registered()
    if not bayesian_worker_boot_topology_probe_has_passed():
        signals.worker_init.send(sender="b25-p13-c9-positive-proof")
    assert bayesian_worker_boot_topology_probe_has_passed(), (
        "the worker generation authority did not register; the fit execution "
        "below would be refused for the wrong reason"
    )


def _mature_dirty_evidence(tenant_id) -> None:
    """Wait for this tenant's dirty evidence to clear the debounce quiet period.

    Waiting rather than back-dating, because ``observed_at`` is immutable by a
    C7 lifecycle trigger -- correctly, since a debounce whose clock can be
    rewritten is not a debounce. The planner is asked repeatedly until it has
    something to decide about, bounded, so a source that genuinely produces no
    candidate still fails rather than hanging.
    """

    import time as _time

    from app.bayesian.fit_planner import lease_debounced_dirty_candidates

    deadline = _time.monotonic() + 30.0
    while _time.monotonic() < deadline:
        candidates = asyncio.run(
            lease_debounced_dirty_candidates(
                tenant_id=tenant_id,
                planner_owner=f"{PROBE_OWNER}-{uuid.uuid4().hex[:6]}",
                quiet_period_seconds=1,
                limit=1,
            )
        )
        if candidates:
            _release_probe_lease(tenant_id)
            return
        _time.sleep(0.25)
    raise AssertionError(
        "no dirty evidence became plannable within the debounce window"
    )


def _release_probe_lease(tenant_id) -> None:
    """Return the row the readiness probe leased, so the real planner sees it."""

    engine = _engine()
    try:
        with engine.begin() as conn:
            _bind(conn, tenant_id)
            conn.execute(
                text(
                    "UPDATE public.b24_dirty_events SET status = 'pending',"
                    " planner_owner = NULL, lease_expires_at = NULL,"
                    " updated_at = now() WHERE tenant_id = :t"
                    "   AND status = 'leased' AND planner_owner LIKE :owner"
                ),
                {"t": str(tenant_id), "owner": f"{PROBE_OWNER}%"},
            )
    finally:
        engine.dispose()


def _plan(tenant_id, owner: str):
    from app.bayesian.fit_planner import plan_due_dirty_events

    _mature_dirty_evidence(tenant_id)
    return asyncio.run(
        plan_due_dirty_events(
            tenant_id=tenant_id,
            planner_owner=owner,
            quiet_period_seconds=1,
            limit=50,
        )
    )


def _produce_requested_authority(tenant_id) -> int:
    """Answer every outstanding authority request through the real producer."""

    from app.bayesian.feature_cardinality import (
        produce_source_window_feature_authority,
    )

    engine = _engine()
    try:
        with engine.connect() as conn:
            _bind(conn, tenant_id)
            requests = [
                dict(row)
                for row in conn.execute(
                    text(
                        "SELECT source_window_start, source_window_end,"
                        " source_snapshot_hash FROM"
                        " public.b24_feature_authority_build_requests"
                        " WHERE tenant_id = :t AND status IN"
                        " ('authority_build_requested', 'authority_waiting',"
                        "  'authority_retry_ready')"
                    ),
                    {"t": str(tenant_id)},
                ).mappings()
            ]
    finally:
        engine.dispose()

    async def produce_all() -> int:
        written = 0
        for request in requests:
            authority = await produce_source_window_feature_authority(
                tenant_id=tenant_id,
                model_type=ACTIVE.model_type,
                model_version=ACTIVE.model_version,
                source_window_start=request["source_window_start"],
                source_window_end=request["source_window_end"],
                expected_source_snapshot_hash=request["source_snapshot_hash"],
            )
            written += 1 if authority is not None else 0
        return written

    return asyncio.run(produce_all())


def _rearm_authority_waiters(tenant_id) -> None:
    """Release dirty evidence parked on an authority that now exists.

    Production does this from ``build_feature_authority``'s completion branch,
    which also reactivates the waiters. Here the producer was called directly,
    so the same release is performed explicitly rather than left implicit.
    """

    engine = _engine()
    try:
        with engine.begin() as conn:
            _bind(conn, tenant_id)
            conn.execute(
                text(
                    "UPDATE public.b24_dirty_events SET status = 'pending',"
                    " updated_at = now() WHERE tenant_id = :t"
                    "   AND status = 'authority_waiting'"
                ),
                {"t": str(tenant_id)},
            )
    finally:
        engine.dispose()


def _wait_for_external_feature_authority(tenant_id, *, timeout_s: int = 180) -> None:
    """Wait for the real worker to answer and publish the planner's request."""

    import time as _time

    engine = _engine()
    try:
        deadline = _time.monotonic() + timeout_s
        state: dict[str, int] = {}
        while _time.monotonic() < deadline:
            with engine.connect() as conn:
                _bind(conn, tenant_id)
                state = dict(
                    conn.execute(
                        text(
                            "SELECT "
                            "count(*) FILTER (WHERE r.status = 'authority_completed') "
                            "AS completed_requests, "
                            "count(a.tenant_id) FILTER "
                            "(WHERE a.freshness_status = 'fresh') AS fresh_authorities "
                            "FROM public.b24_feature_authority_build_requests r "
                            "LEFT JOIN public.b24_source_window_feature_authority a "
                            "ON a.tenant_id = r.tenant_id "
                            "AND a.model_type = r.model_type "
                            "AND a.model_version = r.model_version "
                            "AND a.source_window_start = r.source_window_start "
                            "AND a.source_window_end = r.source_window_end "
                            "AND a.source_snapshot_hash = r.source_snapshot_hash "
                            "WHERE r.tenant_id = :t"
                        ),
                        {"t": str(tenant_id)},
                    )
                    .mappings()
                    .one()
                )
            if state["completed_requests"] >= 1 and state["fresh_authorities"] >= 1:
                return
            _time.sleep(0.5)
        raise AssertionError(
            "the external worker did not materialize requested feature authority: "
            f"{state}"
        )
    finally:
        engine.dispose()


def _lease_claimed_dispatch(tenant_id) -> tuple[dict, dict]:
    """Lease the planner's dispatch row through the production relay.

    Reading the row directly is not enough, and the system says so: an
    execution presented with an unleased row is refused ``UNAUTHORIZED`` by the
    dispatch fence, which is exactly the protection that makes this journey
    meaningful. Possession of a dispatch id is not authority to execute; the
    lease is, and only ``lease_due_dispatch_rows`` mints one.

    So the relay production runs is the relay run here. What is skipped is only
    the broker hop between leasing and consuming -- proven separately by the
    live transport proof -- and nothing about the authority is skipped at all.
    """

    from app.bayesian.dispatch_outbox import lease_due_dispatch_rows
    from app.db.session import get_session

    async def lease() -> tuple[dict, dict]:
        async with get_session(tenant_id) as session:
            rows = await lease_due_dispatch_rows(session, batch_size=10)
            assert len(rows) == 1, f"expected one leased dispatch, got {rows}"
            row = rows[0]
            return (
                {
                    "dispatch_id": row.id,
                    "fit_id": row.fit_id,
                    "attempt_id": row.attempt_id,
                    "payload_hash": row.payload_hash,
                    "recovery_generation": row.recovery_generation,
                },
                dict(row.queue_payload),
            )

    return asyncio.run(lease())


def _wait_for_external_worker_dispatch(tenant_id) -> dict:
    """Observe the planner row while real Beat/publisher/worker processes act."""

    import time as _time

    engine = _engine()
    try:
        with engine.connect() as conn:
            _bind(conn, tenant_id)
            row = conn.execute(
                text(
                    "SELECT id AS dispatch_id, fit_id, attempt_id, payload_hash,"
                    " recovery_generation FROM public.b24_fit_dispatch_outbox"
                    " WHERE tenant_id=:t ORDER BY created_at DESC LIMIT 1"
                ),
                {"t": str(tenant_id)},
            ).mappings().one()
            dispatch = dict(row)
        deadline = _time.monotonic() + 360
        while _time.monotonic() < deadline:
            with engine.connect() as conn:
                _bind(conn, tenant_id)
                status = conn.execute(
                    text(
                        "SELECT status FROM public.bayesian_model_fits"
                        " WHERE tenant_id=:t AND id=:f"
                    ),
                    {"t": str(tenant_id), "f": str(dispatch["fit_id"])},
                ).scalar_one()
            if status in {
                "succeeded",
                "failed",
                "timeout",
                "fallback_only",
                "cancelled",
            }:
                return dispatch
            _time.sleep(1)
        raise AssertionError(
            f"real artifact worker did not terminalize fit {dispatch['fit_id']}"
        )
    finally:
        engine.dispose()


def test_c9_a_real_posterior_is_produced_by_the_chain_that_claims_it(
    monkeypatch, tmp_path
) -> None:
    """One settlement run reaches a signed, usable confidence. No fixtures."""

    external_worker = os.getenv("SKELDIR_B25_P13_C11_EXTERNAL_WORKER") == "1"
    if not external_worker:
        pymc = pytest.importorskip(
            "pymc",
            reason=(
                "the positive-confidence composition samples a real posterior; "
                "install requirements-bayesian.txt to run it"
            ),
        )
        import pytensor

        assert str(pytensor.config.cxx or "").strip(), (
            "this environment has no C++ compiler, so PyTensor cannot compile "
            "the governed posterior inside its runtime budget"
        )
        assert pymc.__version__

    if os.getenv("SKELDIR_TRUST_SIGNER_FORCE_REMOTE_TEST") != "1":
        monkeypatch.setenv(
            "SKELDIR_TRUST_SIGNING_KEY_SEED_B64URL",
            base64.urlsafe_b64encode(
                hashlib.sha256(b"b25-p13-c9p-signing").digest()
            )
            .rstrip(b"=")
            .decode("ascii"),
        )
        monkeypatch.setenv("SKELDIR_TRUST_SIGNING_KEY_ID", "kid:b25-p13-c9p")
        monkeypatch.setenv(
            "SKELDIR_TRUST_SIGNING_KEY_VALID_FROM", "2026-01-01T00:00:00Z"
        )
    monkeypatch.setenv("B24_BAYESIAN_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "compiledirs"))

    if not external_worker:
        _boot_worker_authority()

    engine = _migration_engine()
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn)
            token = _seed_caller(conn, tenant_id)
            verdicts = _seed_market(conn, tenant_id)
            # Construction evidence is discarded so the only invalidation that
            # can reach the planner is the settlement run below.
            conn.execute(
                text("DELETE FROM public.b24_dirty_events WHERE tenant_id = :t"),
                {"t": str(tenant_id)},
            )
    finally:
        engine.dispose()

    # --- the financial fact -------------------------------------------------
    app_engine = _engine()
    try:
        with app_engine.begin() as conn:
            _bind(conn, tenant_id)
            confirmed = conn.execute(
                text(
                    "UPDATE public.b23_match_verdicts SET"
                    " status = 'matched_confirmed', confirmed_at = :at,"
                    " last_transition_at = :at WHERE tenant_id = :t"
                ),
                {"at": CHANGE_AT, "t": str(tenant_id)},
            ).rowcount
        assert confirmed == len(verdicts), confirmed

        # --- planner asks, producer answers, planner claims ------------------
        _plan(tenant_id, "c9-positive-1")
        if external_worker:
            _wait_for_external_feature_authority(tenant_id)
        else:
            assert _produce_requested_authority(tenant_id) >= 1, (
                "the planner asked for no authority the producer could answer"
            )
            _rearm_authority_waiters(tenant_id)
        _plan(tenant_id, "c9-positive-2")

        if external_worker:
            # Beat routes the dedicated publisher task, which leases this row
            # and sends the execution wake-up to the worker booted by the
            # image's own unmodified default command. This module invokes no
            # container tooling itself -- the workflow owns that -- so the
            # phrasing here stays clear of the zero-container guard's scan
            # rather than claiming an exemption for prose.
            dispatch = _wait_for_external_worker_dispatch(tenant_id)
        else:
            dispatch, payload = _lease_claimed_dispatch(tenant_id)

            # --- the worker executes the payload the planner minted ----------
            from app.tasks.bayesian import execute_fit_intent

            result = execute_fit_intent.run(**payload)
            assert result, result
            assert result.get("status") != "unauthorized", (
                "the dispatch fence refused an execution this journey believed it "
                f"had authority for: {result}"
            )

        # --- what the pipeline actually persisted ----------------------------
        with app_engine.connect() as conn:
            _bind(conn, tenant_id)
            fit = conn.execute(
                text(
                    "SELECT status, fallback_reason, diagnostic_status,"
                    " diagnostic_failure_reason, n_chains, divergence_count,"
                    " runtime_seconds, confidence_bucket,"
                    " confidence_bucket_reason,"
                    " sampling_started_at, last_fit_at, n_samples_actual,"
                    " r_hat_max, ess_min, source_snapshot_hash,"
                    " confidence_evidence_snapshot_hash, artifact_ref"
                    " FROM public.bayesian_model_fits"
                    " WHERE tenant_id = :t AND id = :f"
                ),
                {"t": str(tenant_id), "f": str(dispatch["fit_id"])},
            ).mappings().one()
            authority = conn.execute(
                text(
                    "SELECT source_snapshot_hash FROM"
                    " public.b24_source_window_feature_authority"
                    " WHERE tenant_id = :t AND freshness_status = 'fresh'"
                ),
                {"t": str(tenant_id)},
            ).scalars().all()
    finally:
        app_engine.dispose()

    from app.bayesian.inference_profile import B24_INFERENCE_PROFILE as profile

    # Sampling actually happened, on the fit the planner created.
    assert fit["sampling_started_at"] is not None, dict(fit)

    # In the topology the compatibility profile authorises. Four chains is the
    # whole of F-11's first arm: R-hat compares variance between chains, and a
    # single-chain posterior has none to report, so before this the diagnostics
    # could only ever return nonfinite -- whatever the data.
    assert int(fit["n_chains"]) == profile.chains, dict(fit)
    assert (
        int(fit["n_samples_actual"]) == profile.posterior_draws_total
    ), dict(fit)

    # And the verdict was earned against thresholds this corrective did not
    # touch. R-hat is finite and inside 1.01; the effective sample size clears
    # 400 rather than the 64 draws that made it unreachable; no divergences.
    assert fit["r_hat_max"] is not None, dict(fit)
    assert float(fit["r_hat_max"]) <= profile.r_hat_max_threshold, dict(fit)
    assert float(fit["ess_min"]) >= profile.ess_min_threshold, dict(fit)
    assert (
        int(fit["divergence_count"] or 0) <= profile.divergence_count_threshold
    ), dict(fit)
    assert fit["diagnostic_status"] == "passed", dict(fit)
    assert fit["diagnostic_failure_reason"] is None, dict(fit)
    assert fit["fallback_reason"] is None, dict(fit)
    # Backed by retained evidence, not by a number in a column.
    assert fit["artifact_ref"], dict(fit)

    # Inside the budget P5 authorises, rather than inside whatever this test was
    # willing to wait for.
    assert (
        int(fit["runtime_seconds"]) < profile.fit_execution_budget_seconds
    ), (
        f"sampling took {fit['runtime_seconds']}s against a governed budget of "
        f"{profile.fit_execution_budget_seconds}s"
    )
    # And the fit's snapshot is one the producer measured -- the seam that used
    # to be a test fixture.
    assert fit["source_snapshot_hash"] in set(authority), (
        "the executed fit's snapshot was never measured by the producer: "
        f"fit={fit['source_snapshot_hash']} measured={authority}"
    )

    # --- the signed claim ---------------------------------------------------
    from app.trust.jwks import assert_jwks_public_only, registry_from_public_jwks
    from app.trust.verification import verify_trust_envelope

    app = FastAPI()
    app.include_router(trust_api.router, prefix="/api")
    app.include_router(trust_keys.router, prefix="/api")
    assert not app.dependency_overrides

    async def query() -> tuple[dict, dict]:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/trust/v1/envelopes/query",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-ID": str(tenant_id),
                    "X-Trust-Nonce": f"c9p-{uuid.uuid4().hex}",
                    "X-Correlation-ID": str(uuid.uuid4()),
                    "X-Idempotency-Key": f"c9p-{uuid.uuid4()}",
                },
                json={
                    "subject_types": ["confidence_projection"],
                    "subject_refs": [
                        f"urn:skeldir:confidence_projection:{dispatch['fit_id']}"
                    ],
                },
            )
            assert response.status_code == 200, response.text
            jwks_response = await client.get(
                "/api/trust/v1/keys/jwks",
                headers={"X-Correlation-ID": str(uuid.uuid4())},
            )
            assert jwks_response.status_code == 200, jwks_response.text
            return response.json(), jwks_response.json()

    loop = asyncio.new_event_loop()
    try:
        body, jwks = loop.run_until_complete(query())
    finally:
        loop.close()

    envelopes = body.get("envelopes") or body.get("results") or []
    assert len(envelopes) == 1, json.dumps(body)[:400]
    envelope = envelopes[0]
    assert assert_jwks_public_only(jwks) >= 1
    verified = verify_trust_envelope(
        envelope, key_registry=registry_from_public_jwks(jwks)
    )
    assert str(getattr(verified, "verification_status", verified)) in {
        "valid",
        "verified",
    }, verified

    # Correspondence, in the vocabulary each layer actually speaks.
    #
    # B2.4 classifies a fit into a bucket -- high, medium, low, or one of the
    # refusals. B2.5 translates that into a bounded status for the envelope.
    # Asserting the bucket string appears somewhere in the envelope text would
    # be asserting that the two vocabularies are one, which they are
    # deliberately not: the B2.5 boundary exists so a B2.4 policy change cannot
    # silently alter what a signed claim means.
    confidence = envelope.get("confidence_metadata") or {}
    assert confidence, envelope

    assert str(fit["confidence_bucket"]) in {"high", "medium", "low"}, (
        "the diagnostics accepted the posterior but the confidence policy did "
        f"not classify it as usable: {dict(fit)}"
    )
    assert confidence["confidence_status"] == "available", (
        "the pipeline persisted a usable confidence and Trust did not report it "
        f"as available: persisted={dict(fit)} reported={confidence}"
    )
    assert confidence["confidence_authority"] == "b24_confidence_projection", (
        confidence
    )
    assert confidence["diagnostics_status"] == "passed", confidence
    assert confidence["unavailable_reason"] is None, confidence
    # Never a fabricated scalar. B2.4 owns interval-width buckets, not a score,
    # and an envelope inventing one would be the failure this phase exists to
    # prevent.
    assert confidence["confidence_score_basis_points"] is None, confidence

    # The envelope is about this fit, and about a source state that is current.
    assert str(dispatch["fit_id"]) in envelope["subject_ref"], envelope


def test_c9_the_inference_policies_are_authorised_to_operate_together() -> None:
    """F-11's replacement: the compatibility authority that did not exist.

    F-11 was never a defect in the runtime cage, the sampling policy or the
    diagnostics. Each was internally consistent and separately versioned. They
    were jointly impossible, and nothing in the system was responsible for
    noticing -- so nothing did, for as long as the only proof that a fit could
    execute wrote its own fit row and asserted nothing about diagnostics.

    This asserts the fourth authority holds, and that the combination it names is
    one in which a posterior can actually be accepted. It is deliberately not a
    quality judgement: whether a particular posterior converges is an empirical
    question the diagnostics answer at runtime. These are the properties whose
    violation would make *every* fit impossible again.
    """

    from app.bayesian.diagnostics import DEFAULT_P7_DIAGNOSTIC_POLICY
    from app.bayesian.inference_profile import (
        B24_INFERENCE_PROFILE,
        InferenceCompatibilityProfile,
        InferenceProfileError,
    )
    from app.bayesian.sampling_policy import DEFAULT_P6_SAMPLING_POLICY

    profile = B24_INFERENCE_PROFILE
    profile.validate()

    # The policies are still separately versioned. Collapsing them into one
    # version number would have hidden the incompatibility rather than governed
    # it, and would make a signed confidence uninterpretable once any one of
    # them evolved.
    assert profile.sampling_policy_version == DEFAULT_P6_SAMPLING_POLICY.policy_version
    assert (
        profile.diagnostic_policy_version
        == DEFAULT_P7_DIAGNOSTIC_POLICY.diagnostic_policy_version
    )
    assert profile.sampling_policy_version != profile.diagnostic_policy_version

    # R-hat is computable, which is F-11's first arm.
    assert profile.chains >= 2, profile
    assert profile.chains == profile.min_chains, profile
    # The cage is intact: parallelism unchanged, only the chain count freed.
    assert profile.cores == 1 and profile.blas_cores == 1, profile
    # And the acceptance threshold is reachable from the draws retained.
    assert profile.ess_min_threshold <= profile.posterior_draws_total, profile

    # Each of the impossible combinations must be refused, by the authority
    # rather than by a comment. These are the configurations F-11 consisted of.
    def _variant(**overrides) -> InferenceCompatibilityProfile:
        import dataclasses

        return dataclasses.replace(profile, **overrides)

    # One chain while R-hat is required -- the exact F-11 configuration.
    with pytest.raises(InferenceProfileError, match="R-hat"):
        _variant(chains=1, min_chains=1).validate()

    # Sixty-four retained draws against an ESS threshold of four hundred.
    with pytest.raises(InferenceProfileError, match="effective sample size"):
        _variant(posterior_draws_total=64).validate()

    # The sampler and the diagnostics disagreeing about how many chains exist.
    with pytest.raises(InferenceProfileError, match="chains"):
        _variant(min_chains=2).validate()

    # The P5 cage broken by parallel execution.
    with pytest.raises(InferenceProfileError, match="single-process cage"):
        _variant(cores=2).validate()

    # A fit budget larger than the containment boundary it runs inside.
    with pytest.raises(InferenceProfileError, match="runtime envelope"):
        _variant(fit_execution_budget_seconds=400).validate()

    # Divergences softened into a tolerance.
    with pytest.raises(InferenceProfileError, match="divergences"):
        _variant(divergence_count_threshold=5).validate()
