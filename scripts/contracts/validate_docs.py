#!/usr/bin/env python3
"""B0.1 placeholder documentation validator."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "api-contracts" / "dist" / "docs" / "v1"

print(f"[docs] Validating placeholder assets under {DOCS_DIR}")
if not DOCS_DIR.exists():
    print("[docs] ERROR: docs directory missing")
    sys.exit(1)

bundles = sorted(DOCS_DIR.glob("*.bundled.yaml"))
if not bundles:
    print("[docs] WARNING: no bundled yaml files present; placeholder validation passes but indicates missing artifacts")
else:
    print(f"[docs] Found {len(bundles)} bundled contracts:")
    for path in bundles:
        print(f"  - {path.name}")

print("[docs] Placeholder validation complete (B0.1 scope)")
