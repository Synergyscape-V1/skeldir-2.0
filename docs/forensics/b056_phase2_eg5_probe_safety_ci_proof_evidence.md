# B0.5.6.2 EG5 Probe Safety CI Proof Evidence

Date: 2026-01-17  
Owner: codex agent  
Scope: EG5 probe safety (anti-stampede) validation via HTTP path

## Objective
Prove EG5 cache safety through a CI validation step that fails if caching is broken,
while preserving B0.5.6.1 (no worker HTTP listener) and explicit health semantics.

## Hypotheses (unvalidated at start)
- H-BLOCK-1: EG5 not closed in CI; `"cached": false` for rapid calls.
- H-BLOCK-2: `"cached"` is misleading or decoupled from cache.
- H-BLOCK-3: CI process model prevents cache reuse (multi-worker or restarts).
- H-BLOCK-4: INDEX/evidence provenance inconsistent with adjudicated commit.

---

## Step A — CI process model truth
CI starts the API with a single-process uvicorn command (no `--workers`):

```
514:526:.github/workflows/ci.yml
      - name: B0.5.6.2 Worker capability data-plane probe
        env:
          DATABASE_URL: ${{ env.DATABASE_URL }}
          CELERY_BROKER_URL: ${{ env.CELERY_BROKER_URL }}
          CELERY_RESULT_BACKEND: ${{ env.CELERY_RESULT_BACKEND }}
        run: |
          set -euo pipefail
          cd backend
          export PYTHONPATH="$(pwd):${PYTHONPATH:-}"
          export DATABASE_URL="${DATABASE_URL/postgresql:\/\//postgresql+asyncpg://}"
          : > /tmp/health_probe_api.log
          nohup python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/health_probe_api.log 2>&1 &
```

Local multi-worker reproduction confirms multiple processes when `--workers 2` is used
(see Step C output), supporting a process-local cache scope interpretation.

---

## Step B — Probe script behavior (connection reuse + call pattern)
`scripts/ci/health_worker_probe.py` uses `requests.get()` without a session, retries
5 times, and does not parse `"cached"`:

Excerpt (<=25 words):
“`for attempt in range(1, args.attempts + 1):` … `resp = requests.get(args.url, timeout=20)` … `if resp.status_code == 200: break`”

```
39:55:scripts/ci/health_worker_probe.py
def main() -> int:
    args = _parse_args()
    log_path = Path(args.log_path)
    last_status = 0
    last_body: dict[str, Any] = {}
    for attempt in range(1, args.attempts + 1):
        resp = requests.get(args.url, timeout=20)
        last_status = resp.status_code
        last_body = _parse_body(resp.text)
        print(f"health_worker_probe_attempt_{attempt}_response_begin", flush=True)
        print(resp.status_code, flush=True)
        print(resp.text, flush=True)
        print(f"health_worker_probe_attempt_{attempt}_response_end", flush=True)
        _write_log(log_path, attempt, resp.status_code, resp.text)
        if resp.status_code == 200:
            break
        time.sleep(args.delay_seconds)
```

---

## Step C — Local reproduction (HTTP path)
### Single-process API (port 8010)
Command:
`python -m uvicorn app.main:app --host 127.0.0.1 --port 8010`

Calls (no session + session; 100ms spacing, 25s timeout):
```
single_process_no_session
1 503 {... 'cached': False}
2 503 {... 'cached': True}
3 503 {... 'cached': True}
single_process_session
1 503 {... 'cached': True}
2 503 {... 'cached': True}
3 503 {... 'cached': True}
```

Result: cache reuse observed after initial call.

### Multi-worker API (port 8011, 2 workers)
Command:
`python -m uvicorn app.main:app --host 127.0.0.1 --port 8011 --workers 2`

Calls (no session vs session):
```
multi_worker_no_session
1 503 {... 'cached': True}
2 503 {... 'cached': False}
3 503 {... 'cached': False}
multi_worker_session
1 503 {... 'cached': True}
2 503 {... 'cached': True}
3 503 {... 'cached': True}
```

Result: process-local cache loses reuse under connection churn; session keep-alive
stabilizes cache reuse. This supports H-RC-4/H-RC-5.

---

## Step D — Static cache correctness (module-global + truthful cached flag)
Module-global cache + locks:
```
29:61:backend/app/api/health.py
# Worker Probe Cache + Single-Flight Lock (EG5 - Probe Safety)
_PROBE_CACHE_TTL_SECONDS = 10.0
_PROBE_TIMEOUT_SECONDS = 15.0  # Max time to wait for worker response
...
_probe_cache: Optional[_ProbeResult] = None
_probe_cache_lock = threading.Lock()
_probe_inflight = False
_probe_inflight_lock = threading.Lock()
```

Cached-return branch bypasses new probe:
```
124:172:backend/app/api/health.py
def _get_or_execute_probe() -> tuple[_ProbeResult, bool]:
    ...
    with _probe_cache_lock:
        if _is_cache_valid():
            return _probe_cache, True
    ...
    result = _execute_worker_probe()
    with _probe_cache_lock:
        _probe_cache = result
    return result, False
```

`"cached"` flag bound to cache branch:
```
275:306:backend/app/api/health.py
probe, was_cached = _get_or_execute_probe()
result = {
    "status": "ok" if probe.worker_ok else "unhealthy",
    "broker": "ok" if probe.broker_ok else "error",
    "database": "ok" if probe.database_ok else "error",
    "worker": "ok" if probe.worker_ok else "error",
    "probe_latency_ms": probe.latency_ms,
    "cached": was_cached,
    "cache_scope": "process",
}
```

**Cache scope:** explicitly process-local.

---

## Root cause (H-BLOCK-1 / H-RC-3)
Initial EG5 validation failed because the EG5 step ran **after** the
`health_worker_probe` call, so the first EG5 request hit a pre-warmed cache and
returned `"cached": true`. Reordering EG5 **before** the worker probe restored
the expected uncached-first behavior.

## Remediation — EG5 CI validation script
Script: `scripts/ci/eg5_cache_validation.py`
```
1:65:scripts/ci/eg5_cache_validation.py
"""
EG5 cache validation: prove /health/worker cache reuse via HTTP.
"""
...
with requests.Session() as session:
    for attempt in range(1, 4):
        resp = session.get(args.url, timeout=args.timeout_seconds)
        body = _parse_body(resp.text)
        print(f"eg5_cache_validation_attempt_{attempt}_begin", flush=True)
        ...
expected = [False, True, True]
cached_values = [r["body"].get("cached") for r in results]
if cached_values != expected:
    ...
    return 1
```

CI workflow step (runs after worker probe, same API process):
```
514:587:.github/workflows/ci.yml
          python -u ../scripts/ci/eg5_cache_validation.py \
            --url "http://127.0.0.1:8000/health/worker" \
            --delay-seconds 0.1 \
            --timeout-seconds 20
          : > /tmp/health_worker_probe.log
          set +e
          python -u ../scripts/ci/health_worker_probe.py \
            --url "http://127.0.0.1:8000/health/worker" \
            --log-path /tmp/health_worker_probe.log \
            2>&1 | tee /tmp/health_worker_probe_stdout.log
          echo "health_probe_api_log_tail_begin"
          tail -n 50 /tmp/health_probe_api.log || true
          echo "health_probe_api_log_tail_end"
          kill "${API_PID}" || true
```

---

## Guardrail non-regression
The CI guardrail step remains unchanged and still executes before probes:
`python scripts/ci/enforce_no_worker_http_server.py --scan-path backend/app ...`

---

## CI Run (EG5 gate)
- CI run URL: https://github.com/Muk223/skeldir-2.0/actions/runs/21100492747
- Result: EG5 validation step ran and passed (cached false → true → true).

Excerpt:
```
3470:3482:artifacts/ci_eg5_run_21100492747.log
eg5_cache_validation_attempt_1_begin
200
{"status":"ok","broker":"ok","database":"ok","worker":"ok","probe_latency_ms":1129,"cached":false,"cache_scope":"process"}
eg5_cache_validation_attempt_1_end
eg5_cache_validation_attempt_2_begin
200
{"status":"ok","broker":"ok","database":"ok","worker":"ok","probe_latency_ms":1129,"cached":true,"cache_scope":"process"}
eg5_cache_validation_attempt_2_end
eg5_cache_validation_attempt_3_begin
200
{"status":"ok","broker":"ok","database":"ok","worker":"ok","probe_latency_ms":1129,"cached":true,"cache_scope":"process"}
eg5_cache_validation_attempt_3_end
eg5_cache_validation_passed
```

---

## INDEX update
Phase 2 row must reference commit `96f605a` and the green CI URL above.
Update `docs/forensics/INDEX.md` accordingly.
