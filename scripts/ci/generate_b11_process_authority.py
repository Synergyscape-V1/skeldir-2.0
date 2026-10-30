#!/usr/bin/env python3
"""Generate and validate the per-process AWS authority matrix.

The matrix is the reviewed input to Terraform's per-process IAM roles. It is
derived from the managed-settings contract, so a path that is not a managed
setting cannot enter a role policy. Secret paths are assigned explicitly; all
non-B26 config paths are readable by every runtime process. B26 witness/source
config is assigned only to the process roles that actually consume it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.managed_settings_contract import (  # noqa: E402
    MANAGED_SETTINGS_CONTRACT,
    PROCESS_DATABASE_SECRET_PATHS,
)

OUT = ROOT / "contracts-internal" / "governance" / "b11_process_authority.v1.json"
PROCESSES = (
    "api",
    "auth_ingress",
    "worker",
    "worker_bayesian",
    "worker_bayesian_publisher",
    "worker_b23",
    "observer_b26_p2",
    "b26_p2_relay",
    "beat",
    "trust_signer",
    "trust_issuer",
    "migration",
)
SECRET_KEYS = {
    "api": (
        "AUTH_JWT_SECRET",
        "AUTH_JWT_PUBLIC_KEY_RING",
        "AUTH_LOGIN_IDENTIFIER_PEPPER",
        "PLATFORM_TOKEN_ENCRYPTION_KEY",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
    ),
    "auth_ingress": (),
    "worker": (
        "PLATFORM_TOKEN_ENCRYPTION_KEY",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
        "LLM_PROVIDER_API_KEY",
    ),
    "worker_bayesian": (
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
        "LLM_PROVIDER_API_KEY",
    ),
    "worker_bayesian_publisher": (
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
    ),
    "worker_b23": (
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
    ),
    "observer_b26_p2": (
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
    ),
    "b26_p2_relay": (
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
    ),
    "beat": ("CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"),
    "trust_signer": (),
    "trust_issuer": (),
    "migration": ("MIGRATION_DATABASE_URL",),
}
B26_CONFIG = {
    "auth_ingress": ("B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH",),
    "observer_b26_p2": (
        "B26_P2_HISTORY_WITNESS_JOURNAL_PATH",
        "B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH",
        "B26_P2_HISTORY_WITNESS_PRIVATE_KEY_PATH",
        "B26_P2_HISTORY_WITNESS_GENESIS_HASH",
        "B26_P2_HISTORY_WITNESS_HORIZON_SECONDS",
        "B26_P2_HISTORY_WITNESS_REQUIRED",
        "B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH",
        "B26_P2_HISTORY_WITNESS_CUSTODY_PATH",
        "B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH",
    ),
    "api": (
        "B26_P2_HISTORY_WITNESS_JOURNAL_PATH",
        "B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH",
        "B26_P2_HISTORY_WITNESS_GENESIS_HASH",
        "B26_P2_HISTORY_WITNESS_HORIZON_SECONDS",
        "B26_P2_HISTORY_WITNESS_REQUIRED",
        "B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH",
        "B26_P2_HISTORY_WITNESS_CUSTODY_PATH",
        "B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH",
    ),
    "trust_signer": (
        "B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH",
        "B26_P2_HISTORY_WITNESS_JOURNAL_PATH",
    ),
    "trust_issuer": (
        "B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH",
        "B26_P2_HISTORY_WITNESS_JOURNAL_PATH",
    ),
}
B26_KEYS = frozenset(
    key for key in MANAGED_SETTINGS_CONTRACT if key.startswith("B26_P2_")
)
SHARED_CONFIG = tuple(
    key
    for key, contract in sorted(MANAGED_SETTINGS_CONTRACT.items())
    if contract.classification == "config" and key not in B26_KEYS
)


def _path(key: str) -> str:
    contract = MANAGED_SETTINGS_CONTRACT.get(key)
    if contract is None:
        raise SystemExit(f"unknown_managed_key:{key}")
    return contract.aws_path_template


TASK_DATABASE_SECRETS = dict(PROCESS_DATABASE_SECRET_PATHS)
if set(TASK_DATABASE_SECRETS) != set(PROCESSES):
    raise SystemExit("process_database_secret_set_mismatch")


def build() -> dict:
    processes: dict[str, dict[str, list[str]]] = {}
    for process in PROCESSES:
        config_keys = set(SHARED_CONFIG)
        config_keys.update(B26_CONFIG.get(process, ()))
        secret_keys = set(SECRET_KEYS.get(process, ()))
        processes[process] = {
            "config": sorted(_path(key) for key in config_keys),
            "secrets": sorted(
                {_path(key) for key in secret_keys}
                | {TASK_DATABASE_SECRETS[process]}
            ),
        }
    return {
        "version": "b11-process-authority-v1",
        "environments": ["prod", "stage"],
        "processes": processes,
        "task_database_secrets": dict(sorted(TASK_DATABASE_SECRETS.items())),
    }


def validate(matrix: dict) -> None:
    if matrix.get("version") != "b11-process-authority-v1":
        raise SystemExit("matrix_version_invalid")
    processes = matrix.get("processes")
    if not isinstance(processes, dict) or set(processes) != set(PROCESSES):
        raise SystemExit("matrix_process_set_mismatch")
    managed_paths = {
        contract.aws_path_template
        for contract in MANAGED_SETTINGS_CONTRACT.values()
    } | set(TASK_DATABASE_SECRETS.values())
    for process, entries in processes.items():
        for kind in ("config", "secrets"):
            paths = entries.get(kind)
            if not isinstance(paths, list):
                raise SystemExit(f"matrix_{process}_{kind}_invalid")
            if kind == "secrets" and not paths and process not in {"auth_ingress", "trust_signer", "trust_issuer"}:
                raise SystemExit(f"matrix_{process}_{kind}_empty")
            if len(paths) != len(set(paths)):
                raise SystemExit(f"matrix_{process}_{kind}_duplicate")
            for path in paths:
                if not isinstance(path, str) or not path.startswith("/skeldir/{env}/"):
                    raise SystemExit(f"matrix_{process}_{kind}_path_invalid:{path}")
                if "*" in path:
                    raise SystemExit(f"matrix_{process}_{kind}_wildcard:{path}")
                if path not in managed_paths:
                    raise SystemExit(f"matrix_{process}_{kind}_unmanaged:{path}")
    database_path = _path("DATABASE_URL")
    if any(
        database_path in entries["secrets"]
        for entries in processes.values()
    ):
        raise SystemExit("shared_runtime_database_secret_in_process_roles")
    # The migration credential and auth secrets may not cross process roles.
    exclusive = {
        "MIGRATION_DATABASE_URL": "migration",
        "AUTH_JWT_SECRET": "api",
        "AUTH_LOGIN_IDENTIFIER_PEPPER": "api",
        "LLM_PROVIDER_API_KEY": None,
    }
    for key, owner in exclusive.items():
        path = _path(key)
        holders = [
            process
            for process, entries in processes.items()
            if path in entries["secrets"]
        ]
        if owner is None:
            if holders != ["worker", "worker_bayesian"]:
                raise SystemExit(f"exclusive_secret_holders_mismatch:{key}:{holders}")
        elif holders != [owner]:
            raise SystemExit(f"exclusive_secret_holder_mismatch:{key}:{holders}")
    task_db = matrix.get("task_database_secrets")
    if not isinstance(task_db, dict) or set(task_db) != set(PROCESSES):
        raise SystemExit("task_database_secret_set_mismatch")
    if len(set(task_db.values())) != len(task_db):
        raise SystemExit("task_database_secret_shared")
    for process, path in task_db.items():
        if not isinstance(path, str) or not path.startswith("/skeldir/{env}/secret/database/"):
            raise SystemExit(f"task_database_secret_path_invalid:{process}")
        if "*" in path:
            raise SystemExit(f"task_database_secret_wildcard:{process}")
    if any(
        _path("MIGRATION_DATABASE_URL") in entries["secrets"]
        for process, entries in processes.items()
        if process != "migration"
    ):
        raise SystemExit("migration_secret_cross_grant")


def main() -> int:
    matrix = build()
    validate(matrix)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")
    print(f"B11_PROCESS_AUTHORITY_OK processes={len(matrix['processes'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
