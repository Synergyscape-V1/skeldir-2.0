"""Topology authority for Bayesian worker database connections."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.engine.url import make_url


class BayesianWorkerDBTopology(StrEnum):
    """Supported Bayesian worker database topology modes."""

    DIRECT_POSTGRES = "direct_postgres"


DIRECT_POSTGRES_ATTESTATIONS = frozenset(
    {
        "direct_postgres_runtime_verified",
        "direct_postgres_deployment_attested",
        "direct_postgres_ci_postgres15",
    }
)
UNSUPPORTED_POOLER_TOPOLOGIES = frozenset(
    {
        "pgbouncer",
        "pgbouncer_session",
        "pgbouncer_transaction",
        "rds_proxy",
        "neon_pooler",
        "supabase_pooler",
        "proxy",
        "transparent_proxy",
    }
)
POOLER_NEGATIVE_CONTROL_TOKENS = frozenset(
    {
        "pgbouncer",
        "pooler",
        "rds-proxy",
        "rds_proxy",
        "proxy",
        "neon",
        "supabase",
        "transaction_pool",
        "session_pool",
    }
)
PROTECTED_ENVIRONMENTS = frozenset(
    {
        "ci",
        "prod",
        "production",
        "stage",
        "staging",
        "preview",
    }
)


@dataclass(frozen=True)
class BayesianWorkerDBTopologyPolicy:
    """Resolved topology policy used before creating a worker DB engine."""

    topology: BayesianWorkerDBTopology
    attestation: str | None
    protected_runtime: bool
    source: str


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def protected_topology_runtime() -> bool:
    """Return whether topology must be explicitly attested and fail-closed."""

    environment = os.getenv("ENVIRONMENT", "").strip().lower()
    return (
        os.getenv("CI", "").strip().lower() == "true"
        or environment in PROTECTED_ENVIRONMENTS
        or _truthy_env("SKELDIR_BAYESIAN_DB_TOPOLOGY_REQUIRE_ATTESTATION")
    )


def _is_postgres_url(database_url: str) -> bool:
    try:
        return make_url(database_url).drivername.startswith("postgresql")
    except Exception:
        return False


def _is_non_postgres_test_url(database_url: str) -> bool:
    try:
        driver = make_url(database_url).drivername
    except Exception:
        return False
    return driver.startswith("sqlite") and _truthy_env("TESTING")


def _pooler_negative_control_detected(database_url: str) -> bool:
    try:
        parsed = make_url(database_url)
    except Exception:
        candidate = database_url.lower()
    else:
        parts = [
            parsed.host or "",
            parsed.database or "",
            parsed.drivername or "",
            "&".join(f"{key}={value}" for key, value in parsed.query.items()),
        ]
        candidate = " ".join(parts).lower()
    return any(token in candidate for token in POOLER_NEGATIVE_CONTROL_TOKENS)


def resolve_bayesian_worker_db_topology_policy(
    database_url: str,
    *,
    require_attestation: bool | None = None,
) -> BayesianWorkerDBTopologyPolicy:
    """Resolve and validate Bayesian worker DB topology authority.

    DSN contents are intentionally insufficient proof of a direct topology. The
    DSN is used only for negative controls against obvious pooler/proxy routing.
    Protected runtimes must provide an explicit topology mode and attestation.
    """

    if not _is_postgres_url(database_url):
        if not _is_non_postgres_test_url(database_url):
            raise RuntimeError("bayesian_worker_db_topology_requires_postgres")
        if require_attestation:
            raise RuntimeError("bayesian_worker_db_topology_requires_postgres")
        return BayesianWorkerDBTopologyPolicy(
            topology=BayesianWorkerDBTopology.DIRECT_POSTGRES,
            attestation=None,
            protected_runtime=False,
            source="non_postgres_test_url",
        )

    if _pooler_negative_control_detected(database_url):
        raise RuntimeError("bayesian_worker_db_topology_proxy_dsn_rejected")

    protected = (
        protected_topology_runtime()
        if require_attestation is None
        else bool(require_attestation)
    )
    raw_topology = os.getenv("SKELDIR_BAYESIAN_DB_TOPOLOGY", "").strip().lower()
    raw_attestation = os.getenv("SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION", "").strip()
    source = os.getenv("SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE", "").strip()

    if not raw_topology:
        if protected:
            raise RuntimeError("bayesian_worker_db_topology_missing")
        return BayesianWorkerDBTopologyPolicy(
            topology=BayesianWorkerDBTopology.DIRECT_POSTGRES,
            attestation=None,
            protected_runtime=False,
            source="local_unattested_default",
        )

    if raw_topology in UNSUPPORTED_POOLER_TOPOLOGIES:
        raise RuntimeError("bayesian_worker_db_topology_pooler_unsupported")
    if raw_topology != BayesianWorkerDBTopology.DIRECT_POSTGRES.value:
        raise RuntimeError("bayesian_worker_db_topology_unknown")

    if protected:
        if raw_attestation not in DIRECT_POSTGRES_ATTESTATIONS:
            raise RuntimeError("bayesian_worker_db_topology_attestation_missing")
        if not source:
            raise RuntimeError("bayesian_worker_db_topology_source_missing")

    return BayesianWorkerDBTopologyPolicy(
        topology=BayesianWorkerDBTopology.DIRECT_POSTGRES,
        attestation=raw_attestation or None,
        protected_runtime=protected,
        source=source or "local_declared",
    )
