#!/usr/bin/env python3
"""
Execute EXPLAIN ANALYZE on canonical queries and capture the output.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from scripts.security.db_secret_access import resolve_runtime_database_url


QUERIES = [
    "EXPLAIN ANALYZE SELECT id, name FROM tenants LIMIT 10;",
    "EXPLAIN ANALYZE SELECT * FROM attribution_events ORDER BY occurred_at DESC LIMIT 10;",
    "EXPLAIN ANALYZE SELECT * FROM attribution_allocations ORDER BY created_at DESC LIMIT 10;",
    "EXPLAIN ANALYZE SELECT * FROM revenue_ledger ORDER BY verification_timestamp DESC LIMIT 10;",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run query performance checks.")
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write the JSON report.",
    )
    return parser.parse_args()


def run_query(database_url: str, query: str) -> dict:
    process = subprocess.run(
        ["psql", database_url, "-c", query],
        capture_output=True,
        text=True,
    )
    return {
        "query": query,
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def main() -> int:
    args = parse_args()
    database_url = resolve_runtime_database_url()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    results = [run_query(database_url, query) for query in QUERIES]
    status = "success" if all(r["returncode"] == 0 for r in results) else "failure"

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump({"status": status, "results": results}, fh, indent=2)

    if status != "success":
        print("Query performance validation failed.")
        return 1

    print("Query performance validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
