#!/bin/bash
# scripts/r0/enforce_network_isolation.sh
# R0 EG-R0-6: Enforced Network Isolation for Runtime Evaluation
#
# Purpose: Ensure harness execution cannot reach public internet
# Mechanism: Docker internal network + iptables egress DROP
# Usage: Source this before running evaluation harness
#
# HARD REQUIREMENT: This must be ACTIVE during authoritative runs

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
ARTIFACTS_DIR="$ROOT_DIR/artifacts/runtime_preflight/$(date +%Y-%m-%d)_$(git rev-parse --short HEAD)/NETWORK_ISOLATION_PROOF"

mkdir -p "$ARTIFACTS_DIR"

echo "[R0-EG-R0-6] Enforcing network isolation..."

# ============================================================================
# Step 1: Docker Network Isolation
# ============================================================================

# Create isolated internal network if not exists
docker network ls | grep -q skeldir-r0-isolated || \
  docker network create --internal skeldir-r0-isolated

echo "✓ Docker internal network 'skeldir-r0-isolated' created/verified"
echo "  (containers on this network have NO internet egress by design)"

# ============================================================================
# Step 2: Firewall Rules (iptables - Linux only)
# ============================================================================

if command -v iptables &> /dev/null; then
  echo "[R0-EG-R0-6] Setting iptables rules to DROP docker egress..."

  # Note: This requires sudo. If running in CI, this should be pre-configured.
  # For local dev, this demonstrates the enforcement mechanism.

  # Block all egress from Docker bridge network except internal and loopback
  # (This is a sample; adjust DOCKER_BRIDGE based on your setup)
  DOCKER_BRIDGE="docker0"

  # Allow internal Docker communication
  sudo iptables -I OUTPUT -o $DOCKER_BRIDGE -d 172.17.0.0/16 -j ACCEPT || echo "Warning: iptables rule may already exist"

  # Allow localhost
  sudo iptables -I OUTPUT -o lo -j ACCEPT || echo "Warning: iptables rule may already exist"

  # DROP all other egress from Docker
  sudo iptables -A OUTPUT -o $DOCKER_BRIDGE -j DROP || echo "Warning: iptables rule may already exist"

  # Capture current rules
  sudo iptables -S > "$ARTIFACTS_DIR/iptables_rules.txt"

  echo "✓ iptables egress DROP rules applied"
  echo "  Rules captured to: $ARTIFACTS_DIR/iptables_rules.txt"
else
  echo "⚠ iptables not available (Windows or non-Linux)"
  echo "  Network isolation will rely on Docker internal network only"
  echo "  For CI Ubuntu (authoritative), iptables MUST be configured"
fi

# ============================================================================
# Step 3: Verification Probe (Should Fail)
# ============================================================================

echo "[R0-EG-R0-6] Running egress probe (should FAIL to prove isolation)..."

# Attempt to reach a known public host from a container on the isolated network
# This MUST fail if isolation is working
docker run --rm --network skeldir-r0-isolated alpine:3.18 \
  sh -c "wget --timeout=2 --tries=1 https://www.google.com -O /dev/null" \
  > "$ARTIFACTS_DIR/egress_probe_output.txt" 2>&1 \
  && PROBE_RESULT="FAIL_ISOLATION_BROKEN" \
  || PROBE_RESULT="PASS_EGRESS_BLOCKED"

echo "Probe result: $PROBE_RESULT" | tee "$ARTIFACTS_DIR/probe_result.txt"

if [ "$PROBE_RESULT" = "FAIL_ISOLATION_BROKEN" ]; then
  echo "❌ CRITICAL: Network isolation is NOT enforced!"
  echo "   Container was able to reach public internet"
  echo "   EG-R0-6 FAILS - cannot proceed with authoritative run"
  exit 1
else
  echo "✓ Network isolation verified: Public egress blocked"
fi

# ============================================================================
# Step 4: Docker Compose Network Configuration
# ============================================================================

echo "[R0-EG-R0-6] Ensuring docker-compose uses isolated network..."

# Check if docker-compose files specify the isolated network
# If not, they should be updated or a custom compose override should be used

if [ -f "$ROOT_DIR/docker-compose.component-dev.yml" ]; then
  if ! grep -q "skeldir-r0-isolated" "$ROOT_DIR/docker-compose.component-dev.yml"; then
    echo "⚠ Warning: docker-compose.component-dev.yml does NOT use isolated network"
    echo "  Remediation: Add 'networks: [skeldir-r0-isolated]' to services"
    echo "  Or use: docker-compose --network skeldir-r0-isolated up"
  else
    echo "✓ docker-compose configured for isolated network"
  fi
fi

# ============================================================================
# Summary
# ============================================================================

cat > "$ARTIFACTS_DIR/summary.txt" <<EOF
R0 EG-R0-6 Network Isolation Enforcement Summary
================================================
Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
Candidate SHA: $(git rev-parse HEAD)
Substrate: Local (developer convenience - CI Ubuntu is authoritative)

Enforcement Mechanisms:
1. Docker internal network: skeldir-r0-isolated (ENABLED)
2. iptables egress DROP: $(command -v iptables &> /dev/null && echo "APPLIED" || echo "N/A (non-Linux)")

Verification:
- Egress probe result: $PROBE_RESULT
- Proof artifacts: $ARTIFACTS_DIR

Status: $([ "$PROBE_RESULT" = "PASS_EGRESS_BLOCKED" ] && echo "✓ ISOLATED" || echo "❌ FAIL")

Note: For authoritative CI runs, this script MUST be executed before harness.
EOF

cat "$ARTIFACTS_DIR/summary.txt"

echo ""
echo "[R0-EG-R0-6] Network isolation enforcement complete"
echo "Artifacts saved to: $ARTIFACTS_DIR"
