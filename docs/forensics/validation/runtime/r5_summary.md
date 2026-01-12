# R5 Determinism + Scaling Summary (Truth Anchor)

## Status

R5 = **COMPLETE**.

- **Candidate SHA:** `387ac2ff004b990d2c8a636d11fff0794a8be808`
- **CI run:** https://github.com/Muk223/skeldir-2.0/actions/runs/20582893787
- **Last updated:** `2025-12-29`

## Exit Gates (R5-FIX)

- **EG-R5-FIX-0 (Temporal coherence / SHA binding):** PASS
- **EG-R5-FIX-1 (Input binding enforcement):** PASS
- **EG-R5-FIX-2 (Baseline determinism):** PASS
- **EG-R5-FIX-3 (Concurrency invariance):** PASS
- **EG-R5-FIX-4 (Retry invariance):** PASS
- **EG-R5-FIX-5 (Hash authoritativeness):** PASS
- **EG-R5-FIX-6 (Complexity ratio):** PASS
- **EG-R5-FIX-7 (Documentation anchoring):** PASS

## Evidence Policy

No artifact-only proofs. If the proof is not visible in the GitHub Actions run logs, it is inadmissible.

## Evidence (Browser-Verifiable Logs)

Log step: `Run R5 verification harness` in `.github/workflows/r5-remediation.yml`.

Proof lines observed in the CI logs for the run URL above:

### Truth Anchor

- `R5_SHA=387ac2ff004b990d2c8a636d11fff0794a8be808`
- `R5_RUN_URL=https://github.com/Muk223/skeldir-2.0/actions/runs/20582893787`

### Input Binding (Same Dataset/Window Across Modes)

- `R5_RUN_MODE=serial R5_TENANT_ID=042f0a38-930e-5136-92c7-d36c336964c2 R5_DATASET_ID=sha256:bcbd2590bb78d4cde7105d228fa062f3593c8328de31854514b6688472dd5fd9 R5_WINDOW_START=2025-05-01T00:00:00+00:00 R5_WINDOW_END=2025-05-02T00:00:00+00:00`
- `R5_RUN_MODE=concurrency10 R5_TENANT_ID=042f0a38-930e-5136-92c7-d36c336964c2 R5_DATASET_ID=sha256:bcbd2590bb78d4cde7105d228fa062f3593c8328de31854514b6688472dd5fd9 R5_WINDOW_START=2025-05-01T00:00:00+00:00 R5_WINDOW_END=2025-05-02T00:00:00+00:00`
- `R5_RUN_MODE=retry_injected R5_TENANT_ID=042f0a38-930e-5136-92c7-d36c336964c2 R5_DATASET_ID=sha256:bcbd2590bb78d4cde7105d228fa062f3593c8328de31854514b6688472dd5fd9 R5_WINDOW_START=2025-05-01T00:00:00+00:00 R5_WINDOW_END=2025-05-02T00:00:00+00:00`

### EG-R5-FIX-2 — Baseline Determinism (3x Serial)

- `R5_RUN_MODE=serial R5_RUN_INDEX=1 R5_DETERMINISM_FULL_SHA256=703ad9fbac4e2289aa2e629a2aa8fca948b40827e144a94aac399ffa32e12b30`
- `R5_RUN_MODE=serial R5_RUN_INDEX=2 R5_DETERMINISM_FULL_SHA256=703ad9fbac4e2289aa2e629a2aa8fca948b40827e144a94aac399ffa32e12b30`
- `R5_RUN_MODE=serial R5_RUN_INDEX=3 R5_DETERMINISM_FULL_SHA256=703ad9fbac4e2289aa2e629a2aa8fca948b40827e144a94aac399ffa32e12b30`
- `R5_BASELINE_SHA256=703ad9fbac4e2289aa2e629a2aa8fca948b40827e144a94aac399ffa32e12b30`

### EG-R5-FIX-3 — Concurrency Invariance (Observed)

- `R5_RUN_MODE=concurrency10 R5_CONCURRENCY_TARGET=10`
- `R5_RUN_MODE=concurrency10 R5_CONCURRENCY_TASKS=10 R5_CONCURRENCY_OVERLAP=9`
- `R5_RUN_MODE=concurrency10 R5_DETERMINISM_FULL_SHA256=703ad9fbac4e2289aa2e629a2aa8fca948b40827e144a94aac399ffa32e12b30`
- `R5_CONC_SHA256=703ad9fbac4e2289aa2e629a2aa8fca948b40827e144a94aac399ffa32e12b30`

### EG-R5-FIX-4 — Retry Invariance (Retry Observed)

- `R5_RUN_MODE=retry_injected R5_RETRY_ATTEMPT=1`
- `R5_RETRY_INJECTED_FAILURE_CAUGHT=1 R5_ERROR=RuntimeError`
- `R5_RUN_MODE=retry_injected R5_RETRY_ATTEMPT=2`
- `R5_RUN_MODE=retry_injected R5_RETRY_OBSERVED=1 R5_RETRY_ATTEMPTS_TOTAL=2 R5_DETERMINISM_FULL_SHA256=703ad9fbac4e2289aa2e629a2aa8fca948b40827e144a94aac399ffa32e12b30`
- `R5_RETRY_SHA256=703ad9fbac4e2289aa2e629a2aa8fca948b40827e144a94aac399ffa32e12b30`

### EG-R5-FIX-6 — Complexity Ratios (10k vs 100k)

- `R5_N=10000 R5_EVENTS_INGESTED=10000 R5_EVENTS_PROCESSED=10000 R5_WALL_S=1.566493 R5_STATEMENTS_TOTAL=3 R5_PEAK_RSS_KB=111704`
- `R5_N=100000 R5_EVENTS_INGESTED=100000 R5_EVENTS_PROCESSED=100000 R5_WALL_S=17.346274 R5_STATEMENTS_TOTAL=3 R5_PEAK_RSS_KB=368140`
- `R5_TIME_RATIO=11.073317`
- `R5_STMT_RATIO=1.0`
- `R5_PEAK_RSS_RATIO=3.295674`
