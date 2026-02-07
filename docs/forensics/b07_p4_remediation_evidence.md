# B0.7-P4 Remediation Evidence (E2E Integration + Operational Closure)

Status: implemented in code, awaiting canonical CI run on `main` for immutable run URLs.

## Implemented CI Gate
- Workflow: `.github/workflows/b07-p4-e2e-operational-readiness.yml`
- Trigger: `push` to `main`, `pull_request` to `main`, `workflow_dispatch`
- Runtime topology: `docker-compose.e2e.yml` (Postgres + mock + API + worker)
- Migration step: `python -m alembic upgrade head`
- E2E runtime proof: `pytest -q backend/tests/integration/test_b07_p4_operational_readiness_e2e.py`
- Operational SQL dashboards: `scripts/ci/run_b07_p4_operational_queries.sh`
- Artifact bundle: `artifacts/b07-p4` uploaded as `b07-p4-operational-readiness`

## Implemented E2E Proofs
File: `backend/tests/integration/test_b07_p4_operational_readiness_e2e.py`

Assertions covered:
1. Full chain consumption for each LLM task type (`route`, `explanation`, `investigation`, `budget_optimization`) with persisted `llm_api_calls` evidence.
2. Investigation and budget job materialization.
3. Cache hit path where second identical request is `was_cached=true` and `provider_attempted=false`.
4. Breaker-open fail-fast after repeated provider failures (`blocked_reason=breaker_open`).
5. Kill-switch deny path (`blocked_reason=provider_kill_switch`) with `provider_attempted=false`.
6. Hourly shutoff deny path (manual seeded shutoff row + blocked execution).
7. Idempotency under duplicate delivery (same request id/endpoint yields one `llm_api_calls` row).
8. Distillation capture persistence (reasoning/metadata refs present on provider-backed success rows).
9. Runtime RLS identity checks: wrong tenant/user GUC reads return zero rows.

Runtime evidence emitted:
- `artifacts/b07-p4/runtime_db_probe.json`

## Operational Closure Pack
- `docs/ops/b07_p4/README.md`
- `docs/ops/b07_p4/runbooks/first_traffic_checklist.md`
- `docs/ops/b07_p4/runbooks/kill_switch_runbook.md`
- `docs/ops/b07_p4/runbooks/incident_response_runbook.md`
- `docs/ops/b07_p4/sql/01_monthly_spend.sql`
- `docs/ops/b07_p4/sql/02_cache_hit_rate.sql`
- `docs/ops/b07_p4/sql/03_breaker_shutoff_state.sql`
- `docs/ops/b07_p4/sql/04_provider_cost_latency_distribution.sql`

CI-executed SQL outputs:
- `artifacts/b07-p4/sql/01_monthly_spend.csv`
- `artifacts/b07-p4/sql/02_cache_hit_rate.csv`
- `artifacts/b07-p4/sql/03_breaker_shutoff_state.csv`
- `artifacts/b07-p4/sql/04_provider_cost_latency_distribution.csv`

## CI-like Local Repro
```bash
python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
rm -f .env
docker compose -f docker-compose.e2e.yml up -d --build postgres mock_platform
python -m alembic upgrade head
docker compose -f docker-compose.e2e.yml up -d --build api worker
python scripts/wait_for_e2e_health.py
python scripts/wait_for_e2e_worker.py
PYTHONPATH="$PWD:$PWD/backend" \
DATABASE_URL="postgresql+asyncpg://skeldir:skeldir_e2e@127.0.0.1:5432/skeldir_e2e" \
B07_P4_RUNTIME_DATABASE_URL="postgresql://skeldir:skeldir_e2e@127.0.0.1:5432/skeldir_e2e" \
CELERY_BROKER_URL="sqla+postgresql://skeldir:skeldir_e2e@127.0.0.1:5432/skeldir_e2e" \
CELERY_RESULT_BACKEND="db+postgresql://skeldir:skeldir_e2e@127.0.0.1:5432/skeldir_e2e" \
B07_P4_ARTIFACT_DIR="artifacts/b07-p4" \
pytest -q backend/tests/integration/test_b07_p4_operational_readiness_e2e.py
scripts/ci/run_b07_p4_operational_queries.sh \
  "postgresql://skeldir:skeldir_e2e@127.0.0.1:5432/skeldir_e2e" \
  "artifacts/b07-p4/runtime_db_probe.json" \
  "artifacts/b07-p4/sql"
docker compose -f docker-compose.e2e.yml down -v
```
