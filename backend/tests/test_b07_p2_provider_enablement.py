import importlib

import pytest


def _reload_config_module():
    import app.core.config as config

    return importlib.reload(config)


def test_provider_enabled_requires_api_key(monkeypatch):
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:pass@localhost:5432/skeldir_config_test",
    )
    monkeypatch.setenv("LLM_PROVIDER_ENABLED", "true")
    monkeypatch.delenv("LLM_PROVIDER_API_KEY", raising=False)

    with pytest.raises(ValueError, match="LLM_PROVIDER_API_KEY"):
        _reload_config_module()


def test_provider_disabled_without_api_key_is_allowed(monkeypatch):
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:pass@localhost:5432/skeldir_config_test",
    )
    monkeypatch.setenv("LLM_PROVIDER_ENABLED", "false")
    monkeypatch.delenv("LLM_PROVIDER_API_KEY", raising=False)

    config = _reload_config_module()

    assert config.settings.LLM_PROVIDER_ENABLED is False
    assert config.settings.LLM_PROVIDER_API_KEY is None
