#!/bin/bash
# scripts/r0/run_preflight_normalized.sh
# Executes R0 preflight checks and outputs normalized JSON (no timestamps in normalized fields)
#
# Usage: run_preflight_normalized.sh
# Outputs: JSON to stdout with deterministic fields only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Collect normalized preflight results
cat <<EOF
{
  "repo_anchor": {
    "head_sha": "$(git -C "$ROOT_DIR" rev-parse HEAD)",
    "branch": "$(git -C "$ROOT_DIR" rev-parse --abbrev-ref HEAD)",
    "status": "$(git -C "$ROOT_DIR" status --porcelain | wc -l) files modified"
  },
  "lockfile_present": $([ -f "$ROOT_DIR/backend/requirements-lock.txt" ] && echo "true" || echo "false"),
  "lockfile_sha256": "$(sha256sum "$ROOT_DIR/backend/requirements-lock.txt" 2>/dev/null | cut -d' ' -f1 || echo 'missing')",
  "workflow_file_sha256": "$(sha256sum "$ROOT_DIR/.github/workflows/r0-preflight-validation.yml" | cut -d' ' -f1)",
  "network_isolation_script_sha256": "$(sha256sum "$ROOT_DIR/scripts/r0/enforce_network_isolation.sh" | cut -d' ' -f1)",
  "normalization_script_sha256": "$(sha256sum "$ROOT_DIR/scripts/r0/normalize_pg_dump.sh" | cut -d' ' -f1)"
}
EOF
