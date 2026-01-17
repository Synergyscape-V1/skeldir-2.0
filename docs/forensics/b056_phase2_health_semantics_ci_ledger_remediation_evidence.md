# B0.5.6 Phase 2 CI Ledger Remediation Evidence

Date: 2026-01-17
Owner: codex agent
Scope: Phase B0.5.6.2 CI truth-layer remediation (health semantics)

## Objective
- Resolve CI red state and ensure B0.5.6.2 health semantics tests are executed in CI.
- Maintain B0.5.6.1 invariant (no worker-side HTTP server).
- Make `/health` behavior explicit and stable as a strict liveness alias.

## Provenance
- Repo: `skeldir-2.0`
- Branch: `main`
- HEAD: `683aadc9afb09bdd879e71918f1cfb88c3063802`
- CI run inspected: https://github.com/Muk223/skeldir-2.0/actions/runs/21099221107

## Findings
### CI failure root cause (H-CI1 confirmed)
The `B0.5.6.2 Worker capability data-plane probe` step fails immediately due to
`set -euo pipefail` combined with `PYTHONPATH` being unset.

Evidence (CI log excerpt):
- `export PYTHONPATH=$(pwd):$PYTHONPATH`
- `/home/runner/work/_temp/...sh: line 3: PYTHONPATH: unbound variable`

### B0.5.6.2 tests were not enforced in CI (H-CI3 confirmed)
The `celery-foundation` job did not include `tests/test_b0562_health_semantics.py`
in the pytest list.

### CI probe script path regression (new)
CI run `21099327198` failed in the `B0.5.6.2 Worker capability data-plane probe`
step because the probe script path resolved relative to `backend/`:
`python -u scripts/ci/health_worker_probe.py` (missing file).

Evidence (CI log excerpt):
- `python: can't open file '/home/runner/work/skeldir-2.0/skeldir-2.0/backend/scripts/ci/health_worker_probe.py'`

### B0.5.6.2 tests failing in CI (new)
CI run `21099391086` executed `tests/test_b0562_health_semantics.py` but failed
mocked worker probe tests because `app.api.health` did not expose a
`celery_app` attribute for patching.

Evidence (CI log excerpt):
- `AttributeError: <module 'app.api.health' ...> does not have the attribute 'celery_app'`

### `/health` decision stability (H-CTX4 confirmed)
Current API exposes `/health` as a strict liveness alias in `backend/app/api/health.py`.
This preserves legacy behavior while keeping explicit `/health/live` semantics.

## Remediation Applied
### CI workflow hardening
File: `.github/workflows/ci.yml`
- Guard against unset `PYTHONPATH` in two steps:
  - `Start Celery worker`
  - `B0.5.6.2 Worker capability data-plane probe`
- Use `export PYTHONPATH="$(pwd):${PYTHONPATH:-}"` to avoid `set -u` failures.

### Enforce B0.5.6.2 tests in CI
File: `.github/workflows/ci.yml`
- Added `tests/test_b0562_health_semantics.py` to the Celery foundation pytest list.

### Fix probe script path
File: `.github/workflows/ci.yml`
- Updated to `python -u ../scripts/ci/health_worker_probe.py` after `cd backend`.

### Align test patch target
File: `backend/app/api/health.py`
- Added module-level import of `celery_app` so tests can patch `app.api.health.celery_app`.

## Guardrail Evidence (B0.5.6.1)
Command:
`python scripts/ci/enforce_no_worker_http_server.py --scan-path backend/app --output docs/forensics/evidence/b056_phase2_worker_http_guardrail.log`

Result:
- `Violations: 0`
- `PASS: No worker HTTP server primitives detected.`

Log: `docs/forensics/evidence/b056_phase2_worker_http_guardrail.log`

## Status
- CI remediation verified GREEN.
- CI run: https://github.com/Muk223/skeldir-2.0/actions/runs/21099463882 (success)
- B0.5.6.2 tests are now explicitly included in CI.
- `/health` alias remains explicitly documented and implemented as liveness-only.

## Next Steps
- Trigger CI and confirm green outcome for `celery-foundation`.
- Capture CI run URL and update this ledger with verified results.
