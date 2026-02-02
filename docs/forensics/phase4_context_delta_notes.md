# Phase 4 Context Delta Notes (B0.6)

Date: 2026-02-02
Repo: C:\Users\ayewhy\II SKELDIR II

## Step A — Map the realtime revenue refresh path

Commands:
- Get-Content backend/app/api/attribution.py
- Get-Content backend/app/api/revenue.py
- Get-Content backend/app/services/realtime_revenue_cache.py

Findings:
- Endpoint path (attribution): `backend/app/api/attribution.py:get_realtime_revenue` calls `get_realtime_revenue_snapshot`.
- Endpoint path (v1): `backend/app/api/revenue.py:get_realtime_revenue_v1` calls `get_realtime_revenue_snapshot`.
- Cache service: `backend/app/services/realtime_revenue_cache.py:get_realtime_revenue_snapshot` uses an advisory-lock singleflight and calls `_refresh_snapshot`, which calls a `fetcher` (default `_default_fetcher`).
- Default fetcher is a hardcoded stub: `backend/app/services/realtime_revenue_cache.py:_default_fetcher` returns a fixed `revenue_total_cents=12_500_050` and `verified=False`.

Conclusion:
- Realtime revenue refresh path is endpoint -> cache service -> default fetcher stub. There is no provider adapter or normalization layer in this path.

## Step B — Verify Phase 2 substrate capabilities

Commands:
- Get-Content backend/app/models/platform_connection.py
- Get-Content backend/app/models/platform_credential.py
- Get-Content backend/app/services/platform_connections.py
- Get-Content backend/app/services/platform_credentials.py
- Get-Content backend/app/db/deps.py
- Get-Content backend/app/db/session.py
- Get-Content alembic/versions/007_skeldir_foundation/202601281200_b060_phase2_platform_connections.py

Findings:
- Platform connections exist: `platform_connections` table + ORM (`PlatformConnection`), with required `platform_account_id` and RLS enabled via migration `202601281200_b060_phase2_platform_connections.py`.
- Platform credentials exist: `platform_credentials` table + ORM (`PlatformCredential`), storing encrypted access/refresh tokens (pgcrypto), also RLS enabled.
- Credential storage/retrieval service exists: `PlatformCredentialStore.upsert_tokens` uses `pgp_sym_encrypt`; `PlatformCredentialStore.get_valid_token` decrypts via `pgp_sym_decrypt` using the provided `encryption_key`.
- Tenant context is set via `get_db_session` -> `db.session.get_session`, which sets `app.current_tenant_id` before yielding the session.

Conclusion:
- Phase 2 substrate exists in code (tables, models, RLS, service methods), and platform account binding is present via `platform_account_id`.
- There is no direct service that retrieves credentials by connection id for provider dispatch (only by platform + platform_account_id).

## Step C — Verify Phase 3 cache integration points

Commands:
- Get-Content backend/app/services/realtime_revenue_cache.py
- Get-Content alembic/versions/007_skeldir_foundation/202601281230_b060_phase3_realtime_revenue_cache.py

Findings:
- Cache service expects a `fetcher(tenant_id) -> RealtimeRevenueSnapshot` and writes payload + `data_as_of` to `revenue_cache_entries`.
- Failure semantics exist: `RealtimeRevenueUnavailable` raised on cooldown or refresh failure; `_record_failure` writes `error_cooldown_until`, `last_error_at`, and `last_error_message`, and endpoints map failures to 503 + Retry-After.

Conclusion:
- Phase 3 substrate is present and expects a deterministic fetcher; cooldown fields are implemented and wired to HTTP 503 handling.

## Step D — Verify CI adjudication hook

Commands:
- Get-Content .github/workflows/b06_phase0_adjudication.yml
- Get-Content .github/workflows/ci.yml
- rg -n "Required Checks" docs/CICD_WORKFLOW.md

Findings:
- Required-check visibility is not available from repo files; branch protection settings live in GitHub settings.
- The repo includes a dedicated workflow `B0.6 Phase 0 Adjudication` (`.github/workflows/b06_phase0_adjudication.yml`) running:
  - `tests/test_b06_realtime_revenue_v1.py`
  - `tests/test_b060_phase1_auth_tenant.py`
  - `tests/test_b060_phase2_platform_connections.py`
  - `tests/contract/test_contract_semantics.py`
- The broader `CI` workflow (`.github/workflows/ci.yml`) runs phase gates + multiple jobs, but required check enforcement cannot be proven locally.

Conclusion:
- Phase 4 tests must be added to a workflow that is (or is made) required for merges; the only explicit B0.6 adjudication workflow in-repo is `B0.6 Phase 0 Adjudication`.

## Hypothesis status (H4)

- H4-1 (Provider layer absent or stubbed): CONFIRMED. Default fetcher is stub; no provider adapters exist in code.
- H4-2 (No stable provider interface/registry/factory): CONFIRMED. No provider interface or registry in `backend/app`.
- H4-3 (Phase 2 credentials not wired into fetch path): CONFIRMED. Cache fetcher does not load platform connections or credentials.
- H4-4 (Missing platform account binding for API calls): REFUTED. `platform_account_id` exists on `platform_connections`.
- H4-5 (Normalization into OpenAPI schema not implemented as strict contract): CONFIRMED. No normalization layer exists; stub fetcher bypasses provider output normalization.
- H4-6 (Failure semantics not integrated with Phase 3 cooldown logic): PARTIALLY REFUTED. Cooldown + 503 mapping exists in cache + endpoints, but no provider error mapping is integrated.
- H4-7 (Test strategy insufficient for N>=2 / integration): CONFIRMED. No provider tests or integration tests exist.

## Root-cause hypotheses (RH4) alignment

- RH4-A (Real integration conflated with live network): PLAUSIBLE. Provider adapter work absent; no evidence of in-repo mock transport usage yet.
- RH4-B (No account binding model clarified): REFUTED. `platform_account_id` exists as canonical binding.
- RH4-C (Missing test taxonomy): SUPPORTED. Only cache/stub tests exist; no provider adapter or system integration tests.

## Stop condition check

- Phase 4 changes will touch:
  - `backend/app/services/realtime_revenue_cache.py` (replace default fetcher with provider aggregator)
  - New provider interface/registry modules under `backend/app/services/` (or `backend/app/providers/` if repo conventions require)
  - Platform credential retrieval service integration (new service or extension to `PlatformCredentialStore`)
  - Tests under `tests/` and/or `backend/tests/` (provider adapter, polymorphism, integration, stampede, cooldown)
  - CI workflow `b06_phase0_adjudication.yml` to include Phase 4 tests

Stop condition satisfied: exact functions/files are identified.
