#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

echo "[negative-control] Start"

ORIG_RT="backend/app/services/realtime_revenue_response.py"
BACKUP_RT="$(mktemp)"
cp "$ORIG_RT" "$BACKUP_RT"
ORIG_ATTR="api-contracts/openapi/v1/attribution.yaml"
BACKUP_ATTR="$(mktemp)"
cp "$ORIG_ATTR" "$BACKUP_ATTR"
ORIG_BASE="api-contracts/openapi/v1/_common/base.yaml"
BACKUP_BASE="$(mktemp)"
cp "$ORIG_BASE" "$BACKUP_BASE"
ORIG_AUTH="backend/app/security/auth.py"
BACKUP_AUTH="$(mktemp)"
cp "$ORIG_AUTH" "$BACKUP_AUTH"
ORIG_TASK_CONTEXT="backend/app/tasks/context.py"
BACKUP_TASK_CONTEXT="$(mktemp)"
cp "$ORIG_TASK_CONTEXT" "$BACKUP_TASK_CONTEXT"

cleanup() {
  cp "$BACKUP_RT" "$ORIG_RT" || true
  cp "$BACKUP_ATTR" "$ORIG_ATTR" || true
  cp "$BACKUP_BASE" "$ORIG_BASE" || true
  cp "$BACKUP_AUTH" "$ORIG_AUTH" || true
  cp "$BACKUP_TASK_CONTEXT" "$ORIG_TASK_CONTEXT" || true
  rm -f "$BACKUP_RT" || true
  rm -f "$BACKUP_ATTR" || true
  rm -f "$BACKUP_BASE" || true
  rm -f "$BACKUP_AUTH" || true
  rm -f "$BACKUP_TASK_CONTEXT" || true
  rm -f frontend/src/contract-consumption-negative-control.ts || true
  rm -f frontend/tsconfig.contract-gate.negative.json || true
  rm -f /tmp/auth.breaking.yaml || true
}
trap cleanup EXIT

echo "[negative-control] 1/3 Runtime conformance should fail when backend drifts"
python - <<'PY'
from pathlib import Path

path = Path("backend/app/services/realtime_revenue_response.py")
text = path.read_text(encoding="utf-8")
needle = '"total_revenue": snapshot.revenue_total_cents / 100.0,'
replacement = '"total_revenue": "not-a-number",'
if needle not in text:
    raise SystemExit("Unable to apply runtime negative control mutation")
path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
PY

if DATABASE_URL="postgresql://postgres:postgres@localhost:5432/postgres" \
  pytest tests/contract/test_contract_semantics.py -q -k test_attribution_revenue_realtime_happy_path; then
  echo "[negative-control] ERROR: runtime conformance did not fail under intentional drift"
  exit 1
fi
cp "$BACKUP_RT" "$ORIG_RT"

echo "[negative-control] 2/3 Frontend contract compile should fail under type drift"
cat > frontend/src/contract-consumption-negative-control.ts <<'TS'
import type { operations as attributionOps } from "./types/api/attribution";

type Realtime200 =
  attributionOps["getRealtimeRevenue"]["responses"]["200"]["content"]["application/json"];

const shouldFail: Realtime200 = {
  total_revenue: "not-a-number",
  event_count: 1,
  last_updated: "2026-02-10T00:00:00Z",
  data_freshness_seconds: 1,
  verified: true,
  tenant_id: "00000000-0000-0000-0000-000000000000",
};

void shouldFail;
TS

cat > frontend/tsconfig.contract-gate.negative.json <<'JSON'
{
  "extends": "./tsconfig.json",
  "compilerOptions": {
    "noUnusedLocals": false,
    "noUnusedParameters": false
  },
  "include": ["src/contract-consumption-negative-control.ts", "src/types/api/**/*.ts"]
}
JSON

if npx --yes -p typescript@5.6.3 tsc -p frontend/tsconfig.contract-gate.negative.json --noEmit; then
  echo "[negative-control] ERROR: frontend compile did not fail under intentional type drift"
  exit 1
fi
rm -f frontend/src/contract-consumption-negative-control.ts frontend/tsconfig.contract-gate.negative.json

echo "[negative-control] 3/3 oasdiff should fail on breaking contract change"
if ! command -v oasdiff >/dev/null 2>&1; then
  echo "[negative-control] ERROR: oasdiff is not installed or not on PATH"
  exit 1
fi

python - <<'PY'
from pathlib import Path
import yaml

src = Path("api-contracts/dist/openapi/v1/auth.bundled.yaml")
dst = Path("/tmp/auth.breaking.yaml")
doc = yaml.safe_load(src.read_text(encoding="utf-8"))
doc["paths"]["/api/auth/login"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"]["access_token"]["type"] = "integer"
dst.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
PY

OASDIFF_OUT="$(mktemp)"
oasdiff breaking api-contracts/dist/openapi/v1/auth.bundled.yaml /tmp/auth.breaking.yaml >"$OASDIFF_OUT" 2>&1 || true
cat "$OASDIFF_OUT"
if grep -q "0 changes" "$OASDIFF_OUT"; then
  echo "[negative-control] ERROR: oasdiff did not detect intentional breaking change"
  exit 1
fi
rm -f "$OASDIFF_OUT"

echo "[negative-control] 4/8 Auth topology drift should fail contract adjudication"
python - <<'PY'
from pathlib import Path

path = Path("api-contracts/openapi/v1/attribution.yaml")
text = path.read_text(encoding="utf-8")
needle = "security:\n  - bearerAuth: []\n"
replacement = "security: []\n"
if needle not in text:
    raise SystemExit("Unable to apply auth topology negative control mutation")
path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
PY

bash scripts/contracts/bundle.sh
if DATABASE_URL="postgresql://postgres:postgres@localhost:5432/postgres" \
  pytest tests/contract/test_contract_semantics.py -q -k test_contract_auth_topology_and_error_surface; then
  echo "[negative-control] ERROR: contract adjudication did not fail under auth topology drift"
  exit 1
fi
cp "$BACKUP_ATTR" "$ORIG_ATTR"
bash scripts/contracts/bundle.sh

echo "[negative-control] 5/8 401 schema drift should fail contract adjudication"
python - <<'PY'
from pathlib import Path

path = Path("api-contracts/openapi/v1/_common/base.yaml")
text = path.read_text(encoding="utf-8")
needle = "application/problem+json:"
replacement = "application/json:"
if needle not in text:
    raise SystemExit("Unable to apply error schema negative control mutation")
path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
PY

bash scripts/contracts/bundle.sh
if DATABASE_URL="postgresql://postgres:postgres@localhost:5432/postgres" \
  pytest tests/contract/test_contract_semantics.py -q -k test_contract_auth_topology_and_error_surface; then
  echo "[negative-control] ERROR: contract adjudication did not fail under error schema drift"
  exit 1
fi
cp "$BACKUP_BASE" "$ORIG_BASE"
bash scripts/contracts/bundle.sh

echo "[negative-control] 6/8 403 schema drift should fail contract adjudication"
python - <<'PY'
from pathlib import Path

path = Path("api-contracts/openapi/v1/_common/base.yaml")
text = path.read_text(encoding="utf-8")
needle = "    ForbiddenError:\n      description: Authentication is valid but action is not permitted.\n      headers:\n        X-Correlation-ID:\n          $ref: '#/components/headers/X-Correlation-ID'\n      content:\n        application/problem+json:\n          schema:\n            $ref: '#/components/schemas/ProblemDetails'\n"
replacement = "    ForbiddenError:\n      description: Authentication is valid but action is not permitted.\n      headers:\n        X-Correlation-ID:\n          $ref: '#/components/headers/X-Correlation-ID'\n      content:\n        application/json:\n          schema:\n            $ref: '#/components/schemas/ProblemDetails'\n"
if needle not in text:
    raise SystemExit("Unable to apply 403 schema negative control mutation")
path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
PY

bash scripts/contracts/bundle.sh
if DATABASE_URL="postgresql://postgres:postgres@localhost:5432/postgres" \
  pytest tests/contract/test_contract_semantics.py -q -k test_contract_auth_topology_and_error_surface; then
  echo "[negative-control] ERROR: contract adjudication did not fail under 403 schema drift"
  exit 1
fi
cp "$BACKUP_BASE" "$ORIG_BASE"
bash scripts/contracts/bundle.sh

echo "[negative-control] 7/8 JWT missing-tenant invariant should fail under bypass mutation"
python - <<'PY'
from pathlib import Path

path = Path("backend/app/security/auth.py")
text = path.read_text(encoding="utf-8")
needle = 'tenant_id = claims.get("tenant_id")'
replacement = 'tenant_id = claims.get("tenant_id") or "00000000-0000-0000-0000-000000000000"'
if needle not in text:
    raise SystemExit("Unable to apply JWT tenant invariant negative control mutation")
path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
PY

if pytest tests/test_b060_phase1_auth_tenant.py -q -k test_missing_tenant_claim_returns_401; then
  echo "[negative-control] ERROR: JWT tenant-context invariant did not fail under bypass mutation"
  exit 1
fi
cp "$BACKUP_AUTH" "$ORIG_AUTH"

echo "[negative-control] 8/8 worker @tenant_task invariant should fail under bypass mutation"
python - <<'PY'
from pathlib import Path

path = Path("backend/app/tasks/context.py")
text = path.read_text(encoding="utf-8")
needle = "        if tenant_id_value is None:\n            raise ValueError(\"tenant_id is required for tenant-scoped tasks\")\n"
replacement = "        if False and tenant_id_value is None:\n            raise ValueError(\"tenant_id is required for tenant-scoped tasks\")\n"
if needle not in text:
    raise SystemExit("Unable to apply worker tenant-task negative control mutation")
path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
PY

if pytest backend/tests/test_b07_p1_identity_guc.py -q -k test_worker_tenant_task_rejects_missing_tenant_envelope; then
  echo "[negative-control] ERROR: worker tenant-task invariant did not fail under bypass mutation"
  exit 1
fi
cp "$BACKUP_TASK_CONTEXT" "$ORIG_TASK_CONTEXT"

echo "[negative-control] PASS"
