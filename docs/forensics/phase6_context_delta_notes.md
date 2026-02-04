# Phase 6 Context Delta Notes (B0.6)

Date: 2026-02-03
Repo: <repo-root>

## Step A - Runtime topology + start command

Commands:
- Get-Content docker-compose.component-dev.yml
- Get-ChildItem -Recurse -Filter Dockerfile
- Get-Content Procfile
- Get-Content docs/backend/local_db_rebuild_windows.md

Findings:
- docker-compose.component-dev.yml declares the component-dev stack and usage `docker-compose -f docker-compose.component-dev.yml up` (docker-compose.component-dev.yml:3-5).
- Services + ports in compose: postgres 5432, ingestion 8001, attribution 8002, auth 8003, webhooks 8004 (docker-compose.component-dev.yml:8-118).
- Compose references Dockerfiles at `backend/app/ingestion/Dockerfile`, `backend/app/attribution/Dockerfile`, `backend/app/auth/Dockerfile`, and `backend/app/webhooks/Dockerfile` (docker-compose.component-dev.yml:28-30, 49-52, 70-74, 96-98). `Get-ChildItem -Recurse -Filter Dockerfile` returns only `node_modules/swagger2openapi/Dockerfile`, so the referenced Dockerfiles are missing.
- Procfile defines the monolith API entrypoint: `uvicorn app.main:app --host 0.0.0.0 --port 8000` (Procfile:17-19).
- Migrations are documented as manual commands (no compose hook): `alembic upgrade 202511131121` then `alembic upgrade skeldir_foundation@head` (docs/backend/local_db_rebuild_windows.md:273-280).

Conclusion:
- The only concrete runtime entrypoint in-repo is the Procfile monolith on port 8000. The component-dev compose is not startable as-is because it references missing Dockerfiles, and migrations are manual (no startup hook in compose).

## Step B - Provider activation gates (DB rows required)

Commands:
- Get-Content backend/app/services/realtime_revenue_providers.py
- Get-Content backend/app/services/platform_credentials.py
- Get-Content alembic/versions/007_skeldir_foundation/202601281200_b060_phase2_platform_connections.py
- Get-Content backend/app/api/platforms.py
- Get-Content backend/app/core/config.py

Findings:
- Provider fetcher selects platform_connections for the tenant with status = "active" (backend/app/services/realtime_revenue_providers.py:396-401) and dedupes to one connection per platform.
- Only connections whose platform key exists in ProviderRegistry are used (backend/app/services/realtime_revenue_providers.py:411-416).
- Credentials are required per connection: PlatformCredentialService.get_credentials uses PLATFORM_TOKEN_ENCRYPTION_KEY and raises if missing/expired (backend/app/services/realtime_revenue_providers.py:432-446; backend/app/services/platform_credentials.py:150-200).
- platform_connections and platform_credentials tables (with RLS) are created in migration 202601281200 (alembic/versions/007_skeldir_foundation/202601281200_b060_phase2_platform_connections.py:24-79, 104-113).
- Platform connection API validates platforms against settings.PLATFORM_SUPPORTED_PLATFORMS (backend/app/api/platforms.py:36-46; backend/app/core/config.py:58-69).

Conclusion:
- Provider fetch is enabled only when the DB has: (1) tenants row, (2) platform_connections row for the tenant with status "active" and platform in registry, (3) platform_credentials row for the connection, and (4) PLATFORM_TOKEN_ENCRYPTION_KEY configured. RLS requires app.current_tenant_id to be set for non-admin sessions.

## Step C - Provider base URL routing

Commands:
- Get-Content backend/app/services/realtime_revenue_providers.py
- Get-Content backend/app/core/config.py
- Get-Content backend/app/api/attribution.py
- Get-Content backend/app/api/revenue.py

Findings:
- StripeRevenueProvider defaults base_url to https://api.stripe.com and uses DefaultHttpClient if no custom client is injected (backend/app/services/realtime_revenue_providers.py:176-203).
- Default provider registry includes StripeRevenueProvider and DummyRevenueProvider only (backend/app/services/realtime_revenue_providers.py:310-312).
- Settings define token/key and supported platforms only; there are no base URL settings for providers (backend/app/core/config.py:58-69).
- API handlers build the fetcher without a custom registry, so they use DEFAULT_PROVIDER_REGISTRY (backend/app/api/attribution.py:63-71; backend/app/api/revenue.py:51-60; backend/app/services/realtime_revenue_providers.py:362-376).

Conclusion:
- There is currently no env-configured base URL override for providers. If a stripe connection is seeded, the API will attempt to call https://api.stripe.com unless the registry is overridden in-process. This violates the Phase 6 no-external-calls constraint unless routing is made explicit.

## Step D - CI workflow that would adjudicate Phase 6 E2E

Commands:
- Get-Content .github/workflows/b06_phase0_adjudication.yml
- Get-Content .github/workflows/ci.yml

Findings:
- B0.6 Phase 0 Adjudication workflow runs unit/contract tests only; no E2E or docker compose steps (.github/workflows/b06_phase0_adjudication.yml:1-57).
- The main CI workflow is ci.yml and it runs B0.6 unit tests but no B0.6 E2E orchestration (.github/workflows/ci.yml:1219-1228).

Conclusion:
- There is no existing workflow that runs B0.6 E2E. The merge-blocking candidate to extend is `.github/workflows/ci.yml` (and optionally the B0.6 adjudication workflow if it is required in branch protection; this cannot be verified from repo files).


## Stop condition check
- Exact DB rows/conditions for provider fetch are identified. (Step B complete.)
- Env vars for provider base URL do not exist; routing is hardcoded in provider defaults. (Step C complete.)
- CI workflow for adjudication identified; no E2E yet. (Step D complete.)
