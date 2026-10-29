"""
Pytest fixtures for B0.4.3 tests.

Provides tenant creation/cleanup fixtures to satisfy FK constraints.
"""
import os
import logging
from uuid import uuid4
from urllib.parse import urlparse

import pytest
from sqlalchemy import create_engine, text

from app.db.dsn import to_sync_postgres_dsn
from app.testing.jwt_rs256 import private_ring_payload, public_ring_payload

os.environ["TESTING"] = "1"
os.environ.setdefault("SKELDIR_TEST_RUN_ID", f"m2-{uuid4().hex}")
os.environ.setdefault("SKELDIR_TEST_PARALLEL_MODE", "serial-only")
os.environ.setdefault("SKELDIR_TEST_WORKER_ID", os.getenv("PYTEST_XDIST_WORKER", "master"))
os.environ.setdefault("AUTH_JWT_SECRET", private_ring_payload())
os.environ.setdefault("AUTH_JWT_PUBLIC_KEY_RING", public_ring_payload())
os.environ.setdefault("AUTH_JWT_ALGORITHM", "RS256")
os.environ.setdefault("AUTH_JWT_ISSUER", "https://issuer.skeldir.test")
os.environ.setdefault("AUTH_JWT_AUDIENCE", "skeldir-api")
os.environ.setdefault("PLATFORM_TOKEN_ENCRYPTION_KEY", "test-platform-key")
os.environ.setdefault("PLATFORM_TOKEN_KEY_ID", "test-key")
os.environ.setdefault("B26_P2_HISTORY_WITNESS_REQUIRED", "false")

# httpx/httpcore may emit INFO records with incompatible %-format args under pytest capture.
# Keep backend test logging deterministic and focused on app-level signals.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# B0.5.3.3 Gate C: CI-first credential coherence (MUST execute before any imports)
# In CI, DATABASE_URL MUST be provided by step env vars - no fallbacks, no defaults.
if os.getenv("CI") == "true":
    if "DATABASE_URL" not in os.environ:
        raise RuntimeError(
            "[B0.5.3.3 Gate C] CI FAILURE: DATABASE_URL not set in environment. "
            "pytest step MUST explicitly set DATABASE_URL env var before test execution. "
            "This prevents conftest from setting stale fallback credentials that cause "
            "Celery broker/result backend auth failures (psycopg2.OperationalError)."
        )

    # Validate CI DSN is localhost (not Neon production)
    from app.core.secrets import get_database_url

    ci_runtime_dsn = get_database_url()
    if "neon.tech" in ci_runtime_dsn:
        raise RuntimeError(
            f"[B0.5.3.3 Gate C] CI DSN MUST be localhost; "
            f"resolved={ci_runtime_dsn.split('@')[1].split('/')[0]}"
        )

    # Diagnostic logging for CI DSN transparency
    dsn = ci_runtime_dsn
    if "@" in dsn and "/" in dsn:
        host = dsn.split('@')[1].split('/')[0]
        print(f"[B0.5.3.3 Gate C] CI DATABASE_URL host: {host}")
        # Log password fingerprint for credential coherence validation
        import hashlib
        if "://" in dsn and "@" in dsn:
            try:
                creds = dsn.split('://')[1].split('@')[0]
                if ':' in creds:
                    password = creds.split(':')[1]
                    pass_hash = hashlib.sha256(password.encode()).hexdigest()[:8]
                    print(f"[B0.5.3.3 Gate C] CI DATABASE_URL password hash: {pass_hash}")
            except Exception:
                pass
    else:
        print(f"[B0.5.3.3 Gate C] DATABASE_URL format unexpected: {dsn[:30]}...")

else:
    # Local dev fallback (only when NOT in CI)
    if "DATABASE_URL" not in os.environ:
        os.environ["DATABASE_URL"] = "postgresql://app_user:app_user@127.0.0.1:5432/skeldir"
        print("[B0.5.3.3 Gate C] Local dev: Using localhost DSN fallback (override with DATABASE_URL env var)")

from app.db.session import engine  # noqa: E402

# B0.5.3.3 Gate C: Trigger Celery configuration AFTER DATABASE_URL validation
# This ensures settings is imported with validated credentials
from app.celery_app import _ensure_celery_configured  # noqa: E402
_ensure_celery_configured()

_RUNTIME_IDENTITY_VERIFIED = False


def _managed_runtime_dsn() -> str:
    from app.core.secrets import get_database_url

    return get_database_url()


def _managed_migration_dsn() -> str:
    from app.core.secrets import get_migration_database_url

    return get_migration_database_url()


def _cleanup_migration_dsn() -> str | None:
    """Sync migration DSN for test-database hygiene, or None when unavailable.

    Regression batteries seed authenticated financial rows through the atomic
    function rather than the authentication root, so those rows carry no
    source-money attestation. The XXV live sweep correctly refuses a row that
    claims ``current`` without an attestation. The test database must not be
    left in that state: CI runs the mandatory proof against the same database
    in some jobs, and a fixture-residue failure is not an artifact failure.
    """
    raw = os.environ.get("MIGRATION_DATABASE_URL") or ""
    if not raw:
        return None
    if raw.startswith("postgresql+asyncpg://"):
        raw = to_sync_postgres_dsn(raw)
    return raw


def _cleanup_database_name(dsn: str) -> str:
    from urllib.parse import urlparse

    return urlparse(dsn).path.lstrip("/")


def _cleanup_is_permitted(dsn: str) -> bool:
    name = _cleanup_database_name(dsn).lower()
    if os.environ.get("ENVIRONMENT", "").lower() in {"prod", "production"}:
        return False
    if name == "skeldir_xxv" and os.environ.get("B26_P2_XXV_LANE_ROOT"):
        return False
    markers = ("test", "ci", "consequence", "isolation", "_lane", "xxv_amend")
    return any(marker in name for marker in markers)


def pytest_configure(config: pytest.Config) -> None:
    """Refuse the live XXV lane database; it is not a regression database."""
    dsn = _cleanup_migration_dsn()
    if dsn is None:
        return
    name = _cleanup_database_name(dsn)
    if name == "skeldir_xxv" and os.environ.get("B26_P2_XXV_LANE_ROOT"):
        raise pytest.UsageError(
            "refusing to run pytest against the live XXV lane database "
            "skeldir_xxv; use skeldir_xxv_test for regression batteries"
        )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Withdraw fixture-seeded current claims that have no attestation.

    The update is one transaction with RLS/triggers relaxed only for the
    cleanup, then restored. A failure to clean leaves the session red rather
    than silently leaving a contamination that a later mandatory proof would
    attribute to the artifact.
    """
    dsn = _cleanup_migration_dsn()
    if dsn is None or not _cleanup_is_permitted(dsn):
        return
    import psycopg2  # noqa: PLC0415

    conn = None
    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute(
            "SELECT pg_get_userbyid(relowner) = current_user"
            " FROM pg_class WHERE oid ="
            " 'public.b23_match_verdicts'::regclass"
        )
        owned = cur.fetchone()
        if not owned or owned[0] is not True:
            # A runtime DSN cannot alter the guard; leave the test database
            # alone rather than turning a skip into a false red.
            conn.rollback()
            return
        for statement in (
            "ALTER TABLE public.b23_match_verdicts"
            " NO FORCE ROW LEVEL SECURITY",
            "ALTER TABLE public.webhook_ingress_identities"
            " NO FORCE ROW LEVEL SECURITY",
            "ALTER TABLE public.b26_p2_provider_auth_consequence"
            " NO FORCE ROW LEVEL SECURITY",
            "ALTER TABLE public.b26_p2_source_money_attestation"
            " NO FORCE ROW LEVEL SECURITY",
            "ALTER TABLE public.b23_match_verdicts DISABLE TRIGGER USER",
            "ALTER TABLE public.webhook_ingress_identities"
            " DISABLE TRIGGER USER",
        ):
            cur.execute(statement)
        cur.execute(
            """
            SELECT v.id::text, v.webhook_ingress_identity_id::text
              FROM public.b23_match_verdicts AS v
              JOIN public.b26_p2_provider_auth_consequence AS c
                ON c.webhook_ingress_identity_id =
                   v.webhook_ingress_identity_id
               AND c.tenant_id = v.tenant_id
              LEFT JOIN public.b26_p2_source_money_attestation AS a
                ON a.webhook_ingress_identity_id =
                   v.webhook_ingress_identity_id
               AND a.tenant_id = v.tenant_id
             WHERE c.recorded_by = 'app_ingress'
               AND v.b26_p2_source_authority_state = 'current'
               AND a.webhook_ingress_identity_id IS NULL
            """
        )
        rows = cur.fetchall()
        if not rows:
            conn.rollback()
            return
        for verdict_id, ingress_id in rows:
            if ingress_id is not None:
                cur.execute(
                    "UPDATE public.webhook_ingress_identities"
                    " SET b26_p2_demotion_reason ="
                    " 'xxv_test_fixture_withdrawn'"
                    " WHERE id = %s",
                    (ingress_id,),
                )
            cur.execute(
                "UPDATE public.b23_match_verdicts"
                " SET b26_p2_source_authority_state ="
                " 'historically_unverifiable'"
                " WHERE id = %s",
                (verdict_id,),
            )
        for statement in (
            "ALTER TABLE public.b23_match_verdicts ENABLE TRIGGER USER",
            "ALTER TABLE public.webhook_ingress_identities"
            " ENABLE TRIGGER USER",
            "ALTER TABLE public.b23_match_verdicts"
            " FORCE ROW LEVEL SECURITY",
            "ALTER TABLE public.webhook_ingress_identities"
            " FORCE ROW LEVEL SECURITY",
            "ALTER TABLE public.b26_p2_provider_auth_consequence"
            " FORCE ROW LEVEL SECURITY",
            "ALTER TABLE public.b26_p2_source_money_attestation"
            " FORCE ROW LEVEL SECURITY",
        ):
            cur.execute(statement)
        conn.commit()
        print(
            "[xxv-fixture-hygiene] withdrew"
            f" {len(rows)} unattested current-claiming test verdict(s)"
        )
    except Exception as exc:  # noqa: BLE001 - cleanup failure must be visible
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        print(f"[xxv-fixture-hygiene] cleanup failed: {type(exc).__name__}: {exc}")
        session.exitstatus = 1
    finally:
        if conn is not None:
            conn.close()


def _is_runtime_proof_test(node) -> bool:
    keywords = node.keywords
    if "integration" in keywords or "e2e" in keywords:
        return True
    node_path = str(getattr(node, "fspath", "")).replace("\\", "/").lower()
    return "/integration/" in node_path or node_path.endswith("_e2e.py")


def _dsn_username(dsn: str) -> str:
    return urlparse(dsn).username or ""


@pytest.fixture(autouse=True)
def _assert_runtime_identity_parity(request: pytest.FixtureRequest) -> None:
    """Global invariant: runtime proof tests in CI must execute as runtime DB identity."""
    global _RUNTIME_IDENTITY_VERIFIED
    if _RUNTIME_IDENTITY_VERIFIED:
        return
    if os.getenv("ENFORCE_RUNTIME_IDENTITY_PARITY") != "1":
        return
    if os.getenv("CI") != "true":
        return
    if not _is_runtime_proof_test(request.node):
        return

    runtime_dsn = _managed_runtime_dsn()
    migration_dsn = _managed_migration_dsn()
    expected_runtime_user = os.getenv("EXPECTED_RUNTIME_DB_USER")

    if not runtime_dsn:
        raise RuntimeError("CI runtime proof requires DATABASE_URL.")
    if not migration_dsn:
        raise RuntimeError("CI runtime proof requires MIGRATION_DATABASE_URL for identity parity checks.")
    if not expected_runtime_user:
        raise RuntimeError("CI runtime proof requires EXPECTED_RUNTIME_DB_USER.")
    if runtime_dsn == migration_dsn:
        raise RuntimeError("DATABASE_URL and MIGRATION_DATABASE_URL must not be identical in CI runtime proofs.")

    runtime_engine = create_engine(to_sync_postgres_dsn(runtime_dsn))
    migration_engine = create_engine(to_sync_postgres_dsn(migration_dsn))
    with runtime_engine.connect() as runtime_conn:
        runtime_current_user = runtime_conn.execute(text("SELECT current_user")).scalar_one()
    with migration_engine.connect() as migration_conn:
        migration_current_user = migration_conn.execute(text("SELECT current_user")).scalar_one()

    runtime_dsn_user = _dsn_username(runtime_dsn)
    if runtime_current_user != expected_runtime_user:
        raise RuntimeError(
            f"runtime identity mismatch: current_user={runtime_current_user}, expected={expected_runtime_user}"
        )
    if runtime_dsn_user and runtime_dsn_user != expected_runtime_user:
        raise RuntimeError(
            f"runtime DSN username mismatch: username={runtime_dsn_user}, expected={expected_runtime_user}"
        )
    if migration_current_user == runtime_current_user:
        raise RuntimeError(
            "runtime proof connected as migration/privileged identity; strict separation violated."
        )

    _RUNTIME_IDENTITY_VERIFIED = True


async def _insert_tenant(conn, tenant_id: uuid4, api_key_hash: str) -> None:
    """
    Insert a tenant row while tolerating schema drift (api_key_hash/notification_email optional).
    """
    result = await conn.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name = 'tenants'")
    )
    columns = set(result.scalars().all())

    insert_cols = ["id", "name"]
    params = {
        "id": str(tenant_id),
        "name": f"Test Tenant {str(tenant_id)[:8]}",
        "api_key_hash": api_key_hash,
        "notification_email": f"test_{str(tenant_id)[:8]}@test.local",
    }

    if "api_key_hash" in columns:
        insert_cols.append("api_key_hash")
    if "notification_email" in columns:
        insert_cols.append("notification_email")

    values_clause = ", ".join(f":{col}" for col in insert_cols)
    # RAW_SQL_ALLOWLIST: bootstrap tenant fixture during migration/rls setup
    await conn.execute(
        text(
            f"INSERT INTO tenants ({', '.join(insert_cols)}) VALUES ({values_clause})"
        ),
        params,
    )


@pytest.fixture(scope="function")
async def test_tenant():
    """
    Create a test tenant record and clean up after test.

    Returns tenant_id UUID that satisfies FK constraints.
    """
    tenant_id = uuid4()
    api_key_hash = "test_hash_" + str(tenant_id)[:8]

    async with engine.begin() as conn:
        await _insert_tenant(conn, tenant_id, api_key_hash)

    yield tenant_id

    # Cleanup - delete tenant and cascading records
    # Note: attribution_events is append-only (trg_events_prevent_mutation)
    # We cannot delete from it, so we skip cleanup for that table
    async with engine.begin() as conn:
        # Skip attribution_events cleanup (append-only)
        # await conn.execute(
        #     text("DELETE FROM attribution_events WHERE tenant_id = :tid"),
        #     {"tid": str(tenant_id)},
        # )

        # Dead events can be deleted (no mutation trigger)
        try:
            await conn.execute(
                text("DELETE FROM dead_events WHERE tenant_id = :tid"),
                {"tid": str(tenant_id)},
            )
        except Exception:
            pass  # Best effort cleanup

        # Tenants - may fail due to FK constraints from attribution_events
        # We'll leave test tenants in database for now
        # Production cleanup would use archival/retention policies
        # await conn.execute(
        #     text("DELETE FROM tenants WHERE id = :tid"),
        #     {"tid": str(tenant_id)},
        # )


@pytest.fixture(scope="function")
async def test_tenant_pair():
    """
    Create two test tenant records for RLS validation tests.

    Returns tuple (tenant_a_id, tenant_b_id).
    """
    tenant_a = uuid4()
    tenant_b = uuid4()

    async with engine.begin() as conn:
        # Insert both tenants
        for tenant_id in [tenant_a, tenant_b]:
            await _insert_tenant(
                conn, tenant_id, api_key_hash=f"test_hash_{str(tenant_id)[:8]}"
            )

    yield (tenant_a, tenant_b)

    # Cleanup (best effort - attribution_events is append-only)
    async with engine.begin() as conn:
        for tenant_id in [tenant_a, tenant_b]:
            # Skip attribution_events (append-only)
            # Dead events cleanup
            try:
                await conn.execute(
                    text("DELETE FROM dead_events WHERE tenant_id = :tid"),
                    {"tid": str(tenant_id)},
                )
            except Exception:
                pass
            # Skip tenants (FK constraints)
