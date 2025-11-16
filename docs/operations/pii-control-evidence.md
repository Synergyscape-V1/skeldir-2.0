# PII Control Evidence

**Purpose**: Empirical evidence of PII defense-in-depth controls operational effectiveness.

**Last Updated**: 2025-11-16  
**Status**: ⚠️ PENDING (Requires database connection for execution)

## Layer 2: Database Guardrail Evidence

### Test Protocol

**Script**: `scripts/database/validate-pii-guardrails.sh`

**Execution Command**:
```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/skeldir_test"
bash scripts/database/validate-pii-guardrails.sh
```

### Test Results

#### Test 1: INSERT with PII Key (Should FAIL)

**Command**:
```sql
INSERT INTO attribution_events (tenant_id, occurred_at, raw_payload) 
VALUES (
    '550e8400-e29b-41d4-a716-446655440000'::uuid, 
    NOW(), 
    '{"order_id": "123", "email": "test@test.com"}'::jsonb
);
```

**Expected Output**:
```
ERROR:  PII key detected in attribution_events.raw_payload. Ingestion blocked by database policy (Layer 2 guardrail). Key found: email. Reference: ADR-003-PII-Defense-Strategy.md. Action: Remove PII key from payload before retry.
```

**Actual Output**: ⚠️ PENDING (requires database connection)

**Status**: ✅ Test protocol documented, execution pending

---

#### Test 2: INSERT with PII in Value (Should SUCCEED - Expected Limitation)

**Command**:
```sql
INSERT INTO attribution_events (tenant_id, occurred_at, raw_payload) 
VALUES (
    '550e8400-e29b-41d4-a716-446655440000'::uuid, 
    NOW(), 
    '{"order_id": "123", "notes": "contact test@test.com"}'::jsonb
);
```

**Expected Output**:
```
INSERT 0 1
```

**Actual Output**: ⚠️ PENDING (requires database connection)

**Status**: ✅ Test protocol documented, execution pending

---

#### Test 3: INSERT into revenue_ledger with PII in metadata (Should FAIL)

**Command**:
```sql
INSERT INTO revenue_ledger (
    tenant_id, transaction_id, amount_cents, currency, state, 
    verification_source, verification_timestamp, metadata
) VALUES (
    '550e8400-e29b-41d4-a716-446655440000'::uuid,
    'tx_test_123',
    1000,
    'USD',
    'captured',
    'test',
    NOW(),
    '{"processor": "stripe", "email": "test@test.com"}'::jsonb
);
```

**Expected Output**:
```
ERROR:  PII key detected in revenue_ledger.metadata. Write blocked by database policy (Layer 2 guardrail). Key found: email. Reference: ADR-003-PII-Defense-Strategy.md. Action: Remove PII key from metadata before retry.
```

**Actual Output**: ⚠️ PENDING (requires database connection)

**Status**: ✅ Test protocol documented, execution pending

---

#### Test 4: INSERT into revenue_ledger with NULL metadata (Should SUCCEED)

**Command**:
```sql
INSERT INTO revenue_ledger (
    tenant_id, transaction_id, amount_cents, currency, state, 
    verification_source, verification_timestamp, metadata
) VALUES (
    '550e8400-e29b-41d4-a716-446655440000'::uuid,
    'tx_null_metadata_124',
    1000,
    'USD',
    'captured',
    'test',
    NOW(),
    NULL
);
```

**Expected Output**:
```
INSERT 0 1
```

**Actual Output**: ⚠️ PENDING (requires database connection)

**Status**: ✅ Test protocol documented, execution pending

---

## Layer 3: Audit Scan Evidence

### Test Protocol

**Script**: `scripts/database/run-audit-scan.sh`

**Execution Command**:
```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/skeldir_test"
bash scripts/database/run-audit-scan.sh
```

### Test Results

#### Test 1: Audit Scan Execution

**Command**:
```sql
SELECT fn_scan_pii_contamination();
```

**Expected Output** (clean database):
```
 fn_scan_pii_contamination 
---------------------------
                         0
(1 row)
```

**Actual Output**: ⚠️ PENDING (requires database connection)

**Status**: ✅ Test protocol documented, execution pending

---

#### Test 2: Findings Query

**Command**:
```sql
SELECT COUNT(*) FROM pii_audit_findings;
```

**Expected Output** (clean database):
```
 count 
-------
     0
(1 row)
```

**Actual Output**: ⚠️ PENDING (requires database connection)

**Status**: ✅ Test protocol documented, execution pending

---

#### Test 3: Intentional Contamination Test

**Setup** (bypass Layer 2 using migration_owner role):
```sql
SET ROLE migration_owner;

INSERT INTO attribution_events (id, tenant_id, occurred_at, raw_payload)
VALUES (
    '00000000-0000-0000-0000-000000000002'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    NOW(),
    '{"order_id": "999", "email": "contaminated@test.com"}'::jsonb
);

RESET ROLE;
```

**Audit Scan**:
```sql
SELECT fn_scan_pii_contamination();
```

**Expected Output**:
```
 fn_scan_pii_contamination 
---------------------------
                         1
(1 row)
```

**Findings Query**:
```sql
SELECT * FROM pii_audit_findings 
WHERE record_id = '00000000-0000-0000-0000-000000000002'::uuid;
```

**Expected Output**:
```
 id | table_name          | column_name | record_id                            | detected_key | sample_snippet        | detected_at                
----+---------------------+-------------+--------------------------------------+--------------+----------------------+---------------------------
  1 | attribution_events  | raw_payload | 00000000-0000-0000-0000-000000000002 | email        | Redacted for security | 2025-11-16 12:15:00.123456
(1 row)
```

**Actual Output**: ⚠️ PENDING (requires database connection)

**Status**: ✅ Test protocol documented, execution pending

---

## Summary

**Test Protocols**: ✅ All documented  
**Test Execution**: ⚠️ PENDING (requires database connection)  
**Evidence Collection**: Ready for execution

**Next Steps**: Execute tests when database is available and capture actual SQL outputs as evidence.

