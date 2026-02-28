"""
B1.2-P2 auth substrate tests.

Covers:
- migration reversibility (upgrade -> downgrade -> re-upgrade)
- tenant RLS isolation on membership and role-assignment tables
- auth-substrate 0-PII scan (no raw email/IP columns or values)
- users registry least-privilege (self-only RLS + tenantless lookup boundary)
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
from sqlalchemy.engine.url import make_url

from app.core.secrets import get_database_url, get_migration_database_url


P2_REVISION = "202602271430"
P2_CORRECTIVE_REVISION = "202602281100"
P2_INSERT_CORRECTIVE_REVISION = "202602281430"
PRE_P2_REVISION = "202602221700"
AUTH_TABLES = ("users", "tenant_memberships", "roles", "tenant_membership_roles")
RUNTIME_ROLES = ("app_user", "app_rw", "app_ro")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_sync_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def _resolved_database_url(*, prefer_migration: bool) -> str:
    if prefer_migration:
        try:
            return _normalize_sync_url(get_migration_database_url())
        except Exception:
            pass
    try:
        return _normalize_sync_url(get_database_url())
    except Exception:
        pass
    url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL or MIGRATION_DATABASE_URL is required")
    return _normalize_sync_url(url)


def _sync_database_url() -> str:
    return _resolved_database_url(prefer_migration=True)


def _bootstrap_database_url() -> str:
    # Prefer runtime credential resolution path to match existing CI test jobs.
    return _resolved_database_url(prefer_migration=False)


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


def _ensure_runtime_roles(conn) -> None:
    """Provision deterministic runtime roles for least-privilege assertions."""
    conn.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
                    CREATE ROLE app_rw NOLOGIN NOSUPERUSER NOBYPASSRLS;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ro') THEN
                    CREATE ROLE app_ro NOLOGIN NOSUPERUSER NOBYPASSRLS;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                    CREATE ROLE app_user LOGIN PASSWORD 'app_user' NOSUPERUSER NOBYPASSRLS INHERIT;
                END IF;
            END
            $$;
            """
        )
    )
    conn.execute(text("GRANT app_rw TO app_user"))
    conn.execute(text("GRANT app_ro TO app_user"))


def _role_posture_rows(conn, roles: tuple[str, ...] = RUNTIME_ROLES):
    role_filter = ", ".join(f"'{role}'" for role in roles)
    return conn.execute(
        text(
            """
            SELECT rolname, rolsuper, rolbypassrls
            FROM pg_roles
            WHERE rolname IN ("""
            + role_filter
            + """)
            ORDER BY rolname
            """
        )
    ).mappings().all()


def _users_grants(conn):
    return conn.execute(
        text(
            """
            SELECT grantee, privilege_type
            FROM information_schema.role_table_grants
            WHERE table_schema = 'public' AND table_name = 'users'
            ORDER BY grantee, privilege_type
            """
        )
    ).mappings().all()


def _assert_runtime_role_posture_safe(posture_rows) -> None:
    assert posture_rows, "runtime role posture query returned no rows"
    for row in posture_rows:
        assert bool(row["rolsuper"]) is False, f"{row['rolname']} must not be superuser"
        assert bool(row["rolbypassrls"]) is False, (
            f"{row['rolname']} must not have BYPASSRLS"
        )


def _assert_users_grants_locked(grants_rows) -> None:
    grants = {(row["grantee"], row["privilege_type"]) for row in grants_rows}
    assert ("app_rw", "SELECT") not in grants, "app_rw must not have SELECT on users"
    assert ("app_rw", "INSERT") not in grants, "app_rw must not have INSERT on users"
    assert ("app_ro", "SELECT") not in grants, "app_ro must not have SELECT on users"
    assert ("app_ro", "INSERT") not in grants, "app_ro must not have INSERT on users"
    assert ("app_user", "SELECT") in grants, "app_user must retain SELECT on users"
    assert ("app_user", "INSERT") in grants, "app_user must retain INSERT on users"


def _activate_rls_probe_role(conn) -> tuple[str | None, bool]:
    """
    Activate a non-bypass role for RLS assertions.

    Prefer app_rw if present; otherwise provision a transient probe role when
    permissions allow. Returns (active_role, created_transient_role).
    """
    has_app_rw = conn.execute(
        text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw')")
    ).scalar_one()
    if bool(has_app_rw):
        conn.execute(text("SET ROLE app_rw"))
        return "app_rw", False

    try:
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'b12_p2_rls_probe') THEN
                        CREATE ROLE b12_p2_rls_probe NOLOGIN;
                    END IF;
                END
                $$;
                """
            )
        )
        conn.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE tenant_memberships TO b12_p2_rls_probe"
            )
        )
        conn.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE tenant_membership_roles TO b12_p2_rls_probe"
            )
        )
        conn.execute(text("SET ROLE b12_p2_rls_probe"))
        return "b12_p2_rls_probe", True
    except Exception:
        return None, False


def _cleanup_transient_rls_probe_role(conn) -> None:
    """Revoke transient role grants before dropping the probe role."""
    role_exists = conn.execute(
        text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'b12_p2_rls_probe')")
    ).scalar_one()
    if not bool(role_exists):
        return

    cleanup_statements = (
        "REVOKE ALL PRIVILEGES ON TABLE tenant_memberships FROM b12_p2_rls_probe",
        "REVOKE ALL PRIVILEGES ON TABLE tenant_membership_roles FROM b12_p2_rls_probe",
        "DROP OWNED BY b12_p2_rls_probe",
        "DROP ROLE b12_p2_rls_probe",
    )
    for statement in cleanup_statements:
        try:
            conn.execute(text(statement))
        except Exception:
            # Teardown must be best-effort in fallback CI database modes.
            pass


def _ensure_fallback_prerequisites(sync_url: str) -> None:
    """
    Provision minimal prerequisites when isolated DB creation is unavailable.

    Shared fallback databases in CI may not have run the full migration chain.
    B1.2-P2 requires pgcrypto + tenants FK target to create auth tables.
    """
    engine = create_engine(sync_url)
    with engine.begin() as conn:
        # RAW_SQL_ALLOWLIST: deterministic fallback bootstrap for CI-shared DB mode.
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.tenants (
                    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    name text NOT NULL,
                    api_key_hash text,
                    notification_email text,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    updated_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
        )


def _drop_auth_tables_best_effort(sync_url: str) -> None:
    """Best-effort cleanup for partially provisioned auth substrate tables."""
    engine = create_engine(sync_url)
    with engine.begin() as conn:
        for table_name in (
            "tenant_membership_roles",
            "tenant_memberships",
            "users",
            "roles",
        ):
            try:
                conn.execute(text(f"DROP TABLE IF EXISTS public.{table_name} CASCADE"))
            except Exception:
                # Fallback mode may run under a role without ownership; if so,
                # rely on existing objects and revision stamping below.
                pass


@pytest.fixture(scope="session")
def _isolated_database_url():
    """
    Provision a per-session temporary database to avoid cross-test schema collisions.

    In CI the JWT invariant job shares a Postgres service across multiple test modules.
    Running this suite in an isolated DB prevents duplicate migration side effects
    (for example kombu transport tables already created by prior tests).
    """
    base_url = _bootstrap_database_url()
    if os.getenv("B12_P2_FORCE_SHARED_DB_FALLBACK") == "1":
        os.environ["B12_P2_SHARED_DB_FALLBACK"] = "1"
        print("[b12-p2] forced shared DB fallback mode enabled")
        yield base_url
        return

    parsed = make_url(base_url)
    admin_parsed = parsed.set(database="postgres")
    isolated_db_name = f"skeldir_b12_p2_{uuid4().hex[:12]}"

    created = False
    admin_engine = create_engine(str(admin_parsed), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{isolated_db_name}"'))
        created = True
    except Exception as exc:
        # Some CI topologies deny CREATE DATABASE for runtime credentials.
        os.environ["B12_P2_SHARED_DB_FALLBACK"] = "1"
        print(
            f"[b12-p2] isolated DB provisioning unavailable; using shared DB fallback: {type(exc).__name__}: {exc}"
        )
        yield base_url
        return
    finally:
        admin_engine.dispose()

    os.environ["B12_P2_SHARED_DB_FALLBACK"] = "0"
    isolated_url = str(parsed.set(database=isolated_db_name))
    try:
        yield isolated_url
    finally:
        if not created:
            return
        cleanup_engine = create_engine(str(admin_parsed), isolation_level="AUTOCOMMIT")
        try:
            with cleanup_engine.connect() as conn:
                conn.execute(
                    text(
                        """
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = :db_name
                          AND pid <> pg_backend_pid()
                        """
                    ),
                    {"db_name": isolated_db_name},
                )
                conn.execute(text(f'DROP DATABASE IF EXISTS "{isolated_db_name}"'))
        finally:
            cleanup_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _migrate_head_once(_isolated_database_url):
    sync_url = _isolated_database_url
    os.environ["MIGRATION_DATABASE_URL"] = sync_url
    os.environ["DATABASE_URL"] = sync_url
    config = _alembic_config(sync_url)
    try:
        if os.environ.get("B12_P2_SHARED_DB_FALLBACK") == "1":
            # Shared DB fallback can contain runtime-created transport tables
            # that conflict with early Alembic revisions. Stamp to PRE_P2 then
            # upgrade only through the B1.2-P2 revision chain for setup.
            _ensure_fallback_prerequisites(sync_url)
            auth_tables_ready = all(_table_exists(sync_url, name) for name in AUTH_TABLES)
            if auth_tables_ready:
                # Existing auth substrate + stale revision metadata can occur in
                # shared fallback DBs. Normalize revision pointer only.
                command.stamp(config, "head")
            else:
                _drop_auth_tables_best_effort(sync_url)
                command.stamp(config, PRE_P2_REVISION)
                command.upgrade(config, "head")
        else:
            command.upgrade(config, "head")
    except Exception as exc:
        error_text = str(exc).lower()
        if "permission denied for table alembic_version" in error_text:
            raise RuntimeError(
                "B1.2-P2 auth substrate tests require migration-capable DB credentials. "
                "Set MIGRATION_DATABASE_URL (preferred) or DATABASE_URL to a role that can run Alembic."
            ) from exc
        raise

    engine = create_engine(sync_url)
    with engine.begin() as conn:
        _ensure_runtime_roles(conn)


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
        active_role: str | None = None
        created_probe_role = False
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

        active_role, created_probe_role = _activate_rls_probe_role(conn)
        if active_role is None:
            is_superuser = conn.execute(
                text(
                    """
                    SELECT rolsuper
                    FROM pg_roles
                    WHERE rolname = current_user
                    """
                )
            ).scalar_one()
            if bool(is_superuser):
                pytest.skip(
                    "RLS probe requires a non-superuser role (app_rw or transient probe role)."
                )

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
        if active_role is not None:
            conn.execute(text("RESET ROLE"))
        if created_probe_role:
            _cleanup_transient_rls_probe_role(conn)

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


def test_06_users_registry_least_privilege_contract():
    """
    Enforce B1.2-P2 corrective boundaries:
    - runtime roles cannot bypass RLS
    - users table is non-enumerable for app_rw/app_ro
    - users RLS is ENABLE + FORCE
    - tenantless lookup boundary exists via SECURITY DEFINER function

    Negative control toggles (used by CI harness):
    - SKELDIR_B12_USERS_FORCE_BYPASS_ROLE=1
    - SKELDIR_B12_USERS_FORCE_GRANT_REGRESSION=1
    - SKELDIR_B12_USERS_FORCE_DISABLE_RLS=1
    - SKELDIR_B12_USERS_FORCE_LOOKUP_OWNER_BYPASS=1
    """
    sync_url = _sync_database_url()
    engine = create_engine(sync_url)

    force_bypass = os.getenv("SKELDIR_B12_USERS_FORCE_BYPASS_ROLE") == "1"
    force_grant_regression = (
        os.getenv("SKELDIR_B12_USERS_FORCE_GRANT_REGRESSION") == "1"
    )
    force_disable_rls = os.getenv("SKELDIR_B12_USERS_FORCE_DISABLE_RLS") == "1"
    force_lookup_owner_bypass = (
        os.getenv("SKELDIR_B12_USERS_FORCE_LOOKUP_OWNER_BYPASS") == "1"
    )
    active_roles = RUNTIME_ROLES

    with engine.begin() as conn:
        _ensure_runtime_roles(conn)
        if force_bypass:
            conn.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_roles WHERE rolname = 'b12_p2_runtime_bypass_probe'
                        ) THEN
                            CREATE ROLE b12_p2_runtime_bypass_probe NOLOGIN BYPASSRLS;
                        END IF;
                    END
                    $$;
                    """
                )
            )
            active_roles = (*RUNTIME_ROLES, "b12_p2_runtime_bypass_probe")
        if force_grant_regression:
            conn.execute(text("GRANT SELECT ON TABLE public.users TO app_rw"))
        if force_disable_rls:
            conn.execute(text("ALTER TABLE public.users DISABLE ROW LEVEL SECURITY"))
        if force_lookup_owner_bypass:
            conn.execute(
                text("ALTER FUNCTION auth.lookup_user_by_login_hash(text) OWNER TO postgres")
            )

        posture_rows = _role_posture_rows(conn, active_roles)
        grants_rows = _users_grants(conn)
        rls_row = conn.execute(
            text(
                """
                SELECT relrowsecurity, relforcerowsecurity
                FROM pg_class
                WHERE oid = 'public.users'::regclass
                """
            )
        ).mappings().one()
        lookup_row = conn.execute(
            text(
                """
                SELECT routine_schema, routine_name, security_type
                FROM information_schema.routines
                WHERE routine_schema = 'auth'
                  AND routine_name = 'lookup_user_by_login_hash'
                """
            )
        ).mappings().one()
        insert_policy_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename = 'users'
                  AND policyname = 'users_provision_insert_policy'
                  AND cmd = 'INSERT'
                """
            )
        ).scalar_one()
        lookup_owner_row = conn.execute(
            text(
                """
                SELECT
                    r.rolname AS owner_role,
                    r.rolsuper,
                    r.rolbypassrls
                FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                JOIN pg_roles r ON r.oid = p.proowner
                WHERE n.nspname = 'auth'
                  AND p.proname = 'lookup_user_by_login_hash'
                  AND p.pronargs = 1
                """
            )
        ).mappings().one()

        _assert_runtime_role_posture_safe(posture_rows)
        _assert_users_grants_locked(grants_rows)
        assert bool(rls_row["relrowsecurity"]) is True
        assert bool(rls_row["relforcerowsecurity"]) is True
        assert int(insert_policy_count) == 1
        assert lookup_row["security_type"] == "DEFINER"
        assert lookup_row["routine_schema"] == "auth"
        assert lookup_row["routine_name"] == "lookup_user_by_login_hash"
        assert bool(lookup_owner_row["rolsuper"]) is False, (
            "lookup function owner must not be superuser"
        )
        assert bool(lookup_owner_row["rolbypassrls"]) is False, (
            "lookup function owner must not have BYPASSRLS"
        )


def test_07_users_registry_self_only_rls_and_non_enumerability():
    sync_url = _sync_database_url()
    engine = create_engine(sync_url)

    user_a = uuid4()
    user_b = uuid4()

    with engine.begin() as conn:
        _ensure_runtime_roles(conn)
        conn.execute(
            text(
                """
                INSERT INTO users (id, login_identifier_hash, external_subject_hash, auth_provider)
                VALUES
                    (:user_a, :hash_a, :sub_a, 'password'),
                    (:user_b, :hash_b, :sub_b, 'password')
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
            },
        )

        conn.execute(text("SET ROLE app_user"))
        hidden_count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one()
        assert int(hidden_count) == 0

        conn.execute(
            text("SELECT set_config('app.current_user_id', :user_id, false)"),
            {"user_id": str(user_a)},
        )
        visible_count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one()
        assert int(visible_count) == 1

        cross_tenant_row = conn.execute(
            text("SELECT id FROM users WHERE id = :user_b"),
            {"user_b": str(user_b)},
        ).scalar_one_or_none()
        assert cross_tenant_row is None
        conn.execute(text("RESET ROLE"))


def test_08_tenantless_lookup_boundary_without_users_scan():
    sync_url = _sync_database_url()
    engine = create_engine(sync_url)

    target_user = uuid4()
    login_hash = f"lookup-hash-{target_user}"

    with engine.begin() as conn:
        _ensure_runtime_roles(conn)
        conn.execute(
            text(
                """
                INSERT INTO users (id, login_identifier_hash, external_subject_hash, auth_provider, is_active)
                VALUES (:user_id, :login_hash, :subject_hash, 'password', true)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "user_id": str(target_user),
                "login_hash": login_hash,
                "subject_hash": f"subject-{target_user}",
            },
        )

        conn.execute(text("SET ROLE app_user"))
        lookup = conn.execute(
            text(
                """
                SELECT user_id, is_active, auth_provider
                FROM auth.lookup_user_by_login_hash(:login_hash)
                """
            ),
            {"login_hash": login_hash},
        ).mappings().one()
        assert str(lookup["user_id"]) == str(target_user)
        assert bool(lookup["is_active"]) is True
        assert lookup["auth_provider"] == "password"

        direct_scan_count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one()
        assert int(direct_scan_count) == 0
        conn.execute(text("RESET ROLE"))

        conn.execute(text("SET ROLE app_rw"))
        savepoint = conn.begin_nested()
        try:
            with pytest.raises(Exception):
                conn.execute(text("SELECT COUNT(*) FROM users"))
        finally:
            savepoint.rollback()
        conn.execute(text("RESET ROLE"))


def test_09_users_schema_invariant_no_tenant_id_column():
    sync_url = _sync_database_url()
    engine = create_engine(sync_url)
    with engine.begin() as conn:
        tenant_id_columns = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'users'
                  AND column_name = 'tenant_id'
                """
            )
        ).scalar_one()
        assert int(tenant_id_columns) == 0


def test_10_users_preauth_insert_viability_under_force_rls():
    """
    Enforce B1.2-P2 corrective v3 boundaries:
    - runtime writer role (app_user) can INSERT users pre-auth (no app.current_user_id)
    - read-only runtime roles remain blocked from INSERT

    Negative control toggle (used by CI harness):
    - SKELDIR_B12_USERS_FORCE_DROP_INSERT_POLICY=1
    """
    sync_url = _sync_database_url()
    engine = create_engine(sync_url)
    force_drop_insert_policy = (
        os.getenv("SKELDIR_B12_USERS_FORCE_DROP_INSERT_POLICY") == "1"
    )

    with engine.begin() as conn:
        _ensure_runtime_roles(conn)
        if force_drop_insert_policy:
            conn.execute(
                text("DROP POLICY IF EXISTS users_provision_insert_policy ON public.users")
            )

        insert_policy = conn.execute(
            text(
                """
                SELECT polname, polcmd, polroles::regrole[]::text AS polroles
                FROM pg_policy
                WHERE polrelid = 'public.users'::regclass
                  AND polname = 'users_provision_insert_policy'
                """
            )
        ).mappings().one_or_none()
        assert insert_policy is not None, "users INSERT policy must exist"
        assert insert_policy["polcmd"] == "a", "users INSERT policy must be FOR INSERT"
        policy_roles = str(insert_policy["polroles"])
        assert ("{app_user}" in policy_roles) or ("{public}" in policy_roles), (
            "users INSERT policy roles must be app_user (or PUBLIC fallback when app_user is absent at migration time)"
        )
        grants_rows = _users_grants(conn)
        _assert_users_grants_locked(grants_rows)

        probe_user_id = uuid4()
        conn.execute(text("SET ROLE app_user"))
        conn.execute(text("RESET app.current_user_id"))
        conn.execute(
            text(
                """
                INSERT INTO users (id, login_identifier_hash, external_subject_hash, auth_provider)
                VALUES (:user_id, :login_hash, :subject_hash, 'password')
                """
            ),
            {
                "user_id": str(probe_user_id),
                "login_hash": f"preauth-insert-hash-{probe_user_id}",
                "subject_hash": f"preauth-insert-subject-{probe_user_id}",
            },
        )
        conn.execute(text("RESET ROLE"))
        inserted_row = conn.execute(
            text("SELECT id FROM users WHERE id = :user_id"),
            {"user_id": str(probe_user_id)},
        ).scalar_one_or_none()
        assert str(inserted_row) == str(probe_user_id)
        conn.execute(
            text("DELETE FROM users WHERE id = :user_id"), {"user_id": str(probe_user_id)}
        )

        conn.execute(text("SET ROLE app_ro"))
        savepoint = conn.begin_nested()
        try:
            with pytest.raises(Exception):
                conn.execute(
                    text(
                        """
                        INSERT INTO users (id, login_identifier_hash, external_subject_hash, auth_provider)
                        VALUES (:user_id, :login_hash, :subject_hash, 'password')
                        """
                    ),
                    {
                        "user_id": str(uuid4()),
                        "login_hash": f"ro-insert-hash-{uuid4()}",
                        "subject_hash": f"ro-insert-subject-{uuid4()}",
                    },
                )
        finally:
            savepoint.rollback()
            conn.execute(text("RESET ROLE"))
