from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

import app.services.tenant_webhook_secrets as tenant_secret_service


@pytest.fixture(autouse=True)
def _reset_cache():
    tenant_secret_service.reset_tenant_webhook_secret_cache_for_testing()
    yield
    tenant_secret_service.reset_tenant_webhook_secret_cache_for_testing()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_b11_p5_plaintext_guard_non_vacuous(tmp_path: Path):
    violating = tmp_path / "violating.py"
    violating.write_text(
        "x = 'shopify_webhook_secret'\n",
        encoding="utf-8",
    )
    root = _repo_root()
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/security/b11_p5_webhook_plaintext_guard.py"),
            "--paths",
            str(violating),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=root,
    )
    assert result.returncode != 0
    assert "forbidden plaintext webhook field reference" in (result.stdout + result.stderr)


def test_b11_p5_plaintext_guard_passes_repo_state():
    root = _repo_root()
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/security/b11_p5_webhook_plaintext_guard.py"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=root,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


@pytest.mark.asyncio
async def test_b11_p5_tenant_secret_cache_bounded_single_decrypt(monkeypatch):
    calls: list[tuple[str, bytes]] = []

    async def fake_decrypt(conn, *, ciphertext: bytes, key: str) -> str:
        calls.append((key, ciphertext))
        return "resolved-secret"

    async def noop_lazy(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(tenant_secret_service, "_decrypt_ciphertext_once", fake_decrypt)
    monkeypatch.setattr(tenant_secret_service, "_maybe_lazy_reencrypt", noop_lazy)
    monkeypatch.setattr(
        tenant_secret_service,
        "resolve_platform_encryption_key_by_id",
        lambda _key_id: "k-material",
    )

    tenant_id = uuid4()
    row = {
        "shopify_webhook_secret_ciphertext": b"cipher-1",
        "shopify_webhook_secret_key_id": "k1",
        "stripe_webhook_secret_ciphertext": None,
        "stripe_webhook_secret_key_id": None,
        "paypal_webhook_secret_ciphertext": None,
        "paypal_webhook_secret_key_id": None,
        "woocommerce_webhook_secret_ciphertext": None,
        "woocommerce_webhook_secret_key_id": None,
    }

    first = await tenant_secret_service.resolve_tenant_webhook_secrets_from_row(
        None,  # type: ignore[arg-type]
        tenant_id=tenant_id,
        row=row,
    )
    second = await tenant_secret_service.resolve_tenant_webhook_secrets_from_row(
        None,  # type: ignore[arg-type]
        tenant_id=tenant_id,
        row=row,
    )

    assert first["shopify_webhook_secret"] == "resolved-secret"
    assert second["shopify_webhook_secret"] == "resolved-secret"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_b11_p5_key_id_addressed_decrypt(monkeypatch):
    selected_key_ids: list[str] = []

    async def fake_decrypt(conn, *, ciphertext: bytes, key: str) -> str:
        return f"plaintext-{key}"

    async def noop_lazy(*args, **kwargs) -> None:
        return None

    def fake_resolve(key_id: str) -> str:
        selected_key_ids.append(key_id)
        return f"material-{key_id}"

    monkeypatch.setattr(tenant_secret_service, "_decrypt_ciphertext_once", fake_decrypt)
    monkeypatch.setattr(tenant_secret_service, "_maybe_lazy_reencrypt", noop_lazy)
    monkeypatch.setattr(
        tenant_secret_service,
        "resolve_platform_encryption_key_by_id",
        fake_resolve,
    )

    tenant_id = uuid4()
    row = {
        "shopify_webhook_secret_ciphertext": b"cipher-shopify",
        "shopify_webhook_secret_key_id": "previous-key",
        "stripe_webhook_secret_ciphertext": None,
        "stripe_webhook_secret_key_id": None,
        "paypal_webhook_secret_ciphertext": None,
        "paypal_webhook_secret_key_id": None,
        "woocommerce_webhook_secret_ciphertext": None,
        "woocommerce_webhook_secret_key_id": None,
    }

    resolved = await tenant_secret_service.resolve_tenant_webhook_secrets_from_row(
        None,  # type: ignore[arg-type]
        tenant_id=tenant_id,
        row=row,
    )

    assert selected_key_ids == ["previous-key"]
    assert resolved["shopify_webhook_secret"] == "plaintext-material-previous-key"


@pytest.mark.asyncio
async def test_b11_p5_mutation_version_triggers_sync_cache_evict(monkeypatch):
    decrypt_calls = 0

    async def fake_decrypt(conn, *, ciphertext: bytes, key: str) -> str:
        nonlocal decrypt_calls
        decrypt_calls += 1
        return f"resolved-{ciphertext.decode('utf-8')}"

    async def noop_lazy(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(tenant_secret_service, "_decrypt_ciphertext_once", fake_decrypt)
    monkeypatch.setattr(tenant_secret_service, "_maybe_lazy_reencrypt", noop_lazy)
    monkeypatch.setattr(
        tenant_secret_service,
        "resolve_platform_encryption_key_by_id",
        lambda _key_id: "k-material",
    )

    tenant_id = uuid4()
    row_v1 = {
        "tenant_updated_at": "2026-02-22T10:00:00+00:00",
        "shopify_webhook_secret_ciphertext": b"cipher-v1",
        "shopify_webhook_secret_key_id": "k1",
        "stripe_webhook_secret_ciphertext": None,
        "stripe_webhook_secret_key_id": None,
        "paypal_webhook_secret_ciphertext": None,
        "paypal_webhook_secret_key_id": None,
        "woocommerce_webhook_secret_ciphertext": None,
        "woocommerce_webhook_secret_key_id": None,
    }
    row_v2 = dict(row_v1)
    row_v2["tenant_updated_at"] = "2026-02-22T11:00:00+00:00"
    row_v2["shopify_webhook_secret_ciphertext"] = b"cipher-v2"

    first = await tenant_secret_service.resolve_tenant_webhook_secrets_from_row(
        None,  # type: ignore[arg-type]
        tenant_id=tenant_id,
        row=row_v1,
    )
    second = await tenant_secret_service.resolve_tenant_webhook_secrets_from_row(
        None,  # type: ignore[arg-type]
        tenant_id=tenant_id,
        row=row_v1,
    )
    third = await tenant_secret_service.resolve_tenant_webhook_secrets_from_row(
        None,  # type: ignore[arg-type]
        tenant_id=tenant_id,
        row=row_v2,
    )

    assert first["shopify_webhook_secret"] == "resolved-cipher-v1"
    assert second["shopify_webhook_secret"] == "resolved-cipher-v1"
    assert third["shopify_webhook_secret"] == "resolved-cipher-v2"
    assert decrypt_calls == 2


@pytest.mark.asyncio
async def test_b11_p5_expand_phase_plaintext_fallback():
    tenant_id = uuid4()
    row = {
        "tenant_updated_at": "2026-02-22T10:00:00+00:00",
        "shopify_webhook_secret": "legacy-plain-secret",
        "shopify_webhook_secret_ciphertext": None,
        "shopify_webhook_secret_key_id": None,
        "stripe_webhook_secret_ciphertext": None,
        "stripe_webhook_secret_key_id": None,
        "paypal_webhook_secret_ciphertext": None,
        "paypal_webhook_secret_key_id": None,
        "woocommerce_webhook_secret_ciphertext": None,
        "woocommerce_webhook_secret_key_id": None,
    }
    resolved = await tenant_secret_service.resolve_tenant_webhook_secrets_from_row(
        None,  # type: ignore[arg-type]
        tenant_id=tenant_id,
        row=row,
    )
    assert resolved["shopify_webhook_secret"] == "legacy-plain-secret"
