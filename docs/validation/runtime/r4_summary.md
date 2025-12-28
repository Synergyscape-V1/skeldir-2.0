# R4 Worker Failure Semantics Summary (Truth Anchor)

## Status

R4 = **IN PROGRESS** as of:

- **Candidate SHA:** `9d96def2661506678d7395d952806bad07bd3d6f`
- **CI run:** https://github.com/Muk223/skeldir-2.0/actions/runs/20560316544
- **Generated at:** `2025-12-28T22:21:06.267630+00:00`

## Run Configuration (from harness log)

- `broker_url` = `sqla+postgresql://app_user:app_user@127.0.0.1:5432/r4`
- `result_backend` = `db+postgresql://app_user:app_user@127.0.0.1:5432/r4`
- `acks_late` = `True`
- `reject_on_worker_lost` = `True`
- `acks_on_failure_or_timeout` = `True`
- `prefetch_multiplier` = `1`
- `tenant_a` = `c99f0ff9-2f83-58a1-b0dd-7a1fee711bd4`
- `tenant_b` = `68ce4355-d9ed-5bfa-87ff-d4d686ee503f`

## Exit Gates (Pass Matrix)

| Gate | Description | Status |
|------|-------------|--------|
| EG-R4-FIX-0 | Instrument integrity (SHA + config + verdicts) | PASS |
| EG-R4-FIX-1 | Poison retries proven (attempts_min_per_task >= 2) | PASS |
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
  "candidate_sha": "9d96def2661506678d7395d952806bad07bd3d6f",
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
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/20560316544",
  "scenario": "S1_PoisonPill",
  "tenant_a": "c99f0ff9-2f83-58a1-b0dd-7a1fee711bd4",
  "tenant_b": "68ce4355-d9ed-5bfa-87ff-d4d686ee503f",
  "worker_observed": {
    "dlq_rows_observed": 10
  }
}
```

### S2 CrashAfterWritePreAck (N=10)
```json
{
  "N": 10,
  "candidate_sha": "9d96def2661506678d7395d952806bad07bd3d6f",
  "db_truth": {
    "attempts": {
      "attempts_distribution": {
        "14": 1,
        "15": 1
      },
      "attempts_max_per_task": 15,
      "attempts_min_per_task": 14,
      "attempts_total": 29,
      "task_count_observed": 2
    },
    "worker_side_effects": {
      "duplicate_task_ids": 0,
      "rows": 2
    }
  },
  "passed": false,
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/20560316544",
  "scenario": "S2_CrashAfterWritePreAck",
  "tenant_a": "c99f0ff9-2f83-58a1-b0dd-7a1fee711bd4",
  "tenant_b": "68ce4355-d9ed-5bfa-87ff-d4d686ee503f",
  "worker_observed": {
    "crash_physics": {
      "barrier_observed_count": 2,
      "kill_issued_count": 2,
      "redelivery_observed_count": 2,
      "worker_exited_count": 2,
      "worker_restarted_count": 2
    },
    "kill_issued": true,
    "kill_sig": 9,
    "redelivery_observed_count": 2,
    "worker_exit_codes": [
      -9,
      -9
    ],
    "worker_pid_after": 2758,
    "worker_pid_before": 2672,
    "worker_pid_restarts": [
      2717,
      2758
    ]
  }
}
```

### S3 RLSProbe (N=1)
```json
{
  "N": 1,
  "candidate_sha": "9d96def2661506678d7395d952806bad07bd3d6f",
  "db_truth": {
    "missing_tenant_dlq_rows": 0
  },
  "passed": false,
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/20560316544",
  "scenario": "S3_RLSProbe",
  "tenant_a": "c99f0ff9-2f83-58a1-b0dd-7a1fee711bd4",
  "tenant_b": "68ce4355-d9ed-5bfa-87ff-d4d686ee503f",
  "worker_observed": {
    "bad_failed": true,
    "visible_count_for_tenant_a": 0
  }
}
```

### S4 RunawayNoStarve (sentinels N=10)
```json
{
  "N": 10,
  "candidate_sha": "9d96def2661506678d7395d952806bad07bd3d6f",
  "db_truth": {
    "worker_side_effects": {
      "duplicate_task_ids": 0,
      "rows": 10
    }
  },
  "passed": true,
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/20560316544",
  "scenario": "S4_RunawayNoStarve",
  "tenant_a": "c99f0ff9-2f83-58a1-b0dd-7a1fee711bd4",
  "tenant_b": "68ce4355-d9ed-5bfa-87ff-d4d686ee503f",
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
  "candidate_sha": "9d96def2661506678d7395d952806bad07bd3d6f",
  "db_truth": {
    "worker_failed_jobs_rows": 0
  },
  "passed": true,
  "run_url": "https://github.com/Muk223/skeldir-2.0/actions/runs/20560316544",
  "scenario": "S5_LeastPrivilege",
  "tenant_a": "c99f0ff9-2f83-58a1-b0dd-7a1fee711bd4",
  "tenant_b": "68ce4355-d9ed-5bfa-87ff-d4d686ee503f",
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

