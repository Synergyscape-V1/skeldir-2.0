from __future__ import annotations

"""B11-P1 runtime resolver for environment-namespaced config/secret retrieval."""

import json
import os
import subprocess
from typing import Any

from app.core.managed_settings_contract import (
    ALLOWED_SECRET_ENVS,
    MANAGED_SETTINGS_CONTRACT,
    ManagedSettingContract,
)

_ENV_ALIAS_MAP: dict[str, str] = {
    "prod": "prod",
    "production": "prod",
    "stage": "stage",
    "staging": "stage",
    "ci": "ci",
    "dev": "dev",
    "development": "dev",
    "local": "local",
    "test": "ci" if os.getenv("CI") == "true" else "local",
}


def resolve_control_plane_env(raw_value: str | None) -> str:
    candidate = (raw_value or "").strip().lower()
    if not candidate:
        raise ValueError("ENVIRONMENT must be set for control-plane resolution")

    canonical = _ENV_ALIAS_MAP.get(candidate)
    if canonical is None or canonical not in ALLOWED_SECRET_ENVS:
        allowed = ", ".join(ALLOWED_SECRET_ENVS)
        raise ValueError(f"Invalid ENVIRONMENT '{raw_value}'. Allowed values: {allowed}")
    return canonical


def resolve_aws_path_for_key(*, key: str, canonical_env: str) -> str:
    contract = MANAGED_SETTINGS_CONTRACT.get(key)
    if contract is None:
        raise KeyError(f"No managed setting contract defined for key: {key}")
    if canonical_env not in contract.env_scopes:
        scopes = ", ".join(contract.env_scopes)
        raise ValueError(f"Key {key} is not allowed in env '{canonical_env}'. Allowed: {scopes}")

    path = contract.aws_path_template.format(env=canonical_env)
    if contract.classification == "secret" and not path.startswith("/skeldir/"):
        raise ValueError(f"Secret path for {key} must begin with /skeldir/: {path}")
    if contract.classification == "config" and not path.startswith("/skeldir/"):
        raise ValueError(f"Config path for {key} must begin with /skeldir/: {path}")
    return path


def _fetch_value_from_aws(contract: ManagedSettingContract, path: str) -> str:
    region = os.getenv("AWS_REGION", "us-east-2")

    if contract.classification == "secret":
        cmd = [
            "aws",
            "secretsmanager",
            "get-secret-value",
            "--secret-id",
            path,
            "--region",
            region,
            "--query",
            "SecretString",
            "--output",
            "text",
        ]
    else:
        cmd = [
            "aws",
            "ssm",
            "get-parameter",
            "--name",
            path,
            "--with-decryption",
            "--region",
            region,
            "--query",
            "Parameter.Value",
            "--output",
            "text",
        ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError(f"AWS CLI not found while reading {path}: {exc}") from exc
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"AWS read failed for {path}: {stderr}")
    return (result.stdout or "").strip()


def should_enable_control_plane() -> bool:
    return os.getenv("SKELDIR_CONTROL_PLANE_ENABLED", "0") == "1"


def preload_environment_from_control_plane() -> None:
    if not should_enable_control_plane():
        return

    canonical_env = resolve_control_plane_env(os.getenv("ENVIRONMENT"))
    for key, contract in MANAGED_SETTINGS_CONTRACT.items():
        if os.getenv(key):
            continue
        path = resolve_aws_path_for_key(key=key, canonical_env=canonical_env)
        os.environ[key] = _fetch_value_from_aws(contract, path)


def hydrate_settings_from_control_plane(settings_obj: Any) -> None:
    if not should_enable_control_plane():
        return

    canonical_env = resolve_control_plane_env(getattr(settings_obj, "ENVIRONMENT", None))

    for key, contract in MANAGED_SETTINGS_CONTRACT.items():
        current_value = getattr(settings_obj, key, None)
        if current_value is not None:
            continue

        path = resolve_aws_path_for_key(key=key, canonical_env=canonical_env)
        resolved = _fetch_value_from_aws(contract, path)
        if contract.classification == "config":
            maybe_json = resolved.strip()
            if maybe_json.startswith("{") or maybe_json.startswith("["):
                try:
                    setattr(settings_obj, key, json.loads(maybe_json))
                    continue
                except json.JSONDecodeError:
                    pass
        setattr(settings_obj, key, resolved)
