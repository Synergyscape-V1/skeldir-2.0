#!/bin/bash
# scripts/r0/normalize_pg_dump.sh
# Normalizes pg_dump output to remove volatile fields for deterministic fingerprinting
#
# Usage: normalize_pg_dump.sh <input_schema.sql> <output_normalized.sql>
#
# Removes:
# - Dump header comments (PostgreSQL version, pg_dump version, timestamp)
# - Session-specific tokens (\restrict, \unrestrict)
# - SET statements with volatile values
# - COMMENT lines (may contain timestamps)

set -euo pipefail

INPUT_FILE="${1:-}"
OUTPUT_FILE="${2:-}"

if [ -z "$INPUT_FILE" ] || [ -z "$OUTPUT_FILE" ]; then
  echo "Usage: $0 <input_schema.sql> <output_normalized.sql>"
  exit 1
fi

if [ ! -f "$INPUT_FILE" ]; then
  echo "Error: Input file not found: $INPUT_FILE"
  exit 1
fi

# Normalize pg_dump output by removing volatile fields
grep -v '^--' "$INPUT_FILE" | \
  grep -v '^\restrict' | \
  grep -v '^\\unrestrict' | \
  grep -v '^SET ' | \
  grep -v '^SELECT pg_catalog.set_config' | \
  grep -v '^COMMENT ON EXTENSION' | \
  sed '/^$/N;/^\n$/D' \
  > "$OUTPUT_FILE"

echo "Normalized schema written to: $OUTPUT_FILE"
