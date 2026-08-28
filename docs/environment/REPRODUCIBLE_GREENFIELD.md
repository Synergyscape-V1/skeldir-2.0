# Reproducible Greenfield Environment

**A deterministic greenfield environment exists.** Following this document on a clean
machine produces a validated Skeldir development environment. If you follow it exactly
and still hit an environmental failure, you have found a defect in this spec - fix the
spec, do not work around it locally.

- **Last verified:** 2026-08-28
- **Verified against main SHA:** 9113ecf64fcbb38c4e3ef328da3db28c3cf4c00f
- **Verified Alembic head:** 202608271200 (30 revisions, 118 tables)

---

## 1. Prerequisites

| Component | Version verified | Notes |
|---|---|---|
| Docker Engine | any current | Required. Postgres runs in a container, never on the host. |
| Python | 3.11 | What CI uses. See section 6 for the Windows constraint. |
| Node | 22+ (v25.0.0 verified) | Frontend/marketing only. Not needed for backend work. |
| Git | any current | On Windows, Git Bash. See section 6 for the /tmp caveat. |
| oasdiff | v1.11.7 | Not installed by default. Install with: go install github.com/oasdiff/oasdiff@v1.11.7 -- Windows devs may instead rely on the vendored tools/oasdiff/oasdiff.exe, which scripts/contracts/validate-contracts.sh:72 prepends to PATH when present. |

## 2. One-command bootstrap

    bash scripts/environment/bootstrap_greenfield.sh

Idempotent. Safe to re-run. Creates the container if absent, reuses it if present,
re-runs migrations to head, and prints a verification block. Exits non-zero on any
failed verification.

## 3. Manual sequence (what the script does)

### 3.1 Postgres

    docker run -d --name skeldir-dev-pg \
      -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=postgres \
      -p 127.0.0.1:55432:5432 postgres:15-alpine

postgres:15-alpine is authoritative. Postgres 15 is what CI and every migration replay
use; a Postgres 16 data directory will not start under a 15 binary.

### 3.2 Authority boundary BEFORE migration

Ordering is load-bearing and is the single most common failure. Running
alembic upgrade head first produces a database with RLS reading disabled and the
runtime roles absent, which looks like a security regression and is not one.

    python scripts/database/prepare_migration_authority_boundary.py \
      --admin-dsn postgresql://postgres:postgres@127.0.0.1:55432/postgres \
      --database-name skeldir_dev

Creates app_user, app_worker, app_dispatch_publisher, migration_owner, app_rw, app_ro.
Expect authority_monotonic=true. Privilege reduction is a ratchet: re-provisioning can
never restore authority a migration removed, because the script reads the revision
graph rather than live privilege.

### 3.3 Migrate

    cd <repo-root>          # NOT backend/ -- alembic.ini lives at the repo root
    DATABASE_URL=postgresql://migration_owner:migration_owner@127.0.0.1:55432/skeldir_dev \
    MIGRATION_DATABASE_URL=$DATABASE_URL \
    python -m alembic upgrade head

Running from backend/ fails with: No 'script_location' key found in configuration.

### 3.4 Backend dependencies

    pip install -r backend/requirements-dev.txt        # includes requirements.txt
    pip install -r backend/requirements-bayesian.txt   # PyMC lane, needs a C++ toolchain

Five manifests exist and all are consumed by CI: requirements.txt, -dev.txt,
-bayesian.txt, -science.txt, -lock.txt (hash-pinned by r0-preflight-validation.yml,
which fails closed if absent).

### 3.5 Frontend / marketing

    cd marketing && npm ci     # live production site (Netlify) - never modified by backend work
    cd frontend  && npm ci

## 4. Verification

    docker exec skeldir-dev-pg psql -U postgres -d skeldir_dev -Atc \
      "SELECT version_num FROM alembic_version"
    # -> 202608271200

    docker exec skeldir-dev-pg psql -U postgres -d skeldir_dev -At -F'|' -c \
      "SELECT rolname,rolsuper,rolbypassrls FROM pg_roles WHERE rolname IN
       ('app_user','app_worker','app_dispatch_publisher','migration_owner','app_rw','app_ro')"
    # -> six rows, every rolsuper and rolbypassrls = f

    docker exec skeldir-dev-pg psql -U postgres -d skeldir_dev -At -F'|' -c \
      "SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname IN
       ('b23_match_verdicts','bayesian_model_fits','bayesian_artifacts')"
    # -> three rows, all t|t

    PYTHONPATH="$PWD;$PWD/backend" python -c "from app.main import app; print(len(app.routes))"
    # -> 72

    DATABASE_URL=postgresql://app_user:app_user@127.0.0.1:55432/skeldir_dev \
      python -m pytest backend/tests/trust -q
    # -> 314 passed, 73 skipped

The 73 skips are opt-in PostgreSQL tests, not failures.

## 5. Environment variables

| Variable | Default used above | Consumed by |
|---|---|---|
| DATABASE_URL | postgresql://app_user:app_user@127.0.0.1:55432/skeldir_dev | app + tests |
| MIGRATION_DATABASE_URL | postgresql://migration_owner:migration_owner@... | alembic |
| B24_DISPATCH_PUBLISHER_DATABASE_URL | postgresql://app_dispatch_publisher:... | dispatch publisher |
| SKELDIR_B25_P13_E2E_PROOF | 1 | opts into the P13 end-to-end proof |
| PYTHONPATH | <repo>;<repo>/backend | all local runs |

146 further variables are read by code but declared in no manifest (no .env.example,
no compose file, no workflow env: block). They fall back to defaults. Production-path
examples: B15_INVESTIGATION_MIN_HOLD_SECONDS, B24_BAYESIAN_CPU_BUDGET,
B24_BAYESIAN_WORKSPACE_ROOT, B24_PYTENSOR_COMPILEDIR, ATTRIBUTION_STRATEGY_BATCH_EVENTS.
Treat this as known configuration debt: what runs is not fully described by any
declared surface.

## 6. Platform constraints

**Windows: uvloop has no wheel and refuses to build.** Installing
backend/requirements-lock.txt fails with:
RuntimeError: uvloop does not support Windows at the moment.
Use requirements-dev.txt + requirements-bayesian.txt for local work, or run the full
lock inside Linux:

    docker run -d --name skeldir-dev-py -v "<repo>:/repo:ro" python:3.11-slim sleep infinity
    docker exec skeldir-dev-py sh -c 'apt-get update -qq && apt-get install -y -qq build-essential g++'

build-essential and g++ are required by the PyTensor C backend.

**Git Bash /tmp is not visible to Windows Python.** Writing a file to /tmp from Bash
and reading it from python raises FileNotFoundError. Use a Windows-form path for
anything crossing that boundary.

**Docker volume mounts from Git Bash need MSYS_NO_PATHCONV=1**, otherwise the
container-side path is rewritten and the mount silently misbehaves.

## 7. Gates: local vs CI

Runs locally, no extra credentials: B0.4/B0.6 phase gates; B2.1-B2.4 validators; all
backend/tests/trust (B2.5-P1 through P14); validate_b25_p13_c13_closure and
_c14_closure including --negative-control; migration and role/RLS checks; backend import.

Requires pushed-branch CI:

| Gate | Why |
|---|---|
| B0.1 / B0.2 / B0.3 | Need oasdiff on PATH and running Prism mock servers. These fail identically on pristine main locally - environmental, not a regression. |
| B1.1-B1.7 (incl. B1.4 / B1.6 CloudTrail) | Authenticate via OIDC role arn:aws:iam::326730685463:role/skeldir-ci-deploy, region us-east-2. No static AWS keys - never introduce one; scripts/security/b11_p6_repo_secret_scan.py matches AKIA[0-9A-Z]{16} and will catch it. |
| ci.yml, b2_5-p13-e2e-trust-closure.yml | GitHub-runner hosted. |
| M0 / M1 scope locks | Diff semantics differ locally: the validator diffs M0_BASELINE_SHA to local HEAD and sweeps in every commit since the baseline, producing false violations. CI is authoritative. |

## 8. Known-good reference points

- Alembic head 202608271200, 118 tables
- Trust suite: 314 passed / 73 skipped
- Backend: 72 routes
- Six runtime roles, none superuser, none BYPASSRLS
- relrowsecurity AND relforcerowsecurity on b23_match_verdicts, bayesian_model_fits,
  bayesian_artifacts
- H-A1 / H-A2 / H-A4 falsifiers all REFUSED with issuance_capability_required
