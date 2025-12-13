"""
B0.5.2 Queue Topology & Worker DLQ Validation Tests

Tests empirically validate:
1. Explicit queue topology configuration
2. Task routing to correct queues
3. Worker DLQ capture for failed tasks
4. DLQ schema alignment with B0.4 patterns
"""

import os
import sys
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text

# Set env before importing app modules
DEFAULT_ASYNC_DSN = os.environ.get("TEST_ASYNC_DSN", "postgresql+asyncpg://skeldir:skeldir_ci_validation@localhost:5432/skeldir_validation")
os.environ.setdefault("DATABASE_URL", DEFAULT_ASYNC_DSN)

from app.celery_app import celery_app
from app.tasks.housekeeping import ping
from app.tasks.maintenance import refresh_all_materialized_views_task
from app.tasks.llm import llm_routing_worker
from app.db.session import engine


class TestQueueTopology:
    """Test explicit queue topology (B0.5.2 Criterion #1)."""

    def test_explicit_queues_defined(self):
        """Validate explicit queue declarations exist."""
        queues = celery_app.conf.task_queues
        assert queues is not None, "task_queues must be explicitly defined"
        assert len(queues) >= 3, "At least 3 queues (housekeeping, maintenance, llm) must exist"

        queue_names = {q.name for q in queues}
        assert "housekeeping" in queue_names
        assert "maintenance" in queue_names
        assert "llm" in queue_names

    def test_task_routing_rules_defined(self):
        """Validate task routing rules map tasks to queues."""
        routes = celery_app.conf.task_routes
        assert routes is not None, "task_routes must be explicitly defined"

        # Verify routing patterns
        assert "app.tasks.housekeeping.*" in routes
        assert "app.tasks.maintenance.*" in routes
        assert "app.tasks.llm.*" in routes

        # Verify queue assignments
        assert routes["app.tasks.housekeeping.*"]["queue"] == "housekeeping"
        assert routes["app.tasks.maintenance.*"]["queue"] == "maintenance"
        assert routes["app.tasks.llm.*"]["queue"] == "llm"

    def test_task_names_stable(self):
        """Validate task names remain stable (prevent accidental renames)."""
        registered_tasks = set(celery_app.tasks.keys())

        # B0.5.1 baseline tasks
        expected_tasks = {
            "app.tasks.housekeeping.ping",
            "app.tasks.maintenance.refresh_all_materialized_views",
            "app.tasks.maintenance.scan_for_pii_contamination",
            "app.tasks.maintenance.enforce_data_retention",
            "app.tasks.llm.route",
            "app.tasks.llm.explanation",
            "app.tasks.llm.investigation",
            "app.tasks.llm.budget_optimization",
        }

        for task_name in expected_tasks:
            assert task_name in registered_tasks, f"Expected task {task_name} not registered"

    def test_queue_routing_deterministic(self):
        """Validate tasks route to expected queues deterministically."""
        # Get routing info for sample tasks
        housekeeping_route = celery_app.tasks["app.tasks.housekeeping.ping"].routing_key
        maintenance_route = celery_app.tasks["app.tasks.maintenance.refresh_all_materialized_views"].routing_key
        llm_route = celery_app.tasks["app.tasks.llm.route"].routing_key

        # Verify routing keys align with queue topology
        # Note: routing_key may be None if not explicitly set on task decorator,
        # but task_routes config will override at runtime
        routes = celery_app.conf.task_routes

        assert routes["app.tasks.housekeeping.*"]["routing_key"] == "housekeeping.task"
        assert routes["app.tasks.maintenance.*"]["routing_key"] == "maintenance.task"
        assert routes["app.tasks.llm.*"]["routing_key"] == "llm.task"


class TestWorkerDLQ:
    """Test worker-level DLQ schema and capture (B0.5.2 Criterion #2)."""

    @pytest.mark.asyncio
    async def test_dlq_table_exists(self):
        """Validate celery_task_failures table exists with correct schema."""
        async with engine.begin() as conn:
            # Check table existence
            result = await conn.execute(
                text("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'celery_task_failures'
                """)
            )
            tables = [row[0] for row in result.fetchall()]
            assert "celery_task_failures" in tables, "celery_task_failures table must exist"

            # Check key columns exist
            result = await conn.execute(
                text("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = 'celery_task_failures'
                    ORDER BY column_name
                """)
            )
            columns = {row[0]: row[1] for row in result.fetchall()}

            # Verify B0.4 DLQ pattern columns
            assert "id" in columns
            assert "task_id" in columns
            assert "task_name" in columns
            assert "error_type" in columns
            assert "exception_class" in columns
            assert "error_message" in columns
            assert "traceback" in columns
            assert "retry_count" in columns
            assert "status" in columns
            assert "failed_at" in columns

            # Verify Celery-specific columns
            assert "queue" in columns
            assert "worker" in columns
            assert "task_args" in columns
            assert "task_kwargs" in columns

            # Verify tenant context column
            assert "tenant_id" in columns

    @pytest.mark.asyncio
    async def test_dlq_privileges_granted(self):
        """Validate app_user has CRUD privileges on celery_task_failures."""
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT privilege_type
                    FROM information_schema.role_table_grants
                    WHERE table_name = 'celery_task_failures'
                    AND grantee = 'app_user'
                    ORDER BY privilege_type
                """)
            )
            privileges = {row[0] for row in result.fetchall()}

            # Verify full CRUD
            assert "SELECT" in privileges
            assert "INSERT" in privileges
            assert "UPDATE" in privileges
            assert "DELETE" in privileges

    @pytest.mark.asyncio
    async def test_task_failure_captured_to_dlq(self):
        """Validate failed tasks are persisted to celery_task_failures."""
        # Run task in eager mode to test DLQ capture
        celery_app.conf.task_always_eager = True

        try:
            # Trigger a task failure
            with pytest.raises(ValueError):
                ping.delay(fail=True).get(propagate=True)

            # Query DLQ for captured failure
            async with engine.begin() as conn:
                result = await conn.execute(
                    text("""
                        SELECT task_name, exception_class, error_message, status
                        FROM celery_task_failures
                        WHERE task_name = 'app.tasks.housekeeping.ping'
                        ORDER BY failed_at DESC
                        LIMIT 1
                    """)
                )
                row = result.fetchone()

            # Verify failure captured
            assert row is not None, "Failed task should be captured in DLQ"
            assert row[0] == "app.tasks.housekeeping.ping"
            assert row[1] == "ValueError"
            assert "ping failure requested" in row[2]
            assert row[3] == "pending"

        finally:
            celery_app.conf.task_always_eager = False

            # Cleanup: Delete test DLQ entry
            async with engine.begin() as conn:
                await conn.execute(
                    text("""
                        DELETE FROM celery_task_failures
                        WHERE task_name = 'app.tasks.housekeeping.ping'
                        AND exception_class = 'ValueError'
                    """)
                )

    @pytest.mark.asyncio
    async def test_dlq_rls_policy_exists(self):
        """Validate RLS policy exists for tenant isolation."""
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT policyname, tablename
                    FROM pg_policies
                    WHERE tablename = 'celery_task_failures'
                    AND policyname = 'tenant_isolation_policy'
                """)
            )
            policies = result.fetchall()

            assert len(policies) > 0, "tenant_isolation_policy must exist on celery_task_failures"


class TestObservabilityOperability:
    """Test observability endpoints operational (B0.5.2 Criterion #3)."""

    def test_monitoring_server_configured(self):
        """Validate monitoring server configuration."""
        from app.core.config import settings

        # Verify config values
        assert settings.CELERY_METRICS_PORT is not None
        assert settings.CELERY_METRICS_ADDR is not None

        # Default or CI-overridden port
        assert settings.CELERY_METRICS_PORT in (9540, 9546)

    # Note: Actual HTTP endpoint tests exist in test_b051_celery_foundation.py
    # and CI workflow now captures curl artifacts for empirical evidence
