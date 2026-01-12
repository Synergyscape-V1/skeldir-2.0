"""
Value Trace 01-WIN: Ghost Revenue Reconciliation (Forensic Load)

This test proves deterministic conflict resolution under adversarial conditions:
- Meta claims $500 for order X
- Google claims $500 for order X (double-counting)
- Verified truth is $500 (Shopify webhook)

Expected outcome:
- claimed_total_cents = 100000 (both platforms claim full amount)
- verified_total_cents = 50000 (actual truth)
- ghost_revenue_cents = 50000 (over-claim)
- discrepancy_bps = 10000 (100% discrepancy)

This proves:
1. Verified truth wins (Shopify webhook is source of truth)
2. Ghost revenue is detected (platforms over-claim)
3. Penny-perfect calculations (no float errors)
4. Idempotent reconciliation (running twice yields same result)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from backend.tests.builders.core_builders import build_attribution_allocation, build_tenant
from app.core.money import MoneyCents, BasisPoints, to_cents
from app.db.session import engine
from app.services.revenue_reconciliation import (
    PlatformClaim,
    RevenueReconciliationService,
    VerifiedRevenue,
)

EVIDENCE_JSON = Path("backend/validation/evidence/value_traces/value_01_summary.json")
EVIDENCE_MD = Path("docs/forensics/evidence/value_traces/value_01_revenue_trace.md")


@pytest.mark.asyncio
async def test_value_trace_ghost_revenue_reconciliation():
    """
    VALUE_01-WIN: Prove ghost revenue detection under adversarial double-counting.

    Scenario:
    - Meta claims $500 for order X (last-click attribution)
    - Google claims $500 for order X (view-through attribution)
    - Shopify webhook confirms $500 actual revenue

    Expected:
    - claimed_total_cents = 100000 (both claim full amount)
    - verified_total_cents = 50000 (actual)
    - ghost_revenue_cents = 50000 (100% over-claim)
    - discrepancy_bps = 10000 (100%)
    """
    # Setup: Create tenant and order
    tenant_record = await build_tenant(name="ValueTrace Ghost Revenue Tenant")
    tenant_id = tenant_record["tenant_id"]
    allocation_record = await build_attribution_allocation(tenant_id=tenant_id)
    allocation_id = allocation_record["id"]

    order_id = f"order-{uuid4().hex[:8]}"
    transaction_id = f"txn-{uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    # Adversarial scenario: Both platforms claim full amount
    meta_claim = PlatformClaim(
        source="meta",
        amount_cents=to_cents("500.00"),  # $500 claim
        claim_timestamp=now,
        claim_id=f"meta-{uuid4().hex[:8]}",
    )

    google_claim = PlatformClaim(
        source="google",
        amount_cents=to_cents("500.00"),  # $500 claim (duplicate!)
        claim_timestamp=now,
        claim_id=f"google-{uuid4().hex[:8]}",
    )

    # Verified truth: Only $500 actually happened
    verified = VerifiedRevenue(
        source="shopify",
        amount_cents=to_cents("500.00"),  # $500 actual
        verification_timestamp=now,
        transaction_id=transaction_id,
    )

    # Run reconciliation
    service = RevenueReconciliationService()

    async with engine.begin() as conn:
        # Set tenant context for RLS
        await conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, false)"),
            {"tid": str(tenant_id)},
        )

        result = await service.reconcile_order(
            conn=conn,
            tenant_id=tenant_id,
            order_id=order_id,
            platform_claims=[meta_claim, google_claim],
            verified_revenue=verified,
        )

    # Assertions: Prove ghost revenue detection
    assert result.claimed_total_cents == 100000, \
        f"Expected claimed_total_cents=100000 (Meta $500 + Google $500), got {result.claimed_total_cents}"

    assert result.verified_total_cents == 50000, \
        f"Expected verified_total_cents=50000 (actual $500), got {result.verified_total_cents}"

    assert result.ghost_revenue_cents == 50000, \
        f"Expected ghost_revenue_cents=50000 (100% over-claim), got {result.ghost_revenue_cents}"

    assert result.discrepancy_bps == 10000, \
        f"Expected discrepancy_bps=10000 (100%), got {result.discrepancy_bps}"

    # Verify idempotency: Running again should yield same result
    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, false)"),
            {"tid": str(tenant_id)},
        )

        result2 = await service.reconcile_order(
            conn=conn,
            tenant_id=tenant_id,
            order_id=order_id,
            platform_claims=[meta_claim, google_claim],
            verified_revenue=verified,
        )

    assert result2.ghost_revenue_cents == result.ghost_revenue_cents, \
        "Idempotency violated: second run produced different result"

    # Query ledger to verify persistence
    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, false)"),
            {"tid": str(tenant_id)},
        )

        ledger_result = await conn.execute(
            text("""
                SELECT
                    order_id, transaction_id, amount_cents,
                    claimed_total_cents, verified_total_cents,
                    ghost_revenue_cents, discrepancy_bps,
                    verification_source
                FROM revenue_ledger
                WHERE tenant_id = :tenant_id AND order_id = :order_id
            """),
            {"tenant_id": str(tenant_id), "order_id": order_id},
        )
        row = ledger_result.mappings().first()

    assert row is not None, "Ledger row must exist"
    assert row["claimed_total_cents"] == 100000
    assert row["verified_total_cents"] == 50000
    assert row["ghost_revenue_cents"] == 50000
    assert row["discrepancy_bps"] == 10000
    assert row["verification_source"] == "shopify"

    # Build SQL proof query for evidence
    sql_proof = f"""
    SELECT
        order_id,
        claimed_total_cents,
        verified_total_cents,
        ghost_revenue_cents,
        discrepancy_bps,
        verification_source
    FROM revenue_ledger
    WHERE tenant_id = '{tenant_id}'
      AND order_id = '{order_id}';

    -- Result:
    -- order_id: {order_id}
    -- claimed_total_cents: 100000
    -- verified_total_cents: 50000
    -- ghost_revenue_cents: 50000
    -- discrepancy_bps: 10000
    -- verification_source: shopify
    """

    # Emit evidence artifacts
    summary = {
        "tenant_id": str(tenant_id),
        "allocation_id": str(allocation_id),
        "order_id": order_id,
        "transaction_id": transaction_id,
        "platform_claims": [
            {"source": "meta", "amount_cents": 50000},
            {"source": "google", "amount_cents": 50000},
        ],
        "verified_revenue": {
            "source": "shopify",
            "amount_cents": 50000,
        },
        "reconciliation_result": {
            "claimed_total_cents": result.claimed_total_cents,
            "verified_total_cents": result.verified_total_cents,
            "ghost_revenue_cents": result.ghost_revenue_cents,
            "discrepancy_bps": result.discrepancy_bps,
        },
        "invariants": {
            "verified_wins": True,
            "penny_perfect": True,
            "idempotent": True,
        },
        "timestamp": now.isoformat(),
    }

    EVIDENCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE_JSON.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    EVIDENCE_MD.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE_MD.open("w", encoding="utf-8") as fh:
        fh.write("# Value Trace 01-WIN: Ghost Revenue Reconciliation\n\n")
        fh.write("## Scenario\n\n")
        fh.write("- Meta claims $500 for order (last-click attribution)\n")
        fh.write("- Google claims $500 for order (view-through attribution)\n")
        fh.write("- Shopify webhook confirms $500 actual revenue\n\n")
        fh.write("## Results\n\n")
        fh.write(f"| Metric | Value |\n")
        fh.write(f"|--------|-------|\n")
        fh.write(f"| tenant_id | `{tenant_id}` |\n")
        fh.write(f"| order_id | `{order_id}` |\n")
        fh.write(f"| claimed_total_cents | {result.claimed_total_cents} |\n")
        fh.write(f"| verified_total_cents | {result.verified_total_cents} |\n")
        fh.write(f"| ghost_revenue_cents | {result.ghost_revenue_cents} |\n")
        fh.write(f"| discrepancy_bps | {result.discrepancy_bps} (100%) |\n\n")
        fh.write("## SQL Proof Query\n\n")
        fh.write("```sql\n")
        fh.write(sql_proof)
        fh.write("\n```\n\n")
        fh.write("## Invariants Proven\n\n")
        fh.write("- [x] Verified truth wins (Shopify is source of truth)\n")
        fh.write("- [x] Ghost revenue detected (100% over-claim)\n")
        fh.write("- [x] Penny-perfect calculations (integer cents, no floats)\n")
        fh.write("- [x] Idempotent reconciliation (second run = same result)\n")
