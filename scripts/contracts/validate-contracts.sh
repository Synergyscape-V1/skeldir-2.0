#!/bin/bash
# Contract Validation Script - Phase E
# Validates OpenAPI contracts for syntax, semantics, and breaking changes
#
# Exit codes:
#   0 - All validations passed
#   1 - Validation failures detected
#   2 - Validation tools unavailable

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "OpenAPI Contract Validation"
echo "Phase E: Contract Authority Restoration"
echo "=========================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONTRACTS_DIR="$REPO_ROOT/api-contracts/dist/openapi/v1"
BASELINES_DIR="$REPO_ROOT/api-contracts/baselines/v1.0.0"

to_native_path() {
    if command -v cygpath >/dev/null 2>&1; then
        cygpath -m "$1"
    else
        printf '%s' "$1"
    fi
}

to_cli_path() {
    local native
    native="$(to_native_path "$1")"
    case "$native" in
        *\ * )
            local win_path="${native//\//\\}"
            local short_path=""
            if [ -n "$PYTHON_CMD" ]; then
                short_path=$($PYTHON_CMD - "$win_path" <<'PY'
import sys
path = sys.argv[1]
try:
    import ctypes
    kernel32 = ctypes.windll.kernel32
    GetShortPathNameW = kernel32.GetShortPathNameW
except AttributeError:
    print(path)
    raise SystemExit(0)

length = GetShortPathNameW(path, None, 0)
if length == 0:
    print(path)
    raise SystemExit(0)

buffer = ctypes.create_unicode_buffer(length)
result = GetShortPathNameW(path, buffer, length)
if result == 0:
    print(path)
else:
    print(buffer.value)
PY
)
            fi
            if [ -n "$short_path" ]; then
                native="$short_path"
            fi
            ;;
    esac
    printf '%s' "$native"
}

echo "Configuration:"
echo "  Contracts: $CONTRACTS_DIR"
echo "  Baselines: $BASELINES_DIR"
echo ""

# Check dependencies
echo "[1/4] Checking validation tools..."
if ! command -v npx &> /dev/null; then
    echo -e "${RED}✗${NC} npx not found (required for openapi-generator-cli)"
    exit 2
fi
echo -e "${GREEN}✓${NC} npx available"

if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo -e "${RED}✗${NC} Python not found"
    exit 2
fi
PYTHON_CMD=$(command -v python3 || command -v python)

LOCAL_OASDIFF_DIR="$REPO_ROOT/tools/oasdiff"
if [ -d "$LOCAL_OASDIFF_DIR" ]; then
    local_oasdiff_cli=$(to_cli_path "$LOCAL_OASDIFF_DIR")
    if command -v cygpath >/dev/null 2>&1; then
        local_oasdiff_posix=$(cygpath -u "$local_oasdiff_cli")
    else
        local_oasdiff_posix="$local_oasdiff_cli"
    fi
    export PATH="$local_oasdiff_posix:$PATH"
fi

echo -e "${GREEN}✓${NC} Python available: $PYTHON_CMD"
echo ""

# Step 1: Bundle contracts
echo "[2/4] Bundling contracts..."
if [ -x "$SCRIPT_DIR/bundle.sh" ]; then
    bash "$SCRIPT_DIR/bundle.sh" || {
        echo -e "${RED}✗${NC} Contract bundling failed"
        exit 1
    }
    echo -e "${GREEN}✓${NC} Contracts bundled successfully"
else
    echo -e "${YELLOW}→${NC} Bundle script not executable, assuming contracts already bundled"
fi
echo ""

# Step 2: Validate each contract
echo "[3/4] Validating OpenAPI specifications..."
VALIDATION_ERRORS=0

for contract in "$CONTRACTS_DIR"/*.bundled.yaml; do
    filename=$(basename "$contract")
    echo -n "  $filename ... "
    native_contract=$(to_cli_path "$contract")
    
    if npx --yes @openapitools/openapi-generator-cli validate -i "$native_contract" > /dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC}"
    else
        echo -e "${RED}FAIL${NC}"
        ((VALIDATION_ERRORS++)) || true
        echo "    Error details:"
        npx --yes @openapitools/openapi-generator-cli validate -i "$native_contract" 2>&1 | sed 's/^/      /'
    fi
done

if [ $VALIDATION_ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓${NC} All contracts passed OpenAPI validation"
else
    echo -e "${RED}✗${NC} $VALIDATION_ERRORS contract(s) failed validation"
fi
echo ""

# Step 3: Breaking change detection (if baselines exist)
echo "[4/4] Checking for breaking changes..."
if [ -d "$BASELINES_DIR" ]; then
    if command -v oasdiff &> /dev/null; then
        BREAKING_CHANGES=0
        
        for baseline in "$BASELINES_DIR"/*.yaml; do
            filename=$(basename "$baseline" .yaml)
            current="$CONTRACTS_DIR/${filename}.bundled.yaml"
            
            if [ -f "$current" ]; then
                echo -n "  $filename ... "
                native_baseline=$(to_cli_path "$baseline")
                native_current=$(to_cli_path "$current")
                
                if oasdiff breaking "$native_baseline" "$native_current" > /dev/null 2>&1; then
                    echo -e "${GREEN}NO BREAKING CHANGES${NC}"
                else
                    echo -e "${YELLOW}BREAKING CHANGES DETECTED${NC}"
                    ((BREAKING_CHANGES++)) || true
                    oasdiff breaking "$native_baseline" "$native_current" | sed 's/^/      /'
                fi
            fi
        done
        
        if [ $BREAKING_CHANGES -eq 0 ]; then
            echo -e "${GREEN}✓${NC} No breaking changes detected"
        else
            echo -e "${YELLOW}→${NC} $BREAKING_CHANGES contract(s) have breaking changes"
            echo "    (Breaking changes allowed in B0.1 development phase)"
        fi
    else
        echo -e "${YELLOW}→${NC} oasdiff not installed, skipping breaking change detection"
        echo "    Install: go install github.com/tufin/oasdiff@latest"
    fi
else
    echo -e "${YELLOW}→${NC} No baselines found at $BASELINES_DIR"
    echo "    Skipping breaking change detection"
fi
echo ""

# Summary
echo "=========================================="
if [ $VALIDATION_ERRORS -eq 0 ]; then
    echo -e "${GREEN}Validation Complete: ALL PASS${NC}"
    echo "=========================================="
    exit 0
else
    echo -e "${RED}Validation Complete: FAILURES DETECTED${NC}"
    echo "=========================================="
    exit 1
fi
