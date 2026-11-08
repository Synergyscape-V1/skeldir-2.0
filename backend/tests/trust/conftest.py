import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def _history_witness_not_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings, "B26_P2_HISTORY_WITNESS_REQUIRED", False, raising=False
    )


@pytest.fixture(autouse=True)
def _source_attestation_not_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """XXV: these modules exercise envelope field shape on fake sessions.

    The sovereign source attestation is a live-database authority: it is
    proven on the production-equivalent lane (xxv-hb03-owner-money and the
    live sweep cell of the mandatory composition proof), not against an
    in-memory fake that cannot hold a signature. Production refuses to start
    with this requirement disabled (Settings.model_post_init), so switching
    it off here cannot leak into a deployment.
    """
    monkeypatch.setattr(
        settings, "B26_P2_SOURCE_ATTESTATION_REQUIRED", False, raising=False
    )
