## B0.5.4.0 — GitHub CI Truth-Layer Evidence (Backend Only)

### Run Attribution
- Branch: `b0540-zero-drift-v3-proofpack`
- Commit (checkout): `3c999f29aae0c53120fad160c049890a875f12cd`
- Workflow: `.github/workflows/ci.yml` (`zero-drift-v3-2` job)
- Workflow title: `B0.5.4.0-CI-ZERO-DRIFT-V3-2-TRUTH-AUDIT`
- Run URL: https://github.com/Muk223/skeldir-2.0/actions/runs/20414138528 (Zero-Drift v3.2 CI Truth Layer job: ✅)
- Log capture: `tmp/zero_drift_v3_2_run7.log` (local export of the Actions log for the run above)

### Canonical Inventory Contract (5)
- Contract source: B0.5.4 approach intent + prior forensic ledger (`docs/forensics/evidence/b054-forensic-readiness-evidence.md`, G8).
- Canonical matviews (registry-enforced): `mv_allocation_summary`, `mv_channel_performance`, `mv_daily_revenue_summary`, `mv_realtime_revenue`, `mv_reconciliation_status`.

### Gate Ledger (GATE-0A..0D, binary/falsifiable)
- **GATE-0A — Inventory determinism (registry ↔ pg_matviews = 5)**: **PASS**  
  - `pg_matviews` (fresh DB) shows exactly 5: `mv_allocation_summary`, `mv_channel_performance`, `mv_daily_revenue_summary`, `mv_realtime_revenue`, `mv_reconciliation_status` (`tmp/zero_drift_v3_2_run7.log` @ `2025-12-21T18:40:01.562Z`).  
  - Registry print matches, and the harness equality check reports `MATVIEW INVENTORY OK (registry == pg_matviews)` (same log block).
- **GATE-0B — Alembic determinism (single head, upgradeable)**: **PASS**  
  - Fresh upgrade reaches head with `202512201000 (head)` and `202512201000 (skeldir_foundation, celery_foundation) (head)` after `alembic current`/`alembic heads` (`tmp/zero_drift_v3_2_run7.log` @ `2025-12-21T18:39:59.748Z` and `2025-12-21T18:40:02.195Z`).  
  - Existing DB seed-before-upgrade repeats the same head (log block at `2025-12-21T18:40:01.399Z`).
- **GATE-0C — Privilege compatibility (grants + refresh + worker immutability)**: **PASS**  
  - Owners: all mv_* owned by `app_user` (`tmp/zero_drift_v3_2_run7.log` rows following `== ZG-4` @ `2025-12-21T18:40:01.647Z`).  
  - Indexes: all 5 have unique indexes for CONCURRENTLY refresh (`2025-12-21T18:40:01.685Z` block).  
  - Grants evidence: `Role grants for app_user` shows SELECT on ingestion tables and Celery tables plus refresh dependencies (`tmp/zero_drift_v3_2_run7.log` @ `2025-12-21T18:40:01.907Z`).  
  - Refresh as app_user: `REFRESH MATERIALIZED VIEW CONCURRENTLY` executed for all 5 views on fresh and existing DBs with no errors (commands in ZG-4 block).  
  - Worker ingestion immutability: worker-context INSERT rejected with `ERROR:  permission denied for table attribution_events` (`tmp/zero_drift_v3_2_run7.log` @ `2025-12-21T18:40:25.375Z` during `== ZG-7`).
- **GATE-0D — CI attribution + evidence immutability**: **PASS**  
  - workflow_dispatch run recorded above; checkout SHA logged (`git log -1 --format=%H` → `3c999f29aae0c53120fad160c049890a875f12cd` at `2025-12-21T18:39:23.615Z`).  
  - Harness completed end-to-end with exit 0 (`== Zero-Drift v3.2 CI harness completed ==` @ `2025-12-21T18:40:25.376Z`). Evidence captured in log and summarized here.

### ZG-5 / ZG-6 / ZG-7 Evidence Anchors
- **Beat dispatch proof (ZG-5)**: `Scheduler: Sending due task refresh-matviews-every-5-min (app.tasks.maintenance.refresh_all_matviews_global_legacy)` repeats with 1s interval (`tmp/zero_drift_v3_2_run7.log` lines @ `2025-12-21T18:40:04Z`–`18:40:22Z`), demonstrating dispatch, not just startup.
- **Serialization proof (ZG-6)**: Concurrent refresh test shows lock acquisition + skip + success: `refresh_lock_acquired`, `refresh_lock_already_held`, `matview_refresh_skipped_already_running`, `refresh_lock_released`, final results `{'skip': 'skipped_already_running', 'success': 'success'}` (`tmp/zero_drift_v3_2_run7.log` @ `2025-12-21T18:40:23Z`–`18:40:25Z`).
- **Worker ingestion write-block (ZG-7)**: worker execution context INSERT blocked with `ERROR:  permission denied for table attribution_events` (`tmp/zero_drift_v3_2_run7.log` @ `2025-12-21T18:40:25.375Z`), proving immutability invariant.

### Notes / Scope Compliance
- Backend-only; no changes under `frontend/**`.
- Zero-Drift harness uses `scripts/ci/zero_drift_v3_2.sh` (matview registry equality enforced; refreshes run as `app_user`; beat interval forced to 1s in CI).
- Canonical matview registry centralized at `backend/app/core/matview_registry.py` and enforced by migration `alembic/versions/007_skeldir_foundation/202512201000_restore_matview_contract_five_views.py` (reintroduces mv_realtime_revenue + mv_reconciliation_status and sets ownership/grants).
