"""
Application configuration management for Skeldir backend.

This module centralizes environment-driven configuration using Pydantic
BaseSettings to keep deployment configuration deterministic and validated.
"""

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


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

    model_config = SettingsConfigDict(
        env_file=".env",
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


settings = Settings()
