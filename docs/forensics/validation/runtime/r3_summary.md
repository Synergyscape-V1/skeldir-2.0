# R3 Ingestion Under Fire Validation Summary (Truth Anchor)

## Status

R3 = **COMPLETE** as of:

- **Candidate SHA:** `a999aa43e348aab5f7dc35db89e0da31117299c0`
- **CI run:** https://github.com/Muk223/skeldir-2.0/actions/runs/20980408389
- **Generated at:** `2026-01-14T02:45:42.597302+00:00`

## Run Configuration (from harness log)

- `R3_API_BASE_URL` = `http://127.0.0.1:8000`
- `R3_LADDER` = `[50, 250, 1000]`
- `R3_CONCURRENCY` = `200`
- `R3_TIMEOUT_S` = `10.0`
- `RUN_START_UTC` = `2026-01-14T02:44:53.675636+00:00`

## Exit Gates (Pass Matrix)

| Gate | Description | Status |
|------|-------------|--------|
| EG-R3-0 | Truth anchor & clean room | PASS |
| EG-R3-1 | Idempotency under fire (ReplayStorm @ N=1000) | PASS |
| EG-R3-2 | Tenant-correct idempotency (CrossTenantCollision @ N=1000) | PASS |
| EG-R3-3 | DLQ reliability (MalformedStorm @ N=1000) | PASS |
| EG-R3-4 | PII self-defense (PIIStorm @ N=1000) | PASS |
| EG-R3-5 | MixedStorm stability (MixedStorm @ N=1000) | PASS |
| EG-R3-6 | Evidence pack present (verdict blocks for S1..S6) | PASS |

## Evidence (Browser-Verifiable Logs)

This run prints, to CI logs:

- One `R3_VERDICT_BEGIN/END` JSON block per scenario (S1..S6), per ladder step.
- DB truth checks (canonical/DLQ counts + PII key hit scan summaries).

## Key Verdicts (Max Ladder Step)

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

### S5 CrossTenantCollision
```json
{
  "HTTP_5XX_COUNT": 0,
  "HTTP_CONNECTION_ERRORS": 0,
  "HTTP_TIMEOUT_COUNT": 0,
  "TENANT_A_CANONICAL_ROWS_FOR_KEY": 1,
  "TENANT_B_CANONICAL_ROWS_FOR_KEY": 1,
  "http_status_counts": {
    "200": 2
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
  "CANONICAL_ROWS_CREATED": 0,
  "DLQ_ROWS_CREATED": 1000,
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

## Where the Evidence Lives

- Workflow: `.github/workflows/r3-ingestion-under-fire.yml`
- Harness: `scripts/r3/ingestion_under_fire.py`
- Summary generator: `scripts/r3/render_r3_summary.py`

