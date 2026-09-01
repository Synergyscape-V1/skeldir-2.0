"""B2.5-P13 C8-N: how far a financial fact can actually travel.

Both independent audits (Reports 42 and 43) reached the same conclusion by
different routes, and it was not that any individual proof was wrong. It was
that the proofs did not touch. The source-causality suite ends at a dirty row.
The Trust suite begins at a fit row it writes itself. Between those two points
sat the seam where the model identity changed, and because no proof spanned the
seam, a chain that could not physically conduct still measured green end to end.

The remedy cannot be another proof of another segment. It has to be one journey
in which every intermediate authority is produced by the component that owns it:

    a financial fact changes
      -> the production invalidation trigger writes the dirty evidence
        -> the production wake-up trigger makes the tenant due
          -> a real Beat emits onto a real PostgreSQL broker
            -> a real ``celery worker -Q bayesian`` subprocess consumes it
              -> the production planner judges the change fittable
                -> a feature-authority producer supplies the authority
                  -> fit -> confidence -> Trust route -> published JWKS

Nothing in that list is seeded by this module. There is no ``append_dirty_event``
call, no hand-written ``bayesian_model_fits`` row, no ``.run()`` standing in for
delivery, and no dependency override standing in for authentication. Each stage
asserts against an artefact only that stage could have produced, so a break
anywhere makes the journey fail at the stage that broke rather than silently
shortening it.

Built that way, the journey found two things nothing else could.

The first was that the planner never reached a verdict at all. It fitted the
dirty window verbatim, and both invalidation triggers bucket to a single day --
a window the sparse-privacy contract refuses outright, because it cannot span
the twenty distinct days the contract requires. The fallback path the planner
fell to is rejected by the C5 dispatch fence, so the task raised, held its
lease, and left the obligation to expire. That is fixed, and reaching a verdict
here is the first time a real financial change has been judged fittable.

The second is not fixed, and is not this directive's to fix.
``build_feature_authority`` does not build a feature authority. It reads the
table, finds nothing, and parks the request for a sixty-second retry. Nothing in
the application writes that table -- the only writer is called exclusively from
tests, which is precisely how every previous proof of a fit obtained one. So the
chain conducts to that point and stops.

This module asserts that frontier rather than stepping over it. Seeding the
missing authority to reach a signed envelope would be the same substitution both
audits condemned, and would bury the finding under a passing result. The
assertions are two-sided: implement the producer and they go red, delete the
existing writer and they go red. Either way the boundary is stated.

The journey carries a negative interval throughout. Before the worker starts,
messages are on the broker, the durable obligation is unmoved, and no fit exists.
A verdict that could be reached without a worker would mean this module was
proving something about its own process.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text

from app.api import trust_api, trust_keys
from app.bayesian.fit_planner import (
    MIN_FIT_WINDOW_DAYS,
    DirtyPlanningCandidate,
    fit_window_for,
)
from app.bayesian.model_identity import active_identity
from app.core.queues import QUEUE_BAYESIAN
from app.core.secrets import get_database_url
from app.db.dsn import to_sync_postgres_dsn
from app.tasks.bayesian import FIT_PLANNER_TASK_NAME
from app.trust.machine_identity import AgentScope
from tests.test_b24_p9_postgres_runtime import (
    _beat_env,
    _max_broker_message_id,
    _read_log,
    _terminate_worker,
    _wait_for_broker_task_messages,
    _wait_for_log,
    _wait_for_probe_event,
    _worker_env,
)


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_C8_JOURNEY_PROOF") != "1",
    reason="B2.5-P13 C8 contiguous journey proof is opt-in locally",
)

ROOT = Path(__file__).resolve().parents[3]
ACTIVE = active_identity()
PLANNER_BEAT_ENTRY = "b24-fit-planner"

# The window the journey operates in. The change lands inside it but is not
# aligned to its edges, because a window that happens to equal the trigger's own
# day bucket is the one shape F-02 could already handle.
DAY = datetime(2026, 9, 10, tzinfo=timezone.utc)
CHANGE_AT = DAY + timedelta(hours=9)
WINDOW_START = DAY - timedelta(days=6)
WINDOW_END = DAY + timedelta(days=8)


# ---------------------------------------------------------------------------
# Engines. Three principals, each doing only what production lets it do.
# ---------------------------------------------------------------------------
def _engine(url: str | None = None):
    return create_engine(
        to_sync_postgres_dsn(url or get_database_url()),
        pool_pre_ping=True,
        future=True,
    )


def _migration_engine():
    """Tenant and agent-client rows are owned by the migration principal."""

    return _engine(os.environ.get("MIGRATION_DATABASE_URL"))


def _bind(conn, tenant_id: UUID) -> None:
    conn.execute(
        text("SELECT set_config('app.current_tenant_id', :t, false)"),
        {"t": str(tenant_id)},
    )


# ---------------------------------------------------------------------------
# Stage 0. The pre-state: a real financial history, and a caller allowed to ask.
# ---------------------------------------------------------------------------
def _seed_financial_history(
    conn, tenant_id: UUID, *, days: int, per_day: int
) -> list[UUID]:
    """Real attribution events, verdicts and revenue events, in provisional state.

    The referential chain is load-bearing rather than decorative: a confirmed
    verdict is constrained to reference an actual attribution event, which needs
    a governed channel row, and the revenue event needs the verdict. A bare row
    would be a subject the database itself considers impossible.

    The history before the final day is already settled; only the final day is
    left ``matched_provisional``, so the journey has a genuine financial
    transition to make later, rather than a synthetic touch.

    Which day matters. C19 buckets invalidation on the financial event's own
    clock rather than on the settlement clock, so confirming a twenty-day
    backlog in one run marks twenty financial days dirty and the planner works
    through them oldest first -- each of those windows reaching back before any
    data exists, and each correctly refused for density. Settling the backlog
    up front leaves exactly one dirty financial day, and ``fit_window_for``
    anchors on that day's end, so the window the planner fits is the window the
    fixture actually populated.
    """

    verdicts: list[UUID] = []
    settled_rows = (days - 1) * per_day
    for index in range(days * per_day):
        # One channel and one campaign per row. B2.4's sparse-input privacy
        # floor refuses to fit a market thinner than twenty distinct channels,
        # and that guard is production behaviour rather than an obstacle: a
        # journey that cleared it by lowering it would prove nothing about the
        # pipeline a tenant actually gets.
        channel = f"c8n_channel_{index:03d}"
        event_id = uuid4()
        verdict_id = uuid4()
        # Spread across every day of the window the planner will fit. B2.4's
        # sparse-privacy contract requires the source data to span at least
        # ``minimum_source_window_density_days`` distinct days, so a market
        # concentrated on one day is refused however much revenue it carries.
        occurred_at = (
            DAY
            - timedelta(days=days - 1 - (index // per_day))
            + timedelta(hours=2 + (index % per_day) * 3)
        )
        amount = 25_000 + index * 137
        conn.execute(
            text(
                "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
                " display_name, state) VALUES (:c, 'b25_p13_c8n', true, :d,"
                " 'active') ON CONFLICT (code) DO NOTHING"
            ),
            {"c": channel, "d": f"C8N {index}"},
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
                "corr": str(uuid4()),
                "sess": str(uuid4()),
                "amt": amount,
                "payload": json.dumps({"source": "b25_p13_c8n_journey"}),
                "key": f"c8n:{tenant_id.hex[:8]}:{index}",
                "ch": channel,
                "camp": f"c8n-campaign-{index:03d}",
            },
        )
        # C19 made verified allocation lineage the authority for B2.4 source
        # membership. Without it this history is ineligible, the planner records
        # fallback_only, and the journey never reaches a feature-authority
        # request. Seeded unverified; the confirmed verdict projects it.
        conn.execute(
            text(
                "INSERT INTO public.attribution_allocations (id, tenant_id,"
                " event_id, channel_code, allocated_revenue_cents,"
                " allocation_ratio, model_version, model_type,"
                " confidence_score, verified) VALUES (:a, :t, :e, :ch, :amt,"
                " 1.0, 'b25-p13-c8n-v1', 'last_touch', 1.0, false)"
            ),
            {
                "a": str(uuid4()),
                "t": str(tenant_id),
                "e": str(event_id),
                "ch": channel,
                "amt": amount,
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
                " 'stripe', :ref, :pev, :ref, :vstatus, 'high',"
                " :amt, :amt, 'USD', :confirmed, :at, :amt, :amt, :amt, 0, 0,"
                " 'exact')"
            ),
            {
                "v": str(verdict_id),
                "t": str(tenant_id),
                "e": str(event_id),
                "ref": f"c8n-order-{tenant_id.hex[:8]}-{index:03d}",
                "pev": f"c8n-event-{tenant_id.hex[:8]}-{index:03d}",
                "amt": amount,
                "vstatus": (
                    "matched_confirmed" if index < settled_rows
                    else "matched_provisional"
                ),
                "confirmed": occurred_at if index < settled_rows else None,
                # Settled history transitioned when it occurred; the one day
                # left provisional transitions in the settlement run below.
                "at": occurred_at if index < settled_rows else CHANGE_AT,
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
                "pev": f"c8n-capture-{tenant_id.hex[:8]}-{index:03d}",
                "ref": f"c8n-order-{tenant_id.hex[:8]}-{index:03d}",
                "at": occurred_at,
                "amt": amount,
            },
        )
        if index >= settled_rows:
            # Only the still-provisional day is the transition under test.
            verdicts.append(verdict_id)
    return verdicts


# ---------------------------------------------------------------------------
# Observation. Each reads an artefact only one stage in the chain can produce.
# ---------------------------------------------------------------------------
def _dirty_rows(conn, tenant_id: UUID) -> list[dict]:
    _bind(conn, tenant_id)
    return [
        dict(row)
        for row in conn.execute(
            text(
                "SELECT model_type, model_version, source_window_start,"
                " source_window_end, dirty_reason, source_family, status"
                " FROM public.b24_dirty_events WHERE tenant_id = :t"
                " ORDER BY observed_at, id"
            ),
            {"t": str(tenant_id)},
        ).mappings()
    ]


def _wakeup_rows(conn, tenant_id: UUID) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            text(
                "SELECT status, wakeup_revision FROM"
                " public.b24_fit_planner_wakeups WHERE tenant_id = :t"
            ),
            {"t": str(tenant_id)},
        ).mappings()
    ]


def _fit_rows(conn, tenant_id: UUID) -> list[dict]:
    _bind(conn, tenant_id)
    return [
        dict(row)
        for row in conn.execute(
            text(
                "SELECT id, model_type, model_version, status,"
                " source_window_start, source_window_end,"
                " source_snapshot_hash IS NOT NULL AS has_snapshot"
                " FROM public.bayesian_model_fits WHERE tenant_id = :t"
                " ORDER BY created_at, id"
            ),
            {"t": str(tenant_id)},
        ).mappings()
    ]


def _await_planner_verdict(engine, tenant_id: UUID, *, timeout_s: int) -> dict:
    """Block until the planner has durably judged this tenant's dirty evidence.

    Polling is the only honest option: the verdict is reached in another
    process, so the test cannot know when it lands without watching for it. The
    states are read from durable rows rather than inferred from a return value,
    because a planner that returned successfully having done nothing is exactly
    the failure this journey exists to detect.
    """

    import time as _time

    deadline = _time.monotonic() + timeout_s
    state: dict = {}
    while _time.monotonic() < deadline:
        with engine.connect() as conn:
            _bind(conn, tenant_id)
            state = {
                "dirty_status": conn.execute(
                    text(
                        "SELECT string_agg(DISTINCT status, ',') FROM"
                        " public.b24_dirty_events WHERE tenant_id = :t"
                    ),
                    {"t": str(tenant_id)},
                ).scalar_one(),
                "requested_hash": conn.execute(
                    text(
                        "SELECT source_snapshot_hash FROM"
                        " public.b24_feature_authority_build_requests"
                        " WHERE tenant_id = :t ORDER BY created_at DESC LIMIT 1"
                    ),
                    {"t": str(tenant_id)},
                ).scalar_one_or_none(),
                "requested_window": conn.execute(
                    text(
                        "SELECT source_window_start, source_window_end FROM"
                        " public.b24_feature_authority_build_requests"
                        " WHERE tenant_id = :t ORDER BY created_at DESC LIMIT 1"
                    ),
                    {"t": str(tenant_id)},
                ).one_or_none(),
                "authority_requests": conn.execute(
                    text(
                        "SELECT count(*) FROM"
                        " public.b24_feature_authority_build_requests"
                        " WHERE tenant_id = :t"
                    ),
                    {"t": str(tenant_id)},
                ).scalar_one(),
                "feature_authorities": conn.execute(
                    text(
                        "SELECT count(*) FROM"
                        " public.b24_source_window_feature_authority"
                        " WHERE tenant_id = :t"
                    ),
                    {"t": str(tenant_id)},
                ).scalar_one(),
                "fits": conn.execute(
                    text(
                        "SELECT count(*) FROM public.bayesian_model_fits"
                        " WHERE tenant_id = :t"
                    ),
                    {"t": str(tenant_id)},
                ).scalar_one(),
            }
        # Return on a durable milestone, never on a transient status. The
        # authority build request survives its own completion, so it is still
        # observable after the chain has moved on; ``authority_waiting`` is not.
        if state["authority_requests"] or state["fits"]:
            return state
        _time.sleep(2.0)
    raise AssertionError(
        f"the planner reached no durable verdict within {timeout_s}s: {state}"
    )


def _seed_caller(conn, tenant_id: UUID) -> tuple[UUID, str]:
    """A real credential and a real scope grant, not a dependency override.

    The production ``authenticate_machine_caller`` runs against these rows, so
    the envelope this journey obtains is obtained the way a real agent obtains
    one -- including the scope check and the replay check.
    """

    client_id = uuid4()
    # Entropy first: token_prefix is the first eight characters and unique.
    token = f"{uuid4().hex}{uuid4().hex}c8n"
    conn.execute(
        text(
            "INSERT INTO public.agent_clients (id, tenant_id, client_name,"
            " client_display_hash, audience, status) VALUES (:c, :t, :n, :h,"
            " 'b25-p13-c8n', 'active')"
        ),
        {
            "c": str(client_id),
            "t": str(tenant_id),
            "n": f"c8n-client-{client_id}",
            "h": "sha256:" + "c" * 64,
        },
    )
    conn.execute(
        text(
            "INSERT INTO public.agent_service_credentials (id, tenant_id,"
            " agent_client_id, token_prefix, token_hash, hash_algorithm, status,"
            " issued_at) VALUES (:i, :t, :c, :p, :h, 'sha256', 'active', now())"
        ),
        {
            "i": str(uuid4()),
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
            "i": str(uuid4()),
            "t": str(tenant_id),
            "c": str(client_id),
            "s": AgentScope.ENVELOPE_READ.value,
        },
    )
    return client_id, token


def _await_feature_authority(engine, tenant_id: UUID, *, timeout_s: int) -> dict:
    """Block until the producer has written this tenant's snapshot width."""

    import time as _time

    deadline = _time.monotonic() + timeout_s
    row = None
    while _time.monotonic() < deadline:
        with engine.connect() as conn:
            _bind(conn, tenant_id)
            row = conn.execute(
                text(
                    "SELECT source_snapshot_hash, freshness_status, policy_version,"
                    " channel_count, currency_count, provider_count,"
                    " campaign_or_feature_count FROM"
                    " public.b24_source_window_feature_authority"
                    " WHERE tenant_id = :t ORDER BY computed_at DESC LIMIT 1"
                ),
                {"t": str(tenant_id)},
            ).mappings().one_or_none()
        if row is not None:
            return dict(row)
        _time.sleep(2.0)
    raise AssertionError(
        f"no feature authority was produced within {timeout_s}s; the chain "
        "still stops where C8-N first found it stopping"
    )


def _await_fit(engine, tenant_id: UUID, *, timeout_s: int) -> dict:
    """Block until the planner has produced exactly one fit for this tenant."""

    import time as _time

    deadline = _time.monotonic() + timeout_s
    rows: list[dict] = []
    while _time.monotonic() < deadline:
        with engine.connect() as conn:
            rows = _fit_rows(conn, tenant_id)
        if rows:
            break
        _time.sleep(2.0)
    assert rows, (
        f"the feature authority exists but no fit appeared within {timeout_s}s"
    )
    assert len(rows) == 1, f"one change produced {len(rows)} fits: {rows}"
    return rows[0]


def _build_trust_app() -> FastAPI:
    """Production routers, production dependencies, no overrides."""

    app = FastAPI()
    app.include_router(trust_api.router, prefix="/api")
    app.include_router(trust_keys.router, prefix="/api")
    assert not app.dependency_overrides, "C8-N must use production dependencies"
    return app


async def _verified_envelope(app: FastAPI, *, tenant_id: UUID, token: str, fit_id):
    """Fetch one envelope and verify it against the *published* JWKS.

    The registry is rebuilt from the public document rather than reused from
    server state, so a signature that only verifies with private material a
    consumer could never hold is not accepted here.
    """

    from app.trust.jwks import assert_jwks_public_only, registry_from_public_jwks
    from app.trust.verification import verify_trust_envelope

    ref = f"urn:skeldir:confidence_projection:{fit_id}"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/trust/v1/envelopes/query",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-ID": str(tenant_id),
                "X-Trust-Nonce": f"c8n-{uuid4().hex}",
                "X-Correlation-ID": str(uuid4()),
                "X-Idempotency-Key": f"c8n-{uuid4()}",
            },
            json={
                "subject_types": ["confidence_projection"],
                "subject_refs": [ref],
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        envelopes = body.get("envelopes") or body.get("results") or []
        assert len(envelopes) == 1, json.dumps(body)[:400]
        envelope = envelopes[0]

        jwks_response = await client.get(
            "/api/trust/v1/keys/jwks", headers={"X-Correlation-ID": str(uuid4())}
        )
    assert jwks_response.status_code == 200, jwks_response.text
    jwks = jwks_response.json()
    assert assert_jwks_public_only(jwks) >= 1
    verified = verify_trust_envelope(
        envelope, key_registry=registry_from_public_jwks(jwks)
    )
    status = str(getattr(verified, "verification_status", verified))
    assert status in {"valid", "verified"}, (
        f"public-only verification of a chain-produced envelope: {verified}"
    )
    return envelope, verified


def _assert_confidence_reflects_fit(payload: dict, fit: dict) -> None:
    """The signed claim must agree with the fit the pipeline actually has.

    Checked structurally rather than against one hard-coded verdict string, so
    the assertion stays about correspondence: a fit that has not been sampled
    must not be reported as carrying a usable confidence value, and one that has
    must not be reported as withholding it.
    """

    flat = json.dumps(payload, default=str).lower()
    terminal = str(fit["status"]).lower() in {"succeeded", "completed"}
    if terminal:
        assert "unavailable" not in flat, (
            f"a succeeded fit was reported as unavailable: {flat[:400]}"
        )
    else:
        assert (
            "unavailable" in flat or "withheld" in flat or "degraded" in flat
        ), (
            f"a {fit['status']!r} fit was reported as carrying confidence: "
            f"{flat[:400]}"
        )


def _isolate_planner_worklist(engine, tenant_id: UUID) -> int:
    """Leave this tenant as the only obligation the planner can see."""

    with engine.begin() as conn:
        return conn.execute(
            text(
                "DELETE FROM public.b24_fit_planner_wakeups WHERE tenant_id <> :t"
            ),
            {"t": str(tenant_id)},
        ).rowcount


def _purge_queue(engine, queue_name: str) -> int:
    """Drop any broker backlog for one queue. Environment hygiene only."""

    with engine.begin() as conn:
        return conn.execute(
            text(
                "DELETE FROM kombu_message WHERE queue_id = (SELECT id FROM"
                " kombu_queue WHERE name = :q)"
            ),
            {"q": queue_name},
        ).rowcount


# ---------------------------------------------------------------------------
# C8-N. The journey.
# ---------------------------------------------------------------------------
def test_c8_financial_change_reaches_a_jwks_verified_trust_claim(
    tmp_path, monkeypatch
) -> None:
    """One fact, one chain, no substituted authority at any seam."""

    from app.celery_app import celery_app

    # The signing authority the route needs. Supplied the same way the P13 E2E
    # suite supplies it -- a deterministic seed rather than a fixture key -- so
    # the envelope this journey verifies is signed by the production signer
    # holding real Ed25519 material, and the JWKS it verifies against is the
    # document that signer publishes.
    monkeypatch.setenv(
        "SKELDIR_TRUST_SIGNING_KEY_SEED_B64URL",
        base64.urlsafe_b64encode(
            hashlib.sha256(b"b25-p13-c8n-signing-key").digest()
        )
        .rstrip(b"=")
        .decode("ascii"),
    )
    monkeypatch.setenv("SKELDIR_TRUST_SIGNING_KEY_ID", "kid:b25-p13-c8n")
    monkeypatch.setenv(
        "SKELDIR_TRUST_SIGNING_KEY_VALID_FROM", "2026-01-01T00:00:00Z"
    )

    app_engine = _engine()
    admin_engine = _migration_engine()
    original_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = False

    tenant_id = uuid4()
    worker_log = tmp_path / "c8n_worker.log"
    beat_log = tmp_path / "c8n_beat.log"
    probe_log = tmp_path / "c8n_probe.jsonl"
    beat_schedule_db = tmp_path / "c8n_celerybeat-schedule"

    worker_process: subprocess.Popen[str] | None = None
    beat_process: subprocess.Popen[str] | None = None
    worker_handle = worker_log.open("w", encoding="utf-8", buffering=1)
    beat_handle = beat_log.open("w", encoding="utf-8", buffering=1)

    try:
        broker_url = str(celery_app.conf.broker_url)
        assert "postgresql://" in broker_url, broker_url
        assert "memory://" not in broker_url, broker_url

        # -- Stage 0: pre-state ------------------------------------------------
        with admin_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, api_key_hash,"
                    " notification_email) VALUES (:t, :n, :h, :e)"
                ),
                {
                    "t": str(tenant_id),
                    "n": f"c8n-{tenant_id.hex[:8]}",
                    "h": uuid.uuid4().hex,
                    "e": f"c8n-{tenant_id.hex[:8]}@example.invalid",
                },
            )
            _bind(conn, tenant_id)
            # A twenty-day market with three settlements a day: dense enough
            # for every floor the eligibility contract enforces, and no denser.
            _, token = _seed_caller(conn, tenant_id)
            verdicts = _seed_financial_history(
                conn, tenant_id, days=MIN_FIT_WINDOW_DAYS, per_day=3
            )

            # Building the fixture is itself a source write, so the production
            # triggers have already recorded evidence describing the fixture's
            # own construction. It is discarded, and discarding it makes the
            # journey's claim stronger: from here, any dirty row, any wake-up
            # and any fit can only have come from the change made below.
            conn.execute(
                text("DELETE FROM public.b24_dirty_events WHERE tenant_id = :t"),
                {"t": str(tenant_id)},
            )

        # The wake-up ledger carries a policy of ``CURRENT_USER = 'app_worker'``,
        # so it is unreachable from the migration principal -- a silent no-op
        # rather than an error. Clearing it under the worker identity is both
        # what works and what production would do.
        with app_engine.begin() as conn:
            conn.execute(
                text(
                    "DELETE FROM public.b24_fit_planner_wakeups WHERE"
                    " tenant_id = :t"
                ),
                {"t": str(tenant_id)},
            )

        with app_engine.begin() as conn:
            assert _dirty_rows(conn, tenant_id) == [], "pre-state is not quiet"
            assert _wakeup_rows(conn, tenant_id) == [], "pre-state is not quiet"
            assert _fit_rows(conn, tenant_id) == [], "pre-state already has a fit"

        # -- Stage 1: the financial fact changes -------------------------------
        # A provisional verdict becomes confirmed. This is an ordinary UPDATE
        # issued by the ordinary application role. Nothing here knows that a
        # Bayesian pipeline exists.
        with app_engine.begin() as conn:
            _bind(conn, tenant_id)
            changed = conn.execute(
                text(
                    "UPDATE public.b23_match_verdicts SET"
                    " status = 'matched_confirmed', confirmed_at = :at,"
                    " last_transition_at = :at WHERE tenant_id = :t"
                    " AND id = ANY(CAST(:ids AS uuid[]))"
                ),
                {
                    "at": CHANGE_AT,
                    "t": str(tenant_id),
                    "ids": [str(v) for v in verdicts],
                },
            ).rowcount
        assert changed == len(verdicts), changed

        # -- Stage 2: invalidation, written by the production trigger ----------
        with app_engine.connect() as conn:
            dirty = _dirty_rows(conn, tenant_id)
        assert dirty, "a confirmed financial verdict produced no dirty evidence"
        # F-01: the identity the trigger emits must be one Trust can project.
        assert {row["model_type"] for row in dirty} == {ACTIVE.model_type}, dirty
        assert {row["model_version"] for row in dirty} == {ACTIVE.model_version}
        # Confirming a verdict lawfully changes two B2.4 source relations under
        # C19: the verdict itself, and the allocation the verdict projects
        # verification onto. Both must invalidate; neither may be a family the
        # read model refuses.
        assert {row["source_family"] for row in dirty} <= {
            "b23_match_verdicts",
            "attribution_allocations",
        }, dirty
        assert "b23_match_verdicts" in {row["source_family"] for row in dirty}, dirty

        # -- Stage 3: the wake-up, written by the production trigger -----------
        with app_engine.connect() as conn:
            wakeups = _wakeup_rows(conn, tenant_id)
        assert len(wakeups) == 1, wakeups
        assert wakeups[0]["status"] == "pending", wakeups

        # -- Stage 4: real Beat onto a real broker, deliberately unconsumed ----
        # The negative interval. If the fit below could appear without a worker,
        # the journey would be proving something about this test process rather
        # than about the pipeline.
        beat_env = _beat_env(log_path=probe_log, disable_recovery_schedule=True)
        # The Beat entry derives its message ``expires`` from its own interval
        # (interval x 2), so a short interval is not merely noisy -- it is
        # self-defeating. A one-second interval expires messages after two
        # seconds, faster than a solo worker running a real planning pass can
        # drain them, and the queue fills with messages the worker discards as
        # revoked while the live one behind them expires in turn. The pipeline
        # starves with a hot queue. A minute is slow enough that the backlog
        # never forms and long-lived enough that every emission is consumed.
        beat_env["B24_FIT_PLANNER_INTERVAL_SECONDS"] = "60"
        beat_env["B24_FIT_PLANNER_TENANT_BATCH_SIZE"] = "25"
        beat_env["B24_FIT_PLANNER_CANDIDATE_LIMIT"] = "25"
        beat_env.pop("SKELDIR_B24_DISABLE_FIT_PLANNER_JOB", None)

        # Broker hygiene, not evidence management. A database reused across
        # local runs accumulates planner messages that expired long ago; the
        # worker discards them as revoked, but the visibility recovery keeps
        # re-offering them and a solo worker never reaches the live ones. CI
        # builds this database from nothing, so this is a no-op there. The
        # baseline below is taken *after* the purge, so the negative interval
        # still measures only what this journey emitted.
        _purge_queue(app_engine, QUEUE_BAYESIAN)
        # And the same for the planner's worklist. This journey runs last in a
        # database it shares with every earlier P13 step, so the wake-up ledger
        # still holds their tenants. That is not merely noise competing for a
        # bounded batch: plan_due_fit_intents leases its whole batch up front
        # and disposes each tenant in a per-tenant finally, so an exception
        # raised while planning one tenant propagates out of the loop and leaves
        # every tenant leased behind it stranded under a ten-minute lease. One
        # unplannable residue tenant can therefore hold this journey's
        # obligation for longer than any reasonable timeout, and the journey
        # would report a broken chain when what it observed was a stranded
        # batch. Clearing other tenants' wake-ups isolates this journey without
        # touching a single row of its own evidence.
        _isolate_planner_worklist(app_engine, tenant_id)
        with app_engine.connect() as conn:
            baseline_message_id = _max_broker_message_id(conn.engine)
        beat_process = subprocess.Popen(
            [
                sys.executable, "-m", "celery",
                "-A", "app.celery_app.celery_app", "beat",
                "--loglevel=INFO", "--pidfile=",
                "--schedule", str(beat_schedule_db),
            ],
            cwd=ROOT / "backend",
            env=beat_env,
            text=True,
            stdout=beat_handle,
            stderr=subprocess.STDOUT,
        )
        emission = _wait_for_log(beat_log, PLANNER_BEAT_ENTRY, timeout_s=180)
        beat_handle.flush()
        assert beat_process.poll() is None, emission
        assert FIT_PLANNER_TASK_NAME in emission, emission

        messages = _wait_for_broker_task_messages(
            app_engine,
            task_name=FIT_PLANNER_TASK_NAME,
            queue_name=QUEUE_BAYESIAN,
            after_message_id=baseline_message_id,
            timeout_s=60,
        )
        assert messages, "Beat emitted no planner message onto the broker"
        assert {str(row["queue_name"]) for row in messages} == {QUEUE_BAYESIAN}

        with app_engine.connect() as conn:
            assert _wakeup_rows(conn, tenant_id)[0]["status"] == "pending"
            assert _fit_rows(conn, tenant_id) == [], (
                "a fit appeared with no Bayesian worker consuming the queue"
            )

        # -- Stage 5: a real Bayesian worker consumes and the planner runs -----
        worker_env = _worker_env(include_bayesian_tasks=True, log_path=probe_log)
        worker_env["B24_BAYESIAN_WORKSPACE_ROOT"] = str(tmp_path / "workspaces")
        worker_env["B24_PYTENSOR_ROOT"] = str(tmp_path / "compiledirs")
        worker_process = subprocess.Popen(
            [
                sys.executable, "-m", "celery",
                "-A", "app.celery_app.celery_app", "worker",
                "-P", "solo", "-c", "1", "-Q", QUEUE_BAYESIAN,
                "--loglevel=INFO",
                "--without-gossip", "--without-mingle", "--without-heartbeat",
            ],
            cwd=ROOT / "backend",
            env=worker_env,
            text=True,
            stdout=worker_handle,
            stderr=subprocess.STDOUT,
        )
        ready = _wait_for_log(worker_log, " ready", timeout_s=120)
        worker_handle.flush()
        assert worker_process.poll() is None, ready
        assert f".> {QUEUE_BAYESIAN}" in ready, ready

        delivery = _wait_for_probe_event(
            probe_log, "b24_fit_planner_beat_delivery", timeout_s=180
        )
        # The probe is written from inside the task body, so it can only exist
        # if a Bayesian worker executed the planner under the worker login.
        assert delivery["database_user"] == "app_worker", delivery
        assert delivery["task_name"] == FIT_PLANNER_TASK_NAME, delivery

        # -- Stage 6: the planner's verdict, read from durable state ---------
        # The planner accepted the candidate. Before F-05 this was unreachable:
        # the dirty window was fitted verbatim, a one-day window can never span
        # the twenty distinct days the sparse-privacy contract requires, and the
        # fallback the planner fell to is rejected by the C5 dispatch fence -- so
        # the task raised, the lease stayed held, and the obligation sat until it
        # expired. Reaching an authority wait is the first time in the system's
        # history that a real financial change has been judged fittable.
        accepted = _await_planner_verdict(app_engine, tenant_id, timeout_s=900)
        # Asserted on the request rather than on the dirty row's status. The
        # chain now runs to completion in well under the time it takes to poll,
        # so a dirty event can be through ``authority_waiting`` and out the
        # other side before this reads it. A proof that requires catching a
        # transient state is measuring the observer, not the system.
        assert accepted["authority_requests"] >= 1, accepted

        # F-05, observed causally rather than asserted statically. The dirty
        # evidence is a one-day bucket; the window the planner actually went to
        # work on is the derived one. Reading it back from the request the
        # planner durably wrote is what makes this a claim about the running
        # system rather than about the function in isolation.
        expected_start, expected_end = fit_window_for(
            DirtyPlanningCandidate(
                tenant_id=tenant_id,
                model_type=ACTIVE.model_type,
                model_version=ACTIVE.model_version,
                source_window_start=dirty[0]["source_window_start"],
                source_window_end=dirty[0]["source_window_end"],
                dirty_event_count=1,
                first_observed_at=CHANGE_AT,
                last_observed_at=CHANGE_AT,
            )
        )
        assert (expected_end - expected_start).days == MIN_FIT_WINDOW_DAYS
        assert accepted["requested_window"] == (expected_start, expected_end), (
            "the planner asked for an authority over the raw dirty bucket; the "
            f"derived window was {expected_start}..{expected_end} but the "
            f"request records {accepted['requested_window']}"
        )

        # -- Stage 7: the authority the pipeline never used to produce -------
        # C8-N previously stopped here and asserted that it stopped, because
        # build_feature_authority read a table nothing wrote. It writes now, and
        # the assertion is inverted: the width of this snapshot must exist, and
        # it must be the width of the snapshot the planner asked about.
        authority = _await_feature_authority(app_engine, tenant_id, timeout_s=300)
        assert authority["freshness_status"] == "fresh", authority
        assert authority["source_snapshot_hash"] == accepted["requested_hash"], (
            "a feature authority was written for a snapshot nobody asked about"
        )
        # Cardinality, not confidence. The fixture is a known market, so these
        # are exact numbers rather than a range: one settlement provider, one
        # currency, and one channel and one campaign per settlement.
        assert authority["provider_count"] == 1, authority
        assert authority["currency_count"] == 1, authority
        assert authority["channel_count"] == MIN_FIT_WINDOW_DAYS * 3, authority
        assert authority["campaign_or_feature_count"] == MIN_FIT_WINDOW_DAYS * 3

        # -- Stage 8: a fit, produced by the planner from that authority -----
        fit = _await_fit(app_engine, tenant_id, timeout_s=600)
        # F-01 at the far end of the chain: the identity the trigger emitted is
        # the identity the fit carries, which is the identity Trust projects.
        assert fit["model_type"] == ACTIVE.model_type, fit
        assert fit["model_version"] == ACTIVE.model_version, fit
        assert fit["has_snapshot"], fit
        assert fit["source_window_start"] <= CHANGE_AT < fit["source_window_end"], fit

        # -- Stage 9: the signed claim, verified against the published JWKS --
        # The route runs production authentication, the production confidence
        # projection and the production signer. The subject is the fit id the
        # planner chose; nothing in this module picked it.
        loop = asyncio.new_event_loop()
        try:
            envelope, verified = loop.run_until_complete(
                _verified_envelope(
                    _build_trust_app(),
                    tenant_id=tenant_id,
                    token=token,
                    fit_id=fit["id"],
                )
            )
        finally:
            loop.close()
        assert envelope["subject_type"] == "confidence_projection", envelope
        assert str(fit["id"]) in envelope["subject_ref"], envelope
        assert str(
            getattr(verified, "verification_status", verified)
        ) in {"valid", "verified"}, verified

        # -- Stage 10: the claim must describe the chain's real state --------
        # The envelope is signed and verifiable. That is not the same as true.
        # A planner-created fit has not been sampled, so the governed answer is
        # a withheld confidence rather than a number, and the envelope has to
        # say so. An envelope that reported a usable confidence for an unsampled
        # fit would be a verifiable lie, which is worse than an unverifiable one.
        payload = envelope.get("payload") or envelope.get("claims") or envelope
        _assert_confidence_reflects_fit(payload, fit)
        return

    finally:
        celery_app.conf.task_always_eager = original_eager
        for process in (beat_process, worker_process):
            if process is not None:
                _terminate_worker(process)
        beat_handle.close()
        worker_handle.close()
        # The tenant is deliberately left in place. Deleting it would delete its
        # revenue events, and deleting revenue events fires the production
        # DELETE invalidation trigger, which would try to write dirty evidence
        # for a tenant that no longer exists. Every P13 database proof runs
        # against a purpose-built database, so the row costs nothing and the
        # cleanup would cost the journey its meaning.
        app_engine.dispose()
        admin_engine.dispose()


def test_c8_the_feature_authority_producer_is_wired_and_derives_its_rules() -> None:
    """The inverse of the pin C8-N carried while F-06 was open.

    That test asserted no production component wrote the feature authority, and
    said in its own failure message that finding one meant the frontier had
    moved and the journey had to be extended. It has, and this is what replaces
    it: the producer exists, the task that is named for building the authority
    actually builds it, and -- the part worth guarding -- the producer states no
    policy of its own.

    That last property is the whole design. Feature authority measures how wide
    a snapshot is so that two other authorities can decide whether it is
    sufficient and whether it is affordable. A threshold appearing in the
    producer would mean a third opinion had been created about data quality with
    nothing versioning it, which is how the identity space fractured in the
    first place.
    """

    import ast as _ast

    source = (ROOT / "backend/app/bayesian/feature_cardinality.py").read_text(
        encoding="utf-8"
    )
    tree = _ast.parse(source)

    # Prose is not evidence either way, so it is removed before anything is
    # scanned. A docstring explaining why the producer has no TTL must not be
    # what makes a TTL check pass, and must not be what makes it fail.
    for node in _ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body:
            first = body[0]
            if (
                isinstance(first, _ast.Expr)
                and isinstance(first.value, _ast.Constant)
                and isinstance(first.value.value, str)
            ):
                body.pop(0)
    code = _ast.unparse(tree)

    # 1. It is wired: the task reads a table it now also writes.
    task_body = (ROOT / "backend/app/tasks/bayesian.py").read_text(encoding="utf-8")
    start = task_body.index("def build_feature_authority(")
    end = task_body.index("@_bayesian_task", start)
    assert "produce_source_window_feature_authority(" in task_body[start:end], (
        "build_feature_authority still only reads the authority table"
    )

    # 2. Membership is derived, not restated. The producer must not carry its
    #    own copy of the lifecycle values the source contract already renders.
    for restated in ("matched_confirmed", "payment_capture", "processed"):
        assert restated not in code, (
            f"the producer restates source membership ({restated!r}) instead of "
            "deriving it from SOURCE_CONTRACT_AUTHORITY"
        )
    assert "member_predicate(" in code, (
        "the producer does not render membership from the source contract"
    )

    # 3. Caps are read from the resource policy, never spelled out.
    for cap in ("128", "2048", "2_048"):
        assert cap not in code, f"the producer hard-codes a resource cap ({cap})"
    assert "B24_RESOURCE_POLICY.max_channels" in code
    assert "B24_RESOURCE_POLICY.max_providers" in code

    # 4. The bounded counting discipline is the one B2.4 already adjudicated,
    #    and it is a walk rather than an unbounded distinct scan.
    assert "B24_DISTINCT_CARDINALITY_POLICY" in code
    assert "WITH RECURSIVE" in code
    assert "count(distinct" not in code.lower()

    # 5. Freshness is snapshot identity, not elapsed time. A TTL would make a
    #    correct cardinality expire while its snapshot was still on disk, and an
    #    incorrect one survive a change that happened a second later. Checked as
    #    identifiers rather than as text: what matters is whether the producer
    #    computes with a duration, not whether it mentions one.
    identifiers = {
        node.id for node in _ast.walk(tree) if isinstance(node, _ast.Name)
    } | {node.attr for node in _ast.walk(tree) if isinstance(node, _ast.Attribute)}
    forbidden = {"timedelta", "ttl", "expires_at", "max_age", "monotonic"}
    assert not (identifiers & forbidden), (
        "the producer introduces time-based freshness: "
        f"{sorted(identifiers & forbidden)}"
    )
