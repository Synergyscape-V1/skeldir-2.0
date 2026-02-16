# Value Trace 01-WIN: Ghost Revenue Reconciliation

## Scenario

- Meta claims $500 for order (last-click attribution)
- Google claims $500 for order (view-through attribution)
- Shopify webhook confirms $500 actual revenue

## Results

| Metric | Value |
|--------|-------|
| tenant_id | `bdfc84e9-53e1-4022-88c6-1ebfc78ff9c1` |
| order_id | `order-362e81bb` |
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
    WHERE tenant_id = 'bdfc84e9-53e1-4022-88c6-1ebfc78ff9c1'
      AND order_id = 'order-362e81bb';

    -- Result:
    -- order_id: order-362e81bb
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
