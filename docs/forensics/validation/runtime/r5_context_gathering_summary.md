# R5 Context Gathering Summary (Determinism + Complexity Minefield Map)

R5 = **CONTEXT GATHERED** (measurement-only; no determinism/perf remediation applied in this phase).

- **Candidate SHA:** `2baa453a3bcb5634a8d09650635d45a86de45f56`
- **CI run:** https://github.com/Muk223/skeldir-2.0/actions/runs/20577145549

## EG-R5-CG-0 — Truth Anchor (PASS)

From CI logs (`Run R5 probes` step):

- OS: `Linux-6.8.0-1044-azure-x86_64-with-glibc2.35`
- CPU: `4`
- RAM: `16379784 kB` (MemTotal)
- Python: `3.11.14`
- Postgres: `16.11 (Debian 16.11-1.pgdg13+1)`

## Repro Commands (authoritative)

- Run the probes in CI:
  - `gh workflow run 219429083 --ref main`
  - Inspect logs: `gh run view 20577145549 --log`
- Run locally (requires Postgres + migrations):
  - `alembic upgrade heads`
  - `python scripts/r5/r5_probes.py` with env:
    - `PYTHONPATH=backend`
    - `DATABASE_URL=postgresql://app_user:app_user@127.0.0.1:5432/r5`
    - `MIGRATION_DATABASE_URL=postgresql://r5_admin:r5_admin@127.0.0.1:5432/r5`
    - `R5_ADMIN_DATABASE_URL=postgresql://r5_admin:r5_admin@127.0.0.1:5432/r5`
    - If tables are owned by the migration role, also run: `GRANT app_rw TO app_user;`

## EG-R5-CG-1 — Determinism Surface Map (PASS)

### Ordering / Total Ordering

- `backend/app/tasks/attribution.py:253` uses `ORDER BY occurred_at ASC` without a total tie-breaker (e.g., `, id ASC`).

### Time / Timestamp Surfaces

- `backend/app/tasks/attribution.py:305` and `backend/app/tasks/attribution.py:314` write `CURRENT_TIMESTAMP` on insert/update (`updated_at` drift across reruns).
- `backend/app/api/attribution.py:64` uses `datetime.utcnow()` for `last_updated` (always drifts; endpoint is currently stubbed).

### Float / Numeric / Rounding

- `backend/app/tasks/attribution.py:277` uses float `allocation_ratio = 1.0 / len(BASELINE_CHANNELS)`.
- `backend/app/tasks/attribution.py:279` quantizes `confidence_score` from the float ratio (float → string → Decimal → float).

### UUID / Nonce Surfaces

- `backend/app/tasks/attribution.py:317` uses `uuid4()` for `allocation_id` on insert.
- `backend/app/services/attribution.py:60` generates `correlation_uuid = uuid4()` when caller does not provide one.

### Concurrency / Retry / Merge Points (static)

- `backend/app/services/attribution.py:64` enqueues `recompute_window.apply_async(...)` and depends on caller-provided correlation for deterministic tracing.
- `backend/app/tasks/attribution.py:92`–`backend/app/tasks/attribution.py:215` manages window idempotency via `attribution_recompute_jobs` and updates timestamps with `CURRENT_TIMESTAMP` (non-bit-identical operational metadata by design).

### DB Trigger / Constraint Surfaces (order-dependent)

- `alembic/versions/003_data_governance/202511131240_add_sum_equality_validation.py:79` installs `trg_check_allocation_sum` AFTER each row insert/update/delete.
- `alembic/versions/003_data_governance/202511131240_add_sum_equality_validation.py:62` raises if `SUM(allocated_revenue_cents)` != event revenue (±1 cent tolerance), meaning partial per-event inserts can fail mid-loop for revenue>0.

## EG-R5-CG-2 — Harness Capacity Characterized (PASS)

Harness path used for measurement:

- Seeder: `scripts/r5/r5_probes.py` uses `asyncpg.copy_records_to_table(...)` for deterministic event generation.
- Compute under test: `app.tasks.attribution._compute_allocations_deterministic_baseline` (called directly in-process for measurement; no Celery scheduling in this run).

Feasibility evidence (CI run above):

- 10k seed: `seed_wall_s=0.395096` (P3 small)
- 100k seed: `seed_wall_s=4.165286` (P3 large)
- 10k compute completed; 100k compute timed out (details below).

## EG-R5-CG-3 — Complexity Risk Map (static Big-O + suspected N+1) (PASS)

### Primary attribution loop(s)

- Nested loop: `backend/app/tasks/attribution.py:286` (events) × `backend/app/tasks/attribution.py:292` (channels) → per-event/per-channel upsert.

### Suspected scaling hazards

- Per-row SQL writes: `backend/app/tasks/attribution.py:297` executes one INSERT/UPSERT per channel per event → ~`O(N * C)` statements.
- Trigger amplification: `alembic/versions/003_data_governance/202511131240_add_sum_equality_validation.py:53`–`alembic/versions/003_data_governance/202511131240_add_sum_equality_validation.py:60` performs two SELECTs per write (event revenue + allocation sum), turning each write into multiple DB operations.
- Memory scaling: `backend/app/tasks/attribution.py:260` uses `.fetchall()` (loads full window into memory) → `O(N)` memory.

## EG-R5-CG-4 — Minimal Determinism Probe Executed (PASS)

Probe: `P1_Determinism` in CI run logs.

- Dataset: 500 deterministic events (revenue_cents=0 to avoid mid-loop trigger abort; see trigger analysis above).
- Result: values are stable, but rowset is not bit-identical across reruns due to `updated_at`.

Checksums (SHA256 of canonical JSON):

- `allocations_full` (includes `id/created_at/updated_at`): drifted across 3 runs
  - `9747fcc1b9e0f593466b4e8760bd53caa897ff7ac718d28c67507d6b6beba8de`
  - `f7925b2b97078de3cb4b1183d323495462eddd970b3ed2ef235f8adeeab5efac`
  - `92c472cdac476f76d2afbee15e75e69f8e3dda87b3d87c4b926af722fb414343`
- `allocations_normalized` (excludes `id/created_at/updated_at`): stable across 3 runs
  - `e804e6ddeeeafb0444dfc26bad5052b8916b4fc46b249c36fe05f0da037a58c2` (x3)

First diff evidence:

- Drift field: `updated_at` (matches `backend/app/tasks/attribution.py:314`).

## EG-R5-CG-5 — Minimal Scaling Probe OR Infeasibility Proven (PASS)

Probe: `P3_Scaling` in CI run logs.

- N=10k completed:
  - compute wall: `96.327906s`
  - SQLAlchemy statement count: `30002` (~ `1 + 3*N` in this baseline path)
  - peak RSS: `80628 kB`
- N=100k attempted but did not complete within the probe max window:
  - `timeout_after_s=900.0`

Interpretation (ratio-based):

- The baseline compute path is consistent with ~`O(N)` statement count, but 100k is infeasible on this runner within a 15-minute window due to high per-row write cost plus trigger amplification.

## Minefield Map (top risks)

### Top 5 determinism risks

1. Non-total ORDER BY: `backend/app/tasks/attribution.py:253`
2. Timestamp drift on update: `backend/app/tasks/attribution.py:314`
3. UUID drift on insert: `backend/app/tasks/attribution.py:317`
4. Float → NUMERIC coercion surfaces: `backend/app/tasks/attribution.py:277`
5. Trigger makes partial writes order-sensitive / abort-prone: `alembic/versions/003_data_governance/202511131240_add_sum_equality_validation.py:79`

### Top 5 complexity risks

1. Per-event-per-channel DB writes: `backend/app/tasks/attribution.py:286` + `backend/app/tasks/attribution.py:292`
2. Trigger adds per-write SELECTs: `alembic/versions/003_data_governance/202511131240_add_sum_equality_validation.py:53`
3. Full-window `.fetchall()` memory growth: `backend/app/tasks/attribution.py:260`
4. ORDER BY sort cost without total tie-breaker: `backend/app/tasks/attribution.py:253`
5. 100k infeasibility under current baseline path (CI evidence above)

