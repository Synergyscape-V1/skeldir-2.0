#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import jwt
import psycopg2


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_endpoint(base_url: str, path: str, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    last_exc: Exception | None = None
    while time.time() < deadline:
        try:
            _ = httpx.get(f"{base_url}{path}", timeout=1.0)
            return
        except Exception as exc:  # pragma: no cover
            last_exc = exc
            time.sleep(0.25)
    raise RuntimeError(f"endpoint never became reachable: {path} last_exc={last_exc}")


def _run_readiness_fail_closed() -> dict[str, Any]:
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "backend")
    env["SKELDIR_REQUIRE_AUTH_SECRETS"] = "1"
    env["DATABASE_URL"] = env.get("DATABASE_URL", "postgresql+asyncpg://app_user:app_user@127.0.0.1:5432/skeldir_b11_p6")
    env["MIGRATION_DATABASE_URL"] = env.get("MIGRATION_DATABASE_URL", "postgresql://migration_owner:migration_owner@127.0.0.1:5432/skeldir_b11_p6")
    env["PLATFORM_TOKEN_ENCRYPTION_KEY"] = ""
    env["AUTH_JWT_SECRET"] = ""
    env["AUTH_JWT_JWKS_URL"] = ""

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_endpoint(base_url, "/health/ready", timeout_s=30.0)
        r1 = httpx.get(f"{base_url}/health/ready", timeout=5.0)
        r2 = httpx.get(f"{base_url}/api/health", timeout=5.0)
        r3 = httpx.get(f"{base_url}/api/health/ready", timeout=5.0)
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            proc.kill()
            proc.wait(timeout=10)

    if not (r1.status_code == 503 and r2.status_code == 503 and r3.status_code == 503):
        raise RuntimeError(
            f"readiness fail-closed violated: /health/ready={r1.status_code} /api/health={r2.status_code} /api/health/ready={r3.status_code}"
        )
    missing = r1.json().get("missing_required_secrets", [])
    return {
        "status": "pass",
        "health_ready_status": r1.status_code,
        "api_health_status": r2.status_code,
        "api_health_ready_status": r3.status_code,
        "missing_required_secrets": missing,
        "drill_mode": "live_uvicorn_runtime_no_monkeypatch",
    }


def _reload_crypto_modules() -> tuple[Any, Any]:
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    import app.core.config as config_module
    import app.core.secrets as secrets_module
    import app.security.auth as auth_module

    importlib.reload(config_module)
    secrets_reloaded = importlib.reload(secrets_module)
    auth_reloaded = importlib.reload(auth_module)
    return secrets_reloaded, auth_reloaded


def _sync_dsn(raw: str) -> str:
    return raw.replace("postgresql+asyncpg://", "postgresql://", 1)


def _run_rotation_jwt_and_envelope() -> dict[str, Any]:
    os.environ["SKELDIR_JWT_KEY_RING_MAX_STALENESS_SECONDS"] = "1"
    os.environ["SKELDIR_JWT_UNKNOWN_KID_REFRESH_DEBOUNCE_SECONDS"] = "1"
    os.environ["AUTH_JWT_ALGORITHM"] = "HS256"
    os.environ["AUTH_JWT_ISSUER"] = "https://issuer.skeldir.test"
    os.environ["AUTH_JWT_AUDIENCE"] = "skeldir-api"

    old_ring = {"current_kid": "kid-old", "keys": {"kid-old": "secret-old"}}
    overlap_ring = {
        "current_kid": "kid-new",
        "keys": {"kid-old": "secret-old", "kid-new": "secret-new"},
        "previous_kids": ["kid-old"],
    }
    os.environ["AUTH_JWT_SECRET"] = json.dumps(old_ring)

    secrets_module, auth_module = _reload_crypto_modules()
    secrets_module.reset_crypto_secret_caches_for_testing()

    old_token = auth_module.mint_internal_jwt(tenant_id=uuid4(), user_id=uuid4(), expires_in_seconds=180)
    old_header = jwt.get_unverified_header(old_token)
    old_kid = old_header.get("kid")

    os.environ["AUTH_JWT_SECRET"] = json.dumps(overlap_ring)
    time.sleep(1.1)
    secrets_module, auth_module = _reload_crypto_modules()
    secrets_module.reset_crypto_secret_caches_for_testing()
    new_token = auth_module.mint_internal_jwt(tenant_id=uuid4(), user_id=uuid4(), expires_in_seconds=180)
    new_header = jwt.get_unverified_header(new_token)
    new_kid = new_header.get("kid")
    _decoded_old = auth_module._decode_token(old_token)

    platform_ring = {
        "current_key_id": "platform-new",
        "keys": {"platform-old": "old-material", "platform-new": "new-material"},
        "previous_key_ids": ["platform-old"],
    }
    os.environ["PLATFORM_TOKEN_ENCRYPTION_KEY"] = json.dumps(platform_ring)
    secrets_module, _ = _reload_crypto_modules()
    secrets_module.reset_crypto_secret_caches_for_testing()

    from app.core.secrets import get_database_url, get_migration_database_url  # noqa: WPS433

    admin_dsn = _sync_dsn(get_migration_database_url() or get_database_url())
    if not admin_dsn:
        raise RuntimeError("rotation drill requires B11_P6_ADMIN_DATABASE_URL or MIGRATION_DATABASE_URL or DATABASE_URL")

    with psycopg2.connect(admin_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pgp_sym_encrypt(%s, %s)", ("oauth-token-p6", "old-material"))
            ciphertext = cur.fetchone()[0]
            resolved_old_key = secrets_module.resolve_platform_encryption_key_by_id("platform-old")
            cur.execute("SELECT pgp_sym_decrypt(%s::bytea, %s)", (ciphertext, resolved_old_key))
            decrypted = cur.fetchone()[0]

    if old_kid != "kid-old":
        raise RuntimeError(f"expected old kid-old, got {old_kid}")
    if new_kid != "kid-new":
        raise RuntimeError(f"expected new kid-new, got {new_kid}")
    if decrypted != "oauth-token-p6":
        raise RuntimeError("envelope rotation decrypt compatibility failed")

    return {
        "status": "pass",
        "old_jwt_kid": old_kid,
        "new_jwt_kid": new_kid,
        "old_jwt_valid_during_overlap": True,
        "oauth_decrypt_across_envelope_rotation": True,
        "drill_mode": "live_modules_live_postgres_no_monkeypatch",
    }


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}={v}" for k, v in payload.items()]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="B11-P6 live E2E runtime drills")
    parser.add_argument("--readiness-out", required=True)
    parser.add_argument("--rotation-out", required=True)
    args = parser.parse_args()

    readiness = _run_readiness_fail_closed()
    rotation = _run_rotation_jwt_and_envelope()

    _write((REPO_ROOT / args.readiness_out).resolve(), readiness)
    _write((REPO_ROOT / args.rotation_out).resolve(), rotation)
    print((REPO_ROOT / args.readiness_out).resolve().as_posix())
    print((REPO_ROOT / args.rotation_out).resolve().as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
