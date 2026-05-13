#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-default}"
PYTHON_BIN="${PYTHON_BIN:-python}"
M2_TEST_PATHS="${M2_TEST_PATHS:-backend/tests}"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
  elif command -v py >/dev/null 2>&1; then
    PYTHON_BIN=py
  fi
fi
export PYTHONPATH="${PYTHONPATH:-backend}"
export TEST_DIRECT_DATABASE_URL="${TEST_DIRECT_DATABASE_URL:-${DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:5432/skeldir_m2}}"
export TEST_DATABASE_URL="${TEST_DATABASE_URL:-${TEST_DIRECT_DATABASE_URL}}"
export DIRECT_DATABASE_URL="${DIRECT_DATABASE_URL:-${TEST_DIRECT_DATABASE_URL}}"
export DATABASE_URL="${DATABASE_URL:-${TEST_DIRECT_DATABASE_URL}}"
export TEST_POOLED_DATABASE_URL="${TEST_POOLED_DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:6432/skeldir_m2}"
export POOLED_DATABASE_URL="${POOLED_DATABASE_URL:-${TEST_POOLED_DATABASE_URL}}"
export MIGRATION_DATABASE_URL="${MIGRATION_DATABASE_URL:-${TEST_DIRECT_DATABASE_URL}}"
export CELERY_BROKER_URL="${CELERY_BROKER_URL:-sqla+${TEST_DIRECT_DATABASE_URL}}"
export CELERY_RESULT_BACKEND="${CELERY_RESULT_BACKEND:-db+${TEST_DIRECT_DATABASE_URL}}"
export ENVIRONMENT="${ENVIRONMENT:-ci}"
export TESTING=1
export SKELDIR_CONTROL_PLANE_ENABLED="${SKELDIR_CONTROL_PLANE_ENABLED:-0}"
export SKELDIR_REQUIRE_AUTH_SECRETS="${SKELDIR_REQUIRE_AUTH_SECRETS:-0}"
export SKELDIR_REQUIRE_PLATFORM_TOKEN_KEY="${SKELDIR_REQUIRE_PLATFORM_TOKEN_KEY:-0}"
export AUTH_JWT_SECRET="${AUTH_JWT_SECRET:-local-m2-jwt-secret}"
export AUTH_JWT_ALGORITHM="${AUTH_JWT_ALGORITHM:-RS256}"
export AUTH_JWT_ISSUER="${AUTH_JWT_ISSUER:-https://issuer.skeldir.test}"
export AUTH_JWT_AUDIENCE="${AUTH_JWT_AUDIENCE:-skeldir-api}"
export PLATFORM_TOKEN_ENCRYPTION_KEY="${PLATFORM_TOKEN_ENCRYPTION_KEY:-local-m2-platform-key}"
export PLATFORM_TOKEN_KEY_ID="${PLATFORM_TOKEN_KEY_ID:-local-m2}"

mkdir -p artifacts/m2

run_timed() {
  local name="$1"
  shift
  local start
  start="$(date +%s)"
  "$@"
  local duration
  duration="$(( $(date +%s) - start ))"
  printf '{"target":"%s","duration_seconds":%s}\n' "${name}" "${duration}" >> artifacts/m2/runtime_durations.ndjson
}

case "${TARGET}" in
  validate)
    run_timed validate "${PYTHON_BIN}" scripts/ci/validate_m2_test_feedback_loop.py --local-dev
    ;;
  unit-pure)
    run_timed unit-pure "${PYTHON_BIN}" -m pytest -q -m unit_pure ${M2_TEST_PATHS}
    ;;
  db-invariant)
    run_timed db-invariant "${PYTHON_BIN}" -m pytest -q -m "db_invariant" ${M2_TEST_PATHS}
    ;;
  db-direct)
    run_timed db-direct "${PYTHON_BIN}" -m pytest -q -m "integration_db_direct" ${M2_TEST_PATHS}
    ;;
  db-pooler)
    run_timed db-pooler "${PYTHON_BIN}" -m pytest -q -m "integration_db_pooler" ${M2_TEST_PATHS}
    ;;
  fail-visible-tenant-context)
    run_timed fail-visible-tenant-context "${PYTHON_BIN}" -m pytest -q -m "fail_visible_tenant_context" ${M2_TEST_PATHS}
    ;;
  celery-eager)
    run_timed celery-eager "${PYTHON_BIN}" -m pytest -q -m "celery_eager" ${M2_TEST_PATHS}
    ;;
  celery-worker)
    run_timed celery-worker "${PYTHON_BIN}" -m pytest -q -m "celery_worker" ${M2_TEST_PATHS}
    ;;
  broker-topology)
    run_timed broker-topology "${PYTHON_BIN}" scripts/testing/assert_topology_urls.py
    run_timed broker-negative "${PYTHON_BIN}" scripts/testing/assert_topology_urls.py --expect-rejection
    ;;
  b23-representative)
    run_timed b23-representative "${PYTHON_BIN}" -m pytest -q -m "b23_representative" ${M2_TEST_PATHS}
    ;;
  b24-persistence-readiness)
    run_timed b24-persistence-readiness "${PYTHON_BIN}" -m pytest -q -m "b24_persistence_readiness" ${M2_TEST_PATHS}
    ;;
  governance)
    run_timed governance "${PYTHON_BIN}" -m pytest -q -m "governance" ${M2_TEST_PATHS}
    run_timed m2-validator "${PYTHON_BIN}" scripts/ci/validate_m2_test_feedback_loop.py --local-dev
    ;;
  e2e)
    run_timed e2e "${PYTHON_BIN}" -m pytest -q -m "e2e" ${M2_TEST_PATHS}
    ;;
  external-db-smoke)
    run_timed external-db-smoke "${PYTHON_BIN}" scripts/testing/assert_topology_urls.py --external-smoke
    ;;
  append-only-isolation)
    run_timed append-only-isolation "${PYTHON_BIN}" -m pytest -q -m "append_only_sensitive" ${M2_TEST_PATHS}
    ;;
  skeleton-quarantine)
    run_timed skeleton-quarantine "${PYTHON_BIN}" scripts/ci/validate_m2_test_feedback_loop.py --check-skeletons-only --local-dev
    ;;
  celery-mode-classification)
    run_timed celery-mode-classification "${PYTHON_BIN}" -m pytest -q -m "celery_eager or celery_worker" ${M2_TEST_PATHS}
    ;;
  default)
    run_timed validate "${PYTHON_BIN}" scripts/ci/validate_m2_test_feedback_loop.py --local-dev
    run_timed unit-pure "${PYTHON_BIN}" -m pytest -q -m unit_pure ${M2_TEST_PATHS}
    ;;
  *)
    echo "unknown M2 target: ${TARGET}" >&2
    exit 2
    ;;
esac
