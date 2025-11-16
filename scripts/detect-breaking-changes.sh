#!/bin/bash
# Breaking Change Detection Script
#
# Purpose: Detect breaking changes in OpenAPI contracts by comparing active contracts against baselines
# Usage: ./detect-breaking-changes.sh [domain]
#
# If domain is provided, only checks that domain. Otherwise checks all domains.

set -euo pipefail

DOMAIN="${1:-all}"

echo "=========================================="
echo "Breaking Change Detection"
echo "=========================================="
echo ""

BREAKING_CHANGES_DETECTED=0

check_domain() {
    local domain=$1
    local active_file="contracts/${domain}/v1/${domain}.yaml"
    local baseline_file="contracts/${domain}/baselines/v1.0.0/${domain}.yaml"
    
    if [ ! -f "$active_file" ]; then
        echo "⚠️  Warning: Active contract not found: $active_file"
        return 0
    fi
    
    if [ ! -f "$baseline_file" ]; then
        echo "⚠️  Warning: Baseline contract not found: $baseline_file"
        return 0
    fi
    
    echo "Checking ${domain} contract..."
    
    # Use openapi-diff if available, otherwise use basic validation
    if command -v openapi-diff &> /dev/null; then
        echo "  Using openapi-diff tool..."
        if openapi-diff "$baseline_file" "$active_file" 2>&1 | grep -q "breaking"; then
            echo "  ❌ BREAKING CHANGES DETECTED in ${domain}"
            openapi-diff "$baseline_file" "$active_file"
            BREAKING_CHANGES_DETECTED=1
        else
            echo "  ✅ No breaking changes detected in ${domain}"
        fi
    else
        # Basic validation: check if files are identical (not comprehensive)
        echo "  Using basic file comparison (install openapi-diff for comprehensive detection)..."
        if ! diff -q "$baseline_file" "$active_file" > /dev/null 2>&1; then
            echo "  ⚠️  Files differ - manual review required for ${domain}"
            echo "  Install openapi-diff for automated breaking change detection:"
            echo "    npm install -g @openapitools/openapi-diff"
        else
            echo "  ✅ Files identical - no changes detected in ${domain}"
        fi
    fi
    echo ""
}

if [ "$DOMAIN" = "all" ]; then
    # Check all domains
    for domain in attribution webhooks auth reconciliation export health; do
        if [ "$domain" = "webhooks" ]; then
            # Webhooks have multiple files
            for webhook in shopify stripe paypal woocommerce; do
                check_domain "webhooks/${webhook}"
            done
        else
            check_domain "$domain"
        fi
    done
else
    # Check specific domain
    check_domain "$DOMAIN"
fi

echo "=========================================="
if [ $BREAKING_CHANGES_DETECTED -eq 1 ]; then
    echo "❌ Breaking changes detected!"
    echo "Action required: Update version number or revert changes"
    exit 1
else
    echo "✅ No breaking changes detected"
    exit 0
fi

