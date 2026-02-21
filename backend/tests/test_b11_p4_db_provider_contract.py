from __future__ import annotations

import importlib

from app.core.config import settings
from app.core.secrets import get_migration_database_url, validate_runtime_secret_contract


def test_stage_runtime_requires_control_plane_for_db_and_migration(monkeypatch):
    monkeypatch.setenv("SKELDIR_CONTROL_PLANE_ENABLED", "0")
    monkeypatch.setattr(settings, "ENVIRONMENT", "stage")
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://app_user:app_user@127.0.0.1:5432/skeldir")
    monkeypatch.setattr(settings, "MIGRATION_DATABASE_URL", None, raising=False)

    result = validate_runtime_secret_contract("readiness")
    assert not result.ok
    assert "SKELDIR_CONTROL_PLANE_ENABLED" in result.missing


def test_stage_runtime_requires_provider_key_when_llm_enabled(monkeypatch):
    monkeypatch.setenv("SKELDIR_CONTROL_PLANE_ENABLED", "0")
    monkeypatch.setattr(settings, "ENVIRONMENT", "stage")
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://app_user:app_user@127.0.0.1:5432/skeldir")
    monkeypatch.setattr(settings, "MIGRATION_DATABASE_URL", "postgresql://migration:migration@127.0.0.1:5432/skeldir")
    monkeypatch.setattr(settings, "LLM_PROVIDER_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_PROVIDER_API_KEY", None)

    result = validate_runtime_secret_contract("api")
    assert not result.ok
    assert "LLM_PROVIDER_API_KEY" in result.missing


def test_local_migration_url_falls_back_to_runtime_database_url(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "local")
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://app_user:app_user@127.0.0.1:5432/skeldir")
    monkeypatch.setattr(settings, "MIGRATION_DATABASE_URL", None, raising=False)
    monkeypatch.setenv("SKELDIR_CONTROL_PLANE_ENABLED", "0")

    assert get_migration_database_url().startswith("postgresql://app_user:")


def test_database_rotation_contract_reloads_on_process_restart(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "ci")
    monkeypatch.setenv("SKELDIR_CONTROL_PLANE_ENABLED", "0")
    monkeypatch.setattr(
        settings,
        "DATABASE_URL",
        "postgresql://old_user:old_pass@127.0.0.1:5432/skeldir",
    )
    from app.db import session as db_session
    importlib.reload(db_session)
    old_loaded = db_session._ASYNC_DATABASE_URL

    monkeypatch.setattr(
        settings,
        "DATABASE_URL",
        "postgresql://new_user:new_pass@127.0.0.1:5432/skeldir",
    )
    importlib.reload(db_session)
    new_loaded = db_session._ASYNC_DATABASE_URL

    assert "old_user" in old_loaded
    assert "new_user" in new_loaded
