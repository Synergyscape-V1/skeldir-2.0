# M2 Remediation Evidence Pack

## Initial Findings

- Default test paths contained hardcoded Neon/prod-adjacent database URLs.
- Pytest marker taxonomy did not distinguish pure unit, direct DB, pooler DB, Celery eager, real worker, fail-visible tenant context, append-only-sensitive, B2.3 representative, or B2.4 persistence readiness proofs.
- M1 local topology existed, but M2 transaction-pooler topology was absent.
- Legacy skeleton tests passed vacuously.
- Append-only cleanup risks remained visible in test paths.
- B2.4 persistence readiness was unconfirmed.

## Remediations Made

- Added M2 markers to `pytest.ini`.
- Added Makefile targets for all M2 command surfaces.
- Added `docker-compose.test.yml` with local PgBouncer transaction-pooler topology.
- Added `scripts/ci/validate_m2_test_feedback_loop.py`.
- Added `scripts/ci/run_m2_test_feedback_loop.sh`.
- Added topology URL guard at `scripts/testing/assert_topology_urls.py`.
- Added template/disposable DB scripts under `scripts/testing/`.
- Added M2 docs for testing, DB topology, append-only isolation, Celery modes, topology URL authority, and B2.4 persistence readiness.
- Added M2 representative tests in `backend/tests/test_m2_test_feedback_loop.py`.
- Added fail-visible tenant-context guard in `backend/app/db/session.py`.
- Quarantined legacy skeleton tests with M2 issue IDs.
- Replaced hardcoded default-test external DB DSNs with local-only defaults.

## Validation To Record

The authoritative M2 result requires:

1. local validator pass;
2. local command-surface pass;
3. branch pushed;
4. M2 workflow green on GitHub Actions;
5. merge to `main`;
6. post-merge `main` checks green.

This evidence pack must remain non-final until those validations are attached.
