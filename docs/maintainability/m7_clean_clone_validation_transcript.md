# M7 Clean-Clone Validation Transcript

## Coordinate

| Field | Value |
| --- | --- |
| validation_time | 2026-05-19T12:21:07-05:00 |
| worktree | `C:\Users\ayewhy\skeldir_m7_main` |
| branch | `codex/m7-b24-readiness` |
| base | `origin/main` |
| base_sha | `668fb9867ab973023b8ed4b417a5dcf51489146e` |

## Clean Worktree Proof

Command:

```text
git status --short
git rev-parse HEAD
git branch --show-current
git log -1 --oneline
```

Observed result:

```text
git status --short returned no tracked or untracked changes before M7 edits.
HEAD: 668fb9867ab973023b8ed4b417a5dcf51489146e
branch: codex/m7-b24-readiness
last commit: 668fb9867 Register M6 proof pack surface in M1
```

## Canonical Startup Path

Static validation command:

```text
python scripts/ci/validate_m1_local_dev_authority.py --local-dev
```

Observed result:

```text
VERDICT: M1_STATIC_VALID
```

The validator confirmed `DEVELOPMENT.md`, root README, backend README, `.env.example`, `.env.local.example`, `docker-compose.local.yml`, Makefile targets, M1 workflow wiring, local-safe DB/Celery URLs, API health proof language, worker/broker proof language, Celery task round-trip proof language, and external DB/broker rejection proof language.

Host-local startup attempt:

```text
if (!(Test-Path -LiteralPath '.env.local')) { Copy-Item -LiteralPath '.env.local.example' -Destination '.env.local' }
docker compose --env-file .env.local -f docker-compose.local.yml config --quiet
docker compose --env-file .env.local -f docker-compose.local.yml up -d postgres
```

Observed result:

```text
docker compose config: exit 0
docker compose up postgres: exit 1
error during connect: open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified
```

M7 classification: host Docker daemon unavailable. This is not treated as repository startup failure because the compose configuration validated and M1 is CI-wired. Authoritative protected-branch validation remains the M1 workflow plus the B2.4 dry-run lane.

## Migration Authority

Documented command:

```text
make migrate
```

Command target:

```text
migrate: docker compose --env-file .env.local -f docker-compose.local.yml run --rm migrate
```

Static proof:

```text
python scripts/ci/validate_m1_local_dev_authority.py --local-dev
```

Observed result:

```text
VERDICT: M1_STATIC_VALID
```

M7 classification: migration path is canonical and container-first; local runtime execution on this host is blocked by Docker daemon availability, not by repo configuration.

## API Health And Worker Startup Authority

Documented commands:

```text
make api
make worker
make health
make smoke
```

The M1 validator confirmed these targets are present, container-first, and wired into `.github/workflows/m1-local-dev-authority.yml`.
