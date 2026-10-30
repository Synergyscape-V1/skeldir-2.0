"""B1.1-P1 single source of truth for managed settings and secrets."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

SettingClassification = Literal["config", "secret"]
RotationCriticality = Literal["critical", "high", "standard", "none"]

ALLOWED_SECRET_ENVS: tuple[str, ...] = ("prod", "stage", "ci", "dev", "local")


@dataclass(frozen=True)
class ManagedSettingContract:
    key: str
    classification: SettingClassification
    env_scopes: tuple[str, ...]
    aws_path_template: str
    rotation_criticality: RotationCriticality
    owner: str
    call_sites: tuple[str, ...]
    process_roles: tuple[str, ...] | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _contract(
    *,
    key: str,
    classification: SettingClassification,
    aws_path_template: str,
    rotation_criticality: RotationCriticality,
    owner: str,
    call_sites: tuple[str, ...],
    env_scopes: tuple[str, ...] = ALLOWED_SECRET_ENVS,
    process_roles: tuple[str, ...] | None = None,
) -> ManagedSettingContract:
    return ManagedSettingContract(
        key=key,
        classification=classification,
        env_scopes=env_scopes,
        aws_path_template=aws_path_template,
        rotation_criticality=rotation_criticality,
        owner=owner,
        call_sites=call_sites,
        process_roles=process_roles,
    )


# Contract-as-code SSOT: any new Settings key must be added here.
MANAGED_SETTINGS_CONTRACT: dict[str, ManagedSettingContract] = {
    "DATABASE_URL": _contract(
        key="DATABASE_URL",
        classification="secret",
        aws_path_template="/skeldir/{env}/secret/database/runtime-url",
        rotation_criticality="critical",
        owner="platform-security",
        call_sites=("backend/app/db/session.py", "backend/app/celery_app.py"),
    ),
    "MIGRATION_DATABASE_URL": _contract(
        key="MIGRATION_DATABASE_URL",
        classification="secret",
        aws_path_template="/skeldir/{env}/secret/database/migration-url",
        rotation_criticality="critical",
        owner="platform-security",
        call_sites=("alembic/env.py", "scripts/run_alembic.ps1"),
        process_roles=("migration",),
    ),
    "DATABASE_POOL_SIZE": _contract(
        key="DATABASE_POOL_SIZE",
        classification="config",
        aws_path_template="/skeldir/{env}/config/database/pool-size",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/db/session.py",),
    ),
    "DATABASE_MAX_OVERFLOW": _contract(
        key="DATABASE_MAX_OVERFLOW",
        classification="config",
        aws_path_template="/skeldir/{env}/config/database/max-overflow",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/db/session.py",),
    ),
    "DATABASE_POOL_TIMEOUT_SECONDS": _contract(
        key="DATABASE_POOL_TIMEOUT_SECONDS",
        classification="config",
        aws_path_template="/skeldir/{env}/config/database/pool-timeout-seconds",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/db/session.py",),
    ),
    "B23_DATABASE_POOL_SIZE": _contract(
        key="B23_DATABASE_POOL_SIZE",
        classification="config",
        aws_path_template="/skeldir/{env}/config/b23/database/pool-size",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/core/config.py", "backend/app/db/session.py"),
    ),
    "B23_DATABASE_MAX_OVERFLOW": _contract(
        key="B23_DATABASE_MAX_OVERFLOW",
        classification="config",
        aws_path_template="/skeldir/{env}/config/b23/database/max-overflow",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/core/config.py", "backend/app/db/session.py"),
    ),
    "B23_DATABASE_POOL_TIMEOUT_SECONDS": _contract(
        key="B23_DATABASE_POOL_TIMEOUT_SECONDS",
        classification="config",
        aws_path_template="/skeldir/{env}/config/b23/database/pool-timeout-seconds",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/core/config.py", "backend/app/db/session.py"),
    ),
    "B23_DATABASE_STATEMENT_TIMEOUT_MS": _contract(
        key="B23_DATABASE_STATEMENT_TIMEOUT_MS",
        classification="config",
        aws_path_template="/skeldir/{env}/config/b23/database/statement-timeout-ms",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/core/config.py", "backend/app/db/session.py"),
    ),
    "B23_DATABASE_LOCK_TIMEOUT_MS": _contract(
        key="B23_DATABASE_LOCK_TIMEOUT_MS",
        classification="config",
        aws_path_template="/skeldir/{env}/config/b23/database/lock-timeout-ms",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/core/config.py", "backend/app/db/session.py"),
    ),
    "B23_WORKER_CONCURRENCY": _contract(
        key="B23_WORKER_CONCURRENCY",
        classification="config",
        aws_path_template="/skeldir/{env}/config/b23/worker/concurrency",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/core/config.py", "Procfile", "compose.e2e worker fixture"),
    ),
    "B23_WORKER_PREFETCH_MULTIPLIER": _contract(
        key="B23_WORKER_PREFETCH_MULTIPLIER",
        classification="config",
        aws_path_template="/skeldir/{env}/config/b23/worker/prefetch-multiplier",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/core/config.py", "backend/app/celery_app.py"),
    ),
    "DATABASE_POOL_TOTAL_CAP": _contract(
        key="DATABASE_POOL_TOTAL_CAP",
        classification="config",
        aws_path_template="/skeldir/{env}/config/database/pool-total-cap",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/db/session.py",),
    ),
    "TENANT_API_KEY_HEADER": _contract(
        key="TENANT_API_KEY_HEADER",
        classification="config",
        aws_path_template="/skeldir/{env}/config/tenant/api-key-header",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/api/webhooks.py",),
    ),
    "TENANT_SECRETS_CACHE_TTL_SECONDS": _contract(
        key="TENANT_SECRETS_CACHE_TTL_SECONDS",
        classification="config",
        aws_path_template="/skeldir/{env}/config/tenant/secrets-cache-ttl-seconds",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/core/config.py",),
    ),
    "TENANT_SECRETS_CACHE_MAX_ENTRIES": _contract(
        key="TENANT_SECRETS_CACHE_MAX_ENTRIES",
        classification="config",
        aws_path_template="/skeldir/{env}/config/tenant/secrets-cache-max-entries",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/core/config.py",),
    ),
    "WEBHOOK_AUTH_MAX_BODY_BYTES": _contract(
        key="WEBHOOK_AUTH_MAX_BODY_BYTES",
        classification="config",
        aws_path_template="/skeldir/{env}/config/webhooks/auth-max-body-bytes",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/api/webhooks.py", "backend/app/middleware/pii_stripping.py"),
    ),
    "AUTH_JWT_SECRET": _contract(
        key="AUTH_JWT_SECRET",
        classification="secret",
        aws_path_template="/skeldir/{env}/secret/auth/jwt-secret",
        rotation_criticality="critical",
        owner="platform-security",
        call_sites=("backend/app/security/auth.py",),
    ),
    "AUTH_JWT_PUBLIC_KEY_RING": _contract(
        key="AUTH_JWT_PUBLIC_KEY_RING",
        classification="secret",
        aws_path_template="/skeldir/{env}/secret/auth/jwt-public-key-ring",
        rotation_criticality="critical",
        owner="platform-security",
        call_sites=("backend/app/security/auth.py",),
    ),
    "AUTH_JWT_ALGORITHM": _contract(
        key="AUTH_JWT_ALGORITHM",
        classification="config",
        aws_path_template="/skeldir/{env}/config/auth/jwt-algorithm",
        rotation_criticality="none",
        owner="platform-security",
        call_sites=("backend/app/security/auth.py",),
    ),
    "AUTH_JWT_ISSUER": _contract(
        key="AUTH_JWT_ISSUER",
        classification="config",
        aws_path_template="/skeldir/{env}/config/auth/jwt-issuer",
        rotation_criticality="none",
        owner="platform-security",
        call_sites=("backend/app/security/auth.py",),
    ),
    "AUTH_JWT_AUDIENCE": _contract(
        key="AUTH_JWT_AUDIENCE",
        classification="config",
        aws_path_template="/skeldir/{env}/config/auth/jwt-audience",
        rotation_criticality="none",
        owner="platform-security",
        call_sites=("backend/app/security/auth.py",),
    ),
    "AUTH_JWT_JWKS_URL": _contract(
        key="AUTH_JWT_JWKS_URL",
        classification="config",
        aws_path_template="/skeldir/{env}/config/auth/jwks-url",
        rotation_criticality="none",
        owner="platform-security",
        call_sites=("backend/app/security/auth.py",),
    ),
    "AUTH_LOGIN_IDENTIFIER_PEPPER": _contract(
        key="AUTH_LOGIN_IDENTIFIER_PEPPER",
        classification="secret",
        aws_path_template="/skeldir/{env}/secret/auth/login-identifier-pepper",
        rotation_criticality="high",
        owner="platform-security",
        call_sites=("backend/app/services/auth_tokens.py",),
    ),
    "PLATFORM_TOKEN_ENCRYPTION_KEY": _contract(
        key="PLATFORM_TOKEN_ENCRYPTION_KEY",
        classification="secret",
        aws_path_template="/skeldir/{env}/secret/platform/token-encryption-key",
        rotation_criticality="critical",
        owner="platform-security",
        call_sites=("backend/app/api/platforms.py", "backend/app/services/realtime_revenue_providers.py"),
    ),
    "PLATFORM_TOKEN_KEY_ID": _contract(
        key="PLATFORM_TOKEN_KEY_ID",
        classification="config",
        aws_path_template="/skeldir/{env}/config/platform/token-key-id",
        rotation_criticality="none",
        owner="platform-security",
        call_sites=("backend/app/api/platforms.py",),
    ),
    "PLATFORM_SUPPORTED_PLATFORMS": _contract(
        key="PLATFORM_SUPPORTED_PLATFORMS",
        classification="config",
        aws_path_template="/skeldir/{env}/config/platform/supported-platforms",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/api/platforms.py",),
    ),
    "STRIPE_BASE_URL": _contract(
        key="STRIPE_BASE_URL",
        classification="config",
        aws_path_template="/skeldir/{env}/config/platform/stripe-base-url",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/services/realtime_revenue_providers.py",),
    ),
    "ENVIRONMENT": _contract(
        key="ENVIRONMENT",
        classification="config",
        aws_path_template="/skeldir/{env}/config/runtime/environment",
        rotation_criticality="none",
        owner="platform-security",
        call_sites=("backend/app/core/config.py",),
    ),
    "LOG_LEVEL": _contract(
        key="LOG_LEVEL",
        classification="config",
        aws_path_template="/skeldir/{env}/config/runtime/log-level",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/main.py", "backend/app/celery_app.py"),
    ),
    "LLM_PROVIDER_ENABLED": _contract(
        key="LLM_PROVIDER_ENABLED",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/provider-enabled",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=("backend/app/llm/provider_boundary.py",),
    ),
    "LLM_PROVIDER_API_KEY": _contract(
        key="LLM_PROVIDER_API_KEY",
        classification="secret",
        aws_path_template="/skeldir/{env}/secret/llm/provider-api-key",
        rotation_criticality="high",
        owner="ai-platform",
        call_sites=("backend/app/llm/provider_boundary.py",),
    ),
    "LLM_PROVIDER_MODEL": _contract(
        key="LLM_PROVIDER_MODEL",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/provider-model",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=("backend/app/llm/provider_boundary.py",),
    ),
    "LLM_COMPLEXITY_POLICY_PATH": _contract(
        key="LLM_COMPLEXITY_POLICY_PATH",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/complexity-policy-path",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=("backend/app/llm/provider_boundary.py",),
    ),
    "LLM_PROVIDER_KILL_SWITCH": _contract(
        key="LLM_PROVIDER_KILL_SWITCH",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/provider-kill-switch",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=("backend/app/llm/provider_boundary.py",),
    ),
    "LLM_MONTHLY_CAP_CENTS": _contract(
        key="LLM_MONTHLY_CAP_CENTS",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/monthly-cap-cents",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=("backend/app/llm/provider_boundary.py",),
    ),
    "LLM_HOURLY_SHUTOFF_CENTS": _contract(
        key="LLM_HOURLY_SHUTOFF_CENTS",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/hourly-shutoff-cents",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=("backend/app/llm/provider_boundary.py",),
    ),
    "LLM_PROVIDER_TIMEOUT_MS": _contract(
        key="LLM_PROVIDER_TIMEOUT_MS",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/provider-timeout-ms",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=("backend/app/llm/provider_boundary.py",),
    ),
    "LLM_B17_EXPLANATION_FAST_TIER": _contract(
        key="LLM_B17_EXPLANATION_FAST_TIER",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/b17-explanation-fast-tier",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=("backend/app/api/attribution.py",),
    ),
    "LLM_B17_EXPLANATION_TIMEOUT_MS": _contract(
        key="LLM_B17_EXPLANATION_TIMEOUT_MS",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/b17-explanation-timeout-ms",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=("backend/app/api/attribution.py",),
    ),
    "LLM_B17_EXPLANATION_MAX_COST_CENTS": _contract(
        key="LLM_B17_EXPLANATION_MAX_COST_CENTS",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/b17-explanation-max-cost-cents",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=("backend/app/api/attribution.py",),
    ),
    "LLM_B17_PREWARM_ENABLED": _contract(
        key="LLM_B17_PREWARM_ENABLED",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/b17-prewarm-enabled",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=(
            "backend/app/api/attribution.py",
            "backend/app/services/b17_p4_prewarm_policy.py",
        ),
    ),
    "LLM_B17_PREWARM_RUN_SYNC": _contract(
        key="LLM_B17_PREWARM_RUN_SYNC",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/b17-prewarm-run-sync",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=("backend/app/api/attribution.py",),
    ),
    "LLM_B17_PREWARM_ELIGIBLE_ENTITY_TYPES": _contract(
        key="LLM_B17_PREWARM_ELIGIBLE_ENTITY_TYPES",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/b17-prewarm-eligible-entity-types",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=("backend/app/services/b17_p4_prewarm_policy.py",),
    ),
    "LLM_B17_PREWARM_MAX_PERMUTATIONS_PER_TRIGGER": _contract(
        key="LLM_B17_PREWARM_MAX_PERMUTATIONS_PER_TRIGGER",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/b17-prewarm-max-permutations-per-trigger",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=(
            "backend/app/api/attribution.py",
            "backend/app/services/b17_p4_prewarm_policy.py",
        ),
    ),
    "LLM_B17_PREWARM_MIN_TRIGGER_INTERVAL_SECONDS": _contract(
        key="LLM_B17_PREWARM_MIN_TRIGGER_INTERVAL_SECONDS",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/b17-prewarm-min-trigger-interval-seconds",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=(
            "backend/app/api/attribution.py",
            "backend/app/services/b17_p4_prewarm_policy.py",
        ),
    ),
    "LLM_B17_PREWARM_MAX_CALLS_PER_TENANT_PER_HOUR": _contract(
        key="LLM_B17_PREWARM_MAX_CALLS_PER_TENANT_PER_HOUR",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/b17-prewarm-max-calls-per-tenant-per-hour",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=(
            "backend/app/api/attribution.py",
            "backend/app/services/b17_p4_prewarm_policy.py",
        ),
    ),
    "LLM_B17_PREWARM_CALL_BUDGET_CENTS": _contract(
        key="LLM_B17_PREWARM_CALL_BUDGET_CENTS",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/b17-prewarm-call-budget-cents",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=(
            "backend/app/api/attribution.py",
            "backend/app/services/b17_p4_prewarm_policy.py",
        ),
    ),
    "LLM_B17_PREWARM_TIMEOUT_MS": _contract(
        key="LLM_B17_PREWARM_TIMEOUT_MS",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/b17-prewarm-timeout-ms",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=("backend/app/api/attribution.py",),
    ),
    "LLM_BREAKER_FAILURE_THRESHOLD": _contract(
        key="LLM_BREAKER_FAILURE_THRESHOLD",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/breaker-failure-threshold",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=("backend/app/llm/provider_boundary.py",),
    ),
    "LLM_BREAKER_OPEN_SECONDS": _contract(
        key="LLM_BREAKER_OPEN_SECONDS",
        classification="config",
        aws_path_template="/skeldir/{env}/config/llm/breaker-open-seconds",
        rotation_criticality="none",
        owner="ai-platform",
        call_sites=("backend/app/llm/provider_boundary.py",),
    ),
    "IDEMPOTENCY_CACHE_TTL": _contract(
        key="IDEMPOTENCY_CACHE_TTL",
        classification="config",
        aws_path_template="/skeldir/{env}/config/ingestion/idempotency-cache-ttl",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/core/config.py",),
    ),
    "ATTRIBUTION_DETERMINISTIC_DEFAULT_LOOKBACK_DAYS": _contract(
        key="ATTRIBUTION_DETERMINISTIC_DEFAULT_LOOKBACK_DAYS",
        classification="config",
        aws_path_template="/skeldir/{env}/config/attribution/deterministic-default-lookback-days",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/core/config.py", "backend/app/tasks/attribution.py"),
    ),
    "INGESTION_FOLLOWUP_TASKS_ENABLED": _contract(
        key="INGESTION_FOLLOWUP_TASKS_ENABLED",
        classification="config",
        aws_path_template="/skeldir/{env}/config/ingestion/followup-tasks-enabled",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/api/webhooks.py",),
    ),
    "CELERY_BROKER_URL": _contract(
        key="CELERY_BROKER_URL",
        classification="secret",
        aws_path_template="/skeldir/{env}/secret/celery/broker-url",
        rotation_criticality="high",
        owner="backend-platform",
        call_sites=("backend/app/celery_app.py",),
    ),
    "CELERY_RESULT_BACKEND": _contract(
        key="CELERY_RESULT_BACKEND",
        classification="secret",
        aws_path_template="/skeldir/{env}/secret/celery/result-backend-url",
        rotation_criticality="high",
        owner="backend-platform",
        call_sites=("backend/app/celery_app.py",),
    ),
    "CELERY_TASK_ACKS_LATE": _contract(
        key="CELERY_TASK_ACKS_LATE",
        classification="config",
        aws_path_template="/skeldir/{env}/config/celery/task-acks-late",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/celery_app.py",),
    ),
    "CELERY_TASK_REJECT_ON_WORKER_LOST": _contract(
        key="CELERY_TASK_REJECT_ON_WORKER_LOST",
        classification="config",
        aws_path_template="/skeldir/{env}/config/celery/task-reject-on-worker-lost",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/celery_app.py",),
    ),
    "CELERY_TASK_ACKS_ON_FAILURE_OR_TIMEOUT": _contract(
        key="CELERY_TASK_ACKS_ON_FAILURE_OR_TIMEOUT",
        classification="config",
        aws_path_template="/skeldir/{env}/config/celery/task-acks-on-failure-or-timeout",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/celery_app.py",),
    ),
    "CELERY_WORKER_PREFETCH_MULTIPLIER": _contract(
        key="CELERY_WORKER_PREFETCH_MULTIPLIER",
        classification="config",
        aws_path_template="/skeldir/{env}/config/celery/worker-prefetch-multiplier",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/celery_app.py",),
    ),
    "CELERY_TASK_SOFT_TIME_LIMIT_S": _contract(
        key="CELERY_TASK_SOFT_TIME_LIMIT_S",
        classification="config",
        aws_path_template="/skeldir/{env}/config/celery/task-soft-time-limit-s",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/celery_app.py",),
    ),
    "CELERY_TASK_TIME_LIMIT_S": _contract(
        key="CELERY_TASK_TIME_LIMIT_S",
        classification="config",
        aws_path_template="/skeldir/{env}/config/celery/task-time-limit-s",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/celery_app.py",),
    ),
    "BAYESIAN_TASK_SOFT_TIME_LIMIT_S": _contract(
        key="BAYESIAN_TASK_SOFT_TIME_LIMIT_S",
        classification="config",
        aws_path_template="/skeldir/{env}/config/celery/bayesian-task-soft-time-limit-s",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/tasks/bayesian.py",),
    ),
    "BAYESIAN_TASK_TIME_LIMIT_S": _contract(
        key="BAYESIAN_TASK_TIME_LIMIT_S",
        classification="config",
        aws_path_template="/skeldir/{env}/config/celery/bayesian-task-time-limit-s",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/tasks/bayesian.py",),
    ),
    "CELERY_WORKER_MAX_TASKS_PER_CHILD": _contract(
        key="CELERY_WORKER_MAX_TASKS_PER_CHILD",
        classification="config",
        aws_path_template="/skeldir/{env}/config/celery/worker-max-tasks-per-child",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/celery_app.py",),
    ),
    "CELERY_WORKER_MAX_MEMORY_PER_CHILD_KB": _contract(
        key="CELERY_WORKER_MAX_MEMORY_PER_CHILD_KB",
        classification="config",
        aws_path_template="/skeldir/{env}/config/celery/worker-max-memory-per-child-kb",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/celery_app.py",),
    ),
    "CELERY_CHORD_UNLOCK_MAX_RETRIES": _contract(
        key="CELERY_CHORD_UNLOCK_MAX_RETRIES",
        classification="config",
        aws_path_template="/skeldir/{env}/config/celery/chord-unlock-max-retries",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/celery_app.py",),
    ),
    "CELERY_CHORD_UNLOCK_RETRY_DELAY_S": _contract(
        key="CELERY_CHORD_UNLOCK_RETRY_DELAY_S",
        classification="config",
        aws_path_template="/skeldir/{env}/config/celery/chord-unlock-retry-delay-s",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/celery_app.py",),
    ),
    "CELERY_BROKER_ENGINE_POOL_SIZE": _contract(
        key="CELERY_BROKER_ENGINE_POOL_SIZE",
        classification="config",
        aws_path_template="/skeldir/{env}/config/celery/broker-engine-pool-size",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/celery_app.py",),
    ),
    "CELERY_BROKER_ENGINE_MAX_OVERFLOW": _contract(
        key="CELERY_BROKER_ENGINE_MAX_OVERFLOW",
        classification="config",
        aws_path_template="/skeldir/{env}/config/celery/broker-engine-max-overflow",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/celery_app.py",),
    ),
    "CELERY_RESULT_BACKEND_ENGINE_POOL_SIZE": _contract(
        key="CELERY_RESULT_BACKEND_ENGINE_POOL_SIZE",
        classification="config",
        aws_path_template="/skeldir/{env}/config/celery/result-backend-engine-pool-size",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/celery_app.py",),
    ),
    "CELERY_BROKER_VISIBILITY_TIMEOUT_S": _contract(
        key="CELERY_BROKER_VISIBILITY_TIMEOUT_S",
        classification="config",
        aws_path_template="/skeldir/{env}/config/celery/broker-visibility-timeout-s",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/celery_app.py",),
    ),
    "CELERY_BROKER_RECOVERY_SWEEP_INTERVAL_S": _contract(
        key="CELERY_BROKER_RECOVERY_SWEEP_INTERVAL_S",
        classification="config",
        aws_path_template="/skeldir/{env}/config/celery/broker-recovery-sweep-interval-s",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/celery_app.py",),
    ),
    "CELERY_BROKER_RECOVERY_TASK_NAME_FILTER": _contract(
        key="CELERY_BROKER_RECOVERY_TASK_NAME_FILTER",
        classification="config",
        aws_path_template="/skeldir/{env}/config/celery/broker-recovery-task-name-filter",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/celery_app.py",),
    ),
    "B26_P2_HISTORY_WITNESS_JOURNAL_PATH": _contract(
        key="B26_P2_HISTORY_WITNESS_JOURNAL_PATH",
        classification="config",
        aws_path_template="/skeldir/{env}/config/b26-p2/history-witness-journal-path",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=(
            "backend/app/trust/builder.py",
            "backend/app/trust/history_witness.py",
            "backend/app/tasks/b26_p2_history.py",
        ),
        process_roles=("observer_b26_p2", "api"),
    ),
    "B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH": _contract(
        key="B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH",
        classification="config",
        aws_path_template="/skeldir/{env}/config/b26-p2/history-witness-public-key-path",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=(
            "backend/app/trust/builder.py",
            "backend/app/trust/history_witness.py",
        ),
        process_roles=("observer_b26_p2", "api"),
    ),
    "B26_P2_HISTORY_WITNESS_PRIVATE_KEY_PATH": _contract(
        key="B26_P2_HISTORY_WITNESS_PRIVATE_KEY_PATH",
        classification="config",
        aws_path_template="/skeldir/{env}/config/b26-p2/history-witness-private-key-path",
        rotation_criticality="high",
        owner="platform-security",
        call_sites=(
            "backend/app/tasks/b26_p2_history.py",
            "backend/app/trust/history_witness.py",
        ),
        process_roles=("observer_b26_p2",),
    ),
    "B26_P2_HISTORY_WITNESS_GENESIS_HASH": _contract(
        key="B26_P2_HISTORY_WITNESS_GENESIS_HASH",
        classification="config",
        aws_path_template="/skeldir/{env}/config/b26-p2/history-witness-genesis-hash",
        rotation_criticality="high",
        owner="backend-platform",
        call_sites=(
            "backend/app/trust/builder.py",
            "backend/app/tasks/b26_p2_history.py",
        ),
        process_roles=("observer_b26_p2", "api"),
    ),
    "B26_P2_HISTORY_WITNESS_HORIZON_SECONDS": _contract(
        key="B26_P2_HISTORY_WITNESS_HORIZON_SECONDS",
        classification="config",
        aws_path_template="/skeldir/{env}/config/b26-p2/history-witness-horizon-seconds",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/trust/builder.py",),
        process_roles=("api",),
    ),
    "B26_P2_HISTORY_WITNESS_REQUIRED": _contract(
        key="B26_P2_HISTORY_WITNESS_REQUIRED",
        classification="config",
        aws_path_template="/skeldir/{env}/config/b26-p2/history-witness-required",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=("backend/app/trust/builder.py",),
        process_roles=("observer_b26_p2", "api"),
    ),
    "B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH": _contract(
        key="B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH",
        classification="config",
        aws_path_template="/skeldir/{env}/config/b26-p2/history-witness-heartbeat-path",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=(
            "backend/app/trust/builder.py",
            "backend/app/tasks/b26_p2_history.py",
        ),
        process_roles=("observer_b26_p2", "api"),
    ),
    "B26_P2_HISTORY_WITNESS_CUSTODY_PATH": _contract(
        key="B26_P2_HISTORY_WITNESS_CUSTODY_PATH",
        classification="config",
        aws_path_template="/skeldir/{env}/config/b26-p2/history-witness-custody-path",
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=(
            "backend/app/trust/builder.py",
            "backend/app/tasks/b26_p2_history.py",
        ),
        process_roles=("observer_b26_p2", "api"),
    ),
    "B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH": _contract(
        key="B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH",
        classification="config",
        aws_path_template=(
            "/skeldir/{env}/config/b26-p2/source-evidence-journal-path"
        ),
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=(
            "backend/app/revenue_verification/source_evidence_journal.py",
            "backend/app/revenue_verification/source_evidence.py",
            "backend/app/revenue_verification/source_attestation.py",
            "backend/app/tasks/b26_p2_history.py",
        ),
        process_roles=("auth_ingress", "observer_b26_p2", "api"),
    ),
    "B26_P2_SOURCE_ATTESTATION_PRIVATE_KEY_PATH": _contract(
        key="B26_P2_SOURCE_ATTESTATION_PRIVATE_KEY_PATH",
        classification="config",
        aws_path_template=(
            "/skeldir/{env}/config/b26-p2/source-attestation-private-key-path"
        ),
        rotation_criticality="high",
        owner="platform-security",
        call_sites=(
            "backend/app/auth_service/server.py",
            "backend/app/revenue_verification/source_attestation.py",
        ),
        process_roles=("auth_ingress",),
    ),
    "B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH": _contract(
        key="B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH",
        classification="config",
        aws_path_template=(
            "/skeldir/{env}/config/b26-p2/source-attestation-public-key-path"
        ),
        rotation_criticality="high",
        owner="backend-platform",
        call_sites=(
            "backend/app/revenue_verification/source_attestation.py",
            "backend/app/trust/builder.py",
        ),
        process_roles=(
            "auth_ingress",
            "observer_b26_p2",
            "api",
            "worker",
            "trust_issuer",
        ),
    ),
    "B26_P2_SOURCE_ATTESTATION_REQUIRED": _contract(
        key="B26_P2_SOURCE_ATTESTATION_REQUIRED",
        classification="config",
        aws_path_template=(
            "/skeldir/{env}/config/b26-p2/source-attestation-required"
        ),
        rotation_criticality="none",
        owner="backend-platform",
        call_sites=(
            "backend/app/core/config.py",
            "backend/app/revenue_verification/source_attestation.py",
            "backend/app/trust/builder.py",
        ),
        process_roles=(
            "auth_ingress",
            "observer_b26_p2",
            "api",
            "worker",
            "trust_issuer",
        ),
    ),
}

# One database credential per database-using process. The migration role keeps
# its distinct migration secret; every runtime process resolves only its own
# path. This mapping is the runtime consumer of the B11 authority matrix and is
# validated against that matrix by scripts/ci/generate_b11_process_authority.py.
PROCESS_DATABASE_SECRET_PATHS: dict[str, str] = {
    "api": "/skeldir/{env}/secret/database/runtime-api-url",
    "auth_ingress": "/skeldir/{env}/secret/database/runtime-auth_ingress-url",
    "worker": "/skeldir/{env}/secret/database/runtime-worker-url",
    "worker_bayesian": (
        "/skeldir/{env}/secret/database/runtime-worker_bayesian-url"
    ),
    "worker_bayesian_publisher": (
        "/skeldir/{env}/secret/database/runtime-worker_bayesian_publisher-url"
    ),
    "worker_b23": "/skeldir/{env}/secret/database/runtime-worker_b23-url",
    "observer_b26_p2": (
        "/skeldir/{env}/secret/database/runtime-observer_b26_p2-url"
    ),
    "b26_p2_relay": "/skeldir/{env}/secret/database/runtime-b26_p2_relay-url",
    "beat": "/skeldir/{env}/secret/database/runtime-beat-url",
    "trust_signer": "/skeldir/{env}/secret/database/runtime-trust_signer-url",
    "trust_issuer": "/skeldir/{env}/secret/database/runtime-trust_issuer-url",
    "migration": "/skeldir/{env}/secret/database/migration-url",
}


def resolve_process_database_secret_path(
    process_role: str, canonical_env: str
) -> str:
    try:
        template = PROCESS_DATABASE_SECRET_PATHS[process_role]
    except KeyError as exc:
        raise KeyError(
            f"No process database secret defined for role: {process_role}"
        ) from exc
    return template.format(env=canonical_env)


def process_role_allows(role: str, key: str) -> bool:
    """Return whether one process role may resolve a managed setting."""

    contract = MANAGED_SETTINGS_CONTRACT.get(key)
    if contract is None:
        return False
    if contract.process_roles is None:
        return True
    return role in contract.process_roles


def get_managed_setting_contract(key: str) -> ManagedSettingContract:
    try:
        return MANAGED_SETTINGS_CONTRACT[key]
    except KeyError as exc:
        raise KeyError(f"No managed setting contract defined for key: {key}") from exc


def iter_managed_setting_contracts() -> tuple[ManagedSettingContract, ...]:
    return tuple(MANAGED_SETTINGS_CONTRACT[key] for key in sorted(MANAGED_SETTINGS_CONTRACT))
