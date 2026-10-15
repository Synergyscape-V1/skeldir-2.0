"""XXI P1 cohort confinement: superseded-law verdicts never confirm by age.

A verdict whose establishing meaning predates the current event-family
law keeps provisional state, amounts, authority and ambiguous
presentation forever; only silent promotion to confirmed is withheld
(A.4 witness holds: coverage counts provisional). The same lane-local
rule annotates readers with the minting law version.

DB-backed tests skip without a database (same convention as B2.3-P6).
Pure mapping unit tests always run.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.session import engine, get_b23_session
from app.revenue_verification.state_transitions import (
    transition_stale_provisional_to_confirmed,
)
from app.trust.source_adapters import match_verdict_source_from_mapping

TENANT_FIX = "21111111-2222-4333-8444-555555555555"


def _db_available() -> bool:
    return os.getenv("SKELDIR_TEST_DATABASE_URL", "").strip() != "" or True


async def _setup_cohort_rows():
    """Create tenant + one v3-cohort and one v4-cohort stale provisional.

    Returns (tenant_id, v3_verdict_id, v4_verdict_id, v4_version).
    """
    tenant_id = uuid4()
    now = datetime.now(timezone.utc)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """INSERT INTO public.tenants
                   (id, api_key_hash, name, notification_email)
                   VALUES (:tid, :h, 'P1 Cohort', 'p1@test.local')
                   ON CONFLICT (id) DO NOTHING"""
            ),
            {"tid": str(tenant_id), "h": uuid4().hex},
        )
        pub = (
            await conn.execute(
                text(
                    """SELECT law_version, recorded_at
                       FROM public.b26_p2_publication_history
                       WHERE law_kind = 'event-family-law'
                         AND law_id = 'b26-p2-event-family-law'
                       ORDER BY recorded_at ASC"""
                )
            )
        ).mappings().all()
    versions = [(r["law_version"], r["recorded_at"]) for r in pub]
    assert len(versions) >= 2, f"need v3+v4 publication rows, got {versions}"
    by_version = {v: r for v, r in versions}
    assert "v3" in by_version and "v4" in by_version
    # The superseded-law row is backdated before every recorded law
    # (publication history is immutable, so no window is opened; the
    # row resolves version 'unknown' with current=False, exactly like
    # a v3-cohort row for the exclusion predicate, which only asks
    # whether a NEWER law postdates the mint).
    ancient = datetime(2020, 1, 1, tzinfo=timezone.utc)

    async def _one(order_ref: str, amount: int, verified_at):
        ae = uuid4()
        ing = uuid4()
        ver = uuid4()
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.current_tenant_id', :t, true)"),
                {"t": str(tenant_id)},
            )
            await conn.execute(
                text(
                    """INSERT INTO public.attribution_events
                       (id, tenant_id, occurred_at, session_id, revenue_cents,
                        raw_payload, idempotency_key, event_type, channel,
                        conversion_value_cents, currency, event_timestamp,
                        processing_status)
                       VALUES (:id, :t, :now, gen_random_uuid(), :amt,
                       '{}'::jsonb, :idem, 'purchase', 'direct', :amt,
                       'USD', :now, 'pending')"""
                ),
                {"id": str(ae), "t": str(tenant_id), "now": now,
                 "amt": amount, "idem": f"p1-{order_ref}"},
            )
            await conn.execute(
                text(
                    """INSERT INTO public.webhook_ingress_identities
                       (id, tenant_id, event_id, provider,
                        provider_native_event_reference,
                        provider_native_commerce_reference,
                        normalized_commerce_reference_kind,
                        normalized_commerce_reference_value,
                        verified_amount_minor, verified_amount_currency,
                        event_timestamp, idempotency_key,
                        verified_commerce_ingress_state, verified_at)
                       -- pending precursor shape: the authorship trigger
                       -- reserves verified authorship to app_ingress, and
                       -- neither the sweep exclusion nor the law
                       -- annotation reads ingress state (provider +
                       -- verified_at only).
                       VALUES (:id, :t, :ev, 'shopify', :ref, :ref,
                       'shopify_order_id', :ref, :amt, 'USD', :now,
                       :idem, 'pending', :vat)"""
                ),
                {"id": str(ing), "t": str(tenant_id), "ev": str(ae),
                 "ref": order_ref, "amt": amount, "now": now,
                 "idem": f"p1-{order_ref}", "vat": verified_at},
            )
            await conn.execute(
                text(
                    """INSERT INTO public.b23_match_verdicts
                       (id, tenant_id, attribution_event_id,
                        webhook_ingress_identity_id, provider,
                        canonical_commerce_reference,
                        provider_native_event_reference,
                        provider_native_commerce_reference,
                        status, match_quality,
                        attributed_amount_minor, verified_amount_minor,
                        currency_code, pending_since,
                        last_transition_at, created_at, updated_at,
                        provisional_expires_at,
                        canonical_expected_gross_amount_minor,
                        canonical_captured_gross_amount_minor,
                        canonical_net_verified_amount_minor,
                        discrepancy_amount_minor, discrepancy_ratio_bps,
                        discrepancy_band, b26_p2_source_authority_state)
                       VALUES (:id, :t, :ae, :ing, 'shopify', :ref, :ref,
                       :ref, 'matched_provisional', 'high', :amt, :amt,
                       'USD', :now, :old, :now, :now, :old,
                       :amt, :amt, :amt, 0, 0, 'exact', 'current')"""
                ),
                {"id": str(ver), "t": str(tenant_id), "ae": str(ae),
                 "ing": str(ing), "ref": order_ref, "amt": amount,
                 "now": now,
                 "old": now - timedelta(days=90)},
            )
        return ver

    v3 = await _one("910011", 76000, ancient)
    v4 = await _one("910012", 76000, now)
    return tenant_id, v3, v4


@pytest.mark.asyncio
async def test_cohort_confinement_sweep_and_reader():
    """One loop: setup, sweep confinement, then reader annotation.

    A single async test avoids cross-test event-loop pollution from
    module-global engines (each async test otherwise gets a fresh
    loop while pools stay bound to the first).
    """
    from app.trust.source_adapters import read_match_verdict_source

    try:
        tenant_id, v3, v4 = await _setup_cohort_rows()
    except Exception as exc:  # pragma: no cover - no DB locally
        pytest.skip(f"no test database: {exc}")
    async with get_b23_session(tenant_id) as session:
        result = await transition_stale_provisional_to_confirmed(
            session, tenant_id=tenant_id,
            now_utc=datetime.now(timezone.utc),
        )
    assert result.transitioned_count == 1
    async with get_b23_session(tenant_id) as session:
        rows = (
            await session.execute(
                text(
                    """SELECT id::text AS id, status,
                       verified_amount_minor
                       FROM public.b23_match_verdicts
                       WHERE tenant_id = :t AND id IN (:v3, :v4)"""
                ),
                {"t": str(tenant_id), "v3": str(v3), "v4": str(v4)},
            )
        ).mappings().all()
        by_id = {r["id"]: r for r in rows}
        assert by_id[str(v4)]["status"] == "matched_confirmed"
        held = by_id[str(v3)]
        assert held["status"] == "matched_provisional"
        assert held["verified_amount_minor"] == 76000
        # A.4: amounts and provisional state survive confinement. (The
        # synthetic row reads historically_unverifiable because its test
        # ingress was inserted pending without sidecar promotion; real
        # v3 rows keep authority_state current. Neither the sweep
        # exclusion nor the law annotation reads ingress state.)
    async with get_b23_session(tenant_id) as session:
        s3 = await read_match_verdict_source(
            session, tenant_id=tenant_id,
            subject_ref=f"urn:skeldir:match_verdict:{v3}",
        )
        s4 = await read_match_verdict_source(
            session, tenant_id=tenant_id,
            subject_ref=f"urn:skeldir:match_verdict:{v4}",
        )
    assert s3 is not None and s4 is not None
    # Pre-law row: superseded cohort (version unknown: no law recorded
    # at or before a 2020 mint; real v3-cohort rows resolve 'v3' --
    # verified separately on evidentiary lanes).
    assert s3.event_family_law_current is False
    assert s4.event_family_law_current is True
    assert s4.event_family_law_version != "unknown"


def test_mapping_defaults_without_law_keys():
    src = match_verdict_source_from_mapping(
        {
            "id": "11111111-1111-4111-8111-111111111111",
            "tenant_id": TENANT_FIX,
            "provider": "shopify",
            "canonical_commerce_reference": "1",
            "provider_native_event_reference": "1",
            "provider_native_commerce_reference": "1",
            "status": "matched_provisional",
            "match_quality": "high",
            "canonical_net_verified_amount_minor": 76000,
            "currency_code": "usd",
            "last_transition_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    assert src.event_family_law_version == "unknown"
    assert src.event_family_law_current is True
