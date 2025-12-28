"""
Celery application configured for PostgreSQL broker/result backend.

This module centralizes Celery initialization so workers and tests share
the same configuration, logging, and metrics wiring as the FastAPI app.
"""
import logging
import threading
import time
from typing import Optional

from celery import Celery, signals
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

# B0.5.3.3 Gate C: Defer settings import to prevent premature initialization
# Import settings ONLY when Celery config is actually built, not at module load time
# from app.core.config import settings  # REMOVED - now imported in _get_settings()

from app.observability import metrics
from app.observability.logging_config import configure_logging
from app.observability.worker_monitoring import start_worker_http_server

logger = logging.getLogger(__name__)


def _get_settings():
    """
    B0.5.3.3 Gate C: Lazy settings import to ensure conftest validation runs first.

    By deferring settings import until Celery config build time, we guarantee
    that pytest conftest.py can validate/set DATABASE_URL before settings reads it.
    """
    from app.core.config import settings
    return settings


def _sync_sqlalchemy_url(raw_url: str) -> str:
    """
    Convert async-friendly DATABASE_URL to a sync SQLAlchemy URL suitable for Celery.

    B0.5.3.3 Gate G5 Fix: Manually construct DSN to preserve password.
    str(url) drops password after multiple .set() calls, causing auth failures.
    """
    url = make_url(raw_url)
    # Drop channel_binding for psycopg2 compatibility.
    query = dict(url.query)
    query.pop("channel_binding", None)
    url = url.set(query=query)
    driver = url.drivername
    if driver.startswith("postgresql+"):
        driver = "postgresql"
    url = url.set(drivername=driver)

    # Manually construct DSN to preserve password (str(url) may drop it after .set() calls)
    dsn_parts = [f"{driver}://"]
    if url.username:
        dsn_parts.append(url.username)
        if url.password:
            dsn_parts.append(":")
            dsn_parts.append(url.password)
        dsn_parts.append("@")
    dsn_parts.append(url.host or "localhost")
    if url.port:
        dsn_parts.append(f":{url.port}")
    if url.database:
        dsn_parts.append(f"/{url.database}")
    if query:
        query_str = "&".join(f"{k}={v}" for k, v in query.items())
        dsn_parts.append(f"?{query_str}")

    return "".join(dsn_parts)


def _build_broker_url() -> str:
    """
    Build broker URL using SQLAlchemy transport over Postgres (sqla+postgresql://...).
    Defaults to DATABASE_URL-derived sync DSN when CELERY_BROKER_URL is unset.
    """
    settings = _get_settings()  # B0.5.3.3 Gate C: Lazy settings access
    if settings.CELERY_BROKER_URL:
        return settings.CELERY_BROKER_URL
    base = _sync_sqlalchemy_url(settings.DATABASE_URL.unicode_string())
    return f"sqla+{base}"


def _build_result_backend() -> str:
    """
    Build result backend URL using Celery database backend over Postgres (db+postgresql://...).
    Defaults to DATABASE_URL-derived sync DSN when CELERY_RESULT_BACKEND is unset.
    """
    settings = _get_settings()  # B0.5.3.3 Gate C: Lazy settings access
    if settings.CELERY_RESULT_BACKEND:
        return settings.CELERY_RESULT_BACKEND
    base = _sync_sqlalchemy_url(settings.DATABASE_URL.unicode_string())
    return f"db+{base}"


# B0.5.3.3 Gate C: Create Celery app but defer configuration until first use
# This prevents premature settings import at module load time
celery_app = Celery("skeldir_backend")
_celery_configured = False
_kombu_visibility_recovery_started = False


def _ensure_celery_configured():
    """
    B0.5.3.3 Gate C: Lazy Celery configuration to prevent premature DB connections.

    By deferring broker/backend configuration until first actual use, we ensure
    pytest conftest validation runs before settings is imported and DB connections
    are attempted.

    This function is idempotent - safe to call multiple times.
    """
    global _celery_configured
    if _celery_configured:
        return

    from kombu import Queue
    settings = _get_settings()  # Lazy settings access

    broker_url = _build_broker_url()
    broker_transport_options: dict[str, object] = {
        "pool_recycle": 300,
        "pool_size": settings.CELERY_BROKER_ENGINE_POOL_SIZE,
        "max_overflow": settings.CELERY_BROKER_ENGINE_MAX_OVERFLOW,
    }

    celery_app.conf.update(
        broker_url=broker_url,
        result_backend=_build_result_backend(),
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        enable_utc=True,
        timezone="UTC",
        task_track_started=True,
        broker_transport_options=broker_transport_options,
        database_engine_options={
            "pool_recycle": 300,
            "pool_size": settings.CELERY_RESULT_BACKEND_ENGINE_POOL_SIZE,
        },
        worker_send_task_events=True,
        worker_hijack_root_logger=False,
        # R4: crash-safe + starvation-resistant defaults (override via env via Settings)
        task_acks_late=settings.CELERY_TASK_ACKS_LATE,
        task_reject_on_worker_lost=settings.CELERY_TASK_REJECT_ON_WORKER_LOST,
        task_acks_on_failure_or_timeout=settings.CELERY_TASK_ACKS_ON_FAILURE_OR_TIMEOUT,
        worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
        include=[
            "app.tasks.housekeeping",
            "app.tasks.maintenance",
            "app.tasks.llm",
            "app.tasks.attribution",
            "app.tasks.r4_failure_semantics",
        ],
        # B0.5.2: Fixed queue topology
        # B0.5.3.1: Added attribution queue for deterministic routing
        task_queues=[
            Queue('housekeeping', routing_key='housekeeping.#'),
            Queue('maintenance', routing_key='maintenance.#'),
            Queue('llm', routing_key='llm.#'),
            Queue('attribution', routing_key='attribution.#'),
        ],
        task_routes={
            'app.tasks.housekeeping.*': {'queue': 'housekeeping', 'routing_key': 'housekeeping.task'},
            'app.tasks.maintenance.*': {'queue': 'maintenance', 'routing_key': 'maintenance.task'},
            'app.tasks.llm.*': {'queue': 'llm', 'routing_key': 'llm.task'},
            'app.tasks.attribution.*': {'queue': 'attribution', 'routing_key': 'attribution.task'},
            'app.tasks.r4_failure_semantics.*': {'queue': 'housekeeping', 'routing_key': 'housekeeping.task'},
        },
        task_default_queue='housekeeping',
        task_default_exchange='tasks',
        task_default_routing_key='housekeeping.task',
    )

    # B0.5.4.0: Load Beat schedule (closes G11 drift - beat not deployed)
    from app.tasks.beat_schedule import BEAT_SCHEDULE
    celery_app.conf.beat_schedule = BEAT_SCHEDULE

    logger.info(
        "celery_app_configured",
        extra={
            "broker_url": celery_app.conf.broker_url,
            "result_backend": celery_app.conf.result_backend,
            "broker_transport_options": celery_app.conf.broker_transport_options,
            "queues": [q.name for q in celery_app.conf.task_queues],
            "beat_schedule_loaded": bool(celery_app.conf.beat_schedule),
            "scheduled_tasks": list(celery_app.conf.beat_schedule.keys()) if celery_app.conf.beat_schedule else [],
            "app_name": celery_app.main,
        },
    )
    _celery_configured = True


@signals.worker_process_init.connect
def _configure_worker_logging(**kwargs):
    """
    Ensure structured logging is configured inside each worker process.
    """
    settings = _get_settings()  # B0.5.3.3 Gate C: Lazy settings access
    configure_logging(settings.LOG_LEVEL)
    start_worker_http_server(
        celery_app,
        host=settings.CELERY_METRICS_ADDR,
        port=settings.CELERY_METRICS_PORT,
    )
    logger.info(
        "celery_worker_logging_configured",
        extra={"metrics_addr": settings.CELERY_METRICS_ADDR, "metrics_port": settings.CELERY_METRICS_PORT},
    )


def _recover_invisible_kombu_messages(*, engine, visibility_timeout_s: int, task_name_filter: str | None) -> int:
    sql = """
        UPDATE public.kombu_message
        SET visible = true
        WHERE visible = false
          AND "timestamp" IS NOT NULL
          AND "timestamp" < (now() - make_interval(secs => :visibility_timeout_s))
    """
    params: dict[str, object] = {"visibility_timeout_s": int(visibility_timeout_s)}
    if task_name_filter:
        sql += "\n          AND payload LIKE :task_name_filter"
        params["task_name_filter"] = f"%{task_name_filter}%"

        # R4: Prevent infinite redelivery loops for crash probes once redelivery has been observed.
        # The Kombu SQLAlchemy transport does not delete messages on ack; without this guard, the
        # recovery sweep will keep re-queueing the same message forever.
        if "r4_failure_semantics.crash_after_write_pre_ack" in task_name_filter:
            sql += """
              AND NOT EXISTS (
                SELECT 1
                FROM public.r4_recovery_exclusions e
                WHERE e.scenario = 'S2_CrashAfterWritePreAck'
                  AND e.task_id = COALESCE(
                    (public.kombu_message.payload::jsonb -> 'headers' ->> 'id'),
                    (public.kombu_message.payload::jsonb -> 'headers' ->> 'task_id'),
                    (public.kombu_message.payload::jsonb ->> 'id')
                  )
              )
            """

    with engine.begin() as conn:
        res = conn.execute(text(sql), params)
        return int(res.rowcount or 0)


def _start_kombu_visibility_recovery_thread() -> None:
    """
    Kombu SQLAlchemy transport marks reserved messages as visible=false, with no built-in redelivery.

    This worker-side recovery loop re-queues "stuck" invisible messages by restoring visible=true once
    they are older than the configured visibility timeout. This restores at-least-once semantics
    after worker loss, and is safe when paired with idempotent side effects + task time limits.
    """
    global _kombu_visibility_recovery_started
    if _kombu_visibility_recovery_started:
        return

    settings = _get_settings()
    if not str(celery_app.conf.broker_url or "").startswith("sqla+"):
        return

    dsn = _sync_sqlalchemy_url(settings.DATABASE_URL.unicode_string())
    visibility_timeout_s = int(settings.CELERY_BROKER_VISIBILITY_TIMEOUT_S)
    sweep_interval_s = float(settings.CELERY_BROKER_RECOVERY_SWEEP_INTERVAL_S)
    task_name_filter = settings.CELERY_BROKER_RECOVERY_TASK_NAME_FILTER

    recovery_engine = create_engine(
        dsn,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=1,
        max_overflow=0,
    )

    logger.info(
        "celery_kombu_visibility_recovery_started",
        extra={
            "visibility_timeout_s": visibility_timeout_s,
            "sweep_interval_s": sweep_interval_s,
            "task_name_filter": task_name_filter,
        },
    )

    def _loop() -> None:
        while True:
            try:
                recovered = _recover_invisible_kombu_messages(
                    engine=recovery_engine,
                    visibility_timeout_s=visibility_timeout_s,
                    task_name_filter=task_name_filter,
                )
                if recovered:
                    logger.warning(
                        "celery_kombu_visibility_recovered_messages",
                        extra={"recovered": recovered, "visibility_timeout_s": visibility_timeout_s},
                    )
            except Exception:
                logger.exception("celery_kombu_visibility_recovery_failed")
            time.sleep(sweep_interval_s)

    threading.Thread(target=_loop, name="celery-kombu-visibility-recovery", daemon=True).start()
    _kombu_visibility_recovery_started = True


@signals.worker_ready.connect
def _on_worker_ready(**kwargs):
    _ensure_celery_configured()
    _start_kombu_visibility_recovery_thread()


@signals.task_prerun.connect
def _on_task_prerun(task_id, task, **kwargs):
    task.request._started_at = time.perf_counter()
    metrics.celery_task_started_total.labels(task_name=task.name).inc()


@signals.task_postrun.connect
def _on_task_postrun(task_id, task, retval, state, **kwargs):
    started = getattr(task.request, "_started_at", None)
    if started is not None:
        duration = time.perf_counter() - started
        metrics.celery_task_duration_seconds.labels(task_name=task.name).observe(duration)
    if state == "SUCCESS":
        metrics.celery_task_success_total.labels(task_name=task.name).inc()


@signals.task_failure.connect
def _on_task_failure(task_id=None, exception=None, args=None, kwargs=None, einfo=None, **extra):
    # Extract task from extra if available (signal signature variations)
    task = extra.get('sender')
    task_name = task.name if task else "unknown"

    metrics.celery_task_failure_total.labels(task_name=task_name).inc()
    logger.error(
        "celery_task_failed",
        extra={
            "task_name": task_name,
            "task_id": task_id,
            "error": str(exception),
        },
    )

    # B0.5.2: Persist task failure to worker DLQ (G4 remediation: sync psycopg2 path)
    try:
        import os
        import psycopg2
        import psycopg2.extras
        from uuid import UUID, uuid4
        from sqlalchemy.engine.url import make_url

        # B0.5.3.3 Gate C: Lazy settings access in DLQ handler
        settings = _get_settings()

        # G4-AUTH: Build sync DSN with 127.0.0.1 normalization for CI determinism
        # Step 1: Get raw DATABASE_URL from settings
        raw_database_url = settings.DATABASE_URL.unicode_string()

        # G4-AUTH DIAGNOSTIC: Log raw DATABASE_URL (password redacted) BEFORE make_url parsing
        if os.getenv("CI") == "true":
            # Redact password for logging
            if "@" in raw_database_url:
                parts = raw_database_url.split("@")
                prefix = parts[0]
                if ":" in prefix:
                    user_part = prefix.split("://")[1] if "://" in prefix else prefix
                    if ":" in user_part:
                        user = user_part.split(":")[0]
                        redacted_prefix = prefix.split(":")[0] + "://" + user + ":***"
                    else:
                        redacted_prefix = prefix
                else:
                    redacted_prefix = prefix
                redacted_raw = redacted_prefix + "@" + "@".join(parts[1:])
            else:
                redacted_raw = raw_database_url
            logger.info(
                f"[G4-AUTH-RAW] settings.DATABASE_URL.unicode_string() = {redacted_raw}",
                extra={"raw_dsn_redacted": redacted_raw}
            )

        # Step 2: Parse with make_url
        url = make_url(raw_database_url)

        # G4-AUTH DIAGNOSTIC: Check if password survived make_url parsing
        if os.getenv("CI") == "true":
            has_password = url.password is not None and url.password != ""
            logger.info(
                f"[G4-AUTH-PARSED] After make_url: host={url.host} user={url.username} password_present={has_password}",
                extra={"parsed_host": url.host, "parsed_user": url.username, "password_present": has_password}
            )

        # Step 3: Normalize localhost to 127.0.0.1 for IPv4 enforcement
        if url.host == "localhost" and os.getenv("CI") == "true":
            url = url.set(host="127.0.0.1")
        query = dict(url.query)
        query.pop("channel_binding", None)
        url = url.set(query=query)
        if url.drivername.startswith("postgresql+"):
            url = url.set(drivername="postgresql")

        # G4-AUTH FIX: Manually construct DSN to preserve password
        # str(url) may drop password after multiple .set() calls
        dsn_parts = ["postgresql://"]
        if url.username:
            dsn_parts.append(url.username)
            if url.password:
                dsn_parts.append(":")
                dsn_parts.append(url.password)
            dsn_parts.append("@")
        dsn_parts.append(url.host or "localhost")
        if url.port:
            dsn_parts.append(f":{url.port}")
        if url.database:
            dsn_parts.append(f"/{url.database}")
        dsn = "".join(dsn_parts)

        # G4-AUTH DIAGNOSTIC: Log final DSN (password redacted)
        if os.getenv("CI") == "true":
            # Redact password in final DSN
            if "@" in dsn:
                parts = dsn.split("@")
                prefix = parts[0]
                if ":" in prefix:
                    user_part = prefix.split("://")[1] if "://" in prefix else prefix
                    if ":" in user_part:
                        user = user_part.split(":")[0]
                        redacted_prefix = prefix.split(":")[0] + "://" + user + ":***"
                    else:
                        redacted_prefix = prefix
                else:
                    redacted_prefix = prefix
                redacted_dsn = redacted_prefix + "@" + "@".join(parts[1:])
            else:
                redacted_dsn = dsn
            logger.info(
                f"[G4-AUTH-FINAL] Final DSN for psycopg2.connect() = {redacted_dsn}",
                extra={"final_dsn_redacted": redacted_dsn}
            )

        # Extract metadata
        tenant_id = None
        if kwargs and 'tenant_id' in kwargs:
            try:
                tenant_id = UUID(str(kwargs['tenant_id']))
            except (ValueError, TypeError):
                pass

        # Classify error type
        error_type = "unknown"
        if exception:
            exc_name = exception.__class__.__name__
            if exc_name in ("ValueError", "KeyError"):
                error_type = "validation_error"
            elif exc_name in ("IntegrityError", "OperationalError"):
                error_type = "database_error"
            else:
                error_type = "application_error"

        # Get worker info
        queue = None
        worker_name = None
        correlation_id = None
        retry_count = 0
        if task and hasattr(task, 'request'):
            queue = getattr(task.request, 'delivery_info', {}).get('routing_key', None)
            worker_name = getattr(task.request, 'hostname', None)
            correlation_id_val = getattr(task.request, 'correlation_id', None)
            if correlation_id_val:
                try:
                    correlation_id = UUID(str(correlation_id_val))
                except (ValueError, TypeError):
                    pass
            try:
                retry_count = int(getattr(task.request, "retries", 0) or 0)
            except (TypeError, ValueError):
                retry_count = 0
        if correlation_id is None and kwargs and "correlation_id" in kwargs:
            try:
                correlation_id = UUID(str(kwargs["correlation_id"]))
            except (ValueError, TypeError):
                correlation_id = None
        # Correlation must be present for DLQ diagnostics; fall back to task_id when missing.
        if correlation_id is None and task_id:
            try:
                correlation_id = UUID(str(task_id))
            except (ValueError, TypeError):
                correlation_id = None

        # B0.5.3.1: Convert UUIDs to strings for JSON serialization
        def _serialize_for_json(obj):
            """Recursively convert UUIDs to strings for JSON serialization."""
            if isinstance(obj, UUID):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: _serialize_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [_serialize_for_json(item) for item in obj]
            return obj

        # G4-LOOP/G4-JSON: Sync persistence with proper JSONB encoding
        # B0.5.3.1: Write to canonical worker_failed_jobs table
        conn = psycopg2.connect(dsn)
        try:
            cur = conn.cursor()
            # G4-JSON: Use psycopg2.extras.Json for JSONB columns to prevent encoding defects
            # B0.5.3.1: Serialize UUIDs to strings before JSON encoding
            serialized_args = _serialize_for_json(args if args else [])
            serialized_kwargs = _serialize_for_json(kwargs if kwargs else {})

            cur.execute("""
                SELECT set_config('app.execution_context', 'worker', true);
             """)
            if tenant_id:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, true);",
                    (str(tenant_id),),
                )
            if correlation_id:
                cur.execute(
                    "SELECT set_config('app.correlation_id', %s, true);",
                    (str(correlation_id),),
                )

            cur.execute("""
                INSERT INTO worker_failed_jobs (
                    id, task_id, task_name, queue, worker,
                    task_args, task_kwargs, tenant_id,
                    error_type, exception_class, error_message, traceback,
                    retry_count, status, correlation_id, failed_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, CURRENT_TIMESTAMP
                )
            """, (
                str(uuid4()),
                task_id,
                task_name,
                queue,
                worker_name,
                psycopg2.extras.Json(serialized_args),  # G4-JSON: Explicit JSONB encoding with UUID serialization
                psycopg2.extras.Json(serialized_kwargs),  # G4-JSON: Explicit JSONB encoding with UUID serialization
                str(tenant_id) if tenant_id else None,
                error_type,
                exception.__class__.__name__ if exception else "Unknown",
                str(exception)[:500] if exception else "",
                str(einfo)[:2000] if einfo else None,
                retry_count,
                "pending",
                str(correlation_id) if correlation_id else None,
            ))
            conn.commit()

            # G4-AUTH: Confirm successful persistence
            if os.getenv("CI") == "true":
                logger.info(
                    "[G4-AUTH] DB CONNECT OK - DLQ row persisted",
                    extra={"task_id": task_id, "task_name": task_name}
                )
        finally:
            conn.close()

    except Exception as dlq_error:
        # DLQ failure should not crash worker
        logger.error(
            "celery_dlq_persist_failed",
            exc_info=dlq_error,
            extra={"task_id": task_id, "task_name": task_name},
        )


__all__ = ["celery_app", "_build_broker_url", "_build_result_backend", "_ensure_celery_configured"]

# B0.5.3.3 Gate B FIX: Remove module-level task imports to prevent premature psycopg2 import
# Tasks are discovered via `include` config in _ensure_celery_configured() - no need for eager imports
# Module-level imports caused: conftest → celery_app → tasks.housekeeping → psycopg2 → DB connection
# during pytest COLLECTION (before DATABASE_URL validation), causing auth failures with stale .env creds

# Ensure the Celery app is configured whenever this module is imported (worker or test process).
# This remains safe because _ensure_celery_configured() is idempotent and tests set env vars before import.
_ensure_celery_configured()
