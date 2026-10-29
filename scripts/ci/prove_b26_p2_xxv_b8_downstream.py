#!/usr/bin/env python3
"""B8 downstream reader proof on the provider-recovered XX cohort."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, Request

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

EVIDENCE = Path(
    os.environ.get(
        "B8_REPLAY_EVIDENCE",
        r"C:/Users/ayewhy/AppData/Local/Temp/b26p2xxv-lane/evidence/xxv-b8-provider-replay.json",
    )
)
OUT = Path(
    os.environ.get(
        "B8_DOWNSTREAM_OUT",
        r"C:/Users/ayewhy/AppData/Local/Temp/b26p2xxv-lane/evidence/xxv-b8-downstream.json",
    )
)
DATABASE = "xxv_b8_replay6_xx"


def main() -> int:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    xx = next(item for item in evidence["generations"] if item["generation"] == "XX")
    recovery = xx["recovery"]
    tenant = xx["before"]["verdict"][1]
    verdict = xx["before"]["verdict"][0]
    source_journal = recovery["source_journal"]
    source_public = recovery["source_public_key"]

    from app.trust.history_witness import generate_keypair

    witness_seed, witness_public = generate_keypair()
    work = Path(r"C:/Users/ayewhy/AppData/Local/Temp/b8-downstream")
    work.mkdir(parents=True, exist_ok=True)
    (work / "witness.key").write_text(witness_seed, encoding="utf-8")
    (work / "witness.pub").write_text(witness_public, encoding="utf-8")
    journal = work / "history_witness.jsonl"
    custody = work / "history_witness_custody.json"
    heartbeat = work / "history_witness_heartbeat.json"
    for path in (journal, custody, heartbeat):
        if path.exists():
            path.unlink()

    os.environ["DATABASE_URL"] = (
        f"postgresql+asyncpg://app_worker:app_worker@127.0.0.1:55471/{DATABASE}"
    )
    os.environ["MIGRATION_DATABASE_URL"] = (
        f"postgresql://postgres:postgres@127.0.0.1:55471/{DATABASE}"
    )
    os.environ["ENVIRONMENT"] = "ci"
    os.environ["TESTING"] = "1"
    os.environ["B26_P2_SOURCE_ATTESTATION_REQUIRED"] = "true"
    os.environ["B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH"] = source_public
    os.environ["B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH"] = source_journal
    os.environ["B26_P2_HISTORY_WITNESS_REQUIRED"] = "true"
    os.environ["B26_P2_HISTORY_WITNESS_JOURNAL_PATH"] = str(journal)
    os.environ["B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH"] = str(work / "witness.pub")
    os.environ["B26_P2_HISTORY_WITNESS_PRIVATE_KEY_PATH"] = str(work / "witness.key")
    os.environ["B26_P2_HISTORY_WITNESS_CUSTODY_PATH"] = str(custody)
    os.environ["B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH"] = str(heartbeat)
    os.environ["B26_P2_HISTORY_WITNESS_GENESIS_HASH"] = ""
    os.environ["TRUST_ISSUANCE_DATABASE_URL"] = (
        f"postgresql+asyncpg://app_trust_issuer:app_trust_issuer@127.0.0.1:55471/{DATABASE}"
    )
    os.environ["TRUST_SIGNER_DATABASE_URL"] = (
        f"postgresql+asyncpg://app_trust_signer:app_trust_signer@127.0.0.1:55471/{DATABASE}"
    )
    os.environ["SKELDIR_TRUST_SIGNING_KEY_SEED_B64URL"] = (
        base64.urlsafe_b64encode(hashlib.sha256(b"b8-downstream-signing").digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    os.environ["SKELDIR_TRUST_SIGNING_KEY_ID"] = "kid:b8-downstream"
    os.environ["SKELDIR_TRUST_SIGNING_KEY_VALID_FROM"] = "2026-01-01T00:00:00Z"

    from app.db.session import AsyncSessionLocal
    from app.tasks.b26_p2_history import observe_history_integrity
    from app.trust.builder import (
        TrustEnvelopeBuildRequest,
        build_unsigned_trust_envelope,
        read_history_integrity_status,
    )
    from app.trust.source_adapters import read_match_verdict_source
    from sqlalchemy import text

    async def run():
        observation = await observe_history_integrity()
        from app.core.config import settings as live_settings  # noqa: PLC0415

        first_line = journal.read_text(encoding="utf-8").splitlines()[0]
        live_settings.B26_P2_HISTORY_WITNESS_GENESIS_HASH = json.loads(
            first_line
        )["payload"]["checkpoint_hash"]
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :t, false)"),
                {"t": tenant},
            )
            source = await read_match_verdict_source(
                session,
                tenant_id=uuid.UUID(tenant),
                subject_ref=f"urn:skeldir:match_verdict:{verdict}",
            )
            request = TrustEnvelopeBuildRequest(
                tenant_id=uuid.UUID(tenant),
                subject_type="match_verdict",
                subject_ref=f"urn:skeldir:match_verdict:{verdict}",
                request_context={
                    "created_at": datetime.now(timezone.utc),
                    "valid_until": datetime.now(timezone.utc).replace(
                        year=datetime.now(timezone.utc).year + 1
                    ),
                    "audience_id": "b8-downstream-proof",
                },
            )
            history_ok, history_reason = await read_history_integrity_status(
                session
            )
            result = await build_unsigned_trust_envelope(
                session, request, source=source
            )
            return observation, source, result, history_ok, history_reason

    observation, source, result, history_ok, history_reason = asyncio.run(run())
    payload = result.unsigned_payload or {}

    # Signed production Trust route on the same recovered cohort. The
    # dependency override supplies the app_user DB principal; machine-token
    # authentication is a separate boundary and is not claimed here.
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import text as sql_text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from app.api import trust_api, trust_keys
    from app.trust.jwks import assert_jwks_public_only, registry_from_public_jwks
    from app.trust.verification import verify_trust_envelope

    trust_app = FastAPI()
    trust_app.include_router(trust_api.router, prefix="/api")
    trust_app.include_router(trust_keys.router, prefix="/api")
    api_engine = create_async_engine(
        f"postgresql+asyncpg://app_user:app_user@127.0.0.1:55471/{DATABASE}"
    )

    async def app_user_session(
        request: Request, x_tenant_id: uuid.UUID = Header(alias="X-Tenant-ID")
    ):
        async with AsyncSession(api_engine) as session:
            await session.execute(
                sql_text("SELECT set_config('app.current_tenant_id', :t, false)"),
                {"t": str(x_tenant_id)},
            )
            request.state.db_session = session
            yield session

    trust_app.dependency_overrides[trust_api.get_machine_db_session] = app_user_session

    # Seed one machine caller so the production auth dependency, not only the
    # app_user session override, is exercised.
    import psycopg2  # noqa: PLC0415

    token = uuid.uuid4().hex + uuid.uuid4().hex
    token_prefix = token[:8]
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    client_id = str(uuid.uuid4())
    conn = psycopg2.connect(
        f"postgresql://postgres:postgres@127.0.0.1:55471/{DATABASE}"
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.agent_clients"
                " (id, tenant_id, client_name, client_display_hash, audience, status)"
                " VALUES (%s, %s, %s, %s, 'b8-downstream', 'active')",
                (client_id, tenant, f"b8-downstream-{client_id[:8]}", "sha256:" + "e" * 64),
            )
            cur.execute(
                "INSERT INTO public.agent_service_credentials"
                " (id, tenant_id, agent_client_id, token_prefix, token_hash,"
                "  hash_algorithm, status, issued_at)"
                " VALUES (%s, %s, %s, %s, %s, 'sha256', 'active', now())",
                (str(uuid.uuid4()), tenant, client_id, token_prefix, token_hash),
            )
            for scope in (
                "trust.envelope.read",
                "trust.envelope.verify",
                "trust.keys.read",
            ):
                cur.execute(
                    "INSERT INTO public.agent_scope_grants"
                    " (id, tenant_id, agent_client_id, scope_value, granted_at)"
                    " VALUES (%s, %s, %s, %s, now())",
                    (str(uuid.uuid4()), tenant, client_id, scope),
                )
    finally:
        conn.close()

    async def signed_query():
        async with AsyncClient(
            transport=ASGITransport(app=trust_app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/trust/v1/envelopes/query",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-ID": tenant,
                    "X-Trust-Nonce": f"b8-{uuid.uuid4().hex}",
                    "X-Correlation-ID": str(uuid.uuid4()),
                    "X-Idempotency-Key": f"b8-{uuid.uuid4()}",
                },
                json={
                    "subject_types": ["match_verdict"],
                    "subject_refs": [f"urn:skeldir:match_verdict:{verdict}"],
                },
            )
            jwks = await client.get(
                "/api/trust/v1/keys/jwks",
                headers={"X-Correlation-ID": str(uuid.uuid4())},
            )
            return response, jwks

    signed_response, signed_jwks = asyncio.run(signed_query())
    signed_body = signed_response.json() if signed_response.status_code == 200 else {}
    envelopes = signed_body.get("envelopes") or signed_body.get("results") or []
    signed_envelope = envelopes[0] if envelopes else None
    signed_verified = None
    if signed_envelope is not None and signed_jwks.status_code == 200:
        signed_verified = verify_trust_envelope(
            signed_envelope,
            key_registry=registry_from_public_jwks(signed_jwks.json()),
        )
    signed_money = (
        signed_envelope.get("verified_revenue_minor") if signed_envelope else None
    )

    # Coverage is the remaining downstream surface. It is read from the same
    # recovered tenant/window through the canonical coverage authority.
    from datetime import timedelta  # noqa: PLC0415

    from app.finance_reconciliation.coverage_authority import (  # noqa: PLC0415
        resolve_canonical_coverage,
    )

    coverage_engine = create_async_engine(
        f"postgresql+asyncpg://app_user:app_user@127.0.0.1:55471/{DATABASE}"
    )

    async def coverage_read():
        async with AsyncSession(coverage_engine) as session:
            await session.execute(
                sql_text("SELECT set_config('app.current_tenant_id', :t, false)"),
                {"t": tenant},
            )
            return await resolve_canonical_coverage(
                session,
                tenant_id=uuid.UUID(tenant),
                window_start=datetime(2026, 2, 1, tzinfo=timezone.utc),
                window_end=datetime(2026, 2, 1, tzinfo=timezone.utc)
                + timedelta(days=1),
                supported_platforms=None,
                currency_code="USD",
            )

    coverage = asyncio.run(coverage_read())
    asyncio.run(coverage_engine.dispose())
    coverage_result = coverage.result
    coverage_payload = {
        "numerator_matched_webhook_revenue_minor": (
            coverage_result.numerator_matched_webhook_revenue_minor
        ),
        "denominator_connected_platform_revenue_minor": (
            coverage_result.denominator_connected_platform_revenue_minor
        ),
        "coverage_percent": str(coverage_result.coverage_percent),
        "zero_denominator": coverage_result.zero_denominator,
        "unverifiable_historical_revenue_minor": (
            coverage.aggregate.unverifiable_historical_revenue_minor
        ),
        "unverifiable_attestation_revenue_minor": (
            coverage.aggregate.unverifiable_attestation_revenue_minor
        ),
        "producer": coverage.producer,
    }
    record = {
        "database": DATABASE,
        "tenant_id": tenant,
        "verdict_id": verdict,
        "observation": observation,
        "source": {
            "status": source.status if source else None,
            "canonical_net_verified_amount_minor": (
                source.canonical_net_verified_amount_minor if source else None
            ),
            "ingress_has_current_authority": (
                source.ingress_has_current_authority if source else None
            ),
        },
        "history_integrity": {
            "ok": history_ok,
            "reason": history_reason,
        },
        "builder_status": result.status,
        "builder_reason": result.reason_code,
        "verified_revenue_minor": payload.get("verified_revenue_minor"),
        "match_verdict_status": payload.get("match_verdict_status"),
        "confidence_status": (payload.get("confidence_metadata") or {}).get(
            "confidence_status"
        ),
        "coverage": coverage_payload,
        "signed_query": {
            "http_status": signed_response.status_code,
            "envelope_count": len(envelopes),
            "verified": str(getattr(signed_verified, "verification_status", signed_verified)),
            "verified_revenue_minor": signed_money,
            "jwks_status": signed_jwks.status_code,
            "body": signed_response.text[:1000],
            "jwks_public_keys": (
                assert_jwks_public_only(signed_jwks.json())
                if signed_jwks.status_code == 200
                else 0
            ),
        },
        "oracle": {
            "source_resolved": source is not None,
            "builder_success": result.status == "success",
            "money_1000": payload.get("verified_revenue_minor") == 1000,
            "signed_verified": signed_envelope is not None
            and str(getattr(signed_verified, "verification_status", signed_verified))
            in {"valid", "verified"},
            "signed_money_1000": signed_money == 1000,
            "coverage_money_1000": coverage_result.numerator_matched_webhook_revenue_minor
            == 1000,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    print(json.dumps(record["oracle"], indent=2))
    return 0 if all(record["oracle"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
