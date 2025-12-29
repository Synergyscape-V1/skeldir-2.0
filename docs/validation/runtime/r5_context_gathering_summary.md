# R5 Context Gathering Summary (Determinism + Complexity Minefield Map)

R5 = **IN PROGRESS** (context gathering only; no remediation in this phase).

- **Candidate SHA:** `TBD`
- **CI run:** TBD

## Repro Commands (authoritative)

- Run probes (CI): trigger workflow `R5: Context Gathering` (`.github/workflows/r5-context-gathering.yml`)
- Run probes (local, requires Postgres + migrations):
  - `python scripts/r5/r5_probes.py` with env:
    - `PYTHONPATH=backend`
    - `DATABASE_URL=postgresql://app_user:app_user@127.0.0.1:5432/r5`
    - `MIGRATION_DATABASE_URL=postgresql://r5_admin:r5_admin@127.0.0.1:5432/r5`
    - `R5_ADMIN_DATABASE_URL=postgresql://r5_admin:r5_admin@127.0.0.1:5432/r5`

## Notes

This file must be updated only after a single run produces browser-visible logs containing:

- The `=== R5_ENV ===` block (truth anchor: SHA + environment snapshot)
- `R5_VERDICT_BEGIN/END` blocks for:
  - `P1_Determinism`
  - `P3_Scaling`

