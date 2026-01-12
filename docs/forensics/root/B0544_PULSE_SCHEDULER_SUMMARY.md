# B0544_PULSE_SCHEDULER_SUMMARY.md

## Candidate Completion SHA

- candidate_sha: 4c3f1d5e31e1c6e025216f6ff7fa0bbd3a0e6eb0

## Status

- CI_RUN_URL: https://github.com/Muk223/skeldir-2.0/actions/runs/20700005995
- CI_JOB_URL: https://github.com/Muk223/skeldir-2.0/actions/runs/20700005995/job/59420921942
- R7_RUN_URL: https://github.com/Muk223/skeldir-2.0/actions/runs/20700007606

## Files Changed

- backend/app/tasks/matviews.py
- backend/app/tasks/beat_schedule.py
- Procfile
- backend/tests/test_b0543_matview_task_layer.py
- B0544_CONTEXT_DUMP.md
- B0544_EVIDENCE_PACK_local_windows.md

## Implementation Summary

- Added a global beat-safe pulse task that enumerates tenants and dispatches `app.tasks.matviews.refresh_all_for_tenant` per tenant.
- Repointed the existing `refresh-matviews-every-5-min` schedule key to the pulse adapter (no new schedule keys added).
- Preserved governance schedules (`pii-audit-scanner`, `enforce-data-retention`) unchanged.
- Added a single beat entrypoint in Procfile to avoid split-brain scheduler behavior.
- Added a worker survival regression test that proves failure to DLQ/metrics and subsequent task success.

## Evidence Summary

- Pre/post schedule dumps, adapter registration, and runtime entrypoint proof are captured in `B0544_EVIDENCE_PACK_local_windows.md`.
- Local beat + worker logs show Beat dispatching the pulse task and workers receiving the adapter and tenant refresh tasks.
- Local survival test output (worker failure then success) is captured in `B0544_REMEDIATION_EVIDENCE_PACK_local_windows_v2.md`.
- R6 fuses remain global in celery_app configuration; adapter does not override them.

## Atomic Replacement Statement

- The schedule key `refresh-matviews-every-5-min` now targets `app.tasks.matviews.pulse_matviews_global` and no longer schedules `app.tasks.maintenance.refresh_all_matviews_global_legacy`.
- No additional matview schedule keys were added.

## Governance Preservation Statement

- `pii-audit-scanner` and `enforce-data-retention` remain in the beat schedule with the same task strings and crontab cadence.
