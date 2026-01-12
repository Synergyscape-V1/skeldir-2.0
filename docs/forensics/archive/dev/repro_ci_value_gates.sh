#!/usr/bin/env bash
#
# ARCHIVED: CI-like reproduction harness for VALUE gates (local debugging only).
#
# NOTE: This file is intentionally located under docs/forensics/archive/** so it does not
# violate the Zero Container Doctrine enforcement in CI.
#
# Usage:
#   bash docs/forensics/archive/dev/repro_ci_value_gates.sh VALUE_01
#   bash docs/forensics/archive/dev/repro_ci_value_gates.sh VALUE_03
#   bash docs/forensics/archive/dev/repro_ci_value_gates.sh VALUE_05
#

set -euo pipefail

GATE_ID="${1:-VALUE_01}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EVIDENCE_DIR="$REPO_ROOT/backend/validation/evidence/local_repro"
mkdir -p "$EVIDENCE_DIR"

LOG_FILE="$EVIDENCE_DIR/${GATE_ID}_$(date +%Y%m%d_%H%M%S).log"

echo "=== CI Reproduction Harness for $GATE_ID ===" | tee "$LOG_FILE"
echo "Repo root: $REPO_ROOT" | tee -a "$LOG_FILE"
echo "Evidence dir: $EVIDENCE_DIR" | tee -a "$LOG_FILE"
echo "Log file: $LOG_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# This harness used to start Postgres via Docker. That content is archived here
# for forensic reference only; CI remains the source of truth.
echo "NOTE: Archived harness placeholder. Prefer reproducing in CI or using a local Postgres instance." | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

echo "Recommended env for running VALUE tests locally:" | tee -a "$LOG_FILE"
echo "  export PYTHONPATH=\"$REPO_ROOT:$REPO_ROOT/backend\"" | tee -a "$LOG_FILE"
echo "  export DATABASE_URL=postgresql://app_user:app_user@127.0.0.1:5432/skeldir_phase" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

echo "This script is archived to comply with Zero Container Doctrine and is not executed." | tee -a "$LOG_FILE"
exit 2


