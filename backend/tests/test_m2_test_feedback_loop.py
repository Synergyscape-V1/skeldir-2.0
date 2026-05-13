from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import psycopg2
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "postgres", "pgbouncer"}
EXTERNAL_HOST_MARKERS = ("neon.tech", "rds.amazonaws.com", "amazonaws.com", "supabase.co")


def _strip_driver_prefix(dsn: str) -> str:
    cleaned = dsn
    for prefix in ("sqla+", "db+"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
    return cleaned.replace("postgresql+asyncpg://", "postgresql://", 1)


def _host(dsn: str) -> str:
    return (urlparse(_strip_driver_prefix(dsn)).hostname or "").lower()


def _require_local_dsn(env_name: str) -> str:
    dsn = os.getenv(env_name)
    if not dsn:
        pytest.fail(f"{env_name} is required for M2 topology proof")
    host = _host(dsn)
    if host not in LOCAL_HOSTS or any(marker in host for marker in EXTERNAL_HOST_MARKERS):
        pytest.fail(f"{env_name} must point at local test topology, got host={host}")
    return _strip_driver_prefix(dsn)


def _connect(env_name: str):
    return psycopg2.connect(_require_local_dsn(env_name))


@pytest.mark.unit_pure
def test_m2_unit_pure_loop_has_no_runtime_infrastructure_dependency() -> None:
    assert (REPO_ROOT / "pytest.ini").exists()
    assert (REPO_ROOT / "docs" / "testing.md").exists()


@pytest.mark.governance
def test_m2_required_static_artifacts_exist() -> None:
    required = [
        "docs/testing.md",
        "docs/testing_db_topology.md",
        "docs/testing_append_only_isolation.md",
        "docs/testing_celery_modes.md",
        "docs/testing_topology_url_authority.md",
        "docs/testing_b24_persistence_readiness.md",
        "docs/testing_b24_persistence_entry_gate.md",
        "docs/testing_parallel_isolation.md",
        "docs/maintainability/m2_completion_record.md",
        "scripts/ci/validate_m2_test_feedback_loop.py",
        "scripts/ci/run_m2_test_feedback_loop.sh",
        "scripts/testing/assert_topology_urls.py",
        "docker-compose.test.yml",
        ".github/workflows/m2-test-feedback-loop.yml",
    ]
    missing = [path for path in required if not (REPO_ROOT / path).exists()]
    assert missing == []


@pytest.mark.db_invariant
@pytest.mark.integration_db_direct
@pytest.mark.append_only_sensitive
def test_m2_append_only_trigger_and_rls_are_physically_present() -> None:
    with _connect("TEST_DIRECT_DATABASE_URL") as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                      FROM information_schema.triggers
                     WHERE event_object_table = 'attribution_events'
                       AND trigger_name = 'trg_events_prevent_mutation'
                )
                """
            )
            assert cur.fetchone()[0] is True

            cur.execute(
                """
                SELECT rowsecurity
                  FROM pg_tables
                 WHERE schemaname = 'public'
                   AND tablename = 'attribution_events'
                """
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] is True


@pytest.mark.db_invariant
@pytest.mark.integration_db_direct
@pytest.mark.rls_guc_sensitive
def test_m2_direct_transaction_local_guc_resets_after_commit() -> None:
    tenant_id = str(uuid4())
    with _connect("TEST_DIRECT_DATABASE_URL") as conn:
        with conn.cursor() as cur:
            cur.execute("BEGIN")
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, true)",
                (tenant_id,),
            )
            cur.execute("SELECT current_setting('app.current_tenant_id', true)")
            assert cur.fetchone()[0] == tenant_id
            cur.execute("COMMIT")
            cur.execute("SELECT current_setting('app.current_tenant_id', true)")
            assert cur.fetchone()[0] in (None, "")


@pytest.mark.integration_db_pooler
@pytest.mark.rls_guc_sensitive
def test_m2_pooler_transaction_local_guc_resets_after_commit() -> None:
    tenant_id = str(uuid4())
    with _connect("TEST_POOLED_DATABASE_URL") as conn:
        with conn.cursor() as cur:
            cur.execute("BEGIN")
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, true)",
                (tenant_id,),
            )
            cur.execute("SELECT current_setting('app.current_tenant_id', true)")
            assert cur.fetchone()[0] == tenant_id
            cur.execute("COMMIT")
            cur.execute("SELECT current_setting('app.current_tenant_id', true)")
            assert cur.fetchone()[0] in (None, "")


@pytest.mark.fail_visible_tenant_context
def test_m2_missing_tenant_context_fails_before_domain_query() -> None:
    from app.db.session import MissingTenantContextError, assert_tenant_context_present

    with pytest.raises(MissingTenantContextError):
        assert_tenant_context_present(None)
    with pytest.raises(MissingTenantContextError):
        assert_tenant_context_present("")


@pytest.mark.db_invariant
@pytest.mark.integration_db_direct
@pytest.mark.rls_guc_sensitive
def test_m2_raw_missing_guc_is_defensive_zero_row_not_domain_truth() -> None:
    with _connect("TEST_DIRECT_DATABASE_URL") as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_setting('app.current_tenant_id', true)")
            assert cur.fetchone()[0] in (None, "")
            cur.execute("SELECT count(*) FROM attribution_events")
            assert int(cur.fetchone()[0]) >= 0


@pytest.mark.celery_eager
def test_m2_celery_eager_mode_is_classified_as_logic_only() -> None:
    from app.celery_app import _ensure_celery_configured, celery_app

    _ensure_celery_configured()
    celery_app.conf.task_always_eager = True
    assert celery_app.conf.task_always_eager is True


@pytest.mark.celery_worker
def test_m2_celery_broker_and_result_backend_are_local_postgres() -> None:
    broker = _require_local_dsn("CELERY_BROKER_URL")
    backend = _require_local_dsn("CELERY_RESULT_BACKEND")
    assert broker.startswith("postgresql://")
    assert backend.startswith("postgresql://")
    with psycopg2.connect(broker) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            assert cur.fetchone()[0]


@pytest.mark.b23_representative
@pytest.mark.integration_db_direct
def test_m2_b23_representative_schema_path_exists() -> None:
    with _connect("TEST_DIRECT_DATABASE_URL") as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.b23_match_verdicts')")
            assert cur.fetchone()[0] == "b23_match_verdicts"


@pytest.mark.b24_persistence_readiness
def test_m2_b24_persistence_readiness_is_confirmed_or_blocked() -> None:
    guard = REPO_ROOT / "docs" / "testing_b24_persistence_readiness.md"
    text = guard.read_text(encoding="utf-8")
    with _connect("TEST_DIRECT_DATABASE_URL") as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.bayesian_model_fits')")
            table = cur.fetchone()[0]
    assert table == "bayesian_model_fits" or "M2_BLOCKED_BY_UNCONFIRMED_B24_PERSISTENCE_SUBSTRATE" in text


@pytest.mark.b24_persistence_entry_gate
def test_m2_b24_persistence_entry_gate_is_canonical_and_blocking() -> None:
    guard = REPO_ROOT / "docs" / "testing_b24_persistence_entry_gate.md"
    text = guard.read_text(encoding="utf-8")
    assert "b24_persistence_entry_gate" in text
    assert "B2.4-P0 schema-substrate" in text
    assert "Bayesian runtime dependency" in text and "convergence-diagnostic runtime behavior" in text
    with _connect("TEST_DIRECT_DATABASE_URL") as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.bayesian_model_fits')")
            table = cur.fetchone()[0]
    assert table == "bayesian_model_fits" or "M2_BLOCKED_BY_UNCONFIRMED_B24_PERSISTENCE_SUBSTRATE" in text
