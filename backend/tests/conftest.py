"""
Pytest fixtures for B0.4.3 tests.

Provides tenant creation/cleanup fixtures to satisfy FK constraints.
"""
import os
import sys
import hashlib
import traceback
from uuid import uuid4

import pytest
from sqlalchemy import text

os.environ["TESTING"] = "1"

# B0.5.3.3 Gate B: Install forensic instrumentation BEFORE any other imports
# This must be installed BEFORE psycopg2 is imported to capture first connection
if os.getenv("CI") == "true":
    class Psycopg2ImportHook:
        def find_module(self, fullname, path=None):
            if fullname == 'psycopg2':
                return self
            return None

        def load_module(self, fullname):
            if fullname in sys.modules:
                return sys.modules[fullname]

            # Import psycopg2 normally
            import importlib
            module = importlib.import_module(fullname)

            # Install monitor immediately after import
            original_connect = module.connect
            first_call_logged = [False]

            def instrumented_connect(*args, **kwargs):
                if not first_call_logged[0]:
                    first_call_logged[0] = True

                    # Extract DSN
                    dsn = None
                    if args:
                        dsn = args[0] if isinstance(args[0], str) else None
                    if not dsn and 'dsn' in kwargs:
                        dsn = kwargs['dsn']

                    # Log stack trace
                    print("\n" + "="*80, flush=True)
                    print("[GATE B FORENSICS] First psycopg2.connect() call detected!", flush=True)
                    print("="*80, flush=True)

                    if dsn:
                        if '://' in dsn and '@' in dsn:
                            try:
                                creds_part = dsn.split('://')[1].split('@')[0]
                                if ':' in creds_part:
                                    user, password = creds_part.split(':', 1)
                                    pass_hash = hashlib.sha256(password.encode()).hexdigest()[:8]
                                    redacted_dsn = dsn.replace(f':{password}@', ':***@')
                                    print(f"DSN: {redacted_dsn}", flush=True)
                                    print(f"User: {user}", flush=True)
                                    print(f"Password SHA256 prefix: {pass_hash}", flush=True)
                            except Exception as e:
                                print(f"Could not parse DSN: {e}", flush=True)
                                print(f"DSN (raw): {dsn[:50]}...", flush=True)
                    else:
                        print("DSN: <not provided as string>", flush=True)

                    print("\nStack trace at first psycopg2.connect() call:", flush=True)
                    print("-" * 80, flush=True)
                    for line in traceback.format_stack()[:-1]:
                        print(line.rstrip(), flush=True)
                    print("=" * 80, flush=True)
                    print("", flush=True)

                return original_connect(*args, **kwargs)

            module.connect = instrumented_connect
            print("[GATE B] psycopg2.connect monitor installed via import hook", flush=True)
            return module

    sys.meta_path.insert(0, Psycopg2ImportHook())
    print("[GATE B] Import hook installed to monitor psycopg2.connect", flush=True)

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
    if "neon.tech" in os.environ["DATABASE_URL"]:
        raise RuntimeError(
            f"[B0.5.3.3 Gate C] CI DSN MUST be localhost; "
            f"resolved={os.environ['DATABASE_URL'].split('@')[1].split('/')[0]}"
        )

    # Diagnostic logging for CI DSN transparency
    dsn = os.environ["DATABASE_URL"]
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
        # Local dev default (should be overridden by .env or explicit export)
        os.environ["DATABASE_URL"] = "postgresql://app_user:Sk3ld1r_App_Pr0d_2025!@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
        print("[B0.5.3.3 Gate C] Local dev: Using Neon DSN fallback (override with DATABASE_URL env var)")

from app.db.session import engine

# B0.5.3.3 Gate C: Trigger Celery configuration AFTER DATABASE_URL validation
# This ensures settings is imported with validated credentials
from app.celery_app import _ensure_celery_configured
_ensure_celery_configured()


@pytest.fixture(scope="function")
async def test_tenant():
    """
    Create a test tenant record and clean up after test.

    Returns tenant_id UUID that satisfies FK constraints.
    """
    tenant_id = uuid4()
    api_key_hash = "test_hash_" + str(tenant_id)[:8]

    async with engine.begin() as conn:
        # Insert tenant record (id is the PK, not tenant_id)
        await conn.execute(
            text("""
                INSERT INTO tenants (id, api_key_hash, name, notification_email, created_at, updated_at)
                VALUES (:id, :api_key_hash, :name, :email, NOW(), NOW())
            """),
            {
                "id": str(tenant_id),
                "api_key_hash": api_key_hash,
                "name": f"Test Tenant {str(tenant_id)[:8]}",
                "email": f"test_{str(tenant_id)[:8]}@test.local",
            },
        )

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
            await conn.execute(
                text("""
                    INSERT INTO tenants (id, api_key_hash, name, notification_email, created_at, updated_at)
                    VALUES (:id, :api_key_hash, :name, :email, NOW(), NOW())
                """),
                {
                    "id": str(tenant_id),
                    "api_key_hash": f"test_hash_{str(tenant_id)[:8]}",
                    "name": f"Test Tenant {str(tenant_id)[:8]}",
                    "email": f"test_{str(tenant_id)[:8]}@test.local",
                },
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
