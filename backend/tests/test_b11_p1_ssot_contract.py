from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.control_plane import resolve_aws_path_for_key, resolve_control_plane_env
from app.core.managed_settings_guard import assert_contract_covers_keys
from app.core.managed_settings_contract import (
    MANAGED_SETTINGS_CONTRACT,
    process_role_allows,
)


def test_process_database_authority_resolves_per_process_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SKELDIR_CONTROL_PLANE_ENABLED", "1")
    monkeypatch.setenv("SKELDIR_PROCESS_ROLE", "api")
    monkeypatch.setenv("ENVIRONMENT", "prod")
    from app.core import secrets as secrets_module

    seen: list[str] = []

    def _fetch(_contract, path: str) -> str:
        seen.append(path)
        return f"postgresql://{path.rsplit('-', 1)[-1]}@example/db"

    monkeypatch.setattr(secrets_module, "_fetch_value_from_aws", _fetch)
    assert secrets_module.get_database_url().startswith("postgresql://")
    assert seen == ["/skeldir/prod/secret/database/runtime-api-url"]

    seen.clear()
    monkeypatch.setenv("SKELDIR_PROCESS_ROLE", "trust_signer")
    assert secrets_module.get_database_url().startswith("postgresql://")
    assert seen == ["/skeldir/prod/secret/database/runtime-trust_signer-url"]


def test_each_process_role_grants_only_its_task_database_secret() -> None:
    root = Path(__file__).resolve().parents[2]
    matrix = json.loads(
        (root / "contracts-internal/governance/b11_process_authority.v1.json").read_text(
            encoding="utf-8"
        )
    )
    task_paths = matrix["task_database_secrets"]
    assert len(set(task_paths.values())) == len(task_paths)
    shared_path = "/skeldir/{env}/secret/database/runtime-url"
    for process, task_path in task_paths.items():
        secrets = matrix["processes"][process]["secrets"]
        assert task_path in secrets
        assert shared_path not in secrets


def test_process_database_authority_refuses_missing_process_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SKELDIR_CONTROL_PLANE_ENABLED", "1")
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.delenv("SKELDIR_PROCESS_ROLE", raising=False)
    from app.core import secrets as secrets_module

    with pytest.raises(RuntimeError, match="process_role_required"):
        secrets_module.get_database_url()


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


def test_process_roles_scope_migration_authority() -> None:
    assert not process_role_allows("trust_signer", "MIGRATION_DATABASE_URL")
    assert not process_role_allows("auth_ingress", "MIGRATION_DATABASE_URL")
    assert not process_role_allows("api", "MIGRATION_DATABASE_URL")
    assert process_role_allows("migration", "MIGRATION_DATABASE_URL")
    assert process_role_allows("api", "DATABASE_URL")
    assert not process_role_allows("trust_signer", "UNKNOWN_SETTING")


def test_process_roles_scope_b26_witness_and_source_journal() -> None:
    assert process_role_allows(
        "observer_b26_p2", "B26_P2_HISTORY_WITNESS_PRIVATE_KEY_PATH"
    )
    assert not process_role_allows(
        "api", "B26_P2_HISTORY_WITNESS_PRIVATE_KEY_PATH"
    )
    assert process_role_allows(
        "auth_ingress", "B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH"
    )
    assert process_role_allows(
        "observer_b26_p2", "B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH"
    )
    assert not process_role_allows(
        "worker", "B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH"
    )
    assert not process_role_allows("worker", "B26_P2_HISTORY_WITNESS_REQUIRED")
