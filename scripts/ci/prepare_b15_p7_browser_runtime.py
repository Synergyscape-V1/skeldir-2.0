#!/usr/bin/env python3
"""Prepare auth/runtime prerequisites for B1.5-P7 browser closure proofs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID

import jwt
import psycopg2
from psycopg2.extras import RealDictCursor


DEFAULT_TENANT_ID = "11111111-1111-4111-8111-111111111111"
DEFAULT_USER_ID = "22222222-2222-4222-8222-222222222222"
DEFAULT_JWT_KID = "b15-p7-browser-ci"


def _sync_dsn(raw_dsn: str) -> str:
    if raw_dsn.startswith("postgresql+asyncpg://"):
        return raw_dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    return raw_dsn


def _read_key(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _ensure_tenant_exists(*, dsn: str, tenant_id: UUID) -> None:
    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'tenants'
                """
            )
            columns = {str(row["column_name"]) for row in cursor.fetchall()}

            insert_cols = ["id", "name"]
            params: dict[str, Any] = {
                "id": str(tenant_id),
                "name": f"B15-P7 Browser Tenant {str(tenant_id)[:8]}",
                "api_key_hash": f"b15_p7_{str(tenant_id)[:12]}",
                "notification_email": f"b15_p7_{str(tenant_id)[:8]}@skeldir.local",
            }
            if "api_key_hash" in columns:
                insert_cols.append("api_key_hash")
            if "notification_email" in columns:
                insert_cols.append("notification_email")

            placeholders = ", ".join(f"%({col})s" for col in insert_cols)
            cursor.execute(
                f"""
                INSERT INTO tenants ({", ".join(insert_cols)})
                VALUES ({placeholders})
                ON CONFLICT (id) DO NOTHING
                """,
                params,
            )
        conn.commit()


def _build_key_ring(*, kid: str, key_material: str) -> str:
    return json.dumps(
        {
            "current_kid": kid,
            "keys": {kid: key_material},
            "previous_kids": [],
        }
    )


def _mint_browser_token(
    *,
    private_key: str,
    kid: str,
    tenant_id: UUID,
    user_id: UUID,
    issuer: str,
    audience: str,
) -> str:
    claims: dict[str, Any] = {
        "tenant_id": str(tenant_id),
        "sub": str(user_id),
        "user_id": str(user_id),
        "jti": "33333333-3333-4333-8333-333333333333",
        "iat": 1_774_764_800,  # 2026-03-29T00:00:00Z
        "exp": 2_054_764_800,  # 2035-02-03T00:00:00Z
        "role": "viewer",
        "roles": ["viewer"],
        "scopes": ["viewer"],
        "iss": issuer,
        "aud": audience,
    }
    return jwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )


def _write_env(path: Path, values: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare B1.5-P7 browser proof runtime auth/tenant prerequisites.",
    )
    parser.add_argument("--private-key-path", required=True)
    parser.add_argument("--public-key-path", required=True)
    parser.add_argument("--emit-github-env", required=True)
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--jwt-kid", default=DEFAULT_JWT_KID)
    parser.add_argument("--jwt-issuer", default="https://issuer.skeldir.test")
    parser.add_argument("--jwt-audience", default="skeldir-api")
    parser.add_argument("--investigation-hold-seconds", default="15")
    args = parser.parse_args()

    tenant_id = UUID(args.tenant_id)
    user_id = UUID(args.user_id)
    private_key = _read_key(Path(args.private_key_path))
    public_key = _read_key(Path(args.public_key_path))

    migration_dsn = os.getenv("MIGRATION_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not migration_dsn:
        raise RuntimeError("MIGRATION_DATABASE_URL or DATABASE_URL must be set.")
    sync_dsn = _sync_dsn(migration_dsn)

    _ensure_tenant_exists(dsn=sync_dsn, tenant_id=tenant_id)

    private_ring = _build_key_ring(kid=args.jwt_kid, key_material=private_key)
    public_ring = _build_key_ring(kid=args.jwt_kid, key_material=public_key)
    bearer_token = _mint_browser_token(
        private_key=private_key,
        kid=args.jwt_kid,
        tenant_id=tenant_id,
        user_id=user_id,
        issuer=args.jwt_issuer,
        audience=args.jwt_audience,
    )

    env_payload = {
        "AUTH_JWT_SECRET": private_ring,
        "AUTH_JWT_PUBLIC_KEY_RING": public_ring,
        "AUTH_JWT_ALGORITHM": "RS256",
        "AUTH_JWT_ISSUER": args.jwt_issuer,
        "AUTH_JWT_AUDIENCE": args.jwt_audience,
        "B15_P7_E2E_BEARER_TOKEN": bearer_token,
        "B15_P7_E2E_TENANT_ID": str(tenant_id),
        "B15_P7_E2E_USER_ID": str(user_id),
        "B15_P7_FRONTEND_BASE_URL": "http://127.0.0.1:5173",
        "B15_P7_INVESTIGATIONS_BASE_URL": "http://127.0.0.1:4024",
        "B15_INVESTIGATION_MIN_HOLD_SECONDS": str(args.investigation_hold_seconds),
    }
    _write_env(Path(args.emit_github_env), env_payload)

    print("b15_p7_browser_runtime_prepared")
    print(f"tenant_id={tenant_id}")
    print(f"user_id={user_id}")
    print(f"jwt_kid={args.jwt_kid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
