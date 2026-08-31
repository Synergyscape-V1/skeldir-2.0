#!/usr/bin/env bash
# Reproduce the P13 production Bayesian topology from a clean clone.
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$repo_root"

db_host=${C16_TOPOLOGY_DB_HOST:-127.0.0.1}
db_port=${C16_TOPOLOGY_DB_PORT:-55432}
db_name=${C16_TOPOLOGY_DB_NAME:-skeldir_b25_p13_c16_topology}
admin_user=${C16_TOPOLOGY_ADMIN_USER:-postgres}
admin_password=${C16_TOPOLOGY_ADMIN_PASSWORD:-postgres}
image=${C16_TOPOLOGY_IMAGE:-skeldir-bayesian:c16-topology-proof}
execution_container=${C16_TOPOLOGY_EXECUTION_CONTAINER:-skeldir-c16-execution}
publisher_container=${C16_TOPOLOGY_PUBLISHER_CONTAINER:-skeldir-c16-publisher}
prometheus_dir=${C16_TOPOLOGY_PROMETHEUS_DIR:-/tmp/skeldir-c16-prometheus}

admin_dsn="postgresql://${admin_user}:${admin_password}@${db_host}:${db_port}/postgres"
migration_dsn="postgresql://migration_owner:migration_owner@${db_host}:${db_port}/${db_name}"
worker_dsn="postgresql://app_worker:app_worker@${db_host}:${db_port}/${db_name}"
publisher_dsn="postgresql://app_dispatch_publisher:app_dispatch_publisher@${db_host}:${db_port}/${db_name}"
issuer_dsn="postgresql://app_trust_issuer:app_trust_issuer@${db_host}:${db_port}/${db_name}"
signer_dsn="postgresql://app_trust_signer:app_trust_signer@${db_host}:${db_port}/${db_name}"

beat_pid=""
cleanup() {
  if [[ -n "$beat_pid" ]]; then
    kill "$beat_pid" >/dev/null 2>&1 || true
  fi
  docker rm -f "$execution_container" "$publisher_container" >/dev/null 2>&1 || true
}
trap cleanup EXIT

python scripts/database/prepare_migration_authority_boundary.py \
  --admin-dsn "$admin_dsn" \
  --database-name "$db_name" \
  --runtime-user app_user \
  --runtime-password app_user \
  --migration-user migration_owner \
  --migration-password migration_owner \
  --app-rw-role app_rw \
  --app-ro-role app_ro \
  --worker-user app_worker \
  --worker-password app_worker \
  --publisher-user app_dispatch_publisher \
  --publisher-password app_dispatch_publisher \
  --trust-issuer-user app_trust_issuer \
  --trust-issuer-password app_trust_issuer \
  --trust-signer-user app_trust_signer \
  --trust-signer-password app_trust_signer

DATABASE_URL="$migration_dsn" MIGRATION_DATABASE_URL="$migration_dsn" \
  ENVIRONMENT=local python -m alembic upgrade head

role_flags=$(PGPASSWORD=app_worker psql "$worker_dsn" -tAc \
  "SELECT rolbypassrls::text || ':' || rolsuper::text FROM pg_roles WHERE rolname = current_user")
[[ "$role_flags" == "false:false" || "$role_flags" == "f:f" ]]

# B2.5-P13 Corrective XVI. Issuance-consequence authority is a separate login,
# so the auditor observes it here rather than inferring it from configuration.
issuer_identity=$(PGPASSWORD=app_trust_issuer psql "$issuer_dsn" -tAc "SELECT current_user")
[[ "$issuer_identity" == "app_trust_issuer" ]]
issuer_flags=$(PGPASSWORD=app_trust_issuer psql "$issuer_dsn" -tAc \
  "SELECT rolbypassrls::text || ':' || rolsuper::text FROM pg_roles WHERE rolname = current_user")
[[ "$issuer_flags" == "false:false" || "$issuer_flags" == "f:f" ]]

signer_identity=$(PGPASSWORD=app_trust_signer psql "$signer_dsn" -tAc "SELECT current_user")
[[ "$signer_identity" == "app_trust_signer" ]]
signer_flags=$(PGPASSWORD=app_trust_signer psql "$signer_dsn" -tAc \
  "SELECT rolbypassrls::text || ':' || rolsuper::text FROM pg_roles WHERE rolname = current_user")
[[ "$signer_flags" == "false:false" || "$signer_flags" == "f:f" ]]

docker build -f backend/Dockerfile.bayesian -t "$image" .
image_id=$(docker image inspect "$image" --format '{{.Id}}')
image_cmd=$(docker image inspect "$image" --format '{{json .Config.Cmd}}')
[[ "$image_cmd" == *celery* && "$image_cmd" == *bayesian* ]]

docker run --rm -i "$image" \
  python - < scripts/ci/validate_b25_p13_c13_artifact_closure.py

for run in 1 2; do
  topology_output=$(docker run --rm -i "$image" \
    python - < scripts/ci/validate_b24_artifact_topology.py 2>&1)
  printf '%s\n' "$topology_output"
  grep -q 'B24_ARTIFACT_TOPOLOGY_PASS' <<<"$topology_output"
  grep -q 'Sequential sampling (4 chains in 1 job)' <<<"$topology_output"
  grep -q '"observed_posterior_draws_total": 4000' <<<"$topology_output"
  grep -q '"divergence_count": 0' <<<"$topology_output"
  grep -q '"identical_chain_pairs": \[\]' <<<"$topology_output"
done

containment_output=$(docker run --rm -i "$image" python - <<'PY'
import json
import os

from app.bayesian.runtime_policy import build_runtime_policy

runtime = build_runtime_policy()
assert runtime.pymc_chains == 4
assert runtime.pymc_cores == 1
assert runtime.blas_total_threads == 1
for variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    assert os.environ.get(variable) == "1", (variable, os.environ.get(variable))
print("B24_ARTIFACT_CONTAINMENT_PASS " + json.dumps({
    "chains": runtime.pymc_chains,
    "cores": runtime.pymc_cores,
    "blas_total_threads": runtime.blas_total_threads,
    "worker_concurrency": runtime.worker_concurrency,
}, sort_keys=True))
PY
)
printf '%s\n' "$containment_output"
grep -q 'B24_ARTIFACT_CONTAINMENT_PASS' <<<"$containment_output"

export DATABASE_URL="$worker_dsn"
export MIGRATION_DATABASE_URL="$migration_dsn"
export B24_DISPATCH_PUBLISHER_DATABASE_URL="$publisher_dsn"
export TRUST_ISSUANCE_DATABASE_URL="$issuer_dsn"
export TRUST_SIGNER_DATABASE_URL="$signer_dsn"
export CELERY_BROKER_URL="sqla+${worker_dsn}"
export CELERY_RESULT_BACKEND="db+${worker_dsn}"
export PYTHONPATH="$repo_root:$repo_root/backend"
export TESTING=1
export CI=true
export SKELDIR_B25_P13_C9_POSITIVE_PROOF=1
export SKELDIR_B25_P13_C11_DB_PROOF=1
export SKELDIR_B25_P13_C11_EXTERNAL_WORKER=1
export SKELDIR_CELERY_WORKER_ROLE=bayesian
export SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS=1
export SKELDIR_BAYESIAN_DB_TOPOLOGY=direct_postgres
# The governed registry intentionally accepts only durable semantic labels.
# This run physically verifies the attestation below; it does not mint a new
# ad-hoc label that production code would (correctly) reject.
export SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION=direct_postgres_deployment_attested
export SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE=independent_postgres_15
export SKELDIR_BAYESIAN_DB_BACKEND_AFFINITY=connection_lifetime
export PLATFORM_TOKEN_ENCRYPTION_KEY=test-platform-key
export PLATFORM_TOKEN_KEY_ID=test-key
export PROMETHEUS_MULTIPROC_DIR="$prometheus_dir"
mkdir -p "$prometheus_dir"

docker run -d --rm --network host --name "$execution_container" \
  -e DATABASE_URL -e CELERY_BROKER_URL -e CELERY_RESULT_BACKEND \
  -e TESTING -e CI \
  -e SKELDIR_BAYESIAN_DB_TOPOLOGY \
  -e SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION \
  -e SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE \
  -e SKELDIR_BAYESIAN_DB_BACKEND_AFFINITY \
  "$image" >/dev/null

docker run -d --rm --network host --name "$publisher_container" \
  -e DATABASE_URL="$publisher_dsn" \
  -e B24_DISPATCH_PUBLISHER_DATABASE_URL="$publisher_dsn" \
  -e CELERY_BROKER_URL="sqla+${publisher_dsn}" \
  -e CELERY_RESULT_BACKEND="db+${publisher_dsn}" \
  -e SKELDIR_CELERY_WORKER_ROLE=bayesian_publisher \
  -e SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS=0 \
  -e TESTING -e CI \
  -e SKELDIR_BAYESIAN_DB_TOPOLOGY \
  -e SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION \
  -e SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE \
  -e SKELDIR_BAYESIAN_DB_BACKEND_AFFINITY \
  "$image" celery -A app.celery_app.celery_app worker \
    -Q bayesian_publisher --loglevel=INFO --concurrency=1 >/dev/null

for container in "$execution_container" "$publisher_container"; do
  ready=0
  for _attempt in $(seq 1 90); do
    boot_log=$(docker logs "$container" 2>&1)
    if grep -q ' ready' <<<"$boot_log"; then
      ready=1
      break
    fi
    sleep 1
  done
  [[ "$ready" == 1 ]] || {
    docker logs "$container"
    exit 1
  }
done

(
  cd backend
  B24_FIT_PLANNER_INTERVAL_SECONDS=1 \
  SKELDIR_B24_DISABLE_FIT_PLANNER_JOB=1 \
  SKELDIR_B24_P9_DISABLE_RECOVERY_RECONCILER_JOB=1 \
    celery -A app.celery_app.celery_app beat --loglevel=INFO \
      --pidfile= --schedule=/tmp/c16-celerybeat-schedule
) >/tmp/c16-topology-beat.log 2>&1 &
beat_pid=$!

python -m pytest \
  backend/tests/trust/test_b25_p13_c9_positive_confidence.py \
  -q -s --no-header \
  -k real_posterior_is_produced_by_the_chain_that_claims_it

docker logs "$execution_container" >/tmp/c16-topology-execution.log 2>&1
docker logs "$publisher_container" >/tmp/c16-topology-publisher.log 2>&1
grep -q 'app.tasks.bayesian.execute_fit_intent' /tmp/c16-topology-execution.log
grep -q 'app.tasks.bayesian.publish_due_fit_dispatches' /tmp/c16-topology-publisher.log

printf 'c16_topology_git_sha=%s\n' "$(git rev-parse HEAD)"
printf 'c16_topology_image_id=%s\n' "$image_id"
printf 'c16_topology_role_flags=%s\n' "$role_flags"
printf 'c16_topology_statistical_repeats=2\n'
printf 'c16_topology_distinct_principals=2\n'
printf 'B25_P13_C16_PRODUCTION_TOPOLOGY_PASS\n'
