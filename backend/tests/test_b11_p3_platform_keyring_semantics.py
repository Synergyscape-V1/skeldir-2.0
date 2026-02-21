from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from app.core.config import settings
from app.core.secrets import (
    reset_crypto_secret_caches_for_testing,
    resolve_platform_encryption_key_by_id,
)
from app.services.platform_credentials import _decrypt_ciphertext_once


def _platform_ring_payload(*, current_key_id: str, keys: dict[str, str], previous_key_ids: list[str] | None = None) -> str:
    payload = {
        "current_key_id": current_key_id,
        "keys": keys,
    }
    if previous_key_ids is not None:
        payload["previous_key_ids"] = previous_key_ids
    return json.dumps(payload)


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setenv("SKELDIR_PLATFORM_KEY_RING_MAX_STALENESS_SECONDS", "1")
    reset_crypto_secret_caches_for_testing()
    yield
    reset_crypto_secret_caches_for_testing()


def test_platform_backward_compat_key_lookup_after_rotation(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PLATFORM_TOKEN_ENCRYPTION_KEY",
        _platform_ring_payload(current_key_id="new", keys={"old": "old-key", "new": "new-key"}, previous_key_ids=["old"]),
    )
    assert resolve_platform_encryption_key_by_id("old") == "old-key"
    assert resolve_platform_encryption_key_by_id("new") == "new-key"
    with pytest.raises(RuntimeError, match="Unknown platform encryption key_id"):
        resolve_platform_encryption_key_by_id("missing")


@pytest.mark.asyncio
async def test_decrypt_ciphertext_executes_single_decrypt_call():
    captured_sql: list[str] = []

    class FakeResult:
        def scalar_one_or_none(self):
            return "plaintext-token"

    class FakeSession:
        async def execute(self, statement, params):
            captured_sql.append(str(statement))
            assert "ciphertext" in params
            assert "key" in params
            return FakeResult()

    value = await _decrypt_ciphertext_once(
        FakeSession(),
        ciphertext=b"abc",
        key="test-key",
    )
    assert value == "plaintext-token"
    assert len(captured_sql) == 1
    assert captured_sql[0].lower().count("pgp_sym_decrypt") == 1


def test_multi_decrypt_guard_non_vacuous(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    fixture = root / "backend/tests/fixtures/forbidden_multi_decrypt_fixture.sql"
    violating = tmp_path / "violating_multi_decrypt.sql"
    violating.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/security/b11_p3_no_multi_decrypt_guard.py"),
            "--paths",
            str(violating),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=root,
    )
    assert result.returncode != 0
    assert "forbidden multi-decrypt" in (result.stdout + result.stderr).lower()
