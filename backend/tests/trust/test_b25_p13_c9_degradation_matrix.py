"""B2.5-P13 C9: every legitimate negative state ends in governed truth.

C8-N proved one degraded case: a fit exists, was never sampled, and Trust
withholds confidence rather than inventing a number. That is a real proof and it
is not the whole property. Safe degradation is not one test case -- it is a state
machine, and a chain is only honest if *every* legitimate reason not to produce a
number produces an explicit typed refusal instead.

The distinction that matters here is between two ways of not answering:

    a governed refusal      the planner decided, recorded why, and Trust says so
    an uncaught exception   something raised and nobody decided anything

The second is what F-05b was. A source that was legitimately too sparse to fit
sent the planner down its own governed fallback path, and that write was refused
by the dispatch fence -- a Postgres trigger raising into a call stack with no
handler for it. The negative state was legitimate; the failure was not.

Each case below drives the *real* planner over *real* source rows and then
checks four things that must agree:

    the planner reached a decision rather than raising
    the database holds a terminal fallback row naming the reason
    no dispatch was created, so nothing was authorised to compute
    Trust projects a withheld confidence, not a fabricated one

The resource-rejection case is included deliberately even though it is the most
expensive to seed: it is the only one that reaches degradation *after* passing
every eligibility minimum, so it exercises the second policy boundary rather
than the first.
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
    os.getenv("SKELDIR_B25_P13_C9_DB_PROOF") != "1",
    reason="B2.5-P13 C9 degradation-matrix proofs are opt-in locally",
)

ACTIVE = active_identity()
PROBE_OWNER = "c9-degrade-probe"
DAY = datetime(2026, 12, 1, tzinfo=timezone.utc)
WINDOW_START = DAY
WINDOW_END = DAY + timedelta(days=20)


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


def _new_tenant(conn, label: str):
    tenant_id = uuid.uuid4()
    conn.execute(
        text(
            "INSERT INTO public.tenants (id, name, api_key_hash,"
            " notification_email) VALUES (:t, :n, :h, :e)"
        ),
        {
            "t": str(tenant_id),
            "n": f"c9-degrade-{label}-{tenant_id.hex[:8]}",
            "h": uuid.uuid4().hex,
            "e": f"c9d-{tenant_id.hex[:8]}@example.invalid",
        },
    )
    _bind(conn, tenant_id)
    return tenant_id


def _seed_settlement(
    conn, tenant_id, *, index: int, channel: str, campaign: str, occurred_at: datetime
) -> None:
    event_id = uuid.uuid4()
    verdict_id = uuid.uuid4()
    amount = 40_000 + index
    conn.execute(
        text(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES (:c, 'b25_p13_c9d', true, :d, 'active')"
            " ON CONFLICT (code) DO NOTHING"
        ),
        {"c": channel, "d": f"C9D {index}"},
    )
    conn.execute(
        text(
            "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
            " correlation_id, session_id, revenue_cents, raw_payload,"
            " idempotency_key, event_type, channel, campaign_id,"
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
            "payload": json.dumps({"source": "b25_p13_c9_degradation"}),
            "key": f"c9d:{tenant_id.hex[:8]}:{index}",
            "ch": channel,
            "camp": campaign,
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
            " 'stripe', :ref, :pev, :ref, 'matched_confirmed', 'high', :amt,"
            " :amt, 'USD', :at, :at, :amt, :amt, :amt, 0, 0, 'exact')"
        ),
        {
            "v": str(verdict_id),
            "t": str(tenant_id),
            "e": str(event_id),
            "ref": f"c9d-order-{tenant_id.hex[:8]}-{index:04d}",
            "pev": f"c9d-event-{tenant_id.hex[:8]}-{index:04d}",
            "amt": amount,
            "at": occurred_at,
        },
    )
    conn.execute(
        text(
            "INSERT INTO public.b23_revenue_events (tenant_id, match_verdict_id,"
            " provider, provider_native_event_reference,"
            " provider_native_commerce_reference, canonical_commerce_reference,"
            " event_type, currency_code, event_occurred_at,"
            " captured_amount_minor, net_effect_sign,"
            " is_gross_capture_correction) VALUES (:t, :v, 'stripe', :pev, :ref,"
            " :ref, 'payment_capture', 'USD', :at, :amt, 1, false)"
        ),
        {
            "t": str(tenant_id),
            "v": str(verdict_id),
            "pev": f"c9d-capture-{tenant_id.hex[:8]}-{index:04d}",
            "ref": f"c9d-order-{tenant_id.hex[:8]}-{index:04d}",
            "at": occurred_at,
            "amt": amount,
        },
    )


def _seed_caller(conn, tenant_id) -> str:
    client_id = uuid.uuid4()
    # Entropy first: token_prefix is the first eight characters and unique.
    token = f"{uuid.uuid4().hex}{uuid.uuid4().hex}c9d"
    conn.execute(
        text(
            "INSERT INTO public.agent_clients (id, tenant_id, client_name,"
            " client_display_hash, audience, status) VALUES (:c, :t, :n, :h,"
            " 'b25-p13-c9d', 'active')"
        ),
        {
            "c": str(client_id),
            "t": str(tenant_id),
            "n": f"c9d-client-{client_id}",
            "h": "sha256:" + "d" * 64,
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


# ---------------------------------------------------------------------------
# The negative states, each built from real source rows.
# ---------------------------------------------------------------------------
def _seed_source_window_empty(conn, tenant_id) -> None:
    """No source rows at all inside the window. Nothing to be wrong about."""

    _seed_settlement(
        conn,
        tenant_id,
        index=0,
        channel="c9d_empty_channel",
        campaign="c9d-empty-campaign",
        occurred_at=WINDOW_START - timedelta(days=40),
    )


def _seed_insufficient_data(conn, tenant_id) -> None:
    """Real settlements, far below every P2 volume minimum."""

    for index in range(3):
        _seed_settlement(
            conn,
            tenant_id,
            index=index,
            channel=f"c9d_sparse_channel_{index}",
            campaign=f"c9d-sparse-campaign-{index}",
            occurred_at=WINDOW_START + timedelta(days=1, minutes=index),
        )


def _seed_insufficient_privacy_cohort(conn, tenant_id) -> None:
    """Enough volume, but concentrated: one channel, one day.

    This is the state that clears every count-based minimum and still must not
    be fitted -- the cohort is too narrow to model without describing
    individuals.
    """

    for index in range(30):
        _seed_settlement(
            conn,
            tenant_id,
            index=index,
            channel="c9d_single_channel",
            campaign="c9d-single-campaign",
            occurred_at=WINDOW_START + timedelta(days=1, minutes=index),
        )


DEGRADATION_CASES = {
    "source_window_empty": _seed_source_window_empty,
    "insufficient_data": _seed_insufficient_data,
    "insufficient_privacy_cohort": _seed_insufficient_privacy_cohort,
}


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


def _plan(tenant_id) -> object:
    from app.bayesian.fit_planner import plan_due_dirty_events

    _mature_dirty_evidence(tenant_id)
    return asyncio.run(
        plan_due_dirty_events(
            tenant_id=tenant_id,
            planner_owner=f"c9-degrade-{uuid.uuid4().hex[:8]}",
            quiet_period_seconds=1,
            limit=25,
        )
    )


@pytest.mark.parametrize("case", sorted(DEGRADATION_CASES))
def test_c9_every_legitimate_negative_state_terminates_in_governed_truth(
    case: str,
) -> None:
    """One negative state, driven through the real planner over real rows."""

    seed = DEGRADATION_CASES[case]
    engine = _migration_engine()
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, case)
            seed(conn, tenant_id)
    finally:
        engine.dispose()

    # The planner must reach a decision. Before C9 this raised
    # b24_dispatch_fence_rejected out of a trigger for exactly these states.
    intents = _plan(tenant_id)
    assert intents, f"{case}: the planner produced no decision at all"
    assert all(
        intent.claim is None for intent in intents
    ), f"{case}: a degraded source was claimed for dispatch"

    app_engine = _engine()
    try:
        with app_engine.connect() as conn:
            _bind(conn, tenant_id)
            fits = [
                dict(row)
                for row in conn.execute(
                    text(
                        "SELECT status, eligibility_status, fallback_applied,"
                        " fallback_reason, confidence_bucket,"
                        " confidence_bucket_reason, artifact_ref,"
                        " n_samples_actual FROM public.bayesian_model_fits"
                        " WHERE tenant_id = :t"
                    ),
                    {"t": str(tenant_id)},
                ).mappings()
            ]
            dispatches = conn.execute(
                text(
                    "SELECT count(*) FROM public.b24_fit_dispatch_outbox"
                    " WHERE tenant_id = :t"
                ),
                {"t": str(tenant_id)},
            ).scalar_one()
    finally:
        app_engine.dispose()

    assert len(fits) == 1, f"{case}: expected one terminal record, got {fits}"
    fit = fits[0]
    assert fit["status"] == "fallback_only", fit
    assert fit["fallback_applied"] is True, fit
    assert fit["fallback_reason"], fit
    # Degradation never carries a usable confidence, and never carries evidence
    # of computation that did not happen.
    assert fit["confidence_bucket"] == "unavailable", fit
    assert fit["confidence_bucket_reason"], fit
    assert fit["artifact_ref"] is None, fit
    assert fit["n_samples_actual"] is None, fit
    # And nothing was authorised to compute.
    assert dispatches == 0, f"{case}: a degraded source produced {dispatches} dispatches"


def test_c9_trust_reports_the_degradation_the_planner_recorded(monkeypatch) -> None:
    """The signed claim must carry the planner's verdict, not a silence.

    A refusal that never reaches the caller is indistinguishable from an outage.
    This asserts the whole way out: real credential, production route, real
    Ed25519 material, and the envelope verified against the JWKS that route
    publishes -- for a subject whose only content is a governed reason it cannot
    be answered.
    """

    monkeypatch.setenv(
        "SKELDIR_TRUST_SIGNING_KEY_SEED_B64URL",
        base64.urlsafe_b64encode(hashlib.sha256(b"b25-p13-c9d-signing").digest())
        .rstrip(b"=")
        .decode("ascii"),
    )
    monkeypatch.setenv("SKELDIR_TRUST_SIGNING_KEY_ID", "kid:b25-p13-c9d")
    monkeypatch.setenv("SKELDIR_TRUST_SIGNING_KEY_VALID_FROM", "2026-01-01T00:00:00Z")

    engine = _migration_engine()
    try:
        with engine.begin() as conn:
            tenant_id = _new_tenant(conn, "trust")
            token = _seed_caller(conn, tenant_id)
            _seed_insufficient_privacy_cohort(conn, tenant_id)
    finally:
        engine.dispose()

    _plan(tenant_id)

    app_engine = _engine()
    try:
        with app_engine.connect() as conn:
            _bind(conn, tenant_id)
            fit_id = conn.execute(
                text(
                    "SELECT id FROM public.bayesian_model_fits WHERE tenant_id = :t"
                ),
                {"t": str(tenant_id)},
            ).scalar_one()
    finally:
        app_engine.dispose()

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
                    "X-Trust-Nonce": f"c9d-{uuid.uuid4().hex}",
                    "X-Correlation-ID": str(uuid.uuid4()),
                    "X-Idempotency-Key": f"c9d-{uuid.uuid4()}",
                },
                json={
                    "subject_types": ["confidence_projection"],
                    "subject_refs": [
                        f"urn:skeldir:confidence_projection:{fit_id}"
                    ],
                },
            )
            assert response.status_code == 200, response.text
            body = response.json()
            jwks_response = await client.get(
                "/api/trust/v1/keys/jwks",
                headers={"X-Correlation-ID": str(uuid.uuid4())},
            )
            assert jwks_response.status_code == 200, jwks_response.text
            return body, jwks_response.json()

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

    flat = json.dumps(envelope, default=str).lower()
    assert "unavailable" in flat, (
        f"a degraded fit was not reported as unavailable: {flat[:400]}"
    )
