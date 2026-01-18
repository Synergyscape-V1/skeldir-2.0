# B0.5.6 Phase 4: Queue Depth + Max Age from Broker Truth (Read-Only, Cached)

**Date**: 2026-01-18  
**Phase**: B0.5.6.4 — Queue Depth + Max Age Gauges from Broker Truth (Read-Only, Cached)  
**Status**: DRAFT (awaiting acceptance commit + CI run)  
**Acceptance Commit**: pending  
**Acceptance CI Run**: pending  

---

## 1. Objective (Non-Negotiable)

Instrument queue depth + max age gauges derived from broker truth (Postgres SQLAlchemy kombu tables) and expose them only via API `/metrics` as read-only, cached metrics that cannot become a DB DoS vector.

---

## 2. Empirical Validation (V1–V4)

### 2.1 V1 — Confirm broker truth + table presence (same DB as API)

**Command (executed from `backend/`, uses API runtime engine):**
```powershell
cd backend
@'
import asyncio
from sqlalchemy import text
from app.db.session import engine

async def main():
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT to_regclass('public.kombu_queue') AS kombu_queue, to_regclass('public.kombu_message') AS kombu_message;"))
        print(res.first())
        res = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='kombu_message' ORDER BY column_name;"))
        cols = [r[0] for r in res.fetchall()]
        print(cols)

asyncio.run(main())
'@ | python -
```

**Output:**
```
('kombu_queue', 'kombu_message')
['id', 'payload', 'queue_id', 'timestamp', 'version', 'visible']
```

### 2.2 V2 — Confirm canonical depth + age SQL works (read-only)

**Command (depth + max-age from Phase0 evidence, verbatim, plus backlog-visible variant):**
```powershell
cd backend
@'
import asyncio
from sqlalchemy import text
from app.db.session import engine

DEPTH_SQL = """\
SELECT
    q.name AS queue_name,
    SUM(CASE WHEN m.visible THEN 1 ELSE 0 END) AS visible_count,
    SUM(CASE WHEN NOT m.visible THEN 1 ELSE 0 END) AS invisible_count,
    COUNT(*) AS total
FROM kombu_queue q
LEFT JOIN kombu_message m ON m.queue_id = q.id
WHERE q.name NOT LIKE '%.reply.celery.pidbox'
GROUP BY q.name
ORDER BY q.name;
"""

MAX_AGE_SQL = """\
SELECT
    q.name AS queue_name,
    MIN(m.timestamp) AS oldest_message,
    EXTRACT(EPOCH FROM (NOW() - MIN(m.timestamp))) AS max_age_seconds
FROM kombu_queue q
LEFT JOIN kombu_message m ON m.queue_id = q.id
WHERE m.timestamp IS NOT NULL
  AND q.name NOT LIKE '%.reply.celery.pidbox'
GROUP BY q.name
ORDER BY q.name;
"""

VISIBLE_MAX_AGE_SQL = """\
SELECT
    q.name AS queue_name,
    MIN(m.timestamp) FILTER (WHERE m.visible) AS oldest_visible_message,
    COALESCE(EXTRACT(EPOCH FROM (NOW() - MIN(m.timestamp) FILTER (WHERE m.visible))), 0) AS max_age_seconds
FROM kombu_queue q
LEFT JOIN kombu_message m ON m.queue_id = q.id
WHERE q.name NOT LIKE '%.reply.celery.pidbox'
GROUP BY q.name
ORDER BY q.name;
"""

async def main():
    async with engine.connect() as conn:
        print('--- depth_sql')
        res = await conn.execute(text(DEPTH_SQL))
        rows = res.fetchall()
        for r in rows[:20]:
            print(tuple(r))
        print('rows:', len(rows))

        print('--- max_age_sql')
        res = await conn.execute(text(MAX_AGE_SQL))
        rows = res.fetchall()
        for r in rows[:20]:
            print(tuple(r))
        print('rows:', len(rows))

        print('--- visible_max_age_sql')
        res = await conn.execute(text(VISIBLE_MAX_AGE_SQL))
        rows = res.fetchall()
        for r in rows[:20]:
            print(tuple(r))
        print('rows:', len(rows))

asyncio.run(main())
'@ | python -
```

**Output:**
```
--- depth_sql
('attribution', 0, 0, 1)
('housekeeping', 1, 6, 7)
('llm', 0, 0, 1)
('maintenance', 0, 612, 612)
rows: 4
--- max_age_sql
('housekeeping', datetime.datetime(2026, 1, 16, 16, 53, 27, 348091), Decimal('162133.809047'))
('maintenance', datetime.datetime(2026, 1, 16, 16, 22, 30, 733660), Decimal('163990.423478'))
rows: 2
--- visible_max_age_sql
('attribution', None, Decimal('0'))
('housekeeping', None, Decimal('0'))
('llm', None, Decimal('0'))
('maintenance', None, Decimal('0'))
rows: 4
```

### 2.3 V3 — Locate queue constants (closed set)

**Command:**
```powershell
rg -n "QUEUE|queue_name|CELERY_.*QUEUE|kombu_queue" backend/app | Select-Object -First 80
```

**Output (excerpt):**
```
backend/app/core/queues.py:9:QUEUE_HOUSEKEEPING = "housekeeping"
backend/app/core/queues.py:10:QUEUE_MAINTENANCE = "maintenance"
backend/app/core/queues.py:11:QUEUE_LLM = "llm"
backend/app/core/queues.py:12:QUEUE_ATTRIBUTION = "attribution"
backend/app/core/queues.py:15:ALLOWED_QUEUES: frozenset[str] = frozenset({
```

### 2.4 V4 — Confirm current API `/metrics` does not already export these gauges (baseline)

**Command (baseline check before implementation):**
```powershell
cd backend
@'
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app

async def main():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        r = await client.get('/metrics')
        print('status', r.status_code)
        text = r.text
        hits = [line for line in text.splitlines() if any(k in line for k in ['kombu','queue','max_age','depth','celery_queue_'])]
        print('hit_count', len(hits))
        for line in hits[:80]:
            print(line)

asyncio.run(main())
'@ | python -
```

**Output:**
```
status 200
hit_count 0
```

---

## 3. Remediation (R1–R4)

### 3.1 Read-only broker stats fetcher + cache (R1, R2)

**Implementation:**
- `backend/app/observability/broker_queue_stats.py`
  - SELECT-only query: `_fetch_broker_truth_stats_from_db()`
  - TTL cache + single-flight: `maybe_refresh_broker_queue_stats()` + `_cache_lock` + `_refresh_inflight`
  - Failure behavior: keeps last-good snapshot, increments `celery_queue_stats_refresh_errors_total`

### 3.2 Export via API `/metrics` only (R3)

**Implementation:**
- `backend/app/api/health.py`
  - `/metrics` calls `broker_queue_stats.maybe_refresh_broker_queue_stats()` before generating exposition
  - `_get_metrics_data()` registers the collector for multiprocess registries

### 3.3 Bounded label policy (R4)

**Implementation:**
- `backend/app/observability/metrics_policy.py`
  - `ALLOWED_LABEL_KEYS` extended with `state`
  - `ALLOWED_QUEUE_STATES` + `normalize_queue_state()`
  - `compute_series_budget()` extended with queue/state dimensions and celery_queue family budget

---

## 4. Enforcement (R5)

### 4.1 Caching + safety tests

**Tests added:**
- `backend/tests/test_b0564_queue_depth_max_age_broker_truth.py`
  - Sequential burst scrapes → ≤ 1 refresh call (patched DB fetch)
  - Concurrent scrapes share a single in-flight refresh
  - Refresh failures keep last-good metrics and increment error counter

### 4.2 Metrics hardening tests updated (boundedness)

**Updated:**
- `backend/tests/test_b0563_metrics_hardening.py`
  - Recognizes `celery_queue_` as an application metric prefix
  - Enforces `state` label boundedness
  - Asserts new metric families exist in exposition

**Local test run (targeted):**
```
pytest -q tests/test_b0563_metrics_hardening.py tests/test_b0564_queue_depth_max_age_broker_truth.py
...
====================== 20 passed, 129 warnings in 1.17s =======================
```

---

## 5. Ledger Closure (EG4.6)

Pending: update `docs/forensics/INDEX.md` with the authoritative Phase 4 row (acceptance commit + CI run) once CI adjudicates.

