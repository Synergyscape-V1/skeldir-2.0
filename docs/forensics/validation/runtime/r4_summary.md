# R4 Worker Failure Semantics Summary (Truth Anchor)

## Status

R4 = **COMPLETE** as of:

- **Candidate SHA:** `165889cabe8f71ca7e1953f176e26627f6341a65`
- **CI run:** https://github.com/Muk223/skeldir-2.0/actions/runs/21963198582
- **Generated at:** `2026-02-12T20:34:37.763548+00:00`

## Run Configuration (from harness log)

- `broker_scheme` = `sqla+postgresql`
- `result_backend_scheme` = `db+postgresql`
- `broker_dsn_sha256` = `480be02d7e3400fa415405d1b343d56165f2d4596ebe25615c46354a0511001b`
- `result_backend_dsn_sha256` = `cbb79a35e3044b55f29ea5154480336d5bfdec42af1a05de8e088bc60c6e31d3`
- `acks_late` = `True`
- `reject_on_worker_lost` = `True`
- `acks_on_failure_or_timeout` = `True`
- `prefetch_multiplier` = `1`
- `tenant_a` = `c23de396-a1e1-58d5-b203-68de01ae9164`
- `tenant_b` = `f4266f71-61e8-5cb6-a552-614c25977da8`

## Exit Gates (Pass Matrix)

| Gate | Description | Status |
|------|-------------|--------|
| EG-R4-FIX-0 | Instrument integrity (SHA + config + verdicts) | PASS |
| EG-R4-FIX-1 | Postgres-only fabric provable (scheme + DSN hashes) | PASS |
| EG-R4-FIX-2 | Cross-tenant RLS probe explicit (tenant A reads tenant B id → 0) | PASS |
| EG-R4-1 | Poison retries proven (attempts_min_per_task >= 2) | PASS |
| EG-R4-2 | Crash physics proven (barrier→kill→exit→restart→redelivery) | PASS |
| EG-R4-3 | Redelivery accounting (redelivery_observed_count == N) | PASS |
| EG-R4-4 | Runaway terminated; no starvation | PASS |
| EG-R4-5 | Least privilege probes fail | PASS |

## Evidence (Browser-Verifiable Logs)

This run prints, to CI logs, one `R4_VERDICT_BEGIN/END` JSON block per scenario.

Log step containing verdict blocks: `Run R4 harness` in `.github/workflows/r4-worker-failure-semantics.yml`.

Fabric proof markers printed in logs:

- `R4_BROKER_SCHEME=...`
- `R4_BACKEND_SCHEME=...`
- `R4_BROKER_DSN_SHA256=...`
- `R4_BACKEND_DSN_SHA256=...`

Cross-tenant RLS probe markers printed in logs:

- `R4_S3_TENANT_A=... R4_S3_TENANT_B=... R4_S3_TARGET_ROW_ID=...`
- `R4_S3_RESULT_ROWS=0` (or `R4_S3_DB_ERROR=...`)

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
  "candidate_sha": "165889cabe8f71ca7e1953f176e26627f6341a65",
  "db_truth": {
    "attempts": {
      "attempts_distribution": {
        "4": 10
      },
      "attempts_max_per_task": 4,
      "attempts_min_per_task": 4,
      "attempts_total": 40,
      "task_count_observed": 10
    },
    "worker_failed_jobs": {
      "max_retry_count": 3,
      "rows": 10,
      "rows_total": 10
    },
    "worker_side_effects": {
      "duplicate_task_ids": 0,
      "rows": 0
    }
  },
  "passed": true,
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/21963198582",
  "scenario": "S1_PoisonPill",
  "tenant_a": "c23de396-a1e1-58d5-b203-68de01ae9164",
  "tenant_b": "f4266f71-61e8-5cb6-a552-614c25977da8",
  "worker_observed": {
    "dlq_rows_observed": 10
  }
}
```

### S2 CrashAfterWritePreAck (N=10)
```json
{
  "N": 10,
  "candidate_sha": "165889cabe8f71ca7e1953f176e26627f6341a65",
  "db_truth": {
    "attempts": {
      "attempts_distribution": {
        "2": 10
      },
      "attempts_max_per_task": 2,
      "attempts_min_per_task": 2,
      "attempts_total": 20,
      "task_count_observed": 10
    },
    "worker_side_effects": {
      "duplicate_task_ids": 0,
      "rows": 10
    }
  },
  "passed": true,
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/21963198582",
  "scenario": "S2_CrashAfterWritePreAck",
  "tenant_a": "c23de396-a1e1-58d5-b203-68de01ae9164",
  "tenant_b": "f4266f71-61e8-5cb6-a552-614c25977da8",
  "worker_observed": {
    "crash_physics": {
      "barrier_observed_count": 10,
      "kill_issued_count": 10,
      "redelivery_observed_count": 10,
      "worker_exited_count": 10,
      "worker_restarted_count": 10
    },
    "kill_issued": true,
    "kill_sig": 9,
    "kombu_payload_debug": {
      "found": true,
      "headers_id": "6d690ee4-47ef-5bba-be89-207d18273d3e",
      "headers_task": "app.tasks.r4_failure_semantics.crash_after_write_pre_ack",
      "headers_task_id": null,
      "top_id": null,
      "top_keys": [
        "body",
        "content-encoding",
        "content-type",
        "headers",
        "properties"
      ]
    },
    "redelivery_observed_count": 10,
    "worker_exit_codes": [
      -9,
      -9,
      -9,
      -9,
      -9,
      -9,
      -9,
      -9,
      -9,
      -9
    ],
    "worker_pid_after": 3146,
    "worker_pid_before": 2719,
    "worker_pid_restarts": [
      2765,
      2807,
      2849,
      2892,
      2933,
      2979,
      3020,
      3061,
      3102,
      3146
    ]
  }
}
```

### S3 RLSProbe (N=1)
```json
{
  "N": 1,
  "candidate_sha": "165889cabe8f71ca7e1953f176e26627f6341a65",
  "db_truth": {
    "target_row_id": "57f5d0b2-ceb3-4143-9f2e-fe8f170ebd57"
  },
  "passed": true,
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/21963198582",
  "scenario": "S3_RLSProbe",
  "tenant_a": "c23de396-a1e1-58d5-b203-68de01ae9164",
  "tenant_b": "f4266f71-61e8-5cb6-a552-614c25977da8",
  "worker_observed": {
    "bypass_detected": false,
    "db_error": "",
    "result_rows": 0,
    "sqlstate": ""
  }
}
```

### S4 RunawayNoStarve (sentinels N=10)
```json
{
  "N": 10,
  "candidate_sha": "165889cabe8f71ca7e1953f176e26627f6341a65",
  "db_truth": {
    "worker_side_effects": {
      "duplicate_task_ids": 0,
      "rows": 10
    }
  },
  "passed": true,
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/21963198582",
  "scenario": "S4_RunawayNoStarve",
  "tenant_a": "c23de396-a1e1-58d5-b203-68de01ae9164",
  "tenant_b": "f4266f71-61e8-5cb6-a552-614c25977da8",
  "worker_observed": {
    "runaway_outcome": "SoftTimeLimitExceeded",
    "sentinel_rows_observed": 10
  }
}
```

### S5 LeastPrivilege (N=1)
```json
{
  "N": 1,
  "candidate_sha": "165889cabe8f71ca7e1953f176e26627f6341a65",
  "db_truth": {
    "worker_failed_jobs_rows": 0
  },
  "passed": true,
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/21963198582",
  "scenario": "S5_LeastPrivilege",
  "tenant_a": "c23de396-a1e1-58d5-b203-68de01ae9164",
  "tenant_b": "f4266f71-61e8-5cb6-a552-614c25977da8",
  "worker_observed": {
    "probe_results": {
      "bypass_rls_attempt": {
        "error": "query would be affected by row-level security policy for table \"attribution_events\"\n",
        "ok": "false"
      },
      "create_role": {
        "error": "permission denied to create role\nDETAIL:  Only roles with the CREATEROLE attribute may create roles.\n",
        "ok": "false"
      },
      "ddl_create_table": {
        "error": "permission denied for schema public\nLINE 1: CREATE TABLE r4_priv_probe_tmp(id INT)\n                     ^\n",
        "ok": "false"
      },
      "disable_rls": {
        "error": "must be owner of table attribution_events\n",
        "ok": "false"
      },
      "force_rls": {
        "error": "must be owner of table attribution_events\n",
        "ok": "false"
      },
      "grant_admin_role": {
        "error": "permission denied to grant role \"pg_read_all_data\"\nDETAIL:  Only roles with the ADMIN option on role \"pg_read_all_data\" may grant this role.\n",
        "ok": "false"
      },
      "set_bypassrls": {
        "error": "permission denied to alter role\nDETAIL:  Only roles with the CREATEROLE attribute and the ADMIN option on role \"app_user\" may alter this role.\n",
        "ok": "false"
      }
    },
    "required_failures": {
      "bypass_rls_attempt": true,
      "create_role": true,
      "ddl_create_table": true,
      "disable_rls": true,
      "force_rls": true,
      "grant_admin_role": true,
      "set_bypassrls": true
    }
  }
}
```

## Where the Evidence Lives

- Workflow: `.github/workflows/r4-worker-failure-semantics.yml`
- Harness: `scripts/r4/worker_failure_semantics.py`
- Summary generator: `scripts/r4/render_r4_summary.py`

