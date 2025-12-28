# R4 Worker Failure Semantics Summary (Truth Anchor)

## Status

R4 = **IN PROGRESS** until one CI run proves *crash physics* and *retry execution* in browser-visible logs.

- **Candidate SHA:** `TBD`
- **CI run:** `TBD` (paste GitHub Actions run URL)

## Acceptance Requirements (No-Theater)

R4 is only admissible when CI logs show, for crash-after-write/pre-ack (S2), the marker chain:

- `R4_S2_BARRIER_OBSERVED` → `R4_S2_KILL_ISSUED` → `R4_S2_WORKER_EXITED` → `R4_S2_WORKER_RESTARTED` → `R4_S2_REDELIVERED`

And for poison pill (S1), attempt execution proof via `r4_task_attempts` (attempts_min_per_task >= 2).

## Evidence (Where It Lives)

- Workflow: `.github/workflows/r4-worker-failure-semantics.yml`
- Harness: `scripts/r4/worker_failure_semantics.py`
- Summary generator: `scripts/r4/render_r4_summary.py`

