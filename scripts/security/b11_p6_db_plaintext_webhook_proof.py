#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg2


REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_dsn() -> str:
    return (
        os.getenv("B11_P6_ADMIN_DATABASE_URL")
        or os.getenv("MIGRATION_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or ""
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="B11-P6 DB plaintext webhook proof")
    parser.add_argument(
        "--output",
        default="docs/forensics/evidence/b11_p6/db_no_plaintext_webhook_secrets.txt",
    )
    args = parser.parse_args()

    dsn = _resolve_dsn()
    if not dsn:
        raise RuntimeError("B11_P6_ADMIN_DATABASE_URL or MIGRATION_DATABASE_URL or DATABASE_URL is required")

    query_plaintext = """
        SELECT table_schema, table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'tenants'
          AND column_name ~ '^(shopify|stripe|paypal|woocommerce)_webhook_secret$'
        ORDER BY column_name
    """
    query_encrypted = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'tenants'
          AND column_name ~ '^(shopify|stripe|paypal|woocommerce)_webhook_secret_(ciphertext|key_id)$'
        ORDER BY column_name
    """

    with psycopg2.connect(dsn.replace("postgresql+asyncpg://", "postgresql://", 1)) as conn:
        with conn.cursor() as cur:
            cur.execute(query_plaintext)
            plaintext_rows = cur.fetchall()
            cur.execute(query_encrypted)
            encrypted_rows = cur.fetchall()

    plaintext_count = len(plaintext_rows)
    encrypted_count = len(encrypted_rows)
    status = "PASS" if plaintext_count == 0 and encrypted_count >= 8 else "FAIL"

    lines = [
        "b11_p6_db_plaintext_webhook_proof",
        f"status={status}",
        f"plaintext_column_count={plaintext_count}",
        f"encrypted_column_count={encrypted_count}",
        "plaintext_query=" + " ".join(query_plaintext.split()),
        "encrypted_query=" + " ".join(query_encrypted.split()),
    ]
    if plaintext_rows:
        for row in plaintext_rows:
            lines.append(f"plaintext_column={row[0]}.{row[1]}.{row[2]}")
    if encrypted_rows:
        for row in encrypted_rows:
            lines.append(f"encrypted_column={row[0]}")

    out_path = (REPO_ROOT / args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(out_path.as_posix())
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
