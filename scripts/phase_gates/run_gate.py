#!/usr/bin/env python3
"""
Phase gate dispatcher.

Dispatches to dedicated gate runners once they are implemented.
"""

from __future__ import annotations

import argparse
import sys
from importlib import import_module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute a phase gate.")
    parser.add_argument("phase", help="Phase identifier (e.g., B0.1)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phase = args.phase.upper()

    handlers = {
        "B0.1": "scripts.phase_gates.b0_1_gate",
        "B0.2": "scripts.phase_gates.b0_2_gate",
        "B0.3": "scripts.phase_gates.b0_3_gate",
    }

    if phase not in handlers:
        print(f"Unknown phase '{phase}'.", file=sys.stderr)
        return 2

    module = import_module(handlers[phase])
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
