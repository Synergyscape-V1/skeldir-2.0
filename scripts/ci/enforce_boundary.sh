#!/usr/bin/env bash
set -euo pipefail

# Enforce compute choke points:
# - LLM provider SDK imports must stay in backend/app/llm/provider_boundary.py
# - Bayesian SDK imports must stay in backend/app/workers/bayesian.py

ALLOWED_PROVIDER_PATH="backend/app/llm/provider_boundary.py"
ALLOWED_BAYESIAN_PATH="backend/app/workers/bayesian.py"

if ! command -v rg >/dev/null 2>&1; then
  echo "ERROR: rg (ripgrep) is required for enforce_boundary.sh"
  exit 2
fi

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

violations=0

scan_pattern='^\s*(from|import)\s+'

echo "[enforce_boundary] scanning Python imports..."

while IFS= read -r path; do
  rel="${path#./}"
  if [[ "$rel" == "$ALLOWED_PROVIDER_PATH" || "$rel" == "$ALLOWED_BAYESIAN_PATH" ]]; then
    continue
  fi

  if rg -n "$scan_pattern(aisuite|pymc)([[:space:]\.].*)?$" "$rel" >/tmp/enforce_boundary_hits.txt 2>/dev/null; then
    echo "Boundary violation in $rel:"
    cat /tmp/enforce_boundary_hits.txt
    violations=1
  fi
done < <(git ls-files '*.py')

if [[ "$violations" -ne 0 ]]; then
  echo
  echo "enforce_boundary.sh failed."
  echo "Allowed import locations:"
  echo "  - $ALLOWED_PROVIDER_PATH"
  echo "  - $ALLOWED_BAYESIAN_PATH"
  exit 1
fi

echo "enforce_boundary.sh passed."
