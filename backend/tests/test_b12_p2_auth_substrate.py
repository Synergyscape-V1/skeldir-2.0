"""
B1.2-P2 auth substrate tests.

Covers:
- migration reversibility (upgrade -> downgrade -> re-upgrade)
- tenant RLS isolation on membership and role-assignment tables
- auth-substrate 0-PII scan (no raw email/IP columns or values)
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


P2_REVISION = "202602271430"
PRE_P2_REVISION = "202602221700"
AUTH_TABLES = ("users", "tenant_memberships", "roles", "tenant_membership_roles")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sync_database_url() -> str:
    url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL or MIGRATION_DATABASE_URL is required")
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def _alembic_config(sync_url: str) -> Config:
    config = Config(str(_repo_root() / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", sync_url)
    return config


def _table_exists(sync_url: str, table_name: str) -> bool:
    engine = create_engine(sync_url)
    with engine.begin() as conn:
        exists = conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = :table_name
                )
                """
            ),
            {"table_name": table_name},
        ).scalar_one()
    return bool(exists)


def _seed_tenant(conn, tenant_id: UUID) -> None:
    # RAW_SQL_ALLOWLIST: tenant fixture seed for auth substrate validation
    conn.execute(
        text(
            """
            INSERT INTO tenants (id, name, api_key_hash, notification_email, created_at, updated_at)
            VALUES (:tenant_id, :name, :api_key_hash, :notification_email, now(), now())
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "name": f"tenant-{str(tenant_id)[:8]}",
            "api_key_hash": f"api_key_hash_{tenant_id}",
            "notification_email": f"redacted-{tenant_id}",
        },
    )


def _hash_identifier(value: str, pepper: str) -> str:
    canonical = value.strip().lower()
    return hashlib.sha256(f"{pepper}:{canonical}".encode("utf-8")).hexdigest()


@pytest.fixture(scope="session", autouse=True)
def _migrate_head_once():
    sync_url = _sync_database_url()
    os.environ["MIGRATION_DATABASE_URL"] = sync_url
    os.environ["DATABASE_URL"] = sync_url
    try:
        command.upgrade(_alembic_config(sync_url), "head")
    except Exception as exc:
        error_text = str(exc).lower()
        if "permission denied for table alembic_version" in error_text:
            raise RuntimeError(
                "B1.2-P2 auth substrate tests require migration-capable DB credentials. "
                "Set MIGRATION_DATABASE_URL (preferred) or DATABASE_URL to a role that can run Alembic."
            ) from exc
        raise


def test_01_auth_substrate_migration_reversibility():
    sync_url = _sync_database_url()
    config = _alembic_config(sync_url)
    os.environ["MIGRATION_DATABASE_URL"] = sync_url
    os.environ["DATABASE_URL"] = sync_url

    command.upgrade(config, "head")
    for table_name in AUTH_TABLES:
        assert _table_exists(
            sync_url, table_name
        ), f"expected table {table_name} at head"

    command.downgrade(config, PRE_P2_REVISION)
    for table_name in AUTH_TABLES:
        assert not _table_exists(
            sync_url, table_name
        ), f"expected table {table_name} absent after downgrade to {PRE_P2_REVISION}"

    command.upgrade(config, "head")
    for table_name in AUTH_TABLES:
        assert _table_exists(
            sync_url, table_name
        ), f"expected table {table_name} present after re-upgrade"


def test_02_auth_membership_rls_isolation():
    sync_url = _sync_database_url()
    engine = create_engine(sync_url)

    tenant_a = uuid4()
    tenant_b = uuid4()
    user_a = uuid4()
    user_b = uuid4()
    user_cross = uuid4()
    membership_a = uuid4()
    membership_b = uuid4()

    with engine.begin() as conn:
        _seed_tenant(conn, tenant_a)
        _seed_tenant(conn, tenant_b)

        # RAW_SQL_ALLOWLIST: controlled auth substrate seed rows for RLS validation.
        conn.execute(
            text(
                """
                INSERT INTO users (id, login_identifier_hash, external_subject_hash, auth_provider)
                VALUES
                    (:user_a, :hash_a, :sub_a, 'password'),
                    (:user_b, :hash_b, :sub_b, 'password'),
                    (:user_cross, :hash_cross, :sub_cross, 'password')
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "user_a": str(user_a),
                "hash_a": f"hash-{user_a}",
                "sub_a": f"sub-{user_a}",
                "user_b": str(user_b),
                "hash_b": f"hash-{user_b}",
                "sub_b": f"sub-{user_b}",
                "user_cross": str(user_cross),
                "hash_cross": f"hash-{user_cross}",
                "sub_cross": f"sub-{user_cross}",
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO tenant_memberships (id, tenant_id, user_id, membership_status)
                VALUES
                    (:membership_a, :tenant_a, :user_a, 'active'),
                    (:membership_b, :tenant_b, :user_b, 'active')
                ON CONFLICT (tenant_id, user_id) DO NOTHING
                """
            ),
            {
                "membership_a": str(membership_a),
                "tenant_a": str(tenant_a),
                "user_a": str(user_a),
                "membership_b": str(membership_b),
                "tenant_b": str(tenant_b),
                "user_b": str(user_b),
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO tenant_membership_roles (tenant_id, membership_id, role_code)
                VALUES
                    (:tenant_a, :membership_a, 'admin'),
                    (:tenant_b, :membership_b, 'viewer')
                ON CONFLICT (membership_id, role_code) DO NOTHING
                """
            ),
            {
                "tenant_a": str(tenant_a),
                "membership_a": str(membership_a),
                "tenant_b": str(tenant_b),
                "membership_b": str(membership_b),
            },
        )

        conn.execute(text("SET ROLE app_rw"))
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_a)},
        )
        memberships_visible_a = conn.execute(
            text("SELECT COUNT(*) FROM tenant_memberships")
        ).scalar_one()
        roles_visible_a = conn.execute(
            text("SELECT COUNT(*) FROM tenant_membership_roles")
        ).scalar_one()

        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_b)},
        )
        memberships_visible_b = conn.execute(
            text("SELECT COUNT(*) FROM tenant_memberships")
        ).scalar_one()
        roles_visible_b = conn.execute(
            text("SELECT COUNT(*) FROM tenant_membership_roles")
        ).scalar_one()

        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_a)},
        )
        savepoint = conn.begin_nested()
        try:
            with pytest.raises(Exception):
                conn.execute(
                    text(
                        """
                        INSERT INTO tenant_memberships (tenant_id, user_id, membership_status)
                        VALUES (:tenant_b, :user_cross, 'active')
                        """
                    ),
                    {
                        "tenant_b": str(tenant_b),
                        "user_cross": str(user_cross),
                    },
                )
        finally:
            savepoint.rollback()
        conn.execute(text("RESET ROLE"))

    assert memberships_visible_a == 1
    assert roles_visible_a == 1
    assert memberships_visible_b == 1
    assert roles_visible_b == 1


def test_03_auth_substrate_stores_no_raw_email_or_ip():
    sync_url = _sync_database_url()
    engine = create_engine(sync_url)

    tenant_id = uuid4()
    user_id = uuid4()
    membership_id = uuid4()

    raw_email = "privacy.user+case@example.com"
    raw_ip = "203.0.113.42"
    pepper = "b12-p2-test-pepper"

    with engine.begin() as conn:
        _seed_tenant(conn, tenant_id)
        conn.execute(
            text(
                """
                INSERT INTO users (id, login_identifier_hash, external_subject_hash, auth_provider)
                VALUES (:user_id, :login_hash, :subject_hash, 'password')
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "user_id": str(user_id),
                "login_hash": _hash_identifier(raw_email, pepper),
                "subject_hash": _hash_identifier(raw_ip, pepper),
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO tenant_memberships (id, tenant_id, user_id, membership_status)
                VALUES (:membership_id, :tenant_id, :user_id, 'active')
                ON CONFLICT (tenant_id, user_id) DO NOTHING
                """
            ),
            {
                "membership_id": str(membership_id),
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO tenant_membership_roles (tenant_id, membership_id, role_code)
                VALUES (:tenant_id, :membership_id, 'viewer')
                ON CONFLICT (membership_id, role_code) DO NOTHING
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "membership_id": str(membership_id),
            },
        )

        hashed_lookup = conn.execute(
            text(
                """
                SELECT id
                FROM users
                WHERE login_identifier_hash = :login_hash
                """
            ),
            {"login_hash": _hash_identifier(raw_email, pepper)},
        ).scalar_one()
        assert str(hashed_lookup) == str(user_id)

        exported_row = conn.execute(
            text(
                """
                SELECT row_to_json(u)::text
                FROM users u
                WHERE u.id = :user_id
                """
            ),
            {"user_id": str(user_id)},
        ).scalar_one()
        exported_lower = str(exported_row).lower()
        assert raw_email.lower() not in exported_lower
        assert raw_ip.lower() not in exported_lower

        disallowed_columns = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name IN ('users', 'tenant_memberships', 'roles', 'tenant_membership_roles')
                  AND column_name ~* '(^|_)(email|ip|ip_address)($|_)'
                """
            )
        ).scalar_one()
        assert int(disallowed_columns) == 0

    script = _repo_root() / "scripts" / "security" / "b12_p2_auth_pii_guard.py"
    result = subprocess.run(
        [sys.executable, str(script), "--database-url", sync_url],
        capture_output=True,
        text=True,
        cwd=_repo_root(),
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_04_auth_pii_guard_negative_control():
    script = _repo_root() / "scripts" / "security" / "b12_p2_auth_pii_guard.py"
    result = subprocess.run(
        [sys.executable, str(script), "--simulate-violation"],
        capture_output=True,
        text=True,
        cwd=_repo_root(),
        check=False,
    )
    assert result.returncode != 0
    assert "synthetic_violation" in (result.stdout + result.stderr)


def test_05_auth_pii_guard_detects_real_raw_value_injection():
    sync_url = _sync_database_url()
    engine = create_engine(sync_url)

    injected_user_id = uuid4()
    injected_email = "guard-negative-control@example.com"

    with engine.begin() as conn:
        # RAW_SQL_ALLOWLIST: intentional raw email injection for non-vacuous scanner validation.
        conn.execute(
            text(
                """
                INSERT INTO users (id, login_identifier_hash, external_subject_hash, auth_provider)
                VALUES (:user_id, :login_hash, :subject_hash, 'password')
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "user_id": str(injected_user_id),
                "login_hash": injected_email,
                "subject_hash": "non-pii-subject",
            },
        )

    script = _repo_root() / "scripts" / "security" / "b12_p2_auth_pii_guard.py"
    result = subprocess.run(
        [sys.executable, str(script), "--database-url", sync_url],
        capture_output=True,
        text=True,
        cwd=_repo_root(),
        check=False,
    )
    assert result.returncode != 0
    assert "disallowed_value: public.users.login_identifier_hash" in (
        result.stdout + result.stderr
    )

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM users WHERE id = :user_id"),
            {"user_id": str(injected_user_id)},
        )
