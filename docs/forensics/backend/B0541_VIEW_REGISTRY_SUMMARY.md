# B0.5.4.1 View Registry Summary

Candidate Completion SHA (C): 40153b852207f9c0fa95ed1807a2410dbcaa8e0e
Branch: main

## Scope

Implements the B0.5.4.1 contract: `backend/app/matviews/registry.py` is the sole authoritative list of refreshable materialized views, with complete metadata and closed-set validation.

## Files Changed

- `.github/workflows/b0541-view-registry.yml`
- `backend/app/matviews/__init__.py`
- `backend/app/matviews/registry.py`
- `backend/app/core/matview_registry.py` (compatibility shim)
- `backend/app/tasks/maintenance.py`
- `backend/tests/test_b0541_view_registry.py`
- `backend/tests/value_traces/test_value_04_registry_trace.py`
- `backend/app/core/__init__.py`
- `scripts/ci/zero_drift_v3_2.sh`
- `docs/backend/B0541_VIEW_REGISTRY_SUMMARY.md` (evidence closure)

## Registry Dump (Authoritative)

Source: `backend/app/matviews/registry.py`

| name | schedule_class | max_staleness_seconds | dependencies | refresh |
| --- | --- | --- | --- | --- |
| mv_allocation_summary | realtime | 60 | [] | refresh_sql |
| mv_channel_performance | hourly | 3600 | [] | refresh_sql |
| mv_daily_revenue_summary | hourly | 3600 | [] | refresh_sql |
| mv_realtime_revenue | realtime | 60 | [] | refresh_sql |
| mv_reconciliation_status | realtime | 60 | [] | refresh_sql |

## Schedule Metadata Derivation

Schedule intent sources are migration comments; no heuristic fallback used in this implementation.

- mv_allocation_summary: TTL 30-60s comment in `alembic/versions/003_data_governance/202511161110_fix_mv_allocation_summary_left_join.py` (comment block near line 93).
- mv_channel_performance: "recommended: hourly or on-demand" in `alembic/versions/003_data_governance/202511151500_add_mv_channel_performance.py` (comment near line 101).
- mv_daily_revenue_summary: "recommended: hourly or on-demand" in `alembic/versions/003_data_governance/202511151510_add_mv_daily_revenue_summary.py` (comment near line 103).
- mv_realtime_revenue: TTL 30-60s comment in `alembic/versions/001_core_schema/202511131119_add_materialized_views.py` (comment near line 63).
- mv_reconciliation_status: TTL 30-60s comment in `alembic/versions/001_core_schema/202511131119_add_materialized_views.py` (comment near line 90).

## Dependency Proof Summary

Dependency extraction uses `pg_get_viewdef` to detect `mv_*` references. All five matviews reference base tables only (no `mv_*` references), so dependencies are `[]` and topological order is the registry order.

## Concurrency Proof Summary

Each registry matview has a unique index in migrations, enabling `REFRESH MATERIALIZED VIEW CONCURRENTLY`:

- mv_allocation_summary: `alembic/versions/003_data_governance/202511161110_fix_mv_allocation_summary_left_join.py` (unique index `idx_mv_allocation_summary_key`).
- mv_channel_performance: `alembic/versions/003_data_governance/202511151500_add_mv_channel_performance.py` (unique index `idx_mv_channel_performance_unique`).
- mv_daily_revenue_summary: `alembic/versions/003_data_governance/202511151510_add_mv_daily_revenue_summary.py` (unique index `idx_mv_daily_revenue_summary_unique`).
- mv_realtime_revenue: `alembic/versions/007_skeldir_foundation/202512201000_restore_matview_contract_five_views.py` (unique index `idx_mv_realtime_revenue_tenant_id`).
- mv_reconciliation_status: `alembic/versions/007_skeldir_foundation/202512201000_restore_matview_contract_five_views.py` (unique index `idx_mv_reconciliation_status_tenant_id`).

## Gate Evidence (Loud Witness)

Tests emit JSON markers:

- G1A: `EG_B0541_G1A_BEGIN {json} EG_B0541_G1A_END`
- G1B: `EG_B0541_G1B_BEGIN {json} EG_B0541_G1B_END`
- G1C: `EG_B0541_G1C_BEGIN {json} EG_B0541_G1C_END`

These are produced by `backend/tests/test_b0541_view_registry.py`.

## CI Evidence (Required)

These runs executed on Candidate Completion SHA (C) = 40153b852207f9c0fa95ed1807a2410dbcaa8e0e.

- B0.5.4.1 Gate run URL: https://github.com/Muk223/skeldir-2.0/actions/runs/20625685998
- B0.5.4.1 Gate job URL (markers in logs): https://github.com/Muk223/skeldir-2.0/actions/runs/20625685998/job/59235756243
- R7 Final Winning State run URL: https://github.com/Muk223/skeldir-2.0/actions/runs/20625689931
