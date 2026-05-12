# Skeldir Local Development Authority

The canonical path is container-first. Host-native Python execution is noncanonical.

M1 successor onboarding uses one topology:

```text
host machine
-> Makefile target
-> docker-compose.local.yml
-> backend API/worker containers
-> local Postgres container used for app DB, Celery broker, and Celery result backend
```

Skeldir remains Postgres-only. There is no alternate broker service; Celery uses
Kombu SQLAlchemy transport and the Celery DB result backend against local
Postgres.

## Host Prerequisites

Install only:

- Git
- Docker Engine or Docker Desktop
- Docker Compose v2 (`docker compose version`)
- `make`

Windows: use Docker Desktop with WSL2 enabled. `make` from Git for Windows,
Chocolatey, Scoop, or WSL is acceptable. Run commands from a shell that can
execute Makefile recipes.

macOS: Docker Desktop is the expected path. On Apple Silicon/ARM64, the
`postgres:15-alpine` and `python:3.11-slim` images are multi-arch; first build
may be slower.

Linux: Docker Engine with the Compose plugin is sufficient. Add your user to the
`docker` group or run from a shell with Docker privileges.

## Branch Assumption

Start from the branch under review or from a clean clone of `main`.

```bash
git status --short
```

The runtime path must not depend on host Python, host Poetry, host `uv`, host
Postgres, host broker services, or previous local database state.

## Environment File

Create the local env file:

```bash
cp .env.local.example .env.local
```

The committed local template uses only local container hosts:

- `DATABASE_URL=postgresql+asyncpg://...@postgres:5432/skeldir_local`
- `MIGRATION_DATABASE_URL=postgresql://...@postgres:5432/skeldir_local`
- `CELERY_BROKER_URL=sqla+postgresql://...@postgres:5432/skeldir_local`
- `CELERY_RESULT_BACKEND=db+postgresql://...@postgres:5432/skeldir_local`

Do not put Neon, RDS, Supabase, or other external DB/broker URLs in `.env.local`
for the canonical path. `make smoke` rejects external DB/broker hosts.

## Command Surface

Start local Postgres:

```bash
make dev
```

Apply migrations:

```bash
make migrate
```

Start the API:

```bash
make api
```

Start a worker:

```bash
make worker
```

Verify API readiness, including DB/RLS/GUC readiness:

```bash
make health
```

Run the M1 non-vacuous smoke proof:

```bash
make smoke
```

Run the bounded maintainability validator set:

```bash
make test
```

`make test` does not claim full test-loop authority before M2. It runs M0/M1
governance validators in containers. M2 owns full test feedback-loop safety,
DB topology profiles, pytest marker taxonomy, hardcoded external DB cleanup,
and append-only-safe test isolation.

Show API/worker logs:

```bash
make logs
```

Stop containers:

```bash
make down
```

## Smoke Boundary

`make smoke` fails unless all of the following hold:

- local DB URLs are present and point to `postgres`, `localhost`, `127.0.0.1`, or `::1`;
- external DB/broker hosts such as Neon/RDS/Supabase are rejected;
- local Postgres accepts `SELECT 1`;
- Alembic has applied at least one head into `alembic_version`;
- `attribution_events` exists with RLS and force RLS enabled;
- `/health/ready` returns HTTP 200;
- `/health/worker` returns HTTP 200 after a real Celery task is serialized,
  brokered through Postgres, executed by the worker, stored in the result
  backend, and observed by the API;
- the worker task proves DB access with a safe `SELECT current_user`.

The smoke path does not write to `attribution_events` or protected financial
truth tables.

## Port Collisions

Defaults:

- API: host `8000` -> container `8000`
- Postgres: host `5432` -> container `5432`

If a port is in use, edit `.env.local`:

This is the port collision handling path for M1.

```bash
API_PORT=8010
POSTGRES_PORT=55432
```

Container-to-container URLs stay unchanged because the canonical topology uses
the Compose service host `postgres`.

## Deferred Work

M2: test feedback-loop authority, hardcoded external DB test cleanup, DB
topology profiles, pytest marker taxonomy, append-only-safe test isolation, and
clearer import-time test diagnostics.

M3: CI monolith rationalization, workflow/enforcer registry, and CI insertion
strategy.

M4: operational runbooks for DLQ, RLS/GUC inspection, webhook replay, and Celery
diagnosis.

M5: B2.4 Bayesian module-home and persistence design only. No PyMC,
PyMC-Marketing, ArviZ, convergence diagnostics, or model-artifact migrations are
implemented in M1.

M6: LLM provider-boundary decomposition or guardrail decision. M1 does not alter
provider-boundary behavior.

## Advanced Noncanonical Host Path

Experienced maintainers may run targeted host-native Python commands for local
debugging, but that path is not successor-authoritative and is not what CI uses
for M1. If host-native commands disagree with the Docker Compose path, the
Docker Compose path is authoritative for onboarding.
