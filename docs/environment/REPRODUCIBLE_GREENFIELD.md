# Reproducible Greenfield Environment

**A deterministic greenfield environment exists, and it is already sanctioned in this
repository.** This document does not introduce a second one. It names the canonical
path and records the environmental constraints that are otherwise rediscovered the
hard way.

If you follow this document on a clean machine and still hit an environmental
failure, you have found a defect in this spec. Fix the spec; do not work around it
locally.

- **Last verified:** 2026-08-28
- **Verified against main SHA:** 9113ecf64fcbb38c4e3ef328da3db28c3cf4c00f
- **Verified Alembic head:** 202608271200 (118 tables)

---

## 1. Canonical bootstrap (use this)

    bash scripts/ci/run_m1_onboarding_bootstrap.sh

This is the sanctioned entry point, allowlisted in `scripts/guard_no_docker.py`. It
copies `.env.local.example` to `.env.local` if absent, validates
`docker-compose.local.yml`, then runs:

    make dev       # canonical local Postgres (Celery broker/result backend is Postgres-backed)
    make migrate   # Alembic head inside the backend container
    make api       # FastAPI through Compose
    make worker    # Celery worker through Compose
    make health    # readiness endpoint from inside the API container
    make smoke     # non-vacuous M1 runtime smoke proof

`make down` stops the topology; `make logs` tails API and worker.

**Do not write a parallel bootstrap script.** The Zero Docker Doctrine
(`scripts/guard_no_docker.py`) forbids Docker references across `.github`,
`api-contracts`, `alembic`, `backend`, `db`, `scripts`, and `tests`, with a narrow
`ALLOWED_DOCKER_PATHS` allowlist. A new Docker-bearing script under `scripts/` fails
the `Zero Container Doctrine` job in `ci.yml`. Adding yourself to the allowlist to
pass your own gate is self-sanctioning — extend the canonical topology instead.

## 2. Prerequisites

| Component | Verified | Notes |
|---|---|---|
| Docker Engine + Compose v2 | any current | Canonical topology is Compose-based. |
| Python | 3.11 | What CI uses. See section 5 for the Windows constraint. |
| Node | 22+ (v25.0.0 verified) | Frontend/marketing only. |
| GNU Make | any current | `make` targets are the canonical interface. **Not present by default on Windows** (verified absent on a stock Windows + Git Bash host). Install via Chocolatey (`choco install make`), MSYS2, or WSL, or invoke the underlying `docker compose` commands from the Makefile directly. |
| oasdiff | v1.11.7 | Not installed by default: `go install github.com/oasdiff/oasdiff@v1.11.7`. Windows devs may rely on the vendored `tools/oasdiff/oasdiff.exe`, which `scripts/contracts/validate-contracts.sh:72` prepends to PATH when present. |

### 1.1 Verified topology facts

`docker compose --env-file .env.local -f docker-compose.local.yml config` validates cleanly and
declares six services: `postgres`, `migrate`, `worker`, `api`, `smoke`, `validator`. Postgres is
pinned to `postgres:15-alpine` at `docker-compose.local.yml:6`.

## 3. Manual path (when you need a bare database, not the full topology)

Useful for running the trust suite or a migration replay without the API/worker.

### 3.1 Ordering is load-bearing

`prepare_migration_authority_boundary.py` MUST run before `alembic upgrade head`.
Reversing the order produces a database with RLS reading disabled and the runtime
roles absent. That looks like a security regression and is not one. CI enforces the
correct order (`b2_5-p13-e2e-trust-closure.yml`, bootstrap step before migrate step).

    python scripts/database/prepare_migration_authority_boundary.py \
      --admin-dsn postgresql://postgres:postgres@127.0.0.1:<port>/postgres \
      --database-name skeldir_dev

Creates `app_user`, `app_worker`, `app_dispatch_publisher`, `migration_owner`,
`app_rw`, `app_ro`. Expect `authority_monotonic=true`. Privilege reduction is a
ratchet: re-provisioning can never restore authority a migration removed, because the
script reads the revision graph rather than live privilege.

### 3.2 Migrate from the repo root

    cd <repo-root>          # NOT backend/ -- alembic.ini lives at the repo root
    DATABASE_URL=postgresql://migration_owner:migration_owner@127.0.0.1:<port>/skeldir_dev \
    MIGRATION_DATABASE_URL=$DATABASE_URL \
    python -m alembic upgrade head

From `backend/` this fails with: `No 'script_location' key found in configuration`.

### 3.3 Postgres 15 is authoritative

Every migration replay and CI job uses Postgres 15. A Postgres 16 data directory will
not start under a 15 binary; mixing them wastes a debugging cycle.

## 4. Verification (known-good reference points)

    docker exec <pg> psql -U postgres -d skeldir_dev -Atc "SELECT version_num FROM alembic_version"
    # -> 202608271200

    docker exec <pg> psql -U postgres -d skeldir_dev -At -F'|' -c \
      "SELECT rolname,rolsuper,rolbypassrls FROM pg_roles WHERE rolname IN
       ('app_user','app_worker','app_dispatch_publisher','migration_owner','app_rw','app_ro')"
    # -> six rows, every rolsuper and rolbypassrls = f

    docker exec <pg> psql -U postgres -d skeldir_dev -At -F'|' -c \
      "SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname IN
       ('b23_match_verdicts','bayesian_model_fits','bayesian_artifacts')"
    # -> three rows, all t|t

    python -c "from app.main import app; print(len(app.routes))"      # -> 72
    python -m pytest backend/tests/trust -q                            # -> 314 passed, 73 skipped

The 73 skips are opt-in PostgreSQL tests, not failures.

Signing-boundary reference: the H-A1 (false revenue), H-A2 (foreign tenant), and
H-A4 (downgrade with stripped provenance) falsifiers must all be REFUSED with
`issuance_capability_required`. Any other outcome is a P13 regression.

## 5. Platform constraints

**Windows: uvloop has no wheel and refuses to build.** Installing
`backend/requirements-lock.txt` natively fails with
`RuntimeError: uvloop does not support Windows at the moment`. Use the canonical
Compose topology, or `requirements-dev.txt` + `requirements-bayesian.txt` for
host-side work. For the full lock, use Linux with `build-essential` and `g++`
present (required by the PyTensor C backend).

**Git Bash `/tmp` is not visible to Windows Python.** Writing a file to `/tmp` from
Bash and reading it from `python` raises `FileNotFoundError`. Use a native path
(`cygpath -m`) for anything crossing that boundary.

**Docker CLI invocations from Git Bash need `MSYS_NO_PATHCONV=1`**, otherwise
container-side paths are rewritten and mounts silently misbehave.

## 6. Environment variables

Canonical values live in `.env.local.example`, copied to `.env.local` by the
bootstrap. For the manual path:

| Variable | Consumed by |
|---|---|
| `DATABASE_URL` | app + tests |
| `MIGRATION_DATABASE_URL` | alembic |
| `B24_DISPATCH_PUBLISHER_DATABASE_URL` | dispatch publisher |
| `SKELDIR_B25_P13_E2E_PROOF=1` | opts into the P13 end-to-end proof |
| `PYTHONPATH` | `<repo>;<repo>/backend` (native path form on Windows) |

**146 further variables are read by code but declared in no manifest** — no
`.env.local.example` entry, no compose file, no workflow `env:` block. They fall back
to defaults. Production-path examples: `B15_INVESTIGATION_MIN_HOLD_SECONDS`,
`B24_BAYESIAN_CPU_BUDGET`, `B24_BAYESIAN_WORKSPACE_ROOT`, `B24_PYTENSOR_COMPILEDIR`,
`ATTRIBUTION_STRATEGY_BATCH_EVENTS`. Known configuration debt: what runs is not fully
described by any declared surface.

## 7. Which gates run locally, which need CI

**Local, no extra credentials:** B0.4 / B0.6 phase gates; B2.1–B2.4 validators; the
full `backend/tests/trust` suite (B2.5-P1 → P14); `validate_b25_p13_c13_closure` and
`_c14_closure` including `--negative-control`; migration, role, and RLS checks;
backend import.

**Requires pushed-branch CI:**

| Gate | Why |
|---|---|
| B0.1 / B0.2 / B0.3 | Need `oasdiff` on PATH and running Prism mock servers. These fail identically on pristine main locally — environmental, not a regression. |
| B1.1–B1.7, incl. B1.4 / B1.6 CloudTrail | Authenticate via OIDC role `arn:aws:iam::326730685463:role/skeldir-ci-deploy`, region `us-east-2`. **Never introduce a static AWS key**: `scripts/security/b11_p6_repo_secret_scan.py` matches `AKIA[0-9A-Z]{16}` and will catch it. |
| `ci.yml`, `b2_5-p13-e2e-trust-closure.yml` | GitHub-runner hosted. |
| M0 / M1 scope locks | Run locally, the validator diffs `M0_BASELINE_SHA` → local HEAD and sweeps in every commit since the baseline, producing false violations. **CI is authoritative.** Recorded because this exact mistake was made and had to be corrected. |
| Zero Container Doctrine | `scripts/guard_no_docker.py`, run by the `ci.yml` phase-gate jobs. Runs locally too, and is worth running before pushing any new script. |
