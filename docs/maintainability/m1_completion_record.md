# M1 Remediation Evidence Pack

**Canonical completion artifact:** `docs/maintainability/m1_completion_record.md`
**Phase:** M1 - Successor Onboarding and Local Development Authority
**Corrective date:** 2026-05-12
**Canonical topology:** `docker-compose.local.yml`
**Execution context:** container-first; host-native Python is noncanonical
**Final verdict:** `M1_BLOCKED_BY_PRIMARY_BRANCH_NOT_GREEN` until merged to `main` and main CI is green.

## Initial Findings

| ID | Finding | Remediation |
|---|---|---|
| H-M1-01 | No root `DEVELOPMENT.md`. | Added executable container-first onboarding guide. |
| H-M1-02 | `backend/README.md` claimed backend code was not migrated. | Removed stale language and pointed to `DEVELOPMENT.md`. |
| H-M1-03 | Runtime topology was ambiguous across E2E/component/deprecated compose files. | Declared `docker-compose.local.yml` as the single canonical local topology. |
| H-M1-04 | Make targets lacked local API/worker/migration authority. | Added `make dev`, `migrate`, `api`, `worker`, `health`, `smoke`, `test`, `down`, and `logs`. |
| H-M1-05 | Env templates did not cover local worker/Celery/B2.3 variables. | Added `.env.local.example` and made `.env.example` local-safe by default. |
| H-M1-06 | Migration path was undocumented and host-native. | `make migrate` runs Alembic inside the backend container. |
| H-M1-07 | API boot was not first-successor proven. | M1 workflow runs `make api` and `make health`. |
| H-M1-08 | Worker/broker proof was not part of onboarding. | M1 smoke calls `/health/worker` for a real Celery task round trip. |
| H-M1-09 | Worker DB access was not part of onboarding. | Existing `app.tasks.health.probe` executes `SELECT current_user`; smoke requires it. |
| H-M1-10 | Local defaults could point at external infrastructure. | Local env and smoke reject external DB/broker hosts. |
| H-M1-11 | Smoke proof could be vacuous. | Smoke checks DB, Alembic, RLS, API readiness, broker, worker, task result, and worker DB access. |
| H-M1-12 | CI did not act as first successor. | Added `.github/workflows/m1-local-dev-authority.yml` running documented commands. |
| H-M1-13 | M1 could pollute later phases. | Validator guards prohibited B2.4/B2.3/provider-boundary/dependency/migration surfaces. |
| CI-GOV-01 | Live `main` protection requires code-owner review, but the governance contract still recorded it as optional. | Updated the branch-protection integrity contract to match live protected-branch enforcement. |
| CI-GOV-02 | Legacy zero-container enforcement blocked the M1-required container-first onboarding artifacts. | Added a narrow M1 allowlist to the existing guard without disabling historical phase enforcement. |

## Files Changed

- `DEVELOPMENT.md`
- `README.md`
- `backend/README.md`
- `backend/Dockerfile`
- `.env.example`
- `.env.local.example`
- `docker-compose.local.yml`
- `Makefile`
- `scripts/smoke/m1_runtime_smoke.py`
- `scripts/ci/validate_m1_local_dev_authority.py`
- `scripts/ci/run_m1_onboarding_bootstrap.sh`
- `scripts/guard_no_docker.py`
- `.github/workflows/m1-local-dev-authority.yml`
- `contracts-internal/governance/main_branch_protection_integrity.main.json`
- `scripts/ci/validate_m0_scope_lock.py`
- `docs/maintainability/m1_completion_record.md`

## Command Surface

| Command | Authority |
|---|---|
| `make dev` | Starts local Postgres. The broker/result backend are Postgres-backed; no alternate broker service is used. |
| `make migrate` | Runs Alembic in the backend container against local Postgres. |
| `make api` | Starts FastAPI through Docker Compose. |
| `make worker` | Starts Celery worker through Docker Compose. |
| `make health` | Checks `/health/ready` from inside the API container. |
| `make smoke` | Runs non-vacuous M1 runtime smoke proof in the Compose topology. |
| `make test` | Runs M0/M1 validators only; full test authority remains M2. |
| `make down` | Stops local Compose topology. |
| `make logs` | Shows API and worker logs. |

## Env Coverage Summary

`.env.local.example` covers API DB, Alembic DB, Celery broker/result backend,
runtime environment, control-plane disablement, ingestion settings, JWT/platform
local placeholders, B2.3 worker pool controls, and Celery execution controls.
Defaults point to the local Compose service host `postgres`.

## CI Onboarding Harness Evidence

Workflow: `.github/workflows/m1-local-dev-authority.yml`

CI onboarding harness evidence is produced by job `m1-local-dev-authority`,
which performs:

```text
cp .env.local.example .env.local
python scripts/ci/validate_m1_local_dev_authority.py --baseline-sha <sha>
docker compose --env-file .env.local -f docker-compose.local.yml config
bash scripts/ci/run_m1_onboarding_bootstrap.sh
```

The bootstrap script runs the same documented commands:

```text
make dev
make migrate
make api
make worker
make health
make smoke
```

Final `main` commit SHA, CI onboarding run URL, compose config validation result,
migration proof, API health proof, worker/broker proof, Celery task round-trip
proof, worker DB access proof, external DB/broker rejection proof, and smoke
proof result must be populated from the protected-branch run before this record
can declare `M1_PASS`.

## Proof Mapping

| Proof | Mechanism |
|---|---|
| Compose config validation result | `docker compose --env-file .env.local -f docker-compose.local.yml config` in CI. |
| Migration proof | `make migrate` runs `alembic upgrade head` in container. |
| API health proof | `make health` requires `/health/ready` HTTP 200. |
| Worker/broker proof | `make smoke` requires `/health/worker` HTTP 200 with `broker=ok` and `worker=ok`. |
| Celery task round-trip proof | `/health/worker` dispatches `app.tasks.health.probe` and observes result backend output. |
| Worker DB access proof | `app.tasks.health.probe` performs safe `SELECT current_user`. |
| External DB/broker rejection proof | `m1_runtime_smoke.py` rejects Neon/RDS/Supabase/non-local DB and broker hosts. |
| Protected truth table safety | Smoke reads `alembic_version` and RLS metadata; it does not mutate financial/event truth tables. |

## OS Prerequisite Notes

Windows requires Docker Desktop with WSL2 and a `make` implementation. macOS
uses Docker Desktop; ARM64 is supported by the selected base images with slower
first builds possible. Linux requires Docker Engine plus Compose v2 and Docker
daemon access.

## Deferred M2/M3/M4/M5/M6

M2: full test-loop safety, DB topology profiles, hardcoded external DB cleanup,
pytest marker taxonomy, append-only-safe test isolation.

M3: CI monolith rationalization and workflow/enforcer registry.

M4: DLQ, RLS/GUC, webhook replay, and Celery diagnosis runbooks.

M5: Bayesian module home and persistence design only.

M6: LLM provider-boundary decomposition/guardrail decision.

## No-Contamination Statement

No B2.4 implementation occurred. No PyMC, PyMC-Marketing, ArviZ, convergence
diagnostics, Bayesian model computation, or model-artifact migrations were
added.

No B2.3 semantics changed. No provider-boundary behavior changed.

## Exit-Gate Table

| Gate | Status | Evidence |
|---|---|---|
| Container-first onboarding authority | PASS pending CI | `DEVELOPMENT.md`, Makefile, Compose. |
| README fidelity | PASS pending CI | Stale backend-placeholder text removed. |
| Canonical local topology | PASS pending CI | `docker-compose.local.yml` declared canonical. |
| Environment authority | PASS pending CI | `.env.local.example` and `.env.example` local-safe defaults. |
| Machine-executed bootstrap | PENDING | M1 workflow must pass on PR and `main`. |
| Migration proof | PENDING | `make migrate` in M1 workflow. |
| API health proof | PENDING | `make health` in M1 workflow. |
| Worker/broker proof | PENDING | `make smoke` in M1 workflow. |
| Worker DB access proof | PENDING | `/health/worker` probe result. |
| Non-vacuous smoke proof | PENDING | `scripts/smoke/m1_runtime_smoke.py`. |
| M1 validator proof | PASS pending CI | `scripts/ci/validate_m1_local_dev_authority.py`. |
| Phase boundary integrity | PASS pending CI | Validator diff-scope checks. |
| Primary branch green | PENDING | Requires merge to `main` and green required checks. |

## Final Verdict

```text
M1_BLOCKED_BY_PRIMARY_BRANCH_NOT_GREEN
```
