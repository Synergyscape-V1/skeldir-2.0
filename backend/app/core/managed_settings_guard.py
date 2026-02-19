from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

from app.core.managed_settings_contract import (
    ALLOWED_SECRET_ENVS,
    MANAGED_SETTINGS_CONTRACT,
    iter_managed_setting_contracts,
)

CANONICAL_SECRET_PREFIX = "/skeldir/{env}/secret/"
CANONICAL_CONFIG_PREFIX = "/skeldir/{env}/config/"


def _ensure_import_env() -> None:
    os.environ.setdefault("DATABASE_URL", "postgresql://app_user:app_user@127.0.0.1:5432/skeldir")


def settings_keys() -> set[str]:
    _ensure_import_env()
    from app.core.config import Settings

    return set(Settings.model_fields.keys())


def assert_contract_covers_keys(settings_keys: Iterable[str], contract_keys: Iterable[str]) -> None:
    settings_set = set(settings_keys)
    contract_set = set(contract_keys)
    missing = sorted(settings_set - contract_set)
    extra = sorted(contract_set - settings_set)

    errors: list[str] = []
    if missing:
        errors.append(f"Unmapped settings keys (hard fail): {missing}")
    if extra:
        errors.append(f"Contract keys not present in Settings (hard fail): {extra}")

    if errors:
        raise ValueError("; ".join(errors))


def validate_contract_shape() -> None:
    allowed_envs = set(ALLOWED_SECRET_ENVS)
    for contract in iter_managed_setting_contracts():
        if "{env}" not in contract.aws_path_template:
            raise ValueError(f"{contract.key}: aws_path_template must include '{{env}}'")
        if contract.classification == "secret":
            if not contract.aws_path_template.startswith(CANONICAL_SECRET_PREFIX):
                raise ValueError(
                    f"{contract.key}: secret path must start with {CANONICAL_SECRET_PREFIX}"
                )
        else:
            if not contract.aws_path_template.startswith(CANONICAL_CONFIG_PREFIX):
                raise ValueError(
                    f"{contract.key}: config path must start with {CANONICAL_CONFIG_PREFIX}"
                )

        invalid_envs = sorted(set(contract.env_scopes) - allowed_envs)
        if invalid_envs:
            raise ValueError(f"{contract.key}: invalid env scopes {invalid_envs}")


def snapshot_payload() -> dict[str, object]:
    records = [c.as_dict() for c in iter_managed_setting_contracts()]
    return {
        "allowed_envs": list(ALLOWED_SECRET_ENVS),
        "keys_total": len(records),
        "records": records,
    }


def write_snapshot(path: Path) -> None:
    payload = snapshot_payload()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_guard(snapshot_path: Path, check_drift: bool) -> int:
    keys = settings_keys()
    assert_contract_covers_keys(keys, MANAGED_SETTINGS_CONTRACT.keys())
    validate_contract_shape()

    if check_drift and snapshot_path.exists():
        before = snapshot_path.read_text(encoding="utf-8")
        write_snapshot(snapshot_path)
        after = snapshot_path.read_text(encoding="utf-8")
        if before != after:
            raise ValueError(
                "SSOT snapshot drift detected. Regenerate and commit docs/forensics/evidence/b11_p1/ssot_contract_snapshot.json"
            )
    else:
        write_snapshot(snapshot_path)

    return len(keys)
