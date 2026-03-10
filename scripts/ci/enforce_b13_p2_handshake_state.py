#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


REQUIRED_MIGRATION_FRAGMENTS = (
    "CREATE TABLE public.oauth_handshake_sessions",
    "tenant_id uuid NOT NULL",
    "user_id uuid NOT NULL",
    "state_nonce_hash",
    "encrypted_pkce_verifier",
    "pkce_key_id",
    "expires_at",
    "consumed_at",
    "status text NOT NULL DEFAULT 'pending'",
    "gc_after",
    "ENABLE ROW LEVEL SECURITY",
    "FORCE ROW LEVEL SECURITY",
    "CREATE POLICY tenant_isolation_policy ON public.oauth_handshake_sessions",
    "idx_oauth_handshake_sessions_gc_after",
)

REQUIRED_MODEL_FRAGMENTS = (
    '__tablename__ = "oauth_handshake_sessions"',
    "state_nonce_hash",
    "encrypted_pkce_verifier",
    "pkce_key_id",
    "expires_at",
    "consumed_at",
    "gc_after",
    "uq_oauth_handshake_sessions_tenant_state_hash",
)

REQUIRED_SERVICE_PATTERNS = (
    ("hash_state", re.compile(r"hashlib\.sha256\(", re.MULTILINE)),
    ("create_session", re.compile(r"def create_session\(", re.MULTILINE)),
    ("consume_session", re.compile(r"def consume_session\(", re.MULTILINE)),
    ("expire_pending_sessions", re.compile(r"def expire_pending_sessions\(", re.MULTILINE)),
    ("gc_eligible_sessions", re.compile(r"def gc_eligible_sessions\(", re.MULTILINE)),
    ("atomic_pending_guard", re.compile(r"status\s*==\s*['\"]pending['\"]", re.MULTILINE)),
    ("atomic_unconsumed_guard", re.compile(r"consumed_at\.is_\(None\)", re.MULTILINE)),
    ("atomic_not_expired_guard", re.compile(r"expires_at\s*>\s*now", re.MULTILINE)),
    ("update_consumed_state", re.compile(r"status\s*=\s*['\"]consumed['\"]", re.MULTILINE)),
)

PROHIBITED_DURABLE_TOKENS = (
    "state_nonce_hash",
    "pkce",
    "code_verifier",
    "gc_after",
    "consumed_at",
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B1.3-P2 handshake substrate enforcement")
    parser.add_argument(
        "--migration-file",
        default="alembic/versions/007_skeldir_foundation/202603101000_b13_p2_oauth_handshake_state_substrate.py",
    )
    parser.add_argument(
        "--model-file",
        default="backend/app/models/oauth_handshake_session.py",
    )
    parser.add_argument(
        "--service-file",
        default="backend/app/services/oauth_handshake_state.py",
    )
    parser.add_argument(
        "--platform-connection-model",
        default="backend/app/models/platform_connection.py",
    )
    parser.add_argument(
        "--platform-credential-model",
        default="backend/app/models/platform_credential.py",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    migration_path = Path(args.migration_file)
    model_path = Path(args.model_file)
    service_path = Path(args.service_file)
    connection_model_path = Path(args.platform_connection_model)
    credential_model_path = Path(args.platform_credential_model)

    files = (
        migration_path,
        model_path,
        service_path,
        connection_model_path,
        credential_model_path,
    )
    missing_files = [path for path in files if not path.exists()]
    if missing_files:
        print("B1.3-P2 handshake substrate gate failed:")
        for path in missing_files:
            print(f"  - file not found: {path}")
        return 1

    migration_text = _read_text(migration_path)
    model_text = _read_text(model_path)
    service_text = _read_text(service_path)
    connection_model_text = _read_text(connection_model_path)
    credential_model_text = _read_text(credential_model_path)

    errors: list[str] = []

    for fragment in REQUIRED_MIGRATION_FRAGMENTS:
        if fragment not in migration_text:
            errors.append(f"migration missing required fragment: {fragment}")

    for fragment in REQUIRED_MODEL_FRAGMENTS:
        if fragment not in model_text:
            errors.append(f"model missing required fragment: {fragment}")

    for label, pattern in REQUIRED_SERVICE_PATTERNS:
        if not pattern.search(service_text):
            errors.append(f"service missing required pattern: {label}")

    for token in PROHIBITED_DURABLE_TOKENS:
        if token in connection_model_text:
            errors.append(f"durable table abuse risk: platform_connection model contains transient token {token!r}")
        if token in credential_model_text:
            errors.append(f"durable table abuse risk: platform_credential model contains transient token {token!r}")

    if errors:
        print("B1.3-P2 handshake substrate gate failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("B1.3-P2 handshake substrate gate passed.")
    print(f"  migration={migration_path}")
    print(f"  model={model_path}")
    print(f"  service={service_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
