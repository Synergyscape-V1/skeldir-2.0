"""Legacy finance consequence fixtures predate XXV source attestation.

They seed authenticated ingress through the atomic transition rather than the
authentication root, so they intentionally exercise the pre-XXV owner-written
coverage shape. Production forbids disabling source attestation; the dedicated
XXV coverage authority tests opt back into it explicitly.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session", autouse=True)
def _legacy_finance_source_coverage():
    from app.core.config import settings

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        settings,
        "B26_P2_SOURCE_ATTESTATION_REQUIRED",
        False,
        raising=False,
    )
    try:
        yield
    finally:
        monkeypatch.undo()
