"""
Revenue Reconciliation Service for Ghost Revenue Detection.

This service implements the deterministic reconciliation algorithm for detecting
ghost revenue - the discrepancy between platform claims and verified truth.

Design Principles:
- Verified truth wins (Shopify/Stripe webhook is source of truth)
- Penny-perfect calculations using integer cents
- Idempotent operations (running twice yields identical result)
- Full audit trail for forensic analysis

Architecture:
- Platform claims come from attribution events (Meta, Google, etc.)
- Verified truth comes from payment processor webhooks
- Ghost revenue = max(0, claimed - verified)
- Discrepancy in basis points (avoids floats)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.money import MoneyCents, BasisPoints, add_cents, to_basis_points

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlatformClaim:
    """A revenue claim from an attribution platform."""
    source: str  # e.g., "meta", "google", "tiktok"
    amount_cents: MoneyCents
    claim_timestamp: datetime
    claim_id: Optional[str] = None


@dataclass(frozen=True)
class VerifiedRevenue:
    """Verified revenue from payment processor webhook."""
    source: str  # e.g., "stripe", "shopify", "paypal"
    amount_cents: MoneyCents
    verification_timestamp: datetime
    transaction_id: str


@dataclass(frozen=True)
class ReconciliationResult:
    """Result of the ghost revenue reconciliation."""
    tenant_id: UUID
    order_id: str
    claimed_total_cents: MoneyCents
    verified_total_cents: MoneyCents
    ghost_revenue_cents: MoneyCents
    discrepancy_bps: BasisPoints
    claim_sources: List[str]
    verification_source: str
    reconciled_at: datetime
    ledger_id: UUID


class RevenueReconciliationService:
    """
    Service for reconciling platform claims against verified revenue.

    The reconciliation algorithm:
    1. Pull all platform claims for the order (Meta, Google, etc.)
    2. Pull verified truth from payment processor
    3. Compute claimed_total = sum(claims)
    4. Compute ghost_revenue = max(0, claimed_total - verified)
    5. Compute discrepancy_bps = (ghost * 10000) / verified
    6. Upsert into revenue_ledger

    Critical Invariants:
    - IDEMPOTENT: Running twice yields identical row
    - SOURCE_OF_TRUTH: Verified wins; claims do not overwrite
    - CENT_CORRECT: All arithmetic uses integers
    """

    async def reconcile_order(
        self,
        conn: AsyncConnection,
        tenant_id: UUID,
        order_id: str,
        platform_claims: List[PlatformClaim],
        verified_revenue: VerifiedRevenue,
    ) -> ReconciliationResult:
        """
        Reconcile platform claims against verified revenue for an order.

        This is the core reconciliation algorithm that detects ghost revenue.

        Args:
            conn: Database connection with tenant context set.
            tenant_id: The tenant UUID.
            order_id: The order identifier.
            platform_claims: List of claims from attribution platforms.
            verified_revenue: The verified truth from payment processor.

        Returns:
            ReconciliationResult with all computed values.

        Raises:
            ValueError: If no verified revenue provided.
        """
        if not verified_revenue:
            raise ValueError("Verified revenue is required for reconciliation")

        now = datetime.now(timezone.utc)

        # Step 1: Calculate claimed total (sum of all platform claims)
        claimed_total_cents = MoneyCents(0)
        if platform_claims:
            claimed_total_cents = add_cents(
                *[MoneyCents(claim.amount_cents) for claim in platform_claims]
            )

        # Step 2: Get verified total
        verified_total_cents = MoneyCents(verified_revenue.amount_cents)

        # Step 3: Calculate ghost revenue (never negative)
        ghost_revenue_cents = MoneyCents(
            max(0, claimed_total_cents - verified_total_cents)
        )

        # Step 4: Calculate discrepancy in basis points (avoids floats)
        if verified_total_cents > 0:
            discrepancy_bps = to_basis_points(ghost_revenue_cents, verified_total_cents)
        else:
            # If verified is 0, discrepancy is 100% if any claims exist
            discrepancy_bps = BasisPoints(10000 if claimed_total_cents > 0 else 0)

        # Step 5: Upsert into revenue_ledger
        ledger_id = uuid4()
        claim_sources = sorted(set(c.source for c in platform_claims))

        await self._upsert_ledger_row(
            conn=conn,
            ledger_id=ledger_id,
            tenant_id=tenant_id,
            order_id=order_id,
            transaction_id=verified_revenue.transaction_id,
            claimed_total_cents=claimed_total_cents,
            verified_total_cents=verified_total_cents,
            ghost_revenue_cents=ghost_revenue_cents,
            discrepancy_bps=discrepancy_bps,
            verification_source=verified_revenue.source,
            verification_timestamp=verified_revenue.verification_timestamp,
            reconciled_at=now,
        )

        logger.info(
            "revenue_reconciliation_complete",
            extra={
                "tenant_id": str(tenant_id),
                "order_id": order_id,
                "claimed_total_cents": claimed_total_cents,
                "verified_total_cents": verified_total_cents,
                "ghost_revenue_cents": ghost_revenue_cents,
                "discrepancy_bps": discrepancy_bps,
                "claim_sources": claim_sources,
            },
        )

        return ReconciliationResult(
            tenant_id=tenant_id,
            order_id=order_id,
            claimed_total_cents=claimed_total_cents,
            verified_total_cents=verified_total_cents,
            ghost_revenue_cents=ghost_revenue_cents,
            discrepancy_bps=discrepancy_bps,
            claim_sources=claim_sources,
            verification_source=verified_revenue.source,
            reconciled_at=now,
            ledger_id=ledger_id,
        )

    async def _upsert_ledger_row(
        self,
        conn: AsyncConnection,
        ledger_id: UUID,
        tenant_id: UUID,
        order_id: str,
        transaction_id: str,
        claimed_total_cents: MoneyCents,
        verified_total_cents: MoneyCents,
        ghost_revenue_cents: MoneyCents,
        discrepancy_bps: BasisPoints,
        verification_source: str,
        verification_timestamp: datetime,
        reconciled_at: datetime,
    ) -> None:
        """
        Upsert a reconciliation row into revenue_ledger.

        Uses ON CONFLICT to ensure idempotency on (tenant_id, order_id).
        """
        # RAW_SQL_ALLOWLIST: revenue reconciliation upsert
        await conn.execute(
            text("""
                INSERT INTO revenue_ledger (
                    id, tenant_id, order_id, transaction_id, state,
                    amount_cents, currency, verification_source, verification_timestamp,
                    claimed_total_cents, verified_total_cents, ghost_revenue_cents, discrepancy_bps,
                    metadata, created_at, updated_at
                ) VALUES (
                    :id, :tenant_id, :order_id, :transaction_id, 'captured',
                    :verified_total_cents, 'USD', :verification_source, :verification_timestamp,
                    :claimed_total_cents, :verified_total_cents, :ghost_revenue_cents, :discrepancy_bps,
                    :metadata, :reconciled_at, :reconciled_at
                )
                ON CONFLICT (transaction_id) DO UPDATE SET
                    claimed_total_cents = EXCLUDED.claimed_total_cents,
                    verified_total_cents = EXCLUDED.verified_total_cents,
                    ghost_revenue_cents = EXCLUDED.ghost_revenue_cents,
                    discrepancy_bps = EXCLUDED.discrepancy_bps,
                    updated_at = EXCLUDED.updated_at
            """),
            {
                "id": str(ledger_id),
                "tenant_id": str(tenant_id),
                "order_id": order_id,
                "transaction_id": transaction_id,
                "verified_total_cents": verified_total_cents,
                "verification_source": verification_source,
                "verification_timestamp": verification_timestamp,
                "claimed_total_cents": claimed_total_cents,
                "ghost_revenue_cents": ghost_revenue_cents,
                "discrepancy_bps": discrepancy_bps,
                "metadata": "{}",
                "reconciled_at": reconciled_at,
            },
        )

    async def get_reconciliation_by_order(
        self,
        conn: AsyncConnection,
        tenant_id: UUID,
        order_id: str,
    ) -> Optional[ReconciliationResult]:
        """
        Retrieve the reconciliation result for an order.

        Args:
            conn: Database connection with tenant context set.
            tenant_id: The tenant UUID.
            order_id: The order identifier.

        Returns:
            ReconciliationResult if found, None otherwise.
        """
        result = await conn.execute(
            text("""
                SELECT
                    id, order_id, transaction_id,
                    claimed_total_cents, verified_total_cents,
                    ghost_revenue_cents, discrepancy_bps,
                    verification_source, verification_timestamp,
                    updated_at
                FROM revenue_ledger
                WHERE tenant_id = :tenant_id AND order_id = :order_id
                ORDER BY updated_at DESC
                LIMIT 1
            """),
            {"tenant_id": str(tenant_id), "order_id": order_id},
        )
        row = result.mappings().first()
        if not row:
            return None

        return ReconciliationResult(
            tenant_id=tenant_id,
            order_id=row["order_id"],
            claimed_total_cents=MoneyCents(row["claimed_total_cents"]),
            verified_total_cents=MoneyCents(row["verified_total_cents"]),
            ghost_revenue_cents=MoneyCents(row["ghost_revenue_cents"]),
            discrepancy_bps=BasisPoints(row["discrepancy_bps"]),
            claim_sources=[],  # Would need join to get this
            verification_source=row["verification_source"],
            reconciled_at=row["updated_at"],
            ledger_id=UUID(str(row["id"])),
        )
