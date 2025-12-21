## B0.5.4.1 Soundness Readiness Evidence (Backend Only)

> Scope: soundness remediation only (no frontend). CI artifact pending after push/dispatch.

### 0) Evidence Pack Header

**0.1 Repo identity (current)**
```
$ git rev-parse HEAD
afc639ee0e1e9b07b9757d69826aa06f5f24c0ac

$ git status -sb
## b0540-zero-drift-v3-proofpack

$ git log -1 --oneline
afc639e Update soundness evidence with clean state and actions
```

**0.2 Environment baseline**
```
$ python --version
Python 3.11.9

$ pip --version
pip 24.0 from C:\Python311\Lib\site-packages\pip (python 3.11)
```

**0.3 DB connection proof (local)**
```
$ psql -U app_user -d skeldir_validation -c "SELECT current_database(), current_user, inet_server_addr(), inet_server_port();"
  current_database  | current_user | inet_server_addr | inet_server_port 
--------------------+--------------+------------------+------------------
 skeldir_validation | app_user     | ::1              |             5432
```

---

## 1) Hypotheses → Evidence → Adjudication

### H-REPO-01 — Repo state reproducible
- Working tree is clean at commit `afc639e...`; evidence updated accordingly.
- **Adjudication:** REFUTED (clean).

### H-MIG-01 — Non-empty DB upgrades deterministically to head
- Migration touching `idempotency_key`: `alembic/versions/003_data_governance/202511151410_realign_attribution_events.py` (adds column, backfills, then SET NOT NULL). Amended to disable/enable RLS around backfill.
- Scratch repro (post-fix):
  ```
  $ psql -U postgres -c "DROP DATABASE IF EXISTS skeldir_migprobe; CREATE DATABASE skeldir_migprobe OWNER app_user;"
  $ DATABASE_URL=postgresql://app_user@localhost:5432/skeldir_migprobe alembic upgrade 202511151400
  $ psql -U app_user -d skeldir_migprobe -v ON_ERROR_STOP=1 -c "SET app.current_tenant_id='11111111-1111-1111-1111-111111111111'; INSERT INTO tenants (...); INSERT INTO attribution_events (...revenue_cents=0, raw_payload='{}');"
  $ DATABASE_URL=postgresql://app_user@localhost:5432/skeldir_migprobe alembic upgrade head
  ... (completes to 202512201000)
  $ DATABASE_URL=postgresql://app_user@localhost:5432/skeldir_migprobe alembic current
  202512201000 (head)
  $ psql -U app_user -d skeldir_migprobe -c "SELECT version_num FROM alembic_version; SELECT COUNT(*) AS null_idempotency_key FROM attribution_events WHERE idempotency_key IS NULL; SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='attribution_events';"
   version_num  
  --------------
   202512201000
   null_idempotency_key 
  ----------------------
                      0
   relrowsecurity | relforcerowsecurity 
  ----------------+---------------------
   t              | t
  ```
- **Adjudication:** CONFIRMED (prior failure) → RESOLVED by RLS disable/enable in migration; upgrade succeeds on non-empty DB and RLS is re-enabled.

### H-MV-01 — Canonical matview inventory exists and refreshable as app_user
```
$ psql -U app_user -d skeldir_validation -c "SELECT schemaname, matviewname FROM pg_matviews WHERE schemaname='public' ORDER BY 2;"
 public | mv_allocation_summary
 public | mv_channel_performance
 public | mv_daily_revenue_summary
 public | mv_realtime_revenue
 public | mv_reconciliation_status

$ psql -U app_user -d skeldir_validation -c "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public' AND tablename IN ('mv_allocation_summary','mv_channel_performance','mv_daily_revenue_summary','mv_realtime_revenue','mv_reconciliation_status') ORDER BY 1;"
... idx_mv_* (all UNIQUE across the 5)

$ psql -U app_user -d skeldir_validation -c "REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_realtime_revenue; REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_allocation_summary;"
REFRESH MATERIALIZED VIEW
REFRESH MATERIALIZED VIEW
```
- **Adjudication:** REFUTED (no drift); canonical 5 present and refreshable as app_user.

### H-INJ-01 / H-QUAL-01 — Refresh executor injection/schema safety
- Executor: `backend/app/tasks/maintenance.py`
  - `_qualified_matview_identifier` → `public.<quoted_view>` using `IdentifierPreparer`.
  - `_refresh_view` executes `text("REFRESH MATERIALIZED VIEW CONCURRENTLY " + qualified_view)` after registry validation.
- Ripgrep checks:
  ```
  $ rg -n 'text\(f"REFRESH MATERIALIZED VIEW' backend   # no matches
  $ rg -n 'REFRESH MATERIALIZED VIEW.*\{.*\}' backend   # no matches
  ```
- Tests:
  ```
  $ cd backend && DATABASE_URL=postgresql://app_user@localhost:5432/skeldir_validation pytest -q tests/test_matview_refresh_validation.py
  ... 6 passed ... (malicious strings and schema-qualified attempts rejected; public prefix asserted)
  ```
- **Adjudication:** REFUTED (injection surface removed; schema-qualified, registry-enforced).

### H-LOCK-01 — Serialization semantics
- Lock key derivation: `backend/app/core/pg_locks.py` uses `lock_str = f"matview_refresh:{view_name}:{tenant_str}"`; tenant_str="GLOBAL" when tenant_id is None.
- Current refresh tasks are global (tenant_id=None), so locks are per view globally.
- Concurrency proof:
  ```
  $ DATABASE_URL=postgresql+asyncpg://app_user@localhost:5432/skeldir_validation python backend/test_eg6_serialization.py
  ... one success, one skipped_already_running; lock acquired/skipped/released ...
  ```
- **Adjudication:** REFUTED (locks behave as intended for global refresh; semantics explicitly global).

### H-OBS-01 — Observability live
- Startup command:
  ```
  cd backend &&
  DATABASE_URL=postgresql+asyncpg://app_user@localhost:5432/skeldir_validation \
  CELERY_BROKER_URL=sqla+postgresql://app_user@localhost:5432/skeldir_validation \
  CELERY_RESULT_BACKEND=db+postgresql://app_user@localhost:5432/skeldir_validation \
  uvicorn app.main:app --host 127.0.0.1 --port 8000
  ```
- Outputs:
  ```
  $ curl -i http://127.0.0.1:8000/health
  HTTP/1.1 200 OK ... {"status":"healthy"}

  $ curl -i http://127.0.0.1:8000/metrics | head
  HTTP/1.1 200 OK
  # HELP python_gc_objects_collected_total Objects collected during gc
  # TYPE python_gc_objects_collected_total counter
  python_gc_objects_collected_total{generation="0"} 444.0
  ...
  ```
- **Adjudication:** REFUTED (observability verified live).

---

## 2) Hard Soundness Exit Gates (current status)

- **GATE-S0 Repo truth sealed:** **PASS** — clean tree at `afc639e...`; evidence recorded.
- **GATE-S1 Migration determinism on non-empty DB:** **PASS** — scratch DB upgrade succeeds; `null_idempotency_key=0`; RLS re-enabled.
- **GATE-S2 Refresh executor hardening:** **PASS** — rg shows no unsafe patterns; tests reject malicious identifiers; schema-qualified executor in place.
- **GATE-S3 Canonical matview contract + refresh privilege:** **PASS** — pg_matviews = canonical 5; unique indexes; refresh as app_user succeeds.
- **GATE-S4 CI truth-layer validation:** **FAIL (pending)** — must trigger CI workflow_dispatch on committed SHA and capture run URL/logs.

---

## 3) Next Required Actions to Exit Soundness Phase
1) Push commit `afc639e...` to `b0540-zero-drift-v3-proofpack`.
2) Trigger CI (`.github/workflows/ci.yml`, zero-drift job) on that commit; capture run URL + log anchors showing registry list, pg_matviews list, equality assertion, refresh proof.
3) Update this evidence file with the CI run URL/log anchors and flip GATE-S4 to PASS.

Only after the above are done is B0.5.4.1 registry work authorized.
