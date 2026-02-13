#!/usr/bin/env bash
set -euo pipefail

# Enforce compute choke points:
# - LLM provider SDK imports must stay in backend/app/llm/provider_boundary.py
# - Bayesian SDK imports must stay in backend/app/workers/bayesian.py

ALLOWED_PROVIDER_PATH="backend/app/llm/provider_boundary.py"
ALLOWED_BAYESIAN_PATH="backend/app/workers/bayesian.py"

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

violations=0

scan_pattern='^[[:space:]]*(from|import)[[:space:]]+'
hits_file="$(mktemp)"
trap 'rm -f "$hits_file"' EXIT

search_imports() {
  local file="$1"
  if command -v rg >/dev/null 2>&1; then
    rg -n "$scan_pattern(aisuite|pymc)([[:space:]\.].*)?$" "$file" >"$hits_file" 2>/dev/null
  else
    grep -nE "$scan_pattern(aisuite|pymc)([[:space:]\.].*)?$" "$file" >"$hits_file" 2>/dev/null
  fi
}

echo "[enforce_boundary] scanning Python imports..."

while IFS= read -r path; do
  rel="${path#./}"
  if [[ "$rel" == "$ALLOWED_PROVIDER_PATH" || "$rel" == "$ALLOWED_BAYESIAN_PATH" ]]; then
    continue
  fi

  if search_imports "$rel"; then
    echo "Boundary violation in $rel:"
    cat "$hits_file"
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
