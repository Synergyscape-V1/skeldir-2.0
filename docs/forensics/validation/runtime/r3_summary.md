# R3 Ingestion Under Fire Validation Summary (Truth Anchor)

## Status

R3 = **COMPLETE** as of:

- **Candidate SHA:** `8216b6cc52d46bbd553d69ae189193deb5b9b7cf`
- **CI run:** https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/39311809280
- **Generated at:** `2026-10-19T19:44:14.434006+00:00`
- **Measurement validity (EG3.5):** `VALID`

## Run Configuration (from harness log)

- `R3_API_BASE_URL` = `http://127.0.0.1:8000`
- `R3_LADDER` = `[50, 250, 1000]`
- `R3_CONCURRENCY` = `200`
- `R3_TIMEOUT_S` = `10.0`
- `RUN_START_UTC` = `2026-10-19T19:34:17.943885+00:00`
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
    "200": 1000,
    "request_error_recovered": 1
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
    "200": 1000,
    "request_error_recovered": 1
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
    "200": 1100,
    "request_error_recovered": 5
  },
  "passed": true
}
```

### EG3.5 Null Benchmark
```json
{
  "achieved_rps": 50.0,
  "client_drain_s": 0.0028,
  "client_stack": "httpx.AsyncClient",
  "concurrency_model": "asyncio-semaphore",
  "duration_s": 60,
  "effective_elapsed_s": 60.0,
  "elapsed_s": 60.0028,
  "http_connection_errors": 0,
  "http_error_count": 0,
  "http_status_counts": {
    "200": 3000
  },
  "http_timeout_count": 0,
  "jitter_allowance_s": 0.12,
  "latency_p50_ms": 2.125,
  "latency_p95_ms": 14.967,
  "measurement_valid": true,
  "minimum_required_rps": 50.0,
  "observed_request_count": 3000,
  "passed": true,
  "reason": "ok",
  "semaphore_wait_max_ms": 16.813,
  "semaphore_wait_p50_ms": 0.03,
  "semaphore_wait_p95_ms": 0.035,
  "send_lag_max_ms": 18.315,
  "send_lag_over_1000ms_count": 0,
  "send_lag_p50_ms": 0.953,
  "send_lag_p95_ms": 2.045,
  "target_request_count": 3000,
  "target_rps": 50.0
}
```

### EG3.4 Test1 Month6
```json
{
  "achieved_rps": 28.988,
  "attribution_events_raw_payload_hits": 0,
  "canonical_rows_for_all_profile_keys": 1132,
  "client_drain_s": 0.0254,
  "db_activity_trace": [
    {
      "groups": [
        {
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 68,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "active",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 3.2e-05,
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.00199,
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -1e-05,
          "n": 1,
          "query_head": "INSERT INTO kombu_message (id, visible, timestamp, payload, version, queue_id) VALUES (nextval('message_id_sequence'), t",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.00012,
          "n": 1,
          "query_head": " SELECT * FROM security.resolve_tenant_webhook_secrets($1) ",
          "wait_event": "ClientRead"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -3.2e-05,
          "n": 1,
          "query_head": " INSERT INTO public.b26_p2_execution_outbox ( tenant_id, dispatch_task_id, webhook_ingress_identity_id, state, publish_a",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "n": 68,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 68,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 68,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -1.4e-05,
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 7.2e-05,
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 68,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 68,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
  "elapsed_s": 60.0254,
  "expected_canonical_rows_for_all_profile_keys": 1132,
  "expected_dlq_rows_for_all_profile_keys": 174,
  "http_connection_errors": 0,
  "http_error_count": 0,
  "http_error_rate_percent": 0.0,
  "http_status_counts": {
    "200": 1740
  },
  "http_timeout_count": 0,
  "latency_first_half_p95_ms": null,
  "latency_p50_ms": 47.192,
  "latency_p95_ms": 55.723,
  "latency_p99_ms": 66.796,
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
    "total_connections": 71,
    "waiting_connections": 0
  },
  "resource_snapshot_before": {
    "active_connections": 1,
    "app_user_connections": 43,
    "max_connections": 100,
    "total_connections": 71,
    "waiting_connections": 0
  },
  "resource_stable": true,
  "semaphore_wait_max_ms": 4.652,
  "semaphore_wait_p50_ms": 0.04,
  "semaphore_wait_p95_ms": 0.063,
  "send_lag_max_ms": 5.561,
  "send_lag_over_1000ms_count": 0,
  "send_lag_p50_ms": 0.731,
  "send_lag_p95_ms": 1.725,
  "target_request_count": 1740,
  "target_rps": 29.0,
  "unique_canonical_rows_created": 957,
  "window_canonical_rows": 1132,
  "window_dlq_rows": 174,
  "window_end_utc": "2026-10-19T19:38:14.164916+00:00",
  "window_start_utc": "2026-10-19T19:37:14.111810+00:00"
}
```

### EG3.4 Test2 Month18
```json
{
  "achieved_rps": 45.951,
  "attribution_events_raw_payload_hits": 0,
  "canonical_rows_for_all_profile_keys": 1795,
  "client_drain_s": 0.0644,
  "db_activity_trace": [
    {
      "groups": [
        {
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "WALSync",
          "wait_type": "IO"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -7e-06,
          "n": 1,
          "query_head": " SELECT * FROM security.resolve_tenant_webhook_secrets($1) ",
          "wait_event": "-"
        },
        {
          "max_query_s": 0.001642,
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.000682,
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 67,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "WALSync",
          "wait_type": "IO"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.006642,
          "n": 1,
          "query_head": "COMMIT",
          "wait_event": "WALSync"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 68,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 67,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 3,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.000374,
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 68,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 66,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 4,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 68,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -2.5e-05,
          "n": 1,
          "query_head": "SELECT public.attribution_events.id, public.attribution_events.occurred_at, public.attribution_events.external_event_id,",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "n": 67,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.002137,
          "n": 1,
          "query_head": "SELECT public.b26_p2_authenticate_ingress_atomic_v2( $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)",
          "wait_event": "-"
        },
        {
          "max_query_s": 0.00034,
          "n": 1,
          "query_head": "UPDATE public.webhook_ingress_identities SET verified_commerce_ingress_state=$1::VARCHAR WHERE public.webhook_ingress_id",
          "wait_event": "ClientRead"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "n": 65,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 3,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.003728,
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
          "n": 64,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 3,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "WALSync",
          "wait_type": "IO"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 66,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 2,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.007219,
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
          "n": 66,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 4,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 67,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -4.1e-05,
          "n": 1,
          "query_head": " SELECT * FROM security.resolve_tenant_webhook_secrets($1) ",
          "wait_event": "-"
        },
        {
          "max_query_s": 0.000266,
          "n": 1,
          "query_head": "SELECT public.b26_p2_authenticate_ingress_atomic_v2( $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)",
          "wait_event": "-"
        },
        {
          "max_query_s": 0.000349,
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
          "n": 67,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 2,
          "state": "idle in transaction",
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
          "n": 66,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 3,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 61,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 4,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 4,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "WALSync",
          "wait_type": "IO"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "WALWrite",
          "wait_type": "LWLock"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.002847,
          "n": 1,
          "query_head": "COMMIT;",
          "wait_event": "-"
        },
        {
          "max_query_s": 0.009896,
          "n": 1,
          "query_head": "SELECT public.b26_p2_authenticate_ingress_atomic_v2( $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)",
          "wait_event": "-"
        },
        {
          "max_query_s": 0.001936,
          "n": 1,
          "query_head": "COMMIT;",
          "wait_event": "WALWrite"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.003317,
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
          "n": 66,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 2,
          "state": "active",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.000147,
          "n": 1,
          "query_head": " INSERT INTO public.b23_match_task_dispatches ( tenant_id, webhook_ingress_identity_id, task_id, task_name, queue, routi",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    }
  ],
  "dead_events_raw_payload_hits": 0,
  "dlq_rows_for_all_profile_keys": 276,
  "duplicate_canonical_keys_in_window": 0,
  "duration_s": 60,
  "elapsed_s": 60.0644,
  "expected_canonical_rows_for_all_profile_keys": 1795,
  "expected_dlq_rows_for_all_profile_keys": 276,
  "http_connection_errors": 0,
  "http_error_count": 0,
  "http_error_rate_percent": 0.0,
  "http_status_counts": {
    "200": 2760
  },
  "http_timeout_count": 0,
  "latency_first_half_p95_ms": null,
  "latency_p50_ms": 69.235,
  "latency_p95_ms": 149.682,
  "latency_p99_ms": 242.781,
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
    "total_connections": 71,
    "waiting_connections": 0
  },
  "resource_snapshot_before": {
    "active_connections": 1,
    "app_user_connections": 43,
    "max_connections": 100,
    "total_connections": 71,
    "waiting_connections": 0
  },
  "resource_stable": true,
  "semaphore_wait_max_ms": 6.417,
  "semaphore_wait_p50_ms": 0.044,
  "semaphore_wait_p95_ms": 0.093,
  "send_lag_max_ms": 6.617,
  "send_lag_over_1000ms_count": 0,
  "send_lag_p50_ms": 0.791,
  "send_lag_p95_ms": 1.934,
  "target_request_count": 2760,
  "target_rps": 46.0,
  "unique_canonical_rows_created": 1518,
  "window_canonical_rows": 1795,
  "window_dlq_rows": 276,
  "window_end_utc": "2026-10-19T19:39:14.311082+00:00",
  "window_start_utc": "2026-10-19T19:38:14.204713+00:00"
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "active",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "active",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": 0.00046,
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
          "wait_event": "WALWrite",
          "wait_type": "IO"
        }
      ],
      "holding_queries": [],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -0.000277,
          "n": 1,
          "query_head": "ROLLBACK;",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
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
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
          "wait_event": "-",
          "wait_type": "-"
        },
        {
          "n": 1,
          "state": "idle in transaction",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        }
      ],
      "holding_queries": [
        {
          "max_query_s": -1.7e-05,
          "n": 1,
          "query_head": "INSERT INTO kombu_message (id, visible, timestamp, payload, version, queue_id) VALUES (nextval('message_id_sequence'), t",
          "wait_event": "-"
        }
      ],
      "long_open_xact_count": 0
    },
    {
      "groups": [
        {
          "n": 69,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 2,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
          "n": 70,
          "state": "idle",
          "wait_event": "ClientRead",
          "wait_type": "Client"
        },
        {
          "n": 1,
          "state": "active",
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
  "elapsed_s": 299.8521,
  "expected_canonical_rows_for_all_profile_keys": 976,
  "expected_dlq_rows_for_all_profile_keys": 150,
  "http_connection_errors": 0,
  "http_error_count": 0,
  "http_error_rate_percent": 0.0,
  "http_status_counts": {
    "200": 1500
  },
  "http_timeout_count": 0,
  "latency_first_half_p95_ms": 48.99,
  "latency_p50_ms": 45.556,
  "latency_p95_ms": 51.759,
  "latency_p99_ms": 57.429,
  "latency_second_half_p95_ms": 53.251,
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
    "total_connections": 71,
    "waiting_connections": 0
  },
  "resource_snapshot_before": {
    "active_connections": 1,
    "app_user_connections": 43,
    "max_connections": 100,
    "total_connections": 71,
    "waiting_connections": 0
  },
  "resource_stable": true,
  "semaphore_wait_max_ms": 2.938,
  "semaphore_wait_p50_ms": 0.055,
  "semaphore_wait_p95_ms": 0.095,
  "send_lag_max_ms": 3.947,
  "send_lag_over_1000ms_count": 0,
  "send_lag_p50_ms": 0.883,
  "send_lag_p95_ms": 1.331,
  "target_request_count": 1500,
  "target_rps": 5.0,
  "unique_canonical_rows_created": 825,
  "window_canonical_rows": 976,
  "window_dlq_rows": 150,
  "window_end_utc": "2026-10-19T19:44:14.231628+00:00",
  "window_start_utc": "2026-10-19T19:39:14.356924+00:00"
}
```

## Where the Evidence Lives

- Workflow: `.github/workflows/r3-ingestion-under-fire.yml`
- Harness: `scripts/r3/ingestion_under_fire.py`
- Summary generator: `scripts/r3/render_r3_summary.py`

