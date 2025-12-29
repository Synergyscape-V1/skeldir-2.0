# R5 Determinism + Scaling Summary (Truth Anchor)

## Status

R5 = **COMPLETE**.

- **Candidate SHA:** `7ab2779c9231322bab9f66f4e510cbbc9d049d88`
- **CI run:** https://github.com/Muk223/skeldir-2.0/actions/runs/20581466574
- **Last updated:** `2025-12-29`

## Exit Gates (R5)

- **EG-R5-1 (Determinism: sequential reruns):** PASS
- **EG-R5-2 (Determinism: concurrency invariance):** PASS
- **EG-R5-3 (Determinism: retry invariance):** PASS
- **EG-R5-4 (Complexity: 10k vs 100k ratios):** PASS
- **EG-R5-5 (Instrument integrity / anti-theater):** PASS
- **EG-R5-6 (Documentation anchoring):** PASS

## Evidence Policy

No artifact-only proofs. If the proof is not visible in the GitHub Actions run logs, it is inadmissible.

## Evidence (Browser-Verifiable Logs)

Log step: `Run R5 verification harness` in `.github/workflows/r5-remediation.yml`.

Proof lines observed in the CI logs for the run URL above:

### Truth Anchor

- `R5_SHA=7ab2779c9231322bab9f66f4e510cbbc9d049d88`
- `R5_RUN_URL=https://github.com/Muk223/skeldir-2.0/actions/runs/20581466574`

### DB Runtime Settings (as observed by harness)

- `R5_DB_SERVER_VERSION=16.11 (Debian 16.11-1.pgdg13+1)`
- `R5_DB_SHARED_BUFFERS=1GB`
- `R5_DB_WORK_MEM=32MB`
- `R5_DB_MAINTENANCE_WORK_MEM=256MB`
- `R5_DB_MAX_WAL_SIZE=4GB`
- `R5_DB_CHECKPOINT_TIMEOUT=30min`
- `R5_DB_CHECKPOINT_COMPLETION_TARGET=0.9`
- `R5_DB_WAL_LEVEL=minimal`
- `R5_DB_WAL_COMPRESSION=pglz`
- `R5_DB_FSYNC=off`
- `R5_DB_SYNCHRONOUS_COMMIT=off`
- `R5_DB_FULL_PAGE_WRITES=off`

### EG-R5-1 — Determinism: 3× Sequential Reruns

- `R5_RUN_MODE=serial R5_RUN_INDEX=1 R5_DETERMINISM_FULL_SHA256=de5f9134697cc0bc2fa8877171af1bcc63d69a630a3dffd3427ea1ed4ea0b4ad`
- `R5_RUN_MODE=serial R5_RUN_INDEX=2 R5_DETERMINISM_FULL_SHA256=de5f9134697cc0bc2fa8877171af1bcc63d69a630a3dffd3427ea1ed4ea0b4ad`
- `R5_RUN_MODE=serial R5_RUN_INDEX=3 R5_DETERMINISM_FULL_SHA256=de5f9134697cc0bc2fa8877171af1bcc63d69a630a3dffd3427ea1ed4ea0b4ad`

### EG-R5-2 — Determinism: Concurrency Invariance

- `R5_RUN_MODE=concurrency10 R5_CONCURRENCY_TARGET=10`
- `R5_RUN_MODE=concurrency10 R5_DETERMINISM_FULL_SHA256=0ab45e9a65c18161070f9ea5586b6a44e920aa127cb767459f9cf6d2afe7f2cd`
- `R5_RUN_MODE=post_concurrency_serial R5_DETERMINISM_FULL_SHA256=0ab45e9a65c18161070f9ea5586b6a44e920aa127cb767459f9cf6d2afe7f2cd`

### EG-R5-3 — Determinism: Retry Invariance (Retry Observed)

- `R5_RUN_MODE=retry_injected R5_RETRY_ATTEMPT=1`
- `R5_RETRY_INJECTED_FAILURE_CAUGHT=1 R5_ERROR=RuntimeError`
- `R5_RETRY_AFTER_FAIL_ALLOCATION_ROWS=0`
- `R5_RUN_MODE=retry_injected R5_RETRY_ATTEMPT=2`
- `R5_RUN_MODE=retry_injected R5_RETRY_OBSERVED=1 R5_DETERMINISM_FULL_SHA256=c8e6bd279cbebcec866c283a94e48f0a24075f0db3b91267f526d38803735740`
- `R5_RUN_MODE=post_retry_serial R5_DETERMINISM_FULL_SHA256=c8e6bd279cbebcec866c283a94e48f0a24075f0db3b91267f526d38803735740`

### EG-R5-4 — Complexity: 10k vs 100k Ratio Proof

- `R5_N=10000 R5_WALL_S=1.559293 R5_STATEMENTS_TOTAL=3 R5_PEAK_RSS_KB=119064`
- `R5_N=100000 R5_WALL_S=17.710344 R5_STATEMENTS_TOTAL=3 R5_PEAK_RSS_KB=394324`
- `R5_TIME_RATIO=11.357932`
- `R5_STMT_RATIO=1.0`
- `R5_PEAK_RSS_RATIO=3.311866`

