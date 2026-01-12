# Schema Contract Guard Evidence

## Hypothesis Ledger

- **H-GUARD-00 — No enforceable schema contract guard exists today** — **VALIDATED**  
  - Search shows only incidental info_schema lookups, no guard suite: `.github/workflows/ci.yml:402`, `backend/tests/conftest.py:72`, `backend/tests/test_b052_queue_topology_and_dlq.py:127`, `backend/tests/test_b0535_worker_readonly_ingestion.py:34`. No dedicated guard test or CI job was present.
- **H-GUARD-01 — “Core tables” can be enumerated and are stable enough for a guard** — **VALIDATED**  
  - Canonical tables required for B0.3–B0.5.1: `tenants`, `attribution_events`, `attribution_allocations`, `revenue_ledger` (see `db/schema/canonical_schema.yaml` under each table). These are the same tables implicated by prior raw-insert failures and Celery foundation tests.
- **H-GUARD-02 — Raw SQL bypass still exists or can reappear undetected** — **VALIDATED**  
  - Inventory (pre-guard) from `rg -n "INSERT INTO (tenants|attribution_events|attribution_allocations|revenue_ledger|worker_failed_jobs|attribution_recompute_jobs)" backend/tests` showed direct inserts across integration/contract tests (e.g., `backend/tests/test_b0533_revenue_input_contract.py:116`, `backend/tests/integration/test_data_retention.py:86`, `backend/tests/test_b045_webhooks.py:51`, etc.). These paths are now explicitly allowlisted in `backend/tests/test_no_raw_inserts_core_tables.py`.
- **H-GUARD-03 — Builders exist but are not contract-verified** — **VALIDATED**  
  - Legacy builder `_insert_tenant` lives in `backend/tests/conftest.py:82` and dynamically omits required columns. No test verified alignment with NOT NULL schema before this change.

## Implementation

- **Manifest + Builders**
  - `backend/tests/builders/manifest.py` — declares core tables → approved builders.
  - `backend/tests/builders/core_builders.py` — RLS-aware builders that introspect required columns and populate deterministic defaults (tenants, attribution_events, attribution_allocations, revenue_ledger). Channel taxonomy seeding now fills required columns (family, is_paid, timestamps).
- **Runtime Schema Contract Guard**
  - `backend/tests/test_schema_contract_guard.py` — Introspects required columns (information_schema; NOT NULL + no default + non-identity), invokes approved builders, and fails with table/column context when drift exists.
- **Static Raw Insert Scanner**
  - `backend/tests/test_no_raw_inserts_core_tables.py` — Scans `backend/tests` for `INSERT INTO <core_table>` and fails unless the file is in the explicit allowlist or contains a `RAW_SQL_ALLOWLIST` marker. Legacy/raw fixtures are now enumerated in `ALLOWLIST_PATHS` with reasons.
- **CI Enforcement**
  - `.github/workflows/ci.yml` — Added `schema-contract-guard` job (Postgres service, Alembic upgrade to `202511131121` + `skeldir_foundation@head`, then `pytest -q backend/tests/test_schema_contract_guard.py backend/tests/test_no_raw_inserts_core_tables.py`).

## Commands & Evidence

- **Guard passing (post-remediation)**
  ```
  docker exec skeldir-gate-run bash -lc '
    cd /tmp/work &&
    export PYTHONPATH=/tmp/work &&
    export DATABASE_URL=postgresql+asyncpg://app_user:app_user@172.17.0.2:5432/skeldir_b03 &&
    export TESTING=1 CI=true &&
    /usr/bin/python3 -m pytest -q backend/tests/test_schema_contract_guard.py backend/tests/test_no_raw_inserts_core_tables.py
  '
  # Result: 2 passed in 1.90s
  ```

- **Sabotage drill (api_key_hash removed from tenant builder)**
  - Temporary change: removed `api_key_hash` population in `backend/tests/builders/core_builders.py`.
  - Run:
    ```
    /usr/bin/python3 -m pytest -q backend/tests/test_schema_contract_guard.py backend/tests/test_no_raw_inserts_core_tables.py
    ```
  - Failure (as expected):
    ```
    FAILED backend/tests/test_schema_contract_guard.py::test_schema_contract_guard
    tenants: builder build_tenant failed (Required columns: ['api_key_hash', 'name', 'notification_email'])
    attribution_events/allocations/revenue_ledger failed because tenant builder omitted api_key_hash
    ```
  - Restoration: reverted builder and reran guard → all tests pass (see passing command above).

## Core Table Manifest (enforced)

- `tenants` → `build_tenant`
- `attribution_events` → `build_attribution_event`
- `attribution_allocations` → `build_attribution_allocation`
- `revenue_ledger` → `build_revenue_ledger`

## Outstanding CI Proof

- Branch-level CI job `schema-contract-guard` is added and will execute on PR/main (runs migrations + guard tests). Main-branch proof pending after push/merge.
