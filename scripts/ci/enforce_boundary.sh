#!/usr/bin/env bash
set -euo pipefail

# Enforce compute choke points (runtime code only):
# - LLM provider + transport access may only exist at the provider boundary.
# - Bayesian model SDK access may only exist at designated Bayesian worker/task boundary.

ALLOWED_LLM_BOUNDARY_PATH="backend/app/llm/provider_boundary.py"
ALLOWED_BAYESIAN_PATHS=(
  "backend/app/workers/bayesian.py"
  "backend/app/tasks/bayesian.py"
)

# Provider SDKs which must remain at the boundary.
PROVIDER_SDK_MODULES=(
  "aisuite"
  "openai"
  "anthropic"
  "mistralai"
  "google.generativeai"
  "vertexai"
)

# Bayesian SDKs which must remain at the Bayesian boundary path(s).
BAYESIAN_SDK_MODULES=(
  "pymc"
)

# Raw HTTP transports that can bypass the boundary if used directly.
TRANSPORT_MODULES=(
  "httpx"
  "requests"
  "aiohttp"
  "urllib3"
)

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

violations=0

declare -a SCAN_FILES=()
while IFS= read -r file_path; do
  SCAN_FILES+=("${file_path}")
done < <(find backend/app -type f -name '*.py' | sort)

if [[ "${#SCAN_FILES[@]}" -eq 0 ]]; then
  echo "enforce_boundary.sh failed: no Python files found under backend/app"
  exit 1
fi

to_regex_group() {
  local IFS='|'
  echo "$*"
}

PROVIDER_GROUP="$(to_regex_group "${PROVIDER_SDK_MODULES[@]}")"
BAYESIAN_GROUP="$(to_regex_group "${BAYESIAN_SDK_MODULES[@]}")"
TRANSPORT_GROUP="$(to_regex_group "${TRANSPORT_MODULES[@]}")"
IMPORT_PATTERN='^[[:space:]]*(from|import)[[:space:]]+'

is_allowed_path() {
  local rel="$1"
  local expected="$2"
  [[ "$rel" == "$expected" ]]
}

is_allowed_bayesian_path() {
  local rel="$1"
  for allowed in "${ALLOWED_BAYESIAN_PATHS[@]}"; do
    if [[ "$rel" == "$allowed" ]]; then
      return 0
    fi
  done
  return 1
}

emit_violation() {
  local rel="$1"
  local reason="$2"
  local matches="$3"
  echo "Boundary violation in ${rel}: ${reason}"
  printf '%s\n' "${matches}"
  violations=1
}

scan_matches() {
  local pattern="$1"
  local path="$2"
  if command -v rg >/dev/null 2>&1; then
    rg -n -e "${pattern}" "${path}" || true
  else
    grep -nE "${pattern}" "${path}" || true
  fi
}

echo "[enforce_boundary] scanning runtime Python code under backend/app ..."

for path in "${SCAN_FILES[@]}"; do
  rel="${path#./}"

  # Provider SDK imports are only allowed in the LLM boundary module.
  provider_import_hits="$(scan_matches "${IMPORT_PATTERN}(${PROVIDER_GROUP})([[:space:]\\.]|$)" "${rel}")"
  if [[ -n "${provider_import_hits}" ]] && ! is_allowed_path "${rel}" "${ALLOWED_LLM_BOUNDARY_PATH}"; then
    emit_violation "${rel}" "provider SDK import outside ${ALLOWED_LLM_BOUNDARY_PATH}" "${provider_import_hits}"
  fi

  # Bayesian SDK imports are only allowed in designated Bayesian boundary modules.
  bayesian_import_hits="$(scan_matches "${IMPORT_PATTERN}(${BAYESIAN_GROUP})([[:space:]\\.]|$)" "${rel}")"
  if [[ -n "${bayesian_import_hits}" ]] && ! is_allowed_bayesian_path "${rel}"; then
    emit_violation "${rel}" "bayesian SDK import outside designated Bayesian boundary paths" "${bayesian_import_hits}"
  fi

  # Raw HTTP transport imports are only allowed in the LLM boundary module.
  transport_import_hits="$(scan_matches "${IMPORT_PATTERN}(${TRANSPORT_GROUP})([[:space:]\\.]|$)" "${rel}")"
  if [[ -n "${transport_import_hits}" ]] && ! is_allowed_path "${rel}" "${ALLOWED_LLM_BOUNDARY_PATH}"; then
    emit_violation "${rel}" "HTTP transport import outside ${ALLOWED_LLM_BOUNDARY_PATH}" "${transport_import_hits}"
  fi

  # Dynamic import bypass patterns for provider SDK modules.
  dynamic_provider_hits="$(scan_matches "importlib\\.import_module\\([[:space:]]*['\"](${PROVIDER_GROUP})['\"][[:space:]]*\\)|__import__\\([[:space:]]*['\"](${PROVIDER_GROUP})['\"][[:space:]]*\\)" "${rel}")"
  if [[ -n "${dynamic_provider_hits}" ]] && ! is_allowed_path "${rel}" "${ALLOWED_LLM_BOUNDARY_PATH}"; then
    emit_violation "${rel}" "dynamic provider import outside ${ALLOWED_LLM_BOUNDARY_PATH}" "${dynamic_provider_hits}"
  fi

  # Dynamic import bypass patterns for Bayesian SDK modules.
  dynamic_bayesian_hits="$(scan_matches "importlib\\.import_module\\([[:space:]]*['\"](${BAYESIAN_GROUP})['\"][[:space:]]*\\)|__import__\\([[:space:]]*['\"](${BAYESIAN_GROUP})['\"][[:space:]]*\\)" "${rel}")"
  if [[ -n "${dynamic_bayesian_hits}" ]] && ! is_allowed_bayesian_path "${rel}"; then
    emit_violation "${rel}" "dynamic bayesian import outside designated Bayesian boundary paths" "${dynamic_bayesian_hits}"
  fi
done

if [[ "${violations}" -ne 0 ]]; then
  echo
  echo "enforce_boundary.sh failed."
  echo "Allowed LLM boundary path:"
  echo "  - ${ALLOWED_LLM_BOUNDARY_PATH}"
  echo "Allowed Bayesian boundary paths:"
  for allowed in "${ALLOWED_BAYESIAN_PATHS[@]}"; do
    echo "  - ${allowed}"
  done
  echo "Provider SDK modules enforced: ${PROVIDER_SDK_MODULES[*]}"
  echo "Bayesian SDK modules enforced: ${BAYESIAN_SDK_MODULES[*]}"
  echo "Transport modules enforced: ${TRANSPORT_MODULES[*]}"
  exit 1
fi

echo "enforce_boundary.sh passed."
echo "Provider SDK modules enforced: ${PROVIDER_SDK_MODULES[*]}"
echo "Bayesian SDK modules enforced: ${BAYESIAN_SDK_MODULES[*]}"
echo "Transport modules enforced: ${TRANSPORT_MODULES[*]}"
echo "Allowed LLM boundary path: ${ALLOWED_LLM_BOUNDARY_PATH}"
echo "Allowed Bayesian boundary paths: ${ALLOWED_BAYESIAN_PATHS[*]}"
