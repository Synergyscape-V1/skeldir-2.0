import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def _history_witness_not_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings, "B26_P2_HISTORY_WITNESS_REQUIRED", False, raising=False
    )
