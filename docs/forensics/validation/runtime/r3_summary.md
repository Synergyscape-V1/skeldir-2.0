# R3 Ingestion Under Fire Validation Summary (Truth Anchor)

## Status

R3 = **COMPLETE** as of:

- **Candidate SHA:** `cb58aed0c604c1f95ffa54235ec43d5e6229c079`
- **CI run:** https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/42487308991
- **Generated at:** `2026-11-08T14:07:09.182250+00:00`
- **Measurement validity (EG3.5):** `VALID`

## Run Configuration (from harness log)

- `R3_API_BASE_URL` = `http://127.0.0.1:8000`
- `R3_LADDER` = `[50, 250, 1000]`
- `R3_CONCURRENCY` = `200`
- `R3_TIMEOUT_S` = `10.0`
- `RUN_START_UTC` = `2026-11-08T13:57:13.583170+00:00`
- `R3_EG34_PROFILES` = `[{'duration_s': 60, 'enforce_no_degradation': False, 'name': 'EG3_4_Test1_Month6', 'p95_max_ms': 2000.0, 'target_rps': 29.0}, {'duration_s': 60, 'enforce_no_degradation': False, 'name': 'EG3_4_Test2_Month18', 'p95_max_ms': 2000.0, 'target_rps': 46.0}, {'duration_s': 300, 'enforce_no_degradation': True, 'name': 'EG3_4_Test3_SustainedOps', 'p95_max_ms': 2000.0, 'target_rps': 5.0}]`
- `R3_NULL_BENCHMARK_ENABLED` = `True`
- `R3_NULL_BENCHMARK_TARGET_RPS` = `50.0`
- `R3_NULL_BENCHMARK_DURATION_S` = `60`
- `R3_NULL_BENCHMARK_MIN_RPS` = `50.0`

## Exit Gates (Pass Matrix)

| Gate | Description | Status |
|------|-------------|--------|
| EG-R3-0 | Truth anchor & clean room | PASS |
| EG3.1 | PII stripping before persistence (PIIStorm @ N=1000) | PASS |
| EG3.2 | Idempotency at persistence boundary (Replay + CrossTenant) | PASS |
| EG3.3 | Deterministic malformed/PII DLQ routing | PASS |
| EG3.4 Test 1 | Month 6 profile (29 rps, 60s, p95 < 2s) | PASS |
| EG3.4 Test 2 | Month 18 profile (46 rps, 60s, p95 < 2s) | PASS |
| EG3.4 Test 3 | Sustained ops (5 rps, 300s, no degradation) | PASS |
| EG3.5 | Measurement validity null benchmark (>=50 rps, 60s) | PASS |
| EG-R3-7 | Channel alias normalization sanity | PASS |

## Key Verdicts

Max ladder step detected: `N=1000`

### S1 ReplayStorm
```json
{
  "CANONICAL_ROWS_FOR_KEY": 1,
  "DLQ_ROWS_FOR_KEY": 0,
  "HTTP_5XX_COUNT": 0,
  "HTTP_CONNECTION_ERRORS": 0,
  "HTTP_TIMEOUT_COUNT": 0,
  "http_status_counts": {
    "200": 1000
  },
  "passed": true
}
```

### S3 MalformedStorm
```json
{
  "CANONICAL_ROWS_CREATED": 0,
  "DLQ_ROWS_CREATED": 1000,
  "HTTP_5XX_COUNT": 0,
  "HTTP_CONNECTION_ERRORS": 0,
  "HTTP_TIMEOUT_COUNT": 0,
  "http_status_counts": {
    "200": 1000
  },
  "passed": true
}
```

### S4 PIIStorm
```json
{
  "CANONICAL_ROWS_CREATED": 1000,
  "DLQ_ROWS_CREATED": 0,
  "HTTP_5XX_COUNT": 0,
  "HTTP_CONNECTION_ERRORS": 0,
  "HTTP_TIMEOUT_COUNT": 0,
  "PII_KEY_HIT_COUNT_IN_DB": 0,
  "attribution_events_raw_payload_hits": 0,
  "dead_events_raw_payload_hits": 0,
  "http_status_counts": {
    "200": 1000
  },
  "passed": true
}
```

### S6 MixedStorm
```json
{
  "HTTP_5XX_COUNT": 0,
  "HTTP_CONNECTION_ERRORS": 0,
  "HTTP_TIMEOUT_COUNT": 0,
  "MALFORMED_DLQ_ROWS_CREATED": 100,
  "REPLAY_CANONICAL_ROWS_FOR_KEY": 1,
  "UNIQUE_CANONICAL_ROWS_CREATED": 300,
  "http_status_counts": {
    "200": 1100
  },
  "passed": true
}
```

### EG3.5 Null Benchmark
```json
{
  "achieved_rps": 50.0,
  "client_drain_s": 0.0,
  "client_stack": "httpx.AsyncClient",
  "concurrency_model": "asyncio-semaphore",
  "duration_s": 60,
  "effective_elapsed_s": 60.0,
  "elapsed_s": 59.99,
  "http_connection_errors": 0,
  "http_error_count": 0,
  "http_status_counts": {
    "200": 3000
  },
  "http_timeout_count": 0,
  "jitter_allowance_s": 0.12,
  "latency_p50_ms": 2.466,
  "latency_p95_ms": 6.965,
  "measurement_valid": true,
  "minimum_required_rps": 50.0,
  "observed_request_count": 3000,
  "passed": true,
  "reason": "ok",
  "semaphore_wait_max_ms": 5.033,
  "semaphore_wait_p50_ms": 0.04,
  "semaphore_wait_p95_ms": 0.059,
  "send_lag_max_ms": 5.586,
  "send_lag_over_1000ms_count": 0,
  "send_lag_p50_ms": 0.775,
  "send_lag_p95_ms": 2.108,
  "target_request_count": 3000,
  "target_rps": 50.0
}
```

### EG3.4 Test1 Month6
```json
{
  "achieved_rps": 28.985,
  "attribution_events_raw_payload_hits": 0,
  "canonical_rows_for_all_profile_keys": 1132,
  "client_drain_s": 0.0307,
  "db_activity_trace": [
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 41,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 2,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -0.00019,
          "n": 1,
          "query_head": "COMMIT",
          "wait_event": "ClientRead"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 41,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 2,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -0.000108,
          "n": 1,
          "query_head": " INSERT INTO public.b23_match_task_dispatches ( tenant_id, webhook_ingress_identity_id, task_id, task_name, queue, routi",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.000727,
          "n": 1,
          "query_head": "INSERT INTO public.attribution_events (id, occurred_at, external_event_id, correlation_id, session_id, revenue_cents, ra",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 32,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_ingress",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.002333,
          "n": 1,
          "query_head": "SELECT public.b26_p2_authenticate_ingress_atomic_v2( $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 32,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 41,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 41,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 2,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 41,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 2,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.00022,
          "n": 1,
          "query_head": "INSERT INTO public.attribution_events (id, occurred_at, external_event_id, correlation_id, session_id, revenue_cents, ra",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 41,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.000957,
          "n": 1,
          "query_head": " SELECT i.id, i.provider, i.provider_native_event_reference, i.provider_native_commerce_reference, i.normalized_commerce",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 41,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -4.6e-05,
          "n": 1,
          "query_head": "UPDATE public.b26_p2_execution_outbox SET state = 'published', updated_at = now() WHERE dispatch_task_id = $1",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 5.5e-05,
          "n": 1,
          "query_head": "COMMIT;",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 5.8e-05,
          "n": 1,
          "query_head": "COMMIT;",
          "wait_event": "WALSync"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 32,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_ingress",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.002279,
          "n": 1,
          "query_head": "SELECT public.b26_p2_authenticate_ingress_atomic_v2( $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    }
  ],
  "dead_events_raw_payload_hits": 0,
  "dlq_rows_for_all_profile_keys": 174,
  "duplicate_canonical_keys_in_window": 0,
  "duration_s": 60,
  "elapsed_s": 60.0307,
  "expected_canonical_rows_for_all_profile_keys": 1132,
  "expected_dlq_rows_for_all_profile_keys": 174,
  "host_after": {
    "cpu_stat": [
      36420,
      2,
      7404,
      374417,
      1651,
      0,
      1936,
      0,
      0,
      0
    ],
    "loadavg": [
      "1.55",
      "1.14",
      "0.51",
      "1/375",
      "3952"
    ],
    "mem_available_kb": 14377100,
    "pressure": {
      "cpu": "some avg10=1.90 avg60=3.28 avg300=4.54 total=32946157\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0",
      "io": "some avg10=0.00 avg60=0.08 avg300=0.56 total=8001434\nfull avg10=0.00 avg60=0.08 avg300=0.54 total=7060831",
      "memory": "some avg10=0.00 avg60=0.00 avg300=0.00 total=93\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=93"
    }
  },
  "host_before": {
    "cpu_stat": [
      30743,
      2,
      6318,
      358495,
      1576,
      0,
      1437,
      0,
      0,
      0
    ],
    "loadavg": [
      "1.20",
      "0.98",
      "0.42",
      "1/378",
      "3691"
    ],
    "mem_available_kb": 14385124,
    "pressure": {
      "cpu": "some avg10=0.04 avg60=6.01 avg300=5.21 total=31666988\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0",
      "io": "some avg10=0.00 avg60=0.24 avg300=0.69 total=7789802\nfull avg10=0.00 avg60=0.23 avg300=0.68 total=6859634",
      "memory": "some avg10=0.00 avg60=0.00 avg300=0.00 total=93\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=93"
    }
  },
  "host_cpu_busy_percent": 31.222,
  "host_pressure_avg10_max": 1.9,
  "http_connection_errors": 0,
  "http_error_count": 0,
  "http_error_rate_percent": 0.0,
  "http_status_counts": {
    "200": 1740
  },
  "http_timeout_count": 0,
  "latency_first_half_p95_ms": null,
  "latency_p50_ms": 57.653,
  "latency_p95_ms": 74.305,
  "latency_p99_ms": 84.327,
  "latency_second_half_p95_ms": null,
  "malformed_dlq_rows_created": 174,
  "no_degradation_over_time": true,
  "observed_request_count": 1740,
  "passed": true,
  "pii_canonical_rows_created": 174,
  "pii_dlq_rows_created": 0,
  "pii_key_hit_count_in_db": 0,
  "replay_canonical_rows_for_key": 1,
  "resource_snapshot_after": {
    "active_connections": 1,
    "app_user_connections": 43,
    "max_connections": 100,
    "total_connections": 77,
    "waiting_connections": 0
  },
  "resource_snapshot_before": {
    "active_connections": 1,
    "app_user_connections": 43,
    "max_connections": 100,
    "total_connections": 77,
    "waiting_connections": 0
  },
  "resource_stable": true,
  "semaphore_wait_max_ms": 3.444,
  "semaphore_wait_p50_ms": 0.05,
  "semaphore_wait_p95_ms": 0.087,
  "send_lag_max_ms": 4.175,
  "send_lag_over_1000ms_count": 0,
  "send_lag_p50_ms": 0.755,
  "send_lag_p95_ms": 1.663,
  "target_request_count": 1740,
  "target_rps": 29.0,
  "unique_canonical_rows_created": 957,
  "window_canonical_rows": 1132,
  "window_dlq_rows": 174,
  "window_end_utc": "2026-11-08T14:01:08.905629+00:00",
  "window_start_utc": "2026-11-08T14:00:08.846028+00:00"
}
```

### EG3.4 Test2 Month18
```json
{
  "achieved_rps": 45.964,
  "attribution_events_raw_payload_hits": 0,
  "canonical_rows_for_all_profile_keys": 1795,
  "client_drain_s": 0.0469,
  "db_activity_trace": [
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 40,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 3,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.000225,
          "n": 1,
          "query_head": " INSERT INTO public.b26_p2_task_authority_directory ( task_id, tenant_id, webhook_ingress_identity_id, window_start, win",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 41,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 32,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 32,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.001437,
          "n": 1,
          "query_head": "SELECT public.b26_p2_authenticate_ingress_atomic_v2( $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 41,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 2,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -5.4e-05,
          "n": 1,
          "query_head": "BEGIN;",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 41,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 2,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 41,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 2,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 32,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_ingress",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.004493,
          "n": 1,
          "query_head": "SELECT public.b26_p2_authenticate_ingress_atomic_v2( $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 32,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.00032,
          "n": 1,
          "query_head": " INSERT INTO public.b24_dirty_events ( tenant_id, model_type, model_version, source_window_start, source_window_end, dir",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 41,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 40,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 3,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -4.8e-05,
          "n": 1,
          "query_head": " SELECT * FROM security.resolve_tenant_webhook_secrets($1) ",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 41,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 32,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 2,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_ingress",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.005802,
          "n": 1,
          "query_head": "SELECT public.b26_p2_authenticate_ingress_atomic_v2( $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 41,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.000376,
          "n": 1,
          "query_head": "BEGIN;",
          "wait_event": "-"
        },
        {
          "max_query_s": 0.001197,
          "n": 1,
          "query_head": " INSERT INTO public.b23_match_task_dispatches ( tenant_id, webhook_ingress_identity_id, task_id, task_name, queue, routi",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 32,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -4.2e-05,
          "n": 1,
          "query_head": "SELECT public.webhook_ingress_identities.id, public.webhook_ingress_identities.event_id, public.webhook_ingress_identiti",
          "wait_event": "ClientRead"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 41,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -8e-05,
          "n": 1,
          "query_head": "INSERT INTO public.webhook_ingress_identities (id, event_id, provider, provider_native_event_reference, provider_native_",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 32,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_ingress",
          "wait_event": "WALSync",
          "wait_type": "IO"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 41,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -1.8e-05,
          "n": 1,
          "query_head": " SELECT * FROM security.resolve_tenant_webhook_secrets($1) ",
          "wait_event": "-"
        },
        {
          "max_query_s": 4.3e-05,
          "n": 1,
          "query_head": "UPDATE public.b23_match_task_dispatches SET delivery_state = 'published', publish_attempts = publish_attempts + 1, updat",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 41,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 2,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    }
  ],
  "dead_events_raw_payload_hits": 0,
  "dlq_rows_for_all_profile_keys": 276,
  "duplicate_canonical_keys_in_window": 0,
  "duration_s": 60,
  "elapsed_s": 60.0469,
  "expected_canonical_rows_for_all_profile_keys": 1795,
  "expected_dlq_rows_for_all_profile_keys": 276,
  "host_after": {
    "cpu_stat": [
      46454,
      2,
      9191,
      384782,
      1748,
      0,
      2667,
      0,
      0,
      0
    ],
    "loadavg": [
      "2.02",
      "1.34",
      "0.62",
      "1/370",
      "4214"
    ],
    "mem_available_kb": 14356628,
    "pressure": {
      "cpu": "some avg10=8.97 avg60=6.53 avg300=5.21 total=38190070\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0",
      "io": "some avg10=0.00 avg60=0.02 avg300=0.45 total=8314680\nfull avg10=0.00 avg60=0.02 avg300=0.43 total=7319526",
      "memory": "some avg10=0.00 avg60=0.00 avg300=0.00 total=93\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=93"
    }
  },
  "host_before": {
    "cpu_stat": [
      36424,
      2,
      7404,
      374429,
      1651,
      0,
      1937,
      0,
      0,
      0
    ],
    "loadavg": [
      "1.55",
      "1.14",
      "0.51",
      "1/375",
      "3952"
    ],
    "mem_available_kb": 14376876,
    "pressure": {
      "cpu": "some avg10=1.90 avg60=3.28 avg300=4.54 total=32946388\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0",
      "io": "some avg10=0.00 avg60=0.08 avg300=0.56 total=8001445\nfull avg10=0.00 avg60=0.08 avg300=0.54 total=7060842",
      "memory": "some avg10=0.00 avg60=0.00 avg300=0.00 total=93\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=93"
    }
  },
  "host_cpu_busy_percent": 54.559,
  "host_pressure_avg10_max": 8.97,
  "http_connection_errors": 0,
  "http_error_count": 0,
  "http_error_rate_percent": 0.0,
  "http_status_counts": {
    "200": 2760
  },
  "http_timeout_count": 0,
  "latency_first_half_p95_ms": null,
  "latency_p50_ms": 67.576,
  "latency_p95_ms": 105.004,
  "latency_p99_ms": 136.863,
  "latency_second_half_p95_ms": null,
  "malformed_dlq_rows_created": 276,
  "no_degradation_over_time": true,
  "observed_request_count": 2760,
  "passed": true,
  "pii_canonical_rows_created": 276,
  "pii_dlq_rows_created": 0,
  "pii_key_hit_count_in_db": 0,
  "replay_canonical_rows_for_key": 1,
  "resource_snapshot_after": {
    "active_connections": 1,
    "app_user_connections": 43,
    "max_connections": 100,
    "total_connections": 77,
    "waiting_connections": 0
  },
  "resource_snapshot_before": {
    "active_connections": 1,
    "app_user_connections": 43,
    "max_connections": 100,
    "total_connections": 77,
    "waiting_connections": 0
  },
  "resource_stable": true,
  "semaphore_wait_max_ms": 6.877,
  "semaphore_wait_p50_ms": 0.053,
  "semaphore_wait_p95_ms": 0.098,
  "send_lag_max_ms": 17.782,
  "send_lag_over_1000ms_count": 0,
  "send_lag_p50_ms": 0.776,
  "send_lag_p95_ms": 1.821,
  "target_request_count": 2760,
  "target_rps": 46.0,
  "unique_canonical_rows_created": 1518,
  "window_canonical_rows": 1795,
  "window_dlq_rows": 276,
  "window_end_utc": "2026-11-08T14:02:09.033561+00:00",
  "window_start_utc": "2026-11-08T14:01:08.945921+00:00"
}
```

### EG3.4 Test3 SustainedOps
```json
{
  "achieved_rps": 5.002,
  "attribution_events_raw_payload_hits": 0,
  "canonical_rows_for_all_profile_keys": 976,
  "client_drain_s": 0.0,
  "db_activity_trace": [
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -6.8e-05,
          "n": 1,
          "query_head": "INSERT INTO public.ephemeral_order_resolution (id, order_id, session_id, observed_at, expires_at, source, tenant_id, cre",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 32,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -4.3e-05,
          "n": 1,
          "query_head": "UPDATE public.webhook_ingress_identities SET verified_commerce_ingress_state=$1::VARCHAR WHERE public.webhook_ingress_id",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 32,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_ingress",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.001068,
          "n": 1,
          "query_head": "SELECT public.b26_p2_authenticate_ingress_atomic_v2( $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -3.5e-05,
          "n": 1,
          "query_head": " INSERT INTO public.b23_match_task_dispatches ( tenant_id, webhook_ingress_identity_id, task_id, task_name, queue, routi",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 32,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -0.000412,
          "n": 1,
          "query_head": "SELECT public.b26_p2_authenticate_ingress_atomic_v2( $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "idle in transaction",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 42,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "app_user",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "application_name": "",
          "n": 43,
          "state": "idle",
          "usename": "app_user",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 33,
          "state": "idle",
          "usename": "app_ingress",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "application_name": "",
          "n": 1,
          "state": "active",
          "usename": "r3",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    }
  ],
  "dead_events_raw_payload_hits": 0,
  "dlq_rows_for_all_profile_keys": 150,
  "duplicate_canonical_keys_in_window": 0,
  "duration_s": 300,
  "elapsed_s": 299.8516,
  "expected_canonical_rows_for_all_profile_keys": 976,
  "expected_dlq_rows_for_all_profile_keys": 150,
  "host_after": {
    "cpu_stat": [
      51414,
      2,
      10393,
      496959,
      1827,
      0,
      3121,
      0,
      0,
      0
    ],
    "loadavg": [
      "0.03",
      "0.50",
      "0.44",
      "1/371",
      "5493"
    ],
    "mem_available_kb": 14313956,
    "pressure": {
      "cpu": "some avg10=0.00 avg60=0.03 avg300=1.85 total=39399530\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0",
      "io": "some avg10=0.00 avg60=0.00 avg300=0.13 total=8569498\nfull avg10=0.00 avg60=0.00 avg300=0.13 total=7570243",
      "memory": "some avg10=0.00 avg60=0.00 avg300=0.00 total=93\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=93"
    }
  },
  "host_before": {
    "cpu_stat": [
      46459,
      2,
      9192,
      384796,
      1748,
      0,
      2667,
      0,
      0,
      0
    ],
    "loadavg": [
      "2.02",
      "1.34",
      "0.62",
      "1/370",
      "4214"
    ],
    "mem_available_kb": 14356404,
    "pressure": {
      "cpu": "some avg10=8.97 avg60=6.53 avg300=5.21 total=38190233\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0",
      "io": "some avg10=0.00 avg60=0.02 avg300=0.45 total=8314684\nfull avg10=0.00 avg60=0.02 avg300=0.43 total=7319531",
      "memory": "some avg10=0.00 avg60=0.00 avg300=0.00 total=93\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=93"
    }
  },
  "host_cpu_busy_percent": 5.562,
  "host_pressure_avg10_max": 0.0,
  "http_connection_errors": 0,
  "http_error_count": 0,
  "http_error_rate_percent": 0.0,
  "http_status_counts": {
    "200": 1500
  },
  "http_timeout_count": 0,
  "latency_first_half_p95_ms": 52.183,
  "latency_p50_ms": 46.947,
  "latency_p95_ms": 52.673,
  "latency_p99_ms": 57.616,
  "latency_second_half_p95_ms": 52.958,
  "malformed_dlq_rows_created": 150,
  "no_degradation_over_time": true,
  "observed_request_count": 1500,
  "passed": true,
  "pii_canonical_rows_created": 150,
  "pii_dlq_rows_created": 0,
  "pii_key_hit_count_in_db": 0,
  "replay_canonical_rows_for_key": 1,
  "resource_snapshot_after": {
    "active_connections": 1,
    "app_user_connections": 43,
    "max_connections": 100,
    "total_connections": 77,
    "waiting_connections": 0
  },
  "resource_snapshot_before": {
    "active_connections": 1,
    "app_user_connections": 43,
    "max_connections": 100,
    "total_connections": 77,
    "waiting_connections": 0
  },
  "resource_stable": true,
  "semaphore_wait_max_ms": 2.424,
  "semaphore_wait_p50_ms": 0.059,
  "semaphore_wait_p95_ms": 0.096,
  "send_lag_max_ms": 2.781,
  "send_lag_over_1000ms_count": 0,
  "send_lag_p50_ms": 0.902,
  "send_lag_p95_ms": 1.347,
  "target_request_count": 1500,
  "target_rps": 5.0,
  "unique_canonical_rows_created": 825,
  "window_canonical_rows": 976,
  "window_dlq_rows": 150,
  "window_end_utc": "2026-11-08T14:07:08.956309+00:00",
  "window_start_utc": "2026-11-08T14:02:09.081315+00:00"
}
```

## Where the Evidence Lives

- Workflow: `.github/workflows/r3-ingestion-under-fire.yml`
- Harness: `scripts/r3/ingestion_under_fire.py`
- Summary generator: `scripts/r3/render_r3_summary.py`

