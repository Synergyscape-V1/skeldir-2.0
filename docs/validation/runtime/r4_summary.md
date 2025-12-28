# R4 Worker Failure Semantics Summary (Truth Anchor)

## Status

R4 = **IN PROGRESS** as of:

- **Candidate SHA:** `87fe934f7cc2da106e275c7be03ab8cba5899b16`
- **CI run:** https://github.com/Muk223/skeldir-2.0/actions/runs/20557998267
- **Generated at:** `2025-12-28T18:44:45.218245+00:00`

## Run Configuration (from harness log)

- `broker_url` = `sqla+postgresql://app_user:app_user@127.0.0.1:5432/r4`
- `result_backend` = `db+postgresql://app_user:app_user@127.0.0.1:5432/r4`
- `acks_late` = `True`
- `reject_on_worker_lost` = `True`
- `acks_on_failure_or_timeout` = `True`
- `prefetch_multiplier` = `1`
- `tenant_a` = `d127106b-29e5-5119-a9b8-ca9bef90bf4a`
- `tenant_b` = `7f4f8d9c-1ab6-5976-922f-ab483978ee9f`

## Exit Gates (Pass Matrix)

| Gate | Description | Status |
|------|-------------|--------|
| EG-R4-0 | Instrument & SHA binding | PASS |
| EG-R4-1 | Retry/DLQ physics (PoisonPill N=10) | FAIL |
| EG-R4-2 | Idempotency under crash (CrashAfterWritePreAck N=10) | PASS |
| EG-R4-3 | Worker RLS enforcement (Cross-tenant probe) | FAIL |
| EG-R4-4 | Timeouts & starvation resistance (Runaway + sentinels) | FAIL |
| EG-R4-5 | Least privilege reality (probes fail) | FAIL |
| EG-R4-6 | Evidence pack present (verdict blocks S1..S5) | FAIL |

## Evidence (Browser-Verifiable Logs)

This run prints, to CI logs, one `R4_VERDICT_BEGIN/END` JSON block per scenario.

Log step containing verdict blocks: `Run R4 harness` in `.github/workflows/r4-worker-failure-semantics.yml`.

## Key Verdicts

### S1 PoisonPill (N=10)
```json
{
  "N": 10,
  "db_truth": {
    "worker_failed_jobs": {
      "max_retry_count": 0,
      "rows": 0
    },
    "worker_side_effects": {
      "duplicate_task_ids": 0,
      "rows": 0
    }
  },
  "passed": false,
  "scenario": "S1_PoisonPill",
  "tenant_a": "d127106b-29e5-5119-a9b8-ca9bef90bf4a",
  "tenant_b": "7f4f8d9c-1ab6-5976-922f-ab483978ee9f",
  "worker_observed": {
    "failed_results": 10,
    "successful_results": 0
  }
}
```

### S2 CrashAfterWritePreAck (N=10)
```json
{
  "N": 10,
  "db_truth": {
    "worker_side_effects": {
      "duplicate_task_ids": 0,
      "rows": 10
    }
  },
  "passed": true,
  "scenario": "S2_CrashAfterWritePreAck",
  "tenant_a": "d127106b-29e5-5119-a9b8-ca9bef90bf4a",
  "tenant_b": "7f4f8d9c-1ab6-5976-922f-ab483978ee9f",
  "worker_observed": {
    "failed_results": 0,
    "successful_results": 10
  }
}
```

### S3 RLSProbe (N=1)
```json
{}
```

### S4 RunawayNoStarve (sentinels N=10)
```json
{}
```

### S5 LeastPrivilege (N=1)
```json
{}
```

## Where the Evidence Lives

- Workflow: `.github/workflows/r4-worker-failure-semantics.yml`
- Harness: `scripts/r4/worker_failure_semantics.py`
- Summary generator: `scripts/r4/render_r4_summary.py`

