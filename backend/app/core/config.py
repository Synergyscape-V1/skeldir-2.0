"""
Application configuration management for Skeldir backend.

This module centralizes environment-driven configuration using Pydantic
BaseSettings to keep deployment configuration deterministic and validated.
"""

import os
from typing import Optional

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load local .env without overriding explicit environment variables.
# Skip in CI environments (CI=true) to prevent local dev credentials from interfering.
if os.getenv("CI") != "true":
    load_dotenv(dotenv_path=".env", override=False)


class Settings(BaseSettings):
    """
    Typed application settings loaded from environment variables.

    Environment is read from `.env` with case-sensitive keys to align with
    deployment expectations. Validation guards against misconfiguration that
    could bypass RLS or break database connectivity.
    """

    # Database
    DATABASE_URL: PostgresDsn = Field(..., description="Async PostgreSQL DSN")
    DATABASE_POOL_SIZE: int = Field(10, description="Base connection pool size")
    DATABASE_MAX_OVERFLOW: int = Field(
        20, description="Additional connections allowed beyond pool size"
    )

    # Tenant Authentication
    TENANT_API_KEY_HEADER: str = Field(
        "X-Skeldir-Tenant-Key", description="Header carrying tenant API key"
    )

    # Application
    ENVIRONMENT: str = Field("development", description="Deployment environment")
    LOG_LEVEL: str = Field("INFO", description="Application log level")

    # Ingestion
    IDEMPOTENCY_CACHE_TTL: int = Field(
        86400, description="Idempotency cache TTL in seconds (24 hours)"
    )

    # Celery (Postgres-only broker/result backend)
    CELERY_BROKER_URL: Optional[str] = Field(
        None,
        description="Celery broker URL (sqla+postgresql://...). Defaults to DATABASE_URL derived sync DSN when unset.",
    )
    CELERY_RESULT_BACKEND: Optional[str] = Field(
        None,
        description="Celery result backend URL (db+postgresql://...). Defaults to DATABASE_URL derived sync DSN when unset.",
    )
    CELERY_METRICS_PORT: int = Field(9540, description="Port for Celery worker metrics/health HTTP server")
    CELERY_METRICS_ADDR: str = Field("0.0.0.0", description="Bind address for Celery worker metrics/health server")
    CELERY_TASK_ACKS_LATE: bool = Field(
        True,
        description="Acknowledge tasks only after execution completes (crash-safe, required for idempotent side effects).",
    )
    CELERY_TASK_REJECT_ON_WORKER_LOST: bool = Field(
        True,
        description="Requeue tasks when a worker process is lost (required for crash-after-write tests).",
    )
    CELERY_TASK_ACKS_ON_FAILURE_OR_TIMEOUT: bool = Field(
        True,
        description="Acknowledge tasks even when they fail/time out to prevent infinite redelivery loops.",
    )
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = Field(
        1,
        description="Prefetch multiplier for worker (1 minimizes starvation and improves crash determinism).",
    )
    CELERY_BROKER_ENGINE_POOL_SIZE: int = Field(
        5,
        description="SQLAlchemy pool_size for sqla+ Postgres broker engine (per process).",
    )
    CELERY_BROKER_ENGINE_MAX_OVERFLOW: int = Field(
        0,
        description="SQLAlchemy max_overflow for sqla+ Postgres broker engine (per process).",
    )
    CELERY_RESULT_BACKEND_ENGINE_POOL_SIZE: int = Field(
        5,
        description="SQLAlchemy pool_size for db+ Postgres result backend engine (per process).",
    )
    CELERY_RESULT_BACKEND_ENGINE_MAX_OVERFLOW: int = Field(
        0,
        description="SQLAlchemy max_overflow for db+ Postgres result backend engine (per process).",
    )
    CELERY_BROKER_VISIBILITY_TIMEOUT_S: int = Field(
        3600,
        description="Visibility timeout (seconds) used by the worker to requeue stuck kombu messages after worker loss; must exceed max task runtime in production.",
    )
    CELERY_BROKER_RECOVERY_SWEEP_INTERVAL_S: float = Field(
        1.0,
        validation_alias=AliasChoices(
            "CELERY_BROKER_RECOVERY_SWEEP_INTERVAL_S",
            "CELERY_BROKER_POLLING_INTERVAL_S",
        ),
        description="Interval (seconds) for worker-side kombu message visibility recovery sweeps (lower improves redelivery latency at higher DB load).",
    )

    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: PostgresDsn) -> PostgresDsn:
        """
        Enforce async PostgreSQL driver usage to match SQLAlchemy engine config.
        """
        if value.scheme not in {"postgresql+asyncpg", "postgresql"}:
            raise ValueError("DATABASE_URL must use postgresql+asyncpg scheme")
        return value

    @field_validator("DATABASE_POOL_SIZE", "DATABASE_MAX_OVERFLOW")
    @classmethod
    def validate_pool_sizes(cls, value: int, info) -> int:
        """
        Ensure pool sizing values are non-negative integers.
        """
        if value < 0:
            raise ValueError(f"{info.field_name} must be >= 0")
        return value

    @field_validator("TENANT_API_KEY_HEADER")
    @classmethod
    def validate_api_key_header(cls, value: str) -> str:
        """
        Prevent accidental empty header configuration.
        """
        if not value or not value.strip():
            raise ValueError("TENANT_API_KEY_HEADER cannot be empty")
        return value.strip()

    @field_validator("IDEMPOTENCY_CACHE_TTL")
    @classmethod
    def validate_idempotency_ttl(cls, value: int) -> int:
        """
        TTL must be positive to avoid unbounded caching behavior.
        """
        if value <= 0:
            raise ValueError("IDEMPOTENCY_CACHE_TTL must be greater than zero")
        return value

    @field_validator("CELERY_WORKER_PREFETCH_MULTIPLIER")
    @classmethod
    def validate_celery_prefetch_multiplier(cls, value: int) -> int:
        if value < 1:
            raise ValueError("CELERY_WORKER_PREFETCH_MULTIPLIER must be >= 1")
        return value

    @field_validator(
        "CELERY_BROKER_ENGINE_POOL_SIZE",
        "CELERY_RESULT_BACKEND_ENGINE_POOL_SIZE",
    )
    @classmethod
    def validate_celery_engine_pool_size(cls, value: int, info) -> int:
        if value < 1:
            raise ValueError(f"{info.field_name} must be >= 1")
        return value

    @field_validator(
        "CELERY_BROKER_ENGINE_MAX_OVERFLOW",
        "CELERY_RESULT_BACKEND_ENGINE_MAX_OVERFLOW",
    )
    @classmethod
    def validate_celery_engine_max_overflow(cls, value: int, info) -> int:
        if value < 0:
            raise ValueError(f"{info.field_name} must be >= 0")
        return value

    @field_validator("CELERY_BROKER_VISIBILITY_TIMEOUT_S")
    @classmethod
    def validate_celery_visibility_timeout(cls, value: int) -> int:
        if value < 1:
            raise ValueError("CELERY_BROKER_VISIBILITY_TIMEOUT_S must be >= 1")
        return value

    @field_validator("CELERY_BROKER_RECOVERY_SWEEP_INTERVAL_S")
    @classmethod
    def validate_celery_recovery_sweep_interval(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("CELERY_BROKER_RECOVERY_SWEEP_INTERVAL_S must be > 0")
        return value


settings = Settings()
