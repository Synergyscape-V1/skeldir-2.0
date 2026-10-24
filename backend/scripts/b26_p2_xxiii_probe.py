#!/usr/bin/env python3
"""B2.6-P2 Corrective XXIII pre/post boundary falsifier probe.

Runs inside the compiled production image. Each command establishes one
physical world, then reports the observed outcome as JSON. The oracle for
each command is fixed before the remediation and is independent of the
implementation path under test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

from app.core.construction_authority import (
    REQUIRED_SCHEMA_REVISION,
    ConstructionAuthorityError,
    assert_production_construction_authority,
)

ADMIN_DSN = os.environ.get("XXIII_ADMIN_DSN", "")
USER_DSN = os.environ.get("XXIII_USER_DSN", "")
WORKER_DSN = os.environ.get("XXIII_WORKER_DSN", "")
INGRESS_DSN = os.environ.get("XXIII_INGRESS_DSN", "")
WITNESS_DIR = Path(os.environ.get("XXIII_WITNESS_DIR", "/tmp/xxiii-witness"))

DAY = datetime.now(timezone.utc)


def _connect(dsn: str):
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    return conn


def _set_tenant(cur, tenant_id: str) -> None:
    cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant_id,))


def _new_tenant(cur) -> str:
    tenant_id = str(uuid.uuid4())
    tag = uuid.uuid4().hex[:10]
    cur.execute(
        "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
        " VALUES (%s, %s, %s, %s)",
        (tenant_id, "xxiii-" + tag, uuid.uuid4().hex, tag + "@x.invalid"),
    )
    return tenant_id


def _insert_ingress(
    cur,
    tenant_id: str,
    tag: str,
    amount: int,
    reference: str,
    *,
    commerce_reference: str | None = None,
    reference_kind: str = "order_reference",
) -> tuple[str, str, str]:
    ingress_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    idem = "xxiii:" + reference
    channel = "xxiii_" + tag[:8]
    cur.execute(
        "INSERT INTO public.channel_taxonomy"
        " (code, family, is_paid, display_name, state)"
        " VALUES (%s, 'xxiii', true, 'XXIII', 'active')"
        " ON CONFLICT (code) DO NOTHING",
        (channel,),
    )
    cur.execute(
        "INSERT INTO public.attribution_events ("
        "id, tenant_id, occurred_at, correlation_id, session_id,"
        " revenue_cents, raw_payload, idempotency_key, event_type, channel,"
        " campaign_id, conversion_value_cents, currency, event_timestamp,"
        " processed_at, processing_status"
        ") VALUES (%s, %s, %s, %s, %s, %s, '{}'::jsonb, %s, 'conversion',"
        " %s, 'c', %s, 'USD', %s, %s, 'processed')",
        (
            event_id,
            tenant_id,
            DAY,
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            amount,
            idem,
            channel,
            amount,
            DAY,
            DAY,
        ),
    )
    commerce = commerce_reference or ("ord-" + tag)
    cur.execute(
        "INSERT INTO public.webhook_ingress_identities ("
        "id, tenant_id, event_id, provider, provider_native_event_reference,"
        " provider_native_commerce_reference, normalized_commerce_reference_kind,"
        " normalized_commerce_reference_value, verified_amount_minor,"
        " verified_amount_currency, event_timestamp, idempotency_key,"
        " verified_commerce_ingress_state"
        ") VALUES (%s, %s, %s, 'stripe', %s, %s, %s, %s,"
        " %s, 'USD', %s, %s, 'authenticity_verified')",
        (
            ingress_id,
            tenant_id,
            event_id,
            reference,
            commerce,
            reference_kind,
            commerce,
            amount,
            DAY,
            idem,
        ),
    )
    cur.execute(
        "ALTER TABLE public.webhook_ingress_identities"
        " DISABLE TRIGGER trg_b26_p2_ingress_provenance"
    )
    cur.execute(
        "UPDATE public.webhook_ingress_identities"
        " SET b26_p2_provenance_status = 'unknown_legacy' WHERE id = %s",
        (ingress_id,),
    )
    cur.execute(
        "ALTER TABLE public.webhook_ingress_identities"
        " ENABLE TRIGGER trg_b26_p2_ingress_provenance"
    )
    return ingress_id, event_id, reference


def _authenticate_ingress(tenant_id: str, ingress_id: str, reference: str) -> str:
    conn = _connect(INGRESS_DSN)
    try:
        cur = conn.cursor()
        _set_tenant(cur, tenant_id)
        cur.execute(
            "SELECT set_config('app.b26_p2_event_family',"
            " 'payment_intent.succeeded', false)"
        )
        cur.execute(
            "SELECT set_config('app.b26_p2_event_family_source',"
            " 'body-signal:type', false)"
        )
        cur.execute(
            "SELECT public.b26_p2_authenticate_ingress_atomic_v2("
            "%s, 'stripe', %s, %s, %s,"
            " 'hmac-sha256-timestamped-hex', 'v1', NULL, NULL, FALSE,"
            " NULL, NULL)",
            (ingress_id, reference, "c" * 64, "d" * 64),
        )
        return str(cur.fetchone()[0])
    finally:
        conn.close()


def _insert_verdict(
    cur,
    tenant_id: str,
    ingress_id: str | None,
    attribution_event_id: str | None,
    tag: str,
    amount: int,
) -> str:
    verdict_id = str(uuid.uuid4())
    reference = "ord-" + tag
    cur.execute(
        "INSERT INTO public.b23_match_verdicts ("
        "id, tenant_id, attribution_event_id, webhook_ingress_identity_id,"
        " provider, canonical_commerce_reference,"
        " provider_native_event_reference, provider_native_commerce_reference,"
        " status, match_quality, attributed_amount_minor,"
        " verified_amount_minor, currency_code,"
        " canonical_expected_gross_amount_minor,"
        " canonical_captured_gross_amount_minor,"
        " canonical_net_verified_amount_minor, discrepancy_amount_minor,"
        " discrepancy_ratio_bps, discrepancy_band"
        ") VALUES (%s, %s, %s, %s, 'stripe', %s, %s, %s, 'matched_confirmed',"
        " 'high', %s, %s, 'USD', %s, %s, %s, 0, 0, 'exact')",
        (
            verdict_id,
            tenant_id,
            attribution_event_id,
            ingress_id,
            reference,
            reference,
            reference,
            amount,
            amount,
            amount,
            amount,
            amount,
        ),
    )
    return verdict_id


def _seed_world(amount: int = 38000) -> dict[str, str]:
    admin = _connect(ADMIN_DSN)
    try:
        cur = admin.cursor()
        tenant_id = _new_tenant(cur)
        _set_tenant(cur, tenant_id)
        tag = uuid.uuid4().hex[:10]
        ingress_id, event_id, reference = _insert_ingress(
            cur, tenant_id, tag, amount, "evt-" + tag
        )
    finally:
        admin.close()
    outcome = _authenticate_ingress(tenant_id, ingress_id, reference)
    admin = _connect(ADMIN_DSN)
    try:
        cur = admin.cursor()
        _set_tenant(cur, tenant_id)
        verdict_id = _insert_verdict(
            cur, tenant_id, ingress_id, event_id, tag, amount
        )
    finally:
        admin.close()
    return {
        "tenant_id": tenant_id,
        "ingress_id": ingress_id,
        "verdict_id": verdict_id,
        "tag": tag,
        "reference": reference,
        "amount": str(amount),
        "ingress_state": outcome,
    }


def _universe() -> str:
    conn = _connect(ADMIN_DSN)
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT public.b26_p2_authority_universe()")
            return str(cur.fetchone()[0])
        except Exception:
            conn.rollback()
            return "pre-fix-universe"
    finally:
        conn.close()


def _live_witness_state() -> dict[str, object]:
    conn = _connect(ADMIN_DSN)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT n, tip_seq, tip_hash"
            " FROM public.b26_p2_read_history_witness_state()"
        )
        count, tip_seq, tip_hash = cur.fetchone()
        cur.execute("SELECT public.b26_p2_read_history_prefix_digest()")
        digest = cur.fetchone()[0]
    finally:
        conn.close()
    return {
        "ledger_count": int(count),
        "ledger_tip_seq": tip_seq,
        "ledger_tip_hash": tip_hash,
        "ledger_prefix_digest": digest,
    }


def _checkpoint_kwargs(journal_path: Path) -> dict[str, object]:
    import inspect

    from app.trust.history_witness import append_checkpoint

    params = inspect.signature(append_checkpoint).parameters
    kwargs: dict[str, object] = {}
    if "authority_universe" in params:
        kwargs["authority_universe"] = _universe()
    if "custody_path" in params:
        kwargs["custody_path"] = journal_path.parent / "custody.json"
    if "heartbeat_path" in params:
        kwargs["heartbeat_path"] = journal_path.parent / "heartbeat.json"
    return kwargs


def _ensure_witness(private_key_path: Path, journal_path: Path) -> dict[str, object]:
    from app.trust.history_witness import (
        append_checkpoint,
        generate_keypair,
        verify_journal,
    )

    WITNESS_DIR.mkdir(parents=True, exist_ok=True)
    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    public_key_path = private_key_path.parent / "witness.pub"
    if not private_key_path.exists():
        private_seed, public_key = generate_keypair()
        private_key_path.write_text(private_seed, encoding="utf-8")
        public_key_path.write_text(public_key, encoding="utf-8")
    if journal_path.exists():
        journal = verify_journal(
            journal_path,
            public_key_path=public_key_path,
            genesis_hash=os.environ.get("B26_P2_HISTORY_WITNESS_GENESIS_HASH") or None,
            require_freshness=False,
        )
        latest = journal.latest
        return {
            "genesis_hash": journal.genesis_hash,
            "count": latest.ledger_count,
            "tip_seq": latest.ledger_tip_seq,
            "tip_hash": latest.ledger_tip_hash,
            "prefix_digest": latest.ledger_prefix_digest,
            "checkpoint_hash": latest.checkpoint_hash,
        }
    live = _live_witness_state()
    checkpoint = append_checkpoint(
        journal_path,
        private_key_path=private_key_path,
        ledger_count=int(live["ledger_count"]),
        ledger_tip_seq=live["ledger_tip_seq"],
        ledger_tip_hash=live["ledger_tip_hash"],
        ledger_prefix_digest=live["ledger_prefix_digest"],
        **_checkpoint_kwargs(journal_path),
    )
    return {
        "genesis_hash": checkpoint.checkpoint_hash,
        "count": checkpoint.ledger_count,
        "tip_seq": checkpoint.ledger_tip_seq,
        "tip_hash": checkpoint.ledger_tip_hash,
        "prefix_digest": checkpoint.ledger_prefix_digest,
        "checkpoint_hash": checkpoint.checkpoint_hash,
    }


def cmd_relay_refusal(_args: argparse.Namespace) -> dict[str, object]:
    import asyncio

    import httpx

    from app.api import webhooks
    from app.ingestion.event_service import ValidationError
    from app.main import app

    tenant_id = uuid.uuid4()
    original_ingest = webhooks.ingest_with_transaction

    async def _stripe_auth_override():
        return {"tenant_id": tenant_id, "verified_at": DAY}

    async def _refused_ingest(**_kwargs):
        raise ValidationError(
            "b26_p2_ingress_relay_refused: status=422"
            " body=b26_p2_lifecycle_not_creation_moment"
        )

    async def _send() -> dict[str, object]:
        payload = {
            "id": "evt_" + uuid.uuid4().hex[:10],
            "type": "payment_intent.succeeded",
            "created": int(DAY.timestamp()),
            "data": {
                "object": {
                    "id": "pi_" + uuid.uuid4().hex[:10],
                    "amount": 1234,
                    "currency": "usd",
                }
            },
        }
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://xxiii",
            ) as client:
                response = await client.post(
                    "/api/webhooks/stripe/payment_intent/succeeded",
                    headers={
                        "Content-Type": "application/json",
                        "X-Idempotency-Key": "xxiii-" + uuid.uuid4().hex,
                    },
                    content=json.dumps(payload).encode("utf-8"),
                )
        except Exception as exc:  # noqa: BLE001 - the uncaught path is the result
            return {
                "http_status": None,
                "exception": f"{type(exc).__name__}:{exc}".splitlines()[0],
                "status": None,
            }
        body = response.json()
        return {
            "http_status": response.status_code,
            "exception": None,
            "status": body.get("status"),
        }

    webhooks.ingest_with_transaction = _refused_ingest
    app.dependency_overrides[webhooks.stripe_webhook_auth] = _stripe_auth_override
    try:
        refused = asyncio.run(_send())
    finally:
        app.dependency_overrides.pop(webhooks.stripe_webhook_auth, None)
        webhooks.ingest_with_transaction = original_ingest

    async def _unreachable_ingest(**_kwargs):
        raise ValidationError("b26_p2_ingress_relay_unreachable:ConnectError")

    webhooks.ingest_with_transaction = _unreachable_ingest
    app.dependency_overrides[webhooks.stripe_webhook_auth] = _stripe_auth_override
    try:
        unreachable = asyncio.run(_send())
    finally:
        app.dependency_overrides.pop(webhooks.stripe_webhook_auth, None)
        webhooks.ingest_with_transaction = original_ingest

    return {
        "refused": refused,
        "unreachable": unreachable,
        "refusal_governed": refused.get("http_status") == 200
        and refused.get("status") == "authority_refused",
        "transport_retryable": unreachable.get("http_status") == 503,
    }


def cmd_inspect(_args: argparse.Namespace) -> dict[str, object]:
    conn = _connect(ADMIN_DSN)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT grantee, privilege_type, column_name"
            " FROM information_schema.column_privileges"
            " WHERE table_name = 'b23_match_verdicts'"
            " AND grantee IN ('app_worker', 'app_user', 'app_rw')"
            " ORDER BY grantee, privilege_type, column_name"
        )
        columns = [
            {"grantee": row[0], "privilege": row[1], "column": row[2]}
            for row in cur.fetchall()
        ]
        cur.execute(
            "SELECT grantee, privilege_type"
            " FROM information_schema.table_privileges"
            " WHERE table_name = 'b23_revenue_events'"
            " AND grantee IN ('app_worker', 'app_user', 'app_rw')"
            " ORDER BY grantee, privilege_type"
        )
        events = [
            {"grantee": row[0], "privilege": row[1]} for row in cur.fetchall()
        ]
    finally:
        conn.close()
    return {"verdict_column_privileges": columns, "event_privileges": events}


def cmd_growth(_args: argparse.Namespace) -> dict[str, object]:
    private_key_path = WITNESS_DIR / "witness.key"
    journal_path = WITNESS_DIR / "journal.jsonl"
    before = _ensure_witness(private_key_path, journal_path)
    world = _seed_world(38000)
    admin = _connect(ADMIN_DSN)
    try:
        cur = admin.cursor()
        _set_tenant(cur, world["tenant_id"])
        correction_ref = "evt-corr-" + uuid.uuid4().hex[:10]
        correction_ingress, _correction_event, _ = _insert_ingress(
            cur,
            world["tenant_id"],
            world["tag"],
            38001,
            correction_ref,
            commerce_reference="corr-" + world["tag"],
            reference_kind="correction_reference",
        )
    finally:
        admin.close()
    correction_state = _authenticate_ingress(
        world["tenant_id"], correction_ingress, correction_ref
    )

    os.environ["CI"] = "true"
    os.environ["DATABASE_URL"] = WORKER_DSN
    os.environ["B23_WORKER_DATABASE_URL"] = WORKER_DSN
    os.environ["B26_P2_HISTORY_WITNESS_PRIVATE_KEY_PATH"] = str(private_key_path)
    os.environ["B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH"] = str(
        WITNESS_DIR / "witness.pub"
    )
    os.environ["B26_P2_HISTORY_WITNESS_JOURNAL_PATH"] = str(journal_path)
    os.environ["B26_P2_HISTORY_WITNESS_GENESIS_HASH"] = str(before["genesis_hash"])
    os.environ["B26_P2_HISTORY_WITNESS_REQUIRED"] = "true"
    os.environ["B26_P2_HISTORY_WITNESS_CUSTODY_PATH"] = str(
        WITNESS_DIR / "custody.json"
    )

    import asyncio
    from uuid import UUID

    from app.db.session import get_b23_session
    from app.revenue_verification import (
        B23PostCaptureInput,
        register_b23_post_capture_event,
    )

    async def _run_correction() -> None:
        async with get_b23_session(UUID(world["tenant_id"])) as session:
            await register_b23_post_capture_event(
                session,
                B23PostCaptureInput(
                    tenant_id=UUID(world["tenant_id"]),
                    provider="stripe",
                    event_type="payment_capture",
                    provider_native_event_reference=correction_ref,
                    provider_native_commerce_reference=world["reference"],
                    currency_code="USD",
                    amount_minor=38001,
                    event_occurred_at=DAY,
                    match_verdict_id=UUID(world["verdict_id"]),
                    is_gross_capture_correction=True,
                ),
            )

    correction_error = None
    try:
        asyncio.run(_run_correction())
    except Exception as exc:  # noqa: BLE001
        correction_error = f"{type(exc).__name__}:{exc}".splitlines()[0]

    from app.tasks.b26_p2_history import observe_history_integrity

    error = None
    observed = None
    try:
        observed = asyncio.run(observe_history_integrity())
    except Exception as exc:  # noqa: BLE001 - the observed refusal is the result
        error = f"{type(exc).__name__}:{exc}".splitlines()[0]

    from app.trust.history_witness import verify_journal

    after = verify_journal(
        journal_path,
        public_key_path=WITNESS_DIR / "witness.pub",
        genesis_hash=str(before["genesis_hash"]),
        require_freshness=False,
    )
    latest = after.latest
    return {
        "world": world,
        "correction_ingress_state": correction_state,
        "correction_error": correction_error,
        "observer_error": error,
        "observer_result": observed,
        "journal_before_count": before["count"],
        "journal_after_count": latest.ledger_count,
        "journal_after_tip_seq": latest.ledger_tip_seq,
        "advance_observed": latest.ledger_count > int(before["count"]),
    }


def cmd_snapshot(_args: argparse.Namespace) -> dict[str, object]:
    import inspect

    base = WITNESS_DIR / "snapshot"
    base.mkdir(parents=True, exist_ok=True)
    private_key_path = base / "witness.key"
    journal_path = base / "journal.jsonl"
    before = _ensure_witness(private_key_path, journal_path)

    world = _seed_world(40000)
    admin = _connect(ADMIN_DSN)
    try:
        cur = admin.cursor()
        _set_tenant(cur, world["tenant_id"])
        correction_ref = "evt-snap-" + uuid.uuid4().hex[:10]
        correction_ingress, _event, _ = _insert_ingress(
            cur,
            world["tenant_id"],
            world["tag"],
            40001,
            correction_ref,
            commerce_reference="snap-" + world["tag"],
            reference_kind="correction_reference",
        )
    finally:
        admin.close()
    _authenticate_ingress(
        world["tenant_id"], correction_ingress, correction_ref
    )

    os.environ["CI"] = "true"
    os.environ["DATABASE_URL"] = WORKER_DSN
    os.environ["B23_WORKER_DATABASE_URL"] = WORKER_DSN
    os.environ["B26_P2_HISTORY_WITNESS_PRIVATE_KEY_PATH"] = str(private_key_path)
    os.environ["B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH"] = str(
        base / "witness.pub"
    )
    os.environ["B26_P2_HISTORY_WITNESS_JOURNAL_PATH"] = str(journal_path)
    os.environ["B26_P2_HISTORY_WITNESS_GENESIS_HASH"] = str(before["genesis_hash"])
    os.environ["B26_P2_HISTORY_WITNESS_REQUIRED"] = "true"
    os.environ["B26_P2_HISTORY_WITNESS_CUSTODY_PATH"] = str(base / "custody.json")

    import asyncio
    from uuid import UUID

    from app.db.session import get_b23_session
    from app.revenue_verification import (
        B23PostCaptureInput,
        register_b23_post_capture_event,
    )

    async def _run_correction() -> None:
        async with get_b23_session(UUID(world["tenant_id"])) as session:
            await register_b23_post_capture_event(
                session,
                B23PostCaptureInput(
                    tenant_id=UUID(world["tenant_id"]),
                    provider="stripe",
                    event_type="payment_capture",
                    provider_native_event_reference=correction_ref,
                    provider_native_commerce_reference=world["reference"],
                    currency_code="USD",
                    amount_minor=40001,
                    event_occurred_at=DAY,
                    match_verdict_id=UUID(world["verdict_id"]),
                    is_gross_capture_correction=True,
                ),
            )

    correction_error = None
    try:
        asyncio.run(_run_correction())
    except Exception as exc:  # noqa: BLE001
        correction_error = f"{type(exc).__name__}:{exc}".splitlines()[0]

    live = _live_witness_state()
    snapshot: dict[str, object] | None = None
    snapshot_error = None
    try:
        conn = _connect(ADMIN_DSN)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT n, tip_seq, tip_hash, prefix_digest, violations,"
                    " authority_universe, prior_tip_hash"
                    " FROM public.b26_p2_read_history_snapshot(%s)",
                    (before["tip_seq"],),
                )
                row = cur.fetchone()
            snapshot = {
                "n": int(row[0]),
                "tip_seq": row[1],
                "tip_hash": row[2],
                "prefix_digest": row[3],
                "violations": row[4],
                "authority_universe": str(row[5]) if row[5] else None,
                "prior_tip_hash": row[6],
            }
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 - surface the missing surface
        snapshot_error = f"{type(exc).__name__}:{exc}".splitlines()[0]

    from app.trust.history_witness import (
        HistoryWitnessError,
        append_checkpoint,
        verify_journal,
    )

    params = inspect.signature(append_checkpoint).parameters
    base_kwargs: dict[str, object] = {}
    if "authority_universe" in params:
        base_kwargs["authority_universe"] = _universe()

    mixed_kwargs: dict[str, object] = {
        "ledger_count": int(live["ledger_count"]),
        "ledger_tip_seq": before["tip_seq"],
        "ledger_tip_hash": before["tip_hash"],
        "ledger_prefix_digest": before["prefix_digest"],
        **base_kwargs,
    }
    if "prefix_anchor_seq" in params:
        mixed_kwargs["prefix_anchor_seq"] = before["tip_seq"]
    if "prefix_anchor_hash" in params:
        mixed_kwargs["prefix_anchor_hash"] = before["tip_hash"]
    mixed_reason = ""
    mixed_accepted = False
    try:
        append_checkpoint(
            journal_path,
            private_key_path=private_key_path,
            **mixed_kwargs,
        )
        mixed_accepted = True
    except HistoryWitnessError as exc:
        mixed_reason = str(exc)
    except Exception as exc:  # noqa: BLE001
        mixed_reason = f"{type(exc).__name__}:{exc}".splitlines()[0]

    lawful_reason = ""
    lawful_accepted = False
    lawful_kwargs: dict[str, object] = {
        "ledger_count": int(live["ledger_count"]),
        "ledger_tip_seq": live["ledger_tip_seq"],
        "ledger_tip_hash": live["ledger_tip_hash"],
        "ledger_prefix_digest": live["ledger_prefix_digest"],
        **base_kwargs,
    }
    if "prefix_anchor_seq" in params:
        lawful_kwargs["prefix_anchor_seq"] = before["tip_seq"]
    if "prefix_anchor_hash" in params:
        lawful_kwargs["prefix_anchor_hash"] = before["tip_hash"]
    try:
        append_checkpoint(
            journal_path,
            private_key_path=private_key_path,
            **lawful_kwargs,
        )
        lawful_accepted = True
    except Exception as exc:  # noqa: BLE001
        lawful_reason = f"{type(exc).__name__}:{exc}".splitlines()[0]

    after = verify_journal(
        journal_path,
        public_key_path=base / "witness.pub",
        genesis_hash=str(before["genesis_hash"]),
        require_freshness=False,
    )
    latest = after.latest
    return {
        "correction_error": correction_error,
        "journal_before_count": before["count"],
        "live_count": live["ledger_count"],
        "snapshot": snapshot,
        "snapshot_error": snapshot_error,
        "snapshot_surface": snapshot is not None,
        "snapshot_matches_live": bool(
            snapshot
            and snapshot["n"] == live["ledger_count"]
            and snapshot["tip_seq"] == live["ledger_tip_seq"]
            and snapshot["tip_hash"] == live["ledger_tip_hash"]
        ),
        "mixed_checkpoint_accepted": mixed_accepted,
        "mixed_checkpoint_reason": mixed_reason,
        "lawful_checkpoint_accepted": lawful_accepted,
        "lawful_checkpoint_reason": lawful_reason,
        "journal_after_count": latest.ledger_count,
        "journal_after_tip_seq": latest.ledger_tip_seq,
    }


def cmd_rollback(_args: argparse.Namespace) -> dict[str, object]:
    import inspect

    base = WITNESS_DIR / "rollback"
    base.mkdir(parents=True, exist_ok=True)
    private_key_path = base / "witness.key"
    public_key_path = base / "witness.pub"
    journal_path = base / "journal.jsonl"
    custody_path = base / "custody.json"

    from app.trust.history_witness import (
        append_checkpoint,
        generate_keypair,
    )

    if not private_key_path.exists():
        private_seed, public_key = generate_keypair()
        private_key_path.write_text(private_seed, encoding="utf-8")
        public_key_path.write_text(public_key, encoding="utf-8")
    for path in (journal_path, custody_path):
        if path.exists():
            path.unlink()

    params = inspect.signature(append_checkpoint).parameters
    supports_custody = "custody_path" in params
    universe = _universe()
    checkpoint_kwargs: dict[str, object] = {}
    if "authority_universe" in params:
        checkpoint_kwargs["authority_universe"] = universe
    if supports_custody:
        checkpoint_kwargs["custody_path"] = custody_path

    empty_digest = hashlib.sha256(b"").hexdigest()
    first = append_checkpoint(
        journal_path,
        private_key_path=private_key_path,
        ledger_count=0,
        ledger_tip_seq=None,
        ledger_tip_hash=None,
        ledger_prefix_digest=empty_digest,
        **checkpoint_kwargs,
    )
    predecessor = journal_path.read_bytes()
    if supports_custody:
        append_checkpoint(
            journal_path,
            private_key_path=private_key_path,
            ledger_count=1,
            ledger_tip_seq=1,
            ledger_tip_hash="e" * 64,
            ledger_prefix_digest="f" * 64,
            prefix_anchor_seq=None,
            prefix_anchor_hash=None,
            **checkpoint_kwargs,
        )
    else:
        append_checkpoint(
            journal_path,
            private_key_path=private_key_path,
            ledger_count=0,
            ledger_tip_seq=None,
            ledger_tip_hash=None,
            ledger_prefix_digest=empty_digest,
            **checkpoint_kwargs,
        )
    custody_after_growth = None
    if custody_path.exists():
        custody_after_growth = json.loads(custody_path.read_text(encoding="utf-8"))

    journal_path.write_bytes(predecessor)

    os.environ["ENVIRONMENT"] = "test"
    os.environ["B26_P2_HISTORY_WITNESS_REQUIRED"] = "true"
    os.environ["B26_P2_HISTORY_WITNESS_PRIVATE_KEY_PATH"] = str(
        private_key_path
    )
    os.environ["B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH"] = str(public_key_path)
    os.environ["B26_P2_HISTORY_WITNESS_JOURNAL_PATH"] = str(journal_path)
    os.environ["B26_P2_HISTORY_WITNESS_GENESIS_HASH"] = first.checkpoint_hash
    os.environ["B26_P2_HISTORY_WITNESS_CUSTODY_PATH"] = str(custody_path)

    from app.trust.builder import _verify_signed_history_witness

    verify_kwargs: dict[str, object] = {
        "ledger_count": 0,
        "ledger_tip_hash": None,
        "ledger_prefix_digest": empty_digest,
    }
    if "authority_universe" in inspect.signature(
        _verify_signed_history_witness
    ).parameters:
        verify_kwargs["authority_universe"] = universe
    accepted, reason = _verify_signed_history_witness(**verify_kwargs)
    return {
        "supports_custody": supports_custody,
        "custody_after_growth": custody_after_growth,
        "rollback_accepted": accepted,
        "rollback_reason": reason,
    }


def cmd_rollback_serviceability(_args: argparse.Namespace) -> dict[str, object]:
    conn = _connect(USER_DSN)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT version_num FROM public.alembic_version")
            revisions = [row[0] for row in cur.fetchall()]
    finally:
        conn.close()
    accepted = False
    reason = ""
    try:
        assert_production_construction_authority(revisions)
        accepted = True
    except ConstructionAuthorityError as exc:
        reason = str(exc)
    return {
        "observed_revisions": revisions,
        "build_required_revision": REQUIRED_SCHEMA_REVISION,
        "service_accepts_rollback_state": accepted,
        "service_refusal_reason": reason,
    }


def cmd_crash_recovery(_args: argparse.Namespace) -> dict[str, object]:
    import inspect

    base = WITNESS_DIR / "crash"
    base.mkdir(parents=True, exist_ok=True)
    private_key_path = base / "witness.key"
    public_key_path = base / "witness.pub"
    journal_path = base / "journal.jsonl"
    custody_path = base / "custody.json"
    for path in (journal_path, custody_path):
        if path.exists():
            path.unlink()

    before = _ensure_witness(private_key_path, journal_path)
    world = _seed_world(38000)
    admin = _connect(ADMIN_DSN)
    try:
        cur = admin.cursor()
        _set_tenant(cur, world["tenant_id"])
        correction_ref = "evt-crash-" + uuid.uuid4().hex[:10]
        correction_ingress, _correction_event, _ = _insert_ingress(
            cur,
            world["tenant_id"],
            world["tag"],
            38001,
            correction_ref,
            commerce_reference="crash-" + world["tag"],
            reference_kind="correction_reference",
        )
    finally:
        admin.close()
    correction_state = _authenticate_ingress(
        world["tenant_id"], correction_ingress, correction_ref
    )

    os.environ["CI"] = "true"
    os.environ["DATABASE_URL"] = WORKER_DSN
    os.environ["B23_WORKER_DATABASE_URL"] = WORKER_DSN
    os.environ["B26_P2_HISTORY_WITNESS_PRIVATE_KEY_PATH"] = str(private_key_path)
    os.environ["B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH"] = str(public_key_path)
    os.environ["B26_P2_HISTORY_WITNESS_JOURNAL_PATH"] = str(journal_path)
    os.environ["B26_P2_HISTORY_WITNESS_GENESIS_HASH"] = str(before["genesis_hash"])
    os.environ["B26_P2_HISTORY_WITNESS_REQUIRED"] = "true"
    os.environ["B26_P2_HISTORY_WITNESS_CUSTODY_PATH"] = str(custody_path)

    import asyncio
    from uuid import UUID

    from app.db.session import get_b23_session
    from app.revenue_verification import (
        B23PostCaptureInput,
        register_b23_post_capture_event,
    )

    async def _run_correction() -> None:
        async with get_b23_session(UUID(world["tenant_id"])) as session:
            await register_b23_post_capture_event(
                session,
                B23PostCaptureInput(
                    tenant_id=UUID(world["tenant_id"]),
                    provider="stripe",
                    event_type="payment_capture",
                    provider_native_event_reference=correction_ref,
                    provider_native_commerce_reference=world["reference"],
                    currency_code="USD",
                    amount_minor=38001,
                    event_occurred_at=DAY,
                    match_verdict_id=UUID(world["verdict_id"]),
                    is_gross_capture_correction=True,
                ),
            )

    correction_error = None
    try:
        asyncio.run(_run_correction())
    except Exception as exc:  # noqa: BLE001
        correction_error = f"{type(exc).__name__}:{exc}".splitlines()[0]

    from app.trust.builder import _verify_signed_history_witness

    verify_params = inspect.signature(_verify_signed_history_witness).parameters
    universe = _universe()

    def _authority() -> tuple[bool, str, dict[str, object]]:
        state = _live_witness_state()
        kwargs: dict[str, object] = {
            "ledger_count": state["ledger_count"],
            "ledger_tip_hash": state["ledger_tip_hash"],
            "ledger_prefix_digest": state["ledger_prefix_digest"],
        }
        if "authority_universe" in verify_params:
            kwargs["authority_universe"] = universe
        accepted, reason = _verify_signed_history_witness(**kwargs)
        return accepted, reason, state

    unwitnessed_accepted, unwitnessed_reason, unwitnessed_state = _authority()

    from app.tasks.b26_p2_history import observe_history_integrity

    recovery_error = None
    recovered = None
    try:
        recovered = asyncio.run(observe_history_integrity())
    except Exception as exc:  # noqa: BLE001 - the observed refusal is the result
        recovery_error = f"{type(exc).__name__}:{exc}".splitlines()[0]

    recovered_accepted, recovered_reason, recovered_state = _authority()
    return {
        "world": world,
        "correction_ingress_state": correction_state,
        "correction_error": correction_error,
        "unwitnessed_authority_accepted": unwitnessed_accepted,
        "unwitnessed_authority_reason": unwitnessed_reason,
        "unwitnessed_state": unwitnessed_state,
        "recovery_error": recovery_error,
        "recovery_result": recovered,
        "recovered_authority_accepted": recovered_accepted,
        "recovered_authority_reason": recovered_reason,
        "recovered_state": recovered_state,
    }


def cmd_worker_authority(_args: argparse.Namespace) -> dict[str, object]:
    world = _seed_world(38000)
    worker = _connect(WORKER_DSN)
    error = None
    try:
        cur = worker.cursor()
        _set_tenant(cur, world["tenant_id"])
        try:
            cur.execute(
                "UPDATE public.b23_match_verdicts SET"
                " attributed_amount_minor = 99999,"
                " verified_amount_minor = 99999,"
                " canonical_expected_gross_amount_minor = 99999,"
                " canonical_captured_gross_amount_minor = 99999,"
                " canonical_net_verified_amount_minor = 99999,"
                " discrepancy_amount_minor = 0,"
                " discrepancy_ratio_bps = 0,"
                " discrepancy_band = 'exact',"
                " last_transition_at = %s,"
                " updated_at = %s"
                " WHERE tenant_id = %s AND id = %s",
                (DAY, DAY, world["tenant_id"], world["verdict_id"]),
            )
        except Exception as exc:  # noqa: BLE001
            worker.rollback()
            error = f"{type(exc).__name__}:{exc}".splitlines()[0]
    finally:
        worker.close()
    admin = _connect(ADMIN_DSN)
    try:
        cur = admin.cursor()
        _set_tenant(cur, world["tenant_id"])
        cur.execute(
            "SELECT verified_amount_minor, attributed_amount_minor"
            " FROM public.b23_match_verdicts WHERE id = %s",
            (world["verdict_id"],),
        )
        row = cur.fetchone()
    finally:
        admin.close()
    return {
        "world": world,
        "update_error": error,
        "amounts_after": {"verified": row[0], "attributed": row[1]},
        "arbitrary_amount_accepted": row[0] == 99999,
    }


def cmd_conservation(_args: argparse.Namespace) -> dict[str, object]:
    admin = _connect(ADMIN_DSN)
    try:
        cur = admin.cursor()
        tenant_id = _new_tenant(cur)
        _set_tenant(cur, tenant_id)
        tag = uuid.uuid4().hex[:10]
        ingress_id, event_id, _reference = _insert_ingress(
            cur, tenant_id, tag, 38000, "evt-" + tag
        )
        verdict_id = _insert_verdict(
            cur, tenant_id, ingress_id, event_id, tag, 99999
        )
        ledger_rows = []
        for prior, new in ((38000, 38001), (38001, 99999)):
            cur.execute(
                "INSERT INTO public.b26_p2_verdict_supersession_ledger ("
                "verdict_id, tenant_id, provider,"
                " provider_native_event_reference,"
                " prior_attributed_amount_minor, new_attributed_amount_minor,"
                " prior_verified_amount_minor, new_verified_amount_minor,"
                " prior_authority_state, new_authority_state,"
                " prior_source_ingress, new_source_ingress"
                ") VALUES (%s, %s, 'stripe', %s, %s, %s, %s, %s,"
                " 'current', 'current', %s, %s) RETURNING id",
                (
                    verdict_id,
                    tenant_id,
                    "ord-" + tag,
                    prior,
                    new,
                    prior,
                    new,
                    ingress_id,
                    ingress_id,
                ),
            )
            ledger_rows.append(str(cur.fetchone()[0]))
    finally:
        admin.close()
    user = _connect(USER_DSN)
    try:
        cur = user.cursor()
        _set_tenant(cur, tenant_id)
        cur.execute(
            "SELECT violation FROM"
            " public.b26_p2_verify_source_money_conservation(%s, %s)",
            (tenant_id, verdict_id),
        )
        violations = [str(row[0]) for row in cur.fetchall()]
    finally:
        user.close()
    return {
        "tenant_id": tenant_id,
        "verdict_id": verdict_id,
        "ledger_rows": ledger_rows,
        "violations": violations,
        "false_world_detected": bool(violations),
    }


def cmd_config(_args: argparse.Namespace) -> dict[str, object]:
    os.environ["CI"] = "true"
    os.environ["DATABASE_URL"] = WORKER_DSN or ADMIN_DSN
    os.environ["ENVIRONMENT"] = "production"
    os.environ["B26_P2_HISTORY_WITNESS_REQUIRED"] = "false"
    os.environ["B26_P2_HISTORY_WITNESS_GENESIS_HASH"] = ""
    error = None
    try:
        from app.core.config import Settings

        Settings()
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}:{exc}".splitlines()[0]
    return {
        "production_accepts_disabled_witness": error is None,
        "validation_error": error,
    }


def cmd_universe(_args: argparse.Namespace) -> dict[str, object]:
    private_key_path = WITNESS_DIR / "universe.key"
    WITNESS_DIR.mkdir(parents=True, exist_ok=True)
    if not private_key_path.exists():
        from app.trust.history_witness import generate_keypair

        seed, public = generate_keypair()
        private_key_path.write_text(seed, encoding="utf-8")
        (WITNESS_DIR / "universe.pub").write_text(public, encoding="utf-8")
    public_key_path = WITNESS_DIR / "universe.pub"
    from app.trust.history_witness import (
        append_checkpoint,
        verify_journal,
    )
    import inspect

    params = inspect.signature(append_checkpoint).parameters
    kwargs: dict[str, object] = {}
    if "authority_universe" in params:
        kwargs["authority_universe"] = _universe()
    journal_path = WITNESS_DIR / "universe.jsonl"
    if journal_path.exists():
        journal_path.unlink()
    checkpoint = append_checkpoint(
        journal_path,
        private_key_path=private_key_path,
        ledger_count=0,
        ledger_tip_seq=None,
        ledger_tip_hash=None,
        ledger_prefix_digest=hashlib.sha256(b"").hexdigest(),
        **kwargs,
    )
    supports_expected = "expected_universe" in inspect.signature(
        verify_journal
    ).parameters
    foreign_rejected = None
    if supports_expected:
        try:
            verify_journal(
                journal_path,
                public_key_path=public_key_path,
                expected_universe="foreign-universe",
                require_freshness=False,
            )
            foreign_rejected = False
        except Exception:
            foreign_rejected = True
    payload_has_universe = False
    try:
        import json as _json

        last = _json.loads(
            journal_path.read_text(encoding="utf-8").splitlines()[-1]
        )
        payload_has_universe = (
            "authority_universe" in last.get("payload", {})
        )
    except Exception:  # noqa: BLE001
        payload_has_universe = False
    return {
        "checkpoint_universe": checkpoint.__dict__.get("authority_universe"),
        "checkpoint_hash": checkpoint.checkpoint_hash,
        "payload_binds_universe": payload_has_universe,
        "verify_accepts_expected_universe": supports_expected,
        "foreign_universe_rejected": foreign_rejected,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=(
            "inspect",
            "growth",
            "worker-authority",
            "conservation",
            "config",
            "universe",
            "snapshot",
            "rollback",
            "rollback-serviceability",
            "crash-recovery",
            "relay-refusal",
        ),
    )
    args = parser.parse_args()
    handler = {
        "inspect": cmd_inspect,
        "growth": cmd_growth,
        "worker-authority": cmd_worker_authority,
        "conservation": cmd_conservation,
        "config": cmd_config,
        "universe": cmd_universe,
        "snapshot": cmd_snapshot,
        "rollback": cmd_rollback,
        "rollback-serviceability": cmd_rollback_serviceability,
        "crash-recovery": cmd_crash_recovery,
        "relay-refusal": cmd_relay_refusal,
    }[args.command]
    result = handler(args)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
