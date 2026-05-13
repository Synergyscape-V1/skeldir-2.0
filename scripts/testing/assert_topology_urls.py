#!/usr/bin/env python3
"""M2 topology URL authority validator."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from urllib.parse import urlparse


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "postgres", "pgbouncer"}
EXTERNAL_MARKERS = ("neon.tech", "rds.amazonaws.com", "amazonaws.com", "supabase.co")


@dataclass(frozen=True)
class UrlRule:
    env_name: str
    required: bool
    pooler_allowed: bool
    external_allowed: bool
    ci_allowed: bool
    default_local_allowed: bool
    purpose: str


RULES = [
    UrlRule("DATABASE_URL", True, False, False, True, True, "application runtime direct local database"),
    UrlRule("DIRECT_DATABASE_URL", False, False, False, True, True, "explicit direct local runtime database"),
    UrlRule("POOLED_DATABASE_URL", False, True, False, True, False, "explicit local transaction-pooler database"),
    UrlRule("TEST_DATABASE_URL", False, False, False, True, True, "default local test database"),
    UrlRule("TEST_DIRECT_DATABASE_URL", False, False, False, True, True, "direct local test database"),
    UrlRule("TEST_POOLED_DATABASE_URL", False, True, False, True, False, "pooled local test database"),
    UrlRule("ALEMBIC_DATABASE_URL", False, False, False, True, True, "direct local migration database"),
    UrlRule("MIGRATION_DATABASE_URL", False, False, False, True, True, "direct local migration database"),
    UrlRule("EXTERNAL_DATABASE_URL", False, True, True, False, False, "explicit opt-in external smoke database"),
    UrlRule("CELERY_BROKER_URL", True, False, False, True, True, "local Postgres Celery broker"),
    UrlRule("CELERY_RESULT_BACKEND", True, False, False, True, True, "local Postgres Celery result backend"),
]


def _strip_driver_prefix(raw: str) -> str:
    value = raw
    for prefix in ("sqla+", "db+"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
    return value.replace("postgresql+asyncpg://", "postgresql://", 1)


def _host(raw: str) -> str:
    return (urlparse(_strip_driver_prefix(raw)).hostname or "").lower()


def _is_pooler(raw: str) -> bool:
    lowered = raw.lower()
    return "pooler" in lowered or _host(raw) == "pgbouncer" or ":6432" in lowered


def _is_external(raw: str) -> bool:
    host = _host(raw)
    return host not in LOCAL_HOSTS or any(marker in host for marker in EXTERNAL_MARKERS)


def validate(*, external_smoke: bool = False) -> list[str]:
    errors: list[str] = []
    allow_external = os.getenv("SKELDIR_ALLOW_EXTERNAL_DB_TESTS", "").lower() == "true"

    for rule in RULES:
        value = os.getenv(rule.env_name)
        if rule.required and not value:
            errors.append(f"{rule.env_name}:missing required URL for {rule.purpose}")
            continue
        if not value:
            continue
        if _is_pooler(value) and not rule.pooler_allowed:
            errors.append(f"{rule.env_name}:pooler URL is not allowed")
        if _is_external(value) and not rule.external_allowed:
            errors.append(f"{rule.env_name}:external host is not allowed ({_host(value)})")
        if rule.env_name == "EXTERNAL_DATABASE_URL":
            if external_smoke and not allow_external:
                errors.append("EXTERNAL_DATABASE_URL:external smoke requires SKELDIR_ALLOW_EXTERNAL_DB_TESTS=true")
            if allow_external and not value:
                errors.append("EXTERNAL_DATABASE_URL:required when external smoke is explicitly enabled")

    if os.getenv("CI", "").lower() == "true":
        for rule in RULES:
            value = os.getenv(rule.env_name)
            if value and _is_external(value) and not rule.ci_allowed:
                errors.append(f"{rule.env_name}:standard CI cannot use external host")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--external-smoke", action="store_true")
    parser.add_argument("--expect-rejection", action="store_true")
    args = parser.parse_args()

    errors = validate(external_smoke=args.external_smoke)
    if args.expect_rejection:
        probe = "postgresql://app_user:app_user@ep-invalid-pooler.example.neon.tech/neondb"
        os.environ["DATABASE_URL"] = probe
        rejected = validate()
        if not any("DATABASE_URL:external host is not allowed" in item for item in rejected):
            print("M2 topology rejection negative control failed")
            return 1
        print("M2 topology rejection negative control passed")
        return 0

    if errors:
        print("M2 topology URL authority failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("M2 topology URL authority passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
