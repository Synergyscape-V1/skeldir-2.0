# Phase 0 Remediation Evidence
## Contract Authority Unification (DB + API)

Date: February 9, 2026  
Scope: Phase 0 remediation for singular authority on DB schema + API contract surfaces, plus runtime identity parity enforcement.

## 1) Adjudication Context

- Primary branch at start: `main`
- Starting truth commit: `42d5ab77d3d5503e84cc7b545b4ee9fae9d8611d`
- Branch protection on `main` (validated): required checks are:
  - `B0.7 P2 Runtime Proof (LLM + Redaction)`
  - `Celery Foundation B0.5.1`

Branch protection source (GitHub API, February 9, 2026):  
`/repos/Muk223/skeldir-2.0/branches/main/protection`

## 2) Hypothesis Validation (H0.1–H0.5)

### H0.1 Canonical DB artifacts exist, but regen->diff authority loop is incomplete
Status: **Validated**

Findings:
- Canonical artifacts existed: `db/schema/canonical_schema.sql`, `db/schema/canonical_schema.yaml`.
- Existing schema workflow used `validate-schema-compliance.py` (YAML-centric validation), not deterministic migrations->snapshot->diff authority loop.

Remediation:
- Added deterministic authority script:
  - `scripts/schema/assert_canonical_schema.py`
- Enforced CI loop:
  - migrations (`alembic upgrade head`) -> pinned dump in CI -> normalization -> diff against canonical SQL -> fail on drift.

### H0.2 Schema drift enforcement disabled/fragmented
Status: **Validated**

Findings:
- `.github/workflows/schema-drift-check.yml` was disabled stub.

Remediation:
- Replaced disabled workflow with active drift gate:
  - `.github/workflows/schema-drift-check.yml`
- Added drift artifact upload for adjudication.

### H0.3 Runtime identity parity not globally enforced
Status: **Validated (gap existed)**

Findings:
- Migration/runtime DSN split existed in selected paths, but no uniform invariant check across runtime-proof surfaces.

Remediation:
- Added identity invariant checker:
  - `scripts/identity/assert_runtime_identity.py`
- Added CI identity parity + negative control in schema validation workflow.
- Added optional global pytest invariant hook for runtime-proof contexts:
  - `backend/tests/conftest.py` (guarded by `ENFORCE_RUNTIME_IDENTITY_PARITY=1`).

### H0.4 Alembic fallback can leak invariants
Status: **Validated**

Findings:
- `alembic/env.py` preferred `MIGRATION_DATABASE_URL` but fell back to `DATABASE_URL`, including CI.

Remediation:
- `alembic/env.py` now fails closed in CI when `MIGRATION_DATABASE_URL` is missing.
- Updated CI jobs to provide `MIGRATION_DATABASE_URL` where Alembic/evidence tooling executes.

### H0.5 API contract authority strong but skip coverage could mask drift
Status: **Validated (coverage governance gap)**

Findings:
- Runtime contract semantics had skip behavior that could pass without explicit governance.

Remediation:
- Added explicit allowlist:
  - `tests/contract/semantics_skip_allowlist.yaml`
- Updated semantics test to fail non-allowlisted skip conditions:
  - `tests/contract/test_contract_semantics.py`

## 3) File-Level Remediation Inventory

### New files
- `scripts/schema/assert_canonical_schema.py`
- `scripts/identity/assert_runtime_identity.py`
- `tests/contract/semantics_skip_allowlist.yaml`
- `docs/forensics/PHASE0_CONTRACT_AUTHORITY_UNIFICATION_REMEDIATION_EVIDENCE.md` (this document)

### Modified files
- `.github/workflows/schema-validation.yml`
- `.github/workflows/schema-drift-check.yml`
- `.github/workflows/ci.yml`
- `alembic/env.py`
- `backend/tests/conftest.py`
- `tests/contract/test_contract_semantics.py`
- `scripts/README.md`
- `db/schema/canonical_schema.sql`

## 4) Deterministic DB Authority Gate (Exit Gate 0.A)

Implemented command:
- `python scripts/schema/assert_canonical_schema.py --mode ci`

Behavior:
- Applies migrations to head using `MIGRATION_DATABASE_URL`.
- In CI mode, dumps schema via pinned container image tooling.
- Normalizes dump output (non-semantic volatility removed).
- Diffs against canonical SQL and fails on mismatch.

Non-vacuity:
- Workflow includes negative control that mutates canonical and asserts failure.

## 5) API Contract Authority Gate (Exit Gate 0.B)

Authority enforcement retained and tightened:
- Contract bundle/validation/breaking-change checks were already active.
- Runtime semantics skip behavior is now explicitly governed by allowlist.
- Non-allowlisted runtime skips fail immediately.

## 6) Runtime Identity Parity Gate (Exit Gate 0.C)

Implemented:
- Script-level assertion:
  - runtime `current_user` must equal expected runtime role
  - runtime and migration identities must differ
- CI-level positive + negative controls in schema-validation workflow.
- Optional harness-wide pytest assertion hook enabled by env gate.

## 7) Drift Negative Controls (Exit Gate 0.D)

Implemented and exercised in CI:
- Schema negative control (mutated canonical must fail).
- Runtime identity negative control (mismatched expected user must fail).

Observed behavior:
- Gates fail when invariants are violated and pass after correction.

## 8) CI Evidence and Merge Path

### PR used for remediation
- PR: `https://github.com/Muk223/skeldir-2.0/pull/61`

### Key workflow evidence
- Schema Validation (`validate-schema-authority`) passed after remediation.
- Schema Drift Check (`drift-check`) passed after canonical SQL reconciliation.
- Required branch-protection checks passed:
  - `B0.7 P2 Runtime Proof (LLM + Redaction)` -> PASS
  - `Celery Foundation B0.5.1` -> PASS

### Important iterative fixes discovered during CI
- `backend/tests/conftest.py` used `pytest.Node` annotation not compatible with runner pytest path -> changed to untyped param.
- `Celery Foundation B0.5.1` evidence generation invoked Alembic without migration DSN -> set `MIGRATION_DATABASE_URL` in CI env.
- Canonical SQL drift surfaced by new deterministic gate -> reconciled `db/schema/canonical_schema.sql` to migrations-derived normalized snapshot.

### Protected branch resolution
- Direct push to `main` was blocked by protection.
- Remediation proceeded via PR until required checks passed.
- Merge completed.

## 9) Final State

- Merge commit on `main`: `ac955199c2a90d04154fb51a20197be3e741cc6d`
- Merge timestamp: February 9, 2026
- Outcome:
  - Phase 0 authority loop is deterministic and CI-adjudicated.
  - Identity parity has explicit enforcement and negative controls.
  - Contract skip behavior is governed and auditable.
  - Required protected checks pass with remediation in place.

