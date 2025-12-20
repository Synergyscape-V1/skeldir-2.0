## B0.5.4.0 — GitHub CI Truth-Layer Evidence (Backend Only)

### Scope
- Backend-only Zero-Drift v3.2 validation in GitHub Actions.
- Frontend untouched.

### Commit / Branch Under Test
- Branch: b0540-zero-drift-v3-proofpack
- CI workflow target commit: fd65767edf9c29524d22759803999dd491a3bcdf (branch head at dispatch)
- CI workflow run: https://github.com/Muk223/skeldir-2.0/actions/runs/20400778070 (workflow_dispatch)

### CI Workflow Entry Points
- `.github/workflows/ci.yml` now contains job `zero-drift-v3-2` (triggered on `workflow_dispatch` and on main/develop).
- Script executed: `scripts/ci/zero_drift_v3_2.sh`.

### Zero-Drift v3.2 CI Gates (CG-1 .. CG-7)
- CG-1 CI run existence: **PASS** - workflow_dispatch run 20400778070 executed on `b0540-zero-drift-v3-proofpack` (Zero-Drift v3.2 job invoked).
- CG-2 Fresh DB migration determinism: **PASS** - ZG-1 fresh upgrade reached head on `skeldir_zg_fresh` (Alembic log stack starting at `== ZG-1: fresh DB upgrade to head ==`).
- CG-3 Seed-before-upgrade determinism: **PASS** - ZG-2 seeded `skeldir_zg_existing`, upgraded to head, and selected seeded attribution_event row.
- CG-4 Matview registry coherence & refresh permissions: **PASS** - ZG-3/4 enumerated mv_* registry, owners `app_user`, unique indexes present, and REFRESH MATERIALIZED VIEW succeeded for fresh + existing contexts.
- CG-5 Beat dispatch proof: **PASS** - ZG-5 shows schedule interval forced to 1s and repeated `Scheduler: Sending due task refresh-matviews-every-5-min` lines (beat dispatch observed).
- CG-6 Serialization enforced in refresh path: **PASS** - ZG-6 shows lock-holder acquired, concurrent attempt skipped (`skipped_already_running`), then successful refresh after release.
- CG-7 Worker ingestion write-block: **PASS** - ZG-7 worker-context INSERT rejected with `ERROR:  permission denied for table attribution_events`.

### How to Trigger CI (workflow_dispatch)
1) In GitHub UI: Actions → CI → “Run workflow”.
2) Select branch: `b0540-zero-drift-v3-proofpack`.
3) Run workflow. Capture run URL.

### Artifacts to Capture Post-Run
- CI run URL.
- `zero-drift-v3-2` job log anchors proving each CG gate (script outputs include all commands/results).
- Update this file with PASS/FAIL per gate + log links after run completes.

### Notes
- No frontend changes.
- Database/broker use Postgres service; roles/db created inside harness.
