"""B2.5-P13 C9-J: available confidence, produced by the chain that claims it.

Every previous proof of a *positive* confidence result in this repository began
from state a test had written. The B2.4-P6 real-fit proof samples a genuine
posterior, but it inserts its own feature authority -- with the cardinalities
spelled out as literals -- and its own ``queued`` fit before it starts. That is
the same fixture substitution that let F-06 hide for as long as it did: a proof
that begins after the seam cannot see whether the seam conducts.

So this journey never writes a feature authority, never writes a fit, and never
constructs a dispatch claim. It performs one real financial settlement run and
then takes, at each stage, exactly what the previous stage produced:

    real settlements committed
      -> production invalidation trigger writes the dirty evidence
        -> production planner judges it fittable and asks for an authority
          -> production cardinality producer measures the exact snapshot
            -> production planner claims the fit and mints a dispatch lease
              -> the dispatch outbox row that lease produced
                -> production worker executes THAT row's payload
                  -> real sampling, real diagnostics, persisted confidence
                    -> production Trust route, signed and JWKS-verified

The bridge to the worker is deliberate and narrow: the payload handed to
``execute_fit_intent`` is ``DispatchOutboxRow.queue_payload`` -- the identical
object production publishes to the broker -- read from the row the planner
actually minted. The broker hop itself is proven separately by the live
transport proof; repeating it here would add a second thing that can break
without adding a fact. What is *not* bridged is any authority: the fit id, the
attempt id, the claim epoch and the payload hash all originate in the planner's
own claim, and if any of them were manufactured here the dispatch fence would
refuse the execution outright.

The negative mirror stays green elsewhere: an unsampled fit must withhold
confidence. This is the other half -- a legitimately sampled fit with accepted
diagnostics must expose one, and it must be the one that was persisted.
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
PER_DAY = 3


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
    for index in range(SETTLEMENT_DAYS * PER_DAY):
        channel = f"c9p_channel_{index:03d}"
        event_id = uuid.uuid4()
        verdict_id = uuid.uuid4()
        occurred_at = (
            DAY
            + timedelta(days=index // PER_DAY)
            + timedelta(hours=2 + (index % PER_DAY) * 4)
        )
        amount = 60_000 + index * 97
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
                "camp": f"c9p-campaign-{index:03d}",
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
    token = f"c9ptok{uuid.uuid4().hex}"
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


def test_c9_available_confidence_comes_from_the_chain_that_claims_it(
    monkeypatch, tmp_path
) -> None:
    """One settlement run reaches a signed, usable confidence. No fixtures."""

    pymc = pytest.importorskip(
        "pymc",
        reason=(
            "the positive-confidence composition samples a real posterior; "
            "install requirements-bayesian.txt to run it"
        ),
    )
    import pytensor

    # Fail here, plainly, rather than sixty seconds later as an opaque timeout.
    #
    # Without a C++ compiler PyTensor evaluates the model graph in pure Python,
    # which cannot draw the governed sample count inside the governed runtime
    # budget. That is an environment fact, not a defect in the chain, and it
    # must not be worked around by lowering either bound: the sampling policy
    # and the execution budget are exactly the governed quantities this journey
    # exists to exercise honestly.
    assert str(pytensor.config.cxx or "").strip(), (
        "this environment has no C++ compiler, so PyTensor cannot compile the "
        "model and the sampling this proof requires cannot finish inside the "
        "governed runtime budget. Run where the B2.4-P6 real-fit proof runs."
    )
    assert pymc.__version__

    monkeypatch.setenv(
        "SKELDIR_TRUST_SIGNING_KEY_SEED_B64URL",
        base64.urlsafe_b64encode(hashlib.sha256(b"b25-p13-c9p-signing").digest())
        .rstrip(b"=")
        .decode("ascii"),
    )
    monkeypatch.setenv("SKELDIR_TRUST_SIGNING_KEY_ID", "kid:b25-p13-c9p")
    monkeypatch.setenv("SKELDIR_TRUST_SIGNING_KEY_VALID_FROM", "2026-01-01T00:00:00Z")
    monkeypatch.setenv("B24_BAYESIAN_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "compiledirs"))

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
        assert _produce_requested_authority(tenant_id) >= 1, (
            "the planner asked for no authority the producer could answer"
        )
        _rearm_authority_waiters(tenant_id)
        _plan(tenant_id, "c9-positive-2")

        dispatch, payload = _lease_claimed_dispatch(tenant_id)

        # --- the worker executes the payload the planner minted --------------
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
                    " diagnostic_failure_reason, confidence_bucket,"
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

    # Sampling actually happened, on the fit the planner created.
    assert fit["sampling_started_at"] is not None, dict(fit)
    assert fit["n_samples_actual"], dict(fit)
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

    # Correspondence first: whatever the pipeline persisted for this exact fit
    # is what Trust must say. This is the assertion that keeps the next one
    # honest -- a number Trust invented would satisfy an availability check and
    # fail this one.
    flat = json.dumps(envelope, default=str)
    assert str(fit["confidence_bucket"]) in flat, (
        f"Trust did not report the persisted confidence bucket "
        f"{fit['confidence_bucket']!r}: {flat[:400]}"
    )
    assert str(dispatch["fit_id"]) in flat, flat[:400]

    # And then the property this gate exists for. A legitimately sampled fit
    # with accepted diagnostics must expose a usable confidence, because the
    # negative mirror -- an unsampled fit withholding one -- is only meaningful
    # if the positive case can actually be reached. Both halves are needed;
    # neither alone distinguishes a working chain from one that always says no.
    assert fit["confidence_bucket"] == "available", (
        "the chain sampled a real posterior but did not expose a usable "
        f"confidence: status={fit['status']!r} "
        f"bucket={fit['confidence_bucket']!r} "
        f"reason={fit['confidence_bucket_reason']!r} "
        f"diagnostics={fit['diagnostic_status']!r}"
    )
    assert fit["r_hat_max"] is not None, dict(fit)
    assert fit["ess_min"] is not None, dict(fit)
    assert fit["confidence_evidence_snapshot_hash"], dict(fit)
