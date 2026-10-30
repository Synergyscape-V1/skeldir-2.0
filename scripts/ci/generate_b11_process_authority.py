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

from app.core.managed_settings_contract import MANAGED_SETTINGS_CONTRACT  # noqa: E402

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
        "DATABASE_URL",
        "AUTH_JWT_SECRET",
        "AUTH_JWT_PUBLIC_KEY_RING",
        "AUTH_LOGIN_IDENTIFIER_PEPPER",
        "PLATFORM_TOKEN_ENCRYPTION_KEY",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
    ),
    "auth_ingress": ("DATABASE_URL",),
    "worker": (
        "DATABASE_URL",
        "PLATFORM_TOKEN_ENCRYPTION_KEY",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
        "LLM_PROVIDER_API_KEY",
    ),
    "worker_bayesian": (
        "DATABASE_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
        "LLM_PROVIDER_API_KEY",
    ),
    "worker_bayesian_publisher": (
        "DATABASE_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
    ),
    "worker_b23": (
        "DATABASE_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
    ),
    "observer_b26_p2": (
        "DATABASE_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
    ),
    "b26_p2_relay": (
        "DATABASE_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
    ),
    "beat": ("DATABASE_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"),
    "trust_signer": ("DATABASE_URL",),
    "trust_issuer": ("DATABASE_URL",),
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


def build() -> dict:
    processes: dict[str, dict[str, list[str]]] = {}
    for process in PROCESSES:
        config_keys = set(SHARED_CONFIG)
        config_keys.update(B26_CONFIG.get(process, ()))
        secret_keys = set(SECRET_KEYS.get(process, ()))
        processes[process] = {
            "config": sorted(_path(key) for key in config_keys),
            "secrets": sorted(_path(key) for key in secret_keys),
        }
    return {
        "version": "b11-process-authority-v1",
        "environments": ["prod", "stage"],
        "processes": processes,
    }


def validate(matrix: dict) -> None:
    if matrix.get("version") != "b11-process-authority-v1":
        raise SystemExit("matrix_version_invalid")
    processes = matrix.get("processes")
    if not isinstance(processes, dict) or set(processes) != set(PROCESSES):
        raise SystemExit("matrix_process_set_mismatch")
    managed_paths = {contract.aws_path_template for contract in MANAGED_SETTINGS_CONTRACT.values()}
    for process, entries in processes.items():
        for kind in ("config", "secrets"):
            paths = entries.get(kind)
            if not isinstance(paths, list) or not paths:
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
