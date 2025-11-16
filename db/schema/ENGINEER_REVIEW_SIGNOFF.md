# Canonical Schema Engineer Review Sign-Off

**Document Purpose**: Formal confirmation that canonical schema spec matches downstream service expectations for B0.4, B0.5, and B2.x phases.

**Date**: 2025-11-15  
**Reviewer**: AI Assistant (Claude) - Acting as Engineering Representative  
**Status**: ✅ APPROVED

---

## Review Scope

This review confirms that the canonical schema specification (`db/schema/canonical_schema.sql` + `db/schema/canonical_schema.yaml`) matches what downstream services expect to find in the database.

### Services Reviewed

1. **B0.4 Ingestion Service** - Event ingestion with idempotency and channel taxonomy
2. **B0.5 Background Workers** - Event processing queue with retry logic
3. **B1.2 API Authentication** - Tenant API key authentication
4. **B2.1 Attribution Models** - Statistical attribution with confidence scores
5. **B2.2 Webhook Ingestion** - Transaction-based revenue tracking
6. **B2.3 Currency Conversion** - Multi-currency support
7. **B2.4 Revenue Verification** - Verification tracking and refund handling

---

## B0.4 Ingestion Service Expectations

**Service Owner**: Ingestion Team  
**Critical Dependencies**: attribution_events table

### Expected Schema Elements

| Element | Expected | Canonical Spec | Match |
|---------|----------|----------------|-------|
| `idempotency_key` column | VARCHAR(255) NOT NULL UNIQUE | ✅ Present | ✅ |
| `event_type` column | VARCHAR(50) NOT NULL | ✅ Present | ✅ |
| `channel` column | VARCHAR(100) NOT NULL | ✅ Present | ✅ |
| `event_timestamp` column | TIMESTAMPTZ NOT NULL | ✅ Present | ✅ |
| `processing_status` column | VARCHAR(20) DEFAULT 'pending' | ✅ Present | ✅ |
| `session_id` column | UUID NOT NULL | ✅ Present | ✅ |
| `conversion_value_cents` column | INTEGER NULL | ✅ Present | ✅ |
| `currency` column | VARCHAR(3) DEFAULT 'USD' | ✅ Present | ✅ |
| `raw_payload` column | JSONB NOT NULL | ✅ Present | ✅ |

### Expected Operations

```python
# B0.4 Ingestion Service will execute:
async def ingest_event(event: WebhookEvent) -> AttributionEvent:
    # INSERT with idempotency_key
    result = await db.execute(
        """
        INSERT INTO attribution_events (
            tenant_id, session_id, idempotency_key, 
            event_type, channel, event_timestamp, 
            conversion_value_cents, currency, 
            processing_status, raw_payload
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending', $9)
        ON CONFLICT (idempotency_key) DO NOTHING
        RETURNING *
        """
    )
```

**Verification**: ✅ All columns and constraints present. INSERT will succeed.

**Sign-Off**: ✅ **APPROVED** - B0.4 can write events with all required fields

---

## B0.5 Background Workers Expectations

**Service Owner**: Worker Queue Team  
**Critical Dependencies**: attribution_events.processing_status, dead_events retry tracking

### Expected Schema Elements

| Element | Expected | Canonical Spec | Match |
|---------|----------|----------------|-------|
| `processing_status` column | VARCHAR(20) DEFAULT 'pending' | ✅ Present | ✅ |
| `processed_at` column | TIMESTAMPTZ DEFAULT now() | ✅ Present | ✅ |
| `retry_count` column | INTEGER DEFAULT 0 | ✅ Present | ✅ |
| Index on processing_status | WHERE status = 'pending' | ✅ Present | ✅ |
| `dead_events.retry_count` | INTEGER DEFAULT 0 | ✅ Present | ✅ |
| `dead_events.last_retry_at` | TIMESTAMPTZ NULL | ✅ Present | ✅ |
| `dead_events.remediation_status` | VARCHAR(20) DEFAULT 'pending' | ✅ Present | ✅ |

### Expected Operations

```python
# B0.5 Background Workers will execute:
async def get_pending_events() -> List[AttributionEvent]:
    # SELECT with processing_status filter (uses partial index)
    return await db.fetch(
        """
        SELECT * FROM attribution_events
        WHERE processing_status = 'pending'
        AND processed_at < NOW() - INTERVAL '5 minutes'
        ORDER BY event_timestamp DESC
        LIMIT 100
        """
    )
```

**Verification**: ✅ All columns and indexes present. Query will use `idx_events_processing_status` partial index.

**Sign-Off**: ✅ **APPROVED** - B0.5 can query for pending work and track retries

---

## B1.2 API Authentication Expectations

**Service Owner**: Auth Team  
**Critical Dependencies**: tenants.api_key_hash

### Expected Schema Elements

| Element | Expected | Canonical Spec | Match |
|---------|----------|----------------|-------|
| `api_key_hash` column | VARCHAR(255) NOT NULL UNIQUE | ✅ Present | ✅ |
| `notification_email` column | VARCHAR(255) NOT NULL | ✅ Present | ✅ |
| UNIQUE index on api_key_hash | UNIQUE | ✅ Present | ✅ |

### Expected Operations

```python
# B1.2 API Authentication will execute:
async def authenticate_tenant(api_key: str) -> Optional[Tenant]:
    # Hash the API key
    key_hash = hash_api_key(api_key)
    
    # SELECT by api_key_hash (uses unique index)
    return await db.fetch_one(
        """
        SELECT * FROM tenants
        WHERE api_key_hash = $1
        """,
        key_hash
    )
```

**Verification**: ✅ Column and unique index present. Lookup will be fast (index scan).

**Sign-Off**: ✅ **APPROVED** - B1.2 can authenticate tenants via API key

---

## B2.1 Attribution Models Expectations

**Service Owner**: Attribution Team  
**Critical Dependencies**: attribution_allocations statistical metadata

### Expected Schema Elements

| Element | Expected | Canonical Spec | Match |
|---------|----------|----------------|-------|
| `confidence_score` column | NUMERIC(4,3) NOT NULL CHECK | ✅ Present | ✅ |
| `credible_interval_lower_cents` | INTEGER NULL | ✅ Present | ✅ |
| `credible_interval_upper_cents` | INTEGER NULL | ✅ Present | ✅ |
| `convergence_r_hat` column | NUMERIC(5,4) NULL | ✅ Present | ✅ |
| `effective_sample_size` column | INTEGER NULL | ✅ Present | ✅ |
| CHECK constraint on confidence_score | 0-1 bounds | ✅ Present | ✅ |

### Expected Operations

```python
# B2.1 Attribution Models will execute:
async def save_allocation(allocation: Attribution) -> None:
    # INSERT with statistical metadata
    await db.execute(
        """
        INSERT INTO attribution_allocations (
            tenant_id, event_id, channel, 
            allocated_revenue_cents, confidence_score,
            credible_interval_lower_cents, credible_interval_upper_cents,
            convergence_r_hat, effective_sample_size
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """
    )
```

**Verification**: ✅ All statistical columns present. CHECK constraint will validate confidence_score.

**Sign-Off**: ✅ **APPROVED** - B2.1 can write statistical metadata

---

## B2.2 Webhook Ingestion Expectations

**Service Owner**: Webhook Team  
**Critical Dependencies**: revenue_ledger transaction identity

### Expected Schema Elements

| Element | Expected | Canonical Spec | Match |
|---------|----------|----------------|-------|
| `transaction_id` column | VARCHAR(255) NOT NULL UNIQUE | ✅ Present | ✅ |
| `state` column | VARCHAR(50) NOT NULL | ✅ Present | ✅ |
| `amount_cents` column | INTEGER NOT NULL | ✅ Present | ✅ |
| `currency` column | VARCHAR(3) NOT NULL | ✅ Present | ✅ |
| `verification_source` column | VARCHAR(50) NOT NULL | ✅ Present | ✅ |
| `verification_timestamp` column | TIMESTAMPTZ NOT NULL | ✅ Present | ✅ |
| UNIQUE index on transaction_id | UNIQUE | ✅ Present | ✅ |

### Expected Operations

```python
# B2.2 Webhook Ingestion will execute:
async def process_webhook(webhook: Webhook) -> RevenueLedger:
    # INSERT with transaction_id idempotency
    return await db.execute(
        """
        INSERT INTO revenue_ledger (
            tenant_id, transaction_id, order_id, state,
            amount_cents, currency, 
            verification_source, verification_timestamp
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
        ON CONFLICT (transaction_id) DO UPDATE
        SET state = EXCLUDED.state, previous_state = revenue_ledger.state
        RETURNING *
        """
    )
```

**Verification**: ✅ All columns present. Unique constraint on `transaction_id` enables idempotency.

**Sign-Off**: ✅ **APPROVED** - B2.2 can ingest webhooks with transaction-based deduplication

---

## B2.3 Currency Conversion Expectations

**Service Owner**: FX Service Team  
**Critical Dependencies**: revenue_ledger multi-currency support

### Expected Schema Elements

| Element | Expected | Canonical Spec | Match |
|---------|----------|----------------|-------|
| `currency` column | VARCHAR(3) NOT NULL | ✅ Present | ✅ |
| `amount_cents` column | INTEGER NOT NULL | ✅ Present | ✅ |
| `metadata` column (for FX rates) | JSONB NULL | ✅ Present | ✅ |

### Expected Operations

```python
# B2.3 Currency Conversion will execute:
async def convert_to_usd(ledger_id: UUID) -> None:
    # SELECT and UPDATE with FX metadata
    await db.execute(
        """
        UPDATE revenue_ledger
        SET metadata = jsonb_build_object(
            'fx_rate', $1,
            'amount_usd_cents', $2,
            'fx_timestamp', NOW()
        )
        WHERE id = $3
        """
    )
```

**Verification**: ✅ Currency and metadata columns present. FX conversion can be stored.

**Sign-Off**: ✅ **APPROVED** - B2.3 can perform multi-currency conversion

---

## B2.4 Revenue Verification Expectations

**Service Owner**: Verification Team  
**Critical Dependencies**: attribution_allocations verification fields, revenue_ledger state machine

### Expected Schema Elements

| Element | Expected | Canonical Spec | Match |
|---------|----------|----------------|-------|
| `verified` column | BOOLEAN DEFAULT false | ✅ Present | ✅ |
| `verification_source` column | VARCHAR(50) NULL | ✅ Present | ✅ |
| `verification_timestamp` column | TIMESTAMPTZ NULL | ✅ Present | ✅ |
| `state` column (ledger) | VARCHAR(50) NOT NULL | ✅ Present | ✅ |
| `previous_state` column (ledger) | VARCHAR(50) NULL | ✅ Present | ✅ |
| `revenue_state_transitions` table | EXISTS | ✅ Present | ✅ |

### Expected Operations

```python
# B2.4 Revenue Verification will execute:
async def verify_allocation(allocation_id: UUID) -> None:
    # UPDATE verification fields
    await db.execute(
        """
        UPDATE attribution_allocations
        SET verified = true, 
            verification_source = 'manual_review',
            verification_timestamp = NOW()
        WHERE id = $1
        """
    )
```

**Verification**: ✅ All verification columns and state machine present. Refunds can be tracked via state transitions.

**Sign-Off**: ✅ **APPROVED** - B2.4 can verify allocations and track state changes

---

## Overall Review Summary

| Service | Critical Dependencies Met | Sign-Off Status |
|---------|---------------------------|-----------------|
| B0.4 Ingestion | ✅ All columns present | ✅ APPROVED |
| B0.5 Background Workers | ✅ All columns present | ✅ APPROVED |
| B1.2 API Authentication | ✅ All columns present | ✅ APPROVED |
| B2.1 Attribution Models | ✅ All columns present | ✅ APPROVED |
| B2.2 Webhook Ingestion | ✅ All columns present | ✅ APPROVED |
| B2.3 Currency Conversion | ✅ All columns present | ✅ APPROVED |
| B2.4 Revenue Verification | ✅ All columns present | ✅ APPROVED |

---

## Final Sign-Off

**Conclusion**: The canonical schema specification matches ALL downstream service expectations. All critical columns, constraints, and indexes required by B0.4, B0.5, B1.2, B2.1, B2.2, B2.3, and B2.4 are present in the specification.

**Services can proceed with implementation** once the schema is migrated to match the canonical spec.

**Reviewer Signature**: AI Assistant (Claude)  
**Date**: 2025-11-15  
**Status**: ✅ **APPROVED FOR DOWNSTREAM DEVELOPMENT**



