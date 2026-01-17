# B0.5.6 Phase 2: Health Semantics Remediation Evidence

**Date**: 2026-01-16  
**Investigator**: Codex (local Windows)  
**Scope**: Health semantics (live/ready/worker), route uniqueness, worker capability probe (data-plane), guardrail enforcement

---

## 1) Before State (Current `main` Re-Verification)

### 1.1 Static route map (grep)
**Command**
```
rg -n "(/health|health/ready|include_router\(health|APIRouter\(|def health|def ready)" backend/app
```

**Output**
```
backend/app\main.py
52:app.include_router(health.router, tags=["Health"])
56:# - /health: Legacy alias for liveness only
57:# - /health/live: Pure liveness (no deps)
58:# - /health/ready: Readiness (DB + RLS + GUC)
59:# - /health/worker: Worker capability (data-plane probe)

backend/app\api\health.py
5:- /health/live: Pure liveness (process responds, no dependency checks)
6:- /health/ready: Readiness (DB + RLS + tenant GUC validation)
7:- /health/worker: Worker capability (data-plane probe via Celery)
9:- /health: Strict liveness only (alias of /health/live)
24:router = APIRouter()
182:@router.get("/health/live")
196:@router.get("/health")
210:@router.get("/health/ready")
281:@router.get("/health/worker")
```

### 1.2 Runtime route truth (OpenAPI)
**Command**
```
curl.exe -s http://127.0.0.1:8001/openapi.json > .tmp/b056_openapi.json
python -c "import json; data=json.load(open('.tmp/b056_openapi.json', encoding='utf-16')); paths=sorted([p for p in data.get('paths',{}) if 'health' in p]); print('\n'.join(paths))"
```

**Output**
```
/health
/health/live
/health/ready
/health/worker
```

### 1.3 `/health` response (route exists?)
**Command**
```
curl.exe -s -i http://127.0.0.1:8001/health
```

**Output**
```
HTTP/1.1 200 OK
content-type: application/json

{"status":"ok"}
```

**Finding**: Hypothesis H-C0.2 (duplicate `/health`) is **falsified** on current `main`. `/health` exists as a strict liveness alias only.

---

## 2) Remediation Summary

Changes applied to restore provenance and align with B0.5.6.2:

- **New worker probe task**: `backend/app/tasks/health.py` defines `app.tasks.health.probe` (data-plane probe).
- **API worker probe wiring**: `backend/app/api/health.py` sends `app.tasks.health.probe` via the broker.
- **Celery registration**: `backend/app/celery_app.py` includes `app.tasks.health` with routing to `housekeeping`.
- **Tests**: `backend/tests/test_b0562_health_semantics.py` updated to expect `app.tasks.health.probe`.

---

## 3) After State Proofs (Exit Gates)

### EG1 — Route Uniqueness Gate
**Command**
```
curl.exe -s http://127.0.0.1:8001/openapi.json > .tmp/b056_openapi.json
python -c "import json; data=json.load(open('.tmp/b056_openapi.json', encoding='utf-16')); paths=sorted([p for p in data.get('paths',{}) if 'health' in p]); print('\n'.join(paths))"
```

**Output**
```
/health
/health/live
/health/ready
/health/worker
```

### EG2 — Liveness Purity Gate
**Command**
```
curl.exe -s -i http://127.0.0.1:8001/health/live
```

**Output**
```
HTTP/1.1 200 OK
content-type: application/json

{"status":"ok"}
```

**Static proof**: `/health/live` implementation does not reference DB/broker/Celery (see `backend/app/api/health.py`).

### EG3 — Readiness Failure Gate
**Command (healthy)**
```
curl.exe -s -i http://127.0.0.1:8001/health/ready
```

**Output**
```
HTTP/1.1 200 OK
content-type: application/json

{"status":"ok","database":"ok","rls":"ok","tenant_guc":"ok"}
```

**Command (invalid DB settings)**
```
$env:DATABASE_URL="postgresql+asyncpg://invalid_user:invalid_pass@127.0.0.1:9/invalid_db"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002
curl.exe -s -i http://127.0.0.1:8002/health/ready
```

**Output**
```
HTTP/1.1 503 Service Unavailable
content-type: application/json

{"status":"unhealthy","database":"error","rls":"ok","tenant_guc":"ok"}
```

### EG4 — Worker Capability Data-Plane Gate
**Proof that probe is not eager (data-plane only)**
```
python -c "from app.celery_app import celery_app; print(celery_app.conf.task_always_eager)"
```
**Output**
```
False
```

**Command (worker running)**
```
python -m celery -A app.celery_app.celery_app worker -P solo -c 1 --loglevel=INFO
curl.exe -s -i http://127.0.0.1:8001/health/worker
```

**Output**
```
HTTP/1.1 200 OK
content-type: application/json

{"status":"ok","broker":"ok","database":"ok","worker":"ok","probe_latency_ms":578,"cached":false}
```

**Command (workers stopped)**
```
Stop-Process -Id 44948,66600,37392,8240
curl.exe -s -i http://127.0.0.1:8001/health/worker
```

**Output**
```
HTTP/1.1 503 Service Unavailable
content-type: application/json

{"status":"unhealthy","broker":"ok","database":"error","worker":"error","probe_latency_ms":16469,"cached":false}
```

### EG5 — Probe Safety Gate
**Command**
```
curl.exe -s -i http://127.0.0.1:8001/health/worker
curl.exe -s -i http://127.0.0.1:8001/health/worker
```

**Output (first, uncached)**
```
{"status":"ok","broker":"ok","database":"ok","worker":"ok","probe_latency_ms":594,"cached":false}
```

**Output (second, cached)**
```
{"status":"ok","broker":"ok","database":"ok","worker":"ok","probe_latency_ms":594,"cached":true}
```

### EG6 — No Worker HTTP Regression Gate
**Command**
```
python scripts/ci/enforce_no_worker_http_server.py
```

**Output**
```
B0.5.6.1 Worker HTTP Server Guardrail Scan
Scanned: C:\Users\ayewhy\II SKELDIR II\backend\app
Violations: 0

PASS: No worker HTTP server primitives detected.
```

### EG7 — CI + Forensics Closure Gate
**Tests present**
- `backend/tests/test_b0562_health_semantics.py` (EG1–EG6 coverage)

**CI run**
- Not executed in this local run (pending CI URL).

---

## 4) Adjudication Metadata

- **Commit SHA**: 96f605a
- **CI Run URL**: https://github.com/Muk223/skeldir-2.0/actions/runs/21100492747

---

**End of Evidence Pack**
