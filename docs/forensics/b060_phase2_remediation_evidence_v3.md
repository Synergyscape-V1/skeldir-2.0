# B0.6 Phase 2 Remediation Evidence v3

Status: **PASSING** (merged + mainline CI adjudication under required check)

## Executive summary
- **Path chosen:** Path 2 (extend required **B0.6 Phase 0 Adjudication** to run Phase 2 tests + migrations).
- **Merge commit on `main`:** `32c9d17593485eb56bd025f366a0edb4d20c77c7`
- **Main CI run (required check):** https://github.com/Muk223/skeldir-2.0/actions/runs/21449343218

## Gate P2-A — Provenance (merge on main)
- **Merge commit SHA:** `32c9d17593485eb56bd025f366a0edb4d20c77c7`
- **Main branch SHA:** `32c9d17593485eb56bd025f366a0edb4d20c77c7`

## Gate P2-F — CI execution (mainline)
**Main run:** https://github.com/Muk223/skeldir-2.0/actions/runs/21449343218  
**Job:** `B0.6 Phase 0 Adjudication` (required check)

Log excerpts (main run):
```
Run alembic upgrade head
alembic upgrade head
```
```
pytest -v --tb=short tests/test_b060_phase2_platform_connections.py
tests/test_b060_phase2_platform_connections.py::test_platform_connections_require_auth PASSED [ 50%]
tests/test_b060_phase2_platform_connections.py::test_platform_connection_tenant_isolation_and_secrecy PASSED [100%]
```

## Gate P2-G — CI durability / governance
**Branch protection (main):** required check list contains only `B0.6 Phase 0 Adjudication` (the required workflow now includes Phase 2 tests + migrations).

Branch protection JSON (excerpt):
```
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["B0.6 Phase 0 Adjudication"],
    "checks": [{"context": "B0.6 Phase 0 Adjudication"}]
  }
}
```

**Governance rationale:** Branch protection is not directly writable via current token (API 404). Path 2 enforces Phase 2 tests under the existing required check, so merges are blocked unless Phase 2 invariants pass.

## Gate P2-H — Migration viability (pgcrypto + clean DB)
**Evidence:** mainline run executed `alembic upgrade head` successfully on a clean Postgres service container (see Gate P2-F excerpt).

**Inference:** The Phase 2 migration includes `CREATE EXTENSION IF NOT EXISTS pgcrypto` and ran without error under `alembic upgrade head`, so pgcrypto creation succeeded in the same migration path.

## References
- PR #31: https://github.com/Muk223/skeldir-2.0/pull/31
- Mainline adjudication run: https://github.com/Muk223/skeldir-2.0/actions/runs/21449343218
- Required check workflow: `.github/workflows/b06_phase0_adjudication.yml`
