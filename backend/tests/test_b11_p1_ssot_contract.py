from __future__ import annotations

import pytest

from app.core.control_plane import resolve_aws_path_for_key, resolve_control_plane_env
from app.core.managed_settings_guard import assert_contract_covers_keys
from app.core.managed_settings_contract import MANAGED_SETTINGS_CONTRACT


def test_control_plane_env_is_fail_closed() -> None:
    assert resolve_control_plane_env("production") == "prod"
    assert resolve_control_plane_env("development") == "dev"
    assert resolve_control_plane_env("stage") == "stage"

    with pytest.raises(ValueError):
        resolve_control_plane_env("qa")


def test_contract_coverage_non_vacuous_unknown_key_fails() -> None:
    settings_keys = set(MANAGED_SETTINGS_CONTRACT.keys()) | {"NEW_UNMAPPED_KEY"}

    with pytest.raises(ValueError, match="Unmapped settings keys"):
        assert_contract_covers_keys(settings_keys, MANAGED_SETTINGS_CONTRACT.keys())


def test_all_paths_resolve_with_canonical_prefix() -> None:
    for key in MANAGED_SETTINGS_CONTRACT:
        path = resolve_aws_path_for_key(key=key, canonical_env="ci")
        assert path.startswith("/skeldir/ci/")
        assert "/secret/" in path or "/config/" in path
