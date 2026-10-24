"""XXIV (A2/B10): natural correction and scheduled witness progress.

Executes three provider-authenticated gross-capture corrections through
the shipping B2.3 worker task, runs the real history observer after each
cycle, and asserts that the append-only ledger and signed journal both
advance while source-money conservation stays clean.

The operator supplies a disposable database already at the release head
with the P2 ingress topology provisioned. All mutations stay inside that
database and a temporary witness directory.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2


def _admin_dsn(args: argparse.Namespace) -> str:
    dsn = args.admin_dsn or os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get(
        "ADMIN_DATABASE_URL"
    )
    if not dsn:
        raise SystemExit(
            "--admin-dsn or MIGRATION_DATABASE_URL/ADMIN_DATABASE_URL is required"
        )
    return dsn


def _seed_world(admin_dsn: str) -> dict[str, str]:
    tenant = str(uuid.uuid4())
    event = str(uuid.uuid4())
    ingress = str(uuid.uuid4())
    verdict = str(uuid.uuid4())
    tag = uuid.uuid4().hex[:10]
    commerce_ref = "xxiv-natural-" + tag
    event_ref = "evt-capture-" + tag
    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = False
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
            " VALUES (%s,%s,%s,%s)",
            (tenant, "xxiv-natural", uuid.uuid4().hex, "xxiv@example.invalid"),
        )
        cur.execute(
            "INSERT INTO public.channel_taxonomy"
            " (code, family, is_paid, display_name, state)"
            " VALUES (%s,'xxiv',true,'XXIV','active')"
            " ON CONFLICT (code) DO NOTHING",
            ("xxiv_" + tag,),
        )
        cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
        )
        cur.execute(
            "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
            " correlation_id, session_id, revenue_cents, raw_payload,"
            " idempotency_key, event_type, channel, campaign_id,"
            " conversion_value_cents, currency, event_timestamp, processed_at,"
            " processing_status)"
            " VALUES (%s,%s,now(),%s,%s,1000,'{}'::jsonb,%s,'conversion',%s,"
            " 'c',1000,'USD',now(),now(),'processed')",
            (
                event,
                tenant,
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                "xxiv-natural-" + tag,
                "xxiv_" + tag,
            ),
        )
        cur.execute(
            "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
            " event_id, provider, provider_native_event_reference,"
            " provider_native_commerce_reference,"
            " normalized_commerce_reference_kind,"
            " normalized_commerce_reference_value, verified_amount_minor,"
            " verified_amount_currency, event_timestamp, idempotency_key,"
            " verified_commerce_ingress_state)"
            " VALUES (%s,%s,%s,'stripe',%s,%s,'stripe_payment_intent_id',%s,"
            " 1000,'USD',now(),%s,'authenticity_verified')",
            (
                ingress,
                tenant,
                event,
                event_ref,
                commerce_ref,
                commerce_ref,
                str(uuid.uuid4()),
            ),
        )
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
            " %s,'stripe',%s,%s,%s,'hmac-sha256-timestamped-hex','v1',"
            " NULL,NULL,FALSE,NULL,NULL)",
            (ingress, event_ref, "c" * 64, "d" * 64),
        )
        cur.execute(
            "INSERT INTO public.b23_match_verdicts (id, tenant_id,"
            " attribution_event_id, webhook_ingress_identity_id, provider,"
            " canonical_commerce_reference, provider_native_event_reference,"
            " provider_native_commerce_reference, status, match_quality,"
            " attributed_amount_minor, verified_amount_minor, currency_code,"
            " last_transition_at, canonical_expected_gross_amount_minor,"
            " canonical_captured_gross_amount_minor,"
            " canonical_net_verified_amount_minor, discrepancy_amount_minor,"
            " discrepancy_ratio_bps, discrepancy_band)"
            " VALUES (%s,%s,%s,%s,'stripe',%s,%s,%s,'matched_confirmed',"
            " 'high',1000,1000,'USD',now(),1000,1000,1000,0,0,'exact')",
            (
                verdict,
                tenant,
                event,
                ingress,
                commerce_ref,
                event_ref,
                commerce_ref,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "tenant": tenant,
        "verdict": verdict,
        "commerce_ref": commerce_ref,
        "tag": tag,
    }


def _seed_correction(
    admin_dsn: str, world: dict[str, str], *, amount_minor: int, round_index: int
) -> str:
    tenant = world["tenant"]
    event = str(uuid.uuid4())
    ingress = str(uuid.uuid4())
    event_ref = f"evt-corr-{world['tag']}-{round_index}"
    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = False
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
        )
        cur.execute(
            "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
            " correlation_id, session_id, revenue_cents, raw_payload,"
            " idempotency_key, event_type, channel, campaign_id,"
            " conversion_value_cents, currency, event_timestamp, processed_at,"
            " processing_status)"
            " VALUES (%s,%s,now(),%s,%s,%s,'{}'::jsonb,%s,'conversion',%s,"
            " 'c',%s,'USD',now(),now(),'processed')",
            (
                event,
                tenant,
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                amount_minor,
                event_ref,
                "xxiv_" + world["tag"],
                amount_minor,
            ),
        )
        cur.execute(
            "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
            " event_id, provider, provider_native_event_reference,"
            " provider_native_commerce_reference,"
            " normalized_commerce_reference_kind,"
            " normalized_commerce_reference_value, verified_amount_minor,"
            " verified_amount_currency, event_timestamp, idempotency_key,"
            " verified_commerce_ingress_state)"
            " VALUES (%s,%s,%s,'stripe',%s,%s,'correction_reference',%s,%s,"
            " 'USD',now(),%s,'authenticity_verified')",
            (
                ingress,
                tenant,
                event,
                event_ref,
                world["commerce_ref"],
                event_ref,
                amount_minor,
                str(uuid.uuid4()),
            ),
        )
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
            " %s,'stripe',%s,%s,%s,'hmac-sha256-timestamped-hex','v1',"
            " NULL,NULL,FALSE,NULL,NULL)",
            (ingress, event_ref, "c" * 64, "d" * 64),
        )
        conn.commit()
    finally:
        conn.close()
    return event_ref


def _global_ledger_count(admin_dsn: str) -> int:
    conn = psycopg2.connect(admin_dsn)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT count(*) FROM public.b26_p2_verdict_supersession_ledger"
        )
        return int(cur.fetchone()[0])
    finally:
        conn.close()


def _live_snapshot(admin_dsn: str) -> tuple[int, int | None, str | None, str, str | None]:
    conn = psycopg2.connect(admin_dsn)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT n, tip_seq, tip_hash, prefix_digest, authority_universe"
            " FROM public.b26_p2_read_history_snapshot(NULL)"
        )
        row = cur.fetchone()
        return (
            int(row[0]),
            row[1],
            row[2],
            str(row[3]),
            str(row[4]) if row[4] is not None else None,
        )
    finally:
        conn.close()


def _conservation_violations(
    admin_dsn: str, world: dict[str, str]
) -> list[str]:
    conn = psycopg2.connect(admin_dsn)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, false)",
            (world["tenant"],),
        )
        cur.execute(
            "SELECT violation FROM"
            " public.b26_p2_verify_source_money_conservation(%s,%s)",
            (world["tenant"], world["verdict"]),
        )
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def _initialize_witness(
    admin_dsn: str, witness_dir: Path
) -> dict[str, str]:
    from app.trust.history_witness import (  # noqa: PLC0415
        append_checkpoint,
        generate_keypair,
    )

    private_key_path = witness_dir / "witness.key"
    public_key_path = witness_dir / "witness.pub"
    journal_path = witness_dir / "journal.jsonl"
    custody_path = witness_dir / "custody.json"
    heartbeat_path = witness_dir / "heartbeat.json"
    private_seed, public_key = generate_keypair()
    private_key_path.write_text(private_seed, encoding="utf-8")
    public_key_path.write_text(public_key, encoding="utf-8")
    count, tip_seq, tip_hash, digest, universe = _live_snapshot(admin_dsn)
    checkpoint = append_checkpoint(
        journal_path,
        private_key_path=private_key_path,
        ledger_count=count,
        ledger_tip_seq=tip_seq,
        ledger_tip_hash=tip_hash,
        ledger_prefix_digest=digest,
        authority_universe=universe,
        custody_path=custody_path,
        heartbeat_path=heartbeat_path,
    )
    values = {
        "private_key_path": str(private_key_path),
        "public_key_path": str(public_key_path),
        "journal_path": str(journal_path),
        "custody_path": str(custody_path),
        "heartbeat_path": str(heartbeat_path),
        "genesis_hash": checkpoint.checkpoint_hash,
    }
    os.environ["B26_P2_HISTORY_WITNESS_PRIVATE_KEY_PATH"] = values[
        "private_key_path"
    ]
    os.environ["B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH"] = values[
        "public_key_path"
    ]
    os.environ["B26_P2_HISTORY_WITNESS_JOURNAL_PATH"] = values["journal_path"]
    os.environ["B26_P2_HISTORY_WITNESS_CUSTODY_PATH"] = values["custody_path"]
    os.environ["B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH"] = values["heartbeat_path"]
    os.environ["B26_P2_HISTORY_WITNESS_GENESIS_HASH"] = values["genesis_hash"]
    os.environ["B26_P2_HISTORY_WITNESS_REQUIRED"] = "true"
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-dsn", default=None)
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    admin_dsn = _admin_dsn(args)
    if not os.environ.get("DATABASE_URL") or not os.environ.get(
        "B23_WORKER_DATABASE_URL"
    ):
        raise SystemExit(
            "DATABASE_URL and B23_WORKER_DATABASE_URL must name the disposable"
            " worker-capable database"
        )

    world = _seed_world(admin_dsn)
    result: dict[str, Any] = {
        "status": "FAIL",
        "world": world,
        "cycles": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with tempfile.TemporaryDirectory(prefix="xxiv-natural-") as directory:
            witness_dir = Path(directory)
            witness = _initialize_witness(admin_dsn, witness_dir)
            result["witness"] = witness
            from app.tasks.b26_p2_history import (  # noqa: PLC0415
                observe_history_integrity_task,
            )
            from app.tasks.revenue_verification import (  # noqa: PLC0415
                register_b23_post_capture_correction_task,
            )

            amount = 1000
            for round_index in range(1, args.cycles + 1):
                amount += 100
                before_count = _global_ledger_count(admin_dsn)
                event_ref = _seed_correction(
                    admin_dsn,
                    world,
                    amount_minor=amount,
                    round_index=round_index,
                )
                correction = register_b23_post_capture_correction_task.run(
                    tenant_id=world["tenant"],
                    verdict_id=world["verdict"],
                    provider="stripe",
                    event_type="payment_capture",
                    provider_native_event_reference=event_ref,
                    is_gross_capture_correction=True,
                    correlation_id=f"xxiv-natural-{round_index}",
                )
                observation = observe_history_integrity_task.run()
                after_count = _global_ledger_count(admin_dsn)
                violations = _conservation_violations(admin_dsn, world)
                cycle = {
                    "round": round_index,
                    "amount_minor": amount,
                    "correction": correction,
                    "observation": observation,
                    "ledger_before": before_count,
                    "ledger_after": after_count,
                    "ledger_advanced": after_count > before_count,
                    "conservation_violations": violations,
                }
                result["cycles"].append(cycle)
                if correction.get("status") != "applied":
                    raise RuntimeError(f"cycle {round_index}: correction not applied")
                if not cycle["ledger_advanced"]:
                    raise RuntimeError(f"cycle {round_index}: ledger did not advance")
                if violations:
                    raise RuntimeError(
                        f"cycle {round_index}: conservation {violations}"
                    )
                journal_count = int(
                    (observation.get("witness") or {}).get("ledger_count", -1)
                )
                if journal_count != after_count:
                    raise RuntimeError(
                        f"cycle {round_index}: journal {journal_count} != ledger {after_count}"
                    )
        result["status"] = "PASS"
    except Exception as exc:  # noqa: BLE001 - the proof result is the output
        result["error"] = f"{type(exc).__name__}:{exc}".splitlines()[0]
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        print(json.dumps(result, default=str, indent=2, sort_keys=True))
        return 1
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(result, default=str, indent=2, sort_keys=True))
    if args.evidence_out:
        path = Path(args.evidence_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(result, default=str, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
