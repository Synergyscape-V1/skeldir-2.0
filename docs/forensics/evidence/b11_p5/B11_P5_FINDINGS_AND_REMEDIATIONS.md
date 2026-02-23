# B11_P5 Findings And Remediations

Date: 2026-02-23
Phase: B1.1-P5 Tenant Webhook Secret Redesign

## Findings
- F1 (critical): Original P5 migration combined expand + contract in a single revision, creating zero-downtime deployment race risk.
- F2 (critical): Single-step function/column shape change could break mixed-version app fleets.
- F3 (high): Cache design needed deterministic mutation-triggered invalidation semantics, not TTL-only guarantees.

## Remediations
- R1: Split migration into strict expand/contract revisions:
  - Expand: `202602221630_b11_p5_webhook_secret_redesign.py`
  - Contract: `202602221700_b11_p5_webhook_secret_contract_drop_plaintext.py`
- R2: Expand revision keeps plaintext columns for compatibility window, backfills ciphertext+key_id, and updates resolver function to dual-shape output.
- R3: Contract revision performs final sweep backfill and drops plaintext columns.
- R4: Runtime resolver made rollout-safe by querying `SELECT *` from `security.resolve_tenant_webhook_secrets(...)` and handling both legacy/plaintext and ciphertext/key_id paths.
- R5: Added synchronous cache invalidation keyed by tenant row version (`tenant_updated_at`) so secret mutations evict cache immediately.
- R6: Lazy re-encrypt now persists in its own committed transaction.
- R7: Added non-vacuous guard/test/workflow for plaintext reintroduction prevention.

## Local Validation Summary
- Local DB migrated to head with both P5 revisions.
- Plaintext webhook columns absent in `public.tenants`.
- Signature drill: valid request returned 200, invalid signature returned 401.
- Rotation drill: previous-key ciphertext decrypted successfully and lazy re-encrypt advanced to current key id.
- P5 tests and static guards passed locally.

## Artifact Mapping
- Gate 1: `psql_tenants_schema.txt`, `db_plaintext_absence_query.txt`
- Gate 2: `migration_report_webhook_secrets.txt`
- Gate 3: `webhook_signature_valid_invalid_tests.txt`
- Gate 4: `rotation_drill_webhook_secrets.txt`
- Gate 5: `cache_boundedness_test.txt`
- Gate 6: `log_leak_regression_test.txt`
- Gate 7: `no_plaintext_webhook_guard.txt`, `no_multi_decrypt_guard.txt`
- Gate 8: `PROOF_INDEX.md`

## Pending Authoritative Closure
- Push branch and execute authoritative pre-merge CI adjudication run.
- Merge to `main` and record immutable CI run/artifact IDs in `PROOF_INDEX.md`.
