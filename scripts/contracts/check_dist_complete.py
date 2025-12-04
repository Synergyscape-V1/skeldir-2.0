#!/usr/bin/env python3
"""
Validates that all expected bundled contract artifacts exist.
Exit code 0 = all bundles present
Exit code 1 = missing bundles
"""

import argparse
import json
import sys
from pathlib import Path

EXPECTED_BUNDLES = [
    "auth.bundled.yaml",
    "attribution.bundled.yaml",
    "reconciliation.bundled.yaml",
    "export.bundled.yaml",
    "health.bundled.yaml",
    "webhooks.shopify.bundled.yaml",
    "webhooks.woocommerce.bundled.yaml",
    "webhooks.stripe.bundled.yaml",
    "webhooks.paypal.bundled.yaml",
    "llm-investigations.bundled.yaml",
    "llm-budget.bundled.yaml",
    "llm-explanations.bundled.yaml",
]

def main():
    parser = argparse.ArgumentParser(description="Check bundled contract completeness")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    dist_dir = Path("api-contracts/dist/openapi/v1")

    if not dist_dir.exists():
        if args.json:
            print(json.dumps({"error": "dist directory does not exist", "path": str(dist_dir)}))
        else:
            print(f"ERROR: Distribution directory does not exist: {dist_dir}")
        sys.exit(1)

    missing = []
    present = []

    for bundle in EXPECTED_BUNDLES:
        bundle_path = dist_dir / bundle
        if bundle_path.exists():
            present.append(bundle)
        else:
            missing.append(bundle)

    if args.json:
        result = {
            "total_expected": len(EXPECTED_BUNDLES),
            "present": present,
            "missing": missing,
            "complete": len(missing) == 0
        }
        print(json.dumps(result, indent=2))
    else:
        print(f"Bundle completeness check:")
        print(f"  Expected: {len(EXPECTED_BUNDLES)}")
        print(f"  Present:  {len(present)}")
        print(f"  Missing:  {len(missing)}")

        if missing:
            print("\nMissing bundles:")
            for m in missing:
                print(f"  - {m}")
        else:
            print("\n✓ All bundles present")

    sys.exit(0 if len(missing) == 0 else 1)

if __name__ == "__main__":
    main()
