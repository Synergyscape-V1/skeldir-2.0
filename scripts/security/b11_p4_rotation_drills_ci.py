#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import os
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sys
from typing import Any

import psycopg2


def _ensure_backend_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    backend_path = repo_root / "backend"
    backend_str = str(backend_path)
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)


def _mask(value: str) -> None:
    print(f"::add-mask::{value}")


def _reload_secret_modules():
    _ensure_backend_on_path()
    import app.core.config as config_module
    import app.core.secrets as secrets_module

    importlib.reload(config_module)
    secrets_reloaded = importlib.reload(secrets_module)
    return secrets_reloaded


def _ensure_sync_dsn(raw: str) -> str:
    return raw.replace("postgresql+asyncpg://", "postgresql://", 1)


def _connect(dsn: str):
    return psycopg2.connect(_ensure_sync_dsn(dsn))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _run_db_rotation_drill(admin_dsn: str) -> dict[str, Any]:
    db_name = "skeldir_p4_rotation_ci"
    old_user = "p4_old_user"
    new_user = "p4_new_user"
    old_pass = secrets.token_urlsafe(18)
    new_pass = secrets.token_urlsafe(18)
    _mask(old_pass)
    _mask(new_pass)

    old_dsn = f"postgresql://{old_user}:{old_pass}@127.0.0.1:5432/{db_name}"
    new_dsn = f"postgresql://{new_user}:{new_pass}@127.0.0.1:5432/{db_name}"

    admin_conn = _connect(admin_dsn)
    admin_conn.autocommit = True
    try:
        with admin_conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {db_name}")
            cur.execute(f"DROP ROLE IF EXISTS {old_user}")
            cur.execute(f"DROP ROLE IF EXISTS {new_user}")
            cur.execute(f"CREATE ROLE {old_user} LOGIN PASSWORD %s", (old_pass,))
            cur.execute(f"CREATE DATABASE {db_name} OWNER {old_user}")
            cur.execute(f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {old_user}")
    finally:
        admin_conn.close()

    os.environ["DATABASE_URL"] = old_dsn
    secrets_module = _reload_secret_modules()
    resolved_old = secrets_module.get_database_url()
    with _connect(resolved_old) as old_conn:
        with old_conn.cursor() as cur:
            cur.execute("SELECT current_user")
            old_current_user = str(cur.fetchone()[0])

    admin_conn = _connect(admin_dsn)
    admin_conn.autocommit = True
    try:
        with admin_conn.cursor() as cur:
            cur.execute(f"CREATE ROLE {new_user} LOGIN PASSWORD %s", (new_pass,))
            cur.execute(f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {new_user}")
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND usename = %s",
                (db_name, old_user),
            )
            cur.execute(f"REVOKE ALL PRIVILEGES ON DATABASE {db_name} FROM {old_user}")
            cur.execute(f"ALTER ROLE {old_user} NOLOGIN")
    finally:
        admin_conn.close()

    old_failed = False
    old_error = ""
    try:
        with _connect(old_dsn):
            pass
    except Exception as exc:  # noqa: BLE001
        old_failed = True
        old_error = f"{exc.__class__.__name__}: {exc}"

    os.environ["DATABASE_URL"] = new_dsn
    secrets_module = _reload_secret_modules()
    resolved_new = secrets_module.get_database_url()
    with _connect(resolved_new) as new_conn:
        with new_conn.cursor() as cur:
            cur.execute("SELECT current_user")
            new_current_user = str(cur.fetchone()[0])

    if not old_failed:
        raise RuntimeError("DB rotation drill failed: old credentials unexpectedly still authenticated")
    if old_current_user != old_user:
        raise RuntimeError(f"old credential resolved unexpected user: {old_current_user}")
    if new_current_user != new_user:
        raise RuntimeError(f"new credential resolved unexpected user: {new_current_user}")

    return {
        "status": "pass",
        "db_name": db_name,
        "old_user": old_user,
        "new_user": new_user,
        "old_authentication_after_rotation": "failed",
        "old_auth_failure": old_error[:400],
        "new_authentication_after_rotation": "success",
    }


class _ProviderHandler(BaseHTTPRequestHandler):
    expected_key = ""

    def do_GET(self):  # noqa: N802
        auth = self.headers.get("Authorization", "")
        expected = f"Bearer {self.expected_key}"
        if auth != expected:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"status":"unauthorized"}')
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def log_message(self, format: str, *args):  # noqa: A003
        return


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _provider_probe(port: int, key: str) -> int:
    import urllib.request
    import urllib.error

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/probe",
        headers={"Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            return int(resp.getcode())
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def _run_provider_rotation_drill() -> dict[str, Any]:
    old_key = secrets.token_urlsafe(16)
    new_key = secrets.token_urlsafe(16)
    _mask(old_key)
    _mask(new_key)

    port = _free_port()
    _ProviderHandler.expected_key = old_key
    server = HTTPServer(("127.0.0.1", port), _ProviderHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        os.environ["LLM_PROVIDER_API_KEY"] = old_key
        secrets_module = _reload_secret_modules()
        loaded_old = secrets_module.require_secret("LLM_PROVIDER_API_KEY")
        old_status = _provider_probe(port, loaded_old)

        _ProviderHandler.expected_key = new_key
        os.environ["LLM_PROVIDER_API_KEY"] = new_key
        secrets_module = _reload_secret_modules()
        loaded_new = secrets_module.require_secret("LLM_PROVIDER_API_KEY")
        old_after_rotation_status = _provider_probe(port, loaded_old)
        new_after_rotation_status = _provider_probe(port, loaded_new)
    finally:
        server.shutdown()
        server.server_close()

    if old_status != 200:
        raise RuntimeError(f"provider drill failed: old key did not initially authenticate (status={old_status})")
    if old_after_rotation_status not in {401, 403}:
        raise RuntimeError("provider drill failed: old key was not rejected after rotation")
    if new_after_rotation_status != 200:
        raise RuntimeError("provider drill failed: new key did not authenticate")

    return {
        "status": "pass",
        "old_key_initial_status": old_status,
        "old_key_post_rotation_status": old_after_rotation_status,
        "new_key_post_rotation_status": new_after_rotation_status,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="B11-P4 non-vacuous CI rotation drills")
    parser.add_argument("--out-dir", default="docs/forensics/evidence/b11_p4")
    parser.add_argument(
        "--admin-dsn",
        default=os.getenv("B11_P4_ROTATION_ADMIN_DSN", "postgresql://postgres:postgres@127.0.0.1:5432/postgres"),
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    db_result = _run_db_rotation_drill(args.admin_dsn)
    provider_result = _run_provider_rotation_drill()

    _write(out_dir / "rotation_drill_db_credentials_ci.txt", db_result)
    _write(out_dir / "rotation_drill_provider_key_ci.txt", provider_result)
    # Backward-compatible filenames referenced by earlier evidence index.
    _write(out_dir / "rotation_drill_db_credentials.txt", db_result)
    _write(out_dir / "rotation_drill_provider_key.txt", provider_result)

    print((out_dir / "rotation_drill_db_credentials_ci.txt").as_posix())
    print((out_dir / "rotation_drill_provider_key_ci.txt").as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
