import importlib

import pytest


def test_provider_enabled_requires_api_key(monkeypatch):
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:pass@localhost:5432/skeldir_config_test",
    )
    monkeypatch.setenv("LLM_PROVIDER_ENABLED", "true")
    monkeypatch.delenv("LLM_PROVIDER_API_KEY", raising=False)

    import app.core.config as config

    with pytest.raises(ValueError, match="LLM_PROVIDER_API_KEY"):
        importlib.reload(config)
