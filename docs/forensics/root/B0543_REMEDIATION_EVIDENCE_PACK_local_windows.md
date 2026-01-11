# B0543 Remediation Evidence Pack (Local Windows)

## Repo Identity

```
Branch: fix/b0543-atomic
HEAD: acbdb43
```

## Artifact-to-Commit Mapping (git log --oneline -- <path>)

backend/app/tasks/matviews.py
```
acbdb43 B0543: Celery task layer + failure surfacing (DLQ+metrics+corr)
```

backend/app/observability/metrics.py
```
acbdb43 B0543: Celery task layer + failure surfacing (DLQ+metrics+corr)
772ad79 fix(ci): restore missing app/observability package
```

backend/app/celery_app.py
```
acbdb43 B0543: Celery task layer + failure surfacing (DLQ+metrics+corr)
...
```

.github/workflows/b0543-matview-task-layer.yml
```
acbdb43 B0543: Celery task layer + failure surfacing (DLQ+metrics+corr)
```

scripts/r2/static_audit_allowlist.json
```
be4c182 R2: allowlist R5 probe cleanup
71ea5ee R2: hard-gated runtime innocence w/ DB window capture
```

backend/tests/test_b0543_matview_task_layer.py
```
acbdb43 B0543: Celery task layer + failure surfacing (DLQ+metrics+corr)
```

## Candidate Definition Confirmation

Candidate SHA must be the atomic commit introducing the complete B0543 phase delta (task layer + metrics + registration + tests + workflow). A green CI run on an unrelated SHA is not acceptable. C_atomic = acbdb43.

## CI Evidence (C_atomic)

- CI_RUN_URL: https://github.com/Muk223/skeldir-2.0/actions/runs/20682769852
- CI_JOB_URL: https://github.com/Muk223/skeldir-2.0/actions/runs/20682769852/job/59379192919
- Head SHA: acbdb4335c92371c33de183175b9efd10b5e35c9

## Local Runtime Validation (Self-Contained)

Local Postgres (service already running):

```
psql -U postgres -d postgres -h localhost -c "SELECT 1;"
```

User/database provisioning:

```
psql -U postgres -d postgres -h localhost -c 'DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = ''app_user'') THEN CREATE ROLE app_user LOGIN PASSWORD ''app_user''; END IF; END $$;'
psql -U postgres -d postgres -h localhost -c "ALTER DATABASE skeldir_validation OWNER TO app_user;"
```

Migrations:

```
$env:MIGRATION_DATABASE_URL="postgresql://app_user:app_user@localhost:5432/skeldir_validation"; python -m alembic upgrade head
```

Local test execution:

```
$env:DATABASE_URL="postgresql+asyncpg://app_user:app_user@localhost:5432/skeldir_validation"; $env:TEST_ASYNC_DSN=$env:DATABASE_URL; python -m pytest backend/tests/test_b0543_matview_task_layer.py -q
```

Output (abridged):

```
4 passed in 0.40s
```

## Exit Gate Status (per directive)

- EG-B0543-REM-1 (Topology Forensics Complete): PASS
- EG-B0543-REM-2 (Atomic Candidate Created): PASS (C_atomic = acbdb43)
- EG-B0543-REM-3 (CI Success Verified): PASS (CI run 20682769852, SUCCESS)
- EG-B0543-REM-4 (Docs Closure Done): PENDING (await E_docs_only update)
- EG-B0543-REM-5 (Local Repro Included): PASS (local Postgres + pytest run)
