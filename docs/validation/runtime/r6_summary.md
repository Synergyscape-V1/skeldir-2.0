# R6 Worker Resource Governance Summary

Candidate SHA: 2b0236c802b0017a50c93903c330e23d49078013
CI Run URL: https://github.com/Muk223/skeldir-2.0/actions/runs/20602002910

## Gate Outcomes

- EG-R6-FIX-0 (Temporal coherence & evidence anchoring): PASS
  - Evidence: `docs/validation/runtime/R6_context_gathering/2b0236c802b0017a50c93903c330e23d49078013/R6_ENV_SNAPSHOT.json`
- EG-R6-FIX-1 (Global time bounds present): PASS
  - Evidence: `docs/validation/runtime/R6_context_gathering/2b0236c802b0017a50c93903c330e23d49078013/R6_GAP_REPORT.md`
- EG-R6-FIX-2 (Worker recycling bounds present): PASS
  - Evidence: `docs/validation/runtime/R6_context_gathering/2b0236c802b0017a50c93903c330e23d49078013/R6_GAP_REPORT.md`
- EG-R6-FIX-3 (Retry bounds present): PASS
  - Evidence: `docs/validation/runtime/R6_context_gathering/2b0236c802b0017a50c93903c330e23d49078013/R6_PROBE_RETRY.json`
- EG-R6-FIX-4 (celery.chord_unlock bounded): PASS
  - Evidence: `docs/validation/runtime/R6_context_gathering/2b0236c802b0017a50c93903c330e23d49078013/R6_TASK_GOVERNANCE_MATRIX.md`
- EG-R6-FIX-5 (Anti-thrash validation): PASS
  - Evidence: `docs/validation/runtime/R6_context_gathering/2b0236c802b0017a50c93903c330e23d49078013/R6_PROBE_PREFETCH.json`
- EG-R6-FIX-6 (Documentation anchoring): PASS (this document)

## Observed Runtime Envelope (from CI run)

- task_soft_time_limit: 300
- task_time_limit: 360
- worker_max_tasks_per_child: 1
- worker_max_memory_per_child: 200000
- worker_prefetch_multiplier: 1

Evidence: `docs/validation/runtime/R6_context_gathering/2b0236c802b0017a50c93903c330e23d49078013/R6_GAP_REPORT.md`

## Probe Results

- Timeout probe: soft + hard limits observed
  - Evidence: `docs/validation/runtime/R6_context_gathering/2b0236c802b0017a50c93903c330e23d49078013/R6_PROBE_TIMEOUT.json`
- Retry probe: attempts 0-2 observed and bounded
  - Evidence: `docs/validation/runtime/R6_context_gathering/2b0236c802b0017a50c93903c330e23d49078013/R6_PROBE_RETRY.json`
- Recycle probe: worker PID rotates per task
  - Evidence: `docs/validation/runtime/R6_context_gathering/2b0236c802b0017a50c93903c330e23d49078013/R6_PROBE_RECYCLE.json`
- Prefetch probe: short task wait within threshold
  - Evidence: `docs/validation/runtime/R6_context_gathering/2b0236c802b0017a50c93903c330e23d49078013/R6_PROBE_PREFETCH.json`
