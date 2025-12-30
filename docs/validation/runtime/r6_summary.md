# R6 Worker Resource Governance Summary

Candidate SHA: 8c4fc7d0b2d861c5cd2126dbf2bc68f76f39c8ae
CI Run URL: https://github.com/Muk223/skeldir-2.0/actions/runs/20602935171

## Evidence Location (browser-visible only)

All evidence is printed directly in CI logs for the run above.

Key log markers:
- SHA guard: `R6_GITHUB_SHA=...`, `R6_GIT_SHA=...`
- Script SHA: `R6_SHA=...` / `R6_GIT_SHA=...` / `R6_GITHUB_SHA=...`
- Runtime dumps: `R6_RUNTIME_SNAPSHOT_JSON_BEGIN` / `R6_RUNTIME_SNAPSHOT_JSON_END`
- Probes: `R6_PROBE_TIMEOUT_JSON_BEGIN`, `R6_PROBE_RETRY_JSON_BEGIN`, `R6_PROBE_PREFETCH_JSON_BEGIN`, `R6_PROBE_RECYCLE_JSON_BEGIN`
- Verification verdicts: `R6_VERIFY_*`

## Gate Outcomes

- EG-R6-FIX-0 (Temporal coherence & measurement integrity): PASS
  - Evidence: `R6_GITHUB_SHA`, `R6_GIT_SHA`, `R6_SHA` all match in logs; `R6_VERIFY_SHA_OK`.
- EG-R6-FIX-1 (Runtime envelope bounded): PASS
  - Evidence: `R6_VERIFY_BOUNDS soft=300 hard=360 max_tasks=1 max_mem=200000 prefetch=1`.
- EG-R6-FIX-2 (Timeout enforcement observed): PASS
  - Evidence: `R6_VERIFY_TIMEOUT_OK` with `soft_limit_observed=true` and `hard_limit_observed=true` in `R6_PROBE_TIMEOUT_JSON`.
- EG-R6-FIX-3 (Retry boundedness observed): PASS
  - Evidence: `R6_VERIFY_RETRY_OK attempts=[0, 1, 2] terminal_state=FAILURE`.
- EG-R6-FIX-4 (Recycling enforcement observed): PASS
  - Evidence: `R6_VERIFY_RECYCLE_OK unique_pids=3`.
- EG-R6-FIX-5 (Anti-thrash behavior observed): PASS
  - Evidence: `R6_VERIFY_PREFETCH_OK max_wait=... threshold=20.0`.
- EG-R6-FIX-6 (celery.chord_unlock bounded): PASS
  - Evidence: `R6_VERIFY_CHORD_UNLOCK max_retries=5 delay=2 backoff=True jitter=True`.
- EG-R6-FIX-7 (No-artifact compliance): PASS
  - Evidence: all proofs above are in CI logs; no artifact download required.
