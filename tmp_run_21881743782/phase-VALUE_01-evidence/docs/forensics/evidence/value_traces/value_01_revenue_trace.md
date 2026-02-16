# Value Trace 01-WIN: Ghost Revenue Reconciliation

## Scenario

- Meta claims $500 for order (last-click attribution)
- Google claims $500 for order (view-through attribution)
- Shopify webhook confirms $500 actual revenue

## Results

| Metric | Value |
|--------|-------|
| tenant_id | `a7c418c8-cb03-4d5e-ac97-6f5ae3a30129` |
| order_id | `order-2a7b82b9` |
| claimed_total_cents | 100000 |
| verified_total_cents | 50000 |
| ghost_revenue_cents | 50000 |
| discrepancy_bps | 10000 (100%) |

## SQL Proof Query

```sql

    SELECT
        order_id,
        claimed_total_cents,
        verified_total_cents,
        ghost_revenue_cents,
        discrepancy_bps,
        verification_source
    FROM revenue_ledger
    WHERE tenant_id = 'a7c418c8-cb03-4d5e-ac97-6f5ae3a30129'
      AND order_id = 'order-2a7b82b9';

    -- Result:
    -- order_id: order-2a7b82b9
    -- claimed_total_cents: 100000
    -- verified_total_cents: 50000
    -- ghost_revenue_cents: 50000
    -- discrepancy_bps: 10000
    -- verification_source: shopify
    
```

## Invariants Proven

- [x] Verified truth wins (Shopify is source of truth)
- [x] Ghost revenue detected (100% over-claim)
- [x] Penny-perfect calculations (integer cents, no floats)
- [x] Idempotent reconciliation (second run = same result)
