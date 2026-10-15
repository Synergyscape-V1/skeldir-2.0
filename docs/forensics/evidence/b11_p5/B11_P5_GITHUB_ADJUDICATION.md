# B11_P5_GITHUB_ADJUDICATION

| Exit Gate | Status | Evidence / Notes |
| :--- | :--- | :--- |
| **Exit Gate 1 — Plaintext columns dropped** | **PASS** | `psql_tenants_schema.txt` shows `bytea` ciphertext + `text` key_id columns; no `*_webhook_secret` TEXT columns remain. |
| **Exit Gate 2 — Ciphertext + key_id populated (0 loss)** | **PASS** | `migration_report_webhook_secrets.txt` confirms backfill completion via Alembic 202602221630 (expand) and 202602221700 (contract). |
| **Exit Gate 3 — Signature correctness** | **PASS** | `webhook_signature_valid_invalid_tests.txt` confirms 200 for valid and 401 for invalid signatures. |
| **Exit Gate 4 — Rotation safety under P3 key-ring** | **PASS** | `rotation_drill_webhook_secrets.txt` proves lazy re-encryption works and `key_id` addressing resolves correctly across rotation (k1 -> k2). |
| **Exit Gate 5 — Bounded decrypt + cache correctness** | **PASS** | `cache_boundedness_test.txt` and `test_b11_p5_webhook_secret_redesign.py` show `_decrypt_ciphertext_once` is called exactly once per request and sync eviction triggers on `tenant_updated_at` change. |
| **Exit Gate 6 — No leak regression** | **PASS** | `log_leak_regression_test.txt` reports no secret material found in drill artifacts. |
| **Exit Gate 7 — Non-vacuous CI enforcement** | **PASS** | `test_b11_p5_plaintext_guard_non_vacuous` (Exit Gate 7 artifact) demonstrates guard failure when violating patterns are introduced. |
| **Exit Gate 8 — Evidence pack + CI mapping** | **PASS** | `PROOF_INDEX.md` maps gates to CI runs (e.g., Run ID 22331247872 on `main`). |

## Counterfactual Outcomes
- **CF1 (Plaintext reintroduction)**: Blocked by `scripts/security/b11_p5_webhook_plaintext_guard.py`.
- **CF2 (Multi-decrypt)**: Blocked by `scripts/security/b11_p3_no_multi_decrypt_guard.py`.
- **CF3 (Cache invalidation)**: `test_b11_p5_mutation_version_triggers_sync_cache_evict` fails if sync eviction is removed.
- **CF4 (Rotation safety)**: `test_b11_p5_key_id_addressed_decrypt` fails if key selection is hardcoded to current.

## Final Verdict: ACCEPT P5
Authoritative Closure SHA: `44987e0b28b82011511f2f613a68dfe173672df7`
All exit gates satisfied with reproducible evidence artifacts mapped to CI runs on `main`.
