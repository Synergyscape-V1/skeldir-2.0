from __future__ import annotations

"""B1.1-P1 single source of truth for managed settings and secrets."""

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
) -> ManagedSettingContract:
    return ManagedSettingContract(
        key=key,
        classification=classification,
        env_scopes=env_scopes,
        aws_path_template=aws_path_template,
        rotation_criticality=rotation_criticality,
        owner=owner,
        call_sites=call_sites,
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
    "AUTH_JWT_SECRET": _contract(
        key="AUTH_JWT_SECRET",
        classification="secret",
        aws_path_template="/skeldir/{env}/secret/auth/jwt-secret",
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
}


def get_managed_setting_contract(key: str) -> ManagedSettingContract:
    try:
        return MANAGED_SETTINGS_CONTRACT[key]
    except KeyError as exc:
        raise KeyError(f"No managed setting contract defined for key: {key}") from exc


def iter_managed_setting_contracts() -> tuple[ManagedSettingContract, ...]:
    return tuple(MANAGED_SETTINGS_CONTRACT[key] for key in sorted(MANAGED_SETTINGS_CONTRACT))
