# B0.5.7-P3 — Webhook Ingestion Unblocking (Least-Privilege Tenant Secret Resolution)

## Authority boundary

This evidence pack treats prior docs/specs/plans as hypotheses and substantiates only what was reproduced from the `main` code + a locally booted DB topology that matches the P3 failure mode (runtime identity cannot `SELECT public.tenants`).

## Change reference

- Implementation commit: `4a00100`
- Ledger update commit: `8bb3c7f`
- Workflow: `.github/workflows/b057-p3-webhook-ingestion-least-privilege.yml` (runs on PRs + pushes to `main`)

## Objective (P3)

Eliminate the hard-stop where webhook ingestion returns HTTP 500 under least-privilege runtime DB identity because tenant secret resolution performs a direct `SELECT ... FROM public.tenants`.

## Static chain mapping (repo truth)

- Webhook route → tenant resolution dependency:
  - `backend/app/api/webhooks.py`: `tenant_secrets()` calls `get_tenant_with_webhook_secrets()`
- Tenant resolution implementation (pre-fix):
  - `backend/app/core/tenant_context.py`: direct `SELECT ... FROM tenants WHERE api_key_hash = :api_key_hash`
- Persistence target:
  - `backend/app/ingestion/event_service.py`: inserts `AttributionEvent` rows into `public.attribution_events` via `ingest_with_transaction(...)` (RLS enforced by `app.current_tenant_id`)

## Runtime topology used (topology truth)

Postgres 16 in Docker with:

- `migration_owner` (admin identity for migrations + seeding)
- `app_user` (runtime identity; member of `app_rw` / `app_ro`)
- No GRANT allowing `app_user`/`app_rw` to `SELECT public.tenants`

Key invariant probe (runtime identity cannot read `tenants`):

```sql
-- as app_user
SELECT id FROM public.tenants LIMIT 1;
-- ERROR:  permission denied for table tenants
```

## Pre-fix reproduction (EG-P3-1 / EG-P3-2)

### 1) Controlled webhook call returns 500

Request:

- Endpoint: `POST /api/webhooks/stripe/payment_intent/succeeded`
- Headers:
  - `X-Skeldir-Tenant-Key: b057_p3_test_tenant_key`
  - `Stripe-Signature: t=<ts>,v1=<sig>`

Observed:

- HTTP status: `500 Internal Server Error`
- API log excerpt (runtime identity `app_user`):

```text
asyncpg.exceptions.InsufficientPrivilegeError: permission denied for table tenants
... backend/app/core/tenant_context.py:get_tenant_with_webhook_secrets
... SELECT ... FROM tenants WHERE api_key_hash = $1
```

This matches the reported hard-stop failure mode: webhook ingress cannot proceed to signature validation / persistence when tenant secret resolution queries `tenants` directly.

## Remediation implemented (P3 constraints preserved)

### 1) Add mediated interface (SECURITY DEFINER)

- Migration: `alembic/versions/007_skeldir_foundation/202601211900_b057_p3_webhook_tenant_secret_resolver.py`
  - Creates `security` schema (if missing)
  - Adds `security.resolve_tenant_webhook_secrets(api_key_hash text)` as `SECURITY DEFINER`
  - Grants `USAGE` on `security` schema + `EXECUTE` on function to runtime roles
  - Explicitly revokes `PUBLIC` from the function

### 2) Switch webhook tenant resolution to mediated interface

- Code: `backend/app/core/tenant_context.py`
  - Replaces direct tenant table read with:
    - `FROM security.resolve_tenant_webhook_secrets(:api_key_hash)`

No GRANT widening to `public.tenants` was introduced for runtime roles.

## Post-fix verification (EG gates)

### EG-P3-1: Repro/Elimination Gate (Hard-stop removed)

Same request as pre-fix now returns `200 OK`:

```json
{"status":"success","event_id":"...","idempotency_key":"...","dead_event_id":null,"channel":"unknown","error":null}
```

### EG-P3-2: Least-Privilege Non-Regression Gate

Runtime identity still cannot read `public.tenants`:

```sql
-- as app_user
SELECT id FROM public.tenants LIMIT 1;
-- ERROR:  permission denied for table tenants
```

### EG-P3-3: Tenant Resolution Mediation Gate

Runtime identity can resolve secrets via mediated function:

```sql
-- as app_user
SELECT stripe_webhook_secret
FROM security.resolve_tenant_webhook_secrets('<sha256(api_key)>');
-- returns 'whsec_b057_p3_stripe'
```

### EG-P3-4: Webhook Semantics Gate

- Invalid signature → `401` (never `500`)
- Missing tenant key → `401` (never `500`)
- Unknown tenant key → `401` (never `500`)

### EG-P3-5: Persistence + Tenant Scoping Gate

DB proof: inserted event exists and is tenant-scoped (requires tenant GUC due to RLS):

```sql
SELECT set_config('app.current_tenant_id','<tenant_uuid>', false);
SELECT tenant_id, external_event_id, revenue_cents
FROM public.attribution_events
WHERE external_event_id = 'pi_b057_p3_post'
LIMIT 1;
-- tenant_id matches the seeded tenant UUID; revenue_cents = 1234
```

### EG-P3-6: CI Reality Gate (anti-Green-Illusion)

Dedicated workflow + test:

- Workflow: `.github/workflows/b057-p3-webhook-ingestion-least-privilege.yml`
- Integration test: `backend/tests/integration/test_b057_p3_webhook_ingestion_unblocking.py`

This boots Postgres, applies migrations as `migration_owner`, runs API under `app_user` (no `SELECT` on `public.tenants`), submits a real HTTP webhook request, and asserts persistence and 4xx semantics.

CI run URL: pending after merge/push (workflow is configured to run on `push` to `main` and on `pull_request`).

## Artifacts (local repro)

Local repro logs captured under `artifacts/b057p3/` (pre-fix + post-fix HTTP responses and API stderr traces).
