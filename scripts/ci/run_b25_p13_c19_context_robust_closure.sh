#!/usr/bin/env bash
# Reproduce Corrective XIX from an empty PostgreSQL 15 database and the
# production API/worker/signer artifacts. No authoritative business or model
# state is seeded by this runner.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
runtime_root="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/skeldir-c19-${GITHUB_RUN_ID:-local}-$$"
tls_dir="$runtime_root/tls"
evidence_dir="$runtime_root/evidence"
project_name="skeldir-c19-${GITHUB_RUN_ID:-local}-$$"
python_bin="${PYTHON_BIN:-python}"
mkdir -p "$tls_dir" "$evidence_dir"

python_path() {
  if [[ "$python_bin" == *.exe ]] && command -v wslpath >/dev/null 2>&1; then
    wslpath -w "$1" 2>/dev/null || {
      local windows_path="C:${1#/mnt/c}"
      printf '%s\n' "${windows_path//\//\\}"
    }
  else
    printf '%s\n' "$1"
  fi
}

evidence_path_unix="$evidence_dir/c19_context_robust_evidence.json"

export C19_POSTGRES_PORT="${C19_POSTGRES_PORT:-55462}"
export C19_API_PORT="${C19_API_PORT:-18019}"
export C19_COMPOSE_PROJECT_NAME="$project_name"
export C19_REPO_ROOT="$repo_root"
export C19_TLS_DIR="$tls_dir"
export C19_API_BASE_URL="http://127.0.0.1:${C19_API_PORT}"
export C19_EVIDENCE_PATH="$evidence_path_unix"
export C19_ADMIN_DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:${C19_POSTGRES_PORT}/skeldir_c19"

compose=(docker compose -p "$project_name" -f "$repo_root/docker-compose.c19.yml")

collect_logs() {
  "${compose[@]}" ps -a || true
  "${compose[@]}" logs --no-color > "$evidence_dir/c19_compose.log" 2>&1 || true
}

cleanup() {
  collect_logs
  if [[ "${C19_KEEP_TOPOLOGY:-0}" != "1" ]]; then
    "${compose[@]}" down --volumes --remove-orphans || true
  fi
}
trap cleanup EXIT

openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "$tls_dir/ca-key.pem" -out "$tls_dir/ca.pem" \
  -days 2 -subj '/CN=Skeldir C19 Ephemeral CA' >/dev/null 2>&1
openssl req -newkey rsa:2048 -nodes \
  -keyout "$tls_dir/signer-key.pem" -out "$tls_dir/signer.csr" \
  -subj '/CN=trust_signer' >/dev/null 2>&1
printf 'subjectAltName=DNS:trust_signer,DNS:localhost\nextendedKeyUsage=serverAuth\n' \
  > "$tls_dir/signer.ext"
openssl x509 -req -in "$tls_dir/signer.csr" \
  -CA "$tls_dir/ca.pem" -CAkey "$tls_dir/ca-key.pem" -CAcreateserial \
  -out "$tls_dir/signer-cert.pem" -days 2 -extfile "$tls_dir/signer.ext" \
  >/dev/null 2>&1

openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 \
  -out "$runtime_root/jwt-private.pem" >/dev/null 2>&1
openssl pkey -in "$runtime_root/jwt-private.pem" -pubout \
  -out "$runtime_root/jwt-public.pem" >/dev/null 2>&1
export C19_JWT_PRIVATE_KEY_PATH="$runtime_root/jwt-private.pem"

eval "$("$python_bin" - "$(python_path "$runtime_root/jwt-public.pem")" <<'PY' | tr -d '\r'
import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import shlex
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

public_pem = Path(sys.argv[1]).read_text(encoding="utf-8")
seed = os.urandom(32)
private_key = Ed25519PrivateKey.from_private_bytes(seed)
public_bytes = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)
b64 = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
valid_from = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
jwks = {
    "keys": [{
        "kty": "OKP",
        "crv": "Ed25519",
        "alg": "EdDSA",
        "use": "sig",
        "kid": "kid:b25-p13-c19",
        "x": b64(public_bytes),
        "skeldir_key_state": "active",
        "skeldir_valid_from": valid_from,
    }]
}
ring = {"current_kid": "c19-jwt", "keys": {"c19-jwt": public_pem}}
values = {
    "C19_AUTH_JWT_PUBLIC_KEY_RING_JSON": json.dumps(ring, separators=(",", ":")),
    "C19_TRUST_SIGNING_KEY_SEED_B64URL": b64(seed),
    "C19_TRUST_SIGNING_KEY_ID": "kid:b25-p13-c19",
    "C19_TRUST_SIGNING_KEY_VALID_FROM": valid_from,
    "C19_TRUST_PUBLIC_JWKS_JSON": json.dumps(jwks, separators=(",", ":")),
    "C19_TRUST_SIGNER_SHARED_SECRET": b64(os.urandom(32)),
}
for key, value in values.items():
    print(f"export {key}={shlex.quote(value)}")
PY
)"

export C19_API_DATABASE_URL='postgresql://app_user:app_user@postgres:5432/skeldir_c19'
export C19_WORKER_DATABASE_URL='postgresql+asyncpg://app_worker:app_worker@postgres:5432/skeldir_c19'
export C19_PUBLISHER_DATABASE_URL='postgresql+asyncpg://app_dispatch_publisher:app_dispatch_publisher@postgres:5432/skeldir_c19'
export C19_PUBLISHER_SYNC_DATABASE_URL='postgresql://app_dispatch_publisher:app_dispatch_publisher@postgres:5432/skeldir_c19'
export C19_TRANSPORT_DATABASE_URL='postgresql+asyncpg://app_celery_transport:app_celery_transport@postgres:5432/skeldir_c19'
export C19_SIGNER_DATABASE_URL='postgresql+asyncpg://app_trust_signer:app_trust_signer@postgres:5432/skeldir_c19'
export C19_ISSUER_DATABASE_URL='postgresql+asyncpg://app_trust_issuer:app_trust_issuer@postgres:5432/skeldir_c19'
export C19_CELERY_BROKER_URL='sqla+postgresql://app_celery_transport:app_celery_transport@postgres:5432/skeldir_c19'
export C19_CELERY_RESULT_BACKEND='db+postgresql://app_celery_transport:app_celery_transport@postgres:5432/skeldir_c19'

# GitHub Actions runs teardown in a fresh shell. Preserve the exact ephemeral
# Compose interpolation context without printing it so that a kept topology can
# still be removed after the physical severance checks. The workflow deletes
# this capsule as part of teardown.
if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
  teardown_env="${RUNNER_TEMP:?RUNNER_TEMP is required in GitHub Actions}/c19-teardown.env"
  : > "$teardown_env"
  teardown_names=(
    C19_POSTGRES_PORT C19_API_PORT C19_TLS_DIR
    C19_API_DATABASE_URL C19_WORKER_DATABASE_URL
    C19_PUBLISHER_DATABASE_URL C19_PUBLISHER_SYNC_DATABASE_URL
    C19_TRANSPORT_DATABASE_URL C19_SIGNER_DATABASE_URL C19_ISSUER_DATABASE_URL
    C19_CELERY_BROKER_URL C19_CELERY_RESULT_BACKEND
    C19_AUTH_JWT_PUBLIC_KEY_RING_JSON C19_TRUST_PUBLIC_JWKS_JSON
    C19_TRUST_SIGNING_KEY_SEED_B64URL C19_TRUST_SIGNING_KEY_ID
    C19_TRUST_SIGNING_KEY_VALID_FROM C19_TRUST_SIGNER_SHARED_SECRET
  )
  for name in "${teardown_names[@]}"; do
    printf '%s=%s\n' "$name" "${!name}" >> "$teardown_env"
  done
  chmod 600 "$teardown_env"
fi

"${compose[@]}" config --quiet
"${compose[@]}" up -d postgres
for _ in $(seq 1 60); do
  if [[ "$(docker inspect -f '{{.State.Health.Status}}' "${project_name}-postgres-1" 2>/dev/null || true)" == "healthy" ]]; then
    break
  fi
  sleep 1
done
test "$(docker inspect -f '{{.State.Health.Status}}' "${project_name}-postgres-1")" = healthy
sleep 2

"$python_bin" "$(python_path "$repo_root/scripts/database/prepare_migration_authority_boundary.py")" \
  --admin-dsn "postgresql://postgres:postgres@127.0.0.1:${C19_POSTGRES_PORT}/postgres" \
  --database-name skeldir_c19 --rotate-existing-credentials \
  | tee "$evidence_dir/c19_authority_boundary.out"

export MIGRATION_DATABASE_URL="postgresql://migration_owner:migration_owner@127.0.0.1:${C19_POSTGRES_PORT}/skeldir_c19"
export DATABASE_URL="postgresql+asyncpg://app_user:app_user@127.0.0.1:${C19_POSTGRES_PORT}/skeldir_c19"
if [[ "$python_bin" == *.exe ]]; then
  export WSLENV="${WSLENV:+$WSLENV:}MIGRATION_DATABASE_URL:DATABASE_URL"
fi
"$python_bin" -m alembic upgrade head | tee "$evidence_dir/c19_migration_replay.out"
"$python_bin" -m alembic current | tee "$evidence_dir/c19_migration_head.out"
if [[ "$python_bin" == *.exe ]]; then
  unset WSLENV
fi

"${compose[@]}" up -d --build \
  trust_signer api worker_attribution worker_b23_a worker_b23_b \
  worker_bayesian worker_publisher beat
for _ in $(seq 1 120); do
  if curl --fail --silent "$C19_API_BASE_URL/health/ready" >/dev/null; then
    break
  fi
  sleep 2
done
curl --fail --silent "$C19_API_BASE_URL/health/ready" \
  | tee "$evidence_dir/c19_api_ready.json"
# A process that dies during bring-up must say why. Without this the topology
# assertion reports only "not running", which makes every bring-up red
# indistinguishable from every other one -- and a first red that cannot be
# explained cannot be dispositioned.
c19_report_topology_failure() {
  local failed="$1"
  echo "c19_topology_service_not_running=$failed"
  "${compose[@]}" ps --all || true
  local service
  for service in postgres trust_signer api worker_attribution worker_b23_a \
      worker_b23_b worker_bayesian worker_publisher beat; do
    echo "----- c19 container logs: $service -----"
    "${compose[@]}" logs --no-color --tail 120 "$service" 2>&1 || true
  done
}

# Every service declares `restart: no`, deliberately: a process that dies must
# stay dead and be seen. That makes the distinction between "has not finished
# starting" and "started and exited" load-bearing, so it is drawn explicitly
# rather than by whichever happens to be true at the instant the API answers.
# An exited container is fatal immediately; a not-yet-running one is waited on.
c19_await_topology() {
  local service attempt state
  for attempt in $(seq 1 60); do
    local pending=0
    for service in worker_attribution worker_b23_a worker_b23_b \
        worker_bayesian worker_publisher beat; do
      state="$("${compose[@]}" ps --all --format '{{.Service}} {{.State}}' \
        | awk -v s="$service" '$1 == s {print $2}' | head -1)"
      case "$state" in
        running) ;;
        exited|dead)
          echo "c19_topology_service_exited=$service state=$state"
          c19_report_topology_failure "$service"
          return 1
          ;;
        *) pending=1 ;;
      esac
    done
    if [[ "$pending" -eq 0 ]]; then
      echo "c19_topology_services_running=9"
      return 0
    fi
    sleep 2
  done
  echo "c19_topology_services_never_started"
  c19_report_topology_failure "timeout"
  return 1
}

c19_await_topology

export PYTHONPATH="$repo_root/backend"
export SKELDIR_B25_P13_C19_TOPOLOGY_PROOF=1
# Corrective XX. The verdict fence is proved against the retained
# production topology, under the same real roles the nine processes hold.
export SKELDIR_B25_P13_C20_RUNTIME_AUTHORITY_PROOF=1
export C20_ADMIN_DATABASE_URL="$C19_ADMIN_DATABASE_URL"
export C20_EVIDENCE_PATH="$evidence_dir/b25_p13_c20_runtime_authority_evidence.json"
# Corrective XXI. Same argument, one layer further down the spine: B2.4
# freshness authority and durable issuance history are proved here, against the
# database the nine production processes are actually connected to, under the
# same real logins they hold.
export SKELDIR_B25_P13_C21_AUTHORITY_PROOF=1
export C21_ADMIN_DATABASE_URL="$C19_ADMIN_DATABASE_URL"
export C21_EVIDENCE_PATH="$evidence_dir/b25_p13_c21_authority_evidence.json"
echo "c19_topology_test_path=$repo_root/backend/tests/trust/test_b25_p13_c19_context_robust_topology.py"
echo "c20_authority_test_path=$repo_root/backend/tests/trust/test_b25_p13_c20_runtime_authority.py"
echo "c21_authority_test_path=$repo_root/backend/tests/trust/test_b25_p13_c21_freshness_issuance_authority.py"
if [[ "$python_bin" == *.exe ]]; then
  powershell_runner="$runtime_root/run-c19-observer.ps1"
  : > "$powershell_runner"
  printf '%s\n' '$ErrorActionPreference = "Stop"' >> "$powershell_runner"
  observer_env=(
    MIGRATION_DATABASE_URL DATABASE_URL
    C19_POSTGRES_PORT C19_API_PORT C19_COMPOSE_PROJECT_NAME
    C19_API_BASE_URL C19_ADMIN_DATABASE_URL
    C19_CELERY_BROKER_URL C19_CELERY_RESULT_BACKEND
    C19_AUTH_JWT_PUBLIC_KEY_RING_JSON C19_TRUST_PUBLIC_JWKS_JSON
    C19_TRUST_SIGNING_KEY_SEED_B64URL C19_TRUST_SIGNING_KEY_ID
    C19_TRUST_SIGNING_KEY_VALID_FROM C19_TRUST_SIGNER_SHARED_SECRET
    C19_API_DATABASE_URL C19_WORKER_DATABASE_URL
    C19_PUBLISHER_DATABASE_URL C19_PUBLISHER_SYNC_DATABASE_URL
    C19_TRANSPORT_DATABASE_URL C19_SIGNER_DATABASE_URL C19_ISSUER_DATABASE_URL
    SKELDIR_B25_P13_C19_TOPOLOGY_PROOF SKELDIR_B25_P13_C20_RUNTIME_AUTHORITY_PROOF
    C20_ADMIN_DATABASE_URL C20_EVIDENCE_PATH
    SKELDIR_B25_P13_C21_AUTHORITY_PROOF
    C21_ADMIN_DATABASE_URL C21_EVIDENCE_PATH
    C19_REPO_ROOT C19_TLS_DIR C19_EVIDENCE_PATH C19_JWT_PRIVATE_KEY_PATH PYTHONPATH
  )
  for name in "${observer_env[@]}"; do
    value="${!name:-}"
    case "$name" in
      C19_REPO_ROOT|C19_TLS_DIR|C19_EVIDENCE_PATH|C20_EVIDENCE_PATH|C21_EVIDENCE_PATH|C19_JWT_PRIVATE_KEY_PATH|PYTHONPATH)
        value="$(python_path "$value")"
        ;;
    esac
    encoded="$(printf '%s' "$value" | base64 -w 0)"
    printf '$env:%s = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("%s"))\n' \
      "$name" "$encoded" >> "$powershell_runner"
  done
  printf 'Set-Location -LiteralPath "%s"\n' "$(python_path "$repo_root")" >> "$powershell_runner"
  printf '& "%s" -m pytest backend/tests/trust/test_b25_p13_c19_context_robust_topology.py backend/tests/trust/test_b25_p13_c20_runtime_authority.py backend/tests/trust/test_b25_p13_c21_freshness_issuance_authority.py -q -s --no-header -p no:randomly *>&1 | Tee-Object -FilePath "%s"\n' \
    "$(python_path "$python_bin")" "$(python_path "$evidence_dir/c19_topology_pytest.out")" \
    >> "$powershell_runner"
  printf '%s\n' 'if ($null -eq $LASTEXITCODE) { exit 1 }' >> "$powershell_runner"
  printf '%s\n' 'exit $LASTEXITCODE' >> "$powershell_runner"
  observer_status=1
  for _ in 1 2 3; do
    set +e
    powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
      -File "$(python_path "$powershell_runner")"
    observer_status=$?
    set -e
    if [[ -f "$evidence_dir/c19_topology_pytest.out" ]]; then
      break
    fi
    sleep 2
  done
  if [[ -f "$evidence_dir/c19_topology_pytest.out" ]]; then
    cat "$evidence_dir/c19_topology_pytest.out"
  fi
  test "$observer_status" -eq 0
else
  "$python_bin" -m pytest \
    backend/tests/trust/test_b25_p13_c19_context_robust_topology.py \
    backend/tests/trust/test_b25_p13_c20_runtime_authority.py \
    backend/tests/trust/test_b25_p13_c21_freshness_issuance_authority.py \
    -q -s --no-header -p no:randomly \
    2>&1 | tee "$evidence_dir/c19_topology_pytest.out"
fi

"$python_bin" - "$(python_path "$evidence_path_unix")" <<'PY'
import json
from pathlib import Path
import sys

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
assert payload["status"] == "PASS"
assert payload["authoritative_state_seeded"] is False
assert payload["settlement_count"] == 20
assert payload["confirmed_verdicts"] == 20
assert payload["verified_allocations"] == 20
assert payload["diagnostic_status"] == "passed"
assert payload["signature_verified_by_public_key"] is True
assert payload["remote_signer_absence_failed_closed"] is True
assert set(payload["concurrency_cases"].keys()) == {
    "A_exact_duplicate",
    "B_same_commerce_different_provider_event",
    "C_unrelated_same_tenant",
    "D_same_refs_different_tenant",
    "E_transition_race",
    "F_rows_arriving_during_work",
    "G_worker_restart_with_peer",
    "H_database_lock_contention",
}
print("B25_P13_C19_CONTEXT_ROBUST_CLOSURE_PASS")
PY

"$python_bin" - "$(python_path "$C20_EVIDENCE_PATH")" <<'PY'
import json
from pathlib import Path
import sys

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
conservation = payload["c20_authority_conservation"]
falsifier = payload["c20_layer_falsifier"]
# Forbidden direction refused, lawful direction still conducts.
assert conservation["app_user_transition"]["result"] == "REFUSED"
assert conservation["app_user_insert"]["result"] == "REFUSED"
assert conservation["app_user_cross_tenant"]["result"] == "REFUSED"
assert conservation["app_worker_transition"]["result"] == "ALLOWED"
assert conservation["allocation_after_lawful_transition"] == [
    True,
    "b23_match_verdict",
]
# Each layer refuses alone; only both severed reproduces the historical RED.
assert falsifier["historical_grant_restored"]["result"] == "REFUSED"
assert falsifier["guard_trigger_severed"]["result"] == "REFUSED"
assert falsifier["both_layers_severed"]["result"] == "ALLOWED"
assert falsifier["historical_downstream_consequence"] == [
    True,
    "b23_match_verdict",
]
assert falsifier["after_exact_restoration"]["result"] == "REFUSED"
assert payload["violations"] == []
print("B25_P13_C20_VERDICT_AUTHORITY_CONSERVED")
PY

evidence_artifact="$repo_root/docs/forensics/evidence/b25_p13_c19_context_robust_evidence.json"
cp "$evidence_path_unix" "$evidence_artifact"
echo "c19_evidence_artifact=$evidence_artifact"
c20_evidence_artifact="$repo_root/docs/forensics/evidence/b25_p13_c20_runtime_authority_evidence.json"
cp "$C20_EVIDENCE_PATH" "$c20_evidence_artifact"
echo "c20_evidence_artifact=$c20_evidence_artifact"
