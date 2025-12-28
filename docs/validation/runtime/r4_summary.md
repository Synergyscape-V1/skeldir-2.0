# R4 Worker Failure Semantics Summary (Truth Anchor)

## Status

R4 = **IN PROGRESS** as of:

- **Candidate SHA:** `d33fcbdb86934537014c125e6b46ee89a020f012`
- **CI run:** https://github.com/Muk223/skeldir-2.0/actions/runs/20558977697
- **Generated at:** `2025-12-28T20:15:26.815100+00:00`

## Run Configuration (from harness log)

- `broker_url` = `sqla+postgresql://app_user:app_user@127.0.0.1:5432/r4`
- `result_backend` = `db+postgresql://app_user:app_user@127.0.0.1:5432/r4`
- `acks_late` = `True`
- `reject_on_worker_lost` = `True`
- `acks_on_failure_or_timeout` = `True`
- `prefetch_multiplier` = `1`
- `tenant_a` = `e03dd692-9e07-5f63-8276-d222febf25c7`
- `tenant_b` = `b4ac552c-9574-5f31-a34b-e680b9429e6b`

## Exit Gates (Pass Matrix)

| Gate | Description | Status |
|------|-------------|--------|
| EG-R4-FIX-0 | Instrument integrity (SHA + config + verdicts) | PASS |
| EG-R4-FIX-1 | Poison retries proven (attempts_min_per_task >= 2) | FAIL |
| EG-R4-FIX-2 | Crash physics proven (barrier→kill→exit→restart→redelivery) | FAIL |
| EG-R4-FIX-3 | Redelivery accounting (redelivery_observed_count == N) | FAIL |
| EG-R4-FIX-4 | RLS + runaway + least-privilege still pass | FAIL |

## Evidence (Browser-Verifiable Logs)

This run prints, to CI logs, one `R4_VERDICT_BEGIN/END` JSON block per scenario.

Log step containing verdict blocks: `Run R4 harness` in `.github/workflows/r4-worker-failure-semantics.yml`.

Crash proof markers printed in logs (per task_id):

- `R4_S2_BARRIER_OBSERVED`
- `R4_S2_KILL_ISSUED`
- `R4_S2_WORKER_EXITED`
- `R4_S2_WORKER_RESTARTED`
- `R4_S2_REDELIVERED`

## Key Verdicts

### S1 PoisonPill (N=10)
```json
{
  "N": 10,
  "candidate_sha": "d33fcbdb86934537014c125e6b46ee89a020f012",
  "db_truth": {},
  "passed": false,
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/20558977697",
  "scenario": "S1_PoisonPill",
  "tenant_a": "e03dd692-9e07-5f63-8276-d222febf25c7",
  "tenant_b": "b4ac552c-9574-5f31-a34b-e680b9429e6b",
  "worker_observed": {
    "error": "TypeError: Invalid argument(s) 'visibility_timeout','polling_interval' sent to create_engine(), using configuration PGDialect_psycopg2/QueuePool/Engine.  Please check that the keyword arguments are appropriate for this combination of components."
  }
}
```

### S2 CrashAfterWritePreAck (N=10)
```json
{
  "N": 10,
  "candidate_sha": "d33fcbdb86934537014c125e6b46ee89a020f012",
  "db_truth": {},
  "passed": false,
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/20558977697",
  "scenario": "S2_CrashAfterWritePreAck",
  "tenant_a": "e03dd692-9e07-5f63-8276-d222febf25c7",
  "tenant_b": "b4ac552c-9574-5f31-a34b-e680b9429e6b",
  "worker_observed": {
    "error": "TypeError: Invalid argument(s) 'visibility_timeout','polling_interval' sent to create_engine(), using configuration PGDialect_psycopg2/QueuePool/Engine.  Please check that the keyword arguments are appropriate for this combination of components."
  }
}
```

### S3 RLSProbe (N=1)
```json
{
  "N": 1,
  "candidate_sha": "d33fcbdb86934537014c125e6b46ee89a020f012",
  "db_truth": {},
  "passed": false,
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/20558977697",
  "scenario": "S3_RLSProbe",
  "tenant_a": "e03dd692-9e07-5f63-8276-d222febf25c7",
  "tenant_b": "b4ac552c-9574-5f31-a34b-e680b9429e6b",
  "worker_observed": {
    "error": "TypeError: Invalid argument(s) 'visibility_timeout','polling_interval' sent to create_engine(), using configuration PGDialect_psycopg2/QueuePool/Engine.  Please check that the keyword arguments are appropriate for this combination of components."
  }
}
```

### S4 RunawayNoStarve (sentinels N=10)
```json
{
  "N": 10,
  "candidate_sha": "d33fcbdb86934537014c125e6b46ee89a020f012",
  "db_truth": {},
  "passed": false,
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/20558977697",
  "scenario": "S4_RunawayNoStarve",
  "tenant_a": "e03dd692-9e07-5f63-8276-d222febf25c7",
  "tenant_b": "b4ac552c-9574-5f31-a34b-e680b9429e6b",
  "worker_observed": {
    "error": "TypeError: Invalid argument(s) 'visibility_timeout','polling_interval' sent to create_engine(), using configuration PGDialect_psycopg2/QueuePool/Engine.  Please check that the keyword arguments are appropriate for this combination of components."
  }
}
```

### S5 LeastPrivilege (N=1)
```json
{
  "N": 1,
  "candidate_sha": "d33fcbdb86934537014c125e6b46ee89a020f012",
  "db_truth": {},
  "passed": false,
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/20558977697",
  "scenario": "S5_LeastPrivilege",
  "tenant_a": "e03dd692-9e07-5f63-8276-d222febf25c7",
  "tenant_b": "b4ac552c-9574-5f31-a34b-e680b9429e6b",
  "worker_observed": {
    "error": "TypeError: Invalid argument(s) 'visibility_timeout','polling_interval' sent to create_engine(), using configuration PGDialect_psycopg2/QueuePool/Engine.  Please check that the keyword arguments are appropriate for this combination of components."
  }
}
```

## Where the Evidence Lives

- Workflow: `.github/workflows/r4-worker-failure-semantics.yml`
- Harness: `scripts/r4/worker_failure_semantics.py`
- Summary generator: `scripts/r4/render_r4_summary.py`

