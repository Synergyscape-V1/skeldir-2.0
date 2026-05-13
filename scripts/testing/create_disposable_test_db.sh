#!/usr/bin/env bash
set -euo pipefail

ADMIN_DATABASE_URL="${ADMIN_DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:5432/postgres}"
TEMPLATE_DB="${TEMPLATE_DB:-skeldir_test_template}"
DISPOSABLE_DB="${DISPOSABLE_DB:-skeldir_test_$(date +%s)_${RANDOM}}"
ARTIFACT_DIR="${M2_ARTIFACT_DIR:-artifacts/m2}"

mkdir -p "${ARTIFACT_DIR}"
start_epoch="$(date +%s)"

psql "${ADMIN_DATABASE_URL}" -v ON_ERROR_STOP=1 <<SQL
CREATE DATABASE ${DISPOSABLE_DB} TEMPLATE ${TEMPLATE_DB};
SQL

duration="$(( $(date +%s) - start_epoch ))"
cat > "${ARTIFACT_DIR}/disposable_db_measurement.json" <<JSON
{"strategy":"create_database_from_template","template_db":"${TEMPLATE_DB}","disposable_db":"${DISPOSABLE_DB}","duration_seconds":${duration}}
JSON
echo "DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/${DISPOSABLE_DB}" > "${ARTIFACT_DIR}/disposable_db.env"
echo "M2 disposable DB ${DISPOSABLE_DB} created in ${duration}s"
