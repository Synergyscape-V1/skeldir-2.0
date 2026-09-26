#!/usr/bin/env python3
"""Ensure the authenticated-ingress principal exists (role only).

B2.6-P2 Corrective XII: lanes that migrate without the governed
provisioner (local-dev compose, template lanes) still carry the strict
single-regime law, so the ingress role must exist for the lane to be
serviceable. This helper creates ONLY the login role (idempotent,
no grants, no ownership changes): all authority flows from the
migrations themselves, which install the exact governed grants when
the role exists and strict law with a dead auth plane when it does
not. Full topology provisioning remains
``prepare_migration_authority_boundary.py``.

Usage:
    python scripts/database/ensure_ingress_principal.py
Environment:
    MIGRATION_DATABASE_URL (a superuser/admin DSN that may CREATE ROLE)
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    dsn = os.environ.get("MIGRATION_DATABASE_URL", "").strip()
    if not dsn:
        print("ensure_ingress_principal: MIGRATION_DATABASE_URL is required")
        return 2
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        print(f"ensure_ingress_principal: no driver: {exc}")
        return 2
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress'"
            )
            if cur.fetchone() is None:
                cur.execute(
                    "CREATE ROLE app_ingress WITH LOGIN PASSWORD 'app_ingress'"
                )
                print("ensure_ingress_principal: created app_ingress")
            else:
                print("ensure_ingress_principal: app_ingress present")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
