# B0.7-P4 Remediation Evidence (E2E Integration + Operational Closure)

Status at 2026-02-07 (UTC): implemented and CI-proven on PR branch `b07-p4-closure-pack` (PR `#59`), awaiting merge to `main`.

## Canonical Evidence Links
- PR: https://github.com/Muk223/skeldir-2.0/pull/59
- P4 closure workflow (green): https://github.com/Muk223/skeldir-2.0/actions/runs/21788468203
- P4 closure job (green): https://github.com/Muk223/skeldir-2.0/actions/runs/21788468203/job/62863643995
- Required protection check `B0.7 P2 Runtime Proof (LLM + Redaction)` (green): https://github.com/Muk223/skeldir-2.0/actions/runs/21788468172/job/62863653489
- Required protection check `Celery Foundation B0.5.1` (green): https://github.com/Muk223/skeldir-2.0/actions/runs/21788468172/job/62863653520

## Hypothesis Validation Outcomes
1. H-P4-01 (full-chain E2E missing): **refuted**
- Workflow boots compose substrate, provisions runtime identity, migrates, starts API+worker, runs full-chain pytest, then SQL dashboards.
2. H-P4-02 (vacuous green): **refuted**
- E2E includes explicit negative controls: breaker-open blocking, kill-switch blocking, hourly shutoff blocking, duplicate idempotency, cache-hit provider bypass.
3. H-P4-03 (RLS propagation not proven): **refuted**
- Runtime test asserts wrong user and wrong tenant GUC contexts read zero rows.
4. H-P4-04 (retry/idempotency not proven): **refuted for duplicate delivery idempotency**
- Test dispatches duplicate request_id and asserts single `llm_api_calls` row and stable `api_call_id`.
5. H-P4-05 (closure artifacts not executable): **refuted**
- SQL dashboards execute in CI and are uploaded as artifacts with non-empty outputs and validated headers.

## Exit Gate Evidence
1. Exit Gate 1: Full E2E Distributed Chain: **PASS**
- Task types proven in runtime: `route`, `explanation`, `investigation`, `budget_optimization`.
- Worker consumption persisted in DB (`llm_api_calls` and downstream materializations for investigations and budget jobs).
- Evidence source: `backend/tests/integration/test_b07_p4_operational_readiness_e2e.py`.
2. Exit Gate 2: Operational Query & Ledger Truth: **PASS**
- SQL runner: `scripts/ci/run_b07_p4_operational_queries.sh`.
- Dashboards executed against runtime DB under tenant/user GUC context:
  - `docs/ops/llm_p4/sql/01_monthly_spend.sql`
  - `docs/ops/llm_p4/sql/02_cache_hit_rate.sql`
  - `docs/ops/llm_p4/sql/03_breaker_shutoff_state.sql`
  - `docs/ops/llm_p4/sql/04_provider_cost_latency_distribution.sql`
- Artifact outputs:
  - `artifacts/b07-p4/sql/01_monthly_spend.csv`
  - `artifacts/b07-p4/sql/02_cache_hit_rate.csv`
  - `artifacts/b07-p4/sql/03_breaker_shutoff_state.csv`
  - `artifacts/b07-p4/sql/04_provider_cost_latency_distribution.csv`
3. Exit Gate 3: Kill-Switch + Fail-Safe Control: **PASS**
- E2E asserts kill-switch outcome: `status=blocked`, `blocked_reason=provider_kill_switch`, `provider_attempted=false`, with persisted audit row.

## Non-Vacuous SQL Artifact Snapshot (from run 21788468203)
- `01_monthly_spend.csv`: one row with tenant/user monthly totals (`total_cost_cents=6`, `total_calls=6`).
- `02_cache_hit_rate.csv`: includes `app.tasks.llm.explanation` with `cache_hits=1`.
- `03_breaker_shutoff_state.csv`: includes one breaker row (`state=open`) and one hourly shutoff row (`state_value=true`).
- `04_provider_cost_latency_distribution.csv`: includes provider/model/status aggregation rows with non-zero call counts.

## Implemented Files
- Workflow: `.github/workflows/b07-p4-e2e-operational-readiness.yml`
- Runtime E2E: `backend/tests/integration/test_b07_p4_operational_readiness_e2e.py`
- SQL runner: `scripts/ci/run_b07_p4_operational_queries.sh`
- Provider kill switch support:
  - `backend/app/core/config.py`
  - `backend/app/llm/provider_boundary.py`
- Ops closure pack:
  - `docs/ops/llm_p4/README.md`
  - `docs/ops/llm_p4/runbooks/first_traffic_checklist.md`
  - `docs/ops/llm_p4/runbooks/kill_switch_runbook.md`
  - `docs/ops/llm_p4/runbooks/incident_response_runbook.md`
  - `docs/ops/llm_p4/sql/*.sql`

## CI Commands (Exact)
- Runtime proof:
```bash
pytest -q backend/tests/integration/test_b07_p4_operational_readiness_e2e.py
```
- Dashboard execution:
```bash
scripts/ci/run_b07_p4_operational_queries.sh \
  "${B07_P4_RUNTIME_DATABASE_URL}" \
  "${B07_P4_ARTIFACT_DIR}/runtime_db_probe.json" \
  "${B07_P4_ARTIFACT_DIR}/sql"
```

## CI-like Local Repro
```bash
python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
rm -f .env
docker compose -f docker-compose.e2e.yml up -d --build postgres mock_platform

export MIGRATION_DATABASE_URL="postgresql://skeldir:skeldir_e2e@127.0.0.1:5432/skeldir_e2e"
DATABASE_URL="${MIGRATION_DATABASE_URL}" python -m alembic upgrade head

psql "${MIGRATION_DATABASE_URL}" -v ON_ERROR_STOP=1 <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
    CREATE ROLE app_rw NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ro') THEN
    CREATE ROLE app_ro NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
    CREATE USER app_user WITH PASSWORD 'app_user';
  END IF;
END
$$;
GRANT app_rw TO app_user;
GRANT app_ro TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;
SQL

docker compose -f docker-compose.e2e.yml up -d --build api worker
python scripts/wait_for_e2e_health.py
python scripts/wait_for_e2e_worker.py

export PYTHONPATH="$PWD:$PWD/backend"
export DATABASE_URL="postgresql+asyncpg://app_user:app_user@127.0.0.1:5432/skeldir_e2e"
export B07_P4_RUNTIME_DATABASE_URL="postgresql://app_user:app_user@127.0.0.1:5432/skeldir_e2e"
export CELERY_BROKER_URL="sqla+postgresql://app_user:app_user@127.0.0.1:5432/skeldir_e2e"
export CELERY_RESULT_BACKEND="db+postgresql://app_user:app_user@127.0.0.1:5432/skeldir_e2e"
export B07_P4_ARTIFACT_DIR="artifacts/b07-p4"

pytest -q backend/tests/integration/test_b07_p4_operational_readiness_e2e.py
scripts/ci/run_b07_p4_operational_queries.sh \
  "${B07_P4_RUNTIME_DATABASE_URL}" \
  "artifacts/b07-p4/runtime_db_probe.json" \
  "artifacts/b07-p4/sql"

docker compose -f docker-compose.e2e.yml down -v
```
