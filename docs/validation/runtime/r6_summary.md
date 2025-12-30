# R6 Worker Resource Governance Summary

Candidate SHA: 72c71f1073a8ce62f3bf251605a0e388ad5994c1
CI Run URL: https://github.com/Muk223/skeldir-2.0/actions/runs/20603836496

## Evidence Location (browser-visible only)

All evidence is printed directly in CI logs for the run above.

Key log markers:
- SHA guard: `R6_GITHUB_SHA=...`, `R6_GIT_SHA=...`
- Script SHA: `R6_SHA=...` / `R6_GIT_SHA=...` / `R6_GITHUB_SHA=...`
- Runtime dumps: `R6_RUNTIME_SNAPSHOT_JSON_BEGIN` / `R6_RUNTIME_SNAPSHOT_JSON_END`
- Probes: `R6_PROBE_TIMEOUT_JSON_BEGIN`, `R6_PROBE_RETRY_JSON_BEGIN`, `R6_PROBE_PREFETCH_JSON_BEGIN`, `R6_PROBE_RECYCLE_JSON_BEGIN`
- Verification verdicts: `R6_VERIFY_*`

## Gate Outcomes

- EG-R6-FIX-A (Recycling instrument integrity): PASS
  - Evidence: `R6_VERIFY_RECYCLE_OK unique_pid_count=3 pids=[2847, 2848, 2877]`.
- EG-R6-FIX-B (Prefetch instrument integrity): PASS
  - Evidence: `R6_VERIFY_PREFETCH_OK max_wait=10.541225 threshold=20.0 short_start_count=4`.
- EG-R6-FIX-C (Governance physics unchanged): PASS
  - Evidence: `R6_VERIFY_BOUNDS soft=300 hard=360 max_tasks=1 max_mem=200000 prefetch=1`, `R6_VERIFY_RETRY_OK`, `R6_VERIFY_CHORD_UNLOCK`.
- EG-R6-FIX-D (No-theater compliance): PASS
  - Evidence: all proofs above are in CI logs; no artifact download required.

## Probe Integrity Notes

- Recycling probe recomputes unique PID set from `pid_samples` and fails closed on mismatch.
- Prefetch probe requires short-task start markers (`R6_SHORT_TASK_START`) and fails closed if none are observed.
