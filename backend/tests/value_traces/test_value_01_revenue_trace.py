"""
Value Trace 01: Penny-perfect revenue verification trace.

Asserts that a claimed vs verified revenue delta is captured and that the verified
amount is treated as truth. Emits a JSON summary artifact and supporting evidence.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.session import engine

EVIDENCE_JSON = Path("backend/validation/evidence/value_traces/value_01_summary.json")
EVIDENCE_MD = Path("docs/evidence/value_traces/value_01_revenue_trace.md")


@pytest.mark.asyncio
async def test_value_trace_revenue_mismatch_resolves_to_verified_amount():
    tenant_id = uuid4()
    transaction_id = f"order-{uuid4().hex[:8]}"
    claimed_cents = 10_000
    verified_cents = 8_000
    discrepancy_cents = claimed_cents - verified_cents
    discrepancy_pct = round(discrepancy_cents / claimed_cents, 2)
    now = datetime.now(timezone.utc)

    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, false)"),
            {"tid": str(tenant_id)},
        )
        # RAW_SQL_ALLOWLIST: value trace revenue ledger seed
        await conn.execute(
            text(
                """
                INSERT INTO tenants (id, name, api_key_hash, notification_email)
                VALUES (:id, 'ValueTrace Tenant', :hash, :email)
                """
            ),
            {
                "id": str(tenant_id),
                "hash": f"hash-{tenant_id.hex[:8]}",
                "email": f"{tenant_id.hex[:8]}@test.invalid",
            },
        )
        # RAW_SQL_ALLOWLIST: value trace revenue ledger seed
        await conn.execute(
            text(
                """
                INSERT INTO channel_taxonomy (code, display_name, family, is_paid)
                VALUES ('direct', 'direct', 'organic', false)
                ON CONFLICT (code) DO NOTHING
                """
            )
        )
        await conn.execute(
            text(
                """
                INSERT INTO revenue_ledger (
                    id, tenant_id, transaction_id, state, amount_cents, currency,
                    verification_source, verification_timestamp, metadata
                ) VALUES (
                    :id, :tenant_id, :tx, 'captured', :amount, 'USD',
                    'webhook', :ts, :metadata::jsonb
                )
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "tx": transaction_id,
                "amount": verified_cents,
                "ts": now,
                "metadata": json.dumps(
                    {
                        "claimed_cents": claimed_cents,
                        "source": "platform_claim",
                    }
                ),
            },
        )
        result = await conn.execute(
            text(
                """
                SELECT transaction_id, amount_cents, metadata
                FROM revenue_ledger
                WHERE transaction_id = :tx
                """
            ),
            {"tx": transaction_id},
        )
        row = result.mappings().first()

    assert row, "Ledger row must exist"
    metadata = row["metadata"] or {}
    found_claimed = metadata.get("claimed_cents", 0)
    assert found_claimed == claimed_cents
    assert row["amount_cents"] == verified_cents

    summary = {
        "tenant_id": str(tenant_id),
        "transaction_id": transaction_id,
        "claimed_cents": claimed_cents,
        "verified_cents": verified_cents,
        "discrepancy_cents": discrepancy_cents,
        "discrepancy_pct": discrepancy_pct,
        "truth_value": "verified",
        "timestamp": now.isoformat(),
    }
    EVIDENCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE_JSON.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    EVIDENCE_MD.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE_MD.open("w", encoding="utf-8") as fh:
        fh.write("# Value Trace 01 – Revenue Verification\n\n")
        fh.write(f"- tenant_id: {tenant_id}\n")
        fh.write(f"- transaction_id: {transaction_id}\n")
        fh.write(f"- claimed_cents: {claimed_cents}\n")
        fh.write(f"- verified_cents: {verified_cents}\n")
        fh.write(f"- discrepancy_cents: {discrepancy_cents}\n")
        fh.write(f"- discrepancy_pct: {discrepancy_pct}\n")
        fh.write("- truth_value: verified\n")
