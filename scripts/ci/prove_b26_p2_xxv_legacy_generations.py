#!/usr/bin/env python3
"""B8: carry data-bearing VII and XX cohorts into the XXV head.

The immediate-predecessor proof covers 202610180003.  B8 additionally requires
the materially distinct, older semantic/schema generations -- the VII head
(202609210001) and the XX head (202609300003) -- to carry real persisted
financial rows through a linear replay and to be readable by the current
source-attestation authority.

The cohort is inserted using the predecessor schema's own public surface.  At
VII that is the app_user-authored verified ingress row (the VII authentication
boundary) followed by the B2.3 verdict row.  At XX the ingress is passed through
the XX atomic authentication transition before the verdict row is written.

The proof deliberately does not treat an unattested pre-XXV row as current
money.  The required post-upgrade result is that the row and its source money
survive, the mandatory sweep classifies the source as not root-authenticated,
and the current reader returns an unverifiable status rather than an attested
one.  Each generation is prepared immediately before its own migration because
role membership is cluster-global and XXV's auth-owner migration revokes the
temporary membership.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
HEAD = "202610280001"
GENERATIONS = (("VII", "202609210001"), ("XX", "202609300003"))
TENANT_DAY = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)


def _dsn(admin: str, database: str) -> str:
    scheme, rest = admin.split("://", 1)
    credentials, _ = rest.rsplit("@", 1)
    host_db = rest.rsplit("@", 1)[1]
    host = host_db.rsplit("/", 1)[0]
    return f"{scheme}://{credentials}@{host}/{database}"


def _run(command: list[str], *, env: dict[str, str], timeout: int = 1800) -> None:
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout[-4000:]}\n"
            f"stderr:\n{completed.stderr[-4000:]}"
        )


def _create_database(admin: str, database: str) -> None:
    conn = psycopg2.connect(admin)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (database,))
            if cur.fetchone():
                cur.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
                    " WHERE datname=%s",
                    (database,),
                )
                cur.execute(f'DROP DATABASE "{database}"')
            cur.execute(f'CREATE DATABASE "{database}"')
    finally:
        conn.close()


def _prepare(admin: str, database: str) -> None:
    _run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "database" / "prepare_migration_authority_boundary.py"),
            "--admin-dsn",
            admin,
            "--database-name",
            database,
        ],
        env=dict(os.environ),
    )


def _alembic_env(migration_dsn: str) -> dict[str, str]:
    env = dict(os.environ)
    env["DATABASE_URL"] = migration_dsn
    env["MIGRATION_DATABASE_URL"] = migration_dsn
    env.setdefault("ENVIRONMENT", "ci")
    env["PYTHONPATH"] = os.pathsep.join(
        [str(BACKEND_ROOT), str(REPO_ROOT), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    return env


def _grant_auth_membership(admin: str) -> None:
    conn = psycopg2.connect(admin)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "GRANT app_auth_lookup TO migration_owner WITH ADMIN OPTION"
            )
    finally:
        conn.close()


def _migrate(
    admin: str, database: str, revision: str, *, provision: bool = True
) -> None:
    # Membership is cluster-global.  A prior head migration can revoke the
    # temporary auth-owner membership, so the predecessor is provisioned
    # immediately before its first replay and the migration principal gets
    # the temporary membership again before the head replay.  Full
    # provisioning is not repeated after a migration because the provisioning
    # principal deliberately cannot read the postgres-owned alembic_version
    # table.
    if provision:
        _prepare(admin, database)
    else:
        _grant_auth_membership(admin)
    _run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        env=_alembic_env(_dsn(admin, database)),
    )


def _seed(admin: str, database: str, generation: str) -> dict[str, str]:
    tenant = uuid.uuid4()
    event = uuid.uuid4()
    ingress = uuid.uuid4()
    verdict = uuid.uuid4()
    reference = f"b8-{generation.lower()}-{uuid.uuid4().hex[:12]}"
    event_reference = f"evt-{reference}"
    commerce_reference = f"ord-{reference}"
    provider_secret = f"whsec_b8_{tenant.hex[:8]}"
    event_created = int(TENANT_DAY.timestamp())
    raw_body = json.dumps(
        {
            "id": event_reference,
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": commerce_reference,
                    "amount": 1000,
                    "currency": "usd",
                    "created": event_created,
                }
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")
    signature_ts = int(time.time())
    signature_header = (
        f"t={signature_ts},v1="
        + hmac.new(
            provider_secret.encode(),
            f"{signature_ts}.".encode() + raw_body,
            hashlib.sha256,
        ).hexdigest()
    )
    body_sha = hashlib.sha256(raw_body).hexdigest()
    signature_sha = hashlib.sha256(
        signature_header.encode("utf-8")
    ).hexdigest()
    # Compatibility law: the predecessor row must use the same commerce
    # meaning the shipping Stripe parser derives from these exact bytes.
    from app.webhooks.commerce_derivation import derive_commerce  # noqa: PLC0415

    derived = derive_commerce("stripe", raw_body)
    normalized_kind = derived.normalized_commerce_reference_kind
    normalized_value = derived.normalized_commerce_reference_value
    if normalized_value != commerce_reference:
        raise RuntimeError(
            "b8_commerce_derivation_mismatch:"
            f"{normalized_value}!={commerce_reference}"
        )

    conn = psycopg2.connect(_dsn(admin, database))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tenants"
                " (id, name, api_key_hash, notification_email)"
                " VALUES (%s, %s, %s, %s)",
                (
                    str(tenant),
                    f"b8-{generation.lower()}-{tenant.hex[:8]}",
                    uuid.uuid4().hex,
                    f"b8-{generation.lower()}-{tenant.hex[:8]}@example.invalid",
                ),
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant),),
            )
            cur.execute(
                "INSERT INTO public.channel_taxonomy"
                " (code, family, is_paid, display_name, state)"
                " VALUES ('b8_legacy', 'b8', true, 'B8 legacy', 'active')"
                " ON CONFLICT (code) DO NOTHING"
            )
            cur.execute(
                "INSERT INTO public.attribution_events"
                " (id, tenant_id, occurred_at, correlation_id, session_id,"
                " revenue_cents, raw_payload, idempotency_key, event_type,"
                " channel, campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, 1000, '{}'::jsonb, %s,"
                " 'conversion', 'b8_legacy', 'b8-campaign', 1000, 'USD',"
                " %s, %s, 'processed')",
                (
                    str(event),
                    str(tenant),
                    TENANT_DAY,
                    str(uuid.uuid4()),
                    str(uuid.uuid4()),
                    f"b8:{generation}:{uuid.uuid4().hex}",
                    TENANT_DAY,
                    TENANT_DAY,
                ),
            )
            cur.execute(
                "INSERT INTO public.webhook_ingress_identities"
                " (id, tenant_id, event_id, provider,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_kind,"
                " normalized_commerce_reference_value,"
                " verified_amount_minor, verified_amount_currency,"
                " event_timestamp, idempotency_key,"
                " verified_commerce_ingress_state)"
                " VALUES (%s, %s, %s, 'stripe', %s, %s, %s,"
                " %s, 1000, 'USD', %s, %s, 'authenticity_verified')",
                (
                    str(ingress),
                    str(tenant),
                    str(event),
                    event_reference,
                    commerce_reference,
                    normalized_kind,
                    normalized_value,
                    TENANT_DAY,
                    f"b8-ingress:{reference}",
                ),
            )
    finally:
        conn.close()

    if generation == "XX":
        # XX's actual authentication surface.  VII has no atomic transition;
        # its app_user-authored verified ingress is the predecessor contract.
        ingress_dsn = _dsn(admin, database).replace(
            "postgres:postgres@", "app_ingress:app_ingress@"
        )
        auth = psycopg2.connect(ingress_dsn)
        auth.autocommit = True
        try:
            with auth.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (str(tenant),),
                )
                cur.execute(
                    "SELECT set_config('app.b26_p2_event_family', %s, false)",
                    ("payment_intent.succeeded",),
                )
                cur.execute(
                    "SELECT set_config('app.b26_p2_event_family_source', %s, false)",
                    ("body-signal:type",),
                )
                cur.execute(
                    "SELECT public.b26_p2_authenticate_ingress_atomic("
                    "%s, %s, %s, %s, %s, 'hmac-sha256', 'v1')",
                    (
                        str(ingress),
                        "stripe",
                        f"evt-{reference}",
                        body_sha,
                        signature_sha,
                    ),
                )
        finally:
            auth.close()

    conn = psycopg2.connect(_dsn(admin, database))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant),),
            )
            cur.execute(
                "INSERT INTO public.b23_match_verdicts"
                " (id, tenant_id, attribution_event_id,"
                " webhook_ingress_identity_id, provider,"
                " canonical_commerce_reference,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference, status, match_quality,"
                " attributed_amount_minor, verified_amount_minor,"
                " currency_code, canonical_expected_gross_amount_minor,"
                " canonical_captured_gross_amount_minor,"
                " canonical_net_verified_amount_minor,"
                " discrepancy_amount_minor, discrepancy_ratio_bps,"
                " discrepancy_band)"
                " VALUES (%s, %s, %s, %s, 'stripe', %s, %s, %s,"
                " 'matched_confirmed', 'high', 1000, 1000, 'USD',"
                " 1000, 1000, 1000, 0, 0, 'exact')",
                (
                    str(verdict),
                    str(tenant),
                    str(event),
                    str(ingress),
                    commerce_reference,
                    event_reference,
                    commerce_reference,
                ),
            )
            cur.execute(
                "INSERT INTO public.b23_revenue_events"
                " (tenant_id, match_verdict_id, provider,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " canonical_commerce_reference, event_type, currency_code,"
                " event_occurred_at, captured_amount_minor, net_effect_sign,"
                " is_gross_capture_correction)"
                " VALUES (%s, %s, 'stripe', %s, %s, %s, 'payment_capture',"
                " 'USD', %s, 1000, 1, false)",
                (
                    str(tenant),
                    str(verdict),
                    event_reference,
                    commerce_reference,
                    commerce_reference,
                    TENANT_DAY,
                ),
            )
    finally:
        conn.close()
    return {
        "tenant_id": str(tenant),
        "event_id": str(event),
        "ingress_id": str(ingress),
        "verdict_id": str(verdict),
        "reference": reference,
        "provider_secret": provider_secret,
        "provider_input": {
            "provider": "stripe",
            "body": raw_body.decode("utf-8"),
            "signature_header": signature_header,
            "body_sha256": body_sha,
            "signature_sha256": signature_sha,
            "event_reference": event_reference,
            "commerce_reference": commerce_reference,
            "normalized_kind": normalized_kind,
            "normalized_value": normalized_value,
            "amount_minor": 1000,
            "currency": "USD",
        },
    }


def _snapshot(admin: str, database: str) -> dict[str, object]:
    conn = psycopg2.connect(_dsn(admin, database))
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.columns"
                " WHERE table_schema='public'"
                "   AND table_name='b23_match_verdicts'"
                "   AND column_name='b26_p2_source_authority_state'"
            )
            state_expr = (
                "v.b26_p2_source_authority_state::text"
                if cur.fetchone()
                else "NULL::text"
            )
            cur.execute(
                "SELECT v.id::text, v.tenant_id::text,"
                " v.webhook_ingress_identity_id::text,"
                " v.status, v.verified_amount_minor, v.currency_code,"
                f" {state_expr}"
                " FROM public.b23_match_verdicts AS v"
            )
            verdict = cur.fetchone()
            cur.execute(
                "SELECT i.id::text, i.provider, i.verified_amount_minor,"
                " i.verified_amount_currency,"
                " i.verified_commerce_ingress_state::text"
                " FROM public.webhook_ingress_identities AS i"
            )
            ingress = cur.fetchone()
            cur.execute(
                "SELECT to_regclass('public.b26_p2_source_money_attestation')"
            )
            attestations = 0
            if cur.fetchone()[0] is not None:
                cur.execute(
                    "SELECT count(*) FROM public.b26_p2_source_money_attestation"
                )
                attestations = int(cur.fetchone()[0])
            return {
                "verdict": verdict,
                "ingress": ingress,
                "attestation_count": attestations,
            }
    finally:
        conn.close()


def _read_status(database: str, tenant: str, verdict: str) -> dict[str, object]:
    from sqlalchemy import text as sql_text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from app.revenue_verification.source_attestation import (
        read_verdict_source_attestation_status,
    )

    async def read() -> dict[str, object]:
        engine = create_async_engine(
            "postgresql+asyncpg://app_user:app_user@"
            + _host_port(database)
            + "/"
            + database
        )
        try:
            async with AsyncSession(engine) as session:
                await session.execute(
                    sql_text(
                        "SELECT set_config('app.current_tenant_id', :tenant, false)"
                    ),
                    {"tenant": tenant},
                )
                status = await read_verdict_source_attestation_status(
                    session, tenant_id=tenant, verdict_id=verdict
                )
                return {
                    "status": status.status,
                    "reason": status.reason,
                    "attested": status.status == "xxv_attested",
                    "attested_amount_minor": status.attested_amount_minor,
                }
        finally:
            await engine.dispose()

    return asyncio.run(read())


def _project_confidence(database: str, tenant: str) -> dict[str, object]:
    from datetime import timedelta

    from sqlalchemy import text as sql_text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from app.bayesian.api_projection import project_b24_confidence

    async def read() -> list:
        engine = create_async_engine(
            "postgresql+asyncpg://app_user:app_user@"
            + _host_port(database)
            + "/"
            + database
        )
        try:
            async with AsyncSession(engine) as session:
                await session.execute(
                    sql_text(
                        "SELECT set_config('app.current_tenant_id', :tenant, false)"
                    ),
                    {"tenant": tenant},
                )
                return await project_b24_confidence(
                    session,
                    tenant_id=uuid.UUID(tenant),
                    source_window_start=TENANT_DAY,
                    source_window_end=TENANT_DAY + timedelta(days=1),
                    source_snapshot_hash="b8-legacy-projection-probe",
                )
        finally:
            await engine.dispose()

    projections = asyncio.run(read())
    return {
        "count": len(projections),
        "deterministic_revenue_minor": [
            item.deterministic.deterministic_revenue_minor
            for item in projections
        ],
    }


def _host_port(database: str) -> str:
    admin = os.environ["B8_ADMIN_DSN"]
    rest = admin.split("://", 1)[1].rsplit("@", 1)[1]
    return rest.rsplit("/", 1)[0]


def _sweep(database: str, public_key_path: str) -> dict[str, object]:
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))
    from b26_p2_xxv_attestation_sweep import sweep

    return sweep(
        _dsn(os.environ["B8_ADMIN_DSN"], database),
        public_key_path=public_key_path,
    )


def _replay_recovery(
    admin: str, database: str, generation: str, world: dict[str, str]
) -> dict[str, object]:
    """Replay the retained provider bytes to re-attest the inherited ingress.

    The inherited ingress is retained with its pre-XXV demotion flag. A genuine
    provider replay presents the exact verified bytes again; the source writer
    signs the existing ingress statement and the journal makes it current. No
    demotion flag is cleared and no new ingress/verdict is manufactured.
    """

    import asyncio  # noqa: PLC0415

    from sqlalchemy import text as sql_text  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: PLC0415

    from app.core.config import settings  # noqa: PLC0415
    from app.revenue_verification.source_attestation import (  # noqa: PLC0415
        build_statement,
        generate_keypair,
        write_source_attestation,
    )
    from app.webhooks.signatures import verify_stripe_signature  # noqa: PLC0415

    provider_input = world["provider_input"]
    body = provider_input["body"].encode("utf-8")
    signature_ok = verify_stripe_signature(
        body, world["provider_secret"], provider_input["signature_header"]
    )
    tenant = world["tenant_id"]
    ingress_id = world["ingress_id"]
    verdict_id = world["verdict_id"]
    key_dir = Path(tempfile.mkdtemp(prefix="b8-replay-"))
    private_seed, public_b64 = generate_keypair()
    private_path = key_dir / "source.key"
    public_path = key_dir / "source.pub"
    journal_path = key_dir / "source.jsonl"
    private_path.write_text(private_seed, encoding="utf-8")
    public_path.write_text(public_b64, encoding="utf-8")
    settings.B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH = str(public_path)
    settings.B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH = str(journal_path)
    settings.B26_P2_SOURCE_ATTESTATION_REQUIRED = True
    os.environ["B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH"] = str(public_path)
    os.environ["B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH"] = str(journal_path)
    os.environ["B8_PUBLIC_KEY_PATH"] = str(public_path)

    # VII has no provider-auth consequence in its predecessor schema. The
    # real retained bytes are replayed through the atomic surface to create
    # that missing binding; XX already has one and must not be replayed twice.
    body_binding_created = False
    ingress_dsn = _dsn(admin, database).replace(
        "postgres:postgres@", "app_ingress:app_ingress@"
    )
    auth = psycopg2.connect(ingress_dsn)
    auth.autocommit = True
    try:
        with auth.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            cur.execute(
                "SELECT count(*) FROM public.b26_p2_provider_auth_consequence"
                " WHERE webhook_ingress_identity_id=%s",
                (ingress_id,),
            )
            has_consequence = int(cur.fetchone()[0]) > 0
            if not has_consequence:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,),
                )
                cur.execute(
                    "SELECT set_config('app.b26_p2_event_family', %s, false)",
                    ("payment_intent.succeeded",),
                )
                cur.execute(
                    "SELECT set_config('app.b26_p2_event_family_source', %s, false)",
                    ("body-signal:type",),
                )
                cur.execute(
                    "SELECT public.b26_p2_authenticate_ingress_atomic_v2("
                    "%s, %s, %s, %s, %s, 'hmac-sha256', 'v1',"
                    " NULL, NULL, false, NULL, NULL)",
                    (
                        ingress_id,
                        "stripe",
                        provider_input["event_reference"],
                        provider_input["body_sha256"],
                        provider_input["signature_sha256"],
                    ),
                )
                body_binding_created = True
    finally:
        auth.close()

    async def sign_source() -> None:
        engine = create_async_engine(
            "postgresql+asyncpg://app_ingress:app_ingress@"
            + _host_port(database)
            + "/"
            + database
        )
        try:
            async with AsyncSession(engine) as session:
                await session.execute(
                    sql_text(
                        "SELECT set_config('app.current_tenant_id', :t, false)"
                    ),
                    {"t": tenant},
                )
                universe = (
                    await session.execute(
                        sql_text("SELECT public.b26_p2_authority_universe()::text")
                    )
                ).scalar_one()
                statement = build_statement(
                    tenant_id=tenant,
                    webhook_ingress_identity_id=ingress_id,
                    provider="stripe",
                    provider_native_event_reference=provider_input[
                        "event_reference"
                    ],
                    provider_native_commerce_reference=provider_input[
                        "commerce_reference"
                    ],
                    normalized_commerce_reference_kind=provider_input[
                        "normalized_kind"
                    ],
                    normalized_commerce_reference_value=provider_input[
                        "normalized_value"
                    ],
                    verified_amount_minor=1000,
                    verified_amount_currency="USD",
                    verified_amount_scale=2,
                    event_timestamp=TENANT_DAY,
                    body_sha256=provider_input["body_sha256"],
                    authority_universe=universe,
                )
                await write_source_attestation(
                    session,
                    statement=statement,
                    private_key_path=private_path,
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(sign_source())
    # Auth-root-only governed lift after the signed source statement exists.
    lift = psycopg2.connect(ingress_dsn)
    lift.autocommit = True
    try:
        with lift.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            cur.execute(
                "SELECT public.b26_p2_lift_pre_xxv_demotion(%s, %s)",
                (tenant, ingress_id),
            )
            demotion_lifted = bool(cur.fetchone()[0])
    finally:
        lift.close()
    reader = _read_status(database, tenant, verdict_id)
    conn = psycopg2.connect(_dsn(admin, database))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT b26_p2_demotion_reason,"
                " b26_p2_source_authority_state::text"
                " FROM public.webhook_ingress_identities i"
                " JOIN public.b23_match_verdicts v"
                "   ON v.webhook_ingress_identity_id=i.id"
                " WHERE i.tenant_id=%s AND v.id=%s",
                (tenant, verdict_id),
            )
            demotion, authority = cur.fetchone()
    finally:
        conn.close()
    return {
        "generation": generation,
        "provider_signature_verified": signature_ok,
        "body_binding_created": body_binding_created,
        "demotion_lifted": demotion_lifted,
        "inherited_ingress_id": ingress_id,
        "verdict_id": verdict_id,
        "demotion_reason_preserved": demotion,
        "verdict_authority_state": authority,
        "reader": reader,
        "source_journal": str(journal_path),
        "source_public_key": str(public_path),
        "passed": signature_ok and reader["status"] == "xxv_attested",
        "limit_of_inference": (
            "The provider bytes are real and the source statement is signed for"
            " the existing inherited ingress. A pre-XXV demotion, when"
            " present, is lifted only by the auth-root governed function"
            " after the signed source statement exists; no owner or runtime"
            " principal can clear it. The source reader is attested; Trust"
            " and coverage are exercised separately on the same DB, tenant"
            " and window."
        ),
    }


def _verify_generation(
    admin: str, database: str, generation: str, world: dict[str, str]
) -> dict[str, object]:
    before = _snapshot(admin, database)
    _migrate(admin, database, HEAD, provision=False)
    after = _snapshot(admin, database)
    reader = _read_status(database, world["tenant_id"], world["verdict_id"])
    projection = _project_confidence(database, world["tenant_id"])
    sweep_result = _sweep(database, os.environ["B8_PUBLIC_KEY_PATH"])
    provider_input = world["provider_input"]
    from app.webhooks.commerce_derivation import derive_commerce  # noqa: PLC0415
    from app.webhooks.signatures import verify_stripe_signature  # noqa: PLC0415

    provider_body = provider_input["body"].encode("utf-8")
    signed_input_replayable = verify_stripe_signature(
        provider_body,
        world["provider_secret"],
        provider_input["signature_header"],
    )
    derived = derive_commerce("stripe", provider_body)
    checks = {
        "signed_input_replayable": (
            signed_input_replayable
            and int(derived.verified_amount_minor) == 1000
            and derived.verified_amount_currency.upper() == "USD"
        ),
        "row_preserved": (
            after["verdict"] is not None
            and after["verdict"][0] == world["verdict_id"]
            and after["verdict"][2] == world["ingress_id"]
        ),
        "ingress_preserved": (
            after["ingress"] is not None
            and after["ingress"][0] == world["ingress_id"]
            and int(after["ingress"][2]) == 1000
        ),
        "no_new_attestation": after["attestation_count"] == 0,
        "sweep_pass": not sweep_result["unverifiable"],
        "classified_unqualified": (
            int(
                sweep_result["census"].get(
                    "source_not_root_authenticated", 0
                )
            )
            + int(
                sweep_result["census"].get(
                    "unattested_not_claimed_current", 0
                )
            )
            >= 1
        ),
        "reader_unverifiable": (
            reader["status"].startswith("unverifiable:")
            and reader["attested"] is False
        ),
        "not_current_money": after["verdict"][6]
        not in {"current", "xxv_attested"},
        "confidence_projection_absent": projection["count"] == 0,
    }
    recovery = _replay_recovery(admin, database, generation, world)
    return {
        "generation": generation,
        "recovery": recovery,
        "provider_input": {
            key: value
            for key, value in provider_input.items()
            if key != "provider_secret"
        },
        "before": before,
        "after": after,
        "reader": reader,
        "confidence_projection": projection,
        "sweep": {
            "status": "PASS" if not sweep_result["unverifiable"] else "FAIL",
            "census": sweep_result["census"],
            "unverifiable": sweep_result["unverifiable"],
        },
        "checks": checks,
        "passed": all(checks.values()) and bool(recovery["passed"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-dsn", required=True)
    parser.add_argument("--public-key-path", required=True)
    parser.add_argument("--database-prefix", default="xxv_b8_legacy")
    parser.add_argument("--evidence-out", required=True)
    args = parser.parse_args()

    os.environ["B8_ADMIN_DSN"] = args.admin_dsn
    os.environ["B8_PUBLIC_KEY_PATH"] = args.public_key_path
    os.environ.setdefault("ENVIRONMENT", "ci")
    os.environ["B26_P2_SOURCE_ATTESTATION_REQUIRED"] = "true"
    os.environ["B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH"] = (
        args.public_key_path
    )
    os.environ["DATABASE_URL"] = (
        "postgresql+asyncpg://app_user:app_user@"
        + _host_port("")
        + "/postgres"
    )
    os.environ["MIGRATION_DATABASE_URL"] = args.admin_dsn

    results = []
    for label, revision in GENERATIONS:
        database = f"{args.database_prefix}_{label.lower()}"
        _create_database(args.admin_dsn, database)
        _migrate(args.admin_dsn, database, revision)
        world = _seed(args.admin_dsn, database, label)
        result = _verify_generation(
            args.admin_dsn, database, label, world
        )
        results.append(result)

    record = {
        "gate_id": "B26-P2-XXV-B8-LEGACY-GENERATIONS",
        "status": "PASS" if all(item["passed"] for item in results) else "FAIL",
        "head_revision": HEAD,
        "generations": results,
        "limitation": (
            "The predecessor cohorts are persisted legacy-schema rows;"
            " VII has no atomic transition and XX's transition is used only"
            " to authenticate the ingress. Provider inputs are genuine signed"
            " Stripe bytes retained in this evidence and XX digests are real."
            " The proof still demonstrates preservation/refusal, not a provider"
            " replay into a new current lineage; that remains open."
        ),
    }
    out = Path(args.evidence_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    print(record["status"])
    print(json.dumps(record, default=str)[:4000])
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
