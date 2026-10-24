"""XXIV (B4): persisted scope cohort through the canonical consumer.

Seeds a real database cohort whose current authenticated ingress totals
80,000 minor units and whose matched P2 verdicts total 76,000, then
resolves coverage through the downstream canonical consumer. The expected
governed witness is exactly 95.00 percent with the 4,000 unresolved leg
visible as a denominator/numerator difference. EUR must refuse.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
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


def _seed(admin_dsn: str) -> dict[str, Any]:
    tenant = str(uuid.uuid4())
    tag = uuid.uuid4().hex[:10]
    day = datetime(2026, 10, 23, tzinfo=timezone.utc)
    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = False
    verdicts: list[str] = []
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
            " VALUES (%s,%s,%s,%s)",
            (tenant, "xxiv-cohort", uuid.uuid4().hex, "xxiv@example.invalid"),
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
        for index in range(8):
            event = str(uuid.uuid4())
            ingress = str(uuid.uuid4())
            verdict = str(uuid.uuid4())
            event_ref = f"evt-cohort-{tag}-{index}"
            commerce_ref = f"cohort-{tag}-{index}"
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
                " correlation_id, session_id, revenue_cents, raw_payload,"
                " idempotency_key, event_type, channel, campaign_id,"
                " conversion_value_cents, currency, event_timestamp, processed_at,"
                " processing_status)"
                " VALUES (%s,%s,%s,%s,%s,10000,'{}'::jsonb,%s,'conversion',%s,"
                " 'c',10000,'USD',%s,now(),'processed')",
                (
                    event,
                    tenant,
                    day,
                    str(uuid.uuid4()),
                    str(uuid.uuid4()),
                    event_ref,
                    "xxiv_" + tag,
                    day,
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
                " 10000,'USD',%s,%s,'authenticity_verified')",
                (
                    ingress,
                    tenant,
                    event,
                    event_ref,
                    commerce_ref,
                    commerce_ref,
                    day,
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
            net = 6000 if index == 7 else 10000
            cur.execute(
                "INSERT INTO public.b23_match_verdicts (id, tenant_id,"
                " attribution_event_id, webhook_ingress_identity_id, provider,"
                " canonical_commerce_reference, provider_native_event_reference,"
                " provider_native_commerce_reference, status, match_quality,"
                " attributed_amount_minor, verified_amount_minor, currency_code,"
                " last_transition_at, created_at, updated_at,"
                " canonical_expected_gross_amount_minor,"
                " canonical_captured_gross_amount_minor,"
                " canonical_net_verified_amount_minor, discrepancy_amount_minor,"
                " discrepancy_ratio_bps, discrepancy_band)"
                " VALUES (%s,%s,%s,%s,'stripe',%s,%s,%s,'matched_confirmed',"
                " 'high',10000,10000,'USD',%s,%s,%s,10000,10000,%s,0,0,'exact')",
                (
                    verdict,
                    tenant,
                    event,
                    ingress,
                    commerce_ref,
                    event_ref,
                    commerce_ref,
                    day,
                    day,
                    day,
                    net,
                ),
            )
            verdicts.append(verdict)
        conn.commit()
    finally:
        conn.close()
    return {
        "tenant": tenant,
        "verdicts": verdicts,
        "window_start": day.isoformat(),
        "window_end": (day.replace(hour=23, minute=59, second=59)).isoformat(),
        "denominator_minor": 80000,
        "numerator_minor": 76000,
    }


def _resolve(world: dict[str, Any]) -> dict[str, Any]:
    from app.db.session import get_session
    from app.finance_reconciliation.coverage_authority import (
        resolve_canonical_coverage,
    )

    async def _run() -> dict[str, Any]:
        tenant = uuid.UUID(world["tenant"])
        start = datetime.fromisoformat(world["window_start"])
        end = datetime.fromisoformat(world["window_end"])
        async with get_session(tenant) as session:
            coverage = await resolve_canonical_coverage(
                session,
                tenant_id=tenant,
                window_start=start,
                window_end=end,
            )
        result = {
            "numerator_minor": int(
                coverage.aggregate.matched_webhook_revenue_minor
            ),
            "denominator_minor": int(
                coverage.aggregate.connected_platform_revenue_minor
            ),
            "unverifiable_historical_revenue_minor": int(
                coverage.aggregate.unverifiable_historical_revenue_minor
            ),
            "coverage_percent": str(coverage.result.coverage_percent),
            "zero_denominator": bool(coverage.result.zero_denominator),
            "supported_platforms": list(coverage.supported_platforms),
        }
        async with get_session(tenant) as session:
            try:
                await resolve_canonical_coverage(
                    session,
                    tenant_id=tenant,
                    window_start=start,
                    window_end=end,
                    currency_code="EUR",
                )
            except Exception as exc:  # noqa: BLE001 - refusal is the result
                result["eur_refusal"] = f"{type(exc).__name__}:{exc}"
            else:
                result["eur_refusal"] = None
        return result

    return asyncio.run(_run())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("DATABASE_URL is required")
    admin_dsn = _admin_dsn(args)
    world = _seed(admin_dsn)
    result: dict[str, Any] = {"status": "FAIL", "world": world}
    try:
        observed = _resolve(world)
        result["observed"] = observed
        if observed["denominator_minor"] != 80000:
            raise RuntimeError(
                f"denominator {observed['denominator_minor']} != 80000"
            )
        if observed["numerator_minor"] != 76000:
            raise RuntimeError(
                f"numerator {observed['numerator_minor']} != 76000"
            )
        if observed["coverage_percent"] != "95.00":
            raise RuntimeError(
                f"coverage {observed['coverage_percent']} != 95.00"
            )
        if observed["eur_refusal"] is None:
            raise RuntimeError("EUR did not refuse")
        result["status"] = "PASS"
    except Exception as exc:  # noqa: BLE001 - the proof result is the output
        result["error"] = f"{type(exc).__name__}:{exc}".splitlines()[0]
        print(json.dumps(result, default=str, indent=2, sort_keys=True))
        return 1
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
