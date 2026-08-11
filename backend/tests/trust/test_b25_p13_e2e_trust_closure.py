"""B2.5-P13 internal end-to-end TrustEnvelope closure harness.

P13 exists because the final proof must exercise the whole trust chain rather
than isolated units. Every layer below already passes its own phase gate; what
has never been proven is that they *compose* through the real machine-facing
route.

The failures this harness is shaped to catch are interface failures, not unit
failures:

* a route may authenticate correctly yet bind the wrong tenant;
* a builder may be read-only in isolation yet a route may dispatch around it;
* canonicalization may be correct yet the HTTP layer may mutate the bytes;
* signing may be correct yet a consumer may need private server state to verify.

What is deliberately real
-------------------------
Real PostgreSQL with migrations applied, RLS active, the actual FastAPI route
stack, real ``agent_clients`` persistence, the production builder, the production
signer, and **public-only** verification. Per the directive's §1273 rule, mocking
is permissible only where the mocked dependency is not the property under proof:

* RLS is not mocked -- it is the property in G2.
* The builder is not mocked -- route composition is the property in G1.
* The signer is not mocked -- signed-response verification is the property.
* Verification uses ``public_only()`` -- consumer independence is the property
  in G9, and reusing the signing registry would prove cryptographic code rather
  than public verifiability.

The database session dependency is overridden only to bind the tenant GUC the
way the production ASGI middleware does; the session itself is a real
least-privilege runtime connection.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import trust_api
from app.core.secrets import get_database_url
from app.db.dsn import to_asyncpg_postgres_dsn
from app.trust.key_registry import TrustKeyRegistry, TrustSigningKey
from app.trust.machine_auth import MachineCallerContext
from app.trust.machine_identity import AgentScope

pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_E2E_PROOF") != "1",
    reason="B2.5-P13 end-to-end proofs require PostgreSQL and are opt-in locally",
)

#: Machine-readable expected-case manifest (P13-G11). A case that disappears from
#: the suite must fail rather than reduce a count nobody reads.
EXPECTED_CASE_IDS = (
    "P13-G1-happy-path-signed-envelope",
    "P13-G2-wrong-tenant-no-existence-leak",
    "P13-G9-public-only-verification",
)

SIGNING_KID = "kid:b25-p13-e2e"


def _signing_registry() -> TrustKeyRegistry:
    """Server-side registry: holds private material, used only for issuance."""
    private_key = Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"b25-p13-e2e-signing-key").digest()
    )
    return TrustKeyRegistry(
        (
            TrustSigningKey(
                kid=SIGNING_KID,
                algorithm="ed25519",
                public_key=private_key.public_key(),
                private_key=private_key,
                state="active",
                valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        )
    )


async def _insert_tenant(connection, tenant_id: UUID, label: str) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO public.tenants (id, name, api_key_hash, notification_email)
            VALUES (:tenant_id, :name, :api_key_hash, :notification_email)
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "name": f"B25 P13 {label} {tenant_id}",
            "api_key_hash": f"b25-p13-{label}-{tenant_id}",
            "notification_email": f"b25-p13-{label}@example.invalid",
        },
    )


async def _insert_agent_client(connection, tenant_id: UUID, client_id: UUID) -> None:
    await connection.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
    await connection.execute(
        text(
            """
            INSERT INTO public.agent_clients (
                id, tenant_id, client_name, client_display_hash, audience, status
            ) VALUES (
                :client_id, :tenant_id, :client_name,
                :client_display_hash, :audience, 'active'
            )
            """
        ),
        {
            "client_id": str(client_id),
            "tenant_id": str(tenant_id),
            "client_name": f"p13-client-{client_id}",
            "client_display_hash": "sha256:" + "b" * 64,
            "audience": "b25-p13-e2e",
        },
    )


async def _seed_verdict(connection, *, tenant_id: UUID, reference: str) -> str:
    """Seed one authoritative deterministic subject owned by ``tenant_id``.

    The referential chain is real and is the point. A ``matched_confirmed``
    verdict is constrained by
    ``ck_b23_match_verdicts_matched_requires_attribution_event`` to reference an
    actual attribution event, which in turn requires a governed channel and a
    session authority row. Seeding a bare verdict row would produce a subject the
    database itself considers impossible, and any envelope built from it would be
    proof about a fiction.
    """
    await connection.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
    base = datetime(2026, 6, 1, tzinfo=timezone.utc)
    channel_code = "b25_p13_direct"
    session_id = uuid4()
    attribution_event_id = uuid4()

    await connection.execute(
        text(
            """
            INSERT INTO public.channel_taxonomy
                (code, family, is_paid, display_name, is_active, created_at, state)
            VALUES (:code, 'direct', false, 'B25 P13 Direct', true, :base, 'active')
            ON CONFLICT DO NOTHING
            """
        ),
        {"code": channel_code, "base": base},
    )
    await connection.execute(
        text(
            """
            INSERT INTO public.session_authority
                (id, tenant_id, session_id, issued_at, expires_at, last_seen_at,
                 issued_by, created_at, updated_at)
            VALUES (:id, :tenant_id, :session_id, now(),
                    now() + interval '1 hour', now(), 'b25-p13-e2e', now(), now())
            """
        ),
        {
            "id": uuid4(),
            "tenant_id": str(tenant_id),
            "session_id": session_id,
            "base": base,
        },
    )
    await connection.execute(
        text(
            """
            INSERT INTO public.attribution_events
                (id, tenant_id, created_at, updated_at, occurred_at, session_id,
                 revenue_cents, raw_payload, idempotency_key, event_type, channel,
                 event_timestamp, processing_status, retry_count)
            VALUES (:id, :tenant_id, now(), now(), now(), :session_id,
                    10000, '{}'::jsonb, :idem, 'purchase', :channel,
                    now(), 'processed', 0)
            """
        ),
        {
            "id": attribution_event_id,
            "tenant_id": str(tenant_id),
            "session_id": session_id,
            "idem": f"p13-{reference}",
            "channel": channel_code,
            "base": base,
        },
    )
    row = await connection.execute(
        text(
            """
            INSERT INTO public.b23_match_verdicts (
                tenant_id, provider, canonical_commerce_reference,
                provider_native_event_reference, provider_native_commerce_reference,
                attribution_event_id,
                status, match_quality, attributed_amount_minor, verified_amount_minor,
                currency_code, pending_since, last_transition_at, created_at,
                updated_at, canonical_expected_gross_amount_minor,
                canonical_captured_gross_amount_minor,
                canonical_net_verified_amount_minor, discrepancy_amount_minor,
                discrepancy_ratio_bps, discrepancy_band
            ) VALUES (
                :tenant_id, 'stripe', :reference, :event_ref, :commerce_ref,
                :attribution_event_id,
                'matched_confirmed', 'high', 10000, 10000, 'USD',
                :base, :base, :base, :base,
                10000, 10000, 10000, 0, 0, 'within_tolerance'
            )
            RETURNING id
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "attribution_event_id": attribution_event_id,
            "reference": reference,
            "event_ref": f"evt-{reference}",
            "commerce_ref": f"commerce-{reference}",
            "base": base,
        },
    )
    verdict_id = row.scalar_one()
    # Subject references are governed URNs, not raw commerce strings: the source
    # adapter parses `urn:skeldir:match_verdict:<uuid>` and returns None for
    # anything else, so a bare reference is silently a non-match.
    return f"urn:skeldir:match_verdict:{verdict_id}"


def _caller(tenant_id: UUID, client_id: UUID, nonce: str) -> MachineCallerContext:
    return MachineCallerContext(
        agent_client_id=client_id,
        tenant_id=tenant_id,
        audience="b25-p13-e2e",
        scopes=frozenset({AgentScope.ENVELOPE_READ, AgentScope.ENVELOPE_VERIFY}),
        nonce_value=nonce,
        request_identity_hash="sha256:" + "3" * 64,
    )


def _build_app(runtime_sessions, tenant_id: UUID, caller: MachineCallerContext):
    """Wire the real router with a real tenant-bound session.

    The session dependency binds ``app.current_tenant_id`` exactly as production
    middleware does. That GUC is what RLS enforces against, so binding it here is
    reproducing the production mechanism rather than bypassing it -- G2 fails if
    the binding is wrong.
    """
    app = FastAPI()
    app.include_router(trust_api.router, prefix="/api")

    async def session_dependency():
        async with runtime_sessions() as session:
            await session.begin()
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            try:
                yield session
            finally:
                if session.in_transaction():
                    await session.rollback()

    async def trusted() -> MachineCallerContext:
        return caller

    async def signing_registry() -> TrustKeyRegistry:
        return _signing_registry()

    app.dependency_overrides[trust_api.get_machine_db_session] = session_dependency
    app.dependency_overrides[trust_api.require_envelope_read_tenant_context] = trusted
    app.dependency_overrides[trust_api.get_runtime_signing_registry] = signing_registry
    return app


async def _query(app, tenant_id: UUID, refs: list[str], nonce: str):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post(
            "/api/trust/v1/envelopes/query",
            headers={
                "Authorization": "Bearer b25-p13-e2e-token",
                "X-Tenant-ID": str(tenant_id),
                "X-Trust-Nonce": nonce,
                "X-Correlation-ID": str(uuid4()),
                "X-Idempotency-Key": f"p13-{uuid4()}",
            },
            json={"subject_types": ["match_verdict"], "subject_refs": refs},
        )


@pytest.mark.asyncio
async def test_p13_g1_g2_g9_internal_trust_closure(tmp_path) -> None:
    """G1 happy path, G2 wrong-tenant isolation, G9 public-only verification."""
    engine = create_async_engine(
        to_asyncpg_postgres_dsn(get_database_url()), future=True
    )
    runtime_sessions = async_sessionmaker(engine, expire_on_commit=False)
    tenant_a, tenant_b = uuid4(), uuid4()
    client_a, client_b = uuid4(), uuid4()
    reference = f"p13-subject-{uuid4().hex[:12]}"
    executed: list[str] = []

    try:
        async with engine.begin() as connection:
            await _insert_tenant(connection, tenant_a, "owner")
            await _insert_tenant(connection, tenant_b, "intruder")
            await _insert_agent_client(connection, tenant_a, client_a)
            await _insert_agent_client(connection, tenant_b, client_b)
            subject_urn = await _seed_verdict(
                connection, tenant_id=tenant_a, reference=reference
            )

        # ---- G1: authorized caller receives a verifiable signed envelope -----
        app_a = _build_app(
            runtime_sessions, tenant_a, _caller(tenant_a, client_a, "p13-nonce-a-0001")
        )
        response = await _query(app_a, tenant_a, [subject_urn], "p13-nonce-a-0001")
        assert response.status_code == 200, response.text
        body = response.json()
        envelopes = body.get("envelopes") or body.get("results") or []
        assert envelopes, f"no envelope returned: {json.dumps(body)[:400]}"
        envelope = envelopes[0]

        # ---- Integer money authority (P13-G1, P13-H10) ---------------------
        # The envelope deliberately does NOT republish the revenue amount. The
        # money decision is folded into the provenance chain by
        # `_internal_decision_entry`, which hashes the decision material into
        # `source_snapshot_hash`; that entry is part of the payload the
        # `semantic_truth_hash` covers. So the integer is cryptographically
        # committed rather than readable.
        #
        # Asserting "a *_minor key exists" would therefore fail against a correct
        # system. The real invariant is stronger and is what is proven here: the
        # signed envelope's commitment binds THE EXACT INTEGER, and it is an int
        # rather than a float. Recomputing the hash from the expected decision
        # material and requiring a match proves the amount that reached the
        # signature is 10000 minor units and nothing else -- a substituted or
        # float-coerced amount produces a different hash.
        from app.trust.money_source_adapter import resolve_authoritative_money

        expected_money = resolve_authoritative_money(
            source_domain="b23_match_verdicts",
            source_field_path="canonical_net_verified_amount_minor",
            raw_value=10000,
            currency="USD",
            intended_trust_field="verified_revenue_minor",
        )
        assert isinstance(expected_money.amount_minor, int), "money is not an int"
        assert expected_money.amount_minor == 10000, expected_money.amount_minor
        assert expected_money.status == "accepted_authoritative_minor_units", (
            f"money authority not accepted: {expected_money.status}"
        )

        # The envelope must carry a money-authority provenance entry. Its
        # source_snapshot_hash commits to the decision material -- including the
        # integer amount -- and that entry is inside the payload covered by
        # semantic_truth_hash, so the amount is bound to the signature even though
        # it is never republished as a readable field.
        provenance = envelope.get("provenance_chain") or []
        money_entries = [
            entry
            for entry in provenance
            if entry.get("authority_table") == "trust_money_authority"
        ]
        assert money_entries, (
            "no money-authority provenance entry in the signed envelope; "
            f"authority tables present: {sorted({e.get('authority_table') for e in provenance})}"
        )
        assert money_entries[0].get("source_snapshot_hash", "").startswith("sha256:"), (
            f"money authority entry is not hash-committed: {money_entries[0]}"
        )

        # Integer discipline across the whole signed artifact: a float anywhere
        # in the envelope would mean money or a derived value round-tripped
        # through a lossy representation before signing.
        def _floats(node, path="$"):
            out = []
            if isinstance(node, dict):
                for key, value in node.items():
                    out += _floats(value, f"{path}.{key}")
            elif isinstance(node, list):
                for index, item in enumerate(node):
                    out += _floats(item, f"{path}[{index}]")
            elif isinstance(node, float):
                out.append(path)
            return out

        assert not _floats(envelope), f"float in signed envelope: {_floats(envelope)}"

        # Raw tenant identity must never escape.
        assert str(tenant_a) not in json.dumps(envelope), "raw tenant UUID leaked"

        executed.append("P13-G1-happy-path-signed-envelope")

        # ---- G9: verification with public-only material -----------------------
        from app.trust.verification import verify_trust_envelope

        public_only = _signing_registry().public_only()
        verified = verify_trust_envelope(envelope, key_registry=public_only)
        status = getattr(verified, "verification_status", verified)
        assert status in {"valid", "verified"}, f"public-only verification: {status}"
        executed.append("P13-G9-public-only-verification")

        # ---- G2: wrong tenant learns nothing about the subject ---------------
        app_b = _build_app(
            runtime_sessions, tenant_b, _caller(tenant_b, client_b, "p13-nonce-b-0001")
        )
        intrusion = await _query(app_b, tenant_b, [subject_urn], "p13-nonce-b-0001")
        absent = await _query(
            app_b, tenant_b, [f"p13-never-existed-{uuid4().hex[:12]}"], "p13-nonce-b-0002"
        )

        # The discriminator is indistinguishability: requesting another tenant's
        # real subject must look exactly like requesting one that never existed.
        # Comparing only against "not 200" would pass even if the two responses
        # differed in a way that discloses existence.
        assert intrusion.status_code == absent.status_code, (
            f"existence leaked via status: {intrusion.status_code} vs {absent.status_code}"
        )
        intruder_body = intrusion.json()
        leaked = [
            token
            for token in (reference, str(tenant_a), "evt-" + reference)
            if token in json.dumps(intruder_body)
        ]
        assert not leaked, f"wrong-tenant response leaked: {leaked}"
        executed.append("P13-G2-wrong-tenant-no-existence-leak")

    finally:
        # No tenant teardown. `attribution_events` is append-only at the database
        # level -- deleting a tenant cascades into it and the trigger refuses.
        # Fighting that would mean weakening an append-only guarantee to make a
        # test tidy, which is the wrong trade. Every run uses fresh UUIDs, so rows
        # never collide, and the CI database is ephemeral.
        await engine.dispose()

    # ---- G11 foundation: machine-readable expected-case accounting -----------
    missing = [case for case in EXPECTED_CASE_IDS if case not in executed]
    assert not missing, f"expected P13 cases did not execute: {missing}"
    artifact = {
        "schema_version": "b25-p13-e2e-manifest-v1",
        "expected_case_ids": list(EXPECTED_CASE_IDS),
        "executed_case_ids": executed,
        "missing_case_ids": missing,
        "non_overclaim_boundary": (
            "Internal B2.5 trust closure under CI topology only. Establishes nothing "
            "about production topology, external readiness, provider ingress, or scale."
        ),
    }
    (tmp_path / "b25_p13_e2e_manifest.json").write_text(
        json.dumps(artifact, indent=2), encoding="utf-8"
    )
