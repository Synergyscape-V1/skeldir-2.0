#!/usr/bin/env bash
# B0.1 documentation build placeholder
# Full documentation generation occurs in B0.2 governance phase.

set -euo pipefail

log() {
    printf '[docs] %s\n' "$1"
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST_DIR="$ROOT_DIR/api-contracts/dist"
BUNDLE_DIR="$DIST_DIR/openapi/v1"
DOCS_DIR="$DIST_DIR/docs/v1"

log "B0.1 stub: preparing placeholder documentation"
mkdir -p "$DOCS_DIR"

if ls "$BUNDLE_DIR"/*.bundled.yaml >/dev/null 2>&1; then
    log "Copying bundled contracts into docs directory"
    cp "$BUNDLE_DIR"/*.bundled.yaml "$DOCS_DIR"/
    log "✓ Placeholder docs prepared"
else
    log "⚠️ No bundled contracts found under $BUNDLE_DIR"
fi

log "Full documentation generation deferred to B0.2"
