# R4 Worker Failure Semantics Summary (Truth Anchor)

## Status

R4 = **COMPLETE** as of:

- **Candidate SHA:** `53d010a87b1d818ebcb392ebd5f747c667e23d44`
- **CI run:** https://github.com/Muk223/skeldir-2.0/actions/runs/21926723052
- **Generated at:** `2026-02-11T23:13:23.632303+00:00`

## Run Configuration (from harness log)

- `broker_scheme` = `sqla+postgresql`
- `result_backend_scheme` = `db+postgresql`
- `broker_dsn_sha256` = `480be02d7e3400fa415405d1b343d56165f2d4596ebe25615c46354a0511001b`
- `result_backend_dsn_sha256` = `cbb79a35e3044b55f29ea5154480336d5bfdec42af1a05de8e088bc60c6e31d3`
- `acks_late` = `True`
- `reject_on_worker_lost` = `True`
- `acks_on_failure_or_timeout` = `True`
- `prefetch_multiplier` = `1`
- `tenant_a` = `94289046-47cf-54f6-8a3f-c2f320b6a6fa`
- `tenant_b` = `b2419a6c-cc52-58ac-bd1b-4efc44817e0e`

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
  "candidate_sha": "53d010a87b1d818ebcb392ebd5f747c667e23d44",
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
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/21926723052",
  "scenario": "S1_PoisonPill",
  "tenant_a": "94289046-47cf-54f6-8a3f-c2f320b6a6fa",
  "tenant_b": "b2419a6c-cc52-58ac-bd1b-4efc44817e0e",
  "worker_observed": {
    "dlq_rows_observed": 10
  }
}
```

### S2 CrashAfterWritePreAck (N=10)
```json
{
  "N": 10,
  "candidate_sha": "53d010a87b1d818ebcb392ebd5f747c667e23d44",
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
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/21926723052",
  "scenario": "S2_CrashAfterWritePreAck",
  "tenant_a": "94289046-47cf-54f6-8a3f-c2f320b6a6fa",
  "tenant_b": "b2419a6c-cc52-58ac-bd1b-4efc44817e0e",
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
      "headers_id": "cedc1731-16e5-5ecd-aa34-de57f6f2c3de",
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
    "worker_pid_after": 3315,
    "worker_pid_before": 2889,
    "worker_pid_restarts": [
      2937,
      2979,
      3022,
      3062,
      3105,
      3149,
      3190,
      3231,
      3274,
      3315
    ]
  }
}
```

### S3 RLSProbe (N=1)
```json
{
  "N": 1,
  "candidate_sha": "53d010a87b1d818ebcb392ebd5f747c667e23d44",
  "db_truth": {
    "target_row_id": "a7e0eae9-1c2e-43f1-b59f-92a91ac98ff8"
  },
  "passed": true,
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/21926723052",
  "scenario": "S3_RLSProbe",
  "tenant_a": "94289046-47cf-54f6-8a3f-c2f320b6a6fa",
  "tenant_b": "b2419a6c-cc52-58ac-bd1b-4efc44817e0e",
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
  "candidate_sha": "53d010a87b1d818ebcb392ebd5f747c667e23d44",
  "db_truth": {
    "worker_side_effects": {
      "duplicate_task_ids": 0,
      "rows": 10
    }
  },
  "passed": true,
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/21926723052",
  "scenario": "S4_RunawayNoStarve",
  "tenant_a": "94289046-47cf-54f6-8a3f-c2f320b6a6fa",
  "tenant_b": "b2419a6c-cc52-58ac-bd1b-4efc44817e0e",
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
  "candidate_sha": "53d010a87b1d818ebcb392ebd5f747c667e23d44",
  "db_truth": {
    "worker_failed_jobs_rows": 0
  },
  "passed": true,
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/21926723052",
  "scenario": "S5_LeastPrivilege",
  "tenant_a": "94289046-47cf-54f6-8a3f-c2f320b6a6fa",
  "tenant_b": "b2419a6c-cc52-58ac-bd1b-4efc44817e0e",
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

