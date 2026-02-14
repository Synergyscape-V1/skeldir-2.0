"""
Application configuration management for Skeldir backend.

This module centralizes environment-driven configuration using Pydantic
BaseSettings to keep deployment configuration deterministic and validated.
"""

import os
from typing import Optional

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, PostgresDsn, field_validator, model_validator
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
    DATABASE_POOL_SIZE: int = Field(20, description="Base connection pool size")
    DATABASE_MAX_OVERFLOW: int = Field(
        0, description="Additional connections allowed beyond pool size"
    )
    DATABASE_POOL_TIMEOUT_SECONDS: float = Field(
        5.0,
        description=(
            "Seconds to wait for an available pooled connection before failing fast "
            "at the application layer."
        ),
    )
    DATABASE_POOL_TOTAL_CAP: int = Field(
        30,
        description=(
            "Hard per-process cap for pooled connections (pool_size + max_overflow). "
            "Prevents DB listener swamping under burst."
        ),
    )

    # Tenant Authentication
    TENANT_API_KEY_HEADER: str = Field(
        "X-Skeldir-Tenant-Key", description="Header carrying tenant API key"
    )
    TENANT_SECRETS_CACHE_TTL_SECONDS: int = Field(
        60,
        description="In-memory TTL for tenant webhook secret cache (seconds).",
    )
    TENANT_SECRETS_CACHE_MAX_ENTRIES: int = Field(
        2048,
        description="Maximum entries for tenant webhook secret cache.",
    )
    # JWT Authentication (Phase 1)
    AUTH_JWT_SECRET: Optional[str] = Field(
        None, description="JWT HMAC secret (HS*). Required when JWKS URL is not set."
    )
    AUTH_JWT_ALGORITHM: Optional[str] = Field(
        None, description="JWT signing algorithm (e.g., HS256, RS256)."
    )
    AUTH_JWT_ISSUER: Optional[str] = Field(
        None, description="Expected JWT issuer (iss claim)."
    )
    AUTH_JWT_AUDIENCE: Optional[str] = Field(
        None, description="Expected JWT audience (aud claim)."
    )
    AUTH_JWT_JWKS_URL: Optional[str] = Field(
        None, description="JWKS URL for JWT signature verification."
    )

    # Platform Credentials (Phase 2)
    PLATFORM_TOKEN_ENCRYPTION_KEY: Optional[str] = Field(
        None,
        description="Symmetric key for encrypting platform tokens at rest (pgcrypto).",
    )
    PLATFORM_TOKEN_KEY_ID: Optional[str] = Field(
        None,
        description="Identifier for the active platform token encryption key.",
    )
    PLATFORM_SUPPORTED_PLATFORMS: str = Field(
        "google_ads,meta_ads,tiktok_ads,linkedin_ads,stripe,paypal,shopify,woocommerce",
        description="Comma-separated list of supported platform identifiers.",
    )
    STRIPE_BASE_URL: Optional[str] = Field(
        None,
        description="Override base URL for Stripe API calls (useful for E2E mocks).",
    )

    # Application
    ENVIRONMENT: str = Field("development", description="Deployment environment")
    LOG_LEVEL: str = Field("INFO", description="Application log level")

    # LLM Provider (future enablement)
    LLM_PROVIDER_ENABLED: bool = Field(
        False, description="Enable external LLM provider boundary (requires API key)."
    )
    LLM_PROVIDER_API_KEY: Optional[str] = Field(
        None, description="API key for the configured LLM provider (required if enabled)."
    )
    LLM_PROVIDER_MODEL: str = Field(
        "openai:gpt-4o-mini",
        description="Provider/model route in '<provider>:<model>' format for aisuite dispatch.",
    )
    LLM_COMPLEXITY_POLICY_PATH: str = Field(
        "backend/app/llm/policies/complexity_router_policy.json",
        description="Path to deterministic complexity-routing policy JSON.",
    )
    LLM_PROVIDER_KILL_SWITCH: bool = Field(
        False,
        description="Emergency provider kill-switch. When enabled, all LLM requests are blocked before provider invocation.",
    )
    LLM_MONTHLY_CAP_CENTS: int = Field(
        2500,
        description="Per-user monthly hard cap in cents for reservation gating ($25 default).",
    )
    LLM_HOURLY_SHUTOFF_CENTS: int = Field(
        500,
        description="Per-user hourly emergency shutoff threshold in cents.",
    )
    LLM_PROVIDER_TIMEOUT_MS: int = Field(
        10000,
        description="Hard timeout around provider invocation at choke point.",
    )
    LLM_BREAKER_FAILURE_THRESHOLD: int = Field(
        3,
        description="Consecutive failures required to open the provider breaker.",
    )
    LLM_BREAKER_OPEN_SECONDS: int = Field(
        300,
        description="Breaker open window in seconds before half-open probing.",
    )

    # Ingestion
    IDEMPOTENCY_CACHE_TTL: int = Field(
        86400, description="Idempotency cache TTL in seconds (24 hours)"
    )
    INGESTION_FOLLOWUP_TASKS_ENABLED: bool = Field(
        False,
        description="Enable synchronous scheduling of downstream ingestion follow-up tasks from webhook requests.",
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
    # B0.5.6.1: CELERY_METRICS_PORT and CELERY_METRICS_ADDR removed.
    # B0.5.6.5/B0.5.6.7: Worker task metrics are exposed via the dedicated exporter
    # (app.observability.worker_metrics_exporter), not via API /metrics.
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
    CELERY_TASK_SOFT_TIME_LIMIT_S: int = Field(
        300,
        description="Global soft time limit (seconds) for Celery tasks to allow graceful aborts.",
    )
    CELERY_TASK_TIME_LIMIT_S: int = Field(
        360,
        description="Global hard time limit (seconds) for Celery tasks to force termination.",
    )
    BAYESIAN_TASK_SOFT_TIME_LIMIT_S: int = Field(
        270,
        description="Per-task soft time limit for Bayesian/MCMC worker jobs.",
    )
    BAYESIAN_TASK_TIME_LIMIT_S: int = Field(
        300,
        description="Per-task hard time limit for Bayesian/MCMC worker jobs.",
    )
    CELERY_WORKER_MAX_TASKS_PER_CHILD: int = Field(
        100,
        description="Restart worker child processes after this many tasks to bound leaks.",
    )
    CELERY_WORKER_MAX_MEMORY_PER_CHILD_KB: int = Field(
        250000,
        description="Restart worker child processes after exceeding this memory (KB).",
    )
    CELERY_CHORD_UNLOCK_MAX_RETRIES: int = Field(
        5,
        description="Maximum retries for Celery chord unlock orchestration task.",
    )
    CELERY_CHORD_UNLOCK_RETRY_DELAY_S: int = Field(
        2,
        description="Base retry delay (seconds) for Celery chord unlock retries.",
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
    CELERY_BROKER_RECOVERY_TASK_NAME_FILTER: Optional[str] = Field(
        None,
        description="If set, kombu visibility recovery only requeues messages whose payload contains this substring (e.g., a task name).",
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
        if info.field_name == "DATABASE_POOL_SIZE" and value < 1:
            raise ValueError("DATABASE_POOL_SIZE must be >= 1")
        return value

    @field_validator("DATABASE_POOL_TIMEOUT_SECONDS")
    @classmethod
    def validate_pool_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("DATABASE_POOL_TIMEOUT_SECONDS must be > 0")
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

    @field_validator("TENANT_SECRETS_CACHE_TTL_SECONDS", "TENANT_SECRETS_CACHE_MAX_ENTRIES")
    @classmethod
    def validate_tenant_secret_cache_settings(cls, value: int, info) -> int:
        if value < 1:
            raise ValueError(f"{info.field_name} must be >= 1")
        return value

    @field_validator(
        "AUTH_JWT_SECRET",
        "AUTH_JWT_ALGORITHM",
        "AUTH_JWT_ISSUER",
        "AUTH_JWT_AUDIENCE",
        "AUTH_JWT_JWKS_URL",
        "PLATFORM_TOKEN_ENCRYPTION_KEY",
        "PLATFORM_TOKEN_KEY_ID",
        "STRIPE_BASE_URL",
        "LLM_PROVIDER_API_KEY",
    )
    @classmethod
    def validate_optional_strings(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("PLATFORM_SUPPORTED_PLATFORMS")
    @classmethod
    def validate_supported_platforms(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("PLATFORM_SUPPORTED_PLATFORMS cannot be empty")
        return cleaned

    @field_validator("LLM_PROVIDER_MODEL")
    @classmethod
    def validate_llm_provider_model(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("LLM_PROVIDER_MODEL cannot be empty")
        return cleaned

    @field_validator("LLM_COMPLEXITY_POLICY_PATH")
    @classmethod
    def validate_llm_complexity_policy_path(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("LLM_COMPLEXITY_POLICY_PATH cannot be empty")
        return cleaned

    @field_validator("IDEMPOTENCY_CACHE_TTL")
    @classmethod
    def validate_idempotency_ttl(cls, value: int) -> int:
        """
        TTL must be positive to avoid unbounded caching behavior.
        """
        if value <= 0:
            raise ValueError("IDEMPOTENCY_CACHE_TTL must be greater than zero")
        return value

    @field_validator(
        "LLM_MONTHLY_CAP_CENTS",
        "LLM_HOURLY_SHUTOFF_CENTS",
        "LLM_PROVIDER_TIMEOUT_MS",
        "LLM_BREAKER_FAILURE_THRESHOLD",
        "LLM_BREAKER_OPEN_SECONDS",
    )
    @classmethod
    def validate_llm_runtime_limits(cls, value: int, info) -> int:
        if value < 0:
            raise ValueError(f"{info.field_name} must be >= 0")
        return value

    @field_validator("CELERY_WORKER_PREFETCH_MULTIPLIER")
    @classmethod
    def validate_celery_prefetch_multiplier(cls, value: int) -> int:
        if value < 1:
            raise ValueError("CELERY_WORKER_PREFETCH_MULTIPLIER must be >= 1")
        return value

    @field_validator("CELERY_TASK_SOFT_TIME_LIMIT_S", "CELERY_TASK_TIME_LIMIT_S")
    @classmethod
    def validate_celery_task_time_limits(cls, value: int, info) -> int:
        if value < 1:
            raise ValueError(f"{info.field_name} must be >= 1")
        return value

    @field_validator("BAYESIAN_TASK_SOFT_TIME_LIMIT_S", "BAYESIAN_TASK_TIME_LIMIT_S")
    @classmethod
    def validate_bayesian_task_time_limits(cls, value: int, info) -> int:
        if value < 1:
            raise ValueError(f"{info.field_name} must be >= 1")
        return value

    @field_validator("CELERY_WORKER_MAX_TASKS_PER_CHILD", "CELERY_WORKER_MAX_MEMORY_PER_CHILD_KB")
    @classmethod
    def validate_celery_worker_recycle_limits(cls, value: int, info) -> int:
        if value < 1:
            raise ValueError(f"{info.field_name} must be >= 1")
        return value

    @field_validator("CELERY_CHORD_UNLOCK_MAX_RETRIES", "CELERY_CHORD_UNLOCK_RETRY_DELAY_S")
    @classmethod
    def validate_celery_chord_unlock_limits(cls, value: int, info) -> int:
        if value < 0:
            raise ValueError(f"{info.field_name} must be >= 0")
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

    @model_validator(mode="after")
    def validate_llm_provider_config(self) -> "Settings":
        if self.LLM_PROVIDER_ENABLED and not self.LLM_PROVIDER_API_KEY:
            raise ValueError("LLM_PROVIDER_ENABLED requires LLM_PROVIDER_API_KEY")
        if (self.DATABASE_POOL_SIZE + self.DATABASE_MAX_OVERFLOW) > self.DATABASE_POOL_TOTAL_CAP:
            raise ValueError(
                "DATABASE_POOL_SIZE + DATABASE_MAX_OVERFLOW exceeds DATABASE_POOL_TOTAL_CAP"
            )
        if self.BAYESIAN_TASK_TIME_LIMIT_S <= self.BAYESIAN_TASK_SOFT_TIME_LIMIT_S:
            raise ValueError(
                "BAYESIAN_TASK_TIME_LIMIT_S must be greater than BAYESIAN_TASK_SOFT_TIME_LIMIT_S"
            )
        return self


settings = Settings()
